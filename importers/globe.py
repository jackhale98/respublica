"""The debates in Congress on the Fourteenth Amendment, 1866, from the
Congressional Globe (decision 47).

The Congressional Globe, 39th Congress, 1st session (Washington: F. & J.
Rives, 1866), prints three columns to a page under a running head (the page
number, "THE CONGRESSIONAL GLOBE." and the date). Each house's proceedings
for a day open with its name ("IN SENATE.", "HOUSE OF REPRESENTATIVES.")
and the date, and run as items under headings in small capitals.

What is imported is fixed by the print: every item of either house's
proceedings from May 8 to June 13, 1866, headed "Reconstruction" or
"Reconstruction again" whose first paragraph takes up the joint resolution
(H. R. No. 127) proposing the amendment, or "the constitutional amendment"
reported by the joint committee on reconstruction; each from its heading to
the next heading or the end of that house's day. Each item is a division
(`House1866.May8`, a second item that day `House1866.May8b`;
`docs/references.md`).

Layout and words come from the University of North Texas Digital Library's
OCR of its copy (`unt-globe-1866-p{page}-words`: each word and its box, no
punctuation; `-text`: the same OCR as lines of text, with punctuation),
split into columns (`importers/columns.py`). They are checked against the
Internet Archive's scans of two other copies: the University of Michigan's
part 3 (to page 2880) and a microfilm of part 4 (`importers/ocr.py`).
"""

from __future__ import annotations

import datetime as dt
import gzip
import html
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from importers.annals import letters
from importers import corrections
from importers.columns import is_speck, mark_notes, rows, split_columns
from importers.ocr import (
    TOKEN, Block, Line, Page, Para, Reference, Vocabulary, Word, align, attested, blocks, key,
    parse_djvu_xml,
)
from importers.ratification import clean_vocabulary, text_of_readings
from tools.common import TEXTS_DIR, load_manifest, raw_path, read_raw_text, write_json

COLUMNS = 3
UNT = {"part3": "metadc30866", "part4": "metadc30867"}  # UNT Digital Library records (pages to 2880, from 2881)
UNT_URL = "https://digital.library.unt.edu/ark:/67531/{record}/m1/{leaf}/{what}/"
UNT_LICENSE = ("Public domain (the Congressional Globe, 1866). OCR as served by the UNT Digital Library; "
               "credit: UNT Libraries Government Documents Department, UNT Digital Library.")
MICHIGAN = "ia-globe-1866-pt3-michigan-txt"  # pp. 1921-2880
MICROFILM = "ia-globe-1866-pt4-microfilm-xml"  # pp. 2881-
EDITION = ("The Congressional Globe: Containing the Debates and Proceedings of the First Session of the "
           "Thirty-Ninth Congress (Washington: F. & J. Rives, 1866)")

# The days each house took up the joint resolution, and the pages read for
# them: from the page where that house's proceedings for the day begin to
# the page where the other house's (or the next day's) begin. `day_items`
# checks both ends.
DAYS = [
    ("House", dt.date(1866, 5, 8), 2458, 2481),
    ("House", dt.date(1866, 5, 9), 2497, 2519),
    ("House", dt.date(1866, 5, 10), 2530, 2547),
    ("Senate", dt.date(1866, 5, 23), 2760, 2771),
    ("Senate", dt.date(1866, 5, 24), 2794, 2807),
    ("Senate", dt.date(1866, 5, 29), 2865, 2876),
    ("Senate", dt.date(1866, 5, 30), 2887, 2902),
    ("Senate", dt.date(1866, 5, 31), 2912, 2921),
    ("Senate", dt.date(1866, 6, 4), 2934, 2944),
    ("Senate", dt.date(1866, 6, 5), 2957, 2965),
    ("Senate", dt.date(1866, 6, 6), 2980, 2993),
    ("Senate", dt.date(1866, 6, 7), 3007, 3011),
    ("Senate", dt.date(1866, 6, 8), 3025, 3042),
    ("House", dt.date(1866, 6, 13), 3140, 3150),
]


def pages_needed() -> list[int]:
    return sorted({p for _, _, first, last in DAYS for p in range(first, last + 1)})


def words_id(page: int) -> str:
    return f"unt-globe-1866-p{page}-words"


def text_id(page: int) -> str:
    return f"unt-globe-1866-p{page}-text"


