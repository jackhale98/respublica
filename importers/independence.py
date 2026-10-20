"""The road to independence, 1774–1776 (decision 66): the Continental
Congress's Declaration and Resolves of October 14, 1774, its Declaration of
the Causes and Necessity of Taking Up Arms (July 6, 1775), its resolution of
May 10, 1776 on forming new governments and the preamble of May 15, the Lee
Resolution (June 7, 1776), its proceedings on independence of July 2 and 4,
1776, the Virginia Declaration of Rights (June 12, 1776) and Jefferson's
draft preamble for the Virginia constitution (June 1776).

Two kinds of source:

- **Typed transcriptions** (`importers/tcp.py`): where the Text Creation
  Partnership's Evans-TCP has keyed a contemporary printing, its TEI text is
  the text (the Declaration of the Causes, from Fowle's Portsmouth broadside
  of 1775; the Declaration of Rights, from the Richmond printing of 1784 or
  1785). Where the Internet Archive has a scan of the same printing, every
  word is checked against the scan's OCR (`tcp.cross_check`).
- **Scans read by consensus** (`importers/ocr.py`), where no TCP text
  exists: the Library of Congress's edition of the Journals of the
  Continental Congress (ed. Worthington C. Ford, 1904–06), whose volumes are
  not in Evans, and Paul Leicester Ford's Writings of Thomas Jefferson
  (1893), the first printing of Jefferson's draft. The University of
  California's scan of each volume gives the layout and a first reading of
  every word, checked against the OCR of other copies. Where a book prints
  two texts side by side, the right column is the one imported
  (`importers/parallel.py`).

Each work's parts are listed below (`WORKS`): for a part, its printed
pages, the words that open its first paragraph and close its last (as OCR
reads them; the importer stops if either is missing), and the editor's notes
it takes in, each named by its page and the words that open and close it.
Refs: docs/references.md ("The road to independence").
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from importers import corrections, tcp
from importers.ocr import (TOKEN, Block, Reference, Vocabulary, align, attested, blocks, classify, key,
                           parse_djvu_xml, set_aside)
from importers.parallel import mark_notes, right_column
from importers.ratification import clean_vocabulary, text_of_readings
from tools.common import TEXTS_DIR, raw_path, write_json


class ImportError_(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ImportError_(msg)


# ------------------------------------------------------------ books read from scans


@dataclass(frozen=True)
class Columns:
    """A page printed in two columns, of which the right one is imported:
    where its columns begin (`columns_from`, when full-width text comes
    first) and where the editor's notes below them begin (`notes_from`, when
    their type is too close to the text's to tell), as patterns of the line."""
    columns_from: str | None = None
    notes_from: str | None = None
    clauses: bool = False  # a clause's line at the margin begins a paragraph (`parallel.outdented`)


@dataclass(frozen=True)
class Book:
    edition: str
    short: str
    item: str  # the primary scan's Internet Archive item (page links)
    primary: str  # source id (DjVu XML)
    references: dict[str, str]  # name -> source id (DjVu XML, read like the primary)
    head: str  # the running head, as OCR reads it
    signature: str | None = None  # the printer's signature mark at the foot of a page
    columns: dict[int, Columns] = field(default_factory=dict)


