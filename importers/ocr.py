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
    folio: str | None = None  # printed page number, when found


def parse_djvu_xml(path: Path) -> list[Page]:
    """Pages from an Internet Archive DjVu XML file, in scan order."""
    pages: list[Page] = []
    for _, obj in ET.iterparse(path, events=("end",)):
        if obj.tag != "OBJECT":
            continue
        page = Page(leaf=len(pages) + 1, width=int(obj.get("width", 0)), height=int(obj.get("height", 0)))
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
        pages.append(page)
        obj.clear()
    return pages


FOLIO = re.compile(r"^\(?\s*([0-9ivxlcdm]{1,4})\s*\)?$", re.I)


def classify(pages: list[Page]) -> None:
    """Mark running heads, folios and footnotes on each page (in place)."""
    for page in pages:
        if not page.paras:
            continue
        top = page.paras[0]
        # Running head: the first line on the page, short, holding a page number.
        first_line = top.lines[0].text
        if len(top.lines) == 1 and len(first_line.split()) <= 9 and re.search(r"\b\d{1,4}\b", first_line):
            top.kind = "head"
            m = re.search(r"(?:^|\s)(\d{1,4})(?:\s|$)", first_line)
            page.folio = m.group(1) if m else None
        # Folio at the foot: "( 247 )" or "247".
        for para in page.paras[-2:]:
            if len(para.lines) == 1 and FOLIO.match(para.text.replace(" ", "")):
                para.kind = "folio"
                page.folio = page.folio or FOLIO.match(para.text.replace(" ", "")).group(1)
        # Footnotes: smaller type at the foot of the page, after the last body
        # paragraph ("smaller" against the page's own text, since scans of
        # different pages differ in scale).
        heights = [w.height for para in page.paras if para.kind == "text" for w in para.words if w.height > 0]
        body_h = statistics.median(heights) if heights else 0
        for para in reversed(page.paras):
            if para.kind != "text":
                continue
            hs = [w.height for w in para.words if w.height > 0]
            if hs and body_h and statistics.median(hs) < 0.85 * body_h and para.lines[0].words[0].y0 > page.height * 0.5:
                para.kind = "note"
            else:
                break


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


def blocks(pages: list[Page], first_leaf: int = 1, last_leaf: int | None = None) -> list[Block]:
    """Paragraphs of text and notes in reading order between two scan pages,
    with paragraphs split by a page break rejoined."""
    out: list[Block] = []
    last_text: Block | None = None
    for page in pages:
        if page.leaf < first_leaf or (last_leaf and page.leaf > last_leaf):
            continue
        margin = body_margin(page)
        first_on_page = True
        for para in page.paras:
            if para.kind in ("head", "folio"):
                continue
            text = lines_to_text(para.lines)
            if not text:
                continue
            if para.kind == "note":
                out.append(Block(text, [page.leaf], [page.folio] if page.folio else [], "note"))
                continue
            indented = para.lines[0].x0 > margin + max(20, page.width * 0.012)
            if first_on_page and last_text is not None and not indented and not _is_heading(para, margin, page):
                last_text.text = join_across(last_text.text, text)
                last_text.leaves.append(page.leaf)
                if page.folio:
                    last_text.folios.append(page.folio)
            else:
                last_text = Block(text, [page.leaf], [page.folio] if page.folio else [], "text", indented)
                out.append(last_text)
            first_on_page = False
    return out


def _is_heading(para: Para, margin: int, page: Page) -> bool:
    """Centered short lines (titles, essay headings) never continue a paragraph."""
    if len(para.lines) > 2:
        return False
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
        """Start offset of a run of keys in this stream (first 4-gram that
        occurs once), searching forward from `hint` first."""
        for i in range(0, max(1, len(keys) - 3)):
            k = tuple(keys[i:i + 4])
            hits = [h for h in self.index.get(k, []) if h >= hint - 50] or self.index.get(k, [])
            if len(hits) == 1 or (hits and hits[0] >= hint - 50):
                return max(0, hits[0] - i)
        return None


