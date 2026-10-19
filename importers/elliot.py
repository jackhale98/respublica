"""Patrick Henry's speeches in the Virginia ratifying convention, June
1788, from Elliot's Debates (decision 55).

Jonathan Elliot, ed., The Debates in the Several State Conventions on the
Adoption of the Federal Constitution, vol. 3 (Virginia, pp. 1-663), in the
standard pagination of the second edition: the Internet Archive's scan of
the 1907 Lippincott printing (DjVu XML) gives the layout and a first reading
of every word, checked against the OCR of three other copies of the same
pagination (1836, 1861, 1876) by the consensus of `importers/ocr.py`. The
Anti-Federalist Library's text of each speech is a tie-breaker only
(`importers/library.py`).

What is imported: the twenty-four speeches the Anti-Federalist Library
prints, each as Elliot prints it, from the paragraph that opens it (the
speaker's name in capitals: "Mr. HENRY.", "Mr. NICHOLAS informed the
committee ...") to the next speaker's paragraph or the next day's heading.
Where the Library's speech takes in another member's remarks (June 17,
June 23, June 24), so does the unit, with the speakers as Elliot names
them; nothing is trimmed. `SPEECHES` lists each one: the date, the printed
pages, the words that open it, how many speakers' paragraphs it takes in,
and who speaks next; the importer stops if any of these does not hold.

Refs: `Henry.{day}.{paragraph}`, the day as month and day (`Henry.Jun5.1`),
a second speech that day with a letter (`Henry.Jun14b`); notes
`Henry.{day}.fn{k}` (docs/references.md).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from importers import corrections, library
from importers.ocr import TOKEN, Block, Vocabulary, align, attested, blocks
from importers.ratification import clean_vocabulary, leaf_range, load_book, text_of_readings
from importers.ratification_series import BOOKS, SPEAKER
from tools.common import TEXTS_DIR, write_json

BOOK = "elliot-3"
WORK_ID = "patrick-henry"
PREFIX = "Henry"
TITLE = "Speeches of Patrick Henry in the Virginia Ratifying Convention"


@dataclass(frozen=True)
class Speech:
    library: str  # the Anti-Federalist Library's page ("henry1")
    date: dt.date
    pages: tuple[int, int]  # printed pages, first and last
    opens: str  # the words that open it (a pattern, as OCR reads them)
    then: str  # the next speaker, or the next day's heading
    speakers: int = 1  # speakers' paragraphs it takes in
    printed_day: str | None = None  # the weekday the day's heading prints, where it is not the date's


def _d(day: int) -> dt.date:
    return dt.date(1788, 6, day)


HENRY = r"Mr\W{0,2}\s+HENRY\b"
SPEECHES = [
    Speech("henry1", _d(5), (43, 64), HENRY + r"\W+Mr\W+C\w*airman,?\s+I\s+am\s+much", r"Gov\W+RANDOLPH"),
    Speech("henry2", _d(7), (137, 150), HENRY + r"\W+I\s+have\s+thought", r"Monday"),
    Speech("henry3", _d(9), (150, 176), HENRY + r"\W+Mr\W+Chairman,?\s+I\s+find\s+myself", r"Mr\W+LEE\b"),
    Speech("henry4", _d(12), (313, 328), HENRY + r"\W+Mr\W+Chairman,?\s+once\s+more", r"Mr\W+MADISON"),
    Speech("henry5", _d(13), (351, 356), HENRY + r"\W+Mr\W+Chairman\s*:?\s*I\s+hope", r"Mr\W+MADISON"),
    Speech("henry6", _d(14), (368, 369), HENRY + r"\W+Mr\W+Chairman,?\s+our\s+burden", r"Mr\W+MADISON"),
    Speech("henry7", _d(14), (384, 388), HENRY + r"\W+Mr\W+Chairman,?\s+in\s+my\s+judgment", r"Mr\W+NICHOLAS"),
    Speech("henry8", _d(14), (395, 399), HENRY + r"\W+Mr\W+Chairman,?\s+it\s+is\s+now\s+confessed", r"Mr\W+MADISON"),
    Speech("henry9", _d(16), (410, 412), HENRY + r"\s+thought\s+it\s+necessary", r"Mr\W+MADISON"),
    Speech("henry10", _d(16), (422, 424), HENRY + r"\s+still\s+retained", r"Mr\W+MADISON"),
    Speech("henry11", _d(16), (436, 438), HENRY + r"\s+entertained\s+strong", r"Mr\W+MADISON"),
    Speech("henry12", _d(16), (445, 449), HENRY + r"\W+Mr\W+Chairman,?\s+the\s+necessity", r"Mr\W+GRAYSON"),
    # Henry, George Nicholas's answer, and Henry's reply.
    Speech("henry13", _d(17), (455, 457), HENRY + r"\s+insisted", r"Mr\W+NICHOLAS", 3),
    Speech("henry14", _d(17), (460, 462), HENRY + r"\W+Mr\W+Chairman,?\s+we\s+have\s+now\s+come", r"Gov\W+RANDOLPH"),
    Speech("henry15", _d(17), (473, 476), HENRY + r"\W+Mr\W+Chairman,?\s+I\s+am\s+convinced", r"Mr\W+GEORGE\s+NICHOLAS"),
    Speech("henry16", _d(18), (500, 500), HENRY + r"\s+begged\s+gentlemen", r"Mr\W+MADISON"),
    Speech("henry17", _d(18), (502, 504), HENRY + r"\W+Mr\W+Chairman,?\s+gentlemen\s+say", r"Gov\W+RANDOLPH"),
    # The 1861-1907 printings head this day (p. 506) "Wednesday, June 18,
    # 1788." a second time; the 1836 printing reads "June 19" (erratum 60).
    Speech("henry18", _d(19), (512, 514), HENRY + r"\W+Mr\W+Chairman,?\s+this\s+great\s+national", r"Mr\W+MADISON",
           printed_day="wednesday"),
    Speech("henry19", _d(20), (539, 546), HENRY + r"\W+Mr\W+Chairman,?\s+I\s+have\s+already", r"Mr\W+PENDLETON"),
    # George Nicholas, then Henry's reply.
    Speech("henry20", _d(23), (576, 578), r"Mr\W{0,2}\s+NICHOLAS\s+informed\s+the\s+committee", r"Mr\W+MARSHALL", 2),
    # John Marshall's explanation, then Henry's answer.
    Speech("henry21", _d(23), (578, 580), r"Mr\W{0,2}\s+MARSHALL\s+rose\s+to\s+explain", r"Mr\W+STEPHENS", 2),
    # Henry's amendments, read in the middle of his speech, then "Mr. HENRY
    # then resumed the subject."
    Speech("henry22", _d(24), (587, 596), HENRY + r",?\s+after\s+observing", r"Gov\W+RANDOLPH", 2),
    Speech("henry23", _d(24), (622, 625), HENRY + r"\W+Mr\W+Chairman,?\s+the\s+honorable\s+gentleman", r"Mr\W+NICHOLAS"),
    Speech("henry24", _d(25), (649, 652), HENRY + r"\W+Mr\W+Chairman,?\s+when\s+we\s+were\s+told", r"Gov\W+RANDOLPH"),
]

WHO = re.compile(SPEAKER)
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DAY_HEADING = re.compile(r"^\s*(%s),?\s+J\w{2,6}\b" % "|".join(w.capitalize() for w in WEEKDAYS))


class ImportError_(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ImportError_(msg)


@dataclass
class Unit:
    speech: Speech
    key: str  # "Jun14b"
    label: str
    body: list[Block]
    notes: list[Block]


def day_heading(b: Block) -> bool:
    """A day's heading ("Saturday, June 14, 1788.")."""
    return b.kind == "text" and len(b.text.split()) <= 25 and bool(DAY_HEADING.match(b.text))