JCC = "Worthington Chauncey Ford, ed., Journals of the Continental Congress, 1774–1789 (Washington: Government Printing Office)"
JCC_HEAD = r"Journals\s+of\s+Congress|^\S{0,4}\s*[A-Z][a-z]+\W{0,2}\s*17\d\d\b"
JCC_SIGNATURE = r"^\d{3,6}\s*[—-]+\s*[VY]OL"
BOOKS = {
    "jcc-1": Book(
        f"{JCC}, vol. 1 (1904)", "Journals of the Continental Congress, vol. 1", "journalsofcontin01unit",
        "ia-road-jcc-v1-uc-xml", {"google": "ia-road-jcc-v1-google-xml", "upload": "ia-road-jcc-v1-upload-xml"},
        JCC_HEAD, JCC_SIGNATURE,
        # John Sullivan's draft on the left, the resolutions as adopted on the right.
        {63: Columns(columns_from=r"Draught|since\s+the\s+\S*ession"), **{p: Columns() for p in range(64, 74)}}),
    "jcc-4": Book(
        f"{JCC}, vol. 4 (1906)", "Journals of the Continental Congress, vol. 4", "journalsofcontin04unit",
        "ia-road-jcc-v4-uc-xml", {"upload": "ia-road-jcc-v4-upload-xml", "google": "ia-road-jcc-v4-google-xml",
                                  "michigan": "ia-road-jcc-v4-michigan-xml"},
        JCC_HEAD, JCC_SIGNATURE),
    "jcc-5": Book(
        f"{JCC}, vol. 5 (1906)", "Journals of the Continental Congress, vol. 5", "journalscontinen05unit",
        "ia-road-jcc-v5-uc-xml", {"acpl": "ia-road-jcc-v5-acpl-xml", "michigan": "ia-road-jcc-v5-michigan-xml",
                                  "upload": "ia-road-jcc-v5-upload-xml"},
        JCC_HEAD, JCC_SIGNATURE),
    "ford-jefferson-2": Book(
        "Paul Leicester Ford, ed., The Writings of Thomas Jefferson, vol. 2 (New York: G. P. Putnam's Sons, 1893)",
        "Ford, Writings of Thomas Jefferson, vol. 2", "writingsofthom02jeff",
        "ia-road-ford-v2-uc-xml", {"harvard": "ia-road-ford-v2-harvard-xml", "ucgoogle": "ia-road-ford-v2-ucgoogle-xml"},
        r"WRIT\w*\s+OF|JEFF\w*SON",
        None,
        # The first draft on the left, the fair copy on the right; Ford's note
        # on the history of the draft runs below them on pp. 7-9.
        {7: Columns(columns_from=r"DRAFT|FAIR", notes_from=r"fair\s+copy\s+is\s+endorsed", clauses=True),
         8: Columns(notes_from=r"^\W*pare\s+a\b", clauses=True),
         9: Columns(notes_from=r"^\W*work\s+of\s+George", clauses=True),
         **{p: Columns(clauses=True) for p in range(10, 14)}}),
}


@lru_cache(maxsize=None)
def scan_pages(book_key: str, source: str, first: int, last: int) -> tuple:
    """A scan's pages between two printed pages, read as `ocr.blocks` reads
    them: running heads and signature marks set aside, the editor's notes
    marked, and each page printed in two columns cut to its right column."""
    book = BOOKS[book_key]
    pages = parse_djvu_xml(raw_path(source))
    set_aside(pages, book.signature, None, book.head)
    classify(pages)
    out = []
    for p in pages:
        if not (p.number and p.number.isdigit() and first <= int(p.number) <= last):
            continue
        mark_notes(p)
        col = book.columns.get(int(p.number))
        out.extend(right_column(p, col.columns_from, col.notes_from, col.clauses) if col else [p])
    _expect(bool(out), f"{source}: no pages numbered {first}-{last}")
    return tuple(out)


def reference_text(book_key: str, name: str, first: int, last: int, kind: str) -> str:
    """A reference scan's text or its notes (`kind`: text | note), its pages
    read like the primary's (so a page in columns gives only its right
    column). Text and notes are kept apart, so that a passage is never
    matched with a note's words (the editor's notes quote the text)."""
    sid = BOOKS[book_key].references[name]
    return "\n\n".join(b.text for b in blocks(list(scan_pages(book_key, sid, first, last))) if b.kind == kind)


# ------------------------------------------------------------ works


@dataclass(frozen=True)
class Note:
    page: int  # the printed page it begins on
    opens: str  # its first words (a pattern, as OCR reads them)
    closes: str  # its last words


