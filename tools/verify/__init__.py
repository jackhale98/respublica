"""Checks behind `make verify`. Each check returns a list of error strings.

See docs/contributing.md for what each check enforces. Never weaken a check
to make it pass; fix the data or the importer instead.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable

from tools.common import (
    LINKS_DIR, MANIFEST_PATH, RAW_DIR, ROOT, TEXTS_DIR, CASES_DIR, UNTRACKED_RAW, is_safe_url, load_manifest,
    normalize_for_match, read_json, read_jsonl, sha256_file,
)
from tools.corpus import Corpus, load_corpus

LINK_TYPES = {"quotes", "cites", "responds_to", "rebuts", "shared_theme", "interprets", "overrules", "implements"}
STATUSES = {"suggested", "reviewed", "rejected"}
CONFIDENCE = {"high", "medium", "low"}
CREATOR_KINDS = {"agent", "human", "import"}
LINK_KEYS = {
    "id", "from", "to", "type", "from_quote", "to_quote", "rationale", "source", "created_by",
    "created_at", "confidence", "status", "reviewed_by", "reviewed_at", "review_note",
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
        if "auth_env" in e and not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(e["auth_env"])):
            errors.append(f"manifest {eid}: auth_env must name an environment variable, not hold a token")
        if e.get("encoding", "gzip") != "gzip":
            errors.append(f"manifest {eid}: encoding must be gzip (the only one fetch asks for)")
        if "range" in e:
            m = re.fullmatch(r"(\d+)-(\d+)", str(e["range"]))
            if not m or int(m.group(2)) < int(m.group(1)):
                errors.append(f"manifest {eid}: range must be first-last (bytes of the file at url)")
            elif (ROOT / e["path"]).exists() and (ROOT / e["path"]).stat().st_size != int(m.group(2)) - int(m.group(1)) + 1:
                errors.append(f"manifest {eid}: {e['path']} is not the size of its range {e['range']}")
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
    return errors + check_ocr_records({e["id"]: e for e in entries if "id" in e})


OCR_RECORD_KEYS = {"command", "id", "images", "notes", "path", "sha256", "tools"}


def check_ocr_records(raw: dict[str, dict]) -> list[str]:
    """OCR we ran ourselves (sources/ocr/, decision 46): each output is
    recorded with the tool and the raw page images it read, and matches
    its sha256. Tesseract is never run here."""
    from importers.ocr import OCR_DIR, OCR_MANIFEST
    errors: list[str] = []
    records = read_json(OCR_MANIFEST) if OCR_MANIFEST.exists() else []
    listed = set()
    for r in records:
        rid = r.get("id", "?")
        missing = OCR_RECORD_KEYS - r.keys()
        if missing:
            errors.append(f"sources/ocr {rid}: missing {sorted(missing)}")
            continue
        path = (ROOT / r["path"]).resolve()
        listed.add(path)
        if OCR_DIR.resolve() not in path.parents:
            errors.append(f"sources/ocr {rid}: path must be under sources/ocr/")
        elif not path.exists() or sha256_file(path) != r["sha256"]:
            errors.append(f"sources/ocr {rid}: {r['path']} is missing or does not match its sha256 (rerun its OCR)")
        images = r["images"]
        # One file of page images ("source", "sha256"), or one file a page
        # ("sources": [{"source", "sha256"}, …]; decision 60).
        for img in images.get("sources") or [images]:
            src = raw.get(img.get("source"))
            if src is None:
                errors.append(f"sources/ocr {rid}: images come from {img.get('source')!r}, which is not in the manifest")
            elif src["sha256"] != img.get("sha256"):
                errors.append(f"sources/ocr {rid}: was read from a different file than {src['id']} (rerun its OCR)")
        if not r["tools"] or not all(isinstance(v, str) and v for v in r["tools"].values()):
            errors.append(f"sources/ocr {rid}: tools must name each package and its version")
    if OCR_DIR.exists():
        for f in sorted(OCR_DIR.iterdir()):
            if f.is_file() and f != OCR_MANIFEST and f.resolve() not in listed:
                errors.append(f"sources/ocr/{f.name} is not recorded in sources/ocr/manifest.json")
    return errors


# ------------------------------------------------------------ texts


SEGMENT_KINDS = {"footnote", "syllabus"}
# Tie-breakers other than the Anti-Federalist Library whose suggestions a span may carry.
SUGGESTED_BY = {"loc"}
POSITIONS = {"anti", "federalist", "other"}
SCAN_ITEM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,99}$")


def check_uncertain(where: str, text: str, spans: Any) -> list[str]:
    """Words the scans could not settle: each span lies inside the text, in
    order, and the text there is one of the scans' readings."""
    errors = []
    if not isinstance(spans, list):
        return [f"{where}: uncertain must be a list"]
    end = 0
    for u in spans:
        start, stop, readings = u.get("start"), u.get("end"), u.get("readings")
        if not (isinstance(start, int) and isinstance(stop, int) and end <= start < stop <= len(text)):
            errors.append(f"{where}: uncertain span {start}-{stop} is out of place")
            continue
        end = stop
        # The main scan's reading ("primary"), or for a text from the Text
        # Creation Partnership the transcription's ("tcp", decision 67).
        if not (isinstance(readings, dict) and ("primary" in readings) != ("tcp" in readings)
                and all(isinstance(v, str) for v in readings.values())):
            errors.append(f"{where}: uncertain span {start}-{stop} needs the primary scan's (or the TCP's) reading")
        elif "accepted" in u:
            # The Anti-Federalist Library's reading, accepted by the owner
            # without a check against the page (decision 56): still marked.
            acc = u["accepted"]
            if not (isinstance(acc, dict) and acc.get("source") == "library" and isinstance(acc.get("by"), str)
                    and LOGIN.match(acc["by"]) and _is_date(acc.get("at")) and "suggestion" not in u):
                errors.append(f"{where}: uncertain span {start}-{stop} has a bad accepted reading {acc!r}")
        elif text[start:stop] not in readings.values():
            errors.append(f"{where}: {text[start:stop]!r} at {start} is not one of the scans' readings")
        # The Anti-Federalist Library's reading, for a person to check (never
        # in the text): one line, and not what the text already has.
        sug = u.get("suggestion")
        if "suggestion" in u and not (isinstance(sug, str) and sug.strip() and "\n" not in sug and len(sug) <= 200
                                      and sug != text[start:stop]):
            errors.append(f"{where}: uncertain span {start}-{stop} has a bad suggestion {sug!r}")
        # Whose the suggestion is, where not the Library's (decision 68).
        if "suggested_by" in u and not ("suggestion" in u and u["suggested_by"] in SUGGESTED_BY):
            errors.append(f"{where}: uncertain span {start}-{stop} has a bad suggested_by {u['suggested_by']!r}")
    return errors


LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


def check_corrected(where: str, text: str, fixed: Any, spans: list[dict]) -> list[str]:
    """Words a person corrected against the page image (decision 48): each
    lies inside the text, in order, apart from the words still uncertain,
    and names who corrected it and when."""
    if not isinstance(fixed, list):
        return [f"{where}: corrected must be a list"]
    errors, end = [], 0
    unsettled = [(u.get("start", 0), u.get("end", 0)) for u in spans]
    for c in fixed:
        start, stop = c.get("start"), c.get("end")
        if not (isinstance(start, int) and isinstance(stop, int) and end <= start < stop <= len(text)):
            errors.append(f"{where}: corrected span {start}-{stop} is out of place")
            continue
        end = stop
        if any(a < stop and start < b for a, b in unsettled):
            errors.append(f"{where}: corrected span {start}-{stop} overlaps an uncertain word")
        if not (isinstance(c.get("by"), str) and LOGIN.match(c["by"]) and _is_date(c.get("at"))
                and isinstance(c.get("was"), str)):
            errors.append(f"{where}: corrected span {start}-{stop} needs who corrected it (by), when (at) and the scans' word (was)")
    return errors


def check_corrections(corpus: Corpus) -> list[str]:
    """corrections/*.jsonl: one file per work, each line a person's decision
    on a passage of that work (importers/corrections.py applies them; an
    import stops on one that no longer matches)."""
    errors = []
    for f in sorted((ROOT / "corrections").glob("*")):
        if f.name == "README.md":
            continue
        if f.suffix != ".jsonl" or f.stem not in corpus.works:
            errors.append(f"corrections/{f.name}: must be named after a work ({{work}}.jsonl)")
            continue
        prefix = corpus.works[f.stem].get("ref_prefix", "") + "."
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                c = json.loads(line)
            except ValueError:
                errors.append(f"corrections/{f.name}:{n}: not JSON")
                continue
            if sorted(k for k in c if k != "source") != ["at", "by", "index", "now", "ref", "was"] \
                    or c.get("source", "library") != "library":
                errors.append(f"corrections/{f.name}:{n}: needs exactly at, by, index, now, ref, was "
                              "(and source \"library\" for an accepted Library reading)")
                continue
            if not str(c["ref"]).startswith(prefix) or c["ref"] not in corpus.segments:
                errors.append(f"corrections/{f.name}:{n}: {c['ref']!r} is not a passage of {f.stem}")
            if not (isinstance(c["by"], str) and LOGIN.match(c["by"]) and _is_date(c["at"])):
                errors.append(f"corrections/{f.name}:{n}: by must be a GitHub login and at a date")
            if not (isinstance(c["now"], str) and c["now"].strip() and "\n" not in c["now"] and isinstance(c["index"], int)):
                errors.append(f"corrections/{f.name}:{n}: now must be one line of text and index a number")
    return errors


