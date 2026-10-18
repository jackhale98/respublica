"""Download raw source files and keep sources/manifest.json in step.

    python -m tools.fetch              # restore any raw file that is missing
    python -m tools.fetch add --id ID --url URL --license TEXT [--notes TEXT] [--ext .html]

`add` downloads a new original once and records its URL, retrieval date,
sha256 and license. The plain form re-downloads only files that are
missing locally and refuses to keep them if the checksum no longer
matches the manifest (the upstream copy changed; a human must decide
whether to record a new source).

Raw files are never edited after download.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import urllib.parse
from pathlib import Path

from tools.common import (
    MANIFEST_PATH, RAW_DIR, ROOT, check_url, fetch_bytes, load_manifest,
    sha256_bytes, write_json,
)

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _save_manifest(entries: list[dict]) -> None:
    write_json(MANIFEST_PATH, sorted(entries, key=lambda e: e["id"]))


def _guess_ext(url: str) -> str:
    suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
    return suffix if suffix in (".txt", ".html", ".htm", ".json", ".xml", ".pdf") else ".html"


def cmd_add(args: argparse.Namespace) -> int:
    if not ID_RE.match(args.id):
        print(f"error: id must match {ID_RE.pattern}", file=sys.stderr)
        return 2
    check_url(args.url)
    entries = load_manifest()
    if any(e["id"] == args.id for e in entries):
        print(f"error: {args.id} is already in the manifest", file=sys.stderr)
        return 2
    data = fetch_bytes(args.url)
    ext = args.ext or _guess_ext(args.url)
    if ext and not ext.startswith("."):
        ext = f".{ext}"  # "--ext html" means ".html"
    path = RAW_DIR / f"{args.id}{ext}"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    entries.append({
        "id": args.id,
        "license": args.license,
        "notes": args.notes or "",
        "path": str(path.relative_to(ROOT)),
        "retrieved_at": dt.date.today().isoformat(),
        "sha256": sha256_bytes(data),
        "url": args.url,
    })
    _save_manifest(entries)
    print(f"added {args.id}: {len(data)} bytes -> {path.relative_to(ROOT)}")
    return 0


def cmd_restore(_: argparse.Namespace) -> int:
    failed = 0
    for e in load_manifest():
        path = ROOT / e["path"]
        if path.exists():
            continue
        data = fetch_bytes(e["url"])
        if sha256_bytes(data) != e["sha256"]:
            print(f"error: {e['id']}: upstream content changed since {e['retrieved_at']}; "
                  "not saved. Record it as a new source if it should be used.", file=sys.stderr)
            failed += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"restored {e['id']}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m tools.fetch")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("add", help="download and record a new raw source")
    a.add_argument("--id", required=True)
    a.add_argument("--url", required=True)
    a.add_argument("--license", required=True)
    a.add_argument("--notes")
    a.add_argument("--ext")
    args = p.parse_args(argv)
    return cmd_add(args) if args.cmd == "add" else cmd_restore(args)


if __name__ == "__main__":
    sys.exit(main())
