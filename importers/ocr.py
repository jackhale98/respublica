"""Shared machinery for importing printed books from OCR scans.

Layout comes from one scan's DjVu XML (word boxes, lines, paragraphs, pages);
the words are then checked against other scans of the same printed edition
(see `consensus`). Nothing here changes a word on its own judgment: every
word in the output is a reading found in at least one scan, and where the
scans disagree and no rule settles it, the passage records the readings in
`uncertain` for a human to check against the page image.

Steps, each documented in docs/editions.md:
  * page furniture (running heads, page numbers, signature marks) and
    footnotes (smaller type at the foot of a page) are separated from text;
  * a paragraph that continues across a page break is rejoined when the next
    page's first line is not indented;
  * a word hyphenated at a line end is rejoined (see `join_hyphen`).
"""

from __future__ import annotations

import re
from bisect import bisect_left
import statistics
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

# ------------------------------------------------------------ layout


@dataclass
class Word:
    text: str
    x0: int
    y0: int  # top
    x1: int
    y1: int  # bottom
    conf: int

    @property
    def height(self) -> int:
        return self.y1 - self.y0


@dataclass
class Line:
    words: list[Word]

    @property
    def x0(self) -> int:
        return min(w.x0 for w in self.words)

    @property
    def text(self) -> str:
        return " ".join(w.text.strip() for w in self.words if w.text.strip())


@dataclass
class Para:
    lines: list[Line]
    leaf: int
    kind: str = "text"  # text | head | folio | note
    heading: bool = False  # known to be a heading from its layout (the Globe: `globe.paragraphs`)
    starts: bool = False  # known to begin a paragraph (indented, or a speaker's words: `globe.paragraphs`)

    @property
    def words(self) -> list[Word]:
        return [w for l in self.lines for w in l.words]

    @property
    def text(self) -> str:
        return " ".join(l.text for l in self.lines)


@dataclass
class Page:
    leaf: int  # 1-based scan page ("n" in archive.org page URLs is leaf - 1)
    width: int
    height: int
    paras: list[Para] = field(default_factory=list)
    folio: str | None = None  # printed page number, when read on the page
    number: str | None = None  # printed page number, checked against nearby pages (settle_folios)


def _djvu_page(obj: ET.Element, leaf: int) -> Page:
    page = Page(leaf=leaf, width=int(obj.get("width", 0)), height=int(obj.get("height", 0)))
    for para in obj.iter("PARAGRAPH"):
        lines = []
        for line in para.iter("LINE"):
            words = []
            for w in line.iter("WORD"):
                c = [int(v) for v in (w.get("coords") or "0,0,0,0").split(",")[:4]]
                x0, ybot, x1, ytop = c
                words.append(Word(w.text or "", x0, min(ytop, ybot), x1, max(ytop, ybot),
                                  int(w.get("x-confidence") or 0)))
            if words:
                lines.append(Line(words))
        if lines:
            page.paras.append(Para(lines, page.leaf))
    return page


def parse_djvu_xml(path: Path) -> list[Page]:
    """Pages from an Internet Archive DjVu XML file, in scan order."""
    pages: list[Page] = []
    for _, obj in ET.iterparse(path, events=("end",)):
        if obj.tag != "OBJECT":
            continue
        pages.append(_djvu_page(obj, len(pages) + 1))
        obj.clear()
    return pages


def parse_djvu_part(path: Path, base: int) -> list[Page]:
    """Pages from part of an Internet Archive DjVu XML file (a run of its
    OBJECT elements, as `tools.fetch` keeps a byte range of it). Each page's
    leaf comes from the page name the file gives it ("…_0123.djvu"): `base`
    is the number in the name of the scan's first page (1, or 0 in the
    Internet Archive's microfilm scans)."""
    import io
    data = b"<DjVuXML><BODY>" + path.read_bytes() + b"</BODY></DjVuXML>"
    pages: list[Page] = []
    for _, obj in ET.iterparse(io.BytesIO(data), events=("end",)):
        if obj.tag != "OBJECT":
            continue
        name = next((p.get("value", "") for p in obj.iter("PARAM") if p.get("name") == "PAGE"), "")
        m = re.search(r"_(\d+)\.djvu$", name)
        if not m:
            raise ValueError(f"{path.name}: a page without a page name")
        pages.append(_djvu_page(obj, int(m.group(1)) - base + 1))
        obj.clear()
    return pages


FOLIO = re.compile(r"^\(?\s*([0-9ivxlcdm]{1,4})\s*\)?$", re.I)
# The editor's notes end "— Ed." (as OCR reads it: "EJ.", "LJ.", "£d.", "E,i.").
NOTE_MARK = re.compile(r"^\s*(?:[*•♦†‡§\\]|[f■]\s|■?j-|■?\)-)")
EDITOR_NOTE = re.compile(r"(?:^|[\s—.-])(?:Ed|EJ|LJ|£d|£i/|E,i|Ed,)[.,]?\s*$")