def unt_record(page: int) -> str:
    return UNT["part3" if page <= 2880 else "part4"]


@lru_cache(maxsize=None)
def _urls() -> dict[str, str]:
    return {e["id"]: e["url"] for e in load_manifest()}


def unt_leaf(page: int) -> int:
    """The page's place in UNT's record (its page image is m1/{leaf}/), from
    the URL its words were fetched from."""
    m = re.search(r"/m1/(\d+)/", _urls()[words_id(page)])
    _expect(m is not None, f"p. {page}: no UNT page in {words_id(page)}")
    return int(m.group(1))


class ImportError_(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ImportError_(msg)


# ------------------------------------------------------------ UNT pages


def unt_words(page: int) -> list[Word]:
    """UNT's OCR words with their boxes, in UNT's order (IIIF annotations)."""
    data = json.loads(gzip.decompress(raw_path(words_id(page)).read_bytes()))
    out = []
    for r in data.get("resources", []):
        x, y, w, h = (int(v) for v in r["on"].split("#xywh=")[1].split(","))
        out.append(Word(r["resource"].get("chars", ""), x, y, x + w, y + h, 0))
    return out


def unt_lines(page: int) -> list[str]:
    """UNT's OCR of the page as lines of text (the page's "OCR" view)."""
    t = gzip.decompress(raw_path(text_id(page)).read_bytes()).decode("utf-8")
    m = re.search(r'(?s)<div id="ocr-text"[^>]*>(.*?)</div>', t)
    _expect(m is not None, f"p. {page}: no OCR text in {text_id(page)}")
    return [html.unescape(re.sub(r"<[^>]+>", "", l)).strip() for l in re.split(r"<br\s*/?>", m.group(1))]


def unt_page(page: int) -> Page:
    """The page from UNT's two views of one OCR: the words' boxes, in the
    annotations' order, which reads line by line (a line ends where the next
    word goes back to the left or down a line); each word's spelling, with
    punctuation, from the text, matched in order by letters and figures.
    Punctuation standing alone in the text ("—") goes with the word before
    it; a box the text has no word for keeps the annotation's spelling."""
    boxes = [w for w in unt_words(page) if key(w.text)]
    tokens: list[str] = []
    for line in unt_lines(page):
        for t in line.split():
            if key(t) or not tokens:
                tokens.append(t)
            else:
                tokens[-1] += t
    keyed = [t for t in tokens if key(t)]
    sm = SequenceMatcher(None, [key(w.text) for w in boxes], [key(t) for t in keyed], autojunk=False)
    spelling: dict[int, str] = {}
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal" or (op == "replace" and a2 - a1 == b2 - b1):
            for k in range(a2 - a1):
                spelling[a1 + k] = keyed[b1 + k]
    lines: list[Line] = []
    for a, w in enumerate(boxes):
        word = Word(spelling.get(a, w.text), w.x0, w.y0, w.x1, w.y1, 0)
        if lines:
            last = lines[-1].words[-1]
            h = max(last.height, word.height, 1)
            if word.x0 >= last.x1 - 0.5 * h and abs((word.y0 + word.y1) - (last.y0 + last.y1)) / 2 < 0.6 * h:
                lines[-1].words.append(word)
                continue
        lines.append(Line([word]))
    p = Page(page, max((w.x1 for w in boxes), default=0), max((w.y1 for w in boxes), default=0))
    p.paras = [Para([l], page) for l in lines]
    return p


def paragraphs(col: Page) -> list[Para]:
    """A column's lines (one to a paragraph, as UNT gives them) made into
    paragraphs: a paragraph ends at a line that stops short of the right
    margin when the next is indented, and a centred line (a heading) stands
    alone."""
    lines = sorted((l for para in col.paras for l in para.lines), key=lambda l: l.words[0].y0)
    if not lines:
        return []
    # The margin where each line is: scans are often skewed, so a column's
    # flush-left lines drift (from x 12 at the top to -11 at the foot); the
    # lower quartile of the starts of the fifteen lines around each line.
    starts = [l.x0 for l in lines]
    margins = [sorted(starts[max(0, k - 7):k + 8])[len(starts[max(0, k - 7):k + 8]) // 4] for k in range(len(lines))]
    # Straighten the column: each line moved by its margin, so that later
    # steps (`ocr.blocks`, joining paragraphs across columns) see one margin.
    lines = [Line([Word(w.text, w.x0 - m, w.y0, w.x1 - m, w.y1, w.conf) for w in l.words])
             for l, m in zip(lines, margins)]
    margins = [0] * len(lines)
    right = sorted(max(w.x1 for w in l.words) for l in lines)[int(len(lines) * 0.9)]
    lo_off, hi_off = max(4, col.width * 0.012), col.width * 0.12

    def indented(k: int) -> bool:
        return lo_off < lines[k].x0 - margins[k] < hi_off

    tops = [l.words[0].y0 for l in lines]
    gaps = [b - a for a, b in zip(tops, tops[1:])]
    leading = sorted(gaps)[len(gaps) // 2] if gaps else 0

    def heading(k: int) -> bool:
        """Centred, or standing apart with space above and below (a heading
        in small capitals may fill the column)."""
        l = lines[k]
        if l.x0 > margins[k] + col.width * 0.08 and max(w.x1 for w in l.words) < right - col.width * 0.08:
            return True
        above = gaps[k - 1] if k > 0 else float("inf")
        below = gaps[k] if k < len(gaps) else float("inf")
        # (Not the last line of a paragraph, which goes on from a line that
        # does not end a sentence: "… where there / is no peace.")
        ends_sentence = k == 0 or re.search(r"[.:?!\"')\]]$", lines[k - 1].text.rstrip())
        return (bool(leading) and above > 1.2 * leading and below > 1.2 * leading and l.text.rstrip().endswith(".")
                and one_case(l.text) and bool(ends_sentence))

    out: list[list[Line]] = [[lines[0]]]
    for k in range(1, len(lines)):
        prev, line = lines[k - 1], lines[k]
        short = max(w.x1 for w in prev.words) < right - col.width * 0.05
        # A speaker's words always begin a paragraph, indented, even after a
        # line that runs nearly to the margin.
        speaker = SPEAKER.match(line.text) and indented(k)
        if (short and indented(k)) or speaker or heading(k) or heading(k - 1):
            out.append([])
        out[-1].append(line)
    index = {id(l): k for k, l in enumerate(lines)}
    # A paragraph whose first line opens with a speaker, indented, begins a
    # paragraph even at the head of a column (`ocr.blocks` would join it to
    # the column before when the indent is slight).
    return [Para(ls, col.leaf, heading=len(ls) == 1 and heading(index[id(ls[0])]),
                 starts=bool(SPEAKER.match(ls[0].text)) and indented(index[id(ls[0])])) for ls in out]


# The running head: the page number, the title, and the date.
HEAD = re.compile(r"(?i)congressional|globe|\b\d{3,4}\b")


def head_of(page: Page) -> tuple[str, set[int]]:
    """The running head's text and its lines (empty if the page has none)."""
    lines = [l for para in page.paras for l in para.lines]
    first = next((r for r in rows(lines) if not is_speck(r)), None)
    if not (first and first[0].words[0].y0 < 0.08 * page.height and HEAD.search(" ".join(l.text for l in first))):
        return "", set()
    top = max(l.words[0].y0 for l in first)
    head_rows = [r for r in rows(lines) if r[0].words[0].y0 <= top]
    return " | ".join(" ".join(l.text for l in r) for r in head_rows), {id(l) for r in head_rows for l in r}


def column_pages(page: Page, number: int, reference: bool = False) -> list[Page] | None:
    """The page's columns, numbered by its printed page, or None for a page
    not set in three columns."""
    _, head_ids = head_of(page)
    columns = split_columns(page, head_ids, COLUMNS, reference)
    if columns is None:
        return None
    for col in columns:
        col.paras = paragraphs(col) if not reference else col.paras
        mark_notes(col)
        col.folio = col.number = str(number)
    return columns


def page_number(head: str) -> int | None:
    m = re.search(r"\b(\d{4})\b", head.replace("1866", " "))
    return int(m.group(1)) if m else None


def settle_pages(read: dict[int, int | None]) -> dict[int, int]:
    """Printed page numbers by scan page, checked against the pages around
    them: a number read in the head counts when its offset from the scan's
    page count is the one most pages within ten read; any other page takes
    its number from that offset (as `ocr.settle_folios` does)."""
    from collections import Counter
    offsets = {leaf: n - leaf for leaf, n in read.items() if n}
    out = {}
    for leaf in read:
        near = Counter(off for l, off in offsets.items() if abs(l - leaf) <= 10)
        off, count = near.most_common(1)[0] if near else (None, 0)
        if count >= 2:
            out[leaf] = leaf + off
    return out


# ------------------------------------------------------------ references


def michigan_text() -> str:
    """The Michigan copy's OCR text (part 3) from the House's proceedings of
    May 8, 1866, on: the part of it the imported items can be in."""
    t = read_raw_text(MICHIGAN)
    at = re.search(r"Tuesday,\s+May\s+8,\s+1866", t)
    _expect(at is not None, f"{MICHIGAN}: May 8, 1866 not found")
    return t[at.start():]


def microfilm_text(first: int, last: int) -> str:
    """The microfilm's OCR (part 4), pages first to last, column by column
    without running heads (its OCR runs lines across the columns)."""
    pages = [p for p in parse_djvu_xml(raw_path(MICROFILM)) if sum(len(x.words) for x in p.paras) >= 100]
    numbers = settle_pages({p.leaf: page_number(head_of(p)[0]) for p in pages})
    out = []
    for p in pages:
        n = numbers.get(p.leaf)
        if n is None or not first <= n <= last:
            continue
        for col in column_pages(p, n, reference=True) or []:
            out.extend(l.text for para in col.paras for l in para.lines)
    return "\n".join(out)


# ------------------------------------------------------------ items

HOUSES = {"House": "houseofrepresentatives", "Senate": "insenate"}
# The joint resolution, as the first paragraphs of an item name it.
SUBJECT = re.compile(r"No\.?\s*127|constitutional\s+amend|amendment\s+to\s+the\s+Con"
                     r"|joint\s+resolution\s+reported\s+by\s+the\s+(?:joint\s+)?committee", re.I)


# "Mr. STEVENS.", "Mr. RICE, of Massachusetts.", "The SPEAKER.", "The PRESIDENT pro tempore."
SPEAKER = re.compile(r"(?:Mr|The)\W{0,3}\s+[A-Z][A-Z]{2,}\b")  # also as OCR reads it ("Mr.^ HOWARD.")


def one_case(text: str) -> bool:
    """Small capitals as UNT's OCR reads them: in capitals ("RECONSTRUCTION."),
    or in lower case from the first letter ("reconstruction.")."""
    cased = [c for c in text if c.isalpha()]
    if not cased:
        return False
    return (sum(c.isupper() for c in cased) >= 0.75 * len(cased)
            or (cased[0].islower() and sum(c.islower() for c in cased) >= 0.85 * len(cased)))


def is_heading(b: Block) -> bool:
    """An item heading: a short line set as a heading, ending in a full stop,
    in small capitals, which the OCR reads in capitals ("RECONSTRUCTION.")
    or in lower case from the first letter ("reconstruction."). A centred
    sentence ("The motion was agreed to."), a line of verse ("Too feeble
    implements to bind.") or a title line of a bill printed in the debate
    ("Article—.", "Constitution of the United States.") begins with a
    capital and goes on in lower case."""
    t = b.text.strip()
    return b.kind == "text" and b.heading and 1 <= len(t.split()) <= 9 and t.endswith(".") and one_case(t)


def house_of(b: Block) -> str | None:
    """The house whose proceedings a block opens ("IN SENATE.", "HOUSE OF
    REPRESENTATIVES.", as OCR reads them), if it is such a heading."""
    t = letters(b.text)
    for house, name in HOUSES.items():
        if (b.kind == "text" and len(t) < len(name) + 30
                and SequenceMatcher(None, t[:len(name)], name).ratio() >= 0.8):
            return house
    return None


def is_subject(heading: Block) -> bool:
    """"Reconstruction" or "Reconstruction again", as OCR reads it
    ("JtEOONSTJIUCTION.", "reconttiuotion.")."""
    t = letters(heading.text)
    return any(SequenceMatcher(None, t, s).ratio() >= 0.65 and abs(len(t) - len(s)) <= 4
               for s in ("reconstruction", "reconstructionagain"))


@dataclass
class Item:
    house: str
    date: dt.date
    heading: Block
    body: list[Block]


@lru_cache(maxsize=None)
def span_blocks(first: int, last: int) -> tuple[Block, ...]:
    cols = []
    for p in range(first, last + 1):
        cs = column_pages(unt_page(p), p)
        _expect(cs is not None, f"p. {p}: not read as three columns")
        cols.extend(cs)
    return tuple(blocks(cols))


def day_items(house: str, date: dt.date, first: int, last: int) -> list[Item]:
    """The imported items of one house's proceedings on one day."""
    bs = list(span_blocks(first, last))
    start = next((k for k, b in enumerate(bs) if house_of(b) == house), None)
    _expect(start is not None, f"{house} {date}: the house's heading is not on pp. {first}–{last}")
    _expect(bs[start].folios[0] == str(first), f"{house} {date}: the house's heading is on p. {bs[start].folios[0]}")
    dateline = " ".join(b.text for b in bs[start:start + 2])
    # The weekday must be the date's ("Wednesday, Man 0> 1806." is May 9).
    m = re.search(r"([A-Za-z]+day)\W+([A-Za-z]{3,4})", dateline, re.I)
    _expect(m is not None and _weekday_ok(m.group(1), date)
            and SequenceMatcher(None, m.group(2).lower(), date.strftime("%B").lower()).ratio() >= 0.5,
            f"{house} {date}: the day's heading reads {dateline[:60]!r}")
    out: list[Item] = []
    current: Item | None = None
    ended = False
    for b in bs[start + 1:]:
        if house_of(b):
            ended = True
            break  # the other house, or the next day
        if is_heading(b):
            current = None
            if is_subject(b):
                current = Item(house, date, b, [])
                out.append(current)
            continue
        if current is not None:
            current.body.append(b)
    _expect(ended or current is None, f"{house} {date}: the last item runs past p. {last}")
    # An item on the joint resolution names it in its first paragraphs; one
    # headed "Reconstruction again" goes on with the one before it that day.
    kept = []
    for it in out:
        again = "again" in letters(it.heading.text)[12:] or SequenceMatcher(
            None, letters(it.heading.text), "reconstructionagain").ratio() >= 0.85
        if it.body and (any(SUBJECT.search(b.text) for b in it.body[:3]) or (again and kept)):
            kept.append(it)
    out = kept
    _expect(bool(out), f"{house} {date}: no item on the joint resolution")
    return out


def _weekday_ok(read: str, date: dt.date) -> bool:
    names = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    return SequenceMatcher(None, letters(read), names[date.weekday()]).ratio() >= 0.6


def all_items() -> list[Item]:
    return [it for house, date, first, last in DAYS for it in day_items(house, date, first, last)]


# ------------------------------------------------------------ text

WORKS = {
    "House": ("house-fourteenth-amendment-1866", "House1866",
              "Debates in the House of Representatives on the Fourteenth Amendment, 1866", "House debates, 1866"),
    "Senate": ("senate-fourteenth-amendment-1866", "Senate1866",
               "Debates in the Senate on the Fourteenth Amendment, 1866", "Senate debates, 1866"),
}


def prepare(its: list[Item]) -> dict[int, list[dict]]:
    """Each block's words aligned with the other copies' readings."""
    refs = [Reference("michigan", michigan_text()), Reference("microfilm", microfilm_text(2881, DAYS[-1][3]))]
    hints: dict[str, int] = {}
    readings: dict[int, list[dict]] = {}
    for it in its:
        stream = [it.heading, *(b for b in it.body if b.kind != "note")]
        tokens = [TOKEN.findall(b.text) for b in stream]
        aligned = align([t for ts in tokens for t in ts], refs, hints)
        at = 0
        for b, ts in zip(stream, tokens):
            readings[id(b)] = aligned[at:at + len(ts)]
            at += len(ts)
        for b in it.body:
            if b.kind == "note":
                readings[id(b)] = align(TOKEN.findall(b.text), refs, dict(hints))
    return readings


def build(house: str, its: list[Item], readings: dict[int, list[dict]], known: set[str]) -> dict:
    work_id, prefix, title, short = WORKS[house]
    divisions, segments = [], []
    seen: dict[str, int] = {}
    for it in its:
        day = f"{it.date.strftime('%b')}{it.date.day}"
        seen[day] = seen.get(day, 0) + 1
        suffix = "" if seen[day] == 1 else "bcdefgh"[seen[day] - 2]
        base = f"{prefix}.{day}{suffix}"
        label = f"{it.date.strftime('%B')} {it.date.day}, {it.date.year}" + (f" ({seen[day]})" if suffix else "")
        head, spans = text_of_readings(readings[id(it.heading)], known)
        div = {"date": it.date.isoformat(), "label": label, "level": 1, "ref": base, "title": head}
        if spans:
            div["uncertain"] = {"title": spans}
        divisions.append(div)
        body = [b for b in it.body if b.kind != "note"]
        notes = [b for b in it.body if b.kind == "note"]
        for kind, bs, ref_of, label_of in (
                (None, body, lambda n: f"{base}.{n}", lambda n: f"{house}, {label}, ¶ {n}"),
                ("footnote", notes, lambda n: f"{base}.fn{n}", lambda n: f"{house}, {label}, note {n}")):
            for n, b in enumerate(bs, 1):
                text, spans, fixed = corrections.apply(ref_of(n), *text_of_readings(readings[id(b)], known))
                first_page = int(b.folios[0])
                seg = {"label": label_of(n), "pages": b.folios, "ref": ref_of(n),
                       "scan": {"item": unt_record(first_page), "leaves": [unt_leaf(first_page)], "site": "unt"},
                       "text": text}
                if kind:
                    seg["kind"] = kind
                if spans:
                    seg["uncertain"] = spans
                if fixed:
                    seg["corrected"] = fixed
                segments.append(seg)
    pages = sorted({int(f) for s in segments for f in s["pages"]})
    return {
        "date": f"{its[0].date.isoformat()}/{its[-1].date.isoformat()}",
        "divisions": divisions,
        "edition": {"name": EDITION,
                    "notes": f"{EDITION}: the items of the {house}'s proceedings headed \"Reconstruction\" in which "
                             "it took up the joint resolution (H. R. No. 127) proposing the Fourteenth Amendment, "
                             f"pp. {pages[0]}–{pages[-1]}. Read from the UNT Digital Library's OCR of its copy and "
                             "checked word by word against scans of two other copies; words they could not settle "
                             "are marked as uncertain. See docs/editions.md."},
        "id": work_id,
        "ref_prefix": prefix,
        "segments": segments,
        "short": short,
        "source_ids": sorted({sid for p in pages for sid in (words_id(p), text_id(p))}) + [MICHIGAN, MICROFILM],
        "title": title,
    }


def run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    its = all_items()
    readings = prepare(its)
    known = Vocabulary(clean_vocabulary())
    for r in readings.values():
        known.attest(attested(r))
    paths = []
    for house in WORKS:
        mine = [it for it in its if it.house == house]
        path = out_dir / f"{WORKS[house][0]}.json"
        write_json(path, build(house, mine, readings, known))
        paths.append(path)
    return paths


# ------------------------------------------------------------ fetching


def cmd_fetch() -> None:
    """Record UNT's two views of each page the days span, as raw sources:
    the words with their boxes and the OCR text page (both gzip, as UNT
    sends them)."""
    from tools.common import fetch_bytes
    from tools.fetch import add_source
    have = {e["id"] for e in load_manifest()}
    leaves = {}
    for record in UNT.values():
        m = json.loads(fetch_bytes(f"https://digital.library.unt.edu/ark:/67531/{record}/manifest/"))
        leaves[record] = {c["label"]: n for n, c in enumerate(m["sequences"][0]["canvases"], 1)}
    for page in pages_needed():
        record = unt_record(page)
        leaf = leaves[record][str(page)]
        notes = f"The Congressional Globe, 39th Congress, 1st session, p. {page} (UNT Digital Library {record}, page {leaf}): "
        if words_id(page) not in have:
            add_source(words_id(page), UNT_URL.format(record=record, leaf=leaf, what="annotations/ocr"), UNT_LICENSE,
                       notes + "the OCR's words and their boxes (IIIF annotations).", ext=".json.gz", encoding="gzip")
        if text_id(page) not in have:
            add_source(text_id(page), UNT_URL.format(record=record, leaf=leaf, what="ocr"), UNT_LICENSE,
                       notes + "the OCR text page.", ext=".html.gz", encoding="gzip")
        print(f"p. {page}", flush=True)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["fetch"]:
        cmd_fetch()
    else:
        for path in run():
            print(f"wrote {path}")
