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
from functools import lru_cache
from pathlib import Path

from importers.ocr import TOKEN, Reference, align, attested, blocks, classify, consensus, known_words, parse_djvu_xml
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
    classify(pages)
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
    def leaf_of(page: int) -> int:
        exact = [p.leaf for p in book.pages if p.folio == str(page)]
        return exact[0] if exact else page + book.offset
    return leaf_of(first_page), leaf_of(last_page)


# ------------------------------------------------------------ structure


def number_of(numeral: str) -> int:
    """An essay number as printed: arabic, or a Roman numeral in which OCR
    may have read "I" as "1", "l" or "|"."""
    n = numeral.strip().rstrip(".,")
    if n.isdigit():
        return int(n)
    return roman_to_int(re.sub(r"[1l|]", "I", n).upper())


def split_essays(series: dict, bs: list) -> list[tuple[int, object, list]]:
    """[(number, heading block, blocks)] for each essay."""
    heading = re.compile(series["essay_heading"])
    essays: list[tuple[int, object, list]] = []
    for b in bs:
        m = heading.match(b.text.strip()) if b.kind == "text" else None
        if m:
            n = number_of(m.group(1)) if m.groups() and m.group(1) else len(essays) + 1
            essays.append((n, b, []))
            continue
        if essays:
            essays[-1][2].append(b)
    return essays


SALUTATION = re.compile(r"^(To\s.{3,80}[:.,]|(?:Dear\s+)?Sir\s*[:,.]|Gentlemen\s*[:,.]|My\s+(?:dear\s+)?(?:Sir|Friend)[^.]{0,20}[:,.])$", re.I)


@dataclass
class Essay:
    number: int
    header: list = field(default_factory=list)  # blocks
    salutation: object = None  # block
    body: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    closing: list = field(default_factory=list)  # blocks after the body (signature, date)
    inline_tokens: int = 0  # tokens of the inline signature at the end of the last paragraph


def structure(series: dict, number: int, essay_blocks: list) -> Essay:
    e = Essay(number)
    i = 0
    while i < len(essay_blocks) and i < 7:
        b = essay_blocks[i]
        t = b.text.strip()
        if b.kind == "note":
            break
        if SALUTATION.match(t):
            e.salutation = b
            i += 1
            break
        if len(t.split()) <= series.get("header_max_words", 10):
            e.header.append(b)
            i += 1
            continue
        break
    rest = essay_blocks[i:]
    e.notes = [b for b in rest if b.kind == "note"]
    body = [b for b in rest if b.kind == "text"]
    # Closing: short blocks at the end (signature, place, date), and a
    # signature run into the end of the last paragraph ("... truth. Cato.").
    sig = re.compile(series.get("signature", r"(?!x)x"), re.I)
    while len(body) > 1:
        t = body[-1].text.strip()
        if sig.match(t) or (len(t.split()) <= 6 and (re.search(r"\d", t) or e.closing)):
            e.closing.insert(0, body.pop())
            continue
        break
    inline = series.get("signature_inline")
    if inline and body:
        m = re.search(r"\s(" + inline + r")\s*$", body[-1].text.strip(), re.I)
        if m:
            e.inline_tokens = len(TOKEN.findall(m.group(1)))
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
    _expect(len(raw) == series["essays"], f"{series['slug']}: expected {series['essays']} essays, found "
            f"{len(raw)} ({[n for n, _, _ in raw]})")
    essays = []
    hints: dict[str, int] = {}
    readings: dict[int, list[dict]] = {}
    for idx, (n, head, eb) in enumerate(raw, 1):
        _expect(n == idx, f"{series['slug']}: essay {idx} is numbered {n} in the scan")
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

    for e in prepared.essays:
        n = e.number
        label = f"{series['short']} {n}" if series["essays"] > 1 else series["short"]
        # Heading lines, salutation and signature are strings, as in other
        # works; words in them the scans could not settle are listed under
        # "uncertain", keyed by field ("publication.0" is the first line).
        div = {"attribution": series["attribution"], "label": label, "level": 1, "publication": [],
               "ref": f"{prefix}.{n}"}
        unsettled: dict[str, list[dict]] = {}
        for i, b in enumerate(e.header):
            text, sp = joined([b])
            div["publication"].append(text)
            if sp:
                unsettled[f"publication.{i}"] = sp
        if e.salutation:
            div["salutation"], sp = joined([e.salutation])
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
            segments.append(segment(f"{prefix}.{n}.{p}", f"{label}, ¶ {p}", b))
        for k, b in enumerate(e.notes, 1):
            segments.append(segment(f"{prefix}.{n}.fn{k}", f"{label}, note {k}", b, "footnote"))
    return {
        "attribution": series["attribution"],
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