@dataclass(frozen=True)
class Part:
    key: str | None  # "May10", or None for a work of one part
    label: str
    date: dt.date
    pages: tuple[int, int]  # printed pages, first and last
    opens: str  # the words that begin its first paragraph (a pattern)
    closes: str  # the words that end its last paragraph
    notes: tuple[Note, ...] = ()
    # Runs of paragraphs printed as a list (the signers): from the paragraph
    # the first pattern begins to the one before the paragraph the second
    # begins; each run is one passage.
    lists: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Work:
    id: str
    prefix: str
    title: str
    short: str
    date: str
    attribution: dict
    book: str | None  # BOOKS key, for a work read from scans
    parts: tuple[Part, ...] = ()
    tcp: tcp.Text | None = None  # for a work from a TCP transcription
    about: str = ""  # what the work takes in, for its edition notes


CONGRESS = {"byline": "The Continental Congress", "kind": "body", "names": ["Continental Congress"]}
D = dt.date
WORKS = (
    Work("resolves-1774", "Resolves1774", "The Declaration and Resolves of the First Continental Congress",
         "Declaration and Resolves", "1774-10-14", CONGRESS, "jcc-1", (
             Part(None, "October 14, 1774", D(1774, 10, 14), (63, 73),
                  r"The\s+Congress\s+met\s+according\s+to\s+adjournment", r"already\s+entered\s+into\.",
                  notes=(Note(63, r"Ward\s+objected", r"E\S*amina\S*"),
                         Note(73, r"This\s+paragraph\s+was\s+struck\s+out", r"struck\s+out\."))),),
         about="The day's proceedings of October 14, 1774, and the resolutions as adopted, which the Journals print "
               "in the right-hand column beside John Sullivan's draft (left out), with the editor's notes on them."),
    Work("causes-1775", "Causes1775",
         "A Declaration Setting Forth the Causes and Necessity of Taking Up Arms", "Causes and Necessity",
         "1775-07-06", CONGRESS, None,
         tcp=tcp.Text("tcp-n11512-xml", "N11512", "Evans 14550", "declaration",
                      "A Declaration by the Representatives of the United Colonies of North-America, now met in "
                      "General Congress at Philadelphia, Setting forth the Causes and Necessity of their Taking up "
                      "Arms ([Portsmouth, N.H.]: sold at the printing-office in Portsmouth [Daniel Fowle], 1775), "
                      "a broadside"),
         about="The declaration as adopted on July 6, 1775, in the broadside printed at Portsmouth, New Hampshire; "
               "its woodcut view of Boston and the cut's caption are left out."),
    Work("new-governments-1776", "Governments1776",
         "The Resolution of May 10, 1776, and its Preamble of May 15", "Resolution and preamble, May 1776",
         "1776-05-10/1776-05-15", CONGRESS, "jcc-4", (
             Part("May10", "May 10, 1776", D(1776, 5, 10), (342, 342),
                  r"The\s+Congress\s+then\s+resumed\s+the\s+consideration\s+of\s+the\s+report",
                  r"H\[enry\]\s+Lee\.$"),
             Part("May15", "May 15, 1776", D(1776, 5, 15), (357, 358),
                  r"The\s+Congress\s+took\s+into\s+consideration\s+the\s+draught\s+of\s+the\s+preamble",
                  r"10th\s+instant,\s+be\s+published\.\W{0,3}$",
                  notes=(Note(358, r"This\s+preamble\s+was\s+drawn", r"22\s+May,\s+1776\."),)),
         ),
         about="The Journals' entries for May 10, 1776 (the resolution recommending that the colonies adopt "
               "governments, and the committee to prepare a preamble) and May 15 (the preamble, and the order to "
               "publish both)."),
    Work("lee-resolution-1776", "LeeResolution", "The Lee Resolution", "Lee Resolution", "1776-06-07", CONGRESS,
         "jcc-5", (
             Part(None, "June 7, 1776", D(1776, 6, 7), (425, 426),
                  r"Certain\s+resolutions", r"same\s+into\s+consideration\.$",
                  notes=(Note(425, r"This\s+resolution,\s+in\s+the\s+writing\s+of\s+Richard",
                              r"seconded\s+by\s+John\s+Adams\."),)),),
         about="The Journals' entry for June 7, 1776: the resolutions respecting independency as moved and "
               "seconded, and their referral to the next day, with the editor's note on the manuscript."),
    Work("independence-1776", "Independence1776", "The Proceedings on Independence, July 2 and 4, 1776",
         "Proceedings on independence", "1776-07-02/1776-07-04", CONGRESS, "jcc-5", (
             Part("Jul2", "July 2, 1776", D(1776, 7, 2), (506, 507),
                  r"The\s+Congress\s+resumed\s+the\s+consideration\s+of\s+the\s+resolu",
                  r"declaration\s+on\s+independ\s*-?\s*ence\.$",
                  notes=(Note(507, r"This\s+report,\s+in\s+the\s+writing\s+of\s+Charles", r"folio\s+17\."),)),
             Part("Jul4", "July 4, 1776", D(1776, 7, 4), (510, 516),
                  r"Agreeable\s+to\s+the\s+order\s+of\s+the\s+day", r"head\s+of\s+the\s+army\.\W{0,3}$",
                  notes=(Note(515, r"The\s+text\s+used\s+is\s+that\s+of\s+the\s+engrossed",
                              r"Department\s+of\s+State\."),
                         Note(516, r"A\s+determined\s+resolution", r"end\s+of\s+this\s+year\.")),
                  lists=((r"John\s+Hancock", r"Ordered,\s+That\s+the\s+declaration\s+be\s+authenticated"),)),
         ),
         about="The Journals' entries on independence: on July 2, 1776, the resolution of independence and the "
               "Congress's first day in committee of the whole on the declaration; on July 4, the declaration's "
               "adoption, its text as the Journals print it (from the engrossed parchment) with the signers, and "
               "the orders for printing and proclaiming it."),
    Work("virginia-declaration-of-rights", "VirginiaRights", "The Virginia Declaration of Rights",
         "Virginia Declaration of Rights", "1776-06-12",
         {"byline": "The Virginia Convention", "kind": "body", "names": ["Virginia Convention"]}, None,
         tcp=tcp.Text("tcp-n15245-xml", "N15245", "Evans 18818", "declaration_of_rights",
                      "The Articles of Confederation; the Declaration of Rights; the Constitution of the "
                      "Commonwealth, and the Articles of the Definitive Treaty between Great-Britain and the United "
                      "States of America (Richmond: Dixon and Holt, [1784 or 1785]), pp. 12–14",
                      scan=tcp.Scan("ia-ecco-va-1784-xml",
                                    "bim_eighteenth-century_the-articles-of-confeder_virginia-constitution_1784")),
         about="The Declaration of Rights adopted by the Virginia Convention on June 12, 1776, as the Commonwealth "
               "printed it by order of the General Assembly in 1784 or 1785, with its heading and sixteen articles."),
    Work("jefferson-virginia-preamble-1776", "JeffersonPreamble",
         "Jefferson's Draft Preamble for the Virginia Constitution", "Jefferson's draft preamble", "1776-06",
         {"byline": "Thomas Jefferson", "kind": "single", "names": ["Thomas Jefferson"],
          "source": "Ford, Writings of Thomas Jefferson, vol. 2, p. 7 (\"Proposed Constitution for Virginia\")"},
         "ford-jefferson-2", (
             Part(None, "June 1776", D(1776, 6, 1), (7, 13),
                  r"\W*A\s+Bi\S*\s+for\s+new", r"within\s+this\s+colony\.$",
                  notes=(Note(7, r"The\s+fair\s+copy\s+is\s+endorsed", r"development\s+of\s+\S+\s+mind\."),)),),
         about="The fair copy of Jefferson's proposed constitution for Virginia, from its title to the end of the "
               "clause deposing the king (its preamble, which the Virginia Convention adopted in amended form, and "
               "the first enacting clause), as Ford prints it in the right-hand column beside the first draft (left "
               "out), with Ford's note on the manuscripts; Jefferson's deletions are printed struck through and are "
               "read by OCR as words."),
)


