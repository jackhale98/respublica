"""The Library of Congress's typed transcription of Elliot's Debates
(decision 68).

"A Century of Lawmaking for a New Nation" (American Memory, Law Library of
Congress) keyed Elliot's Debates, vols. 1-4, in 1997: "a machine readable
transcription ... intended to have an accuracy rate of 99.95 percent or
greater", from the 1836 Washington printing (the standard pagination, the
same as the 1907 Lippincott printing the Internet Archive's scans are of).
tile.loc.gov serves each volume as XML (`lled00N.xml`): `<p>` and `<head>`
in `<div>`s, `<pageinfo>` at every page with the printed page number
(`<printpgno>`), italics as `<hi>`, footnotes as `<note>` after the
paragraph whose `<anchor>` they belong to. The file's header states its
rights ("Publication exempt from copyright protection"), and the
collection's rights page says its contents "are in the public domain and
are free to use and reuse".

This module reads a volume into paragraphs, each with the printed pages it
is on. It changes no word: the XML's own layout is undone only where it is
plainly the file's, not the book's:

  * the XML was pretty-printed from SGML: a line break and indentation were
    put before each inline element (`<hi>`, `<anchor>`) and a line break
    after it ("Thursday\\n, January"), which are dropped; other runs of
    white space are one space;
  * the printer's signature marks at the foot of a page ("42", "4 3") are
    keyed after a line break (`<lb/>`) just before the next page; they are
    left out, as for the scans (`ocr.set_aside`);
  * the library stamp on the first page (`<stamped>`) is not the book's;
  * a word keyed broken across a page ("in-" and "ference", three times in
    vols. 2-4) is rejoined, as in the scans;
  * a table is its cells in the file's order, one paragraph; a column rule
    or leader (`<hsep/>`) and any other line break are a space.

The transcription marks no illegible words (it has no `<gap>` or
`<unclear>`); the importer stops if a volume has an element it does not
know, so a marker added upstream cannot pass unnoticed.
"""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache

from importers.ocr import Reference, align
from tools.common import raw_path

URL = "https://tile.loc.gov/storage-services/service/ll/llscd/{item}/{item}.xml"
VOLUMES = {n: f"lled00{n}" for n in (2, 3, 4)}
LICENSE = ("Public domain. The file's header (<copyright>): \"Publication exempt from copyright protection; refer to "
           "accompanying matter.\" The collection's rights page "
           "(https://www.loc.gov/collections/century-of-lawmaking/about-this-collection/rights-and-access/, read "
           "2026-10-20 as JSON, ?fo=json): \"The contents of this collection are in the public domain and are free to "
           "use and reuse. Credit Line: Law Library of Congress.\" A transcription made by the Library of Congress "
           "(American Memory, 1997) of a book published in 1836.")


def source_id(vol: int) -> str:
    return f"loc-lled-{vol:03d}-xml"


