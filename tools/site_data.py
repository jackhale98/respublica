"""Build everything the site renders from texts/, cases/ and links/.

    python -m tools.site_data    # writes site/.data/

The Astro site only renders what this module produces; every rule about
URLs, page structure, how text is split into runs, and which links are
shown (and how they are flagged) lives here, where it is tested.

Output:
  site/.data/site.json           works, pages, home-page stats
  site/.data/pages/{page}.json   one file per page: blocks to render
  site/.data/refs.json           ref -> {url, label} for every ref
  site/.data/graph/{page}.json   two-hop link neighborhoods of a page's passages
"""

from __future__ import annotations

import re
import shutil
from collections import Counter

from tools.common import ROOT, write_json
from tools.corpus import Corpus, load_corpus

OUT = ROOT / "site" / ".data"

# Site-level settings per work. URLs are permanent once published.
# `paged`: one page per top-level division (otherwise one page for the work).
WORKS = {
    "declaration": {"collection": "founding", "order": 0, "paged": False, "short": "Declaration", "slug": "declaration"},
    "constitution": {"collection": "founding", "order": 1, "paged": False, "short": "Constitution", "slug": "constitution"},
    "amendments": {"collection": "founding", "order": 2, "paged": False, "short": "Amendments", "slug": "amendments"},
    "federalist": {"collection": "federalist", "order": 3, "paged": True, "short": "Federalist", "slug": "federalist"},
}

# Essays and letters of the ratification debate (texts with a `position`)
# get their settings from the text: one page per essay for a series, one
# page for a single piece. Their order: Anti-Federalist, then Federalist,
# then others, each by date.
POSITIONS = ("anti", "federalist", "other")
POSITION_LABELS = {"anti": "Anti-Federalist", "federalist": "Federalist", "other": "Other"}


def debate_settings(corpus: Corpus) -> dict[str, dict]:
    docs = [d for d in corpus.works.values() if d.get("position")]
    docs.sort(key=lambda d: (POSITIONS.index(d["position"]), d.get("date") or "", d["id"]))
    return {d["id"]: {"collection": "ratification", "order": 10 + i, "paged": len(d.get("divisions", [])) > 1,
                      "short": d.get("short", d["title"]), "slug": d["id"]} for i, d in enumerate(docs)}


# Page images of a scan: archive.org "page/n{index}" counts from 0.
SCAN_PAGE_URL = "https://archive.org/details/{item}/page/n{n}"


def scan_url(item: str, leaf: int) -> str:
    return SCAN_PAGE_URL.format(item=item, n=leaf - 1)


def marked_runs(text: str, spans: list[dict]) -> list[dict]:
    """A line of text as runs, with words the scans could not settle carrying
    their readings ("unc")."""
    runs, at = [], 0
    for u in spans:
        if u["start"] > at:
            runs.append({"t": text[at:u["start"]]})
        runs.append({"t": text[u["start"]:u["end"]], "unc": u["readings"]})
        at = u["end"]
    if at < len(text):
        runs.append({"t": text[at:]})
    return runs


LINK_TYPE_LABELS = {
    "quotes": ("quotes", "quoted by"),
    "cites": ("cites", "cited by"),
    "responds_to": ("responds to", "answered by"),
    "rebuts": ("rebuts", "rebutted by"),
    "shared_theme": ("shares a theme with", "shares a theme with"),
    "interprets": ("interprets", "interpreted by"),
    "overrules": ("overrules", "overruled by"),
    "implements": ("implements", "implemented by"),
}


# ------------------------------------------------------------ links


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
            out_label, in_label = LINK_TYPE_LABELS.get(l["type"], (l["type"], l["type"]))
            entry = {
                "confidence": l["confidence"],
                "created_by": l["created_by"].get("kind"),
                "direction": direction,
                "id": l["id"],
                "other": other,
                "other_label": label_for(corpus, other),
                "other_overruled": case_root(other) in overruled,
                "status": l["status"],
                "type": l["type"],
                "verb": out_label if direction == "out" else in_label,
            }
            for key in ("rationale", "source"):
                if l.get(key):
                    entry[key] = l[key]
            here_q, other_q = ("from_quote", "to_quote") if direction == "out" else ("to_quote", "from_quote")
            if l.get(here_q):
                entry["quote"] = l[here_q]
            if l.get(other_q):
                entry["other_quote"] = l[other_q]
            by_ref.setdefault(here, []).append(entry)
    return {"by_ref": by_ref, "overruled": sorted(overruled)}


