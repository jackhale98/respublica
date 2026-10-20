"""Pages that print two texts side by side (decision 66).

The Journals of the Continental Congress print the Declaration and Resolves
of October 14, 1774 beside John Sullivan's draft, and Ford's Writings of
Thomas Jefferson print the fair copy of Jefferson's proposed constitution
for Virginia beside his first draft: on such pages the left column is one
text and the right column another, with the page's own full-width lines
(the proceedings before the columns begin, the editor's notes at the foot)
above and below them. `right_column` keeps the page's full-width lines and
its right column and drops the left one; the result is a list of Pages (one
per zone, all with the scan page's leaf and printed number) that the steps
of `importers/ocr.py` (`blocks`) read like any other page.

The editor's notes in these books are marked with superscript figures, which
OCR reads as "'", "^" or a figure (not the marks `ocr.NOTE_MARK` knows), so
`mark_notes` finds them by their type alone: paragraphs in smaller type at the
foot of the page.
"""

from __future__ import annotations

import re
import statistics

from importers.columns import body_span, find_gutters, join_rows
from importers.ocr import Line, Page, Para, Word, _line_height, split_paragraphs, body_margin


def _right(line: Line) -> int:
    return max(w.x1 for w in line.words)


def _small(para: Para, body: float) -> bool:
    return statistics.median(_line_height(l) for l in para.lines) < 0.82 * body


def body_size(paras: list[Para]) -> float:
    sizes = sorted(_line_height(l) for p in paras for l in p.lines)
    return sizes[int(len(sizes) * 0.8)] if sizes else 0


def mark_notes(page: Page) -> None:
    """The editor's notes: the paragraphs in smaller type at the foot of the
    page, below its last paragraph in the text's type (in place)."""
    text = [p for p in page.paras if p.kind in ("text", "note")]
    if not text:
        return
    body = body_size(text)
    for p in text:
        p.kind = "text"
    lowest = sorted(text, key=lambda p: p.lines[0].words[0].y0)
    for p in reversed(lowest):
        if _small(p, body) and p.lines[0].words[0].y0 > 0.3 * page.height:
            p.kind = "note"
        else:
            break


def outdented(page: Page, paras: list[Para], clauses: bool = False) -> list[Para]:
    """Paragraphs set with a hanging indent (the grievances of Jefferson's
    fair copy: "by putting his negative on laws / the most wholesome …"):
    a line that starts left of the column's usual margin begins a paragraph
    (`Para.starts`, which `ocr.blocks` never joins to the one before). With
    `clauses`, also a line at the margin after one ending a clause, before an
    indented line (a page whose other lines are set full)."""
    margin = body_margin(page)
    step = 0.01 * page.height
    lines = [l for p in paras for l in p.lines]
    after = {id(a): b for a, b in zip(lines, lines[1:])}

    def hanging(prev: Line, line: Line) -> bool:
        """A line left of the margin; or, where most lines of the column are
        flush (a preamble set full, then one grievance), a line at the
        margin after a line ending a clause (";" or ":") and before an
        indented one."""
        nxt = after.get(id(line))
        return line.x0 < margin - step or (
            clauses and prev is not None and re.search(r"[;:]$", prev.text.strip()) is not None and line.x0 < margin + step
            and nxt is not None and nxt.x0 > line.x0 + step)

    out = []
    prev = None
    for para in paras:
        # (A paragraph OCR set apart that begins in lower case would be
        # joined to the one before by `ocr.blocks`, so its start is marked.)
        cur = Para([para.lines[0]], para.leaf, para.kind, para.heading,
                   para.starts or hanging(prev, para.lines[0]))
        prev = para.lines[0]
        for line in para.lines[1:]:
            if hanging(prev, line):
                out.append(cur)
                cur = Para([], para.leaf, para.kind, False, True)
            cur.lines.append(line)
            prev = line
        out.append(cur)
    return out


def _shifted(lines: list[Line], x0: int) -> list[Line]:
    return [Line([Word(w.text, w.x0 - x0, w.y0, w.x1 - x0, w.y1, w.conf) for w in l.words]) for l in lines]


