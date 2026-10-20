"""Review sheet for words the OCR scans could not settle (docs/ocr.md).

    python -m tools.uncertain                 # counts per work
    python -m tools.uncertain cato            # every uncertain word in a work
    python -m tools.uncertain cato --md > review.md

Each entry gives the ref, the word in context, every scan's reading and a
link to the page image, so a person can check it against the printed page
and record what the page says in docs/errata.md. Read-only.
"""

from __future__ import annotations

import argparse
import sys

from tools.corpus import load_corpus
from tools.site_data import scan_url


def entries(doc: dict) -> list[dict]:
    """Uncertain words in passages and in essay headings, in text order."""
    out = []
    segments = {s["ref"]: s for s in doc["segments"]}
    for d in doc.get("divisions", []):
        for field, spans in d.get("uncertain", {}).items():
            head, _, idx = field.partition(".")
            text = d[head][int(idx)] if head == "publication" else d[head]
            under = [s for r, s in segments.items() if r.startswith(d["ref"] + ".") and s.get("kind") != "footnote"]
            # Heading lines are on the essay's first page, the signature on its last.
            seg = (under[-1] if head == "signature" else under[0]) if under else None
            for u in spans:
                out.append(_entry(f"{d['ref']} ({field})", text, u, seg))
        for s in doc["segments"]:
            if s["ref"].startswith(d["ref"] + ".") or (len(doc["divisions"]) == 1 and s["ref"].startswith(doc["ref_prefix"] + ".")):
                for u in s.get("uncertain", []):
                    out.append(_entry(s["ref"], s["text"], u, s))
    if not doc.get("divisions"):  # a work of one part (the road to independence, decision 66)
        for s in doc["segments"]:
            for u in s.get("uncertain", []):
                out.append(_entry(s["ref"], s["text"], u, s))
    return out


def _entry(where: str, text: str, u: dict, seg: dict | None) -> dict:
    before = text[:u["start"]].split()[-6:]
    after = text[u["end"]:].split()[:6]
    scan = (seg or {}).get("scan")
    return {
        "context": " ".join(before + [f"[{text[u['start']:u['end']]}]"] + after),
        "page": ", ".join((seg or {}).get("pages", [])),
        "readings": u["readings"],
        "ref": where,
        "suggestion": u.get("suggestion"),
        "suggested_by": u.get("suggested_by"),
        "url": scan_url(scan["item"], scan["leaves"][0], scan.get("site", "archive.org"), scan) if scan else "",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("work", nargs="?", help="work id (texts/{work}.json); omit for counts")
    ap.add_argument("--md", action="store_true", help="Markdown checklist")
    args = ap.parse_args(argv)
    corpus = load_corpus()
    ocr = {wid: d for wid, d in corpus.works.items() if any("scan" in s for s in d["segments"])}
    if not args.work:
        total_w = total_u = 0
        for wid, d in sorted(ocr.items()):
            words = sum(len(s["text"].split()) for s in d["segments"])
            n = len(entries(d))
            total_w, total_u = total_w + words, total_u + n
            print(f"{wid:30} {words:7} words {n:4} uncertain")
        print(f"{'total':30} {total_w:7} words {total_u:4} uncertain")
        return 0
    if args.work not in ocr:
        print(f"no work read from scans named {args.work!r}; choose from: {', '.join(sorted(ocr))}", file=sys.stderr)
        return 1
    for e in entries(ocr[args.work]):
        readings = "; ".join(f"{k}: {v}" for k, v in sorted(e["readings"].items()))
        if e["suggestion"]:
            who = "Library of Congress transcription" if e["suggested_by"] == "loc" else "Anti-Federalist Library"
            readings += f"; {who} (a suggestion, not a scan): {e['suggestion']}"
        if args.md:
            print(f"- [ ] `{e['ref']}` p. {e['page'] or '?'}: {e['context']}  \n  scans: {readings}  \n  page image: {e['url']}")
        else:
            print(f"{e['ref']}\n  {e['context']}\n  {readings}\n  p. {e['page'] or '?'}  {e['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