@dataclass
class Uncertain:
    start: int  # token index in the paragraph
    end: int
    readings: dict[str, str]


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
        window_end = min(len(ref.tokens), start + int(len(tokens) * 1.25) + 20)
        sm = SequenceMatcher(None, keys, ref.keys[start:window_end], autojunk=False)
        last = start
        ops = sm.get_opcodes()
        for n, (op, i1, i2, j1, j2) in enumerate(ops):
            # Words that differ are paired only when their letters are mostly
            # alike, or when one or two words differ between runs of at least
            # two words that agree: elsewhere a run of different words, side
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
    """True when opcode n lies between two runs of at least two equal words
    (or the start or end of the paragraph)."""
    def agrees(m: int) -> bool:
        if m < 0 or m >= len(ops):
            return True
        op, i1, i2, _, _ = ops[m]
        return op == "equal" and i2 - i1 >= 2
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


def consensus(readings: list[dict[str, str]], known: set[str]) -> tuple[list[str], list[Uncertain]]:
    """Vote on each word (see `vote`); return the words and the unsettled ones.

    Where a scan read two of the primary's tokens as one word (a reading of
    "" on the second), the tokens are voted on together, as one reading per
    scan, so the choice between "coinni unity" and "community" is made once."""
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
        if not settled and len(group) > 1:
            # No agreement on the run as a whole: vote word by word among the
            # scans that read it word by word.
            split = [{s: v for s, v in r.items() if all(x.get(s) for x in group)} for r in group]
            votes = [vote(r, known) for r in split]
            if all(ok for _, ok in votes):
                word, settled = " ".join(w for w, _ in votes), True
        out.append(word)
        if not settled:
            uncertain.append(Uncertain(len(out) - 1, len(out), joint))
        i = end
    return out, uncertain


# A word as printed: letters, with an inner apostrophe or hyphen, and
# ordinary punctuation before or after.
PLAIN = re.compile(r"^[(\"'\[‘“]*[A-Za-z]+(?:['’-][A-Za-z]+)*[.,;:!?'\")\]’”]*$")


def plain(tok: str) -> bool:
    """A cleanly printed word: PLAIN, with brackets that open and close."""
    return bool(PLAIN.match(tok)) and tok.count("(") == tok.count(")") and tok.count("[") == tok.count("]")

STRAY = re.compile(r"[\\^|*~_{}<>]|([,.;:!?'\"])\1")


def vote(readings: dict[str, str], known: set[str]) -> tuple[str, bool]:
    """Choose among scans' readings of one word. Returns (reading, settled).

    Readings are grouped by their letters and digits. The group most scans
    agree on wins; on a tie, a group whose letters form a known word beats one
    that does not; otherwise the primary scan's group is kept, unsettled.
    Within the winning group (same letters, possibly different marks), the
    primary's reading is used unless it has stray marks another reading lacks.

    A known word cleanly printed in the primary (see PLAIN) is never
    replaced by a reading that is not a known word (two scans agreeing on
    "CATO. serted" for "asserted" have picked up a running head). Three
    cases stay unsettled whatever the count:
      * the primary cleanly reads a known word and the others another known
        word ("friends" against "citizens"): a real word is never silently
        replaced by a different one (but ")our" is not clean, so "your"
        wins);
      * figures the scans read differently ("S181" against "2181"): the
        scans share confusions such as 2/S and 1/i, so a majority of them
        can be wrong about a number;
      * a word only the primary scan has (no other scan aligned there) that
        is not a known word: nothing corroborates it.
    """
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
        if len(groups[a]) == len(groups[b]) and (a in known) == (b in known):
            settled = False
            top = pk
        elif any(c.isdigit() for c in top) or (top != pk and pk in known and top in known
                                                and plain(readings["primary"])):
            settled = False
            top = pk
    elif len(readings) == 1 and pk and pk not in known:
        settled = False
    candidates = groups[top]
    clean = [r for r in candidates if not STRAY.search(r)]
    return (clean[0] if clean else candidates[0]), settled


def known_words(clean: list[str]) -> set[str]:
    """Vocabulary of clean (non-OCR) texts.

    OCR output cannot vouch for itself: a misreading repeats on every page in
    one scan (a ligature read the same wrong way), and scans of different
    copies made with the same OCR engine share such misreadings. So only clean
    texts count; a rare word missing from them is flagged rather than guessed.
    """
    return {k for text in clean for t in TOKEN.findall(text) if is_word(k := key(t))}
