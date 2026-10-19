"""Brutus V-XVI from The New-York Journal (Thomas Greenleaf, New York,
1787-88), read from the Library of Congress's Chronicling America scans
(LCCN sn83030566; decision 55).

Each page's OCR is the Library's ALTO XML (ABBYY FineReader 12): words with
their boxes on the page and a confidence for each (`WC`), set in text
blocks and lines. There is one scan of each page, so no second reading to
vote with: a word is settled when it is a known word (`importers/ocr.py`,
`vote`) read with confidence, or when the Anti-Federalist Library reads it
the same way (`importers/library.py`); otherwise it is marked uncertain for
a person to check against the page image, with the Library's reading as a
suggestion where it differs.

Brutus XI (January 31, 1788) is not in Chronicling America: that issue is
missing from the Library's holdings, and its text is not taken from
anywhere else. Brutus XII and XIV were printed in two instalments each.
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache

from difflib import SequenceMatcher

from importers.ocr import HYPHEN_END, Block, Line, Page, Para, Word
from tools.common import load_manifest, raw_path

LCCN = "sn83030566"
PAPER = "The New-York Journal"
ISSUE_URL = "https://www.loc.gov/item/{lccn}/{date}/ed-1/?fo=json"
LICENSE = ("Public domain (The New-York Journal, 1787-88). Page OCR (ALTO XML) by the Library of Congress, "
           "Chronicling America, which believes the newspapers in it are in the public domain or have no known "
           "copyright restrictions.")
EDITION = "The New-York Journal, and Weekly Register (New York: Thomas Greenleaf), 1787–1788"

# The essays and the issues that print them (Thursdays), with the pages
# read: the essay's own page and the next, where it may run on. XII and XIV
# each run over two issues ("(Continued.)").
ESSAYS = [
    ("5", ["1787-12-13"]),
    ("6", ["1787-12-27"]),
    ("7", ["1788-01-03"]),
    ("8", ["1788-01-10"]),
    ("9", ["1788-01-17"]),
    ("10", ["1788-01-24"]),
    ("12", ["1788-02-07", "1788-02-14"]),
    ("13", ["1788-02-21"]),
    ("14", ["1788-02-28", "1788-03-06"]),
    ("15", ["1788-03-20"]),
    ("16", ["1788-04-10"]),
]
PAGES = (2, 3)
MISSING = {"11": "1788-01-31"}  # not in Chronicling America


def issues() -> list[str]:
    return [d for _, ds in ESSAYS for d in ds]


def alto_id(date: str, seq: int) -> str:
    return f"loc-nyjournal-{date}-p{seq}-alto"


@lru_cache(maxsize=None)
def _urls() -> dict[str, str]:
    return {e["id"]: e["url"] for e in load_manifest()}


def image_service(date: str, seq: int) -> str:
    """The page image's IIIF service id, from the URL its ALTO was fetched
    from (the same storage path)."""
    url = _urls()[alto_id(date, seq)]
    m = re.match(r"https://tile\.loc\.gov/storage-services/service/(.+)\.xml$", url)
    if not m:
        raise ValueError(f"{alto_id(date, seq)}: unexpected ALTO URL {url}")
    return "service:" + m.group(1).replace("/", ":")


# ------------------------------------------------------------ ALTO

ALTO_NS = re.compile(r"^\{[^}]*\}")


def _tag(el) -> str:
    return ALTO_NS.sub("", el.tag)


@dataclass
class AltoPage:
    page: Page  # words in lines in text blocks (one Para per block), in the OCR's reading order
    width: int  # the ALTO page size (its own units): word boxes are in these
    height: int


def parse_alto(path, leaf: int) -> AltoPage:
    """A page of ALTO XML as `ocr.Page`: a paragraph per text block, a line
    per text line, a word per string (its confidence, 0-100, in `conf`). A
    word hyphenated at a line end keeps its hyphen (`ocr.join_across`
    rejoins it)."""
    root = ET.parse(path).getroot()
    pg = next(el for el in root.iter() if _tag(el) == "Page")
    width, height = int(float(pg.get("WIDTH"))), int(float(pg.get("HEIGHT")))
    page = Page(leaf, width, height)
    for block in pg.iter():
        if _tag(block) != "TextBlock":
            continue
        lines = []
        for tl in block:
            if _tag(tl) != "TextLine":
                continue
            words = []
            for s in tl:
                if _tag(s) == "String":
                    x, y = int(float(s.get("HPOS"))), int(float(s.get("VPOS")))
                    w, h = int(float(s.get("WIDTH"))), int(float(s.get("HEIGHT")))
                    words.append(Word(s.get("CONTENT", ""), x, y, x + w, y + h, round(100 * float(s.get("WC", 0)))))
                elif _tag(s) == "HYP" and words:
                    words[-1].text += "-"
            if words:
                lines.append(Line(words))
        if lines:
            page.paras.append(Para(lines, leaf))
    return AltoPage(page, width, height)


@lru_cache(maxsize=None)
def load_page(date: str, seq: int) -> AltoPage:
    return parse_alto(raw_path(alto_id(date, seq)), seq)


# ------------------------------------------------------------ layout


@dataclass
class Column:
    x0: int
    x1: int
    lines: list[Line]


def columns(ap: AltoPage) -> list[Column]:
    """The page's columns, left to right, each a list of lines from top to
    bottom: text blocks that share most of their width are one column (the
    OCR splits a column into several blocks)."""
    cols: list[Column] = []
    for para in sorted(ap.page.paras, key=lambda p: min(l.x0 for l in p.lines)):
        x0, x1 = min(l.x0 for l in para.lines), max(w.x1 for w in para.words)
        for c in cols:
            if min(c.x1, x1) - max(c.x0, x0) > 0.5 * min(c.x1 - c.x0, x1 - x0):
                c.x0, c.x1 = min(c.x0, x0), max(c.x1, x1)
                c.lines.extend(para.lines)
                break
        else:
            cols.append(Column(x0, x1, list(para.lines)))
    for c in cols:
        c.lines.sort(key=lambda l: l.words[0].y0)
    return sorted(cols, key=lambda c: c.x0)


def _right(line: Line) -> int:
    return max(w.x1 for w in line.words)


@dataclass
class Graf:
    """A paragraph as printed, possibly running over columns and pages: its
    lines, and where each is (the page's sequence number in the issue)."""
    lines: list[tuple[str, int, Line]]  # (issue date, page, line)
    heading: bool = False
    indented: bool = False

    @property
    def text(self) -> str:
        from importers.ocr import lines_to_text
        return lines_to_text([l for _, _, l in self.lines])


# A paragraph ends with a stop (and perhaps a quotation mark or bracket).
UNFINISHED = re.compile(r"[.?!:;\"')\]”’]\W{0,2}$")


def grafs(date: str, seqs: tuple[int, ...] = PAGES) -> list[Graf]:
    """An issue's paragraphs, column by column, page by page. A paragraph
    ends at a line that stops short of the column's right margin when the
    next is indented, and a centred line (a heading, a signature) stands
    alone, and so does a line beginning with a large initial (an essay's
    first line). A paragraph goes on into the next column (or page) when the
    column ends with a full line and the next begins flush left, or when it
    stops mid-sentence."""
    out: list[Graf] = []
    open_end = False
    for seq in seqs:
        ap = load_page(date, seq)
        for col in columns(ap):
            lines = col.lines
            if not lines:
                continue
            width = col.x1 - col.x0
            starts = sorted(l.x0 for l in lines)
            margin = starts[len(starts) // 4]
            right = sorted(_right(l) for l in lines)[int(len(lines) * 0.9)]
            lo, hi = 0.02 * width, 0.12 * width
            heights = sorted(max(w.height for w in l.words) for l in lines)
            body = heights[len(heights) // 2]

            def centred(l: Line) -> bool:
                return l.x0 > margin + 0.06 * width and _right(l) < right - 0.06 * width

            for k, line in enumerate(lines):
                indented = lo < line.x0 - margin < hi
                # A paragraph that stops mid-sentence goes on: at the head of
                # the next column, or (OCR split it) at a line in lower case.
                unfinished = bool(out) and not out[-1].heading and not UNFINISHED.search(out[-1].text)
                if k == 0:
                    new = not (out and not out[-1].heading and not centred(line)
                               and ((open_end and not indented) or unfinished))
                else:
                    prev = lines[k - 1]
                    short = _right(prev) < right - 0.05 * width
                    # An essay's first line begins with a large initial ("IT was
                    # intended"), under its heading or salutation.
                    initial = max(w.height for w in line.words) > 1.35 * body
                    new = ((short and indented) or centred(line) or centred(prev) or initial) and not (
                        unfinished and line.text[:1].islower() and not centred(prev))
                if new or not out:
                    out.append(Graf([], heading=centred(line), indented=indented))
                out[-1].lines.append((date, seq, line))
            last = lines[-1]
            open_end = _right(last) >= right - 0.05 * width and not centred(last)
    return out


# ------------------------------------------------------------ essays

# The ALTO confidence (0-100) under which a word read by this one scan is
# not taken as settled unless the Library reads it the same way.
DOUBTFUL = 50


def graf_tokens(g: Graf) -> list[tuple[str, int]]:
    """The paragraph's words with their OCR confidence, as `ocr.lines_to_text`
    joins them (a word hyphenated at a line end is one word, with the lower
    confidence of its two pieces)."""
    out: list[tuple[str, int]] = []
    for _, _, line in g.lines:
        for k, w in enumerate(x for x in line.words if x.text.strip()):
            t = re.sub(r"\s+", "", w.text)
            if (k == 0 and out and HYPHEN_END.search(out[-1][0]) and t[:1].isalpha()
                    and re.search(r"[A-Za-z]{2}[-­]$", out[-1][0])):
                out[-1] = (out[-1][0][:-1] + t, min(out[-1][1], w.conf))
            else:
                out.append((t, w.conf))
    return out


def letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def is_heading(g: Graf) -> bool:
    """"BRUTUS, No. V." (or "B R U T U S." over "No. XVI."), as OCR reads it
    ("BRU T U 8, No. V.", "B K U T U S, No. VI.")."""
    t = letters(g.text)
    return len(t) <= 20 and len(g.text.split()) <= 8 and SequenceMatcher(None, t[:6], "brutus").ratio() >= 0.66


def is_paper(g: Graf) -> bool:
    """"For the New-York Journal, &c." over an essay."""
    t = letters(g.text)
    return len(g.text.split()) <= 9 and SequenceMatcher(None, t[:16], "forthenewyorkjou").ratio() >= 0.6


def signed(g: Graf) -> bool:
    """A paragraph ending with the signature ("… contrary. BRUTUS.", "BRU T U 3.")."""
    tail = letters(" ".join(g.text.split()[-8:]))[-8:]
    return any(SequenceMatcher(None, tail[-n:], "brutus").ratio() >= 0.75 for n in (6, 7, 8))


CONTINUED = re.compile(r"(?i)to\s*be\s*contin")


@dataclass
class Instalment:
    date: str
    heading: Graf
    grafs: list[Graf]  # the paper's line, then everything after the heading to the signature (or "To be continued")


def instalment(essay: str, date: str) -> Instalment:
    gs = grafs(date)
    # (the heading carries the number, "No. V.", or has it on the next line;
    # a signature standing alone, "BRUTUS.", does not)
    heads = [k for k, g in enumerate(gs) if is_heading(g) and k + 1 < len(gs)
             and (re.search(r"\bN\s*[o0°]\b", g.text) or re.match(r"(?i)^\W*no\b", gs[k + 1].text))]
    if len(heads) != 1:
        raise ImportError_(f"Brutus {essay}, {date}: {len(heads)} headings found")
    h = heads[0]
    head = gs[h]
    after = h + 1
    if len(letters(head.text)) <= 7 and re.match(r"(?i)^\W*no\b", gs[h + 1].text):
        head = Graf(head.lines + gs[h + 1].lines, True)  # "B R U T U S." / "No. XVI."
        after += 1
    out = [gs[h - 1]] if h and is_paper(gs[h - 1]) else []
    for g in gs[after:]:
        ends = len(out) > 3 and (signed(g) or (CONTINUED.search(g.text) and len(g.text.split()) <= 5))
        if not ends and (is_paper(g) or is_heading(g)):
            raise ImportError_(f"Brutus {essay}, {date}: no signature before {g.text[:40]!r}")
        out.append(g)
        if ends:
            return Instalment(date, head, out)
    raise ImportError_(f"Brutus {essay}, {date}: no signature")


@dataclass
class Part:
    """A paragraph of an essay: its block (text and pages), its words'
    readings, confidence, and where it is on the page images."""
    block: Block
    tokens: list[tuple[str, int]]
    date: str
    regions: dict[int, list[int]]  # page -> [x0, y0, x1, y1] (the ALTO's units)


SALUTE = re.compile(r"^(T\S{0,2}\s+(?:the\s+)?P\S*ople\s+of\s+.{0,40}?\.)\s+(?=\S)")


def parts(ins: Instalment) -> list[Part]:
    """The instalment's paragraphs as blocks, a salutation run into the first
    paragraph ("To the People of the State of New-York. HE liberties …")
    split off."""
    out = []
    for g in ins.grafs:
        toks = graf_tokens(g)
        text = " ".join(t for t, _ in toks)
        regions: dict[int, list[int]] = {}
        for _, seq, line in g.lines:
            r = regions.setdefault(seq, [line.x0, line.words[0].y0, _right(line), line.words[0].y1])
            r[0], r[2] = min(r[0], line.x0), max(r[2], _right(line))
            r[1] = min(r[1], min(w.y0 for w in line.words))
            r[3] = max(r[3], max(w.y1 for w in line.words))
        seqs = sorted(regions)
        m = SALUTE.match(text) if not out or len(out) <= 2 else None
        if m:
            n = len(m.group(1).split())
            for chunk in (toks[:n], toks[n:]):
                out.append(Part(Block(" ".join(t for t, _ in chunk), seqs, [str(s) for s in seqs], "text", True),
                                chunk, ins.date, regions))
            continue
        out.append(Part(Block(text, seqs, [str(s) for s in seqs], "text", g.indented, g.heading),
                        toks, ins.date, regions))
    # The signature run into the last line ("… nugatory. B R U T U 3.") is
    # the essay's signature, not text.
    last = out[-1]
    for k in range(1, 8):
        if k >= len(last.tokens):
            break
        sig = letters(" ".join(t for t, _ in last.tokens[-k:]))
        if len(sig) >= 5 and SequenceMatcher(None, sig, "brutus").ratio() >= 0.75 \
                and re.search(r"[.?!:;]\W*$", last.tokens[-k - 1][0]):
            body, tail = last.tokens[:-k], last.tokens[-k:]
            b = last.block
            out[-1:] = [Part(Block(" ".join(t for t, _ in body), b.leaves, b.folios, "text", b.first_indented), body,
                             last.date, last.regions),
                        Part(Block(" ".join(t for t, _ in tail), b.leaves[-1:], b.folios[-1:], "text", True), tail,
                             last.date, {s: r for s, r in last.regions.items() if s == b.leaves[-1]})]
            break
    return out


class ImportError_(RuntimeError):
    pass


SITE = "loc"


def scan(p: Part) -> dict:
    """Where a paragraph is: the issue, its pages, and on each page the
    region it fills, in hundredths of a percent of the page (for a page image
    cropped to it; tools/site_data.py)."""
    regions = []
    for seq in p.block.leaves:
        ap = load_page(p.date, seq)
        x0, y0, x1, y1 = p.regions[seq]
        regions.append([round(10000 * x0 / ap.width), round(10000 * y0 / ap.height),
                        round(10000 * (x1 - x0) / ap.width), round(10000 * (y1 - y0) / ap.height)])
    return {"image": [image_service(p.date, seq) for seq in p.block.leaves], "issue": p.date, "item": LCCN,
            "leaves": p.block.leaves, "regions": regions, "site": SITE}


def source_ids() -> list[str]:
    return [alto_id(d, seq) for d in issues() for seq in PAGES]


def edition(book: dict, series: dict, dates: dict[str, list[str]]) -> dict:
    """The Brutus work's edition: its book for I-IV, the newspaper for V-XVI."""
    return {"name": f"{book['name']}; {EDITION}",
            "notes": f"Brutus I–IV: {book['notes'].removesuffix(' See docs/editions.md.')} Brutus V–X and XII–XVI: "
                     f"{EDITION}, the issues of {dates[ESSAYS[0][0]][0]} to {dates[ESSAYS[-1][0]][-1]}, read from the "
                     "Library of Congress's scans (Chronicling America). There is one scan of each page: a word is "
                     "settled when its OCR is confident and it is a known word, or the Anti-Federalist Library reads "
                     "it the same way; every other word is marked as uncertain, with the Library's reading as a "
                     "suggestion where it differs. Brutus XI (January 31, 1788) is not imported: that issue is not "
                     "in Chronicling America, and its text is not taken from anywhere else. See docs/editions.md."}


# ------------------------------------------------------------ fetching


def cmd_fetch(pause: float = 15.0) -> None:
    """Record the ALTO XML of the pages each issue needs, as raw sources.
    Each page's URL is taken from the issue's record at loc.gov (which
    allows about one request every 10-15 seconds; tile.loc.gov serves the
    files)."""
    from tools.common import fetch_bytes
    from tools.fetch import add_source
    have = {e["id"] for e in load_manifest()}
    for date in issues():
        if all(alto_id(date, seq) in have for seq in PAGES):
            continue
        record = json.loads(fetch_bytes(ISSUE_URL.format(lccn=LCCN, date=date)))
        time.sleep(pause)
        pages = record["resources"][0]["files"]
        for seq in PAGES:
            if alto_id(date, seq) in have:
                continue
            xml = [f["url"] for f in pages[seq - 1] if f.get("mimetype") == "text/xml"]
            if len(xml) != 1:
                raise ValueError(f"{date} p. {seq}: no ALTO file in the issue record")
            add_source(alto_id(date, seq), xml[0], LICENSE,
                       f"{EDITION}, issue of {date}, page {seq} (Chronicling America, LCCN {LCCN}): the page's OCR "
                       "as ALTO XML (words, their boxes and confidence).", ext=".xml")
            print(f"{date} p. {seq}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["fetch"]:
        cmd_fetch()