# ------------------------------------------------------------ a work read from scans


@dataclass
class Unit:
    part: Part
    body: list[Block]  # its paragraphs (a run printed as a list is one Block)
    notes: list[Block]


SENTENCE_END = re.compile(r"[.:;?!]\W{0,3}$")


def heading_run_on(prev: Block, b: Block) -> bool:
    """A heading set over two lines that OCR made two blocks ("The unanimous
    Declaration of the thirteen United States of" / "America."), or a short
    line left by a gap in the manuscript ("Whereas George" / "Guelf king of
    ..."): the first is short and stops on a word."""
    return len(prev.text.split()) <= 12 and bool(re.search(r"[A-Za-z]$", prev.text)) and b.kind == "text"


NOTE_START = re.compile(r"^\s*(?:[*†‡§^'‘’]|\d{1,2}\s)")


def cut_note(every: list[Block], note: Note, lo: int, hi: int) -> Block:
    """The note's text among the blocks of its page (and, for a note that runs
    on, the blocks after): from its opening words to its closing words. The
    text taken is removed from the blocks it was in."""
    opens, closes = re.compile(note.opens), re.compile(note.closes)
    for k, b in enumerate(every):
        if not (lo <= b.leaves[0] <= hi) or b.kind not in ("note", "text"):
            continue
        m = opens.search(b.text)
        if not m:
            continue
        # The note's own mark before its words (OCR's "'", "^", a figure).
        start = m.start()
        mark = re.search(r"\S{1,2}\s*$", b.text[:start])
        if mark and not re.search(r"[A-Za-z]{2}", mark.group(0)):
            start = mark.start()
        taken, leaves, folios = [], [], []
        for j in range(k, len(every)):
            c = every[j]
            # (After its first block, the note goes on in the notes that
            # follow, past any other note, which begins with its mark.)
            if j > k and (c.kind != "note" or NOTE_START.match(c.text)):
                continue
            s = start if j == k else 0
            e = closes.search(c.text, s)
            end = e.end() if e else len(c.text)
            taken.append(c.text[s:end])
            leaves += [x for x in c.leaves if x not in leaves]
            folios += [x for x in c.folios if x not in folios]
            rest = (c.text[:s] + " " + c.text[end:]).strip()
            every[j] = Block(rest, c.leaves, c.folios, c.kind, c.first_indented, c.heading)
            if e:
                return Block(" ".join(t.strip() for t in taken), leaves, folios, "note")
        break
    raise ImportError_(f"note {note.opens!r} … {note.closes!r} not found from p. {note.page}")


