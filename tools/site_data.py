"""Derive the data the site needs from links/ and the corpus.

    python -m tools.site_data    # writes site/.data/links.json

The site never reads links/ directly; it reads this file, so every rule
about which links are shown (and how they are flagged) lives here.
"""

from __future__ import annotations

from tools.common import ROOT, write_json
from tools.corpus import Corpus, load_corpus

OUT = ROOT / "site" / ".data" / "links.json"


def case_root(ref: str) -> str:
    parts = ref.split(".")
    return ".".join(parts[:2]) if parts[0] == "Case" else ref


def build_link_index(links: list[dict], corpus: Corpus) -> dict:
    """Index non-rejected links by both endpoints.

    Each entry describes the link from the point of view of one endpoint:
    `other` is the far end, and `other_overruled` is set whenever the far
    end is (part of) a case that some non-rejected `overrules` link targets.
    """
    live = [l for l in links if l.get("status") != "rejected"]
    overruled = {case_root(l["to"]) for l in live if l.get("type") == "overrules"}
    by_ref: dict[str, list[dict]] = {}
    for l in sorted(live, key=lambda x: x["id"]):
        for here, other, direction in ((l["from"], l["to"], "out"), (l["to"], l["from"], "in")):
            entry = {
                "confidence": l["confidence"],
                "direction": direction,
                "id": l["id"],
                "other": other,
                "other_label": _label(corpus, other),
                "other_overruled": case_root(other) in overruled,
                "status": l["status"],
                "type": l["type"],
            }
            for key in ("rationale", "source"):
                if l.get(key):
                    entry[key] = l[key]
            here_q, other_q = ("from_quote", "to_quote") if direction == "out" else ("to_quote", "from_quote")
            if l.get(here_q):
                entry["quote"] = l[here_q]
            if l.get(other_q):
                entry["other_quote"] = l[other_q]
            entry["created_by"] = l["created_by"].get("kind")
            by_ref.setdefault(here, []).append(entry)
    return {"by_ref": by_ref, "overruled": sorted(overruled)}


def _label(corpus: Corpus, ref: str) -> str:
    if ref in corpus.segments:
        return corpus.segments[ref].get("label", ref)
    if ref in corpus.divisions:
        return corpus.divisions[ref].get("label", ref)
    return ref


def main() -> None:
    from tools.verify import load_links

    corpus = load_corpus()
    links = [rec for _, _, rec in load_links()]
    write_json(OUT, build_link_index(links, corpus))
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