def classify(pages: list[Page]) -> None:
    """Split paragraphs OCR ran together, then mark running heads, folios and
    footnotes on each page (in place)."""
    notes_continue = False  # the page before ended in a note
    for page in pages:
        if page.paras:
            page.paras = split_paragraphs(page, body_margin(page))
    # The first line of each page, without figures, to find running heads
    # that repeat from page to page ("604 Letters of Centinel. No. IV.").
    tops = {p.leaf: re.sub(r"[^a-z]", "", p.paras[0].lines[0].text.lower()) if p.paras else "" for p in pages}

    def repeats(leaf: int) -> bool:
        mine = tops.get(leaf, "")
        return len(mine) >= 6 and any(
            SequenceMatcher(None, mine, tops.get(leaf + d, ""), autojunk=False).ratio() >= 0.75 for d in (-2, -1, 1, 2))

    for page in pages:
        if not page.paras:
            continue
        top = page.paras[0]
        # Running head: a short single line at the very top of the page,
        # holding a page number, set in capitals, or repeated from the pages
        # around it (the number itself may be misread: "A LANDHOLDER. I4I").
        first_line = top.lines[0].text
        letters = [c for c in first_line if c.isalpha()]
        capitals = letters and sum(c.isupper() for c in letters) >= 0.6 * len(letters)
        at_top = page.height and top.lines[0].words[0].y0 < 0.16 * page.height
        # OCR may run a head in capitals that begins or ends with the page
        # number into the paragraph below it ("SPIRIT OF THE PRESS. 383 the
        # instances adduced ..."): split it off.
        if (len(top.lines) > 1 and at_top and capitals and len(first_line.split()) <= 12
                and re.search(r"^\S*\d{1,4}\S*\s|\s\S*\d{1,4}\S*$", first_line)):
            page.paras.insert(0, Para([top.lines[0]], top.leaf))
            top.lines = top.lines[1:]
            top = page.paras[0]
        if (len(top.lines) == 1 and len(first_line.split()) <= 12 and len(page.paras) > 1
                and (re.search(r"\b\d{1,4}\b", first_line) or (at_top and (capitals or repeats(page.leaf))))):
            top.kind = "head"
            m = re.search(r"(?:^|\s)(\d{1,4})(?:\s|$)", first_line)
            page.folio = m.group(1) if m else None
            # The rest of a head OCR read as a separate block on the same
            # line ("1788.]" | "SPIRIT OF THE PRESS. 383").
            if len(page.paras) > 2:
                rest = page.paras[1]
                y = top.lines[0].words[0].y0
                if (len(rest.lines) == 1 and len(rest.text.split()) <= 12
                        and abs(rest.lines[0].words[0].y0 - y) < 0.01 * page.height):
                    rest.kind = "head"
                    m = re.search(r"(?:^|\s)(\d{1,4})(?:\s|$)", rest.text)
                    page.folio = page.folio or (m.group(1) if m else None)
        # A printer's signature mark ("40", the sheet number) at the foot of
        # the page that OCR ran into the last paragraph as its last line.
        last = page.paras[-1]
        if last.kind == "text" and len(last.lines) > 1 and page.height:
            mark = last.lines[-1]
            if (len(mark.text.replace(" ", "")) <= 8 and re.search(r"\d", mark.text)
                    and mark.words[0].y0 > 0.85 * page.height
                    and max(w.x1 for w in mark.words) - mark.x0 < 0.12 * page.width):
                last.lines = last.lines[:-1]
                page.paras.append(Para([mark], last.leaf, "folio"))
        # Folio at the foot: "( 247 )" or "247", or a mark of a few
        # characters on its own line at the very bottom ("('56)", "(no)":
        # OCR misreads the small figures).
        for para in page.paras[-2:]:
            squeezed = para.text.replace(" ", "")
            low = page.height and para.lines[0].words[0].y0 > 0.85 * page.height
            # A word and a period is text: a signature closing the last page
            # ("Brutus."), a short note ("† Ibid.").
            word = re.search(r"[A-Za-z]{3,}\.", squeezed)
            if len(para.lines) == 1 and (FOLIO.match(squeezed) or (low and len(squeezed) <= 7 and not word)):
                para.kind = "folio"
                m = FOLIO.match(squeezed)
                page.folio = page.folio or (m.group(1) if m and m.group(1).isdigit() else None)
        # Footnotes: smaller type at the foot of the page, after the last body
        # paragraph ("smaller" against the page's own text, since scans of
        # different pages differ in scale; a line's type size is its tallest
        # word, since OCR boxes fit each word's letters).
        # A note begins with a mark (*, †) unless it continues a note from
        # the page before; small type without one (a signature in small
        # capitals, a quotation) is text.
        # (The text's size is taken high in the range: on some pages a long
        # note has more lines than the text above it.)
        sizes = sorted(_line_height(l) for para in page.paras if para.kind == "text" for l in para.lines)
        body_size = sizes[int(len(sizes) * 0.8)] if sizes else 0
        run = []
        for para in reversed(page.paras):
            if para.kind != "text":
                continue
            lower = para.lines[0].words[0].y0 > page.height * (0.3 if NOTE_MARK.match(para.text) else 0.5)
            small = body_size and statistics.median(_line_height(l) for l in para.lines) < 0.88 * body_size
            if lower and (small or EDITOR_NOTE.search(para.text)):
                run.insert(0, para)
            else:
                break
        marked = [i for i, para in enumerate(run) if NOTE_MARK.match(para.text)]
        start = 0 if notes_continue else (marked[0] if marked else len(run))
        for para in run[start:]:
            para.kind = "note"
        # A note that stops mid-sentence at the foot of the page goes on overleaf.
        notes_continue = bool(run[start:]) and not re.search(r"[.?!:;)\]\"']\s*(?:\(\d+\))?$", run[-1].text)
        # A note of the editor's, marked and signed, even where OCR put a
        # line of text after it ("(To be continued.)").
        for para in page.paras:
            if (para.kind == "text" and para.lines[0].words[0].y0 > page.height * 0.3
                    and NOTE_MARK.match(para.text) and EDITOR_NOTE.search(para.text)):
                para.kind = "note"
    settle_folios(pages)


