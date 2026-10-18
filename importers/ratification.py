"""Import essays and pamphlets of the ratification debate from 19th-century
compilations, read from OCR scans (see importers/ocr.py).

Inputs (sources/manifest.json ids): the Internet Archive scans of
  Ford, ed., Essays on the Constitution (1892)       ia-ford-essays-1892-*
  Ford, ed., Pamphlets on the Constitution (1888)    ia-ford-pamphlets-1888-*
  McMaster and Stone, eds., Pennsylvania and the
    Federal Constitution (1888)                       ia-mcmaster-stone-1888-*
Outputs: texts/{work_id}.json, one per series (refs {Series}.{essay}.{paragraph}).

Series are listed in importers/ratification_series.py. For each, the
importer takes the printed pages the edition's table of contents gives,
splits them into essays at each essay heading, separates the heading block
(newspaper, number, date, salutation) and the closing signature from the
paragraphs, and checks every word against the other scans in two passes:
first align all scans and collect the words two scans read identically
("attested"), then vote on each word (importers/ocr.py: vote).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from importers.ocr import (TOKEN, Block, Reference, align, attested, blocks, classify, consensus, key, known_words,
                          parse_djvu_xml)
from importers.ratification_series import BOOKS, SERIES
from tools.common import TEXTS_DIR, raw_path, read_raw_text, roman_to_int, write_json


class ImportError_(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ImportError_(msg)


# ------------------------------------------------------------ books


@dataclass
class LoadedBook:
    pages: list
    refs: list[Reference]
    offset: int  # leaf = printed page + offset (most common in the book)


@lru_cache(maxsize=None)
def load_book(book_id: str) -> LoadedBook:
    book = BOOKS[book_id]
    pages = parse_djvu_xml(raw_path(book["primary"]))
    classify(pages, book.get("split_heads", False))
    offsets = Counter(p.leaf - int(p.folio) for p in pages if p.folio and p.folio.isdigit())
    _expect(bool(offsets), f"{book_id}: no printed page numbers found")
    refs = [Reference(name, read_raw_text(sid)) for name, sid in book["references"].items()]
    return LoadedBook(pages, refs, offsets.most_common(1)[0][0])


def clean_vocabulary() -> set[str]:
    return known_words([read_raw_text(sid) for sid in (
        "gutenberg-federalist-18", "nara-constitution", "nara-bill-of-rights", "nara-amendments-11-27")])


def leaf_range(book: LoadedBook, first_page: int, last_page: int) -> tuple[int, int]:
    """Scan pages for a range of printed pages (the book's usual page offset,
    corrected wherever the printed page number itself was read)."""
    folio = {p.leaf: int(p.folio) for p in book.pages if p.folio and p.folio.isdigit()}

    def confirmed(leaf: int) -> bool:
        """A page number read on this page and, consistently, on a page near it."""
        return any(folio.get(leaf + d) == folio[leaf] + d for d in (-2, -1, 1, 2))

    def leaf_of(page: int) -> int:
        # Plates (unnumbered leaves) shift the offset; take the page whose
        # number was read (and agrees with its neighbours') nearest to where
        # the usual offset puts it.
        guess = page + book.offset
        exact = [leaf for leaf, n in folio.items() if n == page and abs(leaf - guess) <= 12 and confirmed(leaf)]
        return min(exact, key=lambda leaf: abs(leaf - guess)) if exact else guess
    return leaf_of(first_page), leaf_of(last_page)


# ------------------------------------------------------------ structure


def number_of(numeral: str) -> int | None:
    """An essay number as printed: arabic, or a Roman numeral in which OCR
    may have read "I" as "1", "l", "|" or "!". None if it cannot be read."""
    n = numeral.strip().rstrip(".,;")
    if n.isdigit():
        return int(n)
    try:
        return roman_to_int(re.sub(r"[1l|!]", "I", n).upper())
    except ValueError:
        return None


def numeral_reads_as(printed: str, want: int) -> bool:
    """True when a printed numeral, as OCR read it, can be `want`: OCR reads
    a final I as L ("VL", "XL" for XI), II as H ("VH") and V as Y ("lY")."""
    n = printed.strip().rstrip(".,;").replace("Y", "V")
    readings = {n, n.replace("H", "II"), re.sub(r"(?<=[IVX])L$", "I", n), re.sub(r"(?<=[IVX])L$", "I", n.replace("H", "II"))}
    return want in {number_of(r) for r in readings}


def essay_ids(series: dict) -> list[str]:
    """The essays' ids in order: the printed numbers, unless the series
    lists them (a duplicate printed number gets a letter: "10", "10b")."""
    if "ids" in series:
        return list(series["ids"])
    first = series.get("first", 1)
    return [str(first + k) for k in range(series["essays"])]


def split_essays(series: dict, bs: list) -> list[tuple[str, object, list]]:
    """[(id, heading block, blocks)] for each essay, in order.

    An essay starts at a block matching the series' heading pattern. OCR
    sometimes puts a heading in one paragraph with the line before it (the
    last essay's signature), so a heading at the end of a block is split off.
    The printed number in each heading must agree with the essay's id,
    unless the series lists the id under `unread_numerals` (OCR misread the
    numeral, checked against the page image). A single piece starts at the
    last match (its title page repeats the heading)."""
    heading = re.compile(r"(?:^|\s)(?:" + series["heading"] + r")\s*$", re.I if series.get("heading_ignore_case") else 0)
    ids = essay_ids(series)
    out: list[tuple[str, object, list]] = []
    for b in bs:
        text = b.text.strip()
        m = heading.search(text) if b.kind == "text" and len(text.split()) <= 14 else None
        if not m:
            if out:
                out[-1][2].append(b)
            continue
        if len(ids) == 1 and out:
            out = []  # a single piece: its title page comes first; the text starts at the last heading
        if m.start() > 0 and out:
            out[-1][2].append(Block(text[:m.start()].strip(), b.leaves, b.folios, b.kind, b.first_indented))
            b = Block(text[m.start():].strip(), b.leaves[-1:], b.folios[-1:], b.kind, True)
        rest = (m.groupdict().get("rest") or "").strip()
        if rest:
            # The salutation printed on the heading's line ("No. III. * To the People").
            b, rest_block = (Block(b.text[:len(b.text) - len(rest)].strip(), b.leaves, b.folios, b.kind, True),
                             Block(rest, b.leaves, b.folios, b.kind, True))
        else:
            rest_block = None
        k = len(out)
        _expect(k < len(ids), f"{series['slug']}: more essay headings than the {len(ids)} expected (at scan page "
                f"{b.leaves[0]}: {b.text!r})")
        printed = m.groupdict().get("n")
        want = int(re.match(r"\d+", ids[k]).group())
        if printed is not None and ids[k] not in series.get("unread_numerals", []):
            _expect(numeral_reads_as(printed, want), f"{series['slug']}: essay {ids[k]} is numbered {printed!r} in the "
                    f"scan (page {b.leaves[0]})")
        out.append((ids[k], b, [rest_block] if rest_block else []))
    _expect(len(out) == len(ids), f"{series['slug']}: expected {len(ids)} essays, found {len(out)} "
            f"({[i for i, _, _ in out]})")
    return out


SALUTATION = re.compile(
    r"^(To\s.{3,90}|Mr\.?\s+[A-Z]\w+\s*[:,.;]?|(?:Dear\s+)?Sir\s*[:,.;]|Gentlemen\s*[:,.;]"
    r"|My\s+(?:dear\s+)?(?:Sir|Friend)[^.]{0,20}[:,.;]|Friends.{0,40}[:,.;])$")
CONTINUED = re.compile(r"to\s+be\s+contin|remainder\s+next|^\W*finis\W*$", re.I)
MONTH = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s", re.I)
COMPLIMENT = re.compile(r"(?:Your'?s,?\s*&c|I am,?\s|I have the hono)", re.I)
CONTINUED_FROM = re.compile(r"(?:contin|conclu)\w*\s+from\s+our\s+last", re.I)
# Salutations on a line of their own, as OCR may misread them ("Ge7itlemeii,").
GREETINGS = ("Gentlemen,", "Sir,", "Friends and Brethren,", "Friends and Fellow Citizens,",
             "Friends, Countrymen and Fellow Citizens,", "Fellow Citizens,")


GREETING_END = re.compile(r"^(.*?\S)\s+((?:My\s+)?(?:Dear\s+)?Sir|Gentlemen)\s*[,:.;]?$")


def split_greetings(bs: list) -> list:
    """Split a greeting printed on the line of the date ("October 9, 1787.
    Dear Sir,") into a line of its own, among an essay's first lines."""
    out = []
    for i, b in enumerate(bs):
        m = GREETING_END.match(b.text.strip()) if i < 6 and b.kind == "text" and len(b.text.split()) <= 12 else None
        if m and re.search(r"\d|^To\s", m.group(1)):
            out += [Block(m.group(1), b.leaves, b.folios, b.kind, b.first_indented),
                    Block(b.text.strip()[len(m.group(1)):].strip(), b.leaves, b.folios, b.kind, True)]
        else:
            out.append(b)
    return out


@dataclass
class Essay:
    id: str
    header: list = field(default_factory=list)  # blocks
    salutation: list = field(default_factory=list)  # blocks
    body: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    closing: list = field(default_factory=list)  # blocks after the body (signature, date)
    inline_tokens: int = 0  # tokens of the inline signature at the end of the last paragraph


def title_case(text: str) -> bool:
    """Most longer words capitalized, as in a title."""
    words = [w for w in re.findall(r"[A-Za-z]+", text) if len(w) > 3]
    return len(words) >= 2 and sum(w[0].isupper() for w in words) >= 0.7 * len(words)


def like(text: str, name: str, floor: float = 0.6) -> bool:
    """True when a short line reads as `name` (allowing OCR misreadings)."""
    a, b = key(text), key(name)
    return bool(a) and SequenceMatcher(None, a, b, autojunk=False).ratio() >= floor


def structure(series: dict, essay_id: str, essay_blocks: list) -> Essay:
    """Separate an essay's heading lines, salutation, paragraphs, notes and
    closing. Heading lines are the short lines before the salutation (or
    before the first long paragraph); the closing is the run of short lines
    after the last paragraph: the signature, a place or date, "(To be
    continued.)"."""
    e = Essay(essay_id)
    limit = series.get("header_max_words", 10)
    # A block with no letters or figures is a stray mark, not text.
    essay_blocks = [b for b in essay_blocks if key(b.text) or len(b.text.strip()) > 3]
    i = 0
    while i < len(essay_blocks) and i < 9:
        b = essay_blocks[i]
        t = b.text.strip()
        words = len(t.split())
        if b.kind == "note":
            break
        if (SALUTATION.match(t) and words <= 16) or (words <= 4 and any(like(t, g, 0.5) for g in GREETINGS)):
            e.salutation.append(b)
            i += 1
            continue
        if e.salutation and words <= 6 and (CONTINUED_FROM.search(t) or like(t, "(Continued from our last.)", 0.6)
                                            or like(t, "(Concluded from our last.)", 0.6)):
            e.header.append(b)  # "(Continued from our last.)" under the salutation
            i += 1
            continue
        if e.salutation:
            break
        # A long line is still a heading line when it is a title ("Observations
        # on the New Federal Constitution.") or a salutation follows it.
        if words > limit and not (words <= 18 and (title_case(t) or (
                i + 1 < len(essay_blocks) and SALUTATION.match(essay_blocks[i + 1].text.strip())))):
            break
        e.header.append(b)
        i += 1
    rest = essay_blocks[i:]
    e.notes = [b for b in rest if b.kind == "note"]
    body = [b for b in rest if b.kind == "text"]
    signature = series.get("signature")
    sig_words = len(signature.split()) + 1 if signature else 0
    while len(body) > 1:
        t = body[-1].text.strip()
        words = len(t.split())
        if (words <= 8 and ((signature and words <= sig_words and like(t, signature, 0.5)) or re.search(r"\d", t)
                            or MONTH.search(t) or CONTINUED.search(t) or (e.closing and words <= 6))
                or (words <= 16 and COMPLIMENT.match(t))
                or any(re.search(c, t) for c in series.get("closing_lines", []))):
            e.closing.insert(0, body.pop())
            continue
        break
    # A signature run into the end of the last paragraph ("... free. A Landholder."),
    # perhaps followed by a place and date ("... ? CENTINEL. Philadelphia, Nov. 30, 1787.").
    # When a place or date follows, the name must start a sentence, so a name
    # ending a sentence ("... by Caesar. October 15.") stays in the text.
    if signature and body:
        n = len(TOKEN.findall(signature))
        tail = TOKEN.findall(body[-1].text)
        for after in range(7):
            k = len(tail) - after - n
            if k < 4:
                break
            rest = " ".join(tail[k + n:])
            if after and not (re.search(r"\d", rest) or MONTH.search(rest + " ")):
                continue
            name = " ".join(tail[k:k + n])
            if tail[k][:1].isupper() and (
                    (not after and like(name, signature, 0.75))
                    or (like(name, signature, 0.7) and tail[k - 1].endswith((".", "?", "!")))):
                e.inline_tokens = n + after
                break
    e.body = body
    return e


# ------------------------------------------------------------ passes


@dataclass
class Prepared:
    series: dict
    essays: list[Essay]
    readings: dict[int, list[dict]]  # id(block) -> per-token readings


def prepare(series: dict) -> Prepared:
    book = load_book(series["book"])
    first, last = leaf_range(book, *series["pages"])
    bs = blocks(book.pages, first, last)
    raw = split_essays(series, bs)
    essays = []
    hints: dict[str, int] = {}
    readings: dict[int, list[dict]] = {}
    for n, head, eb in raw:
        eb = split_greetings(eb)
        # The essay's heading and text are aligned as one run, so that short
        # lines (newspaper, date, salutation) are aligned in context. Notes
        # are aligned one by one: a paragraph rejoined across a page break
        # puts them in a different order from the other scans' page text.
        stream = [head, *(b for b in eb if b.kind != "note")]
        tokens = [TOKEN.findall(b.text) for b in stream]
        aligned = align([t for ts in tokens for t in ts], book.refs, hints)
        at = 0
        for b, ts in zip(stream, tokens):
            readings[id(b)] = aligned[at:at + len(ts)]
            at += len(ts)
        for b in eb:
            if b.kind == "note":
                readings[id(b)] = align(TOKEN.findall(b.text), book.refs, dict(hints))
        e = structure(series, n, eb)
        if series.get("heading_in_publication"):
            e.header.insert(0, head)  # the heading is the newspaper's name
        essays.append(e)
    return Prepared(series, essays, readings)


def text_of(block, prepared: Prepared, known: set[str]) -> tuple[str, list[dict]]:
    return text_of_readings(prepared.readings[id(block)], known)


def text_of_readings(readings: list[dict], known: set[str]) -> tuple[str, list[dict]]:
    """Text decided by vote, with uncertain spans as character offsets."""
    words, unsettled = consensus(readings, known)
    pos = [0]
    for w in words:
        pos.append(pos[-1] + len(w) + 1)
    spans = [{"end": pos[u.end] - 1, "readings": dict(sorted(u.readings.items())), "start": pos[u.start]}
             for u in unsettled]
    return " ".join(words), spans


def build(prepared: Prepared, known: set[str]) -> dict:
    series = prepared.series
    bookdef = BOOKS[series["book"]]
    prefix = series["slug"]
    divisions, segments = [], []

    def joined(bs: list, lead: tuple[str, list[dict]] | None = None) -> tuple[str, list[dict]]:
        """Blocks joined with spaces into one line, with their uncertain spans."""
        parts, spans, at = [], [], 0
        for text, sp in ([lead] if lead else []) + [text_of(b, prepared, known) for b in bs]:
            spans += [{**s, "end": s["end"] + at, "start": s["start"] + at} for s in sp]
            parts.append(text)
            at += len(text) + 1
        return " ".join(parts), spans

    def segment(ref: str, label: str, block, kind: str | None = None) -> dict:
        text, spans = text_of(block, prepared, known)
        seg = {"label": label, "pages": block.folios, "ref": ref,
               "scan": {"item": bookdef["item"], "leaves": block.leaves}, "text": text}
        if kind:
            seg["kind"] = kind
        if spans:
            seg["uncertain"] = spans
        return seg

    single = len(prepared.essays) == 1
    for e in prepared.essays:
        # A single piece has refs {Slug}.{paragraph}; a series {Slug}.{essay}.{paragraph}.
        base = prefix if single else f"{prefix}.{e.id}"
        label = series["short"] if single else f"{series['short']} {e.id}"
        # Heading lines, salutation and signature are strings, as in other
        # works; words in them the scans could not settle are listed under
        # "uncertain", keyed by field ("publication.0" is the first line).
        div = {"attribution": series["attribution"], "label": label, "level": 1, "publication": [],
               "ref": base}
        unsettled: dict[str, list[dict]] = {}
        for i, b in enumerate(e.header):
            text, sp = joined([b])
            div["publication"].append(text)
            if sp:
                unsettled[f"publication.{i}"] = sp
        if e.salutation:
            div["salutation"], sp = joined(e.salutation)
            if sp:
                unsettled["salutation"] = sp
        lead = None
        if e.inline_tokens:
            last = e.body[-1]
            lead = text_of_readings(prepared.readings[id(last)][-e.inline_tokens:], known)
            prepared.readings[id(last)] = prepared.readings[id(last)][:-e.inline_tokens]
        if e.closing or lead:
            div["signature"], sp = joined(e.closing, lead)
            if sp:
                unsettled["signature"] = sp
        if unsettled:
            div["uncertain"] = unsettled
        divisions.append(div)
        for p, b in enumerate(e.body, 1):
            segments.append(segment(f"{base}.{p}", f"{label}, ¶ {p}", b))
        for k, b in enumerate(e.notes, 1):
            segments.append(segment(f"{base}.fn{k}", f"{label}, note {k}", b, "footnote"))
    attribution = {"source": f"{bookdef['short']}, title page of the section", **series["attribution"]}
    for d in divisions:
        d["attribution"] = attribution
    return {
        "attribution": attribution,
        "date": series.get("date"),
        "divisions": divisions,
        "edition": {"name": bookdef["edition"],
                    "notes": f"{bookdef['edition']}, pp. {series['pages'][0]}–{series['pages'][1]}. Read from OCR "
                             "scans and checked word by word against independent scans; words the scans could not "
                             "settle are marked as uncertain. See docs/editions.md."},
        "id": series["work_id"],
        "position": series["position"],
        "ref_prefix": prefix,
        "segments": segments,
        "short": series["short"],
        "source_ids": [bookdef["primary"], *bookdef["references"].values()],
        "title": series["title"],
    }


def run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    prepared = [prepare(s) for s in SERIES]
    known = clean_vocabulary()
    for p in prepared:
        for r in p.readings.values():
            known |= attested(r)
    paths = []
    for p in prepared:
        path = out_dir / f"{p.series['work_id']}.json"
        write_json(path, build(p, known))
        paths.append(path)
    return paths


if __name__ == "__main__":
    for p in run():
        print(f"wrote {p}")