class FormatError(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise FormatError(msg)


@dataclass
class Para:
    kind: str  # "head", "text" (a <p>, an <item>'s <p>, a table) or "note"
    text: str
    pages: list[str]  # printed pages it is on, in order
    div: int  # which top-level division of the body it is in (0, 1, ...)
    note_of: int | None = None  # a note: the index of the paragraph its anchor is in


@dataclass
class Volume:
    vol: int
    title: str
    rights: str
    accuracy: str
    paras: list[Para] = field(default_factory=list)
    heads: list[str] = field(default_factory=list)  # each top-level division's heading
    signature_marks: int = 0


# Elements the reader knows. Anything else stops the import.
BLOCK = {"p", "head", "note", "table", "list", "item", "div", "tabletext"}
INLINE = {"hi", "anchor", "lb", "hsep", "xref", "pageinfo", "stamped", "blankpage", "cell", "controlpgno",
          "printpgno"}

# A signature mark keyed at the foot of a page: a line break, one or two
# numbers, then the next page (inside the paragraph, or after it).
SIGNATURE = re.compile(r"<lb/>\s*(\d{1,3}(?:\s+\d{1,3})?)\s*(?=<pageinfo>|</p>\s*<pageinfo>)")
# Pretty-printing: a line break and indentation before an inline element,
# a line break after it.
BEFORE_INLINE = re.compile(r"\n[ \t]*(?=<(?:hi|anchor)\b)")
AFTER_INLINE = re.compile(r"(</hi>|</anchor>)\n")


def clean_markup(xml: str) -> tuple[str, int]:
    """The XML with the pretty-printer's white space around inline elements
    and the keyed signature marks taken out; and how many marks."""
    xml, marks = SIGNATURE.subn("", xml)
    xml = BEFORE_INLINE.sub("", xml)
    xml = AFTER_INLINE.sub(r"\1", xml)
    return xml, marks


# Where a page turns inside a paragraph. A word the transcription keeps
# broken across the turn ("in-" at the foot of p. 589, "ference" at the
# head of p. 590) is rejoined, as a word broken at a line or page end is
# in the scans (`ocr.join_across`); elsewhere the turn is a space.
PAGE_BREAK = "\ue000"
BROKEN = re.compile(r"(?<=[A-Za-z]{2})-\s*\ue000\s*(?=[a-z])")


def join_pages(s: str) -> str:
    return BROKEN.sub("", s).replace(PAGE_BREAK, " ")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


@lru_cache(maxsize=None)
def volume(vol: int) -> Volume:
    """A volume's paragraphs, from its raw XML."""
    return parse(raw_path(source_id(vol)).read_bytes().decode("utf-8"), vol)


def parse(raw: str, vol: int) -> Volume:
    """A volume's paragraphs, from the text of its XML file."""
    _expect(raw.lstrip().startswith("<?xml") and "<tei2>" in raw, f"{source_id(vol)}: not an American Memory XML file")
    xml, marks = clean_markup(raw)
    root = ET.fromstring(xml)
    header = root.find("teiheader")
    title = norm("".join(header.find("filedesc/titlestmt/title").itertext()))
    rights = norm("".join(header.find("filedesc/sourcedesc/copyright").itertext()))
    accuracy = norm("".join(header.find("encodingdesc/editorialdecl").itertext()))
    _expect(f"Volume {vol}]" in title, f"{source_id(vol)}: the header names another volume: {title!r}")
    for el in root.find("text").iter():
        _expect(el.tag in BLOCK | INLINE | {"text", "front", "body", "back"},
                f"{source_id(vol)}: unknown element <{el.tag}>")
    out = Volume(vol, title, rights, accuracy, signature_marks=marks)
    page = _PageCounter(root)
    body = root.find("text/body")
    for el in root.find("text"):
        if el.tag == "pageinfo":
            page.turn(el)
        elif el is body:
            div = -1
            for top in body:
                if top.tag == "pageinfo":
                    page.turn(top)
                    continue
                _expect(top.tag == "div", f"{source_id(vol)}: <{top.tag}> outside a division of the body")
                div += 1
                head = top.find("head")
                out.heads.append(norm("".join(_text(head, page))) if head is not None else "")
                _blocks(top, out, page, div)
        else:
            _skip(el, page)
    return out


class _PageCounter:
    """The printed page at each point of the file. A page the transcription
    numbers is that number; an unnumbered page (a section's first) is the
    next numbered page less the pages between them."""

    def __init__(self, root: ET.Element):
        infos = list(root.iter("pageinfo"))
        self.printed: dict[int, str] = {}
        ctrl = [int(i.find("controlpgno").text) for i in infos]
        nums = [(i.find("printpgno").text or "").strip() for i in infos]
        for k, (c, n) in enumerate(zip(ctrl, nums)):
            if n:
                self.printed[c] = n
                continue
            nxt = next(((ctrl[j], nums[j]) for j in range(k + 1, len(infos)) if nums[j].isdigit()), None)
            self.printed[c] = str(int(nxt[1]) - (nxt[0] - c)) if nxt else ""
        self.current = ""

    def turn(self, info: ET.Element) -> None:
        self.current = self.printed[int(info.find("controlpgno").text)]


def _skip(el: ET.Element, page: _PageCounter) -> None:
    for x in el.iter("pageinfo"):
        page.turn(x)


def _text(el: ET.Element, page: _PageCounter) -> list[str]:
    """The words of a heading (pages not turned)."""
    parts = [el.text or ""]
    for c in el:
        parts += [" "] if c.tag in ("lb", "hsep") else _text(c, page) if c.tag in ("hi", "anchor") else []
        parts.append(c.tail or "")
    return parts


class _Walker:
    """Paragraphs in document order. A paragraph is a `<p>`, `<head>` or
    table; a list inside a paragraph ends it, its items are paragraphs of
    their own, and the words after it begin a new one. A note is set aside
    and follows the paragraph its anchor is in."""

    def __init__(self, out: Volume, page: _PageCounter, div: int):
        self.out, self.page, self.div = out, page, div
        self.parts: list[str] = []
        self.pages: list[str] = []
        self.kind = "text"
        self.notes: list[ET.Element] = []

    def start(self, kind: str) -> None:
        self.flush()
        self.kind, self.parts, self.pages = kind, [], [self.page.current]

    def flush(self) -> None:
        text = norm(join_pages("".join(self.parts)))
        if text:
            self.out.paras.append(Para(self.kind, text, self.pages, self.div))
        at = len(self.out.paras) - 1
        notes, self.notes, self.parts = self.notes, [], []
        for n in notes:
            sub = _Walker(self.out, self.page, self.div)
            sub.kind, sub.pages = "note", [self.page.current]
            sub.inline(n)
            text = norm(join_pages("".join(sub.parts)))
            _expect(bool(text) and not sub.notes, "an empty or nested note")
            self.out.paras.append(Para("note", text, sub.pages, self.div, note_of=at))

    def turn(self, info: ET.Element) -> None:
        self.page.turn(info)
        if self.page.current not in self.pages:
            self.pages.append(self.page.current)

    def inline(self, el: ET.Element) -> None:
        self.parts.append(el.text or "")
        for c in el:
            if c.tag == "pageinfo":
                self.turn(c)
                self.parts.append(PAGE_BREAK)
            elif c.tag == "note":
                self.notes.append(c)
            elif c.tag in ("lb", "hsep", "blankpage", "xref"):
                self.parts.append(" ")
            elif c.tag == "stamped":
                pass
            elif c.tag in ("hi", "anchor", "cell", "tabletext", "p"):
                self.inline(c)
                if c.tag in ("cell", "p"):
                    self.parts.append(" ")
            elif c.tag == "list":
                kind = self.kind
                self.block(c)
                self.start(kind)  # the words after the list
            else:
                raise FormatError(f"<{c.tag}> inside <{el.tag}>")
            self.parts.append(c.tail or "")

    def block(self, el: ET.Element) -> None:
        for c in el:
            if c.tag == "pageinfo":
                self.page.turn(c)
            elif c.tag in ("div", "list", "item"):
                self.block(c)
            elif c.tag in ("p", "head", "table"):
                self.start("head" if c.tag == "head" else "text")
                self.inline(c)
                self.flush()
            elif c.tag == "note":
                # A note between paragraphs belongs to the paragraph before.
                self.notes.append(c)
                self.flush()
            elif c.tag in ("stamped", "blankpage", "xref", "lb", "hsep", "anchor"):
                continue
            else:
                raise FormatError(f"<{c.tag}> inside <{el.tag}>")


def _blocks(el: ET.Element, out: Volume, page: _PageCounter, div: int) -> None:
    w = _Walker(out, page, div)
    w.block(el)
    w.flush()


# ------------------------------------------------------------ as a tie-breaker


# The scans read a ligature as its letters ("Achaean" for "Achæan").
LIGATURES = str.maketrans({"æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe"})


def plain(text: str) -> str:
    """Text for lining up with OCR: a diaeresis ("reëlect") is dropped and a
    ligature spelled out, so the word has the letters the scans read, and a dash is a word of its
    own, as the scans read it ("country—with" is "country — with")."""
    text = "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
    text = text.translate(LIGATURES)
    return re.sub(r"\s*—\s*", " — ", text)


@lru_cache(maxsize=None)
def reference(vol: int, div: int = 0) -> Reference:
    """The text of one division of the body (vol. 3, 0: Virginia), as one
    stream of words to line scans' words up with."""
    paras = [p for p in volume(vol).paras if p.div == div and p.kind != "note"]
    return Reference("loc", "\n\n".join(plain(p.text) for p in paras))


def readings(tokens: list[str], ref: Reference, hints: dict[str, int]) -> list[str | None]:
    """The transcription's reading of each of a run of a scan's words (None
    where it has none, "" where it reads the word together with the one
    before), as `library.readings`."""
    if not tokens:
        return []
    return [r.get(ref.name) for r in align(tokens, [ref], hints)]


# ------------------------------------------------------------ fetching


def cmd_fetch() -> None:
    """Record the transcriptions of Elliot vols. 2-4 as raw sources."""
    from tools.common import load_manifest
    from tools.fetch import add_source
    have = {e["id"] for e in load_manifest()}
    for vol, item in VOLUMES.items():
        sid = source_id(vol)
        if sid in have:
            continue
        add_source(sid, URL.format(item=item), LICENSE,
                   f"Jonathan Elliot, ed., The Debates in the Several State Conventions on the Adoption of the Federal "
                   f"Constitution, vol. {vol} (Washington: printed for the editor, 1836): the Library of Congress's "
                   f"typed transcription (A Century of Lawmaking for a New Nation, American Memory, 1997; item "
                   f"{item}), as XML with the printed page numbers. Its header: \"This transcription is intended to "
                   f"have an accuracy rate of 99.95 percent or greater.\"", ext=".xml")
        v = volume.__wrapped__(vol)
        print(sid, v.title, "|", v.rights, flush=True)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["fetch"]:
        cmd_fetch()
