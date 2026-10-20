"""Typed transcriptions from the Text Creation Partnership (decision 69).

The TCP keyed early printed books by hand from page images and released its
Phase I texts under CC0. Its Evans-TCP texts (American imprints to 1800) are
TEI P5 XML, one file per book in the TCP's public repositories
(github.com/textcreationpartnership/{TCP number}), pinned here to a commit
and kept as raw sources (`python -m importers.tcp fetch`).

`read` turns a file into its divisions and their blocks (headings,
paragraphs, a letter's salutation, date line and signature, notes), each
with the printed page it is on. What the TCP marks is kept as it marks it:

- a word broken at a line end (`<g ref="char:EOLhyphen"/>`, or
  `char:EOLunhyphen`) is joined, as the TCP's own reading of it;
- what the keyers could not read is never filled in: a `gap` keeps the
  transcription's own placeholder (its `desc`: `•` for a letter, `〈◊〉`
  for a word, `〈…〉` for more), and a stop they could not make out its `▪`;
  the word that holds one is a `gap` of the block (`gap_spans`);
- the long s (ſ) and the printing's spelling are kept as keyed;
- type the TCP sets apart (`hi`, mostly italic) is an emphasis span;
- a note is read as a block of its own, its mark (`n`, "*") standing where
  the note is anchored; items of a list inside a paragraph begin new lines;
- a page without a printed number is numbered from the next numbered page,
  in brackets ("[3]").

The importer of new works (`importers/pamphlets.py`) takes the TCP text as
the text. The ratification importer uses it only as a tie-breaker between
scans (`reference`, `readings`; decision 69), as it uses the
Anti-Federalist Library (decision 55).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache

from importers.ocr import Reference, align
from tools.common import raw_path

TEI = "{http://www.tei-c.org/ns/1.0}"
GAP_MARKS = "•◊…▪"

# TCP number -> the commit of its repository the file is pinned to.
TEXTS = {
    "N16599": "fcace6de9e18b1b5b4c257bb17ad3d70e970b372",
    "N16431": "6fdb10c9ee94639d3c54564a1bafae5a533e2bf9",
    "N16481": "0ee6facbbd1dfcfbcdc156fd150a12fcbd380240",
    "N16378": "f3dfd68f63c10749115a0dec5c4150b749108dce",
    "N16445": "6fe82e912780c613d1a8b24311edfed92ffa49d2",
    "N16126": "3cdf2ac34efd8db4ed3383dda4b719957e022c56",
    "N16546": "6e7d414b83757497cad41e7eb0539cf482a1bb3a",
    "N16547": "81467b24a8ca827e8575564c5081f4ba830f1a55",
}
RAW_URL = "https://raw.githubusercontent.com/textcreationpartnership/{tcp}/{commit}/{tcp}.xml"
REPO_URL = "https://github.com/textcreationpartnership/{tcp}"
LICENSE = ("CC0 1.0 Universal (the TEI header's availability statement: \"This Phase I text is available for "
           "reuse, according to the terms of Creative Commons 0 1.0 Universal\").")


def source_id(tcp: str) -> str:
    """The manifest id of a TCP file: "tcp-n16599"."""
    return f"tcp-{tcp.lower()}"


def tag(el: ET.Element) -> str:
    return el.tag.removeprefix(TEI)


def words(el: ET.Element | None) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


# ------------------------------------------------------------ the header


@dataclass
class Header:
    tcp: str  # "N16431"
    evans: str  # "Evans 21112"
    title: str
    authors: list[str]  # the catalogue's headings ("Warren, Mercy Otis, 1728-1814.")
    extent: str  # "22, [2] p. ; 21 cm. (8vo)"
    publisher: str
    place: str
    date: str
    notes: list[str]  # the catalogue's notes on the printing
    licence: str


def header(sid: str) -> Header:
    """The TCP's record of the text and of the printing it was keyed from."""
    root = _root(sid)
    pub = root.find(f"{TEI}teiHeader/{TEI}fileDesc/{TEI}publicationStmt")
    ids = {i.get("type"): (i.text or "").strip() for i in pub.iter(f"{TEI}idno")}
    bibl = root.find(f"{TEI}teiHeader/{TEI}fileDesc/{TEI}sourceDesc/{TEI}biblFull")
    imprint = bibl.find(f"{TEI}publicationStmt")
    return Header(
        tcp=ids.get("TCP", ""), evans=ids.get("STC", ""),
        title=words(bibl.find(f"{TEI}titleStmt/{TEI}title")),
        authors=[words(a) for a in bibl.findall(f"{TEI}titleStmt/{TEI}author")],
        extent=words(bibl.find(f"{TEI}extent")), publisher=words(imprint.find(f"{TEI}publisher")),
        place=words(imprint.find(f"{TEI}pubPlace")), date=words(imprint.find(f"{TEI}date")),
        notes=[words(n) for n in bibl.findall(f"{TEI}notesStmt/{TEI}note")],
        licence=words(pub.find(f"{TEI}availability")))