def set_aside(pages: list[Page], signature: str | None = None, speaker: str | None = None,
              head: str | None = None) -> None:
    """Before `classify`, for books that need it: specks the OCR read as a
    word of a letter or two, alone in a block (they hide a running head
    beneath them), are dropped; the top line of a page matching `head` (the
    book's running head, "580 DEBATES. [Nicholas.", however OCR misread its
    page number) and a printer's signature mark at the foot of a page
    matching `signature` ("VOL. III. 7") are page furniture; and a line that
    opens with a speaker's name (`speaker`: "Mr. MADISON.") always begins a
    paragraph, even where the OCR misread the stop ending the line before
    ("on this subject-") and ran the two together (in place)."""
    sig = re.compile(signature) if signature else None
    who = re.compile(speaker) if speaker else None
    top = re.compile(head) if head else None
    for page in pages:
        page.paras = [p for p in page.paras
                      if not (len(p.words) == 1 and len(p.text.strip()) <= 2 and not any(c.isdigit() for c in p.text))]
        if top and page.paras and page.height:
            first = page.paras[0]
            line = first.lines[0]
            y = line.words[0].y0
            # The head as OCR read it: one line, or blocks side by side on
            # the top line ("Henry.]" | "VIRGINIA." | "355").
            row = [p for p in page.paras if len(p.lines) == 1 and abs(p.lines[0].words[0].y0 - y) < 0.012 * page.height]
            text = " ".join(p.text for p in sorted(row, key=lambda p: p.lines[0].x0))
            if y < 0.16 * page.height and len(row) > 1 and len(text.split()) <= 6 and top.search(text):
                for p in row:
                    p.kind = "head"
            elif y < 0.16 * page.height and len(line.words) <= 6 and top.search(line.text):
                if len(first.lines) == 1:
                    first.kind = "head"
                else:
                    first.lines = first.lines[1:]
                    page.paras.insert(0, Para([line], first.leaf, "head"))
        if who:
            # (Also a line indented as a paragraph's first line is, between
            # lines set flush: the line before may be full, "… is
            # dreadful. / We are threatened …".)
            margin = body_margin(page)
            lo, hi = 0.02 * page.width, 0.06 * page.width

            def first_line(k: int, lines: list[Line]) -> bool:
                ends = re.search(r"[.?!:\"”]$", lines[k - 1].text)
                return (lo < lines[k].x0 - margin < hi and abs(lines[k - 1].x0 - margin) < lo
                        and (ends or (k + 1 < len(lines) and abs(lines[k + 1].x0 - margin) < lo)))

            paras = []
            for para in page.paras:
                cur = Para([para.lines[0]], para.leaf, para.kind, para.heading, para.starts or bool(who.match(para.lines[0].text)))
                for k, line in enumerate(para.lines[1:], 1):
                    if para.kind == "text" and (who.match(line.text) or first_line(k, para.lines)):
                        paras.append(cur)
                        cur = Para([], para.leaf, para.kind, False, True)
                    cur.lines.append(line)
                paras.append(cur)
            page.paras = paras
        if not (sig and page.paras and page.height):
            continue
        for last in list(page.paras):
            mark = last.lines[-1]
            if mark.words[0].y0 > 0.8 * page.height and sig.match(mark.text):
                if len(last.lines) == 1:
                    last.kind = "folio"
                else:
                    last.lines = last.lines[:-1]
                    page.paras.append(Para([mark], last.leaf, "folio"))


def settle_folios(pages: list[Page]) -> None:
    """Printed page numbers, checked against the pages around them (in place).

    A number read on a page counts only when it fits the pages around it:
    its offset from the scan's page count is the one most pages within ten
    read (so two pages misread alike, "53" and "57" for 153 and 157, do not
    confirm each other). Any other page, a misread number ("1" for "16",
    "41" for "411") or none, takes its number from the nearest confirmed
    page on each side; if those disagree (an unnumbered plate between them)
    the nearer one wins, and with none near, the page has no number."""
    read = {p.leaf: int(p.folio) for p in pages if p.folio and p.folio.isdigit()}
    def agreed(leaf: int, n: int) -> bool:
        # The scan-to-print offset most pages within ten read, and at least
        # one other page shares it.
        offsets = Counter(l - m for l, m in read.items() if abs(l - leaf) <= 10)
        top, count = offsets.most_common(1)[0]
        return leaf - n == top and count >= 2

    confirmed = {leaf: n for leaf, n in read.items() if agreed(leaf, n)}
    leaves = sorted(confirmed)
    for page in pages:
        if page.leaf in confirmed:
            page.number = str(confirmed[page.leaf])
            continue
        i = bisect_left(leaves, page.leaf)
        near = [leaf for leaf in leaves[max(0, i - 1):i + 1] if abs(leaf - page.leaf) <= 6]
        guesses = sorted((abs(leaf - page.leaf), confirmed[leaf] + page.leaf - leaf) for leaf in near)
        page.number = str(guesses[0][1]) if guesses and guesses[0][1] > 0 else None


def body_margin(page: Page) -> int:
    xs = [l.x0 for para in page.paras if para.kind == "text" for l in para.lines]
    if not xs:
        return 0
    return Counter(round(x / 10) * 10 for x in xs).most_common(1)[0][0]


@dataclass
class Block:
    """A paragraph of running text, possibly spanning pages."""
    text: str
    leaves: list[int]
    folios: list[str]
    kind: str = "text"  # text | note
    first_indented: bool = True
    heading: bool = False  # set in type or placed as a heading is (see `_is_heading`)


