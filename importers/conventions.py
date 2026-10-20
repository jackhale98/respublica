"""The debates of the state ratifying conventions, from Elliot's Debates,
vols. 2-4, as the Library of Congress typed them (decision 68).

Jonathan Elliot, ed., The Debates in the Several State Conventions on the
Adoption of the Federal Constitution (2nd ed., Washington, 1836; the
standard pagination, reprinted by Lippincott): vol. 2 (Massachusetts,
Connecticut, New Hampshire, New York, Pennsylvania, Maryland), vol. 3
(Virginia), vol. 4 (North Carolina, South Carolina). The text is the
Library of Congress's typed transcription of each volume
(`importers/amem.py`), not OCR. Each word of it is checked against the
Internet Archive's scan of the 1907 Lippincott printing of the same volume
(the copies Patrick Henry's speeches are read from; for vol. 3, its three
other scans too): where the scans read another word, the transcription's
word stays in the text and is marked uncertain with every reading, for a
person to check against the page image (`cross_check`). Nothing is chosen
silently, and no scan's word replaces the transcription's.

One work per convention, as Elliot prints it, from its first paragraph
after the section's heading to the last before the next section. Each work
is divided by day, at the paragraph that begins the day as Elliot prints it
("Thursday, January 10.—The committee ...", "Tuesday, June 3, 1788.");
`CONVENTIONS` lists every day and the words that begin it, and the
importer stops if the days found are not those. A misprinted date is
recorded with the day (`Day.printed`), and the ref follows the date the
weekday and the order of the days give. Every printed paragraph is a
passage, the datelines and headings within a day ("AYES.") too, numbered
from 1 within the day; the speaker's name stays at the head of a speech, as
printed. Footnotes follow the paragraph they belong to.

The two pieces Elliot prints undated (New Hampshire's fragment, the
Maryland minority's address) are single pieces.

Refs (docs/references.md): `Virginia1788.Jun5.{n}`, `Massachusetts1788.Jan9.{n}`,
notes `{day}.fn{k}`; a single piece `NewHampshire1788.{n}`.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from importers import amem
from importers.ocr import Reference, Vocabulary, align, blocks, confused, is_word, key, plain
from importers.ratification import clean_vocabulary, leaf_range, load_book
from importers.ratification_series import BOOKS
from tools.common import TEXTS_DIR, write_json


class ImportError_(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ImportError_(msg)


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")


@dataclass(frozen=True)
class Day:
    date: dt.date
    opens: str  # the words that begin the day, as the transcription prints them (a pattern)
    lead: int = 0  # paragraphs before those words that belong to the day (a heading over it)
    printed: str | None = None  # the date as printed, where it is not the day's (a misprint)


@dataclass(frozen=True)
class Convention:
    work_id: str
    prefix: str
    state: str
    title: str
    short: str
    vol: int
    divs: tuple[int, ...]  # the transcription's top-level divisions of the body (amem.Volume.heads)
    heading: str  # the start of the section's heading, as printed
    pages: tuple[int, int]
    days: tuple[Day, ...] = ()  # none: a single piece
    date: str = ""  # a single piece's date (ISO, or a year)
    summary: str = ""


def _d(y: int, m: int, day: int, opens: str, lead: int = 0, printed: str | None = None) -> Day:
    return Day(dt.date(y, m, day), opens, lead, printed)


def _wd(weekday: str, month: str | None = None) -> str:
    """The opening of a day printed with its weekday ("Thursday, January 10.")."""
    return weekday + r"s?\s*,?\s*" + (month + r"\s+" if month else "")


CONVENTIONS = (
    Convention(
        "massachusetts-convention-1788", "Massachusetts1788", "Massachusetts",
        "Debates in the Massachusetts Ratifying Convention, 1788", "Massachusetts convention", 2, (0,),
        "DEBATES IN THE CONVENTION OF THE COMMONWEALTH OF MASSACHUSETTS", (1, 183),
        (_d(1788, 1, 9, r"In Convention, Boston, January 9, 1788\.$"),
         _d(1788, 1, 10, _wd("Thursday", "January") + r"10\b"),
         _d(1788, 1, 11, _wd("Friday") + r"11th\b"),
         _d(1788, 1, 12, _wd("Saturday") + r"12th\b"),
         _d(1788, 1, 14, _wd("Monday", "January") + r"14\b"),
         _d(1788, 1, 15, _wd("Tuesday", "January") + r"15\b"),
         _d(1788, 1, 16, _wd("Wednesday", "January") + r"16\b"),
         _d(1788, 1, 17, _wd("Thursday", "January") + r"17\b"),
         _d(1788, 1, 18, _wd("Friday", "January") + r"18\b"),
         _d(1788, 1, 19, _wd("Saturday", "January") + r"19\b"),
         _d(1788, 1, 21, _wd("Monday", "January") + r"21\b"),
         _d(1788, 1, 22, _wd("Tuesday", "January") + r"22\b"),
         _d(1788, 1, 23, _wd("Wednesday", "January") + r"23\b"),
         _d(1788, 1, 24, _wd("Thursday", "January") + r"24\b"),
         _d(1788, 1, 25, _wd("Friday", "January") + r"25\b"),
         _d(1788, 1, 26, _wd("Saturday", "January") + r"26\b"),
         _d(1788, 1, 28, _wd("Monday", "January") + r"28\b"),
         _d(1788, 1, 30, _wd("Wednesday", "January") + r"30\b"),
         _d(1788, 2, 1, _wd("Friday", "February") + r"1\b"),
         _d(1788, 2, 2, _wd("Saturday", "February") + r"2\b"),
         _d(1788, 2, 4, _wd("Monday", "February") + r"4\b"),
         _d(1788, 2, 5, _wd("Tuesday", "February") + r"5\b"),
         _d(1788, 2, 6, _wd("Wednesday", "February") + r"6\b"),
         _d(1788, 2, 7, _wd("Thursday", "February") + r"7\b")),
        summary="The Massachusetts convention at Boston, January 9 to February 7, 1788, as Elliot prints its "
                "debates: the minutes, the speeches as reported, the amendments it recommended and the yeas "
                "and nays on ratification."),
    Convention(
        "connecticut-convention-1788", "Connecticut1788", "Connecticut",
        "Debates in the Connecticut Ratifying Convention, 1788", "Connecticut convention", 2, (1,),
        "FRAGMENT OF THE DEBATES IN THE CONVENTION OF THE STATE OF CONNECTICUT", (185, 202),
        # The section's subtitle ("Collected from contemporary publications
        # ...") is printed above the first day's dateline.
        (_d(1788, 1, 4, r"In Convention, Hartford, January 4, 1788\.$", lead=1),
         _d(1788, 1, 7, r"January 7, 1788\."),
         _d(1788, 1, 9, r"January 9, 1788\s*\.")),
        summary="The fragment of the Connecticut convention's debates at Hartford, January 4–9, 1788, that "
                "Elliot collected from the newspapers: the speeches of Oliver Ellsworth, Richard Law, Governor "
                "Huntington and others."),
    Convention(
        "new-hampshire-convention-1788", "NewHampshire1788", "New Hampshire",
        "A Speech in the New Hampshire Ratifying Convention, 1788", "New Hampshire convention", 2, (2,),
        "NEW HAMPSHIRE CONVENTION", (203, 204), date="1788",
        summary="The only speech known to Elliot from the New Hampshire convention: Joshua Atherton on the "
                "clause on the importation of slaves."),
    Convention(
        "new-york-convention-1788", "NewYork1788", "New York",
        "Debates in the New York Ratifying Convention, 1788", "New York convention", 2, (3,),
        "THE DEBATES IN THE CONVENTION OF THE STATE OF NEW YORK", (205, 414),
        (_d(1788, 6, 17, r"In Convention, Poughkeepsie, June 17, 1788\.$"),
         _d(1788, 6, 20, _wd("Friday", "June") + r"20\b"),
         _d(1788, 6, 21, _wd("Saturday", "June") + r"21\b"),
         _d(1788, 6, 23, _wd("Monday", "June") + r"23\b"),
         _d(1788, 6, 24, _wd("Tuesday", "June") + r"24th\b"),
         _d(1788, 6, 25, _wd("Wednesday", "June") + r"25\b"),
         _d(1788, 6, 26, _wd("Thursday", "June") + r"26\b"),
         _d(1788, 6, 27, _wd("Friday", "June") + r"27\b"),
         _d(1788, 6, 28, _wd("Saturday", "June") + r"28\b"),
         _d(1788, 6, 30, _wd("Monday", "June") + r"30\b"),
         _d(1788, 7, 1, _wd("Tuesday", "July") + r"1\b"),
         _d(1788, 7, 2, _wd("Wednesday", "July") + r"2\b"),
         _d(1788, 7, 4, _wd("Friday", "July") + r"4\b"),
         _d(1788, 7, 5, _wd("Saturday", "July") + r"5\b"),
         _d(1788, 7, 7, _wd("Monday", "July") + r"7\b"),
         _d(1788, 7, 8, _wd("Tuesday", "July") + r"8, 1738\b", printed="Tuesday, July 8, 1738"),
         _d(1788, 7, 9, _wd("Wednesday", "July") + r"9\b"),
         _d(1788, 7, 10, _wd("Thursday", "July") + r"10\b"),
         _d(1788, 7, 11, _wd("Friday", "July") + r"11\b"),
         _d(1788, 7, 16, _wd("Wednesday", "July") + r"16\b"),
         _d(1788, 7, 19, _wd("Saturday", "July") + r"19\b"),
         _d(1788, 7, 23, _wd("Wednesday", "July") + r"23, 1783\b", printed="Wednesday, July 23, 1783"),
         _d(1788, 7, 25, _wd("Friday", "July") + r"25\b"),
         _d(1788, 7, 26, _wd("Saturday", "July") + r"26\b")),
        summary="The New York convention at Poughkeepsie, June 17 to July 26, 1788, as Elliot prints its "
                "debates, with the ratification, the amendments recommended and the circular letter to the "
                "states."),
    Convention(
        "pennsylvania-convention-1787", "Pennsylvania1787", "Pennsylvania",
        "Debates in the Pennsylvania Ratifying Convention, 1787", "Pennsylvania convention", 2, (4,),
        "THE DEBATES IN THE CONVENTION OF THE STATE OF PENNSYLVANIA", (415, 546),
        (_d(1787, 11, 20, r"Philadelphia, Tuesday, November 20, 1787"),
         _d(1787, 11, 21, _wd("Wednesday", "November") + r"21\b"),
         _d(1787, 11, 22, _wd("Thursday", "November") + r"22\b"),
         # Friday was November 23 (between the 22d and Saturday the 24th).
         _d(1787, 11, 23, _wd("Friday", "November") + r"25\b", printed="Friday, November 25, 1787"),
         _d(1787, 11, 24, _wd("Saturday", "November") + r"24\b"),
         _d(1787, 11, 26, _wd("Monday", "November") + r"26\b"),
         # Wednesday after Monday the 26th: November 28.
         _d(1787, 11, 28, _wd("Wednesday", "October") + r"28\b", printed="Wednesday, October 28, 1787"),
         _d(1787, 11, 30, _wd("Friday", "November") + r"30\b"),
         _d(1787, 12, 1, _wd("Saturday", "December") + r"1\b"),
         _d(1787, 12, 3, _wd("Monday", "December") + r"3\b"),
         _d(1787, 12, 4, _wd("Tuesday", "December") + r"4\b"),
         _d(1787, 12, 7, _wd("Friday", "December") + r"7\b"),
         _d(1787, 12, 11, _wd("Tuesday", "December") + r"11\b"),
         # The meeting at Harrisburg of the Constitution's opponents, which
         # Elliot prints after the convention.
         _d(1788, 9, 3, r"PROCEEDINGS OF THE MEETING AT HARRISBURG")),
        summary="The Pennsylvania convention at Philadelphia, November 20 to December 11, 1787, as Elliot "
                "prints it: the minutes and the speeches of James Wilson and Thomas M'Kean, then the "
                "proceedings of the meeting at Harrisburg, September 3, 1788."),
    Convention(
        "maryland-convention-1788", "Maryland1788", "Maryland",
        "A Fragment of Facts: the Maryland Ratifying Convention, 1788", "Maryland convention", 2, (5,),
        "A FRAGMENT OF FACTS, DISCLOSING THE CONDUCT OF THE MARYLAND CONVENTION", (547, 556), date="1788-04-21",
        summary="The address of the minority of the Maryland convention to the people of Maryland, which "
                "Elliot prints for want of its debates: the convention's proceedings and the amendments its "
                "committee considered."),
    Convention(
        "virginia-convention-1788", "Virginia1788", "Virginia",
        "Debates in the Virginia Ratifying Convention, 1788", "Virginia convention", 3, (0,),
        "THE DEBATES IN THE CONVENTION OF THE COMMONWEALTH OF VIRGINIA", (1, 663),
        (_d(1788, 6, 2, r"In Convention, Richmond, Monday, June 2, 1788\.$"),
         *(_d(1788, 6, n, WEEKDAYS[dt.date(1788, 6, n).weekday()] + rf", June {n}, 1788\.$")
           for n in (3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 16, 17, 18)),
         # Headed "Wednesday, June 18, 1788." a second time: Thursday the
         # 19th (erratum 60).
         _d(1788, 6, 19, r"Wednesday, June 18, 1788\.$", printed="Wednesday, June 18, 1788"),
         *(_d(1788, 6, n, WEEKDAYS[dt.date(1788, 6, n).weekday()] + rf", June {n}, 1788\.$")
           for n in (20, 21, 23, 24, 25, 26, 27))),
        summary="The Virginia convention at Richmond, June 2–27, 1788, as Elliot prints its debates, with the "
                "ratification, the amendments recommended and the votes. Patrick Henry's speeches are also a "
                "work of their own."),
    Convention(
        "north-carolina-convention-1788", "NorthCarolina1788", "North Carolina",
        "Debates in the North Carolina Ratifying Convention, 1788", "North Carolina convention", 4, (0,),
        "DEBATES IN THE CONVENTION OF THE STATE OF NORTH CAROLINA", (1, 252),
        (_d(1788, 7, 21, r"At a Convention, begun and held at Hillsborough, the 21st day of July"),
         *(_d(1788, m, n, WEEKDAYS[dt.date(1788, m, n).weekday()] + rf", {MONTHS[m - 1]} {n}, 1788\.$")
           for m, n in ((7, 22), (7, 23), (7, 24), (7, 25), (7, 26), (7, 28), (7, 29), (7, 30), (7, 31),
                        (8, 1), (8, 2)))),
        summary="The first North Carolina convention at Hillsborough, July 21 to August 2, 1788, as Elliot "
                "prints its debates, with the declaration of rights and amendments it proposed, neither "
                "ratifying nor rejecting the Constitution."),
    Convention(
        "south-carolina-convention-1788", "SouthCarolina1788", "South Carolina",
        "Debates in the South Carolina Legislature and Ratifying Convention, 1788", "South Carolina convention",
        4, (1, 2), "DEBATES IN THE LEGISLATURE AND IN CONVENTION OF THE STATE OF SOUTH CAROLINA", (253, 341),
        (_d(1788, 1, 16, r"House of Representatives\. In the Legislature, Wednesday, January 16, 1788\.$"),
         *(_d(1788, 1, n, WEEKDAYS[dt.date(1788, 1, n).weekday()] + rf", January {n}, 1788\.$")
           for n in (17, 18, 19)),
         # "DEBATES IN CONVENTION." heads the convention's part.
         _d(1788, 5, 12, r"Monday, May 12, 1788\.$", lead=1),
         *(_d(1788, 5, n, WEEKDAYS[dt.date(1788, 5, n).weekday()] + rf", May {n}, 1788\.$")
           for n in (13, 14, 20, 21, 23))),
        summary="The South Carolina House of Representatives' debate on the Constitution, January 16–19, "
                "1788, and the convention at Charleston, May 12–23, 1788, as Elliot prints them."),
)

# A paragraph that looks like a day's opening: a weekday and a date, or a
# month and day with a year. Each one must be a day in CONVENTIONS, or a
# dateline that is not one (`NOT_DAYS`).
DATELINE = re.compile(
    r"^\W{0,3}(?:In Convention,?\s*)?(?:[A-Z][a-z]+\s*,\s*)?(?:(?:%s)s?\s*,?\s*(?:(?:%s)\s*\d|\d)|(?:%s)\s+\d{1,2}"
    r"(?:st|d|th)?\s*,?\s*1[67]\d\d)" % ("|".join(WEEKDAYS), "|".join(MONTHS), "|".join(MONTHS)))
NOT_DAYS = {
    # The dateline of New York's circular letter to the states.
    "NewYork1788": [r"Poughkeepsie, July 28, 1788\.$"],
    # The dateline of the Harrisburg meeting, which its heading begins.
    "Pennsylvania1787": [r"Harrisburg, Sept\. 3, 1788\.$"],
}


# ------------------------------------------------------------ structure


@dataclass
class Unit:
    key: str  # "Jan9", or "" for a single piece
    label: str
    date: dt.date | None
    paras: list[amem.Para]
    printed: str | None = None


def section(c: Convention) -> list[amem.Para]:
    """A convention's paragraphs, without the section's heading (and a later
    part's: its heading stays, as a paragraph of the day it heads)."""
    vol = amem.volume(c.vol)
    for d in c.divs[:1]:
        _expect(vol.heads[d].startswith(c.heading), f"{c.prefix}: division {d} is headed {vol.heads[d]!r}")
    paras = [p for p in vol.paras if p.div in c.divs]
    _expect(paras[0].kind == "head" and paras[0].text.startswith(c.heading),
            f"{c.prefix}: the section does not begin with its heading: {paras[0].text[:60]!r}")
    first = int(paras[0].pages[0])
    last = max(int(pg) for p in paras for pg in p.pages)
    _expect((first, last) == c.pages, f"{c.prefix}: pp. {first}–{last}, expected {c.pages[0]}–{c.pages[1]}")
    return paras[1:]


def split_days(c: Convention, paras: list[amem.Para]) -> list[Unit]:
    if not c.days:
        return [Unit("", c.short, None, paras)]
    starts: list[int] = []
    for i, p in enumerate(paras):
        if p.kind == "note":
            continue
        k = len(starts)
        if k < len(c.days) and re.match(c.days[k].opens, p.text):
            starts.append(i - c.days[k].lead)
            continue
        if DATELINE.match(p.text) and not any(re.match(x, p.text) for x in NOT_DAYS.get(c.prefix, [])):
            raise ImportError_(f"{c.prefix}: a dateline that is not a day of the list (after day {k}): "
                               f"{p.text[:80]!r}")
    _expect(len(starts) == len(c.days),
            f"{c.prefix}: found {len(starts)} of {len(c.days)} days; the next not found: "
            f"{c.days[len(starts)].opens if len(starts) < len(c.days) else ''!r}")
    _expect(starts[0] == 0, f"{c.prefix}: paragraphs before the first day: {paras[0].text[:60]!r}")
    out = []
    seen: Counter = Counter()
    for k, (d, s) in enumerate(zip(c.days, starts)):
        e = starts[k + 1] if k + 1 < len(starts) else len(paras)
        check_weekday(c, d, paras[s + d.lead].text)
        base = f"{d.date.strftime('%b')}{d.date.day}"
        seen[base] += 1
        _expect(seen[base] == 1, f"{c.prefix}: two days dated {d.date}")
        out.append(Unit(base, f"{MONTHS[d.date.month - 1]} {d.date.day}, {d.date.year}", d.date, paras[s:e],
                        d.printed))
    return out


def check_weekday(c: Convention, d: Day, text: str) -> None:
    """The weekday printed with a day is the date's (or the misprint is
    recorded); a misprinted date reads as recorded."""
    if d.printed:
        _expect(text.startswith(d.printed), f"{c.prefix}: {d.date} is printed {text[:40]!r}, not {d.printed!r}")
        return
    m = re.search("|".join(WEEKDAYS), text[:80])
    if m:
        _expect(m.group() == WEEKDAYS[d.date.weekday()],
                f"{c.prefix}: {d.date} is a {WEEKDAYS[d.date.weekday()]}, printed {text[:40]!r}")


# ------------------------------------------------------------ the scans


@lru_cache(maxsize=None)
def scans(vol: int, first: int, last: int) -> tuple[list[Reference], object]:
    """The scans a volume's pages are checked against, as word streams: the
    Toronto copy's (its DjVu layout, the pages' running heads and folios
    left out), and for vol. 3 the three other scans of `elliot-3`."""
    book = load_book(f"elliot-{vol}")
    lo, hi = leaf_range(book, first, last)
    text = "\n\n".join(b.text for b in blocks(book.pages, max(1, lo - 1), hi + 1) if b.kind == "text")
    refs = [Reference("toronto", text)]
    if vol == 3:
        refs += [r for r in book.refs]
    return refs, book


# A word of the transcription, or a dash: the scans read "country—with" as
# three words.
WORD = re.compile(r"[^\s—]+|—+")


def words_of(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group()) for m in WORD.finditer(text)]


