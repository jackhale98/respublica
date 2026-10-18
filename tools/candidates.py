"""Find candidate links for a linker to judge (docs/linking.md).

    python -m tools.candidates --paper 10        # one Federalist paper
    python -m tools.candidates --ref Cato.3      # any essay, work or passage

Three signals, all from code:
  * overlap: a run of words a passage shares with a clause of the
    Constitution or a paragraph of the Declaration of Independence
    (case-insensitive) that contains enough distinctive words (outside the
    300 most common in The Federalist) to suggest a quotation;
  * structural: wording such as "the second section of the first article",
    which a linker must resolve by reading the paragraph (it may refer to the
    Articles of Confederation, not the Constitution);
  * mention: the name of another writer or series in the library ("Cato",
    "the Federal Farmer", "Publius", "Mr. Martin"), with the series it may
    point to and its dates, for possible `responds_to`, `cites` or `quotes`
    links between essays.

Candidates are hints. Only a linker's judgment, recorded with a rationale
through `python -m tools.links propose`, makes a suggested link.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher

from tools.corpus import Corpus, load_corpus

WORD = re.compile(r"[A-Za-z0-9]+")
CLAUSE_REF = re.compile(r"^(?:Constitution\.(\d+\.\d+(\.\d+)?|Preamble)|Declaration\.\d+)$")
# With --amendments: the amendments' sections and the articles of the Joint
# Resolution of 1789 (the debates in Congress, docs/linking.md run 4).
AMENDMENT_REF = re.compile(r"^(?:Amendment\.\d+\.\d+|Resolution1789\.Article\.\d+)$")
# Names that point at a writer or series in the library -> its ref prefix.
# Ambiguous ones ("Caution", "Remarks") are left out; a linker reads the text.
MENTIONS = [
    (re.compile(r"\b(?:Cato|CATO)\b"), "Cato"),
    (re.compile(r"\bC(?:ae|æ|Æ|AE)sar\b", re.I), "Caesar"),
    (re.compile(r"\bCentinel\b", re.I), "Centinel"),
    (re.compile(r"\bAgrippa\b", re.I), "Agrippa"),
    (re.compile(r"\b(?:Brutus|BRUTUS)\b"), "Brutus"),
    (re.compile(r"\bFederal\s+Farmer\b", re.I), "FederalFarmer"),
    (re.compile(r"\bLand-?holder\b", re.I), "Landholder"),
    (re.compile(r"\b(?:Cassius|CASSIUS)\b"), "Cassius"),
    (re.compile(r"\b(?:Sydney|SYDNEY)\b"), "Sydney"),
    (re.compile(r"\b(?:Countryman|COUNTRYMAN)\b"), "Countryman"),
    (re.compile(r"\bCitizen of New[- ]Haven\b", re.I), "CitizenOfNewHaven"),
    (re.compile(r"\bPlain\s+Dealer\b", re.I), "PlainDealer"),
    (re.compile(r"\bFriend to the Constitution\b", re.I), "FriendToTheConstitution"),
    (re.compile(r"\b(?:Luther\s+)?Martin\b"), "LutherMartin"),
    (re.compile(r"\bGerry\b"), "GerryReply"),
    (re.compile(r"\b(?:Publius|PUBLIUS|Federalist|FEDERALIST)\b"), "Federalist"),
    (re.compile(r"\bDeclaration of Independence\b", re.I), "Declaration"),
]
ORDINAL = r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|last|\d+(?:st|nd|rd|th)?)"
STRUCTURAL = re.compile(
    rf"\b(?:{ORDINAL}(?:\s+and\s+{ORDINAL})?\s+(?:clauses?|sections?|articles?|paragraphs?)\b"
    rf"(?:,?\s+(?:but one\s+)?(?:in|of)\s+the\s+(?:{ORDINAL}|same)\s+(?:sections?|articles?))*)",
    re.I,
)
N = 4  # n-gram size for the prefilter
COMMON = 300  # this many most frequent Federalist words are not distinctive


def tokens(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0).lower(), m.start(), m.end()) for m in WORD.finditer(text)]


def in_quotes(text: str, start: int) -> bool:
    before = text[:start]
    return before.count("“") > before.count("”") or before.count('"') % 2 == 1


def clause_segments(corpus: Corpus, amendments: bool = False) -> dict[str, dict]:
    return {r: s for r, s in corpus.segments.items()
            if CLAUSE_REF.match(r) or (amendments and AMENDMENT_REF.match(r))}


def ngram_index(clauses: dict[str, dict]) -> tuple[dict[tuple, set[str]], dict[str, list]]:
    index: dict[tuple, set[str]] = {}
    toks = {}
    for ref, seg in clauses.items():
        t = tokens(seg["text"])
        toks[ref] = t
        words = [w for w, _, _ in t]
        for i in range(len(words) - N + 1):
            index.setdefault(tuple(words[i:i + N]), set()).add(ref)
    return index, toks


def common_words(corpus: Corpus) -> set[str]:
    freq = Counter(w for r, s in corpus.segments.items() if r.startswith("Federalist.")
                   for w, _, _ in tokens(s["text"]))
    return {w for w, _ in freq.most_common(COMMON)}


def overlaps(seg: dict, index: dict, clause_toks: dict, common: set[str], min_len: int = 4) -> list[dict]:
    text = seg["text"]
    t = tokens(text)
    words = [w for w, _, _ in t]
    hits: dict[str, None] = {}
    for i in range(len(words) - N + 1):
        for ref in index.get(tuple(words[i:i + N]), ()):
            hits[ref] = None
    out = []
    for ref in hits:
        ct = clause_toks[ref]
        cwords = [w for w, _, _ in ct]
        sm = SequenceMatcher(None, words, cwords, autojunk=False)
        for b in sm.get_matching_blocks():
            if b.size < min_len:
                continue
            distinctive = len({w for w in words[b.a:b.a + b.size] if w not in common})
            quoted = in_quotes(text, t[b.a][1])
            if not (distinctive >= 3 or (distinctive >= 2 and quoted) or b.size >= 10):
                continue
            out.append({
                "from": seg["ref"],
                "from_text": text[t[b.a][1]:t[b.a + b.size - 1][2]],
                "in_quotes": quoted,
                "kind": "overlap",
                "to": ref,
                "to_text": clause_toks_text(ref, ct, b.b, b.size),
                "distinctive_words": distinctive,
                "words": b.size,
            })
    return out


_clause_text: dict[str, str] = {}


def clause_toks_text(ref: str, ct: list, start: int, size: int) -> str:
    text = _clause_text[ref]
    return text[ct[start][1]:ct[start + size - 1][2]]


def structural(seg: dict) -> list[dict]:
    out = []
    for m in STRUCTURAL.finditer(seg["text"]):
        context = seg["text"][max(0, m.start() - 80):m.end() + 120]
        out.append({"from": seg["ref"], "kind": "structural", "mention": m.group(0), "context": context})
    return out


def mentions(corpus: Corpus, seg: dict) -> list[dict]:
    """Names of other writers or series in the passage, with where they are."""
    own = seg["ref"].split(".")[0]
    out = []
    for pattern, prefix in MENTIONS:
        if prefix == own:
            continue
        found = list(pattern.finditer(seg["text"]))
        if found:  # one candidate per series per passage, with the first mention
            m = found[0]
            work = next((d for d in corpus.works.values() if d.get("ref_prefix") == prefix), None)
            out.append({
                "count": len(found),
                "context": seg["text"][max(0, m.start() - 120):m.end() + 160],
                "from": seg["ref"],
                "in_library": work is not None,
                "kind": "mention",
                "mention": m.group(0),
                "series": prefix,
                "series_dates": work.get("date") if work else None,
            })
    return out


def candidates_for_paper(corpus: Corpus, paper: int) -> list[dict]:
    return candidates_for(corpus, f"Federalist.{paper}")


def candidates_for(corpus: Corpus, ref: str, amendments: bool = False) -> list[dict]:
    """Candidates for every passage under `ref` (an essay, a work, a passage);
    with `amendments`, overlaps with the amendments are looked for too."""
    clauses = clause_segments(corpus, amendments)
    _clause_text.update({r: s["text"] for r, s in clauses.items()})
    index, ctoks = ngram_index(clauses)
    common = common_words(corpus)
    out: list[dict] = []
    for r, seg in corpus.segments.items():
        if r == ref or r.startswith(ref + "."):
            out.extend(overlaps(seg, index, ctoks, common))
            out.extend(structural(seg))
            out.extend(mentions(corpus, seg))
    # Keep the longest overlap per (paragraph, clause).
    best: dict[tuple, dict] = {}
    rest = []
    for c in out:
        if c["kind"] != "overlap":
            rest.append(c)
            continue
        k = (c["from"], c["to"])
        if k not in best or c["words"] > best[k]["words"]:
            best[k] = c
    return sorted(best.values(), key=lambda c: (c["from"], -c["words"])) + rest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m tools.candidates")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--paper", type=int, help="a Federalist paper number")
    g.add_argument("--ref", help="any essay, work or passage ref (Cato.3, Caution, Federalist.67)")
    p.add_argument("--amendments", action="store_true",
                   help="also look for overlaps with the amendments and the Joint Resolution of 1789")
    args = p.parse_args(argv)
    corpus = load_corpus()
    found = (candidates_for_paper(corpus, args.paper) if args.paper
             else candidates_for(corpus, args.ref, args.amendments))
    print(json.dumps(found, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
