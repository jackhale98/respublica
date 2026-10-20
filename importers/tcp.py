"""Texts from the Text Creation Partnership, checked against a scan
(decision 67).

The Text Creation Partnership (TCP; the University of Michigan and Oxford)
keyed early printed books by hand from page images and released them under
CC0 as TEI P5 XML (one repository per text under
github.com/textcreationpartnership, pinned here to a commit). Where a TCP
text of the printing exists, it is the text, not OCR: `Walker` turns its TEI
into blocks of words with the printed page each is on. Nothing is added or
modernized. What the TCP itself marks is kept as it marks it:

  * a word broken at a line end (`<g ref="char:EOLhyphen"/>`) is joined,
    as the OCR importers rejoin hyphenated words;
  * an abbreviation the TCP expands (`<expan>`) is given as its expansion
    (`<ex>`), the TCP's reading of it;
  * characters the keyers could not read (`<gap>`) are given as the TCP's
    mark for them (its `<desc>`, "•" for a letter), and so is a stop they
    could not make out ("▪", `char:punc`); the word is marked uncertain:
    they are never filled in;
  * the long s is as the TCP keyed it: Common Sense and Locke's text give
    a round s (their keying rules), the Evans-TCP pamphlets of the
    ratification debate the long s (ſ); the editions' notes say which;
  * a word broken at a line end without a hyphen (`char:EOLunhyphen`) is
    joined too.

Each block's words are then checked against the OCR of Internet Archive
scans of the same printing (`check`), as the Anti-Federalist Library's text
was checked against the scans (decision 55), with the roles turned round:
the TCP is the text and the scans only a check. Words are compared by their
letters and figures with the long s set aside (`fkey`). A word is marked
uncertain, with the TCP's reading (`tcp`) and each scan's, when no scan
reads it alike and a scan reads another real word there (`judge`), has no
word there where it reads the words around cleanly, or has a word of the
clean texts more just after it. A scan's reading that is not a word
("tliis"), or is only part of the TCP's, is OCR noise and leaves the TCP's
word settled. The TCP's word is always the one in the text: a difference is
marked, never chosen. The first scan also gives each passage its page
images (`scan.leaves`).

The pamphlets of the ratification debate (`importers/pamphlets.py`,
decision 69) are read by division (`divisions`), a letter's salutation,
date line and signature apart (`Walker(letters=True)`); no scan of their
printings was found, so only their gaps are marked (`gap_spans`). One of
them, N16599, is also a tie-breaker between the scans of two other works
(`reference`, `readings`; importers/ratification.py).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from importers.ocr import Reference, key, pair_similar, plain
from tools.common import raw_path

TEI = "{http://www.tei-c.org/ns/1.0}"

# Markers in the text while it is built (control characters never in a TCP text).
HYPH = "\x07"  # a word broken at a line end
PB_OPEN, PB_CLOSE = "\x05", "\x06"  # a page break, with its printed number
GAP_OPEN, GAP_CLOSE = "\x03", "\x04"  # characters the TCP could not read
SPLIT = "\x08"
KEEP = "\x02"  # a space inside a gap's mark  # a numbered paragraph begins (inside a quotation), around its number


def tag(el: ET.Element) -> str:
    return el.tag.removeprefix(TEI)


def load(source_id: str) -> ET.Element:
    """The TEI root of a TCP file (a raw source)."""
    return ET.parse(raw_path(source_id)).getroot()


def header(root: ET.Element) -> dict[str, str]:
    """The TCP's own record of the text: its TCP and catalogue numbers, and
    the printing it was keyed from (`sourceDesc`)."""
    pub = root.find(f"{TEI}teiHeader/{TEI}fileDesc/{TEI}publicationStmt")
    ids = {i.get("type"): (i.text or "").strip() for i in pub.iter(f"{TEI}idno")}
    bibl = root.find(f"{TEI}teiHeader/{TEI}fileDesc/{TEI}sourceDesc/{TEI}biblFull")
    imprint = bibl.find(f"{TEI}publicationStmt")
    return {
        "tcp": ids.get("TCP", ""),
        "catalogue": ids.get("STC", ""),
        "extent": " ".join((bibl.findtext(f"{TEI}extent") or "").split()),
        "publisher": " ".join((imprint.findtext(f"{TEI}publisher") or "").split()),
        "place": " ".join((imprint.findtext(f"{TEI}pubPlace") or "").split()),
        "date": " ".join((imprint.findtext(f"{TEI}date") or "").split()),
        "licence": " ".join("".join(pub.find(f"{TEI}availability").itertext()).split()),
    }


# ------------------------------------------------------------ text


@dataclass
class Block:
    """A paragraph (or a list item, a heading, a note) of a TCP text."""
    kind: str  # p | head | note | trailer
    tokens: list[str]
    pages: list[str]  # printed page numbers it is on, as the TCP's page breaks give them
    page_of: list[str | None]  # the printed page each token is on
    gaps: set[int] = field(default_factory=set)  # tokens with characters the TCP could not read
    n: str | None = None  # the TCP's number for it (a section's, in Locke)
    mark: str | None = None  # a note's mark ("*")

    @property
    def text(self) -> str:
        return " ".join(self.tokens)


# Parts of a block that stand apart from the words around them.
APART = ("bibl", "l", "p", "item", "salute", "dateline", "opener", "epigraph", "byline")


class Walker:
    """Reads a TEI division in document order into blocks, keeping track of
    the printed page. With `letters`, a letter's opening and closing are
    read into blocks of their parts (`salute`, `dateline`, `signed`;
    decision 69) instead of one paragraph each."""

    def __init__(self, page: str | None = None, letters: bool = False):
        self.page = page
        self.letters = letters

    def pieces(self, el: ET.Element, notes: list[tuple[ET.Element, str | None]]) -> list[str]:
        """The text of an element as pieces with markers (see the top). Notes
        inside it are collected in `notes` (with the page they are on), not
        run into the text."""
        out: list[str] = []
        if el.text:
            out.append(el.text)
        for child in el:
            t = tag(child)
            if t == "g" and child.get("ref") in ("char:EOLhyphen", "char:EOLunhyphen"):
                out.append(HYPH)
            elif t == "pb":
                # (An unnumbered page has an empty number: its words have no printed page.)
                out.append(f"{PB_OPEN}{child.get('n') or ''}{PB_CLOSE}")
            elif t == "note":
                notes.append((child, self.page_at(out)))
            elif t == "g" and child.get("ref") == "char:punc":
                # A stop the keyers could not make out ("▪"): kept, and the word marked.
                out.append(f"{GAP_OPEN}{''.join(child.itertext())}{GAP_CLOSE}")
            elif t == "gap":
                desc = " ".join("".join(child.itertext()).split()) or "•"
                out.append(f"{GAP_OPEN}{desc}{GAP_CLOSE}")
            elif t == "expan":
                ex = child.findall(f"{TEI}ex")
                out.append("".join("".join(e.itertext()) for e in ex) if ex else "".join(self.pieces(child, notes)))
            elif t in ("hi", "q", "abbr", "g", "bibl", "l", "lg", "seg", "date", "name", "foreign", "label", "am", "ex",
                       "sic", "corr", "choice", "orig", "reg", "ref", "num", "head", "p", "trailer", "signed", "closer",
                       "item", "list", "salute", "dateline", "opener", "epigraph", "byline"):
                inner = self.pieces(child, notes)
                # A block inside the text (a quotation's attribution, a line
                # of verse, an item of a list) stands apart from the words before it.
                if t in APART:
                    out.append(" ")
                if t == "p" and child.get("n"):
                    # A numbered paragraph (a section) that begins inside a
                    # quotation: the block ends here and the section begins.
                    out.append(f"{SPLIT}{child.get('n')}{SPLIT}")
                out.extend(inner)
                if t in APART:
                    out.append(" ")
            else:
                raise ValueError(f"TCP text: no rule for <{t}>")
            if child.tail:
                out.append(child.tail)
        return out

    def page_at(self, pieces: list[str]) -> str | None:
        found = re.findall(f"{PB_OPEN}([^{PB_CLOSE}]*){PB_CLOSE}", "".join(pieces))
        return (found[-1] or None) if found else self.page

    def block(self, el: ET.Element, kind: str, notes: list[tuple[ET.Element, str | None]]) -> list[Block]:
        """The element as a block, or as several where a numbered paragraph
        begins inside it."""
        raw = "".join(self.pieces(el, notes))
        parts = raw.split(SPLIT)
        out = []
        for k in range(0, len(parts), 2):
            n = el.get("n") if k == 0 else parts[k - 1]
            b = to_block(parts[k], kind, self.page, n, n if kind == "note" else None)
            ends = re.findall(f"{PB_OPEN}([^{PB_CLOSE}]*){PB_CLOSE}", parts[k])
            if ends:
                self.page = ends[-1] or None
            if b.tokens:
                out.append(b)
        return out

    def blocks(self, div: ET.Element, skip: tuple[str, ...] = ()) -> list[Block]:
        """The blocks of a division, in order: headings, paragraphs (each item
        of a list as one), quotations set apart, trailers, and notes after
        the paragraph they are marked in. Divisions inside it are read too."""
        out: list[Block] = []
        for child in div:
            t = tag(child)
            if t in skip:
                continue
            notes: list[tuple[ET.Element, str | None]] = []
            if t == "pb":
                self.page = child.get("n") or None
                continue
            if self.letters and t in ("opener", "closer", "epigraph"):
                out += self.blocks(child, skip)
            elif self.letters and t in ("salute", "dateline", "signed"):
                out += self.block(child, t, notes)
            elif t in ("head", "p", "q", "trailer", "item", "closer", "signed", "lg", "bibl", "byline"):
                out += self.block(child, {"head": "head", "trailer": "trailer"}.get(t, "p"), notes)
            elif t == "list":
                out += self.blocks(child, skip)
            elif t == "note":
                notes.append((child, self.page))
            elif t == "div":
                out += self.blocks(child, skip)
            else:
                raise ValueError(f"TCP division: no rule for <{t}>")
            for note, page in notes:
                keep = self.page
                self.page = page
                inner: list[tuple[ET.Element, str | None]] = []
                out += self.block(note, "note", inner)
                if inner:
                    raise ValueError("TCP text: a note inside a note")
                self.page = keep
        return out


def to_block(raw: str, kind: str, page: str | None, n: str | None = None, mark: str | None = None) -> Block:
    """Words from text with markers: a broken word is joined across the line
    end (and any page break there), page breaks give each word its page,
    and words holding a gap are noted."""
    raw = re.sub(f"\\s+{HYPH}", HYPH, raw)  # (the TEI may break the line before a line-end mark)
    raw = re.sub(f"{HYPH}((?:\\s|{PB_OPEN}[^{PB_CLOSE}]*{PB_CLOSE})*)",
                 lambda m: re.sub(r"\s", "", m.group(1)), raw)
    tokens, page_of, gaps, pages = [], [], set(), [page] if page else []
    marker = f"{PB_OPEN}([^{PB_CLOSE}]*){PB_CLOSE}"

    def turn(to: str) -> None:
        nonlocal page
        page = to or None
        if to and to not in pages:
            pages.append(to)

    # The TCP's mark for a gap may hold a space ("〈7 letters〉"): it stays in its word.
    raw = re.sub(f"{GAP_OPEN}[^{GAP_CLOSE}]*{GAP_CLOSE}", lambda m: m.group().replace(" ", KEEP), raw)
    for tok in raw.split():
        tok = tok.replace(KEEP, " ")
        # A page break before a word puts it on the new page; one inside or
        # after it (a word broken across the page) puts the next word there.
        lead = re.match(f"(?:{PB_OPEN}[^{PB_CLOSE}]*{PB_CLOSE})*", tok).group()
        for p in re.findall(marker, lead):
            turn(p)
        rest = tok[len(lead):]
        later = re.findall(marker, rest)
        clean = re.sub(marker, "", rest)
        if clean:
            if GAP_OPEN in clean:
                gaps.add(len(tokens))
                clean = clean.replace(GAP_OPEN, "").replace(GAP_CLOSE, "")
            tokens.append(clean)
            page_of.append(page)
        for p in later:
            turn(p)
    if any(c in "".join(tokens) for c in (HYPH, PB_OPEN, PB_CLOSE, GAP_OPEN, GAP_CLOSE, SPLIT)):
        raise ValueError(f"TCP text: a marker left in {' '.join(tokens)[:80]!r}")
    return Block(kind, tokens, pages, page_of, gaps, n, mark)


# ------------------------------------------------------------ the check against a scan


# Letters that compare alike: the long s, which the TCP gives as "s" and OCR
# reads as "f", "l" or "ſ"; and "i"/"j" and "u"/"v", which old type does not
# tell apart where OCR dictionaries do ("Iudge" against "Judge").
ALIKE = str.maketrans({"ſ": "f", "s": "f", "l": "f", "j": "i", "v": "u"})


def fkey(tok: str) -> str:
    """A word's letters and figures, compared with the long s set aside (see
    `ALIKE`): "subject", "fubject" and "lubject" compare alike."""
    return key(tok.lower().translate(ALIKE))


SCAN_HYPHEN = re.compile(r"([A-Za-zſ]{2})[-­¬]\s*\n\s*([a-zſ])")


def scan_tokens(text: str) -> list[str]:
    """A scan's OCR text as words, rejoining words broken at a line end
    (OCR gives the hyphen as "-" or "¬")."""
    return SCAN_HYPHEN.sub(r"\1\2", text).split()


def printed_lines(obj: ET.Element) -> list[str]:
    """A DjVu page's words as printed lines: words whose boxes share most of
    their height are on one line; lines top to bottom, words left to right.
    Words outside the block of text (OCR reads the marbled edges and the
    binding of a photographed book as letters) are left out: the block is
    where nearly all the page's plainly printed words are."""
    words = []
    for w in obj.iter("WORD"):
        c = [int(v) for v in (w.get("coords") or "0,0,0,0").split(",")[:4]]
        x0, y_bottom, x1, y_top = c
        if (w.text or "").strip():
            words.append((min(y_top, y_bottom), max(y_top, y_bottom), x0, x1, w.text.strip()))
    plain_words = [w for w in words if re.fullmatch(r"[a-zſ]{3,}[,.;:]?", w[4])]
    if len(plain_words) >= 20:
        xs0, xs1 = sorted(w[2] for w in plain_words), sorted(w[3] for w in plain_words)
        ys = sorted(w[0] for w in plain_words)
        lo, hi = xs0[len(xs0) // 50], xs1[-1 - len(xs1) // 50]
        top, bottom = ys[len(ys) // 50], ys[-1 - len(ys) // 50]
        width, height = hi - lo, bottom - top
        words = [w for w in words if lo - 0.04 * width <= (w[2] + w[3]) / 2 <= hi + 0.04 * width
                 and top - 0.08 * height <= w[0] <= bottom + 0.08 * height]
    lines: list[list] = []  # [top, bottom, [(x, text)]]
    for top, bottom, x, _, text in sorted(words):
        for line in lines:
            overlap = min(bottom, line[1]) - max(top, line[0])
            if overlap > 0.5 * min(bottom - top, line[1] - line[0]):
                line[2].append((x, text))
                break
        else:
            lines.append([top, bottom, [(x, text)]])
    lines.sort(key=lambda l: (l[0] + l[1]) / 2)
    return [" ".join(text for _, text in sorted(l[2])) for l in lines]


class Scan(Reference):
    """A scan's words, with the scan page (leaf) each is on when read from
    its DjVu XML, searchable by position like a reference scan (`locate`),
    by their letters with the long s set aside."""

    def __init__(self, name: str, item: str | None, tokens: list[str], leaves: list[int | None]):
        self.name, self.item = name, item
        self.tokens, self.leaves = tokens, leaves
        self.keys = [fkey(t) for t in tokens]
        self.index: dict[tuple, list[int]] = {}
        for i in range(len(self.keys) - 3):
            k = tuple(self.keys[i:i + 4])
            if all(k):
                self.index.setdefault(k, []).append(i)

    @classmethod
    def from_xml(cls, name: str, item: str, source_id: str) -> "Scan":
        """Words in reading order: the page's words put into printed lines by
        where they stand (OCR sometimes reads the ends of lines as a block
        of their own), each line from left to right."""
        tokens: list[str] = []
        leaves: list[int | None] = []
        for leaf, obj in enumerate(ET.parse(raw_path(source_id)).getroot().iter("OBJECT"), 1):
            words = scan_tokens("\n".join(printed_lines(obj)))
            tokens += words
            leaves += [leaf] * len(words)
        return cls(name, item, tokens, leaves)

    @classmethod
    def from_text(cls, name: str, source_id: str) -> "Scan":
        words = scan_tokens(raw_path(source_id).read_bytes().decode("utf-8"))
        return cls(name, None, words, [None] * len(words))


@dataclass
class Reading:
    """A scan's reading of a TCP word: the scan's word (None where the scan
    could not be lined up there; "" where it has no word), and any words it
    has more just after it."""
    word: str | None
    extra: str = ""
    leaf: int | None = None


NEAR = 12  # words on each side of a word, to count it in the TCP and in a scan


def line_up(tokens: list[str], scan: Scan, hint: int) -> tuple[list[Reading], int]:
    """Each TCP word's reading in a scan, and where the scan's run ended.

    Words are lined up by their letters (`fkey`). Where the two differ, only
    a short difference between runs that agree is a reading of these words
    (elsewhere they are not at the same place). OCR sometimes reads the
    words of a line out of order, so a word the scan seems to lack counts as
    lacking only when the scan has it fewer times near there than the TCP,
    and a word it seems to have more only when the TCP has none like it
    near there."""
    out = [Reading(None) for _ in tokens]
    keys = [fkey(t) for t in tokens]
    start = scan.locate(keys, hint)
    if start is None:
        return out, hint
    end = min(len(scan.tokens), start + int(len(tokens) * 1.25) + 30)
    sm = SequenceMatcher(None, keys, scan.keys[start:end], autojunk=False)
    ops = sm.get_opcodes()
    if sum(i2 - i1 for op, i1, i2, _, _ in ops if op == "equal") < 0.5 * len(tokens):
        return out, hint  # not the same passage

    # Only a short difference between words that agree on both sides (four
    # or more of them, at least one on each side) is a reading of these
    # words; elsewhere the two are not at the same place, or the OCR lost
    # the words (a stain, a crease).
    def flank(n: int) -> int:
        if n < 0 or n >= len(ops):
            return 4  # the start or end of the block
        op, i1, i2, _, _ = ops[n]
        return i2 - i1 if op == "equal" else 0

    last = start
    for n, (op, i1, i2, j1, j2) in enumerate(ops):
        a, b = start + j1, start + j2
        if op == "equal":
            read_difference(op, tokens, keys, scan, out, i1, i2, a, b)
            last = b
            continue
        before, after = flank(n - 1), flank(n + 1)
        if min(before, after) < 1 or before + after < 4 or max(i2 - i1, j2 - j1) > 2:
            continue
        read_difference(op, tokens, keys, scan, out, i1, i2, a, b)
        last = b
    return out, last


def read_difference(op: str, tokens: list[str], keys: list[str], scan: "Scan", out: list[Reading],
                    i1: int, i2: int, a: int, b: int) -> None:
    """The scan's readings of TCP words i1..i2 from its words a..b."""
    def tcp_count(i: int, k: str) -> int:
        return keys[max(0, i - NEAR):i + NEAR + 1].count(k)

    def scan_count(j: int, k: str) -> int:
        return scan.keys[max(0, j - NEAR - 3):j + NEAR + 4].count(k)

    if op == "equal":
        for k in range(i2 - i1):
            out[i1 + k] = Reading(scan.tokens[a + k], leaf=scan.leaves[a + k])
        return
    lacking = list(range(i1, i2)) if op == "delete" else []
    spare = list(range(a, b)) if op == "insert" else []
    if op == "replace":
        pairs = pair_similar(tokens[i1:i2], scan.tokens[a:b])
        if not pairs and i2 - i1 == b - a <= 2:
            pairs = [([k], [k]) for k in range(i2 - i1)]  # word for word
        for ia, jb in pairs:
            words = [tokens[i1 + i] for i in ia]
            reading = " ".join(scan.tokens[a + j] for j in jb)
            if len(ia) > 1 and fkey("".join(words)) == fkey(reading):
                # The scan reads two words as one ("anew" for "a new"): they agree.
                for i in ia:
                    out[i1 + i] = Reading(tokens[i1 + i], leaf=scan.leaves[a + jb[0]])
                continue
            out[i1 + ia[0]] = Reading(reading, leaf=scan.leaves[a + jb[0]])
            for i in ia[1:]:
                out[i1 + i] = Reading(reading, leaf=scan.leaves[a + jb[0]])
        used_a = {i1 + i for ia, _ in pairs for i in ia}
        used_b = {a + j for _, jb in pairs for j in jb}
        lacking = [i for i in range(i1, i2) if i not in used_a]
        spare = [j for j in range(a, b) if j not in used_b]
    # Where the scan's words around the place are not cleanly read, the OCR
    # lost words there (a stain, a crease): that it lacks one says nothing.
    clear = all(plain(w) for w in scan.tokens[max(0, a - 3):b + 3])
    for i in lacking:
        found = scan_count(a, keys[i]) >= tcp_count(i, keys[i])
        out[i] = Reading(tokens[i] if found else "") if clear else Reading(None)
    for j in spare:
        if tcp_count(i1, scan.keys[j]):
            continue  # a word the TCP has near here, read out of order: not a word more
        at = max((i for i in range(i2) if out[i].word is not None), default=None)
        if at is not None:
            out[at].extra = " ".join(x for x in (out[at].extra, scan.tokens[j]) if x)


def is_word(k: str) -> bool:
    return bool(k) and k.isalpha()


# Letters OCR confuses in this type, where the TCP's reading is plainly the
# printed one: "be" for "he", "the" for "she" (the long s), "fall" for
# "shall" (the long s and h read as one letter).
CONFUSED = (("h", "b"), ("f", "t"), ("fh", "f"))


def confused(k: str, kr: str) -> bool:
    """True when a scan's word is the TCP's with one of OCR's confusions."""
    return any(k.replace(x, y, 1) == kr for x, y in CONFUSED if x in k)


def judge(word: str, readings: dict[str, Reading], known: set[str], clean: set[str], gap: bool) -> bool:
    """True when a TCP word is settled against the scans' readings (see the
    module's docstring). A scan's reading counts as another word only when
    it is cleanly printed (`ocr.plain`), a real word, and not a piece of the
    TCP's word (OCR's half of a word broken at a line end: "grants" for
    "emigrants"); a word a scan has more counts only when it is a word of
    the clean texts of three letters or more (OCR reads specks as "i", "a")."""
    if gap:
        return False
    k = fkey(word)
    seen = {name: r for name, r in readings.items() if r.word is not None}
    if not seen or not k:
        return True

    def another(r: str) -> bool:
        kr = fkey(r)
        return (plain(r) and is_word(kr) and kr in known and kr != k
                and SequenceMatcher(None, k, kr, autojunk=False).ratio() >= 0.5
                and not (len(kr) < len(k) and (k.startswith(kr) or k.endswith(kr)))
                and not confused(k, kr))

    if any(r.extra and all(plain(x) and x.lower() == x and len(fkey(x)) >= 3 and fkey(x) in clean
                           for x in r.extra.split()) for r in seen.values()):
        return False  # a scan has a real word more here
    if any(r.word and fkey(r.word) == k for r in seen.values()):
        return True
    if any(r.word == "" for r in seen.values()):
        return not any(c.isalnum() for c in word)  # a scan has no word where the TCP has one
    return not any(another(r.word) for r in seen.values())


def check(blocks: list[Block], scans: list[Scan], known: set[str], clean: set[str]) -> dict[int, tuple[list[dict], list[int]]]:
    """For each block (by its position), its uncertain spans (character
    offsets into its text, with the readings) and the scan pages its words
    were found on in the first scan (the one that gives page images)."""
    hints = {s.name: 0 for s in scans}
    out = {}
    for n, b in enumerate(blocks):
        per_scan = {}
        for s in scans:
            per_scan[s.name], hints[s.name] = line_up(b.tokens, s, hints[s.name])
        spans, at = [], 0
        for i, word in enumerate(b.tokens):
            rs = {name: per_scan[name][i] for name in per_scan}
            if not judge(word, rs, known, clean, i in b.gaps):
                readings = {"tcp": word}
                for name, r in rs.items():
                    if r.word is not None:
                        readings[name] = " ".join(x for x in (r.word, r.extra) if x)
                spans.append({"end": at + len(word), "readings": dict(sorted(readings.items())), "start": at})
            at += len(word) + 1
        leaves = sorted({r.leaf for r in per_scan[scans[0].name] if r.leaf} if scans else set())
        out[n] = (spans, leaves)
    return out


def page_leaves(blocks: list[Block], scan: Scan) -> dict[str, int]:
    """The scan page each printed page is on: the one most of the words the
    TCP gives that page were found on in the scan."""
    votes: dict[str, Counter] = {}
    hint = 0
    for b in blocks:
        readings, hint = line_up(b.tokens, scan, hint)
        for page, r in zip(b.page_of, readings):
            if page and r.leaf:
                votes.setdefault(page, Counter())[r.leaf] += 1
    return {p: c.most_common(1)[0][0] for p, c in votes.items()}


def leaves_for(b: Block, found: list[int], by_page: dict[str, int], previous: list[int]) -> list[int]:
    """A block's scan pages: those of its printed pages and those its words
    were found on (unless a stray match puts them far apart), or else the
    last page of the block before."""
    pages = {by_page[p] for p in b.pages if p in by_page}
    both = sorted(pages | set(found))
    if both and both[-1] - both[0] <= len(b.pages) + 1:
        return list(range(both[0], both[-1] + 1))
    return sorted(pages) or found or previous[-1:]


def vocabulary(clean: set[str], blocks: list[Block]) -> set[str]:
    """Real words, compared with the long s set aside: the clean texts'
    words and the TCP text's own."""
    return {fkey(w) for w in clean} | {k for b in blocks for t in b.tokens if is_word(k := fkey(t))}


# ------------------------------------------------------------ fetching

TCP_LICENSE = ("CC0 1.0 Universal (the TCP header's availability statement: \"This Phase I text is available for "
               "reuse, according to the terms of Creative Commons 0 1.0 Universal\")")
IA_LICENSE = "Public domain (a scan of a book printed before 1800, on the Internet Archive)"


def tcp_url(tcp_id: str, commit: str) -> str:
    return f"https://raw.githubusercontent.com/textcreationpartnership/{tcp_id}/{commit}/{tcp_id}.xml"


def ia_url(item: str, suffix: str) -> str:
    return f"https://archive.org/download/{item}/{item}{suffix}"


def fetch(sources: list[tuple[str, str, str, str, str]]) -> None:
    """Record raw sources (id, url, licence, notes, extension) not yet in the manifest."""
    from tools.common import load_manifest
    from tools.fetch import add_source
    have = {e["id"] for e in load_manifest()}
    for sid, url, licence, notes, ext in sources:
        if sid in have:
            continue
        add_source(sid, url, licence, notes, ext=ext)
        print(sid, flush=True)



# ------------------------------------------------------------ the pamphlets of the debate (decision 69)

# Evans-TCP texts read by importers/pamphlets.py (and N16599, a tie-breaker
# for importers/ratification.py): TCP number -> the commit pinned.
TEXTS = {
    "N16599": "fcace6de9e18b1b5b4c257bb17ad3d70e970b372",
    "N16431": "6fdb10c9ee94639d3c54564a1bafae5a533e2bf9",
    "N16481": "0ee6facbbd1dfcfbcdc156fd150a12fcbd380240",
    "N16378": "f3dfd68f63c10749115a0dec5c4150b749108dce",
    "N16445": "6fe82e912780c613d1a8b24311edfed92ffa49d2",
    "N16126": "3cdf2ac34efd8db4ed3383dda4b719957e022c56",
    "N16546": "6e7d414b83757497cad41e7eb0539cf482a1bb3a",
    "N16547": "81467b24a8ca827e8575564c5081f4ba830f1a55",
}
REPO_URL = "https://github.com/textcreationpartnership/{tcp}"


def source_id(tcp_id: str) -> str:
    """The manifest id of a TCP file: "tcp-n16599"."""
    return f"tcp-{tcp_id.lower()}"


@dataclass
class Division:
    part: str  # front | body | back
    type: str  # the TEI division's type
    el: ET.Element
    page: str | None  # the printed page it starts on

    def blocks(self) -> list[Block]:
        """Its own blocks (not those of divisions inside it), a letter's
        opening and closing read into their parts."""
        return Walker(self.page, letters=True).blocks(self.el, skip=("div",))

    def heads(self) -> list[str]:
        return [" ".join("".join(h.itertext()).split()) for h in self.el.findall(f"{TEI}head")]


def divisions(root: ET.Element) -> list[Division]:
    """Every division of the text (front matter, body, back matter), those
    inside others too, in document order, with the page each starts on."""
    out: list[Division] = []
    page: list[str | None] = [None]

    def walk(el: ET.Element, part: str) -> None:
        for child in el:
            t = tag(child)
            if t == "pb":
                page[0] = child.get("n") or None
            elif t == "div":
                out.append(Division(part, child.get("type", ""), child, page[0]))
                walk(child, part)
            else:
                for pb in child.iter(f"{TEI}pb"):
                    page[0] = pb.get("n") or None

    text = root.find(f"{TEI}text")
    for part in ("front", "body", "back"):
        if text.find(f"{TEI}{part}") is not None:
            walk(text.find(f"{TEI}{part}"), part)
    return out


def gap_spans(b: Block) -> list[dict]:
    """The words of a block holding something the keyers could not read, as
    uncertain spans of its text: the transcription's reading is the only one."""
    spans, at = [], 0
    for i, tok in enumerate(b.tokens):
        if i in b.gaps:
            spans.append({"end": at + len(tok), "readings": {"tcp": tok}, "start": at})
        at += len(tok) + 1
    return spans


def plain_words(b: Block) -> str:
    """A block's words for lining up with a scan's: the long s as s, an em
    dash apart from the words beside it, and a word holding a gap as "◊",
    which reads as no word."""
    words = ["◊" if i in b.gaps else tok.replace("ſ", "s") for i, tok in enumerate(b.tokens)]
    return re.sub(r"\s*—\s*", " — ", " ".join(words))


_REFERENCES: dict[tuple[str, str], Reference] = {}


def reference(source: str, heading: str) -> Reference:
    """The text of the division of a TCP file whose heading matches
    `heading` (a pattern), as a reference to line a scan's words up with
    (a tie-breaker; importers/ratification.py). Notes are left out (a
    scan's notes are read apart from its text)."""
    if (source, heading) not in _REFERENCES:
        found = [d for d in divisions(load(source)) if any(re.search(heading, h) for h in d.heads())]
        if len(found) != 1:
            raise ValueError(f"{source}: {len(found)} divisions headed {heading!r}")
        text = "\n".join(plain_words(b) for b in found[0].blocks() if b.kind != "note")
        _REFERENCES[(source, heading)] = Reference("tcp", text)
    return _REFERENCES[(source, heading)]


def readings(tokens: list[str], ref: Reference | None) -> list[str | None]:
    """The TCP's reading of each of a run of a scan's words (None where it
    has none, or cannot be read; "" where it reads this word together with
    the one before)."""
    from importers.ocr import align
    if ref is None or not tokens:
        return [None] * len(tokens)
    return [None if r is None or "◊" in r else r for r in (x.get("tcp") for x in align(tokens, [ref], {}))]


def fetch_texts() -> None:
    """Record the pamphlets' TCP files, at their pinned commits, as raw sources."""
    fetch([(source_id(t), tcp_url(t, c), TCP_LICENSE,
            f"Evans-TCP {t} (github.com/textcreationpartnership/{t}, commit {c}): the Text Creation "
            "Partnership's typed transcription, TEI P5 XML.", ".xml") for t, c in TEXTS.items()])


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["fetch"]:
        fetch_texts()