def chunks(paras: list[amem.Para], at_least: int = 200) -> list[list[amem.Para]]:
    """Runs of paragraphs of at least `at_least` words, lined up with the
    scans as one (a vote list's lines are too short to place alone)."""
    out: list[list[amem.Para]] = [[]]
    n = 0
    for p in paras:
        out[-1].append(p)
        n += len(p.text.split())
        if n >= at_least:
            out.append([])
            n = 0
    return [c for c in out if c]


NOISE_LOG: list | None = None


def lkey(tok: str) -> str:
    return key(amem.plain(tok))


@dataclass
class Checked:
    spans: dict[int, list[dict]] = field(default_factory=dict)  # id(para) -> uncertain spans
    words: int = 0
    unaligned: int = 0  # words no scan reading was lined up with
    disagreements: int = 0
    noise: int = 0  # scan readings that differ but are not words (OCR noise), left unmarked


def cross_check(units: list[Unit], refs: list[Reference], known: set[str]) -> Checked:
    """Mark where the scans read another word than the transcription.

    The scans' readings of each word are lined up with it (`ocr.align`);
    where they read it as one word with the next, the two are taken
    together. The scans' reading is the one most of them give. It differs
    from the transcription's when its letters do (marks and capitals aside),
    and it is a reading of a word, not OCR noise: a known word, cleanly
    printed (`ocr.plain`), and not one of the shared OCR confusions of the
    transcription's word ("rn" for "m": `ocr.confused`); or a number. Such a
    word is marked uncertain, with the transcription's reading as `primary`
    and each scan's. Words no scan could be lined up with are counted."""
    out = Checked()
    hints: dict[str, int] = {}
    names = [r.name for r in refs]
    for u in units:
        body = [p for p in u.paras if p.kind != "note"]
        for chunk in chunks(body) + [[p] for p in u.paras if p.kind == "note"]:
            toks = [(p, w) for p in chunk for w in words_of(p.text)]
            plain_toks = [amem.plain(w[2]) for _, w in toks]
            readings = align(plain_toks, refs, hints if chunk[0].kind != "note" else dict(hints))
            out.words += len(toks)
            i = 0
            while i < len(toks):
                end = i + 1
                while end < len(toks) and "" in readings[end].values() and toks[end][0] is toks[i][0]:
                    end += 1
                group = readings[i:end]
                joint = {s: " ".join(v for v in (r[s] for r in group) if v) for s in names
                         if all(s in r for r in group) and group[0].get(s)}
                para = toks[i][0]
                start, stop = toks[i][1][0], toks[end - 1][1][1]
                theirs = para.text[start:stop]
                size, i = end - i, end
                if not joint:
                    out.unaligned += size
                    continue
                votes = Counter(key(v) for v in joint.values())
                top, n = votes.most_common(1)[0]
                mine = lkey(theirs)
                if top == mine or n <= votes[mine] or (len(joint) > 1 and n < 2):
                    continue  # the scans agree with it, or disagree among themselves: nothing to go on
                reading = next(v for v in joint.values() if key(v) == top)
                pieces = [key(t) for t in reading.split()]
                number = top.isdigit() and mine.isdigit()
                # (Not figures the scan read as letters: "SO" for 30.)
                word = (len(top) > 1 and all(is_word(k) and k in known for k in pieces)
                        and all(plain(t) for t in reading.split()) and not any(ch.isdigit() for ch in mine)
                        and not confused(mine, top) and not confused(top, mine))
                # At either end of a run lined up as one, a scan's word
                # beside the transcription's may be the next or last
                # paragraph's: only a reading like the transcription's counts.
                edge = min(i - size, len(toks) - i) < 2
                if edge and SequenceMatcher(None, mine, top, autojunk=False).ratio() <= 0.5:
                    word = number = False
                if not (number or word):
                    out.noise += 1
                    if NOISE_LOG is not None:
                        NOISE_LOG.append((theirs, joint))
                    continue
                out.disagreements += 1
                out.spans.setdefault(id(para), []).append(
                    {"end": stop, "readings": {"primary": theirs, **dict(sorted(joint.items()))}, "start": start})
    return out