def looks_like_markup(text: str, uncertain: list[dict]) -> bool:
    """A tag-like run ("<p ", "</i>") anywhere but inside a word marked
    uncertain: there the text is a scan's reading kept for a person to check
    ("a<l opted" for "adopted"), with the other scans' readings beside it."""
    unsettled = [(u.get("start", 0), u.get("end", 0)) for u in uncertain]
    return any(not any(a <= m.start() < b for a, b in unsettled) for m in re.finditer(r"</?[a-z]+[ >/]", text))


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
        own = {s.get("ref") for s in doc.get("segments", [])}
        for r in doc.get("retired", []):
            # A retired ref is never reused, and points at a passage of the same work.
            if r.get("ref") in corpus.segments or r.get("ref") in corpus.divisions:
                errors.append(f"{name}: retired ref {r.get('ref')} is in use")
            if r.get("merged_into") not in own:
                errors.append(f"{name}: retired ref {r.get('ref')} merged into {r.get('merged_into')!r}, "
                              "which is not a passage of this work")
            if not str(r.get("ref", "")).startswith(prefix) or not str(r.get("reason", "")).strip():
                errors.append(f"{name}: retired ref {r.get('ref')!r} needs this work's prefix and a reason")
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
            if looks_like_markup(text, s.get("uncertain", [])):
                errors.append(f"{ref}: text looks like markup")
            if s.get("source_id") and s["source_id"] not in doc.get("source_ids", []):
                errors.append(f"{ref}: source_id {s['source_id']} not listed in the work's source_ids")
            for span in s.get("emphasis", []):
                if not (isinstance(span, list) and len(span) == 2 and 0 <= span[0] < span[1] <= len(text)):
                    errors.append(f"{ref}: bad emphasis span {span}")
            errors += check_uncertain(ref, text, s.get("uncertain", []))
            if "corrected" in s:
                errors += check_corrected(ref, text, s["corrected"], s.get("uncertain", []))
            if "scan" in s:
                scan = s["scan"]
                if not (isinstance(scan, dict) and isinstance(scan.get("item"), str) and SCAN_ITEM.match(scan["item"])
                        and scan.get("leaves") and all(isinstance(n, int) and n > 0 for n in scan["leaves"])):
                    errors.append(f"{ref}: bad scan {scan!r}")
                elif scan.get("site") == "govinfo":
                    # The bound Congressional Record: its page images are the
                    # microfilm's (decision 61), one for each of the passage's pages.
                    film = scan.get("microfilm")
                    if not (isinstance(film, dict) and isinstance(film.get("item"), str) and SCAN_ITEM.match(film["item"])
                            and isinstance(film.get("leaves"), list) and len(film["leaves"]) == len(scan["leaves"])
                            and all(isinstance(n, int) and n > 0 for n in film["leaves"])):
                        errors.append(f"{ref}: a govinfo scan needs the microfilm's leaves for its pages: {scan!r}")
            if "kind" in s and s["kind"] not in SEGMENT_KINDS:
                errors.append(f"{ref}: unknown kind {s['kind']!r}")
            for cb in s.get("changed_by", []):
                if cb.get("quote") not in text:
                    errors.append(f"{ref}: changed_by quote is not in the text: {cb.get('quote')!r}")
                if not corpus.exists(cb.get("amendment", "")):
                    errors.append(f"{ref}: changed_by refers to unknown {cb.get('amendment')}")
        if "position" in doc and doc["position"] not in POSITIONS:
            errors.append(f"{name}: unknown position {doc['position']!r}")
        for d in doc.get("divisions", []):
            if not corpus.exists(d.get("ref", "")) or not corpus.passages(d["ref"]):
                errors.append(f"{name}: division {d.get('ref')} has no segments")
            for field, spans in d.get("uncertain", {}).items():
                head, _, idx = field.partition(".")
                value = d.get(head)
                if head == "publication" and isinstance(value, list) and idx.isdigit() and int(idx) < len(value):
                    value = value[int(idx)]
                if head not in ("publication", "salutation", "signature", "title") or not isinstance(value, str):
                    errors.append(f"{d.get('ref')}: uncertain names an unknown field {field!r}")
                    continue
                errors += check_uncertain(f"{d.get('ref')} {field}", value, spans)
        for loc, url in walk_urls(doc, str(name)):
            if not is_safe_url(url):
                errors.append(f"{loc}: URL must be http(s): {url!r}")
    return errors


