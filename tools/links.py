"""Write and review links.

    python -m tools.links propose  --batch fed-const-10 --decisions decisions.json --run RUN [--model NAME]
    python -m tools.links review   [--batch BATCH] --reviewer NAME        # a human, interactively
    python -m tools.links apply    --reviewer LOGIN --text FILE           # a human's decisions, from a review issue
    python -m tools.links sample   [--n 20] [--seed 1]                    # spot-check sheet (Markdown)

`propose` is how agents (and people) add links. It never trusts typed
quotes: each quote is located in the passage (allowing only the
whitespace / quote-mark normalization of docs/editions.md) and the exact
text from the passage file is stored. It assigns ids, refuses duplicates,
and writes only `status: "suggested"` records to links/proposed/{batch}.jsonl.

`review` is for a human. Reviewed links move to links/{batch}.jsonl and
rejected ones to links/rejected/{batch}.jsonl, so they are not proposed
again. Agents must never run it (CLAUDE.md rule 4).

`apply` records decisions a human made on the site's review page, which
opens a GitHub issue listing them ("approve lnk_…" / "reject lnk_… — note").
The review workflow runs it only for issues opened by someone with write
access to the repository, under their GitHub login
(.github/workflows/review.yml, docs/linking.md "Reviewing links"). Agents
must never run it either.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import sys
from pathlib import Path

from tools.common import LINKS_DIR, ROOT, normalize_for_match, read_jsonl
from tools.corpus import Corpus, load_corpus

PROPOSED_DIR = LINKS_DIR / "proposed"
REJECTED_DIR = LINKS_DIR / "rejected"
BATCH_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
TYPES = ("quotes", "cites", "responds_to", "rebuts", "shared_theme", "interprets", "overrules", "implements")
CONFIDENCE = ("high", "medium", "low")


class LinkError(ValueError):
    pass


# ------------------------------------------------------------ quotes


def locate(text: str, quote: str) -> str:
    """Return the exact substring of `text` that `quote` matches after
    normalizing whitespace and quote-mark style. Raises if absent or ambiguous
    is irrelevant: the first occurrence is used (the substring is identical)."""
    target = normalize_for_match(quote)
    if not target:
        raise LinkError("empty quote")
    # Build the normalized text with a map back to original offsets.
    norm_chars: list[str] = []
    origin: list[int] = []
    prev_space = True
    for i, ch in enumerate(text):
        n = normalize_for_match(ch) if not ch.isspace() and ch != " " else " "
        if n == " " or n == "":
            if not prev_space:
                norm_chars.append(" ")
                origin.append(i)
            prev_space = True
            continue
        norm_chars.append(n)
        origin.append(i)
        prev_space = False
    norm = "".join(norm_chars)
    at = norm.find(target)
    if at < 0:
        raise LinkError(f"quote not found in passage: {quote[:80]!r}")
    start = origin[at]
    end = origin[at + len(target) - 1] + 1
    return text[start:end]


def resolve_quote(corpus: Corpus, ref: str, quote: str) -> str:
    """Exact text for a quote on `ref` (a segment, or any segment under a parent)."""
    passages = corpus.passages(ref)
    if not passages:
        raise LinkError(f"ref {ref} has no passages")
    for p in passages:
        try:
            return locate(p["text"], quote)
        except LinkError:
            continue
    raise LinkError(f"quote not found in {ref}: {quote[:80]!r}")


# ------------------------------------------------------------ files


def all_link_files() -> list[Path]:
    return sorted(LINKS_DIR.rglob("*.jsonl")) if LINKS_DIR.exists() else []


def existing_links() -> list[dict]:
    out = []
    for path in all_link_files():
        out.extend(rec for _, rec in read_jsonl(path))
    return out


def dumps_line(rec: dict) -> str:
    return json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n"


def batch_id_prefix(batch: str) -> str:
    return "lnk_" + re.sub(r"[^a-z0-9]+", "_", batch.lower()).strip("_") + "_"


# ------------------------------------------------------------ propose


def build_records(corpus: Corpus, batch: str, decisions: list[dict], run: str, model: str,
                  today: str, existing: list[dict]) -> tuple[list[dict], list[str]]:
    """Validate decisions and turn them into link records. Returns (records, skipped messages)."""
    if not BATCH_RE.match(batch):
        raise LinkError(f"batch must match {BATCH_RE.pattern}")
    prefix = batch_id_prefix(batch)
    used = {r.get("id") for r in existing}
    taken = {(r.get("from"), r.get("to"), r.get("type")) for r in existing}
    n = 1 + max([int(i[len(prefix):]) for i in used if isinstance(i, str) and i.startswith(prefix)
                 and i[len(prefix):].isdigit()] or [0])
    records, skipped = [], []
    for k, d in enumerate(decisions, 1):
        where = f"decision {k}"
        unknown = set(d) - {"from", "to", "type", "confidence", "rationale", "from_quote", "to_quote"}
        if unknown:
            raise LinkError(f"{where}: unknown keys {sorted(unknown)}")
        for key in ("from", "to", "type", "confidence", "rationale"):
            if not isinstance(d.get(key), str) or not d[key].strip():
                raise LinkError(f"{where}: {key} is required")
        if d["type"] not in TYPES:
            raise LinkError(f"{where}: unknown type {d['type']!r}")
        if d["confidence"] not in CONFIDENCE:
            raise LinkError(f"{where}: confidence must be one of {CONFIDENCE}")
        for end in ("from", "to"):
            if not corpus.exists(d[end]):
                raise LinkError(f"{where}: {end} ref {d[end]!r} does not exist")
        key = (d["from"], d["to"], d["type"])
        if key in taken:
            skipped.append(f"{where}: {d['from']} -> {d['to']} ({d['type']}) already exists; skipped")
            continue
        rec = {
            "confidence": d["confidence"],
            "created_at": today,
            "created_by": {"kind": "agent", "model": model, "run": run},
            "from": d["from"],
            "id": f"{prefix}{n:03d}",
            "rationale": d["rationale"].strip(),
            "reviewed_by": None,
            "status": "suggested",
            "to": d["to"],
            "type": d["type"],
        }
        for end in ("from", "to"):
            q = d.get(f"{end}_quote")
            if q:
                rec[f"{end}_quote"] = resolve_quote(corpus, d[end], q)
        records.append(rec)
        taken.add(key)
        n += 1
    return records, skipped


def cmd_propose(args) -> int:
    corpus = load_corpus()
    decisions = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
    if not isinstance(decisions, list):
        print("error: decisions file must hold a JSON list", file=sys.stderr)
        return 2
    try:
        records, skipped = build_records(corpus, args.batch, decisions, args.run, args.model,
                                         dt.date.today().isoformat(), existing_links())
    except LinkError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for s in skipped:
        print(s)
    if records:
        PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
        path = PROPOSED_DIR / f"{args.batch}.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            for rec in records:
                fh.write(dumps_line(rec))
        print(f"wrote {len(records)} suggested link(s) to {path.relative_to(ROOT)}")
    else:
        print("no new links")
    return 0


# ------------------------------------------------------------ review (human)


def _show(corpus: Corpus, rec: dict) -> None:
    def passage(ref: str) -> str:
        ps = corpus.passages(ref)
        return "\n".join(p["text"] for p in ps)[:1500]
    print("=" * 78)
    print(f"{rec['id']}  [{rec['type']}, {rec['confidence']}]  {rec['from']}  ->  {rec['to']}")
    print(f"why: {rec.get('rationale') or rec.get('source')}")
    if rec.get("from_quote"):
        print(f"from_quote: “{rec['from_quote']}”")
    if rec.get("to_quote"):
        print(f"to_quote:   “{rec['to_quote']}”")
    print(f"\n--- {rec['from']}\n{passage(rec['from'])}\n\n--- {rec['to']}\n{passage(rec['to'])}\n")


def record_decision(rec: dict, path: Path, approve: bool, reviewer: str, today: str, note: str = "") -> None:
    """Move one suggested link to links/{batch}.jsonl (reviewed) or
    links/rejected/{batch}.jsonl, recording who decided and when."""
    rec = {**rec, "reviewed_at": today, "reviewed_by": reviewer, "status": "reviewed" if approve else "rejected"}
    if note:
        rec["review_note"] = note
    dest = (LINKS_DIR if approve else REJECTED_DIR) / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(dumps_line(rec))


def cmd_review(args) -> int:
    corpus = load_corpus()
    files = [PROPOSED_DIR / f"{args.batch}.jsonl"] if args.batch else sorted(PROPOSED_DIR.glob("*.jsonl"))
    today = dt.date.today().isoformat()
    for path in files:
        if not path.exists():
            continue
        recs = [r for _, r in read_jsonl(path)]
        keep: list[dict] = []
        for i, rec in enumerate(recs):
            _show(corpus, rec)
            ans = input("[a]ccept as reviewed / [r]eject / [s]kip / [q]uit > ").strip().lower()
            if ans == "q":
                keep.extend(recs[i:])
                break
            if ans in ("a", "r"):
                record_decision(rec, path, ans == "a", args.reviewer, today)
            else:
                keep.append(rec)
        if keep:
            path.write_text("".join(dumps_line(r) for r in keep), encoding="utf-8")
        else:
            path.unlink()
        if ans == "q":
            break
    print("done; run make verify")
    return 0


# ------------------------------------------------------------ apply (a human's decisions)

# One decision per line, as the review page writes them. Anything else in
# the issue (the heading, a person's own words) is ignored.
DECISION_LINE = re.compile(r"^\s*(approve|reject)\s+(lnk_[a-z0-9_]{1,80})(?:\s+[—–-]+\s+(.*))?\s*$")
LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


def parse_decisions(text: str) -> list[tuple[str, bool, str]]:
    """(id, approve, note) for each decision line; the last line for an id wins."""
    out: dict[str, tuple[str, bool, str]] = {}
    for line in text.splitlines():
        m = DECISION_LINE.match(line)
        if m:
            note = re.sub(r"[\x00-\x1f\x7f]", "", m.group(3) or "").strip()[:500]
            out[m.group(2)] = (m.group(2), m.group(1) == "approve", note)
    return list(out.values())


def apply_decisions(decisions: list[tuple[str, bool, str]], reviewer: str, today: str) -> dict:
    """Record each decision on a link still in links/proposed/. Returns
    counts and the ids that were not found (already decided, or mistyped)."""
    if not LOGIN.match(reviewer):
        raise LinkError(f"not a GitHub login: {reviewer!r}")
    wanted = {i: (a, n) for i, a, n in decisions}
    done = {"approved": 0, "rejected": 0, "not_found": []}
    for path in sorted(PROPOSED_DIR.glob("*.jsonl")):
        recs = [r for _, r in read_jsonl(path)]
        keep = []
        for rec in recs:
            if rec["id"] in wanted:
                approve, note = wanted.pop(rec["id"])
                record_decision(rec, path, approve, reviewer, today, note)
                done["approved" if approve else "rejected"] += 1
            else:
                keep.append(rec)
        if len(keep) != len(recs):
            if keep:
                path.write_text("".join(dumps_line(r) for r in keep), encoding="utf-8")
            else:
                path.unlink()
    done["not_found"] = sorted(wanted)
    return done


def cmd_apply(args) -> int:
    decisions = parse_decisions(Path(args.text).read_text(encoding="utf-8"))
    result = apply_decisions(decisions, args.reviewer, dt.date.today().isoformat())
    print(json.dumps(result, indent=2))
    return 0


# ------------------------------------------------------------ sample


def cmd_sample(args) -> int:
    corpus = load_corpus()
    recs = [r for path in sorted(PROPOSED_DIR.glob("*.jsonl")) for _, r in read_jsonl(path)]
    rng = random.Random(args.seed)
    pick = sorted(rng.sample(recs, min(args.n, len(recs))), key=lambda r: r["id"])
    print(f"# Spot-check sample: {len(pick)} of {len(recs)} suggested links (seed {args.seed})\n")
    for r in pick:
        frm = corpus.passages(r["from"])
        print(f"## {r['id']}: {r['from']} {r['type']} {r['to']} ({r['confidence']})\n")
        print(f"- Rationale: {r['rationale']}")
        if r.get("from_quote"):
            print(f"- From: “{r['from_quote']}”")
        if r.get("to_quote"):
            print(f"- To: “{r['to_quote']}”")
        to = corpus.passages(r["to"])
        if to:
            print(f"- {r['to']} reads: {to[0]['text'][:400]}")
        if frm and not r.get("from_quote"):
            print(f"- {r['from']} reads: {frm[0]['text'][:400]}")
        print("- [ ] correct  - [ ] wrong type  - [ ] wrong target  - [ ] not a citation\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m tools.links")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("propose", help="add suggested links from a decisions file")
    a.add_argument("--batch", required=True)
    a.add_argument("--decisions", required=True)
    a.add_argument("--run", required=True)
    a.add_argument("--model", default="Claude")
    r = sub.add_parser("review", help="(humans only) mark suggested links reviewed or rejected")
    r.add_argument("--batch")
    r.add_argument("--reviewer", required=True)
    s = sub.add_parser("sample", help="print a spot-check sheet of suggested links")
    s.add_argument("--n", type=int, default=20)
    s.add_argument("--seed", type=int, default=1)
    ap_ = sub.add_parser("apply", help="(a human's decisions) record approvals and rejections listed in a file")
    ap_.add_argument("--reviewer", required=True, help="the GitHub login of the person who decided")
    ap_.add_argument("--text", required=True, help="text with one 'approve lnk_…' or 'reject lnk_… — note' per line")
    args = p.parse_args(argv)
    return {"propose": cmd_propose, "review": cmd_review, "sample": cmd_sample, "apply": cmd_apply}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
