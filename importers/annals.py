"""The House of Representatives' debate on amendments to the Constitution,
1789, from the Annals of Congress (decision 46).

Gales and Seaton's *Debates and Proceedings in the Congress of the United
States*, volume 1 (1834), prints two numbered columns to a page under a
running head: the column numbers and "Gales & Seaton's History" or "of
Debates in Congress" on the first line, then the house ("H. of R."), the
subject of the page and the date. Each day's business is a run of items,
each under a heading in capitals ("AMENDMENTS TO THE CONSTITUTION.").

What is imported is fixed by the print: every item of the House's
proceedings headed "Amendments to the Constitution", from its heading to the
next heading, the next day's date, or "Adjourned." Each item is a division
(`House1789.{Mon}{day}`, `docs/references.md`) and its paragraphs are
passages.

Layout comes from one scan's DjVu XML, split into its two columns; words are
checked against a second scan of the same printing read column by column
(see `importers/ocr.py`). Nothing is typed or corrected by hand.
"""

from __future__ import annotations

import datetime as dt
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from importers.ocr import (
    NOTE_MARK, TOKEN, Block, Line, Page, Para, Reference, Word, Vocabulary, _line_height, align, attested, blocks,
    OCR_DIR, OCR_MANIFEST, TESSERACT_ARGS, body_margin, parse_djvu_xml, parse_tesseract_tsv, run_tesseract,
    split_paragraphs, tesseract_versions,
)
from importers.ratification import clean_vocabulary, text_of_readings
from tools.common import ROOT, TEXTS_DIR, load_manifest, raw_path, read_json, sha256_file, write_json

PRIMARY = "ia-annals-1834-v1-google-xml"
REFERENCES = {"microfilm": "ia-annals-1834-v1-microfilm-xml", "tesseract": "ia-annals-1834-v1-google-tesseract"}
ITEM_URL = "https://archive.org/details/debatesandproce00galegoog"

# ------------------------------------------------------------ layout


@dataclass
class Spread:
    """One scanned page: its running head and its two columns, each a Page
    whose coordinates start at the column's left edge."""
    leaf: int
    head: str
    columns: list[Page]
    numbers: list[int | None]  # the column numbers read in the head