# ------------------------------------------------------------ pages


def leaves(book, pages: list[str]) -> list[int]:
    out = []
    for p in pages:
        leaf = leaf_range(book, int(p), int(p))[0]
        if leaf not in out:
            out.append(leaf)
    return out


# ------------------------------------------------------------ build


def build(c: Convention, units: list[Unit], checked: Checked, book) -> dict:
    vol = amem.volume(c.vol)
    divisions, segments = [], []
    for u in units:
        base = f"{c.prefix}.{u.key}" if u.key else c.prefix
        div = {"label": u.label, "level": 1, "ref": base}
        if u.date:
            div["date"] = u.date.isoformat()
        if u.printed:
            div["notes"] = [{"text": f"Printed “{u.printed}”: a misprint for {u.label} (docs/errata.md)."}]
        divisions.append(div)
        n = fn = 0
        for p in u.paras:
            if p.kind == "note":
                fn += 1
                ref, label = f"{base}.fn{fn}", f"{c.short}, {u.label}, note {fn}"
            else:
                n += 1
                ref, label = f"{base}.{n}", f"{c.short}, {u.label}, ¶ {n}"
            seg = {"label": label, "pages": p.pages, "ref": ref,
                   "scan": {"item": BOOKS[f'elliot-{c.vol}']['item'], "leaves": leaves(book, p.pages)},
                   "text": p.text}
            if p.kind == "note":
                seg["kind"] = "footnote"
            spans = checked.spans.get(id(p))
            if spans:
                seg["uncertain"] = spans
            segments.append(seg)
    dates = [u.date for u in units if u.date]
    date = f"{dates[0].isoformat()}/{dates[-1].isoformat()}" if dates else c.date
    pages = [int(pg) for s in segments for pg in s["pages"]]
    edition = (f"Jonathan Elliot, ed., The Debates in the Several State Conventions on the Adoption of the Federal "
               f"Constitution, vol. {c.vol} (2nd ed., Washington, 1836)")
    return {
        "date": date,
        "divisions": divisions,
        "edition": {
            "name": edition,
            "notes": f"{edition}, pp. {min(pages)}–{max(pages)}, headed “{c.heading.title()} …”. The text is the "
                     f"Library of Congress's typed transcription (A Century of Lawmaking for a New Nation, 1997; "
                     f"{amem.VOLUMES[c.vol]}), not OCR, divided by day as Elliot prints the days. Every word was "
                     f"checked against the Internet Archive's scan of the 1907 Lippincott printing of the same "
                     f"pages ({BOOKS[f'elliot-{c.vol}']['item']}"
                     + (", and three other scans of the volume" if c.vol == 3 else "")
                     + "); where the scans read another word, the transcription's word is kept and marked as "
                       "uncertain, with every reading, for a person to check against the page image. See "
                       "docs/editions.md.",
        },
        "id": c.work_id,
        "ref_prefix": c.prefix,
        "segments": segments,
        "short": c.short,
        "source_ids": [amem.source_id(c.vol), BOOKS[f"elliot-{c.vol}"]["primary"],
                       *(BOOKS[f"elliot-{c.vol}"]["references"].values() if c.vol == 3 else [])],
        "title": c.title,
    }