def check_reproducible(only: list[str] | None = None) -> list[str]:
    """Every file in texts/ and cases/ must be exactly what the importers
    produce from sources/raw/. This is what keeps hand-typed text out of the
    corpus. Each importer runs in a process of its own and reports what it
    reads and writes; that must match importers/outputs.json, which the
    errata workflow uses to re-run only the importers a correction touches.

    `only`: run just these importers (the errata and link-review workflows,
    which first check that nothing outside their outputs changed; decision
    64). The full check runs on every push to main."""
    from importers.__main__ import MAP_PATH, load_map, names, run_separately

    errors: list[str] = []
    committed_map = load_map()
    chosen = names() if only is None else [n for n in names() if n in only]
    found: dict[str, dict] = {}
    produced: dict[Path, set[str]] = {TEXTS_DIR: set(), CASES_DIR: set()}
    with tempfile.TemporaryDirectory() as tmp:
        for name in chosen:
            out = Path(tmp) / name
            out.mkdir()
            try:
                found[name] = run_separately(name, out)
            except Exception as exc:  # report, don't crash the whole run
                errors.append(f"importer {name} failed: {exc}")
                continue
            for rel in found[name]["outputs"]:
                final = ROOT / rel.split("/")[0]
                produced.setdefault(final, set()).add(Path(rel).name)
                p = out / Path(rel).name
                committed = ROOT / rel
                if not committed.exists():
                    errors.append(f"{rel} is missing (run make import)")
                elif committed.read_bytes() != p.read_bytes():
                    errors.append(f"{rel} differs from importer output (run make import; never edit it by hand)")
            if committed_map.get(name) != found[name]:
                errors.append(f"{MAP_PATH.relative_to(ROOT)}: the entry for {name} is out of date (run make import)")
    if only is None and not errors:
        for final, names_ in produced.items():
            for f in sorted(final.glob("*.json")):
                if f.name not in names_:
                    errors.append(f"{final.name}/{f.name} is not produced by any importer")
        if set(committed_map) != set(found):
            errors.append(f"{MAP_PATH.relative_to(ROOT)} names other importers than importers/__init__.py (run make import)")
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
    if rec["status"] == "suggested" and (rec.get("reviewed_by") or rec.get("review_note")):
        errors.append("suggested links must not have reviewed_by or review_note")
    if "review_note" in rec and not (isinstance(rec["review_note"], str) and len(rec["review_note"]) <= 500):
        errors.append("review_note must be text of at most 500 characters")
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


