"""Read the Constitution Annotated (2022 print edition, govinfo GPO-CONAN-2022).

    python -m importers.conan              # summary: essays, cases, overrulings
    python -m importers.conan --cases 20   # the most-cited Supreme Court cases

What it gives the case import (phase 7), all from the official text:

- `essay_pages()`: for every printed page, the essays on it (their ids,
  such as "ArtI.S8.C3.2.1") and so the clauses of the Constitution they
  discuss (`clause_ref`: "Constitution.1.8.3").
- `table_of_cases()`: each case the Constitution Annotated cites, its
  citation as printed, and the pages that cite it.
- `overruled()`: the "Table of Supreme Court Decisions Overruled by
  Subsequent Decisions", row by row, as printed.

It reads the PDFs with tools/pdf.py and fails loudly on anything it does
not recognise. It writes nothing; it is not yet a registered importer.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

from tools.common import raw_path
from tools.corpus import load_corpus
from tools.pdf import Line, pdf_lines

ESSAY_PARTS = range(7, 42)  # granules: the Preamble, Articles I-VII, Amendments 1-27
APPENDIX = 42
ESSAY_ID = re.compile(r"^(Pre|Art(?P<art>[IVX]+)|Amdt(?P<amdt>\d+))(?:\.S(?P<sec>\d+))?(?:\.C(?P<cl>\d+))?(?:\.\d+)+$")
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


class ConanError(ValueError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ConanError(msg)


@lru_cache(maxsize=None)
def _pages(granule: int, column_gap: float | None = None) -> list[list[Line]]:
    return pdf_lines(raw_path(f"conan-2022-{granule}"), column_gap)


def printed_number(page: list[Line]) -> int | None:
    """The page number printed at the foot of the page."""
    if page and re.fullmatch(r"\d{1,4}", page[-1].text) and page[-1].y > 700:
        return int(page[-1].text)
    return None


# ------------------------------------------------------------ essays


def essay_pages() -> dict[int, list[str]]:
    """Printed page -> ids of the essays on it, in order: the essay running
    on from the page before (its id is the running head) and any essay
    whose heading is on the page."""
    out: dict[int, list[str]] = {}
    for g in ESSAY_PARTS:
        current = None
        for page in _pages(g):
            n = printed_number(page)
            if n is None:
                continue
            ids: list[str] = []
            for line in page:
                if ".." in line.text:  # a table of contents line
                    continue
                first = line.text.split(" ", 1)[0]
                if ESSAY_ID.match(first):
                    if line.y < 100 and line.text == first:
                        current = first  # running head: the essay at the top of the page
                        ids.append(first)
                    elif line.size >= 9.5 and first != line.text:
                        current = first  # a heading: an essay starts here
                        ids.append(first)
            if not ids and current:
                ids = [current]
            if ids:
                out[n] = list(dict.fromkeys(ids))
    _expect(len(out) > 2000, f"only {len(out)} essay pages found")
    return out


def essay_titles() -> dict[str, str]:
    """Essay id -> title, from each part's table of contents (a title may
    wrap onto a second line before its dotted leader and page number)."""
    out: dict[str, str] = {}
    for g in ESSAY_PARTS:
        pending = None
        for page in _pages(g):
            for line in page:
                first = line.text.split(" ", 1)[0]
                if ESSAY_ID.match(first) and " " in line.text:
                    pending = line.text
                elif pending is not None:
                    pending += " " + line.text
                else:
                    continue
                if re.search(r"\.{3,}\s*\d+$", pending):
                    eid, title = pending.split(" ", 1)
                    out.setdefault(eid, re.sub(r"\s*\.{3,}\s*\d+$", "", title).strip())
                    pending = None
                elif pending.count(" ") > 40:  # not a contents line after all
                    pending = None
    _expect(len(out) > 1000, f"only {len(out)} essay titles found")
    return out


def clause_ref(essay_id: str, refs: set[str]) -> str | None:
    """The ref of the clause (or section, or article) an essay discusses."""
    m = ESSAY_ID.match(essay_id)
    if not m:
        return None
    if essay_id.startswith("Pre"):
        return "Constitution.Preamble"
    if m.group("amdt"):
        base = f"Amendment.{m.group('amdt')}"
        sec = m.group("sec")
        if sec:
            return f"{base}.{sec}"
        return f"{base}.1" if f"{base}.1" in refs and f"{base}.2" not in refs else base
    base = f"Constitution.{ROMAN[m.group('art')]}"
    sec, cl = m.group("sec"), m.group("cl")
    if sec and cl:
        return f"{base}.{sec}.{cl}"
    if cl:  # Article VI's clauses have no sections
        return f"{base}.{cl}"
    if sec:
        return f"{base}.{sec}.1" if f"{base}.{sec}.1" in refs and f"{base}.{sec}.2" not in refs else f"{base}.{sec}"
    # An essay on a whole article: Article V and VII are one clause each.
    return f"{base}.1" if f"{base}.1" in refs and f"{base}.2" not in refs else base


# ------------------------------------------------------------ table of cases


@dataclass
class CaseEntry:
    name: str
    citation: str
    pages: list[int]

    @property
    def supreme_court(self) -> bool:
        return bool(SCOTUS_CITE.match(f"{self.name}, {self.citation}"))


ENTRY = re.compile(r"^(?P<text>.*?)\s*\.{3,}\s*(?P<pages>[\d,–\- ]+)$")
# A Supreme Court citation: "347 U.S. 483 (1954)", "62 U.S. (21 How.) 506 (1859)",
# or a slip opinion "No. 19-1391 (U.S. June 24, 2022)". Other courts' citations
# are kept as printed.
SCOTUS_CITE = re.compile(r"^(?P<name>.+?), (?P<cite>\d+ U\.S\. (?:\(\d+ [\w.]+\) )?\d+(?:, \d+)* \(\d{4}\)|No\. [\w-]+(?:, [\w-]+)* \(U\.S\. [^)]*\)).*$")
OTHER_CITE = re.compile(r"^(?P<name>.+?),? (?P<cite>(?:\(\d{4}\) )?\d+ .*)$")


def _pages_list(text: str) -> list[int]:
    out: list[int] = []
    for part in re.split(r",\s*", text.strip().strip(",")):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", part)
        if m:
            out.extend(range(int(m.group(1)), int(m.group(2)) + 1))
        elif part.isdigit():
            out.append(int(part))
        else:
            raise ConanError(f"bad page list {text!r}")
    return out


def table_of_cases() -> list[CaseEntry]:
    pages = _pages(APPENDIX)
    start = next(i for i, p in enumerate(pages) if any(l.text == "TABLE OF CASES" for l in p[:3]))
    entries: list[list[str]] = []
    for page in pages[start:]:
        body = [l for l in page if l.y > 75 and printed_number([l]) is None and l.text != "TABLE OF CASES"]
        if not body:
            continue
        margin = min(l.x0 for l in body)
        for line in body:
            if re.fullmatch(r"[A-Z]", line.text):  # a letter heading
                continue
            if abs(line.x0 - margin) < 2 and (not entries or ENTRY.match(" ".join(entries[-1]))):
                entries.append([line.text])
            elif entries:
                entries[-1].append(line.text)
    out = []
    for parts in entries:
        # A docket number broken at its hyphen ("No. 18-" / "1334") joins without a space.
        text = re.sub(r"(\d-) (?=\d)", r"\1", " ".join(parts))
        m = ENTRY.match(text)
        _expect(bool(m), f"table of cases: no page list in {text!r}")
        c = SCOTUS_CITE.match(m.group("text")) or OTHER_CITE.match(m.group("text"))
        name, cite = (c.group("name"), c.group("cite")) if c else (m.group("text"), "")
        out.append(CaseEntry(name, cite, _pages_list(m.group("pages"))))
    _expect(len(out) > 5000, f"only {len(out)} cases in the table")
    return out


# ------------------------------------------------------------ overruled decisions


@dataclass
class Overruling:
    overruling: str
    year: str
    overruled: list[tuple[str, str]] = field(default_factory=list)  # (case as printed, year)
    page: int | None = None  # the printed page of the table the row starts on


def overruled() -> list[Overruling]:
    pages = _pages(APPENDIX, column_gap=12)
    rows: list[Overruling] = []
    started = False
    for page in pages:
        heads = [l.text for l in page[:4]]
        if any("OVERRULED BY SUBSEQUENT" in h or h == "TABLE OF OVERRULED DECISIONS" for h in heads):
            started = True
        elif started and any("TABLE OF LAWS HELD" in h or h.startswith("TABLE OF LAWS") for h in heads):
            break
        if not started:
            continue
        cells = [l for l in page if l.size < 8.5 and printed_number([l]) is None]
        cells.sort(key=lambda l: (l.y, l.x0))
        # Rows are separated by space; within a row, lines are 9 points apart.
        groups: list[list[Line]] = []
        for c in cells:
            if groups and c.y - max(x.y for x in groups[-1]) < 12:
                groups[-1].append(c)
            else:
                groups.append([c])
        for g in groups:
            col = lambda lo, hi: [l for l in g if lo <= l.x0 < hi]
            left, year, mid, years = col(0, 240), col(240, 300), col(300, 460), col(460, 999)
            if not mid:
                continue
            if left:
                rows.append(Overruling(" ".join(l.text for l in left), " ".join(l.text for l in year),
                                       page=printed_number(page)))
            _expect(bool(rows), "overruled table: a row with no overruling decision")
            # Each overruled case starts on the line of its year.
            starts = sorted(l.y for l in years) or [mid[0].y]
            for i, y in enumerate(starts):
                nxt = starts[i + 1] if i + 1 < len(starts) else 1e9
                text = " ".join(l.text for l in mid if y - 1 <= l.y < nxt - 1)
                yr = next(l.text for l in years if l.y == y) if years else ""
                if text:
                    rows[-1].overruled.append((text, yr))
            # Lines of the overruled column above the first year belong to the case before.
            before = [l for l in mid if l.y < starts[0] - 1]
            if before and rows[-1].overruled:
                pass
    _expect(len(rows) > 200, f"only {len(rows)} rows in the overruled table")
    return rows


# ------------------------------------------------------------ report


def citations_by_clause(cases: list[CaseEntry], pages: dict[int, list[str]], refs: set[str]) -> dict[str, Counter]:
    """Clause ref -> Counter of case citations: how many pages of that
    clause's essays cite each Supreme Court case."""
    out: dict[str, Counter] = defaultdict(Counter)
    for c in cases:
        if not c.supreme_court:
            continue
        for p in c.pages:
            for clause in {clause_ref(e, refs) for e in pages.get(p, [])} - {None}:
                out[clause][f"{c.name}, {c.citation}"] += 1
    return out


