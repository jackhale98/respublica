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

Layout comes from one scan's DjVu XML, split into its two columns
(`importers/columns.py`); words are
checked against a second scan of the same printing read column by column
(see `importers/ocr.py`). Nothing is typed or corrected by hand.
"""

from __future__ import annotations

import datetime as dt
import statistics
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from importers import corrections
from importers.columns import body_span, is_speck, mark_notes, rows, split_columns
from importers.ocr import (
    TOKEN, Block, Page, Para, Reference, Vocabulary, align, attested, blocks, OCR_DIR, OCR_MANIFEST, TESSERACT_ARGS,
    body_margin, parse_djvu_xml, parse_tesseract_tsv, run_tesseract, split_paragraphs, tesseract_versions,
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
    mid = (left + right) / 2
    lines = [l for para in page.paras for l in para.lines]
    head_rows = []
    for row, pattern in zip([r for r in rows(lines) if not is_speck(r)][:2], (HEAD_FIRST, HEAD_SECOND)):
        text = " ".join(l.text for l in row)
        if row[0].words[0].y0 < 0.13 * page.height and pattern.search(text) and len(text.split()) <= 16:
            head_rows.append(row)
        else:
            break
    number_row = head_rows[0] if head_rows else []
    # Specks above or between the rows of the head go with it.
    top = max((l.words[0].y0 for row in head_rows for l in row), default=-1)
    head_rows = [r for r in rows(lines) if r[0].words[0].y0 <= top]
    head_ids = {id(l) for row in head_rows for l in row}
    head = " | ".join(" ".join(l.text for l in row) for row in head_rows)
    numbers: list[int | None] = [None, None]
    for w in sorted((w for l in number_row for w in l.words), key=lambda w: w.x0):
        m = re.fullmatch(r"\D?(\d{1,4})\D?", w.text.strip())
        if m:
            side = 0 if (w.x0 + w.x1) / 2 < mid else 1
            if numbers[side] is None or side == 1:
                numbers[side] = int(m.group(1))
    columns = split_columns(page, head_ids, 2, reference)
    if columns is None:
        return None  # set in one column
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
                text, spans, fixed = corrections.apply(ref_of(n), *text_of_readings(readings[id(b)], known))
                seg = {"columns": b.folios, "label": label_of(n), "ref": ref_of(n),
                       "scan": {"item": SCAN_ITEM, "leaves": b.leaves}, "text": text}
                if kind:
                    seg["kind"] = kind
                if spans:
                    seg["uncertain"] = spans
                if fixed:
                    seg["corrected"] = fixed
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


def run_1789(out_dir: Path = TEXTS_DIR) -> list[Path]:
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


# ============================================================ later debates (decision 59)
#
# The Eleventh Amendment (3d Congress, 1794) and the Twelfth (7th Congress,
# 1802, and 8th, 1803), from volumes 4, 11 and 13 of the same series, read
# as the 1789 debate is, with these differences:
#   * each house's proceedings on the amendment, one work per house and
#     Congress, are listed day by day (`ENTRIES`), with the columns each
#     day's item is printed in; an item is the one printed under the
#     subject's heading, or, where a house took the amendment up without a
#     heading (the Senate's journal-like proceedings of 1794 and 1802), the
#     paragraphs from the one that takes it up to the one that turns to
#     other business, named by their first words;
#   * the scans are kept as the pages needed, each a byte range of the
#     Internet Archive's DjVu XML (`cmd_fetch`), so the raw files stay small;
#   * the running head is recognised by its letters, not by exact words (the
#     Google scans of volume 13 are small and their OCR reads "HISXORT OF
#     CONaRBSS"), Google's mark ("Digitized by Google") is left out, a
#     heading OCR ran into a paragraph is set apart again, and column
#     numbers are settled as runs (`settle_runs`): OCR reads 5 as 6 so often
#     in volume 13 that the nearest pages can outvote the right number.


@dataclass(frozen=True)
class Scan:
    """A scan of a volume in the Internet Archive."""
    name: str  # the reading's key in `uncertain` ("microfilm", "nypl", …)
    item: str
    base: int  # the number in its DjVu XML's name for its first page (1 or 0)
    about: str  # whose copy, for the manifest


def is_google(scan: Scan) -> bool:
    return scan.item.endswith("goog")


@dataclass(frozen=True)
class Volume:
    number: int
    year: int  # of printing
    scans: tuple[Scan, ...]  # the first gives layout and words; the others are read against it
    # Readings made by one OCR engine (`independent`): "primary" is the first scan.
    same_engine: tuple[str, ...] = ()
    # A scan whose page images we read with Tesseract for one more reading
    # ("tesseract"; decision 46), where the others are too few or too poor.
    images: str | None = None

    @property
    def edition(self) -> str:
        return (f"Joseph Gales, Sr., comp., The Debates and Proceedings in the Congress of the United States "
                f"(Annals of Congress), vol. {self.number} (Washington: Gales and Seaton, {self.year})")


SIM = "sim_united-states-congress-debates-and-proceedings_"
MICROFILM = "a scan of a microfilm (Serials in Microfilm collection)"
# The Google scans' OCR is one engine's (it reads "ihe", "lo" and "Slates" alike in
# two copies), so their agreement alone never makes a word known (decision 46).
VOLUMES = {
    # Volume 4: the microfilm's OCR is the better (the Google scan is small,
    # and its OCR poor), so it gives layout and words; the Google scan's
    # page images are also read with Tesseract, the microfilm's engine.
    4: Volume(4, 1849, (
        Scan("microfilm", SIM + "december-2-1793-march-3-1795_2", 0, MICROFILM),
        Scan("nypl", "debatesandproce18galegoog", 0, "the Google scan of the New York Public Library's copy")),
        same_engine=("primary", "tesseract"), images="nypl"),
    11: Volume(11, 1851, (
        Scan("michigan", "debatesandproce09galegoog", 1, "the Google scan of the University of Michigan's copy"),
        Scan("nypl", "debatesandproce24galegoog", 0, "the Google scan of the New York Public Library's copy"),
        Scan("microfilm", SIM + "december-7-1801-march-3-1803", 0, MICROFILM)), same_engine=("primary", "nypl")),
    13: Volume(13, 1852, (
        Scan("harvard", "debatesandproce01unkngoog", 1, "the Google scan of Harvard University's copy"),
        Scan("michigan", "debatesandproce34galegoog", 1, "the Google scan of the University of Michigan's copy"),
        Scan("microfilm", SIM + "october-17-1803-march-3-1805", 0, MICROFILM)), same_engine=("primary", "michigan")),
}


@dataclass(frozen=True)
class Work:
    id: str
    prefix: str
    house: str  # "Senate" | "House"
    volume: int
    title: str
    short: str
    what: str  # the edition note's account of what is imported


@dataclass(frozen=True)
class Entry:
    """One item of a work: the day, the columns from where that day's
    proceedings begin to where the item ends (or the next day's begin), and,
    for an item printed without a heading of its own, the first words of
    its first paragraph (`start`) and of the paragraph after it (`until`;
    otherwise it runs to the next heading or day). Where the day began
    many columns before the item, `day_at` is the column of its heading:
    only that column and the item's are read."""
    prefix: str
    date: dt.date
    first: int
    last: int
    start: str | None = None
    until: str | None = None
    day_at: int | None = None


ELEVENTH = "the resolution proposing the Eleventh Amendment (the judicial power of the United States in suits against a State)"
TWELFTH = "the resolutions proposing the Twelfth Amendment (the designation of the persons voted for as President and Vice President)"
LATER_WORKS = (
    Work("senate-eleventh-amendment-1794", "Senate1794", "Senate", 4,
         "Proceedings in the Senate on the Eleventh Amendment, 1794", "Senate proceedings, 1794",
         f"each day's proceedings of the Senate on {ELEVENTH}, from the paragraph that takes it up to the one "
         "that turns to other business (the Senate's proceedings are printed without headings)"),
    Work("house-eleventh-amendment-1794", "House1794", "House", 4,
         "Proceedings in the House of Representatives on the Eleventh Amendment, 1794", "House proceedings, 1794",
         f"each day's proceedings of the House on {ELEVENTH}: the item headed \"Amendment to the Constitution\", "
         "and the paragraphs in which the House received and read the resolution"),
    Work("senate-twelfth-amendment-1802", "Senate1802", "Senate", 11,
         "Proceedings in the Senate on the designation of President and Vice President, 1802",
         "Senate proceedings, 1802",
         f"each day's proceedings of the Senate on {TWELFTH}, from the paragraph that takes them up to the one "
         "that turns to other business (the Senate's proceedings are printed without headings)"),
    Work("house-twelfth-amendment-1802", "House1802", "House", 11,
         "Debates in the House of Representatives on the designation of President and Vice President, 1802",
         "House debates, 1802",
         f"each day's proceedings of the House on {TWELFTH}: the item headed \"Amendments to the Constitution\", "
         "and the paragraphs in which a member offered the resolutions"),
    Work("senate-twelfth-amendment-1803", "Senate1803", "Senate", 13,
         "Debates in the Senate on the Twelfth Amendment, 1803", "Senate debates, 1803",
         f"every item of the Senate's proceedings headed \"Amendment to the Constitution\", and the paragraphs, "
         f"printed without that heading, in which the Senate took up {TWELFTH}"),
    Work("house-twelfth-amendment-1803", "House1803", "House", 13,
         "Debates in the House of Representatives on the Twelfth Amendment, 1803", "House debates, 1803",
         f"every item of the House's proceedings headed \"Amendment to the Constitution\", and the paragraphs, "
         f"printed without that heading, in which the House took up {TWELFTH}"),
)

D = dt.date
ENTRIES = (
    # The Eleventh Amendment, 1794 (vol. 4). The Senate's proceedings are
    # printed as a journal, without headings.
    Entry("Senate1794", D(1794, 1, 2), 25, 25, "A motion was made that it be"),
    Entry("Senate1794", D(1794, 1, 13), 29, 29, "Agreeably to the order of the day, the Senate took into",
          "The Senate resumed the consideration of the motion made the third"),
    Entry("Senate1794", D(1794, 1, 14), 30, 31, "Agreeably to the order of the day, the Senate took into",
          "The Senate proceeded to the consideration of the following motion"),
    Entry("Senate1794", D(1794, 3, 12), 65, 66, "Resolved, That the President of the United States be requested",
          "A message from the House of Representatives informed"),
    Entry("House1794", D(1794, 1, 15), 225, 225, "A message from the Senate informed the House that the Senate have passed a resolution",
          "The following Message was received"),
    Entry("House1794", D(1794, 1, 16), 235, 235, "The resolution sent from the Senate",
          "The following Message was received"),
    Entry("House1794", D(1794, 3, 4), 475, 478),
    Entry("House1794", D(1794, 3, 12), 499, 499, "A message from the Senate informed the House, that the Senate have come",
          "The House resolved itself into a Committee of the Whole House, on the bill"),
    # The Twelfth Amendment, 1802 (vol. 11). (A State's resolutions for
    # amendments, laid before a house, are not a house taking one up; nor
    # is Bradley's motion of April 16 for choosing Electors by districts.)
    Entry("Senate1802", D(1802, 4, 12), 258, 259, "The following motion was made by Mr. Clinton",
          "Agreeably to notice given on the 9th instant, Mr. S. T. Mason"),
    Entry("Senate1802", D(1802, 4, 13), 260, 260, "The Senate took into consideration the motion, made yesterday, for an amendment",
          "The Senate took into consideration the report of the committee"),
    Entry("Senate1802", D(1802, 4, 14), 261, 261, "The Senate resumed the consideration of the motion made on the 12th",
          "The Senate resumed the consideration of the report of the committee"),
    Entry("Senate1802", D(1802, 4, 15), 261, 263, "Ordered, That the consideration of the motion made on the 12th",
          "Friday, April 16"),
    Entry("Senate1802", D(1802, 5, 3), 303, 303, "A message from the House of Representatives informed the Senate that the House agree",
          "The bill, entitled"),
    Entry("Senate1802", D(1802, 5, 3), 303, 304, "The Senate took into consideration the resolution of the House of Representatives of the 1st of May",
          "On motion that the petition of David"),
    Entry("House1802", D(1802, 2, 19), 602, 603, "On motion made and seconded that the House do come to the following resolutions"),
    Entry("House1802", D(1802, 5, 1), 1285, 1296, day_at=1255),
    # The Twelfth Amendment, 1803 (vol. 13). (Not the committee's last
    # resolution, on re-eligibility to the presidency, December 6 and 12.)
    Entry("Senate1803", D(1803, 10, 21), 16, 17, "Mr. Clinton, after a few prefatory observations"),
    Entry("Senate1803", D(1803, 10, 22), 17, 21),
    Entry("Senate1803", D(1803, 10, 24), 21, 25),
    Entry("Senate1803", D(1803, 10, 25), 25, 26, "The resolution to amend the Constitution was"),
    Entry("Senate1803", D(1803, 11, 11), 76, 77, "On motion, that the Senate do now proceed to the consideration of the report",
          "The following Message was received"),
    Entry("Senate1803", D(1803, 11, 16), 78, 78, "On motion, it was agreed that the further consideration of the report"),
    Entry("Senate1803", D(1803, 11, 22), 80, 80, "The Senate resumed the consideration of the report of the committee to whom"),
    Entry("Senate1803", D(1803, 11, 23), 80, 91),
    Entry("Senate1803", D(1803, 11, 24), 91, 105),
    Entry("Senate1803", D(1803, 11, 25), 105, 106),
    Entry("Senate1803", D(1803, 11, 28), 106, 108),
    Entry("Senate1803", D(1803, 11, 29), 108, 124),
    Entry("Senate1803", D(1803, 11, 30), 124, 126),
    Entry("Senate1803", D(1803, 12, 1), 126, 136),
    Entry("Senate1803", D(1803, 12, 2), 136, 210),
    Entry("Senate1803", D(1803, 12, 12), 213, 214, "The Senate took into consideration the resolution sent from the House",
          "The Vice President signed the enrolled resolution last reported to have been"),
    Entry("Senate1803", D(1803, 12, 16), 218, 218, "The Senate resumed the consideration of the resolution of the House of Representatives, of the"),
    Entry("House1803", D(1803, 10, 17), 369, 372, "Mr. Dawson, after a few preliminary",
          "The Speaker laid before the House sundry papers"),
    Entry("House1803", D(1803, 10, 19), 374, 378),
    Entry("House1803", D(1803, 10, 20), 379, 381),
    Entry("House1803", D(1803, 10, 22), 382, 383),
    Entry("House1803", D(1803, 10, 24), 419, 431, day_at=385),
    Entry("House1803", D(1803, 10, 26), 489, 495),
    Entry("House1803", D(1803, 10, 27), 495, 496, "Ordered, That the resolution agreed to yesterday",
          "A memorial and petition of the Illinois"),
    Entry("House1803", D(1803, 10, 27), 495, 497),
    Entry("House1803", D(1803, 10, 28), 514, 545),
    Entry("House1803", D(1803, 10, 31), 551, 551, "Ordered, That the select committee of seventeen members",
          "Mr. John Randolph, jr., from the managers"),
    Entry("House1803", D(1803, 12, 5), 641, 643, "A message was received from the Senate, advising", "On motion, it was"),
    Entry("House1803", D(1803, 12, 6), 645, 663),
    Entry("House1803", D(1803, 12, 7), 663, 699),
    Entry("House1803", D(1803, 12, 8), 699, 776),
    Entry("House1803", D(1803, 12, 12), 777, 777, "On motion, it was", "The House proceeded to consider a motion of the",
          day_at=776),
)


def later_work(prefix: str) -> Work:
    return next(w for w in LATER_WORKS if w.prefix == prefix)


def entries_of(volume: int) -> list[Entry]:
    return [e for e in ENTRIES if later_work(e.prefix).volume == volume]


# ------------------------------------------------------------ later: sources

PART = re.compile(r"^ia-part-annals-v(\d+)-([a-z]+)-(\d{4})-(\d{4})$")
LICENSE = "Public domain in the USA (published {year}). OCR generated by the Internet Archive from its scan."


def part_id(volume: int, scan: Scan, first: int, last: int) -> str:
    return f"ia-part-annals-v{volume}-{scan.name}-{first:04d}-{last:04d}"


def parts(volume: int, scan: Scan) -> list[tuple[int, int, str]]:
    """The runs of scan pages kept of a scan: (first leaf, last leaf, source id)."""
    out = []
    for e in load_manifest():
        m = PART.match(e["id"])
        if m and int(m.group(1)) == volume and m.group(2) == scan.name:
            out.append((int(m.group(3)), int(m.group(4)), e["id"]))
    return sorted(out)


def later_pages(volume: int, scan: Scan) -> list[Page]:
    from importers.ocr import parse_djvu_part
    pages = []
    for first, last, sid in parts(volume, scan):
        got = parse_djvu_part(raw_path(sid), scan.base)
        _expect([p.leaf for p in got] == list(range(first, last + 1)), f"{sid}: not pages {first}-{last}")
        pages += got
    return pages


# ------------------------------------------------------------ later: layout

MONTH_NAMES = ("january", "february", "march", "april", "may", "june", "july", "august", "september",
               "october", "november", "december")
TITLE = "historyofcongress"
# A Google scan's mark at the foot of a page ("Digitized by Google", which OCR
# reads "-^lOogle", "LjOOQIC", ".Google").
WATERMARK = re.compile(r"digitiz|google|oogle|oogie|ooqic|ooglc|ljoo|byg[o0]")


def _alike(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def is_title_row(text: str) -> bool:
    """The first row of the running head: "19 HISTORY OF CONGRESS. 20", as
    OCR reads it ("HISXORT OF CONaRBSS.", "mSTORT OP CONGRESS.")."""
    l = letters(text)
    if not l:
        return bool(re.search(r"\d", text))
    return len(l) <= 30 and max(_alike(l[i:i + len(TITLE)], TITLE) for i in range(max(1, len(l) - len(TITLE) + 1))) >= 0.6


def is_subject_row(text: str) -> bool:
    """The second row of the running head: the month and year, the house and
    the page's subject ("NOVEMBER, 1803. Amendment to the Constitution.
    SENATE."), in mixed case: a heading in capitals in the text is not one."""
    words = text.split()
    # Not a heading in capitals, a line of text (beginning in lower case) or
    # a day's heading ("Thursday, January 12.") at the top of a column.
    if (not words or len(words) > 14 or capitals(text) or re.match(r"\W*[a-z]", text)
            or is_day_heading(text)):
        return False
    if re.search(r"\b1[78S][0-9OIlS]{2}\b|[\[\]]|\bH\W{0,2}\s*[oO][fFpP]\W{0,3}\s*R\b", text):
        return True
    for w in words:
        k = letters(w)
        if len(k) >= 4 and (max(_alike(k, m) for m in MONTH_NAMES) >= 0.7 or (len(words) <= 4 and (
                _alike(k, "senate") >= 0.65 or _alike(k, "proceedings") >= 0.7))):
            return True
    # The page's subject ("Amendment to the Constitution."), read badly
    # ("ATrtmdment to the Coiutitutitm.").
    return len(words) <= 8 and any(_alike(letters(w), "amendment") >= 0.6 for w in words) and any(
        _alike(letters(w), "constitution") >= 0.6 for w in words)


def split_later(page: Page, reference: bool = False, google: bool = False) -> Spread | None:
    """As `split_spread`, for the later volumes: Google's mark is left out
    (`google`: a Google scan), and the running head's rows are recognised by
    their letters."""
    if not page.width or sum(len(para.words) for para in page.paras) < 50:
        return None
    def mark(l) -> bool:
        """Google's mark, below the text at the right of the foot of the page
        (where OCR reads it as anything: ".nOO^Ie")."""
        low = google and l.words[0].y0 > 0.85 * page.height and len(l.words) <= 4
        return low and (bool(WATERMARK.search(letters(l.text))) or (
            l.words[0].y0 > 0.925 * page.height and l.words[0].x0 > 0.55 * page.width and len(l.words) <= 2))
    for para in page.paras:
        para.lines = [l for l in para.lines if not mark(l)]
    page.paras = [p for p in page.paras if p.lines]
    left, right = body_span(page)
    mid = (left + right) / 2
    lines = [l for para in page.paras for l in para.lines]
    body_rows = [r for r in rows(lines) if not is_speck(r)]
    head_rows = []
    for row in body_rows[:2]:
        text = " ".join(l.text for l in row)
        if row[0].words[0].y0 >= 0.13 * page.height:
            break
        # A day's heading at the top of a column ("Thursday, October 20.", as
        # OCR reads it, "THDBflOAT, October 20.") is never part of the head.
        def day_like(t: str) -> bool:
            m = ANY_DAY.match(t.strip())
            return bool(m and month_of(m.group("month")) and not re.search(r"\b1[78S][0-9OIlS]{2}\b", t))
        if not head_rows and is_title_row(text):
            head_rows.append(row)
        elif head_rows and is_subject_row(text) and not any(day_like(l.text) for l in row):
            head_rows.append(row)
        else:
            break
    number_row = head_rows[0] if head_rows else []
    top = max((l.words[0].y0 for row in head_rows for l in row), default=-1)
    head_rows = [r for r in rows(lines) if r[0].words[0].y0 <= top]
    head_ids = {id(l) for row in head_rows for l in row}
    head = " | ".join(" ".join(l.text for l in row) for row in head_rows)
    numbers: list[int | None] = [None, None]
    for w in sorted((w for l in number_row for w in l.words), key=lambda w: w.x0):
        m = re.fullmatch(r"\D?(\d{1,4})\D?", w.text.strip())
        if m:
            side = 0 if (w.x0 + w.x1) / 2 < mid else 1
            if numbers[side] is None or side == 1:
                numbers[side] = int(m.group(1))
    columns = split_columns(page, head_ids, 2, reference)
    if columns is None:
        return None
    return Spread(page.leaf, head, columns, numbers)


def settle_runs(spreads: list[Spread]) -> None:
    """Column numbers: the left column is odd, so each page read gives an
    offset from twice its scan page. The offset stays the same from page to
    page except where the scan skips or repeats a page, so the offsets are
    chosen for the whole scan at once (the best path through them, Viterbi's
    way): a page agrees with each number it reads, a change of offset costs
    as much as three readings, and a change of more than ten columns (a
    misread figure: 602 for 502) as much as twelve, also between the runs of
    pages kept of a scan, whose columns go on from one run to the next."""
    reads: dict[int, list[int]] = {}
    for s in spreads:
        offs = []
        if s.numbers[0] and s.numbers[0] % 2 == 1:
            offs.append(s.numbers[0] - 2 * s.leaf)
        if s.numbers[1] and s.numbers[1] % 2 == 0:
            offs.append(s.numbers[1] - 1 - 2 * s.leaf)
        reads[s.leaf] = offs
    states = sorted({o for offs in reads.values() for o in offs})
    if not states:
        for s in spreads:
            s.numbers = [None, None]
        return
    score = {o: 0.0 for o in states}
    back: list[dict[int, int]] = []
    for s in spreads:
        new, ptr = {}, {}
        for o in states:
            best, arg = score[o], o
            for p in states:
                if p == o:
                    continue
                cost = 3 if abs(p - o) <= 10 else 12
                if score[p] - cost > best:
                    best, arg = score[p] - cost, p
            new[o] = best + reads[s.leaf].count(o)
            ptr[o] = arg
        score = new
        back.append(ptr)
    o = max(states, key=lambda k: score[k])
    path = []
    for ptr in reversed(back):
        path.append(o)
        o = ptr[o]
    for s, off in zip(spreads, reversed(path)):
        s.numbers = [2 * s.leaf + off, 2 * s.leaf + off + 1]


def split_headings(col: Page) -> None:
    """A heading in capitals that OCR ran into the paragraph before or after
    it ("… to be printed. ABUSE OF THE AMERICAN FLAG.") is set apart, as
    print sets it, in a paragraph of its own (in place)."""
    out = []
    for para in col.paras:
        cur: list = []
        for line in para.lines:
            if capitals(line.text) and len(letters(line.text)) >= 8:
                if cur:
                    out.append(Para(cur, para.leaf, para.kind))
                out.append(Para([line], para.leaf, para.kind, heading=True))
                cur = []
            else:
                cur.append(line)
        if cur:
            out.append(Para(cur, para.leaf, para.kind))
    col.paras = out


@lru_cache(maxsize=None)
def later_spreads(volume: int, name: str) -> tuple[Spread, ...]:
    vol = VOLUMES[volume]
    scan = next(s for s in vol.scans if s.name == name)
    out = [s for s in (split_later(p, scan is not vol.scans[0], is_google(scan)) for p in later_pages(volume, scan)) if s]
    settle_runs(out)
    return tuple(out)


def later_columns(volume: int) -> list[list[Page]]:
    """The primary scan's columns, numbered, one list per run of pages kept
    (paragraphs are not joined across runs)."""
    vol = VOLUMES[volume]
    runs: list[list[Page]] = []
    last_leaf = None
    for s in later_spreads(volume, vol.scans[0].name):
        if last_leaf is None or s.leaf != last_leaf + 1:
            runs.append([])
        last_leaf = s.leaf
        for n, col in zip(s.numbers, s.columns):
            if not col.paras:
                continue
            col.folio = col.number = str(n) if n else None
            col.paras = split_paragraphs(col, body_margin(col))
            split_headings(col)
            mark_notes(col)
            runs[-1].append(col)
    return runs


def later_reference(volume: int, scan: Scan) -> str:
    out = []
    for s in later_spreads(volume, scan.name):
        for col in s.columns:
            for para in col.paras:
                out.extend(l.text for l in para.lines)
    return "\n".join(out)


def tesseract_id(volume: int) -> str:
    return f"ia-annals-v{volume}-{VOLUMES[volume].images}-tesseract"


def image_id(volume: int, leaf: int) -> str:
    return f"ia-page-annals-v{volume}-{VOLUMES[volume].images}-{leaf:04d}"


def tesseract_reference(volume: int) -> str | None:
    """Our Tesseract reading of a scan's page images (sources/ocr/), as
    text read column by column, or None where there is none."""
    path = OCR_DIR / f"{tesseract_id(volume)}.tsv"
    if not VOLUMES[volume].images or not path.exists():
        return None
    out = []
    spreads_ = [s for s in (split_later(p, reference=True, google=True) for p in parse_tesseract_tsv(path)) if s]
    for s in spreads_:
        for col in s.columns:
            for para in col.paras:
                out.extend(l.text for l in para.lines)
    return "\n".join(out)


# ------------------------------------------------------------ later: items

ANY_DAY = re.compile(r"(?P<weekday>[A-Za-z][A-Za-z .&^'-]{3,11}?)(?:[.,]+\s*|\s+)(?P<month>[A-Za-z]{3,10})[.,]?\s*"
                     r"(?P<day>[0-9A-Za-z]{1,3})\b")
SUBJECTS = ("amendmenttotheconstitution", "amendmentstotheconstitution", "amendmentoftheconstitution")


def month_of(word: str) -> int | None:
    k = letters(word)
    if len(k) < 3:
        return None
    best = max(range(12), key=lambda i: _alike(k, MONTH_NAMES[i][:len(k)] if len(k) < 5 else MONTH_NAMES[i]))
    ref = MONTH_NAMES[best][:len(k)] if len(k) < 5 else MONTH_NAMES[best]
    return best + 1 if _alike(k, ref) >= 0.7 else None


def day_score(m: re.Match, date: dt.date) -> float:
    """How well a day's heading as OCR read it ("TcESDAY, November 23,")
    names a date. Its month must match; then the weekday counts most (OCR
    misreads figures more than words: that is Tuesday the 22d), and the day
    of the month settles a weekday misread past recognizing."""
    if month_of(m.group("month")) != date.month:
        return 0.0
    figures = re.sub(r"[^0-9]", "", m.group("day")) == str(date.day)
    w = weekday_score(m.group("weekday"), date)
    if w >= 0.7:
        return 2 + w + figures
    if figures:
        return 1 + w
    # Neither read well ("SATDHDAr, October S3." for Saturday the 22d): a
    # weak match, taken only where the columns hold nothing better.
    return w if w >= 0.55 else 0.0


def is_day_heading(text: str) -> bool:
    """A day's heading at the start of a block, of any date."""
    from difflib import SequenceMatcher
    m = ANY_DAY.match(text.strip())
    if not m or month_of(m.group("month")) is None:
        return False
    word = letters(m.group("weekday"))
    return any(SequenceMatcher(None, word, d).ratio() >= 0.7 for d in WEEKDAYS + ("sunday",))


def tokens_of(b: Block) -> list[str]:
    return TOKEN.findall(b.text)


def cut(b: Block, i: int) -> tuple[Block, Block]:
    """A block split before its i-th token."""
    ts = tokens_of(b)
    return (Block(" ".join(ts[:i]), b.leaves, b.folios, b.kind, b.first_indented),
            Block(" ".join(ts[i:]), b.leaves, b.folios, b.kind, True))


def find_words(b: Block, phrase: str) -> int | None:
    """Where a phrase that begins a paragraph begins in a block, by token:
    at its start, or after a full stop or colon where OCR ran two
    paragraphs together; None if it does not. OCR misreads words ("Thai the
    lesolution a^e«d to yesterday"), so the phrase is found where most of
    its words (all but one in four) are read nearly alike, in order."""
    from importers.ocr import key
    want = [key(w) for w in phrase.split()]
    ts = [key(t) for t in tokens_of(b)]
    raw = tokens_of(b)
    for i in range(len(ts)):
        if i and not re.search(r"[.:;!?\"”’)]$", raw[i - 1]):
            continue
        got = ts[i:i + len(want)]
        if len(got) < len(want):
            break
        if sum(1 for a, g in zip(want, got) if a == g or _alike(a, g) >= 0.7) >= len(want) - len(want) // 4:
            return i
    return None


def subject_at(b: Block) -> int | None:
    """The number of tokens of a subject heading at the start of a block
    ("AMENDMENT TO THE CONSTITUTION. The order of the day …"), or None."""
    ts = tokens_of(b)
    for n in range(3, min(7, len(ts)) + 1):
        if capitals(" ".join(ts[:n])) and max(_alike(letters(" ".join(ts[:n])), s) for s in SUBJECTS) >= 0.8:
            return n
    return None


def looks_like_day(text: str) -> bool:
    """A short block ending in a month and a day of it ("tlLosoi.1,
    December 12.", OCR's reading of "Monday, December 12."): the next day's
    heading, read past recognizing its weekday."""
    ts = text.split()
    m = re.search(r"([A-Za-z]{3,10})[.,]?\s+(\d{1,2})[.,:]?$", text.strip())
    return (len(ts) <= 5 and m is not None and month_of(m.group(1)) is not None
            and not re.search(r"\d{4}", text))


def starts_with_day(text: str) -> bool:
    """A block that begins with a day's heading, its weekday read loosely
    ("THDRBOaY, October 37. Another member …"): OCR ran the next day's
    heading into its first paragraph."""
    m = ANY_DAY.match(text.strip())
    if not m or month_of(m.group("month")) is None or not re.match(r"\d", m.group("day")):
        return False
    word = letters(m.group("weekday"))
    return max(_alike(word, d) for d in WEEKDAYS + ("sunday",)) >= 0.5


def ends_item(b: Block) -> bool:
    """A heading of other business, the next day, or "Adjourned."."""
    t = b.text.strip()
    if letters(t) == "adjourned" or is_day_heading(t) or looks_like_day(t) or starts_with_day(t):
        return True
    # A heading, but not a signature ("TH. JEFFERSON.", "G. WASHINGTON.").
    return capitals(t) and not re.match(r"^(?:[A-Z][A-Za-z]?\.\s*)+[A-Z]+\.?$", t)


def entry_blocks(e: Entry, runs: list[list[Page]]) -> list[Block]:
    out = []
    for cols in runs:
        out += [b for b in blocks(cols, by_number=True) if b.folios and e.first <= int(b.folios[0]) <= e.last]
    return out


def entry_item(e: Entry, bs: list[Block]) -> Item:
    """The item of an entry among the blocks of its columns."""
    label = f"{e.prefix} {e.date}"
    # The day's heading: the best match for the date, wherever OCR put it.
    best, at = 0.0, None
    for k, b in enumerate(bs):
        for m in ANY_DAY.finditer(b.text.strip()):
            sc = day_score(m, e.date)
            if sc > best:
                best, at = sc, (k, m)
        # A heading whose weekday OCR misread past matching ("tlLosoi.1,
        # December 12."): its month and day of the month.
        tail = re.search(r"([A-Za-z]{3,10})[.,]?\s+(\d{1,2})[.,:]?$", b.text.strip())
        if (looks_like_day(b.text) and tail and month_of(tail.group(1)) == e.date.month
                and int(tail.group(2)) == e.date.day and best < 1):
            best, at = 1.0, (k, re.match(r".*", b.text.strip()))
    _expect(best > 0, f"{label}: the day's heading is not in columns {e.first}-{e.last}")
    k, m = at
    day = m.group(0)
    rest = bs[k].text.strip()[m.end():].strip()
    bs = ([Block(rest, bs[k].leaves, bs[k].folios)] if rest else []) + bs[k + 1:]
    # The item's start (in its own columns, where the day began earlier).
    start = None
    for k, b in enumerate(bs):
        if e.day_at and int(b.folios[0]) < e.first:
            continue
        if e.start is None:
            n = subject_at(b)
            if n is not None:
                heading, body = cut(b, n)
                start, bs = k, bs[:k] + [heading] + ([body] if body.text else []) + bs[k + 1:]
                break
        else:
            i = find_words(b, e.start)
            if i is not None:
                if i:
                    _, b = cut(b, i)
                start, bs = k, bs[:k] + [b] + bs[k + 1:]
                break
        if k and ends_item(b) and is_day_heading(b.text):
            break
    _expect(start is not None, f"{label}: the item's start is not found")
    heading = bs[start] if e.start is None else None
    body: list[Block] = []
    for b in bs[start + (1 if heading else 0):]:
        if e.until is not None:
            i = find_words(b, e.until)
            if i is not None:
                if i:
                    body.append(cut(b, i)[0])
                break
        elif ends_item(b):
            break
        body.append(b)
    else:
        _expect(e.until is None, f"{label}: the item's end ({e.until!r}) is not found")
    _expect(bool(body), f"{label}: an empty item")
    return Item(day, e.date, heading, body)


@lru_cache(maxsize=None)
def later_items(volume: int) -> tuple[tuple[str, Item], ...]:
    """The volume's items (with their work's prefix), in column order."""
    run_blocks = [blocks(cols, by_number=True) for cols in later_columns(volume)]
    out = []
    for e in sorted(entries_of(volume), key=lambda e: (e.first, e.date)):
        bs = [b for rb in run_blocks for b in rb if b.folios and (
            e.first <= int(b.folios[0]) <= e.last or int(b.folios[0]) == e.day_at)]
        out.append((e.prefix, entry_item(e, bs)))
    for prefix, it in out:
        cols = sorted({int(f) for b in ([it.heading] if it.heading else []) + it.body for f in b.folios})
        _expect(cols == list(range(cols[0], cols[-1] + 1)),
                f"{prefix} {it.date}: columns {cols} are not continuous (a page not read?)")
    return tuple(out)


def independent_of(readings: list[dict], same: tuple[str, ...]) -> list[dict]:
    """As `independent`, for any set of same-engine readings ("primary" for
    the primary scan's): all but one of them left out, once for each."""
    if len(same) < 2:
        return readings
    return [{k: v for k, v in r.items() if k not in same or k == keep} for keep in same for r in readings]


def later_prepare(volume: int) -> tuple[tuple[tuple[str, Item], ...], dict[int, list[dict]]]:
    vol = VOLUMES[volume]
    its = later_items(volume)
    refs = [Reference(s.name, later_reference(volume, s)) for s in vol.scans[1:]]
    tess = tesseract_reference(volume)
    if tess is not None:
        refs.append(Reference("tesseract", tess))
    hints: dict[str, int] = {}
    readings: dict[int, list[dict]] = {}
    for _, it in its:
        stream = ([it.heading] if it.heading else []) + [b for b in it.body if b.kind != "note"]
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


def later_build(work: Work, its: list[Item], readings: dict[int, list[dict]], known: set[str]) -> dict:
    vol = VOLUMES[work.volume]
    divisions, segments = [], []
    seen: Counter = Counter()
    for it in its:
        key = day_key(it.date)
        seen[key] += 1
        base = f"{work.prefix}.{key}" + ("" if seen[key] == 1 else "bcdefgh"[seen[key] - 2])
        label = day_label(it.date)
        div = {"date": it.date.isoformat(), "label": label, "level": 1, "ref": base}
        if it.heading is not None:
            title, spans = text_of_readings(readings[id(it.heading)], known)
            div["title"] = title
            if spans:
                div["uncertain"] = {"title": spans}
        divisions.append(div)
        body = [b for b in it.body if b.kind != "note"]
        notes = [b for b in it.body if b.kind == "note"]
        for kind, bs, ref_of, label_of in (
                (None, body, lambda n: f"{base}.{n}", lambda n: f"{work.house}, {label}, ¶ {n}"),
                ("footnote", notes, lambda n: f"{base}.fn{n}", lambda n: f"{work.house}, {label}, note {n}")):
            for n, b in enumerate(bs, 1):
                text, spans, fixed = corrections.apply(ref_of(n), *text_of_readings(readings[id(b)], known))
                seg = {"columns": b.folios, "label": label_of(n), "ref": ref_of(n),
                       "scan": {"item": vol.scans[0].item, "leaves": b.leaves}, "text": text}
                if kind:
                    seg["kind"] = kind
                if spans:
                    seg["uncertain"] = spans
                if fixed:
                    seg["corrected"] = fixed
                segments.append(seg)
    cols = sorted({int(c) for s in segments for c in s["columns"]})
    others = [s.about for s in vol.scans[1:]]
    sources = [sid for s in vol.scans for _, _, sid in parts(work.volume, s)]
    record = next((r for r in (read_json(OCR_MANIFEST) if OCR_MANIFEST.exists() else [])
                   if r["id"] == tesseract_id(work.volume)), None) if vol.images else None
    if record:
        imaged = next(s for s in vol.scans if s.name == vol.images)
        others.append(f"our Tesseract reading of the page images of {imaged.about}")
        sources += [img["source"] for img in record["images"]["sources"]]
    return {
        "date": f"{its[0].date.isoformat()}/{its[-1].date.isoformat()}",
        "divisions": divisions,
        "edition": {"name": vol.edition,
                    "notes": f"{vol.edition}: {work.what}, columns {cols[0]}–{cols[-1]}. Read from "
                             f"{vol.scans[0].about} (its OCR with page layout) and checked word by word against "
                             f"{' and '.join(others)}; words they could not settle are marked as uncertain. "
                             "See docs/editions.md."},
        "id": work.id,
        "ref_prefix": work.prefix,
        "segments": segments,
        "short": work.short,
        "source_ids": sources,
        "title": work.title,
    }


def later_run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    paths = []
    for volume in sorted(VOLUMES):
        if not entries_of(volume):
            continue
        its, readings = later_prepare(volume)
        known = Vocabulary(clean_vocabulary())
        for r in readings.values():
            known.attest(attested(independent_of(r, VOLUMES[volume].same_engine)))
        for work in (w for w in LATER_WORKS if w.volume == volume):
            mine = sorted((it for prefix, it in its if prefix == work.prefix), key=lambda it: it.date)
            if not mine:
                continue
            path = out_dir / f"{work.id}.json"
            write_json(path, later_build(work, mine, readings, known))
            paths.append(path)
    return paths


def leaf_runs(leaves: set[int]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for leaf in sorted(leaves):
        if out and leaf == out[-1][-1] + 1:
            out[-1].append(leaf)
        else:
            out.append([leaf])
    return [(r[0], r[-1]) for r in out]


def primary_leaves(pages: list[Page], volume: int) -> set[int]:
    """The primary scan's pages that hold the entries' columns, and the page
    on each side."""
    found = [s for s in (split_later(p, google=is_google(VOLUMES[volume].scans[0])) for p in pages) if s]
    settle_runs(found)
    wanted = [(e.first, e.last) for e in entries_of(volume)] + [
        (e.day_at, e.day_at) for e in entries_of(volume) if e.day_at]
    need: set[int] = set()
    for s in found:
        if any(first <= n <= last for n in s.numbers if n for first, last in wanted):
            need.update(range(s.leaf - 1, s.leaf + 2))
    return need


def reference_leaves(pages: list[Page], volume: int, margin: int = 2) -> set[int]:
    """The pages of a scan read against the primary that hold the items:
    each of the primary's paragraphs on the items' pages (and three pages
    either side) is found in the scan as the vote finds it
    (`Reference.locate`; its column numbers are too often misread to go by),
    and the item's pages are moved by the most common difference between
    the two scans' page numbers there, with two pages more on each side."""
    from importers.ocr import key
    toks, where = [], []
    for p in pages:
        for para in p.paras:
            for t in TOKEN.findall(para.text):
                toks.append(t)
                where.append(p.leaf)
    ref = Reference("scan", " ".join(toks))
    _expect(len(ref.tokens) == len(where), "tokens of the scan read differently")
    primary = {s.leaf: s for s in later_spreads(volume, VOLUMES[volume].scans[0].name)}
    need: set[int] = set()
    for _, it in later_items(volume):
        leaves = sorted({l for b in ([it.heading] if it.heading else []) + it.body for l in b.leaves})
        diffs: Counter = Counter()
        for leaf in range(leaves[0] - 3, leaves[-1] + 4):
            for col in primary[leaf].columns if leaf in primary else []:
                for para in col.paras:
                    keys = [key(t) for t in TOKEN.findall(para.text)]
                    at = ref.locate(keys) if len(keys) >= 12 else None
                    if at is not None:
                        diffs[where[at] - leaf] += 1
        _expect(bool(diffs), f"{it.date}: not found in the scan")
        d = diffs.most_common(1)[0][0]
        need.update(range(leaves[0] + d - margin, leaves[-1] + d + margin + 1))
    return need


def cmd_fetch() -> None:
    """Keep the pages of each later volume's scans that the entries need,
    each run of them as a byte range of the scan's DjVu XML (`tools.fetch`,
    decision 59). Each file is downloaded whole into a temporary file to
    find them. The primary scan's pages are those that hold the entries'
    columns; the other scans' pages, those that share the items' text."""
    import tempfile
    from tools.common import fetch_bytes
    from tools.fetch import add_source
    for volume, vol in sorted(VOLUMES.items()):
        if not entries_of(volume):
            continue
        for k, scan in enumerate(vol.scans):
            url = f"https://archive.org/download/{scan.item}/{scan.item}_djvu.xml"
            data = fetch_bytes(url, timeout=600)
            starts = [m.start() for m in re.finditer(rb"<OBJECT\b", data)]
            ends = [m.end() for m in re.finditer(rb"</OBJECT>", data)]
            _expect(len(starts) == len(ends), f"{scan.item}: unbalanced pages")
            first_name = re.search(rb'name="PAGE" value="[^"]*_(\d+)\.djvu"', data[starts[0]:ends[0]])
            _expect(first_name is not None and int(first_name.group(1)) == scan.base,
                    f"{scan.item}: its first page is not numbered {scan.base}")
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "scan.xml"
                path.write_bytes(data)
                pages = parse_djvu_xml(path)
            if k == 0:
                need = primary_leaves(pages, volume)
            else:
                later_items.cache_clear()
                later_spreads.cache_clear()
                need = reference_leaves(pages, volume)
            runs = leaf_runs({l for l in need if 1 <= l <= len(starts)})
            have = {e["id"] for e in load_manifest()}
            for a, b in runs:
                sid = part_id(volume, scan, a, b)
                if sid in have:
                    continue
                byte_range = f"{starts[a - 1]}-{ends[b - 1] - 1}"
                role = "the scan read for layout and words" if k == 0 else "read against the first scan for the vote"
                add_source(sid, url, LICENSE.format(year=vol.year),
                           f"Annals of Congress, vol. {volume} (Gales and Seaton, {vol.year}): scan pages {a}-{b} of "
                           f"Internet Archive item {scan.item} ({scan.about}), {role}. Part of its OCR with page "
                           f"layout (DjVu XML): the pages' OBJECT elements, bytes {byte_range} (decision 59). "
                           "Written by python -m importers.annals fetch.",
                           ext=".xml", byte_range=byte_range)
                print(f"added {sid}")
            stale = [sid for _, _, sid in parts(volume, scan) if sid not in {part_id(volume, scan, a, b) for a, b in runs}]
            if stale:
                print(f"no longer needed (remove by hand if unpublished): {', '.join(stale)}")


def image_leaves(volume: int) -> list[int]:
    """The pages of the scan whose images are read with Tesseract: those
    that hold the items, and the page on each side."""
    scan = next(s for s in VOLUMES[volume].scans if s.name == VOLUMES[volume].images)
    return sorted(reference_leaves(later_pages(volume, scan), volume, margin=1))


def cmd_ocr_later() -> None:
    """Read the item pages of a later volume's chosen scan with Tesseract:
    each page image (JPEG 2000, from the item's jp2.zip, one file a page) is
    kept as a raw source and the words in sources/ocr/ (decision 59)."""
    from tools.fetch import add_source
    for volume, vol in sorted(VOLUMES.items()):
        if not vol.images or not entries_of(volume):
            continue
        scan = next(s for s in vol.scans if s.name == vol.images)
        leaves = image_leaves(volume)
        have = {e["id"]: e for e in load_manifest()}
        for leaf in leaves:
            if image_id(volume, leaf) not in have:
                member = f"{scan.item}_jp2/{scan.item}_{leaf - scan.base:04d}.jp2"
                add_source(image_id(volume, leaf),
                           f"https://archive.org/download/{scan.item}/{scan.item}_jp2.zip/{member.replace('/', '%2F')}",
                           f"Public domain in the USA (published {vol.year}). Page image scanned by Google, as served "
                           "by the Internet Archive.",
                           f"Annals of Congress, vol. {volume} (Gales and Seaton, {vol.year}): the image of scan page "
                           f"{leaf} of Internet Archive item {scan.item} ({scan.about}), {member} in its jp2.zip. "
                           "Read with Tesseract for one more reading (decision 59). Written by python -m "
                           "importers.annals ocr later.", ext=".jp2")
        entries = {e["id"]: e for e in load_manifest()}
        images = [(leaf, raw_path(image_id(volume, leaf)).read_bytes()) for leaf in leaves]
        out = OCR_DIR / f"{tesseract_id(volume)}.tsv"
        run_tesseract(images, out)
        rid = tesseract_id(volume)
        records = [r for r in (read_json(OCR_MANIFEST) if OCR_MANIFEST.exists() else []) if r["id"] != rid]
        records.append({
            "command": "tesseract IMAGE stdout " + " ".join(TESSERACT_ARGS) + " (OMP_THREAD_LIMIT=1)",
            "id": rid,
            "images": {"leaves": leaves, "sources": [
                {"sha256": entries[image_id(volume, leaf)]["sha256"], "source": image_id(volume, leaf)}
                for leaf in leaves]},
            "notes": f"Annals of Congress, vol. {volume} ({vol.year}), the pages of the items imported by "
                     f"importers/annals.py in {scan.about}, read with Tesseract as one more reading for the vote "
                     "(decision 59). Written by python -m importers.annals ocr later.",
            "path": str(out.relative_to(ROOT)),
            "sha256": sha256_file(out),
            "tools": tesseract_versions(),
        })
        write_json(OCR_MANIFEST, sorted(records, key=lambda r: r["id"]))
        print(f"read {len(leaves)} pages -> {out.relative_to(ROOT)}")


def run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    return run_1789(out_dir) + later_run(out_dir)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["ocr"]:
        cmd_ocr()
    elif sys.argv[1:] == ["ocr", "later"]:
        cmd_ocr_later()
    elif sys.argv[1:] == ["fetch"]:
        cmd_fetch()
    else:
        for path in run():
            print(f"wrote {path}")