def find(speech: Speech, every: list[Block], lo: int, hi: int) -> tuple[int, list[Block]]:
    """Where a speech starts among the blocks (scan pages lo to hi), and its
    blocks: from the paragraph its opening words begin to the next
    speaker's paragraph (after `speakers` of them) or the next day's
    heading, which must be `then`."""
    opens = re.compile(speech.opens)
    start = None
    for k, b in enumerate(every):
        if not lo <= b.leaves[0] <= hi or b.kind != "text":
            continue
        m = opens.search(b.text)
        if not m:
            continue
        # The opening words begin the block, or follow a note of the
        # reporter's in brackets that OCR ran into it ("[The 1st and 2d
        # sections ...] Mr. NICHOLAS informed ..."), which is left out.
        _expect(m.start() == 0 or b.text[:m.start()].rstrip().endswith("]"),
                f"{speech.library}: the opening words are inside a paragraph: {b.text[:m.start() + 40]!r}")
        if m.start():
            every[k:k + 1] = [Block(b.text[:m.start()].strip(), b.leaves, b.folios, b.kind, b.first_indented),
                              Block(b.text[m.start():], b.leaves[-1:], b.folios[-1:], b.kind, True)]
            k += 1
        start = k
        break
    _expect(start is not None, f"{speech.library}: {speech.opens!r} not found on pp. {speech.pages[0]}–{speech.pages[1]}")
    out, speakers = [], 0
    for b in every[start:]:
        if b.kind == "text" and (WHO.match(b.text) or day_heading(b)):
            speakers += 1
            if speakers > speech.speakers or day_heading(b):
                _expect(bool(re.match(speech.then, b.text)),
                        f"{speech.library}: expected {speech.then!r} after the speech, found {b.text[:60]!r}")
                _expect(out[-1].leaves[-1] <= hi, f"{speech.library}: runs past p. {speech.pages[1]}")
                return start, out
        out.append(b)
    raise ImportError_(f"{speech.library}: no speaker after the speech on pp. {speech.pages[0]}–{speech.pages[1]}")