def find_unit(part: Part, every: list[Block], lo: int, hi: int) -> Unit:
    opens, closes = re.compile(part.opens), re.compile(part.closes)
    start = next((k for k, b in enumerate(every) if b.kind == "text" and lo <= b.leaves[0] <= hi
                  and opens.match(b.text)), None)
    _expect(start is not None, f"{part.label}: {part.opens!r} does not begin a paragraph on pp. "
                               f"{part.pages[0]}-{part.pages[1]}")
    body: list[Block] = []
    for b in every[start:]:
        if b.kind != "text" or not b.text:
            continue
        _expect(b.leaves[0] <= hi, f"{part.label}: {part.closes!r} not found by p. {part.pages[1]}")
        if body and heading_run_on(body[-1], b):
            last = body[-1]
            body[-1] = Block(f"{last.text} {b.text}", last.leaves + [x for x in b.leaves if x not in last.leaves],
                             last.folios + [x for x in b.folios if x not in last.folios], "text")
        else:
            body.append(b)
        if closes.search(b.text):
            break
    for first, after in part.lists:
        i = next((k for k, b in enumerate(body) if re.match(first, b.text)), None)
        j = next((k for k, b in enumerate(body) if re.match(after, b.text)), None)
        _expect(i is not None and j is not None and i < j, f"{part.label}: the list {first!r} … {after!r} not found")
        run = body[i:j]
        joined = Block(" ".join(b.text for b in run), sorted({x for b in run for x in b.leaves}),
                       list(dict.fromkeys(f for b in run for f in b.folios)), "text")
        body[i:j] = [joined]
    return Unit(part, body, [])