# The first set of cases (decisions 41 to 43) is the union of five rules,
# each applied to the Constitution Annotated as printed:
#  1. in each essay topic, the Supreme Court case its essays cite on the
#     most pages (every case, if tied), when that is at least TOPIC_PAGES;
#  2. every Supreme Court case cited on at least TOTAL_PAGES pages;
#  3. every decision that a case chosen by 1 or 2 overruled, per the Table
#     of Supreme Court Decisions Overruled by Subsequent Decisions;
#  4. every Supreme Court case named in the title of an essay
#     ("Liberty of Contract and Lochner v. New York");
#  5. every decision the table lists as overruled that is cited on at least
#     OVERRULED_PAGES pages: overruled decisions the essays still discuss.
TOPIC_PAGES = 4
TOTAL_PAGES = 10
OVERRULED_PAGES = 5
TOPIC = re.compile(r"^((?:Pre|Art[IVX]+|Amdt\d+)(?:\.S\d+)?(?:\.C\d+)?)\.(\d+)")
US_CITE = re.compile(r"(\d+) U\.S\. (?:\([^)]*\) )?(\d+)")
SLIP = re.compile(r"No\. ([\w-]+)(?:, [\w-]+)* \(U\.S\.")


def topic_of(essay_id: str) -> str | None:
    """An essay's topic: its id to the first number under the clause
    ("Amdt14.S1.8.1.3" -> "Amdt14.S1.8", "ArtI.S8.C3.2.1" -> "ArtI.S8.C3.2")."""
    m = TOPIC.match(essay_id)
    return f"{m.group(1)}.{m.group(2)}" if m else None