def check_date(speech: Speech, every: list[Block], start: int) -> None:
    """The day's heading before the speech names the speech's weekday
    ("Saturday, June 14, 1788."; OCR garbles the figures, not the names)."""
    head = next((b for b in reversed(every[:start]) if day_heading(b)), None)
    _expect(head is not None, f"{speech.library}: no day's heading before it")
    read = DAY_HEADING.match(head.text).group(1).lower()
    _expect(read == (speech.printed_day or WEEKDAYS[speech.date.weekday()]),
            f"{speech.library}: dated {speech.date}, but the day's heading before it reads {head.text[:40]!r}")


def units() -> list[Unit]:
    book = load_book(BOOK)
    every = blocks(book.pages, *leaf_range(book, 1, 663))
    out: list[Unit] = []
    seen: dict[str, int] = {}
    for sp in SPEECHES:
        lo, hi = leaf_range(book, *sp.pages)
        start, body = find(sp, every, lo, hi)
        check_date(sp, every, start)
        day = f"Jun{sp.date.day}"
        seen[day] = seen.get(day, 0) + 1
        key = day + ("" if seen[day] == 1 else "bcdefgh"[seen[day] - 2])
        label = f"June {sp.date.day}, 1788" + ("" if seen[day] == 1 else f" ({seen[day]})")
        out.append(Unit(sp, key, label, [b for b in body if b.kind == "text"], [b for b in body if b.kind == "note"]))
    return out


# ------------------------------------------------------------ text


@dataclass
class Prepared:
    units: list[Unit]
    readings: dict[int, list[dict]]  # id(block) -> per-token readings
    library: dict[int, list[str | None]]  # id(block) -> the Library's reading of each token