def scan_units(work: Work) -> tuple[list[Unit], dict[str, list[Reference]]]:
    book = BOOKS[work.book]
    first = min(p.pages[0] for p in work.parts)
    last = max(p.pages[1] for p in work.parts) + 1
    pages = scan_pages(work.book, book.primary, first, last)
    leaf_of = {}
    for p in pages:
        leaf_of.setdefault(int(p.number), p.leaf)
    units = []
    for part in work.parts:
        every = blocks(list(pages))
        _expect(part.pages[0] in leaf_of and part.pages[1] in leaf_of,
                f"{work.id}: pp. {part.pages[0]}-{part.pages[1]} are not all in the scan")
        notes = []
        for n in part.notes:
            _expect(n.page in leaf_of, f"{work.id}: p. {n.page} is not in the scan")
            notes.append(cut_note(every, n, leaf_of[n.page], leaf_of[n.page]))
        unit = find_unit(part, every, leaf_of[part.pages[0]], leaf_of[part.pages[1]])
        unit.notes = notes
        units.append(unit)
    refs = {kind: [Reference(name, reference_text(work.book, name, first, last, kind)) for name in book.references]
            for kind in ("text", "note")}
    return units, refs


SPACED_HYPHEN = re.compile(r"\b([A-Za-z]{2,}) [-­] ([a-z]+)\b")


def rejoin(text: str, clean: set[str]) -> str:
    """A word broken at a line's end whose hyphen OCR set apart ("independ -
    ence.", "New Hamp - shire") is rejoined where the whole is a word of the
    clean texts, as `ocr.lines_to_text` rejoins one whose hyphen it read in
    place; otherwise the pieces are left as read."""
    return SPACED_HYPHEN.sub(lambda m: m.group(1) + m.group(2) if key(m.group(1) + m.group(2)) in clean
                             else m.group(0), text)


RUN = 60  # words aligned at a time


def align_in_runs(tokens: list[str], refs: list[Reference], hints: dict[str, int]) -> list[dict]:
    """`ocr.align`, a run of words at a time: a passage that runs over a page
    break may be broken in another scan's text by what that scan put between
    (a note that runs on to the next page is printed after the next page's
    text), so each run is found on its own."""
    out: list[dict] = []
    for k in range(0, len(tokens), RUN):
        part = tokens[k:k + RUN]
        if len(tokens) - k - RUN < RUN // 3:  # (no short last run)
            part = tokens[k:]
            out += align(part, refs, hints)
            break
        out += align(part, refs, hints)
    return out


def build_scanned(work: Work, out_dir: Path) -> Path:
    book = BOOKS[work.book]
    units, refs = scan_units(work)
    clean = clean_vocabulary()
    for u in units:
        u.body = [Block(rejoin(b.text, clean), b.leaves, b.folios, b.kind, b.first_indented, b.heading) for b in u.body]
        u.notes = [Block(rejoin(b.text, clean), b.leaves, b.folios, b.kind) for b in u.notes]
    hints: dict[str, int] = {}
    readings: dict[int, list[dict]] = {}
    for u in units:
        # A part's paragraphs are found in the other scans together (a short
        # paragraph, "Certain resolutions ... being moved and seconded.", has
        # too few words to be found alone); each note on its own.
        tokens = [TOKEN.findall(b.text) for b in u.body]
        flat = align_in_runs([t for ts in tokens for t in ts], refs["text"], hints)
        at = 0
        for b, ts in zip(u.body, tokens):
            readings[id(b)] = flat[at:at + len(ts)]
            at += len(ts)
        for b in u.notes:
            readings[id(b)] = align_in_runs(TOKEN.findall(b.text), refs["note"], {})
    known = Vocabulary(clean_vocabulary())
    for r in readings.values():
        known.attest(attested(r))
    divisions, segments = [], []
    for u in units:
        base = f"{work.prefix}.{u.part.key}" if u.part.key else work.prefix
        where = f"{work.short}, {u.part.label}" if u.part.key else work.short
        if u.part.key:
            divisions.append({"date": u.part.date.isoformat(), "label": u.part.label, "level": 1, "ref": base})
        for kind, bs, ref_of, label_of in (
                (None, u.body, lambda n: f"{base}.{n}", lambda n: f"{where}, ¶ {n}"),
                ("footnote", u.notes, lambda n: f"{base}.fn{n}", lambda n: f"{where}, note {n}")):
            for n, b in enumerate(bs, 1):
                text, spans, fixed = corrections.apply(ref_of(n), *text_of_readings(readings[id(b)], known))
                seg = {"label": label_of(n), "pages": b.folios, "ref": ref_of(n),
                       "scan": {"item": book.item, "leaves": b.leaves}, "text": text}
                if kind:
                    seg["kind"] = kind
                if spans:
                    seg["uncertain"] = spans
                if fixed:
                    seg["corrected"] = fixed
                segments.append(seg)
    pages = [int(f) for s in segments for f in s["pages"]]
    doc = {
        "attribution": work.attribution,
        "date": work.date,
        "divisions": divisions,
        "edition": {"name": book.edition,
                    "notes": f"{book.edition}, pp. {min(pages)}–{max(pages)}. {work.about} Read from the OCR of the "
                             f"University of California's scan and checked word by word against the OCR of "
                             f"{len(book.references)} other copies; words the scans could not settle are marked as "
                             f"uncertain. See docs/editions.md."},
        "id": work.id,
        "ref_prefix": work.prefix,
        "segments": segments,
        "short": work.short,
        "source_ids": [book.primary, *book.references.values()],
        "title": work.title,
    }
    if not divisions:
        del doc["divisions"]
    path = out_dir / f"{work.id}.json"
    write_json(path, doc)
    return path