def short_label(label: str) -> str:
    """Compact caption for graph nodes: "Article I, Section 8, Clause 18" ->
    "Art. I §8 cl. 18"; "Federalist No. 44, ¶ 4" -> "Fed. 44 ¶4";
    "Declaration of Independence, ¶ 2" -> "Decl. ¶2"."""
    s = re.sub(r"^Federalist No\. ", "Fed. ", label)
    s = re.sub(r"^Declaration of Independence, ¶ ", "Decl. ¶", s)
    s = re.sub(r"^Article ", "Art. ", s)
    s = re.sub(r"^Amendment ", "Amend. ", s)
    s = s.replace(", Section ", " §").replace(", Clause ", " cl. ").replace(", ¶ ", " ¶").replace(", note ", " n.")
    return s


def work_key(corpus: Corpus, ref: str) -> str:
    """Which work a ref belongs to (its node color in the graph)."""
    for wid, doc in corpus.works.items():
        prefix = doc.get("ref_prefix", "")
        if ref == prefix or ref.startswith(prefix + "."):
            return wid
    return "other"


def build_graph(links: list[dict], corpus: Corpus, url_for, page_refs: dict[str, list[str]]) -> dict[str, dict]:
    """For each page, the links within two hops of its passages.

    Returns page id -> {"nodes": {ref: {label, short, work, url}},
    "edges": [{id, from, to, type, status, confidence}]}. The reader picks a
    passage and walks this data to draw its one- and two-hop neighborhood.
    """
    live = sorted((l for l in links if l.get("status") != "rejected"), key=lambda l: l["id"])
    adj: dict[str, list[dict]] = {}
    for l in live:
        adj.setdefault(l["from"], []).append(l)
        adj.setdefault(l["to"], []).append(l)

    def node(ref: str) -> dict:
        label = label_for(corpus, ref)
        return {"label": label, "short": short_label(label), "url": url_for(ref), "work": work_key(corpus, ref)}

    out = {}
    for pid, refs in page_refs.items():
        hop0 = {r for r in refs if r in adj}
        hop1 = {(l["to"] if l["from"] == r else l["from"]) for r in hop0 for l in adj[r]}
        edges: dict[str, dict] = {}
        for r in hop0 | hop1:
            for l in adj.get(r, []):
                edges[l["id"]] = {k: l[k] for k in ("id", "from", "to", "type", "status", "confidence")}
        nodes = {r: node(r) for e in edges.values() for r in (e["from"], e["to"])}
        out[pid] = {"edges": sorted(edges.values(), key=lambda e: e["id"]), "nodes": dict(sorted(nodes.items()))}
    return out


def label_for(corpus: Corpus, ref: str) -> str:
    if ref in corpus.segments:
        return corpus.segments[ref].get("label", ref)
    if ref in corpus.divisions:
        return corpus.divisions[ref].get("label", ref)
    return ref


# ------------------------------------------------------------ text runs


def runs_for(segment: dict, changed: list[dict]) -> list[list[list[dict]]]:
    """Split a segment's text into paragraphs -> lines -> runs.

    A run is {"t": text} plus optional "em": true (italics),
    "chg": index into `changed` (a span the National Archives marks as
    changed by an amendment) and "unc": the scans' readings of a word they
    could not settle. Paragraphs are separated by a blank line in the text,
    lines by a single newline.
    """
    text = segment["text"]
    n = len(text)
    em = [False] * n
    chg: list[int | None] = [None] * n
    unc: list[int | None] = [None] * n
    spans = segment.get("uncertain", [])
    for idx, u in enumerate(spans):
        for i in range(u["start"], u["end"]):
            unc[i] = idx
    for a, b in segment.get("emphasis", []):
        for i in range(a, b):
            em[i] = True
    for idx, c in enumerate(changed):
        for i in range(c["start"], c["end"]):
            chg[i] = idx

    paras: list[list[list[dict]]] = [[[]]]
    i = 0
    while i < n:
        if text.startswith("\n\n", i):
            paras.append([[]])
            i += 2
            continue
        if text[i] == "\n":
            paras[-1].append([])
            i += 1
            continue
        j = i
        while j < n and text[j] != "\n" and em[j] == em[i] and chg[j] == chg[i] and unc[j] == unc[i]:
            j += 1
        run: dict = {"t": text[i:j]}
        if em[i]:
            run["em"] = True
        if chg[i] is not None:
            run["chg"] = chg[i]
        if unc[i] is not None:
            run["unc"] = spans[unc[i]]["readings"]
        paras[-1][-1].append(run)
        i = j
    return paras