def prepare(us: list[Unit]) -> Prepared:
    """Each block's words aligned with the other scans' readings, and with
    the Library's text of the speech."""
    book = load_book(BOOK)
    hints: dict[str, int] = {}
    readings: dict[int, list[dict]] = {}
    lib: dict[int, list[str | None]] = {}
    for u in us:
        tokens = [TOKEN.findall(b.text) for b in u.body]
        flat = [t for ts in tokens for t in ts]
        aligned = align(flat, book.refs, hints)
        lib_flat = library.readings(flat, library.page_for("Henry", u.speech.library))
        at = 0
        for b, ts in zip(u.body, tokens):
            readings[id(b)] = aligned[at:at + len(ts)]
            lib[id(b)] = lib_flat[at:at + len(ts)]
            at += len(ts)
        for b in u.notes:
            readings[id(b)] = align(TOKEN.findall(b.text), book.refs, dict(hints))
    return Prepared(us, readings, lib)


def build(p: Prepared, known: set[str]) -> dict:
    bookdef = BOOKS[BOOK]
    divisions, segments = [], []
    for u in p.units:
        base = f"{PREFIX}.{u.key}"
        divisions.append({"attribution": ATTRIBUTION, "date": u.speech.date.isoformat(), "label": u.label,
                          "level": 1, "ref": base})
        for kind, bs, ref_of, label_of in (
                (None, u.body, lambda n: f"{base}.{n}", lambda n: f"Henry, {u.label}, ¶ {n}"),
                ("footnote", u.notes, lambda n: f"{base}.fn{n}", lambda n: f"Henry, {u.label}, note {n}")):
            for n, b in enumerate(bs, 1):
                # Elliot's text is the printing the Library follows: a settled
                # word it reads differently is left for a person (`strict`).
                text, spans, fixed = corrections.apply(
                    ref_of(n), *text_of_readings(p.readings[id(b)], known, p.library.get(id(b)), strict=True))
                seg = {"label": label_of(n), "pages": b.folios, "ref": ref_of(n),
                       "scan": {"item": bookdef["item"], "leaves": b.leaves}, "text": text}
                if kind:
                    seg["kind"] = kind
                if spans:
                    seg["uncertain"] = spans
                if fixed:
                    seg["corrected"] = fixed
                segments.append(seg)
    pages = [int(f) for s in segments for f in s["pages"]]
    return {
        "attribution": ATTRIBUTION,
        "date": f"{p.units[0].speech.date.isoformat()}/{p.units[-1].speech.date.isoformat()}",
        "divisions": divisions,
        "edition": {"name": bookdef["edition"],
                    "notes": f"{bookdef['edition']}, pp. {min(pages)}–{max(pages)}: the Virginia convention's "
                             "debates, June 5–25, 1788. The speeches of Patrick Henry that the Anti-Federalist "
                             "Library prints, each as Elliot prints it, with any other member's remarks it takes "
                             "in. Read from OCR scans and checked word by word against scans of three other copies; "
                             "where they disagreed, the Library's text was used to choose among their readings, "
                             "never to add one; words still unsettled are marked as uncertain. See docs/editions.md."},
        "id": WORK_ID,
        "position": "anti",
        "ref_prefix": PREFIX,
        "segments": segments,
        "short": "Patrick Henry",
        "source_ids": [bookdef["primary"], *bookdef["references"].values(),
                       *library.source_ids("Henry", [u.speech.library for u in p.units])],
        "title": TITLE,
    }


# Elliot names him "Mr. HENRY" in the debates, and in full in the volume's
# contents ("Mr. Patrick Henry").
ATTRIBUTION = {"byline": "Patrick Henry", "kind": "single", "names": ["Patrick Henry"],
               "source": "Elliot, Debates, vol. 3, the speakers as printed (\"Mr. HENRY\")"}


def run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    p = prepare(units())
    known = Vocabulary(clean_vocabulary())
    for r in p.readings.values():
        known.attest(attested(r))
    path = out_dir / f"{WORK_ID}.json"
    write_json(path, build(p, known))
    return [path]


if __name__ == "__main__":
    for path in run():
        print(f"wrote {path}")