@lru_cache(maxsize=None)
def vocabulary(vol: int) -> Vocabulary:
    """Known words: the clean texts', and any word the transcription and a
    scan read alike at the same place in this volume's conventions."""
    known = Vocabulary(clean_vocabulary())
    for c in CONVENTIONS:
        if c.vol != vol:
            continue
        refs, _ = scans(vol, *c.pages)
        hints: dict[str, int] = {}
        for chunk in chunks([p for p in section(c) if p.kind != "note"]):
            toks = [amem.plain(w[2]) for p in chunk for w in words_of(p.text)]
            readings = align(toks, refs, hints)
            got = set()
            for r in readings:
                if len(r) > 1 and plain(r["primary"]):
                    k = key(r["primary"])
                    if is_word(k) and any(key(v) == k for s, v in r.items() if s != "primary"):
                        got.add(k)
            known.attest(got)
    return known


def check_pages(c: Convention, paras: list[amem.Para], book) -> tuple[int, int]:
    """That the scan's pages are the transcription's: the first words of
    each paragraph that begins a page are on that page of the scan (its
    printed page, found by its folio). Returns (pages checked, found)."""
    seen, found = 0, 0
    by_leaf = {p.leaf: p for p in book.pages}
    for p in paras:
        if p.kind == "note" or len(p.text.split()) < 6:
            continue
        page = int(p.pages[0])
        leaf = leaf_range(book, page, page)[0]
        words = [key(w) for w in amem.plain(p.text).split()[:6] if key(w)]
        scan = by_leaf.get(leaf)
        if scan is None or len(words) < 4:
            continue
        page_words = {key(w.text) for para in scan.paras for line in para.lines for w in line.words}
        seen += 1
        if sum(w in page_words for w in words) >= len(words) - 1:
            found += 1
    return seen, found