def case_keys(text: str) -> list[str]:
    """Supreme Court decisions cited in a text, as volume and page ("17 U.S.
    316", whatever the nominative reporter) or docket number of a slip
    opinion ("No. 19-1392"), in order."""
    found = [(m.start(), f"{m.group(1)} U.S. {m.group(2)}") for m in US_CITE.finditer(text)]
    found += [(m.start(), f"No. {m.group(1)}") for m in SLIP.finditer(text)]
    return [k for _, k in sorted(found)]


def name_key(text: str) -> str:
    """A case's name reduced to letters, for matching the same decision
    printed with different citations."""
    return re.sub(r"[^a-z]", "", re.split(r", (?:No\.|\d+ U\.S\.)", text)[0].lower())


def overruling_key(row: Overruling, keys: set[str], names: dict[str, str]) -> str | None:
    """The key of a row's overruling decision among `keys`, by citation or,
    failing that, by name (`names`: name_key -> key)."""
    by = [k for k in case_keys(row.overruling) if k in keys]
    return by[0] if by else names.get(name_key(row.overruling))


@dataclass
class Chosen:
    key: str
    name: str             # as the Table of Cases (or the overruled table) prints it
    reasons: list[str] = field(default_factory=list)


def landmark_cases(cases: list[CaseEntry], pages: dict[int, list[str]],
                   overrulings: list[Overruling] | None = None,
                   titles: dict[str, str] | None = None) -> dict[str, Chosen]:
    """The first set of cases, keyed by citation, each with why it was chosen."""
    cited: dict[str, set[int]] = defaultdict(set)
    names: dict[str, str] = {}
    for c in cases:
        if c.supreme_court:
            key = case_keys(c.citation)[0]
            cited[key] |= set(c.pages)  # one decision, whatever form its citation takes
            names.setdefault(key, f"{c.name}, {c.citation}")
    by_topic: dict[str, Counter] = defaultdict(Counter)
    for key, ps in cited.items():
        for p in ps:
            for t in {topic_of(e) for e in pages.get(p, [])} - {None}:
                by_topic[t][key] += 1
    chosen: dict[str, Chosen] = {}

    def choose(key: str, reason: str, name: str | None = None) -> None:
        chosen.setdefault(key, Chosen(key, names.get(key) or name or key)).reasons.append(reason)

    for t, counts in sorted(by_topic.items()):
        ranked = counts.most_common()
        if ranked and ranked[0][1] >= TOPIC_PAGES:
            for key, n in ranked:
                if n == ranked[0][1]:
                    choose(key, f"most cited in essay topic {t} ({n} pages)")
    for key, ps in sorted(cited.items()):
        if len(ps) >= TOTAL_PAGES:
            choose(key, f"cited on {len(ps)} pages")
    # The overruled table and the Table of Cases can print a citation
    # differently (Dobbs: "No. 19-1391" in one, "No. 19-1392" in the other),
    # so an overruling decision is also matched by its name.
    first = set(chosen)  # rule 3 follows only cases chosen by rules 1 and 2: one step, not a chain
    by_name = {name_key(c.name): k for k, c in chosen.items()}
    for row in overrulings or []:
        by = overruling_key(row, first, by_name)
        if by:
            for text, _ in row.overruled:
                for key in case_keys(text):
                    choose(key, f"overruled by {chosen[by].name.split(',')[0]} (table of overruled decisions)", text)
    # Rule 4. A name in a title is matched exactly against the Table of
    # Cases ("Brown v. Board of Education" names both decisions of that name).
    by_case_name: dict[str, set[str]] = defaultdict(set)
    for c in cases:
        if c.supreme_court and (" v. " in c.name or c.name.endswith("Cases")):
            by_case_name[c.name].add(case_keys(c.citation)[0])
    for eid, title in sorted((titles or {}).items()):
        if " v. " not in title and "Cases" not in title:
            continue
        for name, keys in by_case_name.items():
            if name in title and re.search(rf"(?<![\w.]){re.escape(name)}(?![\w])", title):
                for key in sorted(keys):
                    choose(key, f"named in the title of essay {eid}")
    # Rule 5.
    for row in overrulings or []:
        for text, _ in row.overruled:
            for key in case_keys(text):
                if len(cited.get(key, ())) >= OVERRULED_PAGES:
                    choose(key, f"overruled (table of overruled decisions) and cited on {len(cited[key])} pages", text)
    # Rule 6 (decision 53). Every decision the table lists as overruling a case
    # chosen so far, so that an overruled case in the library is never shown
    # without what overruled it (Plessy v. Ferguson and Bob Jones University
    # v. United States). One step: the cases rule 6 adds are not followed.
    so_far = set(chosen)
    by_name = {name_key(c.name): k for k, c in chosen.items()}
    for row in overrulings or []:
        if overruling_key(row, so_far, by_name):
            continue  # already in the set
        hits = [key for text, _ in row.overruled for key in case_keys(text) if key in so_far]
        keys = case_keys(row.overruling)
        if hits and keys:
            for key in hits:
                choose(keys[0], f"overrules {chosen[key].name.split(',')[0]} (table of overruled decisions)", row.overruling)
    return chosen


