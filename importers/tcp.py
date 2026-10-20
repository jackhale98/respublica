"""Typed transcriptions from the Text Creation Partnership (decision 66).

The TCP keyed early printed books from page images and released its Phase I
texts under CC0. Its Evans-TCP texts (American imprints to 1800) are TEI P5
XML, one file per book, kept in the TCP's public repositories
(textcreationpartnership/{TCP number}); each file used is a raw source.

Where a TCP text of the printing exists, it is the text, as keyed:

- Paragraphs are the TEI's `head`, `p` and `closer` elements of the division
  named (`Text.div`); a closer's parts (the signature, the attestation, the
  place and date) are one passage. Quotations (`q`) and highlighting (`hi`)
  are read as text, without marks the printing does not have. A `figure`
  (a woodcut and its caption) is left out.
- A word broken at a line's end (`g ref="char:EOLhyphen"` or
  `char:EOLunhyphen`) is rejoined without the hyphen, as the scans' words are.
- What the keyers could not read is never filled in: a `gap` keeps the
  transcription's own placeholder (`•` for each letter, `〈…〉` for a span),
  and an unreadable stop (`g ref="char:punc"`) its `▪`; the word holding one
  is marked as uncertain, for a person to read off the page.
- The long s (ſ) and the printing's spelling are kept as keyed.

`cross_check` reads the text word by word against the Internet Archive's OCR
of a scan of the same printing (the Library's method, decision 55): where the
scan reads a different word, one the clean texts know (`ocr.Vocabulary`), the
word is marked as uncertain with the scan's reading beside it, never
changed. Figures are not compared (OCR misreads them, and they are no
known word). A reading that is no word (OCR's garble of old type) is not a
reading of another word and is not counted; the long s that OCR reads as f
("firft") is not a difference.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from importers.ocr import Reference, align, is_word, key, parse_djvu_xml, text_tokens
from tools.common import raw_path

TEI = "{http://www.tei-c.org/ns/1.0}"
JOIN = "\x00"  # a line-end break inside a word
GAP_CHARS = "•〈…〉▪"


@dataclass(frozen=True)
class Scan:
    source: str  # source id of its DjVu XML
    item: str  # Internet Archive item (page links)


@dataclass(frozen=True)
class Text:
    source: str  # source id of the TEI file
    tcp: str  # TCP number ("N11512")
    evans: str  # "Evans 14550"
    div: str  # the type of the TEI division that holds the text
    printing: str  # the printing, as the edition note names it
    scan: Scan | None = None  # a scan of the same printing, to check against


@dataclass
class Paragraph:
    kind: str  # head | p | closer
    text: str
    gaps: list[tuple[int, int]]  # character spans of the words holding something the keyers could not read
    pages: list[str] = field(default_factory=list)


def _page_of(pb: ET.Element) -> str:
    """A page break's printed number, or the image's place in the TCP's image
    set, in brackets, for an unnumbered page ("[1]")."""
    if pb.get("n"):
        return pb.get("n")
    m = re.search(r"_(\d{4})_", pb.get("facs", ""))
    return f"[{int(m.group(1))}]" if m else "[?]"


class _Reader:
    def __init__(self, page: str):
        self.page = page
        self.pieces: list[tuple[str, bool]] = []  # (text, unreadable)
        self.pages: list[str] = [page]

    def read(self, el: ET.Element) -> None:
        tag = el.tag.replace(TEI, "")
        if tag == "pb":
            self.page = _page_of(el)
            if self.page not in self.pages:
                self.pages.append(self.page)
        elif tag == "g" and el.get("ref") in ("char:EOLhyphen", "char:EOLunhyphen"):
            self.pieces.append((JOIN, False))
        elif tag == "g" and el.get("ref") == "char:punc":
            self.pieces.append(((el.text or "▪").strip() or "▪", True))
        elif tag == "gap":
            desc = el.find(f"{TEI}desc")
            self.pieces.append(((desc.text if desc is not None and desc.text else "〈…〉").strip(), True))
        elif tag == "figure":
            pass
        else:
            if el.text:
                self.pieces.append((el.text, False))
            for child in el:
                self.read(child)
                if child.tail:
                    self.pieces.append((child.tail, False))
            return
        # (The tail of a leaf element is read by its parent.)

    def paragraph(self, kind: str) -> Paragraph:
        chars: list[tuple[str, bool]] = []
        for text, gap in self.pieces:
            if text == JOIN:
                while chars and chars[-1][0].isspace():
                    chars.pop()
                chars.append((JOIN, False))
                continue
            for c in text:
                if c.isspace():
                    if not chars or chars[-1][0] in (" ", JOIN):
                        continue
                    chars.append((" ", False))
                else:
                    chars.append((c, gap))
        out: list[tuple[str, bool]] = [c for c in chars if c[0] != JOIN]
        while out and out[-1][0] == " ":
            out.pop()
        text = "".join(c for c, _ in out)
        gaps = []
        for m in re.finditer(r"\S+", text):
            if any(out[i][1] for i in range(m.start(), m.end())):
                gaps.append((m.start(), m.end()))
        return Paragraph(kind, text, gaps, self.pages)


def paragraphs(t: Text) -> list[Paragraph]:
    root = ET.parse(raw_path(t.source)).getroot()
    body = root.find(f"{TEI}text")
    page = "[?]"
    found = None
    for el in body.iter():
        tag = el.tag.replace(TEI, "")
        if tag == "pb":
            page = _page_of(el)
        if tag == "div" and el.get("type") == t.div:
            found = el
            break
    if found is None:
        raise ValueError(f"{t.source}: no division of type {t.div!r}")
    out = []
    for child in found:
        tag = child.tag.replace(TEI, "")
        if tag == "pb":
            page = _page_of(child)
            continue
        if tag not in ("head", "p", "closer"):
            raise ValueError(f"{t.source}: an unexpected {tag!r} in the division")
        r = _Reader(page)
        r.read(child)
        page = r.page
        p = r.paragraph(tag)
        if p.text:
            out.append(p)
    return out


def gap_spans(p: Paragraph) -> list[dict]:
    """The words holding a gap, as uncertain spans: the transcription's
    reading is the only one."""
    return [{"end": e, "readings": {"primary": p.text[s:e]}, "start": s} for s, e in p.gaps]


def fold(token: str) -> str:
    """A word's letters for comparison: the long s is an s, and OCR's f for
    the long s is not a difference (both become s)."""
    return key(token.replace("ſ", "s")).replace("f", "s")


def scan_reference(scan: Scan) -> tuple[Reference, list[int]]:
    """The scan's OCR as a reference (its words compared by `fold`), and the
    leaf of each of its words."""
    tokens, leaves = [], []
    for page in parse_djvu_xml(raw_path(scan.source)):
        words = text_tokens("\n".join(line.text for para in page.paras for line in para.lines))
        tokens += words
        leaves += [page.leaf] * len(words)
    ref = Reference("scan", "")
    ref.tokens = tokens
    ref.keys = [fold(t) for t in tokens]
    for i in range(len(ref.keys) - 3):
        k = tuple(ref.keys[i:i + 4])
        if all(k):
            ref.index.setdefault(k, []).append(i)
    return ref, leaves


def cross_check(t: Text, paras: list[Paragraph], known: set[str]) -> list[tuple[list[dict], list[int]]]:
    """For each paragraph, its uncertain spans (its gaps, and the words the
    scan reads as another known word) and the scan's leaves it is on."""
    ref, leaf_of = scan_reference(t.scan)
    folded = {fold(w) for w in known}
    hints: dict[str, int] = {}
    out = []
    for p in paras:
        words = list(re.finditer(r"\S+", p.text))
        folded_words = [fold(m.group(0)) or m.group(0) for m in words]
        first = ref.locate(folded_words, hints.get("scan", 0))
        readings = align(folded_words, [ref], hints)
        spans = []
        gaps = set(p.gaps)
        for m, r in zip(words, readings):
            mine, scan = m.group(0), r.get("scan")
            span = {"end": m.end(), "readings": {"primary": mine}, "start": m.start()}
            if (m.start(), m.end()) in gaps:
                if scan:
                    span["readings"]["scan"] = scan
                spans.append(span)
            elif scan and not re.search(r"\d", mine) and fold(scan) != fold(mine) and len(fold(scan)) > 1 and is_word(fold(scan)) \
                    and fold(scan) in folded:
                span["readings"]["scan"] = scan
                spans.append(span)
        # The scan's pages the paragraph is on: from where it was found to
        # the last word matched.
        leaves = []
        if first is not None and any("scan" in r for r in readings):
            last = min(hints["scan"], len(leaf_of)) - 1
            leaves = sorted({leaf_of[i] for i in range(min(first + 8, last), last + 1)})
        out.append((spans, leaves))
    return out