def right_column(page: Page, columns_from: str | None = None, notes_from: str | None = None,
                 clauses: bool = False) -> list[Page]:
    """The page as zones: its full-width lines above the columns, its right
    column, and its notes; the left column is left out.

    The columns begin at the page's first text line, or at the line that
    `columns_from` (a pattern) matches, which the book's configuration names
    where full-width text comes first (the proceedings of the day before the
    resolutions, a page's heading). The gutter is found from the lines that
    sit in one column (`columns.find_gutters`); on a page with few of them it
    is the middle of the page's text, since both books set the two columns
    alike. A word belongs to the column its first letter is in (some scans'
    word boxes take in the space after the word, so a box can reach across
    the gutter). A page whose lines all sit right of its middle (the left
    column has ended) is all right column."""
    heads = [p for p in page.paras if p.kind in ("head", "folio")]
    notes = [p for p in page.paras if p.kind == "note"]
    text = [p for p in page.paras if p.kind == "text"]
    if not text:
        return [page]
    ordered = sorted((l for p in text for l in p.lines), key=lambda l: l.words[0].y0)
    top_y = ordered[0].words[0].y0
    if columns_from:
        at = next((l for l in ordered if re.search(columns_from, l.text)), None)
        if at is None:
            raise ValueError(f"leaf {page.leaf}: the columns' first line ({columns_from!r}) is not on the page")
        top_y = at.words[0].y0
    in_columns = [l for l in ordered if l.words[0].y0 >= top_y]
    left_edge, right_edge = body_span(page)
    # The editor's notes set across the page below the columns, where their
    # type is too close to the text's for `mark_notes` to tell (Ford): from
    # the line `notes_from` (a pattern) matches to the foot of the page.
    if notes_from:
        at = next((l for l in in_columns if re.search(notes_from, l.text)), None)
        if at is None:
            raise ValueError(f"leaf {page.leaf}: the notes' first line ({notes_from!r}) is not on the page")
        below = {id(l) for l in in_columns if l.words[0].y0 >= at.words[0].y0}
        in_columns = [l for l in in_columns if id(l) not in below]
        moved = [Para([l for l in p.lines if id(l) in below], page.leaf, "note") for p in text]
        notes = [m for m in moved if m.lines] + notes
        text = [t for t in (Para([l for l in p.lines if id(l) not in below], page.leaf) for p in text) if t.lines]
    found = find_gutters(in_columns, left_edge, right_edge - left_edge, 2)
    if columns_from is None and all(l.x0 > page.width * 0.4 for l in in_columns):
        g = min(l.x0 for l in in_columns) - 1
    elif found:
        g = found[0]
    else:
        g = (left_edge + right_edge) / 2
    above, right = [], []
    for p in text:
        a = [l for l in p.lines if l.words[0].y0 < top_y]
        r = []
        for l in p.lines:
            if l.words[0].y0 < top_y:
                continue
            ws = [w for w in l.words if w.x0 >= g]
            if ws:
                r.append(Line(sorted(ws, key=lambda w: w.x0)))
        if a:
            above.append(Para(a, page.leaf))
        if r:
            right.append(Para(r, page.leaf))
    # (Each zone keeps the page's number, so `ocr.blocks` never takes a
    # short zone for a plate.)
    folio = page.folio or page.number
    out = []
    if above:
        sub = Page(page.leaf, page.width, page.height, above, folio, page.number)
        sub.paras = split_paragraphs(sub, body_margin(sub))
        out.append(sub)
    if right:
        x0 = min(l.x0 for p in right for l in p.lines)
        x1 = max(_right(l) for p in right for l in p.lines)
        sub = Page(page.leaf, x1 - x0, page.height, [Para(_shifted(p.lines, x0), page.leaf) for p in right],
                   folio, page.number)
        join_rows(sub)
        sub.paras.sort(key=lambda p: p.lines[0].words[0].y0)
        sub.paras = outdented(sub, split_paragraphs(sub, body_margin(sub)), clauses)
        out.append(sub)
    if notes:
        out.append(Page(page.leaf, page.width, page.height, notes, folio, page.number))
    out[0].paras = heads + out[0].paras
    return out
