"""Record a person's decisions on words read from scans (decision 48).

    python -m tools.errata apply --reviewer LOGIN --text FILE
    python -m tools.errata accept-library --owner LOGIN

The errata page (`/errata/`) opens a GitHub issue titled "Errata review"
whose body lists one decision per line:

    correct House1789.Jun8.1 0 "tlm^his" "this"

that is, the passage, the place of the uncertain word among the passage's
uncertain words (from 0), the word as printed now and what the page image
shows, both as JSON strings. The review workflow runs this for an issue
opened by someone with write access; it appends each decision to
`corrections/{work}.jsonl` under their login (applied by the importers,
`importers/corrections.py`), and updates any link quote that contains the
word, so that quotes stay exact. Then `make import` and `make verify` run.
Humans only: an agent never records a correction.

`accept-library` records, as decided by the project owner, every reading
the Anti-Federalist Library suggests for a word the scans could not settle
(decision 56): each line carries `"source": "library"`, and the word stays
marked as unchecked until a person confirms or overrules it on the errata
page. It is run only on the owner's instruction, under their login.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

from tools.common import LINKS_DIR, ROOT, TEXTS_DIR, read_json, read_jsonl

CORRECTIONS_DIR = ROOT / "corrections"
LINE = re.compile(r'^\s*correct\s+(\S+)\s+(\d+)\s+("(?:[^"\\]|\\.)*")\s+("(?:[^"\\]|\\.)*")\s*$')
MAX_PER_ISSUE = 300


def parse(text: str) -> tuple[list[dict], list[str]]:
    """Decisions in an issue body, and the lines that did not parse."""
    out, bad = [], []
    for line in text.splitlines():
        if not line.strip().startswith("correct"):
            continue
        m = LINE.match(line)
        if not m:
            bad.append(line)
            continue
        was, now = json.loads(m.group(3)), json.loads(m.group(4))
        if not now.strip() or "\n" in now or len(now) > 200:
            bad.append(line)
            continue
        out.append({"index": int(m.group(2)), "now": now, "ref": m.group(1), "was": was})
    return out[:MAX_PER_ISSUE], bad


def works_by_prefix() -> dict[str, tuple[str, dict]]:
    out = {}
    for f in sorted(TEXTS_DIR.glob("*.json")):
        doc = read_json(f)
        out[doc.get("ref_prefix", "")] = (doc["id"], {s["ref"]: s for s in doc.get("segments", [])})
    return out


def update_quotes(ref: str, was: str, now: str) -> int:
    """Quotes of links at this passage that contain the old reading once take the new one."""
    changed = 0
    for f in sorted(LINKS_DIR.rglob("*.jsonl")):
        lines, touched = [], False
        for _, l in read_jsonl(f):
            for end, q in (("from", "from_quote"), ("to", "to_quote")):
                if l.get(end) == ref and l.get(q) and l[q].count(was) == 1:
                    l[q] = l[q].replace(was, now)
                    touched = True
                    changed += 1
            lines.append(json.dumps(l, ensure_ascii=False, sort_keys=True))
        if touched:
            f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


def apply(decisions: list[dict], reviewer: str, today: str) -> dict:
    works = works_by_prefix()
    recorded, not_found = [], []
    by_work: dict[str, list[dict]] = {}
    for d in decisions:
        work = next(((wid, segs) for prefix, (wid, segs) in works.items()
                     if prefix and d["ref"].startswith(prefix + ".")), None)
        seg = work[1].get(d["ref"]) if work else None
        spans = seg.get("uncertain", []) if seg else []
        if not seg or not any(seg["text"][s["start"]:s["end"]] == d["was"] for s in spans):
            not_found.append(d["ref"])
            continue
        by_work.setdefault(work[0], []).append({**d, "at": today, "by": reviewer})
    CORRECTIONS_DIR.mkdir(exist_ok=True)
    quotes = 0
    for wid, items in by_work.items():
        path = CORRECTIONS_DIR / f"{wid}.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            for c in items:
                fh.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
                recorded.append(c["ref"])
                if c["now"] != c["was"]:
                    quotes += update_quotes(c["ref"], c["was"], c["now"])
    return {"not_found": not_found, "quotes_updated": quotes, "recorded": len(recorded), "works": sorted(by_work)}


def accept_library(owner: str, today: str) -> dict:
    """Record every Library suggestion as accepted by `owner` (decision 56)."""
    recorded, quotes = 0, 0
    CORRECTIONS_DIR.mkdir(exist_ok=True)
    for f in sorted(TEXTS_DIR.glob("*.json")):
        doc = read_json(f)
        items = []
        for seg in doc.get("segments", []):
            for i, u in enumerate(seg.get("uncertain", [])):
                # Only the Anti-Federalist Library's: the owner's decision of
                # 56 does not cover another tie-breaker's (decision 68).
                if u.get("suggestion") and "accepted" not in u and u.get("suggested_by", "library") == "library":
                    items.append({"at": today, "by": owner, "index": i, "now": u["suggestion"], "ref": seg["ref"],
                                  "source": "library", "was": seg["text"][u["start"]:u["end"]]})
        if not items:
            continue
        with (CORRECTIONS_DIR / f"{doc['id']}.jsonl").open("a", encoding="utf-8") as fh:
            for c in items:
                fh.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
                quotes += update_quotes(c["ref"], c["was"], c["now"])
        recorded += len(items)
    return {"quotes_updated": quotes, "recorded": recorded}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m tools.errata")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply", help="(humans' decisions) record corrections from an errata review issue")
    a.add_argument("--reviewer", required=True)
    a.add_argument("--text", required=True)
    lib = sub.add_parser("accept-library", help="(the owner's decision) accept every Anti-Federalist Library suggestion")
    lib.add_argument("--owner", required=True)
    args = p.parse_args(argv)
    if args.cmd == "accept-library":
        print(json.dumps(accept_library(args.owner, dt.date.today().isoformat()), indent=2))
        return 0
    decisions, bad = parse(Path(args.text).read_text(encoding="utf-8"))
    result = apply(decisions, args.reviewer, dt.date.today().isoformat())
    result["unreadable"] = bad
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