def check_refs_locked(corpus: Corpus) -> list[str]:
    """Published refs never disappear (CLAUDE.md rule 6)."""
    from tools.refs import LOCK_PATH, missing_locked

    if not LOCK_PATH.exists():
        return ["refs.lock is missing (run python -m tools.refs lock)"]
    return [f"locked ref {r} no longer exists; published refs are permanent (use docs/errata.md)"
            for r in missing_locked(corpus)]


# Free-tier budgets for the repository (see docs/decisions.md). GitHub warns
# at 50 MB per file, rejects 100 MB, and recommends repositories under 1 GB.
RAW_FILE_BUDGET = 40 * 1024 * 1024
RAW_TOTAL_BUDGET = 300 * 1024 * 1024
DATA_FILE_BUDGET = 20 * 1024 * 1024
# Raw files kept out of git (UNTRACKED_RAW) live in the CI cache, which GitHub
# limits to 10 GB per repository: 1 GiB at first (decision 49), 4 GiB for the
# Congressional Record (decision 61), each family cached under its own key.
UNTRACKED_TOTAL_BUDGET = 4 * 1024 * 1024 * 1024


def check_repo_budgets(corpus: Corpus) -> list[str]:
    errors = []
    total = untracked = 0
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines() if (ROOT / ".gitignore").exists() else []
    for pattern in UNTRACKED_RAW:
        if f"sources/raw/{pattern}" not in gitignore:
            errors.append(f".gitignore must list sources/raw/{pattern} (raw files kept out of git)")
    if RAW_DIR.exists():
        for f in RAW_DIR.rglob("*"):
            if f.is_file():
                size = f.stat().st_size
                if any(f.match(p) for p in UNTRACKED_RAW):
                    untracked += size  # not in git: only the cache's total budget applies
                    continue
                total += size
                if size > RAW_FILE_BUDGET:
                    errors.append(f"{f.relative_to(ROOT)} is {size // 2**20} MB; budget is "
                                  f"{RAW_FILE_BUDGET // 2**20} MB per raw file (prefer a text layer over scans)")
    if total > RAW_TOTAL_BUDGET:
        errors.append(f"sources/raw totals {total // 2**20} MB in git; budget is {RAW_TOTAL_BUDGET // 2**20} MB")
    if untracked > UNTRACKED_TOTAL_BUDGET:
        errors.append(f"raw files kept out of git total {untracked // 2**20} MB; budget is "
                      f"{UNTRACKED_TOTAL_BUDGET // 2**20} MB")
    for d in (TEXTS_DIR, CASES_DIR, LINKS_DIR):
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file() and f.stat().st_size > DATA_FILE_BUDGET:
                    errors.append(f"{f.relative_to(ROOT)} exceeds {DATA_FILE_BUDGET // 2**20} MB; split it")
    return errors


CHECKS = [
    ("sources", lambda c: check_manifest()),
    ("budgets", check_repo_budgets),
    ("texts", check_texts),
    ("corrections", check_corrections),
    ("reproducible", lambda c: check_reproducible(ONLY_IMPORTERS)),
    ("refs", check_refs_locked),
    ("links", check_links),
    ("overruled", check_overruled_flags),
]


# Set by `python -m tools.verify --importers a,b` (decision 65).
ONLY_IMPORTERS: list[str] | None = None


def run_all() -> dict[str, list[str]]:
    corpus = load_corpus(TEXTS_DIR, CASES_DIR)
    return {name: fn(corpus) for name, fn in CHECKS}
