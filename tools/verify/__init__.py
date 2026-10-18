"""Checks behind `make verify`. Each check returns a list of error strings.

See docs/contributing.md for what each check enforces. Never weaken a check
to make it pass; fix the data or the importer instead.
"""

from __future__ import annotations

import datetime as dt
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable

from tools.common import (
    LINKS_DIR, MANIFEST_PATH, RAW_DIR, ROOT, TEXTS_DIR, CASES_DIR, is_safe_url, load_manifest,
    normalize_for_match, read_json, read_jsonl, sha256_file,
)
from tools.corpus import Corpus, load_corpus

LINK_TYPES = {"quotes", "cites", "responds_to", "rebuts", "shared_theme", "interprets", "overrules", "implements"}
STATUSES = {"suggested", "reviewed", "rejected"}
CONFIDENCE = {"high", "medium", "low"}
CREATOR_KINDS = {"agent", "human", "import"}
LINK_KEYS = {
    "id", "from", "to", "type", "from_quote", "to_quote", "rationale", "source", "created_by",
    "created_at", "confidence", "status", "reviewed_by", "reviewed_at",
}
REQUIRED_LINK_KEYS = {"id", "from", "to", "type", "created_by", "created_at", "confidence", "status"}
LINK_ID = re.compile(r"^lnk_[a-z0-9_]+$")
REF = re.compile(r"^[A-Za-z][A-Za-z0-9]*(\.[A-Za-z0-9]+)*$")
MANIFEST_KEYS = {"id", "url", "retrieved_at", "sha256", "license", "notes", "path"}


# ------------------------------------------------------------ helpers


