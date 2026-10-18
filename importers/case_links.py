"""Links from the first set of cases, imported from the Constitution Annotated.

    python -m importers.case_links      # writes links/proposed/conan-*.jsonl

Two kinds, written by code as `import` links that cite their source and
proposed like any other link (status "suggested"; a person reviews them):

- `interprets`, case -> clause: the Constitution Annotated's essays on the
  clause cite the case on at least MIN_PAGES printed pages (decision 46).
  The source names the essays and pages. This records where the essays
  cite the case, never what the case held (rule 7).
- `overrules`, case -> case: a row of the Constitution Annotated's Table of
  Supreme Court Decisions Overruled by Subsequent Decisions, where both
  decisions are in the library. The source names the table and its page.

Running it again rewrites both files from the sources; a link that was
already there keeps its id and created_at.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections import defaultdict

from importers import conan, courtlistener
from tools.common import LINKS_DIR, read_jsonl
from tools.corpus import load_corpus

MIN_PAGES = 2
HIGH_PAGES = 4   # cited on this many pages of a clause's essays: high confidence
EDITION = "Constitution of the United States of America: Analysis and Interpretation (2022 ed.)"
RUN = "conan-2022-case-links"


def _pages_text(pages: list[int]) -> str:
    return ("p. " if len(pages) == 1 else "pp. ") + ", ".join(str(p) for p in pages)


def _slug(ref: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", ref.lower()).strip("_")


def build() -> dict[str, list[dict]]:
    corpus = load_corpus()
    refs = set(corpus.segments) | set(corpus.divisions) | corpus.prefixes
    pages = conan.essay_pages()
    cases = conan.table_of_cases()
    rows = conan.overruled()
    chosen = conan.first_set()
    responses = courtlistener.recorded()
    cluster = {k: courtlistener.match(k, c.name, responses).cluster["id"] for k, c in chosen.items()}

    # interprets: clause -> the pages (and essays) of its essays that cite each case
    cited: dict[str, set[int]] = defaultdict(set)
    for c in cases:
        if c.supreme_court:
            key = conan.case_keys(c.citation)[0]
            if key in chosen:
                cited[key] |= set(c.pages)
    interprets = []
    for key in sorted(cited, key=lambda k: cluster[k]):
        by_clause: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
        for p in sorted(cited[key]):
            for essay in pages.get(p, []):
                clause = conan.clause_ref(essay, refs)
                if clause:
                    by_clause[clause][p].add(essay)
        for clause, at in sorted(by_clause.items()):
            if len(at) < MIN_PAGES:
                continue
            essays = sorted({e for es in at.values() for e in es})
            interprets.append({
                "confidence": "high" if len(at) >= HIGH_PAGES else "medium",
                "from": f"Case.{cluster[key]}",
                "id": f"lnk_conan_{cluster[key]}_{_slug(clause)}",
                "rationale": f"The Constitution Annotated's essays on this provision cite the case on {len(at)} pages.",
                "source": f"{EDITION}, essays {', '.join(essays)}, {_pages_text(sorted(at))}.",
                "to": clause,
                "type": "interprets",
            })

    # overrules: rows of the table where both decisions are in the library
    names = {conan.name_key(c.name): k for k, c in chosen.items()}
    overrules = []
    for row in rows:
        by = conan.overruling_key(row, set(chosen), names)
        if not by:
            continue
        for text, _ in row.overruled:
            for key in conan.case_keys(text):
                if key in chosen and key != by:
                    overrules.append({
                        "confidence": "high",
                        "from": f"Case.{cluster[by]}",
                        "id": f"lnk_conan_overrules_{cluster[by]}_{cluster[key]}",
                        "rationale": "The Constitution Annotated's table of decisions overruled by subsequent "
                                     "decisions lists this decision as overruled by the other.",
                        "source": f"{EDITION}, Table of Supreme Court Decisions Overruled by Subsequent Decisions, "
                                  f"p. {row.page}: {row.overruling.rstrip(';')} — {text.rstrip(';')}.",
                        "to": f"Case.{cluster[key]}",
                        "type": "overrules",
                    })
    return {"conan-interprets": interprets, "conan-overrules": overrules}


def write(batches: dict[str, list[dict]]) -> None:
    today = dt.date.today().isoformat()
    for name, links in batches.items():
        path = LINKS_DIR / "proposed" / f"{name}.jsonl"
        before = {r["id"]: r for _, r in read_jsonl(path)} if path.exists() else {}
        # A link a person has already reviewed or rejected lives in another file; never propose it again.
        decided = {r["id"] for f in LINKS_DIR.rglob("*.jsonl") if f != path for _, r in read_jsonl(f)}
        seen = set()
        lines = []
        for link in links:
            if link["id"] in seen:
                raise ValueError(f"duplicate link id {link['id']}")
            seen.add(link["id"])
            if link["id"] in decided:
                continue
            link |= {
                "created_at": before.get(link["id"], {}).get("created_at", today),
                "created_by": {"kind": "import", "run": RUN},
                "reviewed_by": None,
                "status": "suggested",
            }
            lines.append(json.dumps(link, sort_keys=True, ensure_ascii=False))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(lines)} links to {path}")


if __name__ == "__main__":
    write(build())