def blocks(pages: list[Page], first_leaf: int = 1, last_leaf: int | None = None,
           by_number: bool = False) -> list[Block]:
    """Paragraphs of text and notes in reading order between two scan pages.
    A paragraph continues the one before it (across a page break, or where
    OCR split a paragraph in two) when the one before ends with a line that
    runs to the right margin and its own first line is not indented (and is
    not a heading). With `by_number`, a block records each printed number it
    runs onto, also where two of them are on one scan page (the columns of
    the Annals, decision 59); otherwise each scan page's first."""
    out: list[Block] = []
    last_text: Block | None = None
    last_note: Block | None = None
    open_end = False  # the last text line on the previous page ran to the margin
    for page in pages:
        if page.leaf < first_leaf or (last_leaf and page.leaf > last_leaf):
            continue
        if page.folio is None and not any(p.kind == "head" for p in page.paras) and sum(
                len(p.words) for p in page.paras) < 25:
            continue  # a plate (a portrait and its caption), not a page of text
        margin, right = body_margin(page), right_margin(page)
        body_h = body_height(page)
        for para in page.paras:
            if para.kind in ("head", "folio"):
                continue
            text = lines_to_text(para.lines)
            if not text:
                continue
            if para.kind == "note":
                # A note that runs on (no mark, and the last note stopped
                # mid-sentence or at a colon, on this page or the one before)
                # is joined to it.
                if (last_note is not None and not NOTE_MARK.match(text)
                        and (not re.search(r"[.?!:;\"')\]”’]$", last_note.text) or last_note.text.endswith(":"))):
                    last_note.text = join_across(last_note.text, text)
                    if last_note.leaves[-1] != page.leaf:
                        last_note.leaves.append(page.leaf)
                        if page.number:
                            last_note.folios.append(page.number)
                    elif by_number and page.number and page.number not in last_note.folios:
                        last_note.folios.append(page.number)
                else:
                    last_note = Block(text, [page.leaf], [page.number] if page.number else [], "note")
                    out.append(last_note)
                continue
            indented = para.lines[0].x0 > margin + max(20, page.width * 0.012)
            # A paragraph never ends mid-sentence before a line beginning in
            # lower case (OCR drops a leading dash, "——a convention", and the
            # line then looks indented).
            mid_sentence = (last_text is not None and not re.search(r"[.?!:;\"')\]”’]$", last_text.text)
                            and re.match(r"[a-z]", text))
            # A line set flush left that begins in lower case never starts a
            # paragraph ("&c.—— / same art. sect. 8", where OCR dropped the
            # dash and the line before looks short).
            # Not after a quotation in verse, which stands apart from the
            # prose around it, nor before roman numerals OCR read in lower
            # case ("xviii, SEC. 17").
            flush_lower = (not indented and re.match(r"[a-z]", text) and not re.match(r"[ivxlc]+[.,]", text)
                           and last_text is not None and not re.search(r"[\"”]$", last_text.text))
            # A line beginning with a dash after a full line goes on with the
            # paragraph: OCR drops the first of the two dashes ("——In this
            # case"), and the line then looks indented.
            dash_on = open_end and re.match(r"[-—–]", text)
            # A heading of paragraph numbers set over several lines ("XXIII,
            # SEC. 21 ; … XXVII, / SEC. 21 ; …"), as Sydney cites the state
            # constitution.
            numerals = (last_text is not None and NUMERAL_HEAD.match(last_text.text) and NUMERAL_HEAD.match(text)
                        and not last_text.text.endswith("INCLUSIVE."))
            # The author's name set to the right under a quotation ("Pope."
            # under an epigraph) belongs to the quotation.
            attribution = (last_text is not None and len(para.lines) == 1 and len(text.split()) <= 3
                           and para.lines[0].x0 > page.width * 0.5 and re.search(r"[\"”]$", last_text.text))
            if last_text is not None and not para.starts and (attribution or numerals or not _is_heading(para, margin, page, body_h) and (
                    (open_end and not indented) or mid_sentence or flush_lower or dash_on)):
                last_text.text = join_across(last_text.text, text)
                if last_text.leaves[-1] != page.leaf:
                    last_text.leaves.append(page.leaf)
                    if page.number:
                        last_text.folios.append(page.number)
                elif by_number and page.number and page.number not in last_text.folios:
                    last_text.folios.append(page.number)
            else:
                last_text = Block(text, [page.leaf], [page.number] if page.number else [], "text", indented,
                                  _is_heading(para, margin, page, body_h))
                out.append(last_text)
            open_end = max(w.x1 for w in para.lines[-1].words) >= right - page.width * 0.05
    return out


def right_margin(page: Page) -> int:
    """Where full lines end (most text lines are justified to it)."""
    rights = sorted(max(w.x1 for w in l.words) for para in page.paras if para.kind == "text" for l in para.lines)
    return rights[int(len(rights) * 0.9)] if rights else page.width


def body_height(page: Page) -> float:
    hs = [w.height for para in page.paras if para.kind == "text" for w in para.words if w.height > 0]
    return statistics.median(hs) if hs else 0


# A line of roman numerals, figures and "SEC." (OCR reads small capitals in
# lower case, and "SEC." as "SIX.").
NUMERAL_HEAD = re.compile(r"(?i)^(?:(?:[ivxlc]+|\d+|sec|six|to|and|inclusive)[.,;]*\s*|;\s*)+$")


def split_paragraphs(page: Page, margin: int) -> list[Para]:
    """The page's paragraphs, with any that OCR ran together split again
    where print marks a new paragraph: a line that stops short of the right
    margin, followed by a line indented as a paragraph is (verse, indented
    further, is not split line by line)."""
    if not any(para.kind == "text" for para in page.paras):
        return page.paras
    right = right_margin(page)
    lo, hi = margin + max(20, page.width * 0.012), margin + page.width * 0.06
    out = []
    for para in page.paras:
        if para.kind != "text" or len(para.lines) < 2:
            out.append(para)
            continue
        cur = [para.lines[0]]
        for prev, line in zip(para.lines, para.lines[1:]):
            short = max(w.x1 for w in prev.words) < right - page.width * 0.05
            # Text, then a footnote: smaller type, starting with a note mark.
            smaller = _line_height(line) < 0.85 * _line_height(prev) and NOTE_MARK.match(line.text)
            continues = re.match(r"[a-z]", line.text) and not re.search(r"[.?!:;\"')\]”’]$", prev.text)
            if ((short and lo < line.x0 < hi) or smaller) and not continues:
                out.append(Para(cur, para.leaf, para.kind))
                cur = []
            cur.append(line)
        out.append(Para(cur, para.leaf, para.kind))
    return out


def _line_height(line: Line) -> float:
    """The tallest word's height: the type size, whatever letters the line has."""
    return max((w.height for w in line.words), default=0)


def _is_heading(para: Para, margin: int, page: Page, body_h: float = 0) -> bool:
    """Centered short lines and lines in large type (titles, essay headings)
    never continue a paragraph."""
    if para.heading:
        return True
    if len(para.lines) > 2:
        return False
    hs = [w.height for w in para.words if w.height > 0]
    if body_h and hs and statistics.median(hs) > 1.25 * body_h:
        return True
    line = para.lines[0]
    right = max(w.x1 for w in line.words)
    return line.x0 > margin + page.width * 0.08 and right < page.width * 0.85


# ------------------------------------------------------------ text

HYPHEN_END = re.compile(r"[-­‐‑]$")


def lines_to_text(lines: list[Line]) -> str:
    """Join a paragraph's lines, rejoining words hyphenated at a line end."""
    out = ""
    for line in lines:
        t = re.sub(r"\s+", " ", line.text).strip()
        if not t:
            continue
        out = join_across(out, t) if out else t
    return out


def join_across(a: str, b: str) -> str:
    """Join two runs of text; a word hyphenated at the end of `a` is rejoined
    with the first word of `b`."""
    a = a.rstrip()
    b = b.lstrip()
    if HYPHEN_END.search(a) and b and b[0].isalpha() and re.search(r"[A-Za-z]{2}[-­]$", a):
        return a[:-1] + b
    return f"{a} {b}"


# ------------------------------------------------------------ consensus

TOKEN = re.compile(r"\S+")