# ------------------------------------------------------------ a work from a TCP transcription


def build_tcp(work: Work, out_dir: Path) -> Path:
    t = work.tcp
    paras = tcp.paragraphs(t)
    checked = tcp.cross_check(t, paras, Vocabulary(clean_vocabulary())) if t.scan else None
    segments = []
    n = 0
    for k, p in enumerate(paras):
        if p.kind == "head":
            ref, label = f"{work.prefix}.Heading", f"{work.short}, heading"
        elif p.kind == "closer":
            ref, label = f"{work.prefix}.Closing", f"{work.short}, closing"
        else:
            n += 1
            ref, label = f"{work.prefix}.{n}", f"{work.short}, ¶ {n}"
        spans = checked[k][0] if checked else tcp.gap_spans(p)
        text, spans, fixed = corrections.apply(ref, p.text, spans)
        seg = {"label": label, "pages": p.pages, "ref": ref, "text": text}
        if checked and checked[k][1]:
            seg["scan"] = {"item": t.scan.item, "leaves": checked[k][1]}
        if spans:
            seg["uncertain"] = spans
        if fixed:
            seg["corrected"] = fixed
        segments.append(seg)
    _expect(len({s["ref"] for s in segments}) == len(segments), f"{work.id}: two passages share a ref")
    check = (f" Checked word by word against the OCR of the Internet Archive's scan of the same printing "
             f"({t.scan.item}): where the scan reads another word, the word is marked as uncertain, with the "
             f"scan's reading beside it." if t.scan else
             " No scan of this printing was found to check it against.")
    doc = {
        "attribution": work.attribution,
        "date": work.date,
        "edition": {"name": t.printing,
                    "notes": f"{t.printing}. {work.about} The text is the Text Creation Partnership's keyed "
                             f"transcription, Evans-TCP {t.tcp} ({t.evans}), released under CC0; letters and words "
                             f"the transcribers could not read are marked as uncertain, as the transcription marks "
                             f"them, never filled in.{check} See docs/editions.md."},
        "id": work.id,
        "ref_prefix": work.prefix,
        "segments": segments,
        "short": work.short,
        "source_ids": [t.source, *([t.scan.source] if t.scan else [])],
        "title": work.title,
    }
    path = out_dir / f"{work.id}.json"
    write_json(path, doc)
    return path


def run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    return [build_tcp(w, out_dir) if w.tcp else build_scanned(w, out_dir) for w in WORKS]


if __name__ == "__main__":
    import sys
    only = set(sys.argv[1:])
    for w in WORKS:
        if not only or w.id in only:
            print(f"wrote {build_tcp(w, TEXTS_DIR) if w.tcp else build_scanned(w, TEXTS_DIR)}")