# ------------------------------------------------------------ structure


def work_url(wid: str, settings: dict | None = None) -> str:
    return f"/{(settings or WORKS)[wid]['slug']}/"


def part_slug(work: dict, division_ref: str) -> str:
    return division_ref[len(work["ref_prefix"]) + 1:].lower()


def gutter(ref: str, work: dict, segment: dict) -> str:
    """Short number shown beside a passage (its last ref component)."""
    last = ref.rsplit(".", 1)[-1]
    if segment.get("kind") == "footnote":
        return last.removeprefix("fn")
    return "" if not last[0].isdigit() else last


class SiteBuilder:
    def __init__(self, corpus: Corpus, links: list[dict]):
        self.corpus = corpus
        self.link_index = build_link_index(links, corpus)
        self.settings = {**WORKS, **debate_settings(corpus)}
        self.works = [corpus.works[w] for w in sorted(self.settings, key=lambda k: self.settings[k]["order"])
                      if w in corpus.works]
        missing = set(corpus.works) - set(self.settings)
        if missing:
            raise ValueError(f"works without site settings in tools/site_data.py: {sorted(missing)}")
        self.ref_urls: dict[str, str] = {}
        self._plan_urls()

    # Every segment and division gets a URL before any page is built, so
    # links between works resolve regardless of build order.
    def _plan_urls(self) -> None:
        for work in self.works:
            wid = work["id"]
            base = work_url(wid, self.settings)
            self.ref_urls[work["ref_prefix"]] = base
            tops = [d for d in work.get("divisions", []) if d["level"] == 1]
            for d in work.get("divisions", []):
                if self.settings[wid]["paged"]:
                    top = next(t for t in tops if d["ref"] == t["ref"] or d["ref"].startswith(t["ref"] + "."))
                    page = f"{base}{part_slug(work, top['ref'])}/"
                    self.ref_urls[d["ref"]] = page if d is top else f"{page}#{d['ref']}"
                else:
                    self.ref_urls[d["ref"]] = f"{base}#{d['ref']}"
            for s in work["segments"]:
                top = self._top_division(work, s["ref"])
                if self.settings[wid]["paged"] and top:
                    self.ref_urls[s["ref"]] = f"{base}{part_slug(work, top['ref'])}/#{s['ref']}"
                else:
                    self.ref_urls[s["ref"]] = f"{base}#{s['ref']}"

    def url_for(self, ref: str) -> str | None:
        """URL of any ref. A parent ref with no division of its own (rare)
        points at the first passage under it."""
        if ref in self.ref_urls:
            return self.ref_urls[ref]
        first = next((r for r in self.corpus.segments if r.startswith(ref + ".")), None)
        return self.ref_urls.get(first) if first else None

    @staticmethod
    def _top_division(work: dict, ref: str) -> dict | None:
        for d in work.get("divisions", []):
            if d["level"] == 1 and (ref == d["ref"] or ref.startswith(d["ref"] + ".")):
                return d
        return None

    def _passage(self, work: dict, s: dict) -> dict:
        changed = []
        for c in s.get("changed_by", []):
            start = s["text"].find(c["quote"])
            if start < 0 or not c["quote"]:
                continue
            changed.append({
                "end": start + len(c["quote"]),
                "label": self.corpus.divisions.get(c["amendment"], {}).get("label", c["amendment"]),
                "ref": c["amendment"],
                "start": start,
                "url": self.url_for(c["amendment"]),
            })
        conns = []
        for e in self.link_index["by_ref"].get(s["ref"], []):
            conns.append({**e, "other_url": self.url_for(e["other"])})
        block = {
            "changed": changed,
            "connections": conns,
            "gutter": gutter(s["ref"], work, s),
            "label": s.get("label", s["ref"]),
            "paras": runs_for(s, changed),
            "ref": s["ref"],
            "type": "passage",
        }
        if s.get("kind"):
            block["kind"] = s["kind"]
        if s.get("scan"):
            leaves = s["scan"]["leaves"]
            pages = s.get("pages", [])
            block["scan"] = {"pages": pages, "url": scan_url(s["scan"]["item"], leaves[0])}
            block["uncertain"] = len(s.get("uncertain", []))
        return block

    def _blocks(self, work: dict, segments: list[dict], heading_levels: tuple[int, ...]) -> list[dict]:
        """Passages in order, with a heading before the first passage under
        each division whose level is in heading_levels."""
        divs = [d for d in work.get("divisions", []) if d["level"] in heading_levels]
        first_under: dict[str, list[dict]] = {}
        for d in divs:
            first = next((s for s in segments if s["ref"] == d["ref"] or s["ref"].startswith(d["ref"] + ".")), None)
            if first:
                first_under.setdefault(first["ref"], []).append(d)
        blocks = []
        for s in segments:
            for d in sorted(first_under.get(s["ref"], []), key=lambda x: x["level"]):
                h = {"label": d["label"], "level": d["level"], "ref": d["ref"], "type": "heading"}
                # A division that is itself a passage (the Preamble) is anchored by the passage.
                if d["ref"] not in self.corpus.segments:
                    h["anchor"] = d["ref"]
                if d.get("notes"):
                    h["notes"] = [n["text"] for n in d["notes"]]
                blocks.append(h)
            blocks.append(self._passage(work, s))
        return blocks

    def _toc(self, work: dict, levels: tuple[int, ...]) -> list[dict]:
        out = []
        for d in work.get("divisions", []):
            if d["level"] in levels:
                out.append({"label": d["label"], "level": d["level"], "ref": d["ref"], "url": self.url_for(d["ref"])})
        return out

    def _attribution(self, attr: dict | None) -> dict | None:
        if not attr:
            return None
        kind = attr.get("kind")
        names = attr.get("names", [])
        if kind == "disputed":
            text = " or ".join(names)
        elif kind == "pseudonym":
            text = f"{attr['pseudonym']} ({', '.join(names)})"
        else:
            text = " and ".join(names)
        out = {"kind": kind, "names": names, "text": text}
        for key in ("byline", "source"):
            if attr.get(key):
                out[key] = attr[key]
        return out

    @staticmethod
    def _header(d: dict) -> dict:
        """A division's heading lines, salutation and signature as runs, with
        the words the scans could not settle marked."""
        unc = d.get("uncertain", {})
        out = {"publication": [marked_runs(t, unc.get(f"publication.{i}", [])) for i, t in enumerate(d.get("publication", []))]}
        for key in ("salutation", "signature"):
            if d.get(key):
                out[key] = marked_runs(d[key], unc.get(key, []))
        return out

    def build(self) -> tuple[dict, dict[str, dict]]:
        pages: dict[str, dict] = {}
        works_out = []
        for work in self.works:
            wid = work["id"]
            cfg = self.settings[wid]
            tops = [d for d in work.get("divisions", []) if d["level"] == 1]
            info = {
                "attribution": self._attribution(work.get("attribution")),
                "words": sum(len(s["text"].split()) for s in work["segments"] if s.get("kind") != "footnote"),
                "collection": cfg["collection"],
                "date": work.get("date"),
                "edition": work["edition"],
                "id": wid,
                "passages": sum(1 for s in work["segments"] if s.get("kind") != "footnote"),
                "short": cfg["short"],
                "source_ids": work["source_ids"],
                "title": work["title"],
                "top_divisions": len(tops),
                "url": work_url(wid, self.settings),
            }
            if work.get("position"):
                info["position"] = work["position"]
            if work.get("position"):
                notes = sum(1 for s in work["segments"] if s.get("kind") == "footnote")
                info["notes"] = notes
            if not cfg["paged"]:
                pid = wid
                single = work.get("position") and len(work.get("divisions", [])) == 1
                body = [s for s in work["segments"] if not (single and s.get("kind") == "footnote")]
                pages[pid] = {
                    "blocks": self._blocks(work, body, () if single else (1, 2)),
                    "id": pid,
                    "kind": "work",
                    "title": work["title"],
                    "toc": [] if single else self._toc(work, (1, 2)),
                    "url": info["url"],
                    "work": self._work_ref(info),
                }
                if single:
                    d = work["divisions"][0]
                    pages[pid]["division"] = {"header": self._header(d), "label": d["label"], "ref": d["ref"]}
                    pages[pid]["notes"] = self._blocks(work, [s for s in work["segments"] if s.get("kind") == "footnote"], ())
            else:
                parts = []
                for i, d in enumerate(tops):
                    segs = [s for s in work["segments"] if s["ref"].startswith(d["ref"] + ".")]
                    body = [s for s in segs if s.get("kind") != "footnote"]
                    notes = [s for s in segs if s.get("kind") == "footnote"]
                    pid = f"{wid}-{part_slug(work, d['ref'])}"
                    part = {
                        "attribution": self._attribution(d.get("attribution")),
                        "label": d["label"],
                        "numeral": d.get("numeral"),
                        "passages": len(body),
                        "publication": d.get("publication", []),
                        "ref": d["ref"],
                        "title": d.get("title"),
                        "url": self.url_for(d["ref"]),
                        "words": sum(len(s["text"].split()) for s in body),
                    }
                    parts.append(part)
                    pages[pid] = {
                        "blocks": self._blocks(work, body, ()),
                        "division": {
                            **part,
                            "header": self._header(d),
                            "notes": [n["text"] for n in d.get("notes", [])],
                            "salutation": d.get("salutation"),
                            "signature": d.get("signature"),
                            "variants": d.get("variants", []),
                        },
                        "id": pid,
                        "kind": "part",
                        "notes": self._blocks(work, notes, ()),
                        "title": f"{d['label']}" + (f": {d['title']}" if d.get("title") else ""),
                        "url": part["url"],
                        "work": self._work_ref(info),
                    }
                ids = [f"{wid}-{part_slug(work, d['ref'])}" for d in tops]
                for i, pid in enumerate(ids):
                    pages[pid]["prev"] = self._nav(pages[ids[i - 1]]) if i > 0 else None
                    pages[pid]["next"] = self._nav(pages[ids[i + 1]]) if i + 1 < len(ids) else None
                info["parts"] = parts
                info["authors"] = dict(Counter(p["attribution"]["kind"] if p["attribution"]["kind"] != "single"
                                               else p["attribution"]["names"][0] for p in parts if p["attribution"]))
                pages[wid] = {"id": wid, "kind": "index", "title": work["title"], "url": info["url"],
                              "work": self._work_ref(info), "parts": parts}
            works_out.append(info)

        debate = [w for w in works_out if w["collection"] == "ratification"]
        if debate:
            pages["ratification"] = {
                "groups": [{"key": k, "label": POSITION_LABELS[k],
                            "works": [w["id"] for w in debate if w.get("position") == k]}
                           for k in POSITIONS if any(w.get("position") == k for w in debate)],
                "id": "ratification", "kind": "collection", "title": "The Ratification Debate",
                "url": "/ratification/",
            }

        site = {
            "pages": [{"id": p["id"], "kind": p["kind"], "url": p["url"]} for p in pages.values()],
            "stats": {
                "connections": sum(len(v) for v in self.link_index["by_ref"].values()) // 2,
                "passages": sum(w["passages"] for w in works_out),
                "works": len(works_out),
            },
            "works": works_out,
        }
        preamble = self.corpus.segments.get("Constitution.Preamble")
        if preamble:
            site["featured"] = {"label": preamble["label"], "ref": preamble["ref"], "text": preamble["text"],
                                "url": self.url_for(preamble["ref"])}
        return site, pages

    @staticmethod
    def _work_ref(info: dict) -> dict:
        return {"id": info["id"], "short": info["short"], "title": info["title"], "url": info["url"]}

    @staticmethod
    def _nav(page: dict) -> dict:
        d = page["division"]
        return {"label": d["label"], "title": d.get("title"), "url": page["url"]}


