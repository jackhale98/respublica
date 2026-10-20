"""Corrections of words read from scans, made by a person against the page
image (CLAUDE.md, rule 3; decision 48).

A word the scans could not settle is marked uncertain in its passage, with
every scan's reading. On the errata page (`/errata/`) a maintainer compares
it with the page image and records what is printed; the review workflow
writes the decision to `corrections/{work}.jsonl` under their GitHub login
(`python -m tools.errata apply`). Importers apply the corrections when they
build a passage (`apply`): the word is replaced, its uncertain mark removed,
and the change recorded in the passage's `corrected` list, so the text stays
exactly what the importers produce from the raw files and the corrections.

A correction names the passage, the uncertain word as printed now (`was`)
and its place among the passage's uncertain words (`index`), and what the
page shows (`now`; the same as `was` confirms the reading). One that no
longer matches its passage (the scans were read again, say) stops the
import: a person must look at it again.

A correction with `"source": "library"` is the Anti-Federalist Library's
reading, accepted by the project owner in bulk without a check against the
page image (`python -m tools.errata accept-library`; decision 56). Its word
replaces the scans' word in the text, but the word stays among the
passage's uncertain words, marked `accepted`, so that it is still shown
as unchecked and a person can confirm or overrule it on the errata page;
their decision (on the word as it then reads) replaces the Library's.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CORRECTIONS_DIR = Path(__file__).resolve().parent.parent / "corrections"
FIELDS = ("at", "by", "index", "now", "ref", "was")


class CorrectionError(RuntimeError):
    pass


@lru_cache(maxsize=None)
def _by_ref(directory: str = str(CORRECTIONS_DIR)) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in sorted(Path(directory).glob("*.jsonl")):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            c = json.loads(line)
            missing = [k for k in FIELDS if k not in c]
            if missing:
                raise CorrectionError(f"{f.name}:{n}: missing {missing}")
            out.setdefault(c["ref"], []).append(c)
    return out


def for_ref(ref: str) -> list[dict]:
    return _by_ref().get(ref, [])


def apply(ref: str, text: str, spans: list[dict]) -> tuple[str, list[dict], list[dict]]:
    """A passage's text and uncertain spans with its corrections applied;
    returns (text, spans left uncertain, corrections as applied with their
    place in the new text). The latest decision on a word wins; a person's
    decision always wins over the Library's."""
    def place(c: dict, words: list[str]) -> int:
        k = c["index"]
        if not (0 <= k < len(words)) or words[k] != c["was"]:
            # The word may have moved among the uncertain words; it must still be there, once.
            found = [i for i, w in enumerate(words) if w == c["was"]]
            if len(found) != 1:
                raise CorrectionError(f"{ref}: the correction of {c['was']!r} (by {c['by']}, {c['at']}) "
                                      "no longer matches an uncertain word of the passage")
            k = found[0]
        return k

    lines = for_ref(ref)
    if not lines:
        return text, spans, []
    words = [text[s["start"]:s["end"]] for s in spans]
    accepted: dict[int, dict] = {}
    for c in lines:
        if c.get("source") == "library":
            accepted[place(c, words)] = c
    # A person's decision names the word as the reader then shows it.
    current = [accepted[i]["now"] if i in accepted else w for i, w in enumerate(words)]
    decisions: dict[int, dict] = {}
    for c in lines:
        if c.get("source") != "library":
            decisions[place(c, current)] = c
    out, kept, applied, at, shift = [], [], [], 0, 0
    for i, s in enumerate(spans):
        c, lib = decisions.get(i), accepted.get(i)
        if c is None and lib is None:
            kept.append({**s, "end": s["end"] + shift, "start": s["start"] + shift})
            continue
        now = (c or lib)["now"]
        out.append(text[at:s["start"]])
        start = s["start"] + shift
        out.append(now)
        if c is None:
            span = {k: v for k, v in s.items() if k not in ("suggestion", "suggested_by")}
            kept.append({**span, "accepted": {"at": lib["at"], "by": lib["by"], "source": "library"},
                         "end": start + len(now), "start": start})
        else:
            applied.append({"at": c["at"], "by": c["by"], "end": start + len(now), "start": start, "was": words[i]})
        shift += len(now) - (s["end"] - s["start"])
        at = s["end"]
    out.append(text[at:])
    return "".join(out), kept, applied
