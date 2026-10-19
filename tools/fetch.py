"""Download raw source files and keep sources/manifest.json in step.

    python -m tools.fetch              # restore any raw file that is missing
    python -m tools.fetch add --id ID --url URL --license TEXT [--notes TEXT] [--ext .html]
    python -m tools.fetch cache-keys   # name=key per family of raw files kept out of git (CI)

`add` downloads a new original once and records its URL, retrieval date,
sha256 and license. A source behind an API token (CourtListener) records
`auth_env`, the name of the environment variable that holds the token,
never the token itself, and a source that answers a POST (an API lookup)
records the form-encoded body it was sent as `post`. Importers add such
sources with `add_source`. The plain form re-downloads only files that are
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
    MANIFEST_PATH, RAW_DIR, ROOT, UNTRACKED_FAMILIES, auth_headers, check_url, fetch_bytes, load_manifest,
    sha256_bytes, write_json,
)

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _save_manifest(entries: list[dict]) -> None:
    write_json(MANIFEST_PATH, sorted(entries, key=lambda e: e["id"]))


def _guess_ext(url: str) -> str:
    suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
    return suffix if suffix in (".txt", ".html", ".htm", ".json", ".xml", ".pdf", ".zip") else ".html"


def _headers(auth_env: str | None, encoding: str | None) -> dict[str, str] | None:
    headers = {**(auth_headers(auth_env) if auth_env else {}), **({"Accept-Encoding": encoding} if encoding else {})}
    return headers or None


def add_source(source_id: str, url: str, license: str, notes: str = "", ext: str | None = None,
               auth_env: str | None = None, post: str | None = None, encoding: str | None = None) -> dict:
    """Download a new original once, save it under sources/raw/ and record
    it in the manifest. Returns the manifest entry. With `encoding` ("gzip"),
    the server is asked to send the file compressed, and the bytes are kept
    as sent (the file is the original once decompressed)."""
    if not ID_RE.match(source_id):
        raise ValueError(f"source id must match {ID_RE.pattern}: {source_id!r}")
    check_url(url)
    entries = load_manifest()
    if any(e["id"] == source_id for e in entries):
        raise ValueError(f"{source_id} is already in the manifest")
    data = fetch_bytes(url, headers=_headers(auth_env, encoding), post=post)
    if encoding == "gzip" and data[:2] != b"\x1f\x8b":
        raise ValueError(f"{url} was not sent gzip-compressed")
    ext = ext or _guess_ext(url)
    if ext and not ext.startswith("."):
        ext = f".{ext}"  # "--ext html" means ".html"
    path = RAW_DIR / f"{source_id}{ext}"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    entry = {
        "id": source_id,
        "license": license,
        "notes": notes,
        "path": str(path.relative_to(ROOT)),
        "retrieved_at": dt.date.today().isoformat(),
        "sha256": sha256_bytes(data),
        "url": url,
    }
    if auth_env:
        entry["auth_env"] = auth_env
    if post is not None:
        entry["post"] = post
    if encoding:
        entry["encoding"] = encoding
    # Read the manifest again: a download can wait hours on a rate limit,
    # and other sources may have been recorded meanwhile.
    entries = load_manifest()
    if any(e["id"] == source_id for e in entries):
        raise ValueError(f"{source_id} is already in the manifest")
    entries.append(entry)
    _save_manifest(entries)
    return entry


def cmd_add(args: argparse.Namespace) -> int:
    try:
        e = add_source(args.id, args.url, args.license, args.notes or "", args.ext)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print(f"added {e['id']}: {(ROOT / e['path']).stat().st_size} bytes -> {e['path']}")
    return 0


def cmd_restore(_: argparse.Namespace) -> int:
    failed = 0
    for e in load_manifest():
        path = ROOT / e["path"]
        if path.exists():
            continue
        data = fetch_bytes(e["url"], headers=_headers(e.get("auth_env"), e.get("encoding")), post=e.get("post"))
        if sha256_bytes(data) != e["sha256"]:
            print(f"error: {e['id']}: upstream content changed since {e['retrieved_at']}; "
                  "not saved. Record it as a new source if it should be used.", file=sys.stderr)
            failed += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"restored {e['id']}")
    return 1 if failed else 0


def cache_keys() -> dict[str, str]:
    """For each family of raw files kept out of git, a key that changes only
    when that family's manifest entries do (CI caches each family under its
    own key, so adding one family's files does not save the others again)."""
    import fnmatch
    import hashlib
    out = {}
    for name, pattern in UNTRACKED_FAMILIES.items():
        h = hashlib.sha256()
        for e in load_manifest():
            if fnmatch.fnmatch(Path(e["path"]).name, pattern):
                h.update(f"{e['id']} {e['sha256']}\n".encode())
        out[name] = h.hexdigest()[:32]
    return out


def cmd_cache_keys(_: argparse.Namespace) -> int:
    for name, key in cache_keys().items():
        print(f"{name}={key}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m tools.fetch")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("add", help="download and record a new raw source")
    a.add_argument("--id", required=True)
    a.add_argument("--url", required=True)
    a.add_argument("--license", required=True)
    a.add_argument("--notes")
    a.add_argument("--ext")
    sub.add_parser("cache-keys", help="print a CI cache key for each family of raw files kept out of git")
    args = p.parse_args(argv)
    if args.cmd == "add":
        return cmd_add(args)
    if args.cmd == "cache-keys":
        return cmd_cache_keys(args)
    return cmd_restore(args)


if __name__ == "__main__":
    sys.exit(main())