def body_span(page: Page) -> tuple[float, float]:
    """Where the text of the page begins and ends across (ignoring specks
    at the edges): the middle between them is the gutter's, roughly."""
    x0s = sorted(w.x0 for para in page.paras for w in para.words)
    x1s = sorted(w.x1 for para in page.paras for w in para.words)
    return x0s[len(x0s) // 50], x1s[-1 - len(x1s) // 50]


def narrow(line: Line, span: float) -> bool:
    """A line within one column (most of a column's width or less)."""
    return max(w.x1 for w in line.words) - min(w.x0 for w in line.words) < 0.6 * span


def find_gutter(lines: list[Line], mid: float, span: float) -> float | None:
    """Where the left column ends and the right begins, from the lines that
    sit in one column: the middle between the left column's right edge and
    the right column's left edge. None for a page set in one column (where
    the only short lines are the ends of paragraphs, on the left)."""
    inside = [l for l in lines if narrow(l, span)]
    ends = sorted(max(w.x1 for w in l.words) for l in inside if (l.x0 + max(w.x1 for w in l.words)) / 2 < mid)
    starts = sorted(l.x0 for l in inside if (l.x0 + max(w.x1 for w in l.words)) / 2 >= mid)
    if len(ends) < 5 or len(starts) < 5:
        return None
    return (ends[int(len(ends) * 0.9)] + starts[len(starts) // 10]) / 2


def sides(line: Line, gutter: float, span: float) -> list[tuple[int, list]]:
    """A line's words by column (0 left, 1 right): a line within one column
    goes to the side of the gutter its middle is on; a wider one (a scan
    whose OCR read across both columns) is split word by word. Specks in the
    gutter ("|", "}") are not print and are left out."""
    ws = sorted(line.words, key=lambda w: w.x0)
    if narrow(line, span):
        return [(0 if (ws[0].x0 + ws[-1].x1) / 2 < gutter else 1, ws)]
    ws = [w for w in ws if re.search(r"\w", w.text) or abs((w.x0 + w.x1) / 2 - gutter) > 0.03 * span]
    out = [(0, [w for w in ws if (w.x0 + w.x1) / 2 < gutter]), (1, [w for w in ws if (w.x0 + w.x1) / 2 >= gutter])]
    return [(side, words) for side, words in out if words]


def _rows(lines: list[Line]) -> list[list[Line]]:
    """Lines grouped into rows across the page (by the middle of their words)."""
    rows: list[list[Line]] = []
    for line in sorted(lines, key=lambda l: l.words[0].y0):
        mid = statistics.median((w.y0 + w.y1) / 2 for w in line.words)
        h = statistics.median(w.height for w in line.words) or 1
        if rows and abs(rows[-1][0].words[0].y0 + rows[-1][0].words[0].height / 2 - mid) < 0.6 * h:
            rows[-1].append(line)
        else:
            rows.append([line])
    return rows


# The head's two rows: the column numbers and the title ("441 GALES & SEATON'S
# HISTORY 442"), then the house, subject and date ("H. OF R.] Amendments to
# the Constitution. [June 8, 1789.").
HEAD_FIRST = re.compile(r"(?i)\b\d{2,4}\b|histor|debates|congress|seaton|gales")
HEAD_SECOND = re.compile(r"(?i)\]|\[|\bof\s*r\b|senate|17\d\d")


def split_spread(page: Page, reference: bool = False) -> Spread | None:
    """A page split into its running head and two columns, or None for a page
    that is not set in two columns (a title page, a blank leaf). For a
    reference scan, read only for the vote, a page whose OCR ran nearly every
    line across both columns is split at the middle of its text instead."""
    if not page.width or sum(len(para.words) for para in page.paras) < 50:
        return None
    left, right = body_span(page)
    mid, span = (left + right) / 2, right - left
    lines = [l for para in page.paras for l in para.lines]
    rows = [r for r in _rows(lines) if len(re.sub(r"\W", "", " ".join(l.text for l in r))) > 2]  # not specks
    head_rows = []
    for row, pattern in zip(rows[:2], (HEAD_FIRST, HEAD_SECOND)):
        text = " ".join(l.text for l in row)
        if row[0].words[0].y0 < 0.13 * page.height and pattern.search(text) and len(text.split()) <= 16:
            head_rows.append(row)
        else:
            break
    number_row = head_rows[0] if head_rows else []
    # Specks above or between the rows of the head go with it.
    top = max((l.words[0].y0 for row in head_rows for l in row), default=-1)
    head_rows = [r for r in _rows(lines) if r[0].words[0].y0 <= top]
    head_ids = {id(l) for row in head_rows for l in row}
    head = " | ".join(" ".join(l.text for l in row) for row in head_rows)
    numbers: list[int | None] = [None, None]
    for w in sorted((w for l in number_row for w in l.words), key=lambda w: w.x0):
        m = re.fullmatch(r"\D?(\d{1,4})\D?", w.text.strip())
        if m:
            side = 0 if (w.x0 + w.x1) / 2 < mid else 1
            if numbers[side] is None or side == 1:
                numbers[side] = int(m.group(1))
    body = [l for l in lines if id(l) not in head_ids]
    g = find_gutter(body, mid, span)
    if g is None and reference:
        g = mid
    if g is None:
        return None  # set in one column
    split = {id(l): sides(l, g, span) for l in body}
    columns = []
    for side in (0, 1):
        ws = [w for parts in split.values() for s, words in parts if s == side for w in words]
        if not ws:
            columns.append(Page(page.leaf, 0, page.height))
            continue
        # The column's edges from most of its words (a speck in the gutter
        # would widen it, and its short lines would then look centred).
        x0s, x1s = sorted(w.x0 for w in ws), sorted(w.x1 for w in ws)
        x0, x1 = x0s[len(x0s) // 50], x1s[-1 - len(x1s) // 50]
        col = Page(page.leaf, x1 - x0, page.height)
        for para in page.paras:
            plines = []
            for l in para.lines:
                for s, words in split.get(id(l), []):
                    if s == side:
                        plines.append(Line([Word(w.text, w.x0 - x0, w.y0, w.x1 - x0, w.y1, w.conf) for w in words]))
            if plines:
                col.paras.append(Para(plines, page.leaf))
        join_rows(col)
        # A speck read as a paragraph of its own ("sss", "J"): the Annals
        # print no paragraph of three letters or fewer.
        col.paras = [p for p in col.paras if len(p.lines) > 1 or len(re.sub(r"\W", "", p.text)) > 3]
        col.paras.sort(key=lambda p: p.lines[0].words[0].y0)
        columns.append(col)
    return Spread(page.leaf, head, columns, numbers)


def join_rows(col: Page) -> None:
    """Pieces of one printed line that OCR read as separate lines, at the same
    height, are joined into the first piece's line (in place): otherwise a
    piece set in a paragraph of its own is read after the paragraph it
    belongs to ("The question on Mr. Burke' put was negatived." … "'s motion
    being")."""
    def band(line: Line) -> tuple[float, float]:
        # Where most of the line's words sit (a tall quotation mark or a
        # speck may reach into the line above or below).
        return statistics.median(w.y0 for w in line.words), statistics.median(w.y1 for w in line.words)

    lines = [(para, l) for para in col.paras for l in para.lines]
    for i, (pa, a) in enumerate(lines):
        if not a.words:
            continue
        for pb, b in lines[i + 1:]:
            if not b.words or pb is pa:
                continue
            (a0, a1), (b0, b1) = band(a), band(b)
            if min(a1, b1) - max(a0, b0) > 0.5 * (min(a1 - a0, b1 - b0) or 1):
                a.words = sorted(a.words + b.words, key=lambda w: w.x0)
                b.words = []
    for para in col.paras:
        para.lines = [l for l in para.lines if l.words]
    col.paras = [p for p in col.paras if p.lines]
    # A line or two OCR set apart (a speck at its start puts it outside the
    # column) that lies between the lines of another paragraph belongs there.
    for pb in list(col.paras):
        if len(pb.lines) > 2:
            continue
        y = band(pb.lines[0])[0]
        host = next((pa for pa in col.paras if pa is not pb and len(pa.lines) > 1
                     and band(pa.lines[0])[0] < y < band(pa.lines[-1])[0]), None)
        if host is not None:
            host.lines = sorted(host.lines + pb.lines, key=lambda l: band(l)[0])
            col.paras.remove(pb)


def settle_columns(spreads: list[Spread]) -> None:
    """Column numbers, checked against the pages around them: a number read
    in a head counts when its offset from twice the scan page is the one most
    pages within ten read; any other page takes its numbers from the nearest
    page that agrees (as `ocr.settle_folios` does for page numbers)."""
    read = {s.leaf: s.numbers[0] - 2 * s.leaf for s in spreads if s.numbers[0] and s.numbers[0] % 2 == 1}
    read.update({s.leaf: s.numbers[1] - 1 - 2 * s.leaf for s in spreads
                 if s.leaf not in read and s.numbers[1] and s.numbers[1] % 2 == 0})
    for s in spreads:
        near = Counter(off for leaf, off in read.items() if abs(leaf - s.leaf) <= 10)
        if not near:
            s.numbers = [None, None]
            continue
        off, count = near.most_common(1)[0]
        if count < 2:
            s.numbers = [None, None]
            continue
        left = 2 * s.leaf + off
        s.numbers = [left, left + 1]


def mark_notes(col: Page) -> None:
    """Footnotes: paragraphs at the foot of a column in smaller type that
    begin with a mark (* or †)."""
    sizes = sorted(_line_height(l) for para in col.paras for l in para.lines)
    if not sizes:
        return
    body = sizes[int(len(sizes) * 0.8)]
    for para in reversed(col.paras):
        small = statistics.median(_line_height(l) for l in para.lines) < 0.85 * body
        if small and para.lines[0].words[0].y0 > 0.4 * col.height:
            if NOTE_MARK.match(para.text):
                para.kind = "note"
                continue
        break


TESSERACT = "ia-annals-1834-v1-google-tesseract"  # sources/ocr/{TESSERACT}.tsv, from IMAGES
IMAGES = "ia-annals-1834-v1-google-tif"


def scan_pages(name: str) -> list[Page]:
    """A scan's pages: a raw source's DjVu XML, or kept Tesseract output."""
    if name == TESSERACT:
        return parse_tesseract_tsv(OCR_DIR / f"{TESSERACT}.tsv")
    return parse_djvu_xml(raw_path(name))


@lru_cache(maxsize=None)
def spreads(name: str) -> tuple[Spread, ...]:
    out = [s for s in (split_spread(p, reference=name != PRIMARY) for p in scan_pages(name)) if s]
    settle_columns(out)
    return tuple(out)


def column_pages(source_id: str) -> list[Page]:
    """Every column of the scan in reading order, each a Page numbered by
    its printed column number, with paragraphs OCR ran together split again."""
    out = []
    for s in spreads(source_id):
        for n, col in zip(s.numbers, s.columns):
            if not col.paras:
                continue
            col.folio = col.number = str(n) if n else None
            col.paras = split_paragraphs(col, body_margin(col))
            mark_notes(col)
            out.append(col)
    return out


def reference_text(source_id: str) -> str:
    """A second scan as plain text, column by column, without running heads,
    for the vote (its own OCR runs each line across both columns)."""
    out = []
    for s in spreads(source_id):
        for col in s.columns:
            for para in col.paras:
                out.extend(l.text for l in para.lines)
    return "\n".join(out)


# ------------------------------------------------------------ items

# A day's heading, as OCR reads it ("Ti RSDAY, July 21.", "Thursoat, Sept 4."),
# sometimes run together with the first item's heading after it
# ("Wednesday, August 19. INDIAN TREATIES.").
DAY = re.compile(r"^(?P<weekday>[A-Za-z][A-Za-z .]{3,11}?)[.,]+\s*(?P<month>June|July|Aug\w*|Sep\w*)[.,]?\s*"
                 r"(?P<day>[0-9A-Za-z]{1,3})[.,:\-^{]*(?:\s+(?P<rest>.*))?$")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
SUBJECT = "amendmentstotheconstitution"


def letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def capitals(text: str) -> bool:
    """A short line in capitals: an item heading ("AMENDMENTS TO THE
    CONSTITUTION.", "ADJOURNMENT.")."""
    t = text.strip()
    caps = [c for c in t if c.isalpha()]
    return (1 <= len(t.split()) <= 8 and len(caps) >= 8
            and sum(c.isupper() for c in caps) >= 0.8 * len(caps))


def is_heading(b: Block) -> bool:
    return b.kind == "text" and capitals(b.text)


def day_of(b: Block) -> re.Match | None:
    """The day's heading at the start of a block, if it is one."""
    from difflib import SequenceMatcher
    m = DAY.match(b.text.strip()) if b.kind == "text" else None
    if not m or (m.group("rest") and not capitals(m.group("rest"))):
        return None
    word = letters(m.group("weekday"))
    return m if any(SequenceMatcher(None, word, d).ratio() >= 0.7 for d in WEEKDAYS) else None


def is_subject(b: Block) -> bool:
    from difflib import SequenceMatcher
    return is_heading(b) and SequenceMatcher(None, letters(b.text), SUBJECT).ratio() >= 0.8


MONTHS = {"jun": 6, "jul": 7, "aug": 8, "sep": 9}


def weekday_score(read: str, date: dt.date) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, letters(read), WEEKDAYS[date.weekday()] if date.weekday() < 6 else "sunday").ratio()


def date_of(m: re.Match, previous: dt.date | None) -> dt.date | None:
    """The date of a day's heading. The day of the month as read, when it is
    a day of that month whose weekday matches the weekday as read; otherwise
    (OCR misread the figures: "August 91", "August 23" for Saturday the 22d)
    the first day after the previous heading whose weekday matches. None
    when neither settles it."""
    month = MONTHS[m.group("month")[:3].lower()]
    weekday = m.group("weekday")
    try:
        read = dt.date(1789, month, int(m.group("day")))
    except ValueError:
        read = None
    if read and weekday_score(weekday, read) >= 0.6:
        return read
    if previous is None:
        return None
    later = [previous + dt.timedelta(days=k) for k in range(1, 8)]
    best = max(later, key=lambda d: weekday_score(weekday, d))
    return best if weekday_score(weekday, best) >= 0.6 else None


@dataclass
class Item:
    day: str  # the day's heading as read ("Monday, June 8.")
    date: dt.date
    heading: Block
    body: list[Block]


def items(bs: list[Block]) -> list[Item]:
    """The items headed "Amendments to the Constitution", each from its
    heading to the next heading, day or "Adjourned."."""
    out: list[Item] = []
    day, date = "", None
    current: Item | None = None
    for b in bs:
        m = day_of(b)
        if m:
            # The House's proceedings follow the Senate's: dates start again.
            previous = date if date and dt.date(1789, MONTHS[m.group("month")[:3].lower()], 1) >= date.replace(day=1) else None
            day, date, current = b.text.strip(), date_of(m, previous), None
            if not m.group("rest"):
                continue
            b = Block(m.group("rest"), b.leaves, b.folios, b.kind, b.first_indented)
        if is_subject(b):
            current = Item(day, date, b, [])
            out.append(current)
            continue
        if is_heading(b) or (b.kind == "text" and letters(b.text) == "adjourned"):
            current = None
            continue
        if current is not None:
            current.body.append(b)
    for it in out:
        _expect(it.date is not None, f"cannot date {it.day!r}")
        columns = sorted({int(f) for b in [it.heading, *it.body] for f in b.folios})
        _expect(columns == list(range(columns[0], columns[-1] + 1)),
                f"{it.day}: columns {columns} are not continuous (a page not read?)")
    return out


class ImportError_(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ImportError_(msg)


# ------------------------------------------------------------ text

WORK_ID = "house-amendments-1789"
PREFIX = "House1789"
SCAN_ITEM = "debatesandproce00galegoog"
EDITION = ("Joseph Gales, Sr., comp., The Debates and Proceedings in the Congress of the United States "
           "(Annals of Congress), vol. 1 (Washington: Gales and Seaton, 1834)")


def day_key(date: dt.date) -> str:
    """A day's part of a ref: "Jun8", "Aug13"."""
    return f"{date.strftime('%b')}{date.day}"


def day_label(date: dt.date) -> str:
    return f"{date.strftime('%B')} {date.day}, {date.year}"


def prepare() -> tuple[list[Item], dict[int, list[dict]]]:
    """The items, and each block's words aligned with the other readings."""
    its = items(blocks(column_pages(PRIMARY)))
    refs = [Reference(name, reference_text(sid)) for name, sid in REFERENCES.items()]
    hints: dict[str, int] = {}
    readings: dict[int, list[dict]] = {}
    for it in its:
        # The heading and text are aligned as one run (short lines in context);
        # notes one by one.
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
    return its, readings


def build(its: list[Item], readings: dict[int, list[dict]], known: set[str]) -> dict:
    divisions, segments = [], []
    keys = Counter(day_key(it.date) for it in its)
    _expect(all(n == 1 for n in keys.values()), f"two items on one day: {keys}")
    for it in its:
        base = f"{PREFIX}.{day_key(it.date)}"
        label = day_label(it.date)
        title, spans = text_of_readings(readings[id(it.heading)], known)
        div = {"date": it.date.isoformat(), "label": label, "level": 1, "ref": base, "title": title}
        if spans:
            div["uncertain"] = {"title": spans}
        divisions.append(div)
        body = [b for b in it.body if b.kind != "note"]
        notes = [b for b in it.body if b.kind == "note"]
        for kind, bs, ref_of, label_of in (
                (None, body, lambda n: f"{base}.{n}", lambda n: f"House, {label}, ¶ {n}"),
                ("footnote", notes, lambda n: f"{base}.fn{n}", lambda n: f"House, {label}, note {n}")):
            for n, b in enumerate(bs, 1):
                text, spans = text_of_readings(readings[id(b)], known)
                seg = {"columns": b.folios, "label": label_of(n), "ref": ref_of(n),
                       "scan": {"item": SCAN_ITEM, "leaves": b.leaves}, "text": text}
                if kind:
                    seg["kind"] = kind
                if spans:
                    seg["uncertain"] = spans
                segments.append(seg)
    first, last = its[0].date.isoformat(), its[-1].date.isoformat()
    return {
        "date": f"{first}/{last}",
        "divisions": divisions,
        "edition": {"name": EDITION,
                    "notes": f"{EDITION}: the items of the House's proceedings headed \"Amendments to the "
                             f"Constitution\", columns {segments[0]['columns'][0]}–{segments[-1]['columns'][-1]}. Read from OCR scans and checked word by word against "
                             "an independent scan and a second OCR of the same scan; words they could not settle "
                             "are marked as uncertain. See docs/editions.md."},
        "id": WORK_ID,
        "ref_prefix": PREFIX,
        "segments": segments,
        "short": "House debates, 1789",
        "source_ids": [PRIMARY, REFERENCES["microfilm"], IMAGES],
        "title": "Debates in the House of Representatives on Amendments to the Constitution, 1789",
    }


# Readings made by the same OCR engine: the Internet Archive read the
# microfilm with Tesseract, as we read the primary scan's images. They share
# its confusions ("Mapison" for "Madison" in small capitals), so their
# agreement alone does not make a word known (decision 46).
SAME_ENGINE = ("microfilm", "tesseract")


def independent(readings: list[dict]) -> list[dict]:
    """Readings with all but one of the same-engine readings left out, once
    for each: a word counts as attested only where the primary agrees."""
    return [{k: v for k, v in r.items() if k not in SAME_ENGINE or k == keep}
            for keep in SAME_ENGINE for r in readings]


def run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    its, readings = prepare()
    known = Vocabulary(clean_vocabulary())
    for r in readings.values():
        known.attest(attested(independent(r)))
    path = out_dir / f"{WORK_ID}.json"
    write_json(path, build(its, readings, known))
    return [path]


# ------------------------------------------------------------ commands


def item_leaves() -> list[int]:
    its = items(blocks(column_pages(PRIMARY)))
    return sorted({leaf for it in its for b in [it.heading, *it.body] for leaf in b.leaves})


def cmd_ocr() -> None:
    """Read the items' pages of the primary scan's images with Tesseract
    (sources/ocr/, decision 46)."""
    import zipfile
    leaves = item_leaves()
    entry = next(e for e in load_manifest() if e["id"] == IMAGES)
    zpath = ROOT / entry["path"]
    _expect(sha256_file(zpath) == entry["sha256"], f"{IMAGES} does not match the manifest; run make fetch")
    with zipfile.ZipFile(zpath) as z:
        names = {int(n[-8:-4]): n for n in z.namelist() if n.endswith(".tif")}
        images = [(leaf, z.read(names[leaf])) for leaf in leaves]
    out = OCR_DIR / f"{TESSERACT}.tsv"
    run_tesseract(images, out)
    records = [r for r in (read_json(OCR_MANIFEST) if OCR_MANIFEST.exists() else []) if r["id"] != TESSERACT]
    records.append({
        "command": "tesseract IMAGE stdout " + " ".join(TESSERACT_ARGS) + " (OMP_THREAD_LIMIT=1)",
        "id": TESSERACT,
        "images": {"leaves": leaves, "sha256": entry["sha256"], "source": IMAGES},
        "notes": "Annals of Congress, vol. 1 (1834), the pages of the items imported by importers/annals.py, "
                 "read with Tesseract as a third reading for the vote (decision 46). Written by "
                 "python -m importers.annals ocr.",
        "path": str(out.relative_to(ROOT)),
        "sha256": sha256_file(out),
        "tools": tesseract_versions(),
    })
    write_json(OCR_MANIFEST, sorted(records, key=lambda r: r["id"]))
    print(f"read {len(leaves)} pages -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["ocr"]:
        cmd_ocr()
    else:
        for path in run():
            print(f"wrote {path}")