def build(corpus: Corpus, links: list[dict]) -> tuple[dict, dict[str, dict], dict[str, dict], dict[str, dict]]:
    b = SiteBuilder(corpus, links)
    site, pages = b.build()
    refs = {ref: {"label": label_for(corpus, ref), "url": url} for ref, url in sorted(b.ref_urls.items())}
    page_refs = {
        pid: [blk["ref"] for blk in p.get("blocks", []) + p.get("notes", []) if blk["type"] == "passage"]
        for pid, p in pages.items() if p["kind"] in ("work", "part")
    }
    graphs = build_graph(links, corpus, b.url_for, page_refs)
    return site, pages, refs, graphs


def main() -> None:
    from tools.verify import load_links

    corpus = load_corpus()
    links = [rec for _, _, rec in load_links()]
    site, pages, refs, graphs = build(corpus, links)
    if OUT.exists():
        shutil.rmtree(OUT)
    write_json(OUT / "site.json", site)
    write_json(OUT / "refs.json", refs)
    for pid, page in pages.items():
        write_json(OUT / "pages" / f"{pid}.json", page)
    for pid, graph in graphs.items():
        write_json(OUT / "graph" / f"{pid}.json", graph)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(pages)} pages, {len(refs)} refs")


if __name__ == "__main__":
    main()
