"""Ref permanence: refs.lock lists every published ref.

    python -m tools.refs lock     # add every current ref to refs.lock

The lock is append-only: this tool never removes a ref. `make verify`
fails if any locked ref no longer exists in texts/ or cases/, because
published refs are never renumbered or dropped (CLAUDE.md rule 6). A
ref retired by a correction (two passages that were one, joined after a
decision in docs/decisions.md) stays in the lock: its work lists it under
`retired` with the passage it was merged into, which must exist, and the
site keeps its URL pointing there. Its number is never reused.
"""

from __future__ import annotations

import sys

from tools.common import ROOT
from tools.corpus import Corpus, load_corpus

LOCK_PATH = ROOT / "refs.lock"
HEADER = (
    "# Published refs. Append-only: never remove or renumber a ref (CLAUDE.md rule 6).\n"
    "# Add new refs with: python -m tools.refs lock\n"
)


def read_lock() -> set[str]:
    if not LOCK_PATH.exists():
        return set()
    lines = LOCK_PATH.read_text(encoding="utf-8").splitlines()
    return {l.strip() for l in lines if l.strip() and not l.startswith("#")}


def current_refs(corpus: Corpus) -> set[str]:
    return set(corpus.segments) | set(corpus.divisions)


def missing_locked(corpus: Corpus) -> list[str]:
    have = current_refs(corpus)
    have |= {r for r, into in corpus.retired.items() if into in have and r not in have}
    return sorted(r for r in read_lock() if r not in have)


def lock() -> int:
    corpus = load_corpus()
    old = read_lock()
    new = old | current_refs(corpus)
    LOCK_PATH.write_text(HEADER + "".join(f"{r}\n" for r in sorted(new)), encoding="utf-8")
    print(f"refs.lock: {len(new)} refs ({len(new) - len(old)} added)")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] != ["lock"]:
        print(__doc__)
        sys.exit(2)
    sys.exit(lock())