def first_set() -> dict[str, Chosen]:
    """The first set of cases from the 2022 edition as printed: what the
    case import and the case links start from."""
    return landmark_cases(table_of_cases(), essay_pages(), overruled(), essay_titles())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cases", type=int, default=0, help="list the N most-cited Supreme Court cases")
    ap.add_argument("--landmarks", action="store_true", help="list the first set of cases (decision 41)")
    args = ap.parse_args(argv)
    corpus = load_corpus()
    refs = set(corpus.segments) | set(corpus.divisions) | corpus.prefixes
    pages = essay_pages()
    cases = table_of_cases()
    rows = overruled()
    scotus = [c for c in cases if c.supreme_court]
    unknown = sorted({e for ids in pages.values() for e in ids if clause_ref(e, refs) not in refs})
    print(f"essay pages: {len(pages)}; essays: {len({e for ids in pages.values() for e in ids})}; "
          f"essays with no matching ref: {unknown[:10]}")
    print(f"table of cases: {len(cases)} entries, {len(scotus)} Supreme Court")
    print(f"overruled table: {len(rows)} rows, {sum(len(r.overruled) for r in rows)} overruled decisions")
    if args.landmarks:
        chosen = landmark_cases(cases, pages, rows, essay_titles())
        print(f"first set: {len(chosen)} cases")
        for c in sorted(chosen.values(), key=lambda c: c.name):
            print(f"  {c.name}  [{'; '.join(c.reasons)}]")
    if args.cases:
        by_clause = citations_by_clause(cases, pages, refs)
        total = Counter()
        for clause, counts in by_clause.items():
            total.update(counts)
        for name, n in total.most_common(args.cases):
            top = sorted(((counts[name], cl) for cl, counts in by_clause.items() if counts[name]), reverse=True)[:3]
            print(f"{n:4}  {name}  [{', '.join(f'{cl} {k}' for k, cl in top)}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