@lru_cache(maxsize=None)
def _root(sid: str) -> ET.Element:
    return ET.parse(raw_path(sid)).getroot()


# ------------------------------------------------------------ the text


@dataclass
class Block:
    kind: str  # head | p | salute | dateline | signed | trailer | bibl | l | note | byline
    text: str
    pages: list[str]
    gaps: list[tuple[int, int]] = field(default_factory=list)  # words holding a gap
    emphasis: list[tuple[int, int]] = field(default_factory=list)
    notes: list["Block"] = field(default_factory=list)  # notes anchored in it
    mark: str | None = None  # a note's mark


@dataclass
class Div:
    type: str
    n: str | None
    part: str  # front | body | back
    blocks: list[Block] = field(default_factory=list)  # its own, not its divisions'
    divs: list["Div"] = field(default_factory=list)

    def heads(self) -> list[str]:
        return [b.text for b in self.blocks if b.kind == "head"]

    def walk(self) -> list["Div"]:
        """This division and those inside it, in document order."""
        return [self, *(d for c in self.divs for d in c.walk())]


JOIN, LINE = "\x00", "\x01"  # a line-end break inside a word; a new line
INLINE = {"hi", "q", "abbr", "seg", "date", "bibl", "l", "lg", "name", "foreign", "expan", "orig", "sic", "corr",
          "choice", "reg", "num", "ref", "label", "add", "unclear", "list", "item", "p", "salute", "signed", "dateline",
          "head", "trailer", "opener", "closer", "epigraph", "byline", "argument", "quote"}
# Parts that stand apart from the words around them inside a block.
APART = {"l", "p", "bibl", "salute", "signed", "dateline", "head", "trailer", "opener", "closer", "epigraph", "byline",
         "argument", "quote"}
CONTAINERS = {"opener", "closer", "q", "epigraph", "list", "lg", "argument", "quote"}
BLOCKS = {"head", "p", "salute", "dateline", "signed", "trailer", "bibl", "l", "byline", "item", "note"}


def page_labels(root: ET.Element) -> dict[int, str]:
    """Each page break's printed page: its number, or for an unnumbered page
    next to a numbered one the number that implies, in brackets ("[3]").
    Other unnumbered pages (a title page, a dedication) get none (""): the
    TCP's images leave out some blank pages, so counting further is a guess."""
    pbs = list(root.find(f"{TEI}text").iter(f"{TEI}pb"))
    out: dict[int, str] = {}
    for i, pb in enumerate(pbs):
        n = pb.get("n") or ""
        after = (pbs[i + 1].get("n") or "") if i + 1 < len(pbs) else ""
        before = (pbs[i - 1].get("n") or "") if i else ""
        if not n and after.isdigit() and int(after) > 1:
            n = f"[{int(after) - 1}]"
        elif not n and before.isdigit():
            n = f"[{int(before) + 1}]"
        out[id(pb)] = n
    return out


def page_list(sid: str) -> list[str]:
    """The printed page of each page break, in order."""
    root = _root(sid)
    labels = page_labels(root)
    return [labels[id(pb)] for pb in root.find(f"{TEI}text").iter(f"{TEI}pb")]


