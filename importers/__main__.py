"""Run the importers.

    python -m importers                     # every importer, in order; also writes importers/outputs.json
    python -m importers --only ratification,elliot   # just these (the errata workflow)

Each importer runs in a process of its own, which records the raw sources it
reads (tools.common.raw_path). `importers/outputs.json` maps each importer to
the files it writes and the raw sources it reads, so the errata workflow can
fetch and re-run only what a correction touches; the full `make verify` on
main checks that the map is still right (decision 65).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.common import ROOT

MAP_PATH = ROOT / "importers" / "outputs.json"


def run_in_process(name: str, out_dir: Path | None) -> dict:
    """Run one importer here, recording what it reads and writes."""
    import importlib

    from tools import common
    module = importlib.import_module(f"importers.{name}")
    common.RAW_READ = set()
    paths = module.run(out_dir) if out_dir else module.run()
    final = getattr(module, "OUT_DIR", common.TEXTS_DIR)
    return {"outputs": sorted(f"{final.name}/{p.name}" for p in paths), "raw": sorted(common.RAW_READ)}


def run_separately(name: str, out_dir: Path | None = None) -> dict:
    """Run one importer in a fresh process (so caches shared between importers
    cannot hide a raw source one of them reads)."""
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        cmd = [sys.executable, "-m", "importers", "--one", name, "--report", str(report)]
        if out_dir:
            cmd += ["--out", str(out_dir)]
        subprocess.run(cmd, check=True, cwd=ROOT)
        return json.loads(report.read_text(encoding="utf-8"))


def names() -> list[str]:
    from importers import IMPORTERS
    return [m.__name__.split(".")[-1] for m in IMPORTERS]


def write_map(found: dict[str, dict]) -> None:
    MAP_PATH.write_text(json.dumps(found, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_map() -> dict[str, dict]:
    return json.loads(MAP_PATH.read_text(encoding="utf-8")) if MAP_PATH.exists() else {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m importers")
    ap.add_argument("--only", help="comma-separated importers to run (default: all, and rewrite the map)")
    ap.add_argument("--one", help=argparse.SUPPRESS)
    ap.add_argument("--out", help=argparse.SUPPRESS)
    ap.add_argument("--report", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.one:
        found = run_in_process(args.one, Path(args.out) if args.out else None)
        Path(args.report).write_text(json.dumps(found), encoding="utf-8")
        return 0
    known = names()
    chosen = [n for n in (args.only or "").split(",") if n] if args.only is not None else known
    unknown = [n for n in chosen if n not in known]
    if unknown:
        print(f"unknown importer(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    found = {}
    for name in known:  # always in the importers' order
        if name not in chosen:
            continue
        found[name] = run_separately(name)
        for out in found[name]["outputs"]:
            print(f"importers.{name}: wrote {out}")
    if args.only is None:
        write_map(found)
    return 0


if __name__ == "__main__":
    sys.exit(main())
