"""Pages printed in columns: the Annals of Congress (two to a page) and the
Congressional Globe (three). Shared by `importers/annals.py` and
`importers/globe.py` (decisions 46 and 47).

A page is split into its columns before the steps of `importers/ocr.py`.
The gutters are found from the lines that sit in one column; a line OCR
read across several columns is split word by word at them. Each column
becomes a Page of its own, its coordinates starting at the column's left
edge, so the single-column steps (paragraphs, notes, blocks) apply to it
unchanged.
"""

from __future__ import annotations

import re
import statistics
from bisect import bisect_right

from importers.ocr import NOTE_MARK, Line, Page, Para, Word, _line_height


def body_span(page: Page) -> tuple[float, float]:
    """Where the text of the page begins and ends across (ignoring specks
    at the edges)."""
    x0s = sorted(w.x0 for para in page.paras for w in para.words)
    x1s = sorted(w.x1 for para in page.paras for w in para.words)
    return x0s[len(x0s) // 50], x1s[-1 - len(x1s) // 50]


def _right(line: Line) -> int:
    return max(w.x1 for w in line.words)


def narrow(line: Line, span: float, n: int = 2) -> bool:
    """A line within one column (most of a column's width or less)."""
    return _right(line) - line.x0 < 0.6 * span * 2 / n


def boundaries(left: float, span: float, n: int) -> list[float]:
    """Where the gutters would be if the columns were equal and the page square."""
    return [left + span * k / n for k in range(1, n)]


def find_gutters(lines: list[Line], left: float, span: float, n: int = 2) -> list[float] | None:
    """Where each column ends and the next begins, from the lines that sit in
    one column: the middle between one column's right edge and the next
    column's left edge. None for a page not set in n columns (where the only
    short lines are the ends of paragraphs, on the left)."""
    guess = boundaries(left, span, n)
    inside = [l for l in lines if narrow(l, span, n)]
    out = []
    for k, b in enumerate(guess):
        lo = guess[k - 1] if k else float("-inf")
        hi = guess[k + 1] if k + 1 < len(guess) else float("inf")
        ends = sorted(_right(l) for l in inside if lo <= (l.x0 + _right(l)) / 2 < b)
        starts = sorted(l.x0 for l in inside if b <= (l.x0 + _right(l)) / 2 < hi)
        if len(ends) < 5 or len(starts) < 5:
            return None
        out.append((ends[int(len(ends) * 0.9)] + starts[len(starts) // 10]) / 2)
    return out


def sides(line: Line, gutters: list[float], span: float) -> list[tuple[int, list]]:
    """A line's words by column (0 the leftmost): a line within one column
    goes to the column its middle is in; a wider one (a scan whose OCR read
    across columns) is split word by word. Specks in a gutter ("|", "}") are
    not print and are left out."""
    n = len(gutters) + 1
    ws = sorted(line.words, key=lambda w: w.x0)
    if narrow(line, span, n):
        return [(bisect_right(gutters, (ws[0].x0 + ws[-1].x1) / 2), ws)]
    ws = [w for w in ws if re.search(r"\w", w.text)
          or min(abs((w.x0 + w.x1) / 2 - g) for g in gutters) > 0.03 * span]
    by: dict[int, list] = {}
    for w in ws:
        by.setdefault(bisect_right(gutters, (w.x0 + w.x1) / 2), []).append(w)
    return sorted(by.items())


def rows(lines: list[Line]) -> list[list[Line]]:
    """Lines grouped into rows across the page (by the middle of their words)."""
    out: list[list[Line]] = []
    for line in sorted(lines, key=lambda l: l.words[0].y0):
        mid = statistics.median((w.y0 + w.y1) / 2 for w in line.words)
        h = statistics.median(w.height for w in line.words) or 1
        if out and abs(out[-1][0].words[0].y0 + out[-1][0].words[0].height / 2 - mid) < 0.6 * h:
            out[-1].append(line)
        else:
            out.append([line])
    return out


def is_speck(row: list[Line]) -> bool:
    return len(re.sub(r"\W", "", " ".join(l.text for l in row))) <= 2


def split_columns(page: Page, head_ids: set[int], n: int, reference: bool = False) -> list[Page] | None:
    """The page's body (its lines but those in `head_ids`) as n column Pages,
    or None for a page not set in n columns. For a reference scan, read only
    for the vote, a page whose OCR ran nearly every line across the columns
    is split where equal columns would be instead."""
    left, right = body_span(page)
    span = right - left
    body = [l for para in page.paras for l in para.lines if id(l) not in head_ids]
    gutters = find_gutters(body, left, span, n)
    if gutters is None and reference:
        gutters = boundaries(left, span, n)
    if gutters is None:
        return None
    split = {id(l): sides(l, gutters, span) for l in body}
    columns = []
    for side in range(n):
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
        # A speck read as a paragraph of its own ("sss", "J"): neither book
        # prints a paragraph of three letters or fewer.
        col.paras = [p for p in col.paras if len(p.lines) > 1 or len(re.sub(r"\W", "", p.text)) > 3]
        col.paras.sort(key=lambda p: p.lines[0].words[0].y0)
        columns.append(col)
    return columns


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
    bands = {id(l): band(l) for _, l in lines}
    for i, (pa, a) in enumerate(lines):
        if not a.words:
            continue
        for pb, b in lines[i + 1:]:
            if not b.words or pb is pa:
                continue
            (a0, a1), (b0, b1) = bands[id(a)], bands[id(b)]
            if min(a1, b1) - max(a0, b0) > 0.5 * (min(a1 - a0, b1 - b0) or 1):
                a.words = sorted(a.words + b.words, key=lambda w: w.x0)
                b.words = []
                bands[id(a)] = band(a)
    for para in col.paras:
        para.lines = [l for l in para.lines if l.words]
    col.paras = [p for p in col.paras if p.lines]
    # A line or two OCR set apart (a speck at its start puts it outside the
    # column) that lies between the lines of another paragraph belongs there.
    for pb in list(col.paras):
        if len(pb.lines) > 2:
            continue
        y = bands[id(pb.lines[0])][0]
        host = next((pa for pa in col.paras if pa is not pb and len(pa.lines) > 1
                     and bands[id(pa.lines[0])][0] < y < bands[id(pa.lines[-1])][0]), None)
        if host is not None:
            host.lines = sorted(host.lines + pb.lines, key=lambda l: bands[id(l)][0])
            col.paras.remove(pb)


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