class _Reader:
    """The characters of one block, each with whether it is emphasized and
    whether the keyers could not read it, and the pages it is on."""

    def __init__(self, labels: dict[int, str], page: str | None):
        self.labels, self.page = labels, page
        self.chars: list[tuple[str, bool, bool]] = []
        self.pages: list[str] = [page] if page else []
        self.notes: list[Block] = []

    def emit(self, text: str, em: bool = False, gap: bool = False) -> None:
        self.chars += [(c, em, gap) for c in text]

    def turn(self, pb: ET.Element) -> None:
        self.page = self.labels[id(pb)]
        if self.page and self.page not in self.pages:
            self.pages.append(self.page)

    def read(self, el: ET.Element, em: bool = False) -> None:
        """An element's text, its children and their tails."""
        if el.text:
            self.emit(el.text, em)
        for child in el:
            t = tag(child)
            if t == "pb":
                self.turn(child)
            elif t == "g" and child.get("ref") in ("char:EOLhyphen", "char:EOLunhyphen"):
                self.emit(JOIN)
            elif t == "g":
                # A stop the keyers could not make out ("▪"), or another special character.
                self.emit(words(child) or "▪", em, gap=child.get("ref") == "char:punc")
            elif t == "gap":
                self.emit(words(child.find(f"{TEI}desc")) or "〈…〉", em, gap=True)
            elif t == "note":
                r = _Reader(self.labels, self.page)
                r.read(child)
                self.notes.append(r.block("note", mark=child.get("n")))
                if child.get("n"):
                    self.emit(child.get("n"), em)
            elif t in ("lb", "figure"):
                self.emit(" ")
            elif t == "item":
                self.emit(LINE)
                self.read(child, em)
            elif t in INLINE:
                if t in APART:
                    self.emit(" ")
                self.read(child, em or t == "hi")
                if t in APART:
                    self.emit(" ")
            elif t == "desc":
                pass
            else:
                raise ValueError(f"TCP text: no rule for <{t}>")
            if child.tail:
                self.emit(child.tail, em)

    def block(self, kind: str, mark: str | None = None) -> Block:
        """The characters read so far as one block: whitespace collapsed, a
        word broken at a line end joined, the words holding a gap and the
        emphasized runs as character spans."""
        out: list[tuple[str, bool, bool]] = []
        joined = False
        for c, em, gap in self.chars:
            if c == JOIN:
                while out and out[-1][0] == " ":
                    out.pop()
                joined = True
                continue
            if c == LINE or c.isspace():
                if joined or not out:
                    continue
                if c == LINE:
                    while out and out[-1][0] == " ":
                        out.pop()
                    if out and out[-1][0] != "\n":
                        out.append(("\n", False, False))
                elif out[-1][0] not in (" ", "\n"):
                    out.append((" ", em, False))
                continue
            joined = False
            out.append((c, em, gap))
        while out and out[-1][0] in (" ", "\n"):
            out.pop()
        text = "".join(c for c, _, _ in out)
        gaps = [(m.start(), m.end()) for m in re.finditer(r"\S+", text) if any(out[i][2] for i in range(m.start(), m.end()))]
        emphasis, start = [], None
        for i, (c, em, _) in enumerate([*out, (" ", False, False)]):
            if em and not c.isspace() and start is None:
                start = i
            elif start is not None and (not em or c == "\n"):
                end = i
                while text[end - 1].isspace():
                    end -= 1
                emphasis.append((start, end))
                start = None
        return Block(kind, text, self.pages, gaps, emphasis, self.notes, mark)