def walk_urls(obj: Any, where: str) -> Iterable[tuple[str, str]]:
    """Yield (location, value) for every string stored under a key that
    names a URL (url, href, or *_url)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            loc = f"{where}.{k}"
            if isinstance(v, str) and (k in ("url", "href") or k.endswith("_url")):
                yield loc, v
            else:
                yield from walk_urls(v, loc)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_urls(v, f"{where}[{i}]")


def _is_date(s: Any) -> bool:
    try:
        dt.date.fromisoformat(s)
        return True
    except (TypeError, ValueError):
        return False


def quote_in(quote: str, passages: list[dict]) -> bool:
    q = normalize_for_match(quote)
    return bool(q) and any(q in normalize_for_match(p["text"]) for p in passages)


# ------------------------------------------------------------ sources


def check_manifest() -> list[str]:
    errors: list[str] = []
    if not MANIFEST_PATH.exists():
        return ["sources/manifest.json is missing"]
    entries = load_manifest()
    seen: set[str] = set()
    listed: set[Path] = set()
    for e in entries:
        eid = e.get("id", "?")
        missing = MANIFEST_KEYS - e.keys()
        if missing:
            errors.append(f"manifest {eid}: missing {sorted(missing)}")
            continue
        if eid in seen:
            errors.append(f"manifest: duplicate id {eid}")
        seen.add(eid)
        if not is_safe_url(e["url"]):
            errors.append(f"manifest {eid}: url must be http(s): {e['url']!r}")
        if not _is_date(e["retrieved_at"]):
            errors.append(f"manifest {eid}: retrieved_at is not an ISO date")
        if not e["license"].strip():
            errors.append(f"manifest {eid}: license is empty")
        path = (ROOT / e["path"]).resolve()
        if RAW_DIR.resolve() not in path.parents:
            errors.append(f"manifest {eid}: path must be under sources/raw/")
            continue
        listed.add(path)
        if not path.exists():
            errors.append(f"manifest {eid}: {e['path']} is missing (run make fetch)")
        elif sha256_file(path) != e["sha256"]:
            errors.append(f"manifest {eid}: {e['path']} does not match its sha256 (raw files must not be edited)")
    if entries != sorted(entries, key=lambda x: x.get("id", "")):
        errors.append("manifest: entries must be sorted by id")
    if RAW_DIR.exists():
        for f in sorted(RAW_DIR.rglob("*")):
            if f.is_file() and f.name != ".gitkeep" and f.resolve() not in listed:
                errors.append(f"sources/raw/{f.relative_to(RAW_DIR)} is not recorded in the manifest")
    return errors


# ------------------------------------------------------------ texts


def check_texts(corpus: Corpus) -> list[str]:
    errors: list[str] = []
    source_ids = {e["id"] for e in load_manifest()}
    for ref in corpus.duplicate_refs:
        errors.append(f"duplicate segment ref {ref}")
    for wid, doc in corpus.works.items():
        name = corpus.files[wid].relative_to(ROOT)
        for key in ("id", "title", "ref_prefix", "edition", "source_ids", "segments"):
            if key not in doc:
                errors.append(f"{name}: missing {key}")
        if doc.get("id") != corpus.files[wid].stem:
            errors.append(f"{name}: id must equal the file name")
        for sid in doc.get("source_ids", []):
            if sid not in source_ids:
                errors.append(f"{name}: source_id {sid} is not in the manifest")
        prefix = doc.get("ref_prefix", "") + "."
        for s in doc.get("segments", []):
            ref = s.get("ref", "")
            if not REF.match(ref) or not ref.startswith(prefix):
                errors.append(f"{name}: bad ref {ref!r} (must start with {prefix})")
            text = s.get("text")
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{ref}: empty text")
                continue
            if text != text.strip():
                errors.append(f"{ref}: text has leading/trailing whitespace")
            if re.search(r"</?[a-z]+[ >/]", text):
                errors.append(f"{ref}: text looks like markup")
            if s.get("source_id") and s["source_id"] not in doc.get("source_ids", []):
                errors.append(f"{ref}: source_id {s['source_id']} not listed in the work's source_ids")
            for span in s.get("emphasis", []):
                if not (isinstance(span, list) and len(span) == 2 and 0 <= span[0] < span[1] <= len(text)):
                    errors.append(f"{ref}: bad emphasis span {span}")
            for cb in s.get("changed_by", []):
                if cb.get("quote") not in text:
                    errors.append(f"{ref}: changed_by quote is not in the text: {cb.get('quote')!r}")
                if not corpus.exists(cb.get("amendment", "")):
                    errors.append(f"{ref}: changed_by refers to unknown {cb.get('amendment')}")
        for d in doc.get("divisions", []):
            if not corpus.exists(d.get("ref", "")) or not corpus.passages(d["ref"]):
                errors.append(f"{name}: division {d.get('ref')} has no segments")
        for loc, url in walk_urls(doc, str(name)):
            if not is_safe_url(url):
                errors.append(f"{loc}: URL must be http(s): {url!r}")
    return errors


def check_reproducible() -> list[str]:
    """Every file in texts/ must be exactly what the importers produce from
    sources/raw/. This is what keeps hand-typed text out of the corpus."""
    from importers import IMPORTERS

    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        produced: set[str] = set()
        for module in IMPORTERS:
            try:
                paths = module.run(out)
            except Exception as exc:  # report, don't crash the whole run
                errors.append(f"importer {module.__name__} failed: {exc}")
                continue
            for p in paths:
                produced.add(p.name)
                committed = TEXTS_DIR / p.name
                if not committed.exists():
                    errors.append(f"texts/{p.name} is missing (run make import)")
                elif committed.read_bytes() != p.read_bytes():
                    errors.append(f"texts/{p.name} differs from importer output (run make import; never edit texts by hand)")
        for f in sorted(TEXTS_DIR.glob("*.json")):
            if f.name not in produced:
                errors.append(f"texts/{f.name} is not produced by any importer")
    return errors


# ------------------------------------------------------------ links


def iter_link_files() -> list[Path]:
    return sorted(LINKS_DIR.rglob("*.jsonl")) if LINKS_DIR.exists() else []


def load_links() -> list[tuple[Path, int, dict]]:
    out = []
    for path in iter_link_files():
        for n, rec in read_jsonl(path):
            out.append((path, n, rec))
    return out


def check_link(rec: dict, corpus: Corpus, proposed: bool) -> list[str]:
    errors: list[str] = []
    unknown = rec.keys() - LINK_KEYS
    if unknown:
        errors.append(f"unknown keys {sorted(unknown)}")
    missing = REQUIRED_LINK_KEYS - rec.keys()
    if missing:
        errors.append(f"missing {sorted(missing)}")
        return errors
    if not LINK_ID.match(str(rec["id"])):
        errors.append(f"id {rec['id']!r} must match {LINK_ID.pattern}")
    if rec["type"] not in LINK_TYPES:
        errors.append(f"unknown type {rec['type']!r}")
    if rec["status"] not in STATUSES:
        errors.append(f"unknown status {rec['status']!r}")
    if proposed and rec["status"] != "suggested":
        errors.append("links in links/proposed/ must have status 'suggested'")
    if rec["confidence"] not in CONFIDENCE:
        errors.append(f"unknown confidence {rec['confidence']!r}")
    if not _is_date(rec["created_at"]):
        errors.append("created_at must be an ISO date")
    cb = rec["created_by"]
    if not isinstance(cb, dict) or cb.get("kind") not in CREATOR_KINDS:
        errors.append("created_by.kind must be agent, human or import")
    elif cb["kind"] == "agent" and not (cb.get("model") and cb.get("run")):
        errors.append("agent links need created_by.model and created_by.run")
    has_rationale = isinstance(rec.get("rationale"), str) and rec["rationale"].strip()
    has_source = isinstance(rec.get("source"), str) and rec["source"].strip()
    if not has_rationale and not (isinstance(cb, dict) and cb.get("kind") == "import" and has_source):
        errors.append("needs a rationale (or a source, for imported links)")
    if rec["status"] == "reviewed" and not rec.get("reviewed_by"):
        errors.append("reviewed links need reviewed_by")
    if rec["status"] == "suggested" and rec.get("reviewed_by"):
        errors.append("suggested links must not have reviewed_by")
    if rec["from"] == rec["to"]:
        errors.append("a link cannot point to itself")
    for end in ("from", "to"):
        ref = rec[end]
        if not isinstance(ref, str) or not corpus.exists(ref):
            errors.append(f"{end} ref {ref!r} does not exist")
            continue
        q = rec.get(f"{end}_quote")
        if q is not None and not quote_in(q, corpus.passages(ref)):
            errors.append(f"{end}_quote is not an exact substring of {ref}")
    if rec["type"] == "overrules":
        if not (rec["from"].startswith("Case.") and rec["to"].startswith("Case.")):
            errors.append("overrules links must go from a case to a case")
        if not has_source:
            errors.append("overrules links must cite a source")
    if rec["type"] == "interprets" and not rec["from"].startswith("Case."):
        errors.append("interprets links must start from a case")
    for loc, url in walk_urls(rec, "link"):
        if not is_safe_url(url):
            errors.append(f"{loc}: URL must be http(s)")
    if isinstance(rec.get("source"), str) and re.match(r"^[a-z][a-z0-9+.-]*:", rec["source"]) \
            and not is_safe_url(rec["source"].split()[0]):
        errors.append("source looks like a non-http(s) URL")
    return errors


def check_links(corpus: Corpus) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    proposed_dir = (LINKS_DIR / "proposed").resolve()
    for path, n, rec in load_links():
        where = f"{path.relative_to(ROOT)}:{n}"
        if not isinstance(rec, dict):
            errors.append(f"{where}: not a JSON object")
            continue
        proposed = proposed_dir in path.resolve().parents
        errors.extend(f"{where}: {e}" for e in check_link(rec, corpus, proposed))
        lid = str(rec.get("id"))
        if lid in seen:
            errors.append(f"{where}: duplicate link id {lid} (also at {seen[lid]})")
        seen[lid] = where
    return errors


def check_overruled_flags(corpus: Corpus) -> list[str]:
    """Every link that touches an overruled case must come out of the site
    data build flagged, so the site can show it."""
    from tools.site_data import build_link_index, case_root

    links = [rec for _, _, rec in load_links() if isinstance(rec, dict)]
    index = build_link_index(links, corpus)
    overruled = index["overruled"]
    errors = []
    for ref, entries in index["by_ref"].items():
        for e in entries:
            other = e["other"]
            if case_root(other) in overruled and not e.get("other_overruled"):
                errors.append(f"site data: link {e['id']} to overruled {other} is not flagged")
    return errors


CHECKS = [
    ("sources", lambda c: check_manifest()),
    ("texts", check_texts),
    ("reproducible", lambda c: check_reproducible()),
    ("links", check_links),
    ("overruled", check_overruled_flags),
]


def run_all() -> dict[str, list[str]]:
    corpus = load_corpus(TEXTS_DIR, CASES_DIR)
    return {name: fn(corpus) for name, fn in CHECKS}
