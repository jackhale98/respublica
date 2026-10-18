"""The House of Representatives' debate on amendments to the Constitution,
1789, from the Annals of Congress (decision 47).

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
    body_margin, parse_djvu_xml, split_paragraphs,
)
from tools.common import TEXTS_DIR, raw_path, write_json

PRIMARY = "ia-annals-1834-v1-google-xml"
REFERENCES = {"microfilm": "ia-annals-1834-v1-microfilm-xml"}
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


def sides(line: Line, mid: float, span: float) -> list[tuple[int | None, list]]:
    """A line's words by column (0 left, 1 right). A line narrower than most
    of a column goes to the column its middle is in; a wider one (a scan
    whose OCR read across both columns) is cut at its widest gap near the
    middle of the page, and with no gap there it is one line across the
    page (None)."""
    ws = sorted(line.words, key=lambda w: w.x0)
    if ws[-1].x1 - ws[0].x0 < 0.6 * span:
        return [(0 if (ws[0].x0 + ws[-1].x1) / 2 < mid else 1, ws)]
    gaps = [(ws[i + 1].x0 - ws[i].x1, i) for i in range(len(ws) - 1)
            if abs((ws[i].x1 + ws[i + 1].x0) / 2 - mid) < 0.15 * span]
    if not gaps:
        return [(None, ws)]
    _, i = max(gaps)
    return [(0, ws[:i + 1]), (1, ws[i + 1:])]


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


def split_spread(page: Page) -> Spread | None:
    """A page split into its running head and two columns, or None for a page
    that is not set in two columns (a title page, a blank leaf)."""
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
    split = {id(l): sides(l, mid, span) for l in lines if id(l) not in head_ids}
    across = sum(1 for parts in split.values() if parts[0][0] is None)
    if across > 0.2 * max(1, len(split)):
        return None  # set in one column
    columns = []
    for side in (0, 1):
        ws = [w for parts in split.values() for s, words in parts if s == side for w in words]
        if not ws:
            columns.append(Page(page.leaf, 0, page.height))
            continue
        x0, x1 = min(w.x0 for w in ws), max(w.x1 for w in ws)
        col = Page(page.leaf, x1 - x0, page.height)
        for para in page.paras:
            plines = []
            for l in para.lines:
                for s, words in split.get(id(l), []):
                    if s == side:
                        plines.append(Line([Word(w.text, w.x0 - x0, w.y0, w.x1 - x0, w.y1, w.conf) for w in words]))
            if plines:
                col.paras.append(Para(plines, page.leaf))
        col.paras.sort(key=lambda p: p.lines[0].words[0].y0)
        columns.append(col)
    return Spread(page.leaf, head, columns, numbers)


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


@lru_cache(maxsize=None)
def spreads(source_id: str) -> tuple[Spread, ...]:
    out = [s for s in (split_spread(p) for p in parse_djvu_xml(raw_path(source_id))) if s]
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