def run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    paths = []
    for c in CONVENTIONS:
        paras = section(c)
        units = split_days(c, paras)
        refs, book = scans(c.vol, *c.pages)
        seen, found = check_pages(c, paras, book)
        _expect(found >= 0.95 * seen, f"{c.prefix}: only {found} of {seen} paragraphs are on the scan's page of "
                                     "the same number: is it the same pagination?")
        checked = cross_check(units, refs, vocabulary(c.vol))
        path = out_dir / f"{c.work_id}.json"
        write_json(path, build(c, units, checked, book))
        paths.append(path)
    return paths


# ------------------------------------------------------------ fetching

IA_LICENSE = ("Public domain in the USA (published 1907; the text was first published 1836). OCR and layout "
              "generated by the Internet Archive from its scan.")


def cmd_fetch() -> None:
    """Record the transcriptions (importers/amem.py) and the scans of
    vols. 2 and 4 as raw sources."""
    from tools.common import load_manifest
    from tools.fetch import add_source
    amem.cmd_fetch()
    have = {e["id"] for e in load_manifest()}
    for vol in (2, 4):
        book = BOOKS[f"elliot-{vol}"]
        if book["primary"] in have:
            continue
        item = book["item"]
        add_source(book["primary"], f"https://archive.org/download/{item}/{item}_djvu.xml", IA_LICENSE,
                   f"{book['edition']}. Internet Archive item {item} (University of Toronto copy): DjVu XML, the "
                   "scan the Library of Congress's transcription is checked against (decision 68).", ext=".xml")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["fetch"]:
        cmd_fetch()
    else:
        for path in run():
            print(f"wrote {path}")