def read(sid: str) -> list[Div]:
    """The divisions of a TCP text (front matter, body and back matter), in order."""
    root = _root(sid)
    labels = page_labels(root)
    state = {"page": None}
    out: list[Div] = []

    def blocks_of(el: ET.Element, div: Div, kind: str | None = None) -> None:
        for child in el:
            t = tag(child)
            if t == "pb":
                state["page"] = labels[id(child)]
            elif t == "div":
                sub = Div(child.get("type", ""), child.get("n"), div.part)
                div.divs.append(sub)
                blocks_of(child, sub)
            elif t in CONTAINERS and ((child.text or "").strip() or any((g.tail or "").strip() for g in child)):
                # Words loose in a quotation, beside its parts (a text and
                # its reference): one block.
                r = _Reader(labels, state["page"])
                r.read(child)
                state["page"] = r.page
                div.blocks.append(r.block(kind or "p"))
                div.blocks += r.notes
            elif t in CONTAINERS:
                blocks_of(child, div, kind or ("p" if t in ("q", "epigraph", "quote", "lg") else None))
            elif t in BLOCKS:
                r = _Reader(labels, state["page"])
                r.read(child)
                state["page"] = r.page
                b = r.block("note" if t == "note" else kind if kind and t in ("p", "l", "item") else
                            "p" if t in ("item", "l") else t, mark=child.get("n") if t == "note" else None)
                notes, b.notes = b.notes, []
                if b.text:
                    div.blocks.append(b)
                div.blocks += notes
            else:
                raise ValueError(f"TCP division: no rule for <{t}>")
            if child.tail and child.tail.strip():
                raise ValueError(f"TCP division: text outside a block: {child.tail.strip()[:40]!r}")

    text = root.find(f"{TEI}text")
    for part in ("front", "body", "back"):
        el = text.find(f"{TEI}{part}")
        if el is None:
            continue
        for child in el:
            if tag(child) == "pb":
                state["page"] = labels[id(child)]
            elif tag(child) == "div":
                d = Div(child.get("type", ""), child.get("n"), part)
                out.append(d)
                blocks_of(child, d)
            else:
                raise ValueError(f"TCP {part}: no rule for <{tag(child)}>")
    return out


def gap_spans(b: Block) -> list[dict]:
    """The words holding something the keyers could not read, as uncertain
    spans: the transcription's reading is the only one."""
    return [{"end": e, "readings": {"primary": b.text[s:e]}, "start": s} for s, e in b.gaps]


# ------------------------------------------------------------ as a tie-breaker


def plain(b: Block) -> str:
    """A block's words for lining up with a scan's: the long s as s, an em
    dash apart from the words beside it, and a word holding a gap as "◊",
    which reads as no word."""
    words_ = []
    for m in re.finditer(r"\S+", b.text):
        tok = m.group()
        words_.append("◊" if any(s <= m.start() < e for s, e in b.gaps) else tok.replace("ſ", "s"))
    return re.sub(r"\s*—\s*", " — ", " ".join(words_))


@lru_cache(maxsize=None)
def reference(sid: str, heading: str) -> Reference:
    """The text of the division of a TCP file whose heading matches
    `heading` (a pattern), as a reference to line a scan's words up with.
    Notes are left out (a scan's notes are read apart from its text)."""
    found = [d for top in read(sid) for d in top.walk() if any(re.search(heading, h) for h in d.heads())]
    if len(found) != 1:
        raise ValueError(f"{sid}: {len(found)} divisions headed {heading!r}")
    return Reference("tcp", "\n".join(plain(b) for b in found[0].blocks if b.kind != "note"))


def readings(tokens: list[str], ref: Reference | None) -> list[str | None]:
    """The TCP's reading of each of a run of a scan's words (None where it
    has none, or cannot be read; "" where it reads this word together with
    the one before)."""
    if ref is None or not tokens:
        return [None] * len(tokens)
    return [None if r is None or "◊" in r else r for r in (x.get("tcp") for x in align(tokens, [ref], {}))]


# ------------------------------------------------------------ fetching


def cmd_fetch() -> None:
    """Record the TCP files, at their pinned commits, as raw sources."""
    from tools.common import load_manifest
    from tools.fetch import add_source
    have = {e["id"] for e in load_manifest()}
    for tcp, commit in TEXTS.items():
        sid = source_id(tcp)
        if sid in have:
            continue
        add_source(sid, RAW_URL.format(tcp=tcp, commit=commit), LICENSE,
                   f"Evans-TCP {tcp} (github.com/textcreationpartnership/{tcp}, commit {commit}): the Text "
                   "Creation Partnership's typed transcription, TEI P5 XML.", ext=".xml")
        print(sid, flush=True)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["fetch"]:
        cmd_fetch()