def key(tok: str) -> str:
    return re.sub(r"[^a-z0-9]", "", tok.lower())


def text_tokens(raw: str) -> list[str]:
    """Tokens of a plain OCR text, with line-end hyphenation rejoined."""
    text = re.sub(r"([A-Za-z]{2})[-­]\s*\n\s*([a-z])", r"\1\2", raw)
    return TOKEN.findall(text)


class Reference:
    """A secondary scan's token stream, searchable by position."""

    def __init__(self, name: str, raw: str):
        self.name = name
        self.tokens = text_tokens(raw)
        self.keys = [key(t) for t in self.tokens]
        self.index: dict[tuple, list[int]] = {}
        for i in range(len(self.keys) - 3):
            k = tuple(self.keys[i:i + 4])
            if all(k):
                self.index.setdefault(k, []).append(i)

    def locate(self, keys: list[str], hint: int = 0) -> int | None:
        """Start offset of a run of keys in this stream: the offset that the
        most of the run's 4-grams (up to 40 of them) agree on, at least two,
        the nearest to `hint` on a tie."""
        votes: Counter = Counter()
        tried = 0
        for i in range(0, max(1, len(keys) - 3)):
            k = tuple(keys[i:i + 4])
            if not all(k) or k not in self.index:
                continue
            hits = self.index[k]
            if len(hits) > 20:
                continue  # too common to place anything
            for h in hits:
                votes[(h - i) // 8] += 1  # a little slack for words read as two
            tried += 1
            if tried >= 40:
                break
        if not votes:
            return None
        best = max(votes.values())
        if best < 2:
            return None
        bucket = min((b for b, n in votes.items() if n == best), key=lambda b: abs(b * 8 - hint))
        return max(0, bucket * 8 - 8)


@dataclass
class Uncertain:
    start: int  # token index in the paragraph
    end: int
    readings: dict[str, str]
    suggestion: str | None = None  # the Anti-Federalist Library's reading, where no scan's agrees with it


def align(tokens: list[str], refs: list[Reference], hints: dict[str, int]) -> list[dict[str, str]]:
    """For each token of a paragraph (from the primary scan), the readings of
    the other scans aligned to it: [{"primary": ..., "<scan>": ...}, ...].
    A reading of "" means that scan has no word there (it read this token
    and the one before as one word). `hints` carries each reference's
    position forward between paragraphs."""
    keys = [key(t) for t in tokens]
    readings = [{"primary": t} for t in tokens]
    for ref in refs:
        start = ref.locate(keys, hints.get(ref.name, 0))
        if start is None:
            continue
        window_end = min(len(ref.tokens), start + int(len(tokens) * 1.25) + 30)
        sm = SequenceMatcher(None, keys, ref.keys[start:window_end], autojunk=False)
        last = start
        ops = sm.get_opcodes()
        if sum(i2 - i1 for op, i1, i2, _, _ in ops if op == "equal") < 0.5 * len(tokens):
            continue  # not the same passage
        for n, (op, i1, i2, j1, j2) in enumerate(ops):
            # Words that differ are paired only when their letters are mostly
            # alike, or when one or two words differ between runs of at least
            # three words that agree: elsewhere a run of different words, side
            # by side, means the scans are not at the same place, and pairing
            # them would let two misplaced scans outvote the primary.
            if op == "equal":
                for k in range(i2 - i1):
                    readings[i1 + k][ref.name] = ref.tokens[start + j1 + k]
            elif op == "replace" and i2 - i1 == j2 - j1 <= 2 and _anchored(ops, n):
                for k in range(i2 - i1):
                    readings[i1 + k][ref.name] = ref.tokens[start + j1 + k]
            elif op == "replace":
                for ia, jb in pair_similar(tokens[i1:i2], ref.tokens[start + j1:start + j2]):
                    words = [ref.tokens[start + j1 + j] for j in jb]
                    reading = join_tokens(words)
                    first = i1 + ia[0]
                    if fragment(reading, tokens[first]) and len(ia) == 1:
                        continue
                    readings[first][ref.name] = reading
                    for i in ia[1:]:
                        readings[i1 + i][ref.name] = ""
            else:
                continue
            last = start + j2
        hints[ref.name] = last
    return readings


def _anchored(ops: list, n: int) -> bool:
    """True when opcode n lies between two runs of at least three equal words
    (or the start or end of the paragraph)."""
    def agrees(m: int) -> bool:
        if m < 0 or m >= len(ops):
            return True
        op, i1, i2, _, _ = ops[m]
        return op == "equal" and i2 - i1 >= 3
    return agrees(n - 1) and agrees(n + 1)


def join_tokens(words: list[str]) -> str:
    """One reading from a scan's tokens: a word broken by a hyphen is
    rejoined, others are kept apart."""
    out = words[0]
    for w in words[1:]:
        out = out[:-1] + w if HYPHEN_END.search(out) and re.search(r"[A-Za-z]{2}[-­]$", out) else f"{out} {w}"
    return out


def fragment(reading: str, primary: str) -> bool:
    """True when a scan's reading is only part of the primary's word: a
    line-end piece ("citi-" for "citizen") or the rest of a word broken
    across a page ("serted" for "asserted")."""
    r, p = key(reading), key(primary)
    if not r or len(r) >= len(p):
        return False
    return (HYPHEN_END.search(reading) and p.startswith(r)) or (p.endswith(r) and not reading[:1].isupper())


def pair_similar(a: list[str], b: list[str], floor: float = 0.5, limit: int = 40) -> list[tuple[list[int], list[int]]]:
    """Pair tokens of two short runs that differ (a misread word, a word read
    as two, a running head one scan has in its text), in order, keeping only
    pairs whose letters are mostly alike. A token may pair with two adjacent
    tokens of the other run that read as one word ("coinni unity" and
    "community"). Returns [(indices in a, indices in b)]."""
    if not a or not b or len(a) > limit or len(b) > limit:
        return []

    def furniture(t: str) -> bool:
        k = key(t)
        return any(c.isdigit() for c in k) or (len(k) > 1 and t.upper() == t)

    def sim(x: list[str], y: list[str]) -> float:
        """Letters in common, or -1 if the pairing is not allowed."""
        if len(y) == 2 and any(furniture(t) for t in y):
            return -1.0  # a running head or page number, not half a word
        kx, ky = "".join(key(t) for t in x), "".join(key(t) for t in y)
        if not kx or not ky:
            kx, ky = " ".join(x), " ".join(y)
        sm = SequenceMatcher(None, kx, ky, autojunk=False)
        return sum(b.size for b in sm.get_matching_blocks()) if sm.ratio() >= floor else -1.0

    # Best monotone matching: gaps are free, a pairing scores the letters
    # it matches, and pairings less alike than the floor are not allowed.
    n, m = len(a), len(b)
    moves = ((1, 1), (2, 1), (1, 2))
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    back: dict[tuple[int, int], tuple] = {}
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            best, how = -1.0, None
            if i and score[i - 1][j] > best:
                best, how = score[i - 1][j], ("skip", 1, 0)
            if j and score[i][j - 1] > best:
                best, how = score[i][j - 1], ("skip", 0, 1)
            for di, dj in moves:
                if i >= di and j >= dj:
                    s = sim(a[i - di:i], b[j - dj:j])
                    if s >= 0 and score[i - di][j - dj] + s > best:
                        best, how = score[i - di][j - dj] + s, ("pair", di, dj)
            score[i][j], back[(i, j)] = best, how
    pairs = []
    i, j = n, m
    while i or j:
        kind, di, dj = back[(i, j)]
        if kind == "pair":
            pairs.append((list(range(i - di, i)), list(range(j - dj, j))))
        i, j = i - di, j - dj
    return pairs[::-1]


def is_word(k: str) -> bool:
    """A key made of letters only (numbers are never "known words")."""
    return bool(k) and k.isalpha()


def attested(readings: list[dict[str, str]]) -> set[str]:
    """Words two scans read identically at the same place, each cleanly
    printed (see `plain`: a piece of a word broken at a line end, a run read
    as one word, or "wil)" for "will" does not count)."""
    out = set()
    for r in readings:
        c = Counter(key(v) for v in r.values() if plain(v))
        out.update(k for k, n in c.items() if n >= 2 and is_word(k))
    return out


def consensus(readings: list[dict[str, str]], known: set[str], library: list[str | None] | None = None,
              strict: bool = False, doubtful: list[bool] | None = None) -> tuple[list[str], list[Uncertain]]:
    """Vote on each word (see `vote`); return the words and the unsettled ones.

    Where a scan read two of the primary's tokens as one word (a reading of
    "" on the second), the tokens are voted on together, as one reading per
    scan, so the choice between "coinni unity" and "community" is made once.

    `library`: the Anti-Federalist Library's reading of each token, a
    tie-breaker only (see `tie_break`; `strict` as there). `doubtful`: tokens
    the primary scan's OCR read with little confidence, which count as
    unsettled unless another scan or the Library agrees."""
    out: list[str] = []
    uncertain: list[Uncertain] = []
    i = 0
    while i < len(readings):
        end = i + 1
        while end < len(readings) and "" in readings[end].values():
            end += 1
        group = readings[i:end]
        joint = {src: " ".join(v for v in (r[src] for r in group) if v)
                 for src in group[0] if all(src in r for r in group)}
        word, settled = vote(joint, known)
        if len(group) > 1 and settled and key(word) != key(joint["primary"]):
            # Another scan reads one word where the primary reads two. Only
            # a word the primary split with a space ("com munity") is settled;
            # otherwise ("deliver d" against "delivered", where the page has
            # "deliver'd") the readings are kept for a human.
            word, settled = joint["primary"], False
        elif len(group) > 1 and not settled:
            # No agreement on the run as a whole: vote word by word among the
            # scans that read it word by word.
            split = [{s: v for s, v in r.items() if all(x.get(s) for x in group)} for r in group]
            votes = [vote(r, known) for r in split]
            if all(ok for _, ok in votes):
                word, settled = " ".join(w for w, _ in votes), True
        if doubtful and settled and len(joint) == 1 and any(doubtful[i:end]):
            settled = False  # one scan, read with little confidence: nothing corroborates it
        suggestion = None
        # The Library's reading of the same words: none where it has no word
        # there, or reads them together with a word outside them.
        if (library and all(x is not None for x in library[i:end]) and library[i]
                and not (end < len(library) and library[end] == "")):
            lib = " ".join(x for x in library[i:end] if x)
            word, settled, suggestion = tie_break(joint, word, settled, lib, strict, known)
        out.append(word)
        if not settled:
            uncertain.append(Uncertain(len(out) - 1, len(out), joint, suggestion))
        i = end
    return out, uncertain


def edge_marks(v: str) -> tuple[str, str]:
    """The stops, quotation marks and brackets before and after a word
    (curly and straight quotation marks alike)."""
    v = v.translate(str.maketrans("‘’“”", "''\"\""))
    return re.match(r"\W*", v).group(), re.search(r"\W*$", v).group()


def tie_break(joint: dict[str, str], word: str, settled: bool, lib: str, strict: bool = False,
              known: set[str] = frozenset()) -> tuple[str, bool, str | None]:
    """The Anti-Federalist Library as a tie-breaker (importers/library.py;
    decision 55). Returns (word, settled, suggestion).

    The Library never adds a word: the text is always one of the scans'
    readings. A word the vote left unsettled is settled when the Library
    reads it with the same letters as one of the scans (that scan's
    reading is taken, its own spelling and marks, preferring the one whose
    marks around the word match the Library's). Where no scan's reading
    agrees, the word stays unsettled and the Library's reading is returned
    as a suggestion for a person to check against the page image. With
    `strict` (the scans are of the printing the Library follows), a settled
    word the Library reads differently is unsettled too, unless two scans
    read it so and it is a known word (four scans' "right" against the
    Library's "fight": the Library has misreadings of its own)."""
    lk = key(lib)
    pk = key(joint["primary"])
    if not lk:
        return word, settled, None
    if (not all(key(t) in known for t in lib.split())
            and any(v and confused(key(v), lk) for v in joint.values())):
        # The Library's word, not a known word, is a common misreading of a
        # scan's ("discemable" for "discernable"): its text has OCR errors of
        # its own.
        return word, settled, None

    def whole(v: str) -> bool:
        """Not a reading of more or less than the main scan's word, as the
        vote also requires: a scan's reading paired with part of it
        ("that zest" for "thatzestof"), or with a piece of a word broken at
        a line end ("property" for "prop-", before "erty")."""
        k = key(v)
        return (len(k) >= 0.75 * len(pk) or len(pk) < 5) and not (
            abs(len(k) - len(pk)) >= 2 and (k.startswith(pk) or pk.startswith(k) or k.endswith(pk) or pk.endswith(k)))

    def same(v: str) -> bool:
        """The Library's word: the same letters and figures, read as as many words."""
        return bool(v) and key(v) == lk and len(v.split()) == len(lib.split())

    def clean(v: str) -> bool:
        return not STRAY.search(v) and not (STOPS.search(v) and list(joint.values()).count(v) < 2)

    if same(word):
        if not settled and clean(word):
            return word, True, None  # the Library corroborates the reading kept
        return word, settled, None
    matches = [v for v in joint.values() if same(v) and clean(v) and whole(v)]
    if not settled:
        if matches:
            matches.sort(key=lambda v: edge_marks(v) != edge_marks(lib))
            return matches[0], True, None
        return word, False, None if any(same(v) for v in joint.values()) or not whole(lib) else lib
    support = sum(1 for v in joint.values() if key(v) == key(word))
    if strict and (support < 2 or key(word) not in known):
        return word, False, None if any(same(v) for v in joint.values()) or not whole(lib) else lib
    return word, settled, None


# A word as printed: letters, with an inner apostrophe or hyphen, and
# ordinary punctuation before or after.
PLAIN = re.compile(r"^[(\"'\[‘“]*[A-Za-z]+(?:['’-][A-Za-z]+)*[.,;:!?'\")\]’”]*$")


def plain(tok: str) -> bool:
    """A cleanly printed word: PLAIN, with brackets that open and close."""
    return bool(PLAIN.match(tok)) and tok.count("(") == tok.count(")") and tok.count("[") == tok.count("]")

# Marks OCR leaves in a word that print does not: odd symbols (a slash is
# OCR's reading of "!" in italics), a doubled
# stop, and an asterisk inside a word (one before or after a word is a
# footnote mark).
STRAY = re.compile(r"[\\/^|~_{}<>]|(?<=\w)\*(?=\w)|([,.;:!?'\"])\1")
# Two different stops together ("naturally,.") are usually OCR noise, but
# print has them after abbreviations ("art.,", "&c.,"): they count as stray
# only when no other scan reads the word the same way.
STOPS = re.compile(r"[,;:][,.;:]|\.[,;:]")


def vote(readings: dict[str, str], known: set[str]) -> tuple[str, bool]:
    """Choose among scans' readings of one word. Returns (reading, settled).

    Readings are grouped by their letters and digits. The group most scans
    agree on wins; on a tie, a group whose letters form a known word beats one
    that does not, if it is like the primary's reading ("tliis" and "this",
    not "(ISrumlaer" and "Timber"); otherwise the primary scan's group is
    kept, unsettled.
    Within the winning group (same letters, possibly different marks), the
    primary's reading is used unless it has stray marks another reading lacks.

    A known word cleanly printed in the primary (see PLAIN) is never
    replaced by a reading that is not a known word (two scans agreeing on
    "CATO. serted" for "asserted" have picked up a running head). These
    stay unsettled whatever the count:
      * the primary cleanly reads a known word and the others another known
        word ("friends" against "citizens"): a real word is never silently
        replaced by a different one (but ")our" is not clean, so "your"
        wins);
      * the others read capitals where the main scan reads lower case
        ("CASSIUS." for "Ciiuse", i.e. "Cause"): a signature or heading
        lined up with the wrong word;
      * the others read a much shorter word ("moters" for "prometers"): a
        piece of a word broken at a line end, not a reading of it;
      * figures the scans read differently ("S181" against "2181"): the
        scans share confusions such as 2/S and 1/i, so a majority of them
        can be wrong about a number;
      * a word only the primary scan has (no other scan aligned there) that
        is not a known word: nothing corroborates it.
    """
    def elided(k: str) -> bool:
        """A scan reads the word with an elision ("renown'd") that the known
        word ("renowned") spells out: OCR dictionaries regularize these."""
        return k.endswith("ed") and any(re.search(r"\w'\s?d\b", v) for v in readings.values())

    def shouting(k: str) -> bool:
        """The others read capitals ("CASSIUS.") where the main scan reads a
        word in lower case ("Ciiuse"): a signature or heading misplaced."""
        if k == pk:
            return False
        caps = [r for r in groups[k] if sum(c.isalpha() for c in r) >= 3 and r.upper() == r]
        prim = readings["primary"]
        return bool(caps) and len(caps) == len(groups[k]) and any(c.islower() for c in prim)

    def alike(x: str, y: str) -> bool:
        return x == y or SequenceMatcher(None, x, y, autojunk=False).ratio() >= 0.6

    groups: dict[str, list[str]] = {}
    for src in sorted(readings, key=lambda s: s != "primary"):
        groups.setdefault(key(readings[src]), []).append(readings[src])
    pk = key(readings["primary"])
    ranked = sorted(groups, key=lambda k: (-len(groups[k]), k not in known, k != pk))
    top = ranked[0]
    settled = True
    if len(ranked) > 1 and pk in known and top not in known and plain(readings["primary"]):
        top = pk
    elif len(ranked) > 1:
        a, b = ranked[0], ranked[1]
        clean = getattr(known, "clean", None)
        if (clean is not None and len(pk) >= 2 and len(groups[a]) == len(groups[b]) and a in known and b in known
                and (a in clean) != (b in clean) and (pk in clean or (alike(a, pk) and alike(b, pk)))):
            # Both are known, but only one from the clean texts: the other is
            # known only because two scans agree on it, and scans share
            # misreadings ("eflfect" for "effect"), so the clean word wins.
            # Not for a single letter ("i," for "1,"): too little to go on.
            top = a if a in clean else b
        elif len(groups[a]) == len(groups[b]) and ((a in known) == (b in known) or not alike(a, pk) or elided(a)):
            settled = False
            top = pk
        elif (any(c.isdigit() for c in top) or (top != pk and pk in known and top in known and plain(readings["primary"]))
              or shouting(top) or len(top) < 0.75 * len(pk)):
            settled = False
            top = pk
    elif len(readings) == 1 and pk and pk not in known:
        settled = False
    candidates = groups[top]
    clean = [r for r in candidates
             if not STRAY.search(r) and (not STOPS.search(r) or list(readings.values()).count(r) >= 2)]
    if not clean:
        # Every reading of the winning letters has stray marks ("naturally^",
        # "naturally,."): keep the main scan's, for a human.
        return readings["primary"], False
    # A word read whole beats the same letters with a space in them, if it
    # is a known word and cleanly printed, and the pieces are not words
    # themselves ("com munity" -> "community", but not "a vast" -> "avast",
    # "us a" -> "usa" or "of conspiracy." -> "of.conspiracy.").
    # Of readings with the same letters, prefer one that ends in the same
    # marks as the main scan's ("January," not "January").
    tail = re.search(r"\W*$", readings["primary"]).group()
    clean.sort(key=lambda r: re.search(r"\W*$", r).group() != tail)
    whole = [r for r in clean if " " not in r and plain(r) and key(r) in known]
    pieces_are_words = all(key(t) in known for t in clean[0].split())
    if whole and " " in clean[0] and not pieces_are_words:
        return whole[0], settled
    return clean[0], settled


# OCR confusions scans of different copies share (the same engine, the same
# type): undoing one in a word the scans "agree" on that gives a clean word
# shows the agreement is a shared misreading ("eflfect" for "effect", the ff
# ligature; "wliole" for "whole").
SHARED_CONFUSIONS = (("flf", "ff"), ("fif", "ff"), ("ffl", "ff"), ("li", "h"), ("tli", "th"), ("rn", "m"),
                     ("vv", "w"), ("ii", "u"), ("cl", "d"))


def confused(right: str, read: str) -> bool:
    """True when `read` is `right` with one of the shared OCR confusions,
    either way ("discemable" for "discernable", "wliole" for "whole")."""
    return read != right and any(right.replace(x, y, 1) == read for a, b in SHARED_CONFUSIONS
                                 for x, y in ((a, b), (b, a)) if x in right)


class Vocabulary(set):
    """Known words: the clean texts' vocabulary (`clean`) and the words the
    scans attest (two scans reading a word identically). A word the scans
    attest that is a shared OCR confusion of a clean word is not added
    (`attest`); on a tie, a clean word beats one only the scans attest (see
    `vote`)."""

    def __init__(self, clean: set[str]):
        super().__init__(clean)
        self.clean = frozenset(clean)

    def misread(self, word: str) -> bool:
        return word not in self.clean and any(
            word.replace(a, b, 1) in self.clean for a, b in SHARED_CONFUSIONS if a in word)

    def attest(self, words: set[str]) -> None:
        self.update(w for w in words if not self.misread(w))


def known_words(clean: list[str]) -> set[str]:
    """Vocabulary of clean (non-OCR) texts.

    OCR output cannot vouch for itself: a misreading repeats on every page in
    one scan (a ligature read the same wrong way), and scans of different
    copies made with the same OCR engine share such misreadings. So only clean
    texts count; a rare word missing from them is flagged rather than guessed.
    """
    return {k for text in clean for t in TOKEN.findall(text) if is_word(k := key(t))}


# ------------------------------------------------------------ Tesseract
#
# A third reading where only two scans of a printing can be had (decision
# 47): Tesseract is run once on a scan's page images (a raw source) and its
# word boxes are kept in sources/ocr/, with a record of the tool, the
# language data, the command and the image file read (sources/ocr/manifest.json).
# Importers read the kept output; `make verify` checks the record but never
# runs Tesseract.

OCR_DIR = Path(__file__).resolve().parent.parent / "sources" / "ocr"
OCR_MANIFEST = OCR_DIR / "manifest.json"
TESSERACT_ARGS = ["-l", "eng", "--psm", "3", "tsv"]


def tesseract_versions() -> dict[str, str]:
    """The Tesseract and English data packages installed (Debian/Ubuntu)."""
    import subprocess
    out = {}
    for pkg in ("tesseract-ocr", "tesseract-ocr-eng"):
        out[pkg] = subprocess.run(["dpkg-query", "-W", "-f=${Version}", pkg], capture_output=True, text=True,
                                  check=True).stdout
    return out


def run_tesseract(images: list[tuple[int, bytes]], out_path: Path) -> None:
    """OCR page images (leaf, image bytes) into one TSV: Tesseract's own
    columns, prefixed with the leaf. Single-threaded, so that a rerun gives
    the same words."""
    import os
    import subprocess
    import tempfile
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for leaf, data in images:
            img = Path(tmp) / f"{leaf:04d}.tif"
            img.write_bytes(data)
            tsv = subprocess.run(["tesseract", str(img), "stdout", *TESSERACT_ARGS], capture_output=True,
                                 text=True, check=True, env=env).stdout.splitlines()
            if not rows:
                rows.append("leaf\t" + tsv[0])
            rows.extend(f"{leaf}\t{r}" for r in tsv[1:])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def parse_tesseract_tsv(path: Path) -> list[Page]:
    """Pages from a TSV written by `run_tesseract`, in leaf order: a
    paragraph per Tesseract paragraph, a line per line."""
    import csv
    pages: dict[int, Page] = {}
    paras: dict[tuple, Para] = {}
    lines: dict[tuple, Line] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            leaf, level = int(r["leaf"]), int(r["level"])
            x, y, w, h = (int(r[k]) for k in ("left", "top", "width", "height"))
            if level == 1:
                pages[leaf] = Page(leaf, w, h)
            elif level == 5 and (r["text"] or "").strip():
                pk = (leaf, r["block_num"], r["par_num"])
                lk = (*pk, r["line_num"])
                if pk not in paras:
                    paras[pk] = Para([], leaf)
                    pages[leaf].paras.append(paras[pk])
                if lk not in lines:
                    lines[lk] = Line([])
                    paras[pk].lines.append(lines[lk])
                lines[lk].words.append(Word(r["text"], x, y, x + w, y + h, int(float(r["conf"]))))
    return [pages[k] for k in sorted(pages)]
