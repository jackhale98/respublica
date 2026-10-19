"""What a correction or a link review touches, for the errata and link-review
workflows (decision 65), from importers/outputs.json.

    python -m tools.scope --works brutus,patrick-henry
        importers=ratification,elliot        (to re-run)
        families=globe,usrep                 (CI caches to restore)
    python -m tools.scope --check --importers ratification,elliot [--allow corrections,links]
        exit 1, naming them, if anything changed outside those importers'
        outputs and the allowed directories (the workflow's guard: with it, the
        narrower reproducibility check sees every file that could have changed)
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

from importers.__main__ import load_map
from tools.common import ROOT, UNTRACKED_FAMILIES, load_manifest


def importers_for(works: list[str]) -> list[str]:
    files = {f"texts/{w}.json" for w in works} | {f"cases/{w}.json" for w in works}
    return [name for name, entry in load_map().items() if files & set(entry["outputs"])]


def raw_for(importers: list[str]) -> list[str]:
    m = load_map()
    return sorted({r for name in importers for r in m.get(name, {}).get("raw", [])})


def families_for(raw: list[str]) -> list[str]:
    paths = {e["id"]: Path(e["path"]).name for e in load_manifest()}
    return sorted({fam for r in raw for fam, pat in UNTRACKED_FAMILIES.items() if fnmatch.fnmatch(paths.get(r, ""), pat)})


def changed() -> list[str]:
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [line[3:].split(" -> ")[-1] for line in out.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.scope")
    ap.add_argument("--works", help="comma-separated work ids a correction touches")
    ap.add_argument("--check", action="store_true", help="fail if anything changed outside the scope")
    ap.add_argument("--importers", default="", help="with --check: the importers that were re-run")
    ap.add_argument("--allow", default="", help="with --check: comma-separated directories that may change")
    args = ap.parse_args(argv)
    if args.check:
        chosen = [n for n in args.importers.split(",") if n]
        m = load_map()
        allowed = {o for n in chosen for o in m.get(n, {}).get("outputs", [])}
        dirs = tuple(d.rstrip("/") + "/" for d in args.allow.split(",") if d)
        outside = [p for p in changed() if p not in allowed and not p.startswith(dirs)]
        for p in outside:
            print(f"changed outside the scope of this review: {p}", file=sys.stderr)
        return 1 if outside else 0
    works = [w for w in (args.works or "").split(",") if w]
    importers = importers_for(works)
    raw = raw_for(importers)
    print(f"importers={','.join(importers)}")
    print(f"families={','.join(families_for(raw))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
