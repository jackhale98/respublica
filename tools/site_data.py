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
  site/.data/preview/{ref}.json  the far ends of a passage's connections, to read in the panel
  site/.data/map.json            the overview map: links and cases along the founding documents
  site/.data/review/index.json   suggested links awaiting review, by batch
  site/.data/review/{batch}.json one batch's suggested links, with both passages
  site/.data/errata/index.json   words the scans could not settle, by work
  site/.data/errata/{work}.json  one work's uncertain words, with context and page images
"""

from __future__ import annotations

import re
import shutil
from collections import Counter

from tools.common import ROOT, read_json, write_json
from tools.corpus import Corpus, load_corpus

OUT = ROOT / "site" / ".data"

# Site-level settings per work. URLs are permanent once published.
# `paged`: one page per top-level division (otherwise one page for the work).
WORKS = {
    "declaration": {"collection": "founding", "order": 0, "paged": False, "short": "Declaration", "slug": "declaration"},
    "constitution": {"collection": "founding", "order": 1, "paged": False, "short": "Constitution", "slug": "constitution"},
    "amendments": {"collection": "founding", "order": 2, "paged": False, "short": "Amendments", "slug": "amendments"},
    "joint-resolution-1789": {"collection": "founding", "order": 2.5, "paged": False, "short": "Resolution of 1789",
                              "slug": "joint-resolution-1789"},
    "federalist": {"collection": "federalist", "order": 3, "paged": True, "short": "Federalist", "slug": "federalist"},
    # Debates in Congress (decision 46): one page per day.
    "house-amendments-1789": {"collection": "congress", "order": 4, "paged": True, "short": "House debates, 1789",
                              "slug": "house-amendments-1789", "group": "The Bill of Rights, 1789",
                              "printed_in": "Annals of Congress",
                              "summary": "The House of Representatives' proceedings on the amendments that became the "
                                         "Bill of Rights: every item printed under the heading “Amendments to the "
                                         "Constitution” in the Annals of Congress, from James Madison's speech of "
                                         "June 8 to the House's last vote on the articles."},
    "house-fourteenth-amendment-1866": {
        "collection": "congress", "order": 5, "paged": True, "short": "House debates, 1866",
        "slug": "house-fourteenth-amendment-1866", "group": "The Fourteenth Amendment, 1866",
        "printed_in": "Congressional Globe",
        "summary": "The House of Representatives' debate on the joint resolution (H. R. No. 127) proposing the "
                   "Fourteenth Amendment: every item headed “Reconstruction” in which the House took it up, as "
                   "printed in the Congressional Globe, from Thaddeus Stevens's opening of May 8 to the vote on the "
                   "Senate's amendments on June 13."},
    "senate-fourteenth-amendment-1866": {
        "collection": "congress", "order": 6, "paged": True, "short": "Senate debates, 1866",
        "slug": "senate-fourteenth-amendment-1866", "group": "The Fourteenth Amendment, 1866",
        "printed_in": "Congressional Globe",
        "summary": "The Senate's debate on the joint resolution (H. R. No. 127) proposing the Fourteenth "
                   "Amendment: every item headed “Reconstruction” in which the Senate took it up, as printed in "
                   "the Congressional Globe, from Jacob Howard's opening of May 23 to the vote of June 8."},
}

# Collections of works shown on one page each.
CONGRESS_GROUPS = ("The Bill of Rights, 1789", "The Fourteenth Amendment, 1866")

# Essays and letters of the ratification debate (texts with a `position`)
# get their settings from the text: one page per essay for a series, one
# page for a single piece. Their order: Anti-Federalist, then Federalist,
# then others, each by date.
POSITIONS = ("anti", "federalist", "other")
POSITION_LABELS = {"anti": "Anti-Federalist", "federalist": "Federalist", "other": "Other"}


# What a ratification-debate work's parts are called, where not essays.
PARTS = {"patrick-henry": "speeches"}


def debate_settings(corpus: Corpus) -> dict[str, dict]:
    docs = [d for d in corpus.works.values() if d.get("position")]
    docs.sort(key=lambda d: (POSITIONS.index(d["position"]), d.get("date") or "", d["id"]))
    return {d["id"]: {"collection": "ratification", "order": 10 + i, "paged": len(d.get("divisions", [])) > 1,
                      "short": d.get("short", d["title"]), "slug": d["id"]} for i, d in enumerate(docs)}


def case_settings(corpus: Corpus) -> dict[str, dict]:
    """Supreme Court cases (cases/): one page each, at /cases/{cluster_id}/,
    in date order."""
    docs = [d for d in corpus.works.values() if d.get("ref_prefix", "").startswith("Case.")]
    docs.sort(key=lambda d: (d.get("date") or "", d["id"]))
    return {d["id"]: {"collection": "cases", "order": 1000 + i, "paged": False, "short": d["title"],
                      "slug": f"cases/{d['id']}"} for i, d in enumerate(docs)}


# Page images of a scan: archive.org "page/n{index}" counts from 0.
SCAN_PAGE_URL = "https://archive.org/details/{item}/page/n{n}"


# Page images in the UNT Digital Library (the Congressional Globe): "m1/{n}" counts from 1.
UNT_PAGE_URL = "https://digital.library.unt.edu/ark:/67531/{item}/m1/{n}/"
# Page images shown on the errata page (its Content Security Policy allows these hosts).
SCAN_IMAGE_URL = "https://archive.org/download/{item}/page/n{n}_w1200.jpg"
UNT_IMAGE_URL = "https://digital.library.unt.edu/ark:/67531/{item}/m1/{n}/med_res/"
# Newspaper pages in the Library of Congress's Chronicling America (the
# New-York Journal): the issue's page, and on the errata page the region of
# the page the paragraph fills (IIIF, cropped), since a whole newspaper page
# is too large to read at screen size.
LOC_PAGE_URL = "https://www.loc.gov/resource/{item}/{issue}/ed-1/?sp={n}"
LOC_IMAGE_URL = "https://tile.loc.gov/image-services/iiif/{image}/pct:{x},{y},{w},{h}/pct:100/0/default.jpg"
LOC_IMAGE_ID = re.compile(r"^service(?::[A-Za-z0-9_-]+)+$")
LOC_ISSUE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def scan_url(item: str, leaf: int, site: str = "archive.org", scan: dict | None = None) -> str:
    if site == "unt":
        return UNT_PAGE_URL.format(item=item, n=leaf)
    if site == "loc":
        if not LOC_ISSUE.match(scan["issue"]):
            raise ValueError(f"unexpected issue {scan['issue']!r}")
        return LOC_PAGE_URL.format(item=item, issue=scan["issue"], n=leaf)
    return SCAN_PAGE_URL.format(item=item, n=leaf - 1)


def scan_image(item: str, leaf: int, site: str = "archive.org", scan: dict | None = None) -> str:
    if site == "unt":
        return UNT_IMAGE_URL.format(item=item, n=leaf)
    if site == "loc":
        k = scan["leaves"].index(leaf)
        image = scan["image"][k]
        if not LOC_IMAGE_ID.match(image):
            raise ValueError(f"unexpected image id {image!r}")
        x, y, w, h = scan["regions"][k]  # hundredths of a percent; a margin round the paragraph
        x0, y0 = max(0, x - 150), max(0, y - 100)
        x1, y1 = min(10000, x + w + 150), min(10000, y + h + 100)
        return LOC_IMAGE_URL.format(image=image, x=x0 / 100, y=y0 / 100, w=(x1 - x0) / 100, h=(y1 - y0) / 100)
    return SCAN_IMAGE_URL.format(item=item, n=leaf - 1)


def marked_runs(text: str, spans: list[dict]) -> list[dict]:
    """A line of text as runs, with words the scans could not settle carrying
    their readings ("unc")."""
    runs, at = [], 0
    for u in spans:
        if u["start"] > at:
            runs.append({"t": text[at:u["start"]]})
        runs.append({"t": text[u["start"]:u["end"]], "unc": u["readings"], **({"lib": True} if u.get("accepted") else {})})
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


EXCERPT_WORDS = 30


def excerpt(text: str, quote: str | None) -> dict:
    """A passage's words around a quote: the sentence it is in, with at most
    EXCERPT_WORDS words on each side ("…" where cut). {"before", "quote",
    "after"}; with no quote found, the passage's opening words."""
    at = text.find(quote) if quote else -1
    if at < 0:
        words = text.split()
        return {"before": "", "quote": "", "after": " ".join(words[:2 * EXCERPT_WORDS]) + ("…" if len(words) > 2 * EXCERPT_WORDS else "")}
    end = at + len(quote)
    # The sentence: back to the last stop before the quote, on to the first after it.
    starts = [m.end() for m in re.finditer(r"[.?!]\s+", text[:at])]
    stop = re.search(r"[.?!](?=\s|$)", text[end:])
    lo = starts[-1] if starts else 0
    hi = end + stop.end() if stop else len(text)
    before, after = text[lo:at], text[end:hi]
    words = list(re.finditer(r"\S+", before))
    if len(words) > EXCERPT_WORDS:
        before = "…" + before[words[-EXCERPT_WORDS].start():]
    words = list(re.finditer(r"\S+", after))
    if len(words) > EXCERPT_WORDS:
        after = after[:words[EXCERPT_WORDS - 1].end()] + "…"
    return {"before": before, "quote": quote, "after": after}


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
            far = corpus.segments.get(other)
            if far:
                # The far passage's own words around the quote, so that a
                # reader on a clause sees what the Federalist wrote, not only
                # its quotation of the clause.
                entry["other_excerpt"] = excerpt(far["text"], l.get(other_q))
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
    s = re.sub(r"^(.+?) v\. .+?(?=, syllabus| \(\d{4}\)$)", r"\1", s)  # a case: its first party
    return s.replace(", syllabus ¶ ", " syl. ¶")


def work_key(corpus: Corpus, ref: str) -> str:
    """Which work a ref belongs to (its node color in the graph)."""
    for wid, doc in corpus.works.items():
        prefix = doc.get("ref_prefix", "")
        if ref == prefix or ref.startswith(prefix + "."):
            return wid
    return "other"


FOUNDING = {"declaration", "constitution", "amendments"}


def work_group(corpus: Corpus, wid: str) -> str:
    """Graph color group: the founding documents, the Federalist side (The
    Federalist and Federalist essays), the Anti-Federalists, or other."""
    if wid in FOUNDING:
        return "founding"
    if wid == "federalist":
        return "federalist"
    doc = corpus.works.get(wid, {})
    if doc.get("ref_prefix", "").startswith("Case."):
        return "cases"
    return {"anti": "anti", "federalist": "federalist"}.get(doc.get("position"), "other")


def build_graph(links: list[dict], corpus: Corpus, url_for, page_refs: dict[str, list[str]],
                shorts: dict[str, str] | None = None) -> dict[str, dict]:
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
        wid = work_key(corpus, ref)
        return {"group": work_group(corpus, wid), "label": label, "short": short_label(label), "url": url_for(ref),
                "work": wid, "work_name": (shorts or {}).get(wid, wid)}

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
    if ref.startswith("Case."):  # a whole case: its name and year
        doc = corpus.works.get(ref.split(".")[1], {})
        if doc.get("ref_prefix") == ref:
            return f"{doc['title']} ({doc.get('date', '')[:4]})"
    return ref


# ------------------------------------------------------------ text runs


def runs_for(segment: dict, changed: list[dict]) -> list[list[list[dict]]]:
    """Split a segment's text into paragraphs -> lines -> runs.

    A run is {"t": text} plus optional "em": true (italics),
    "chg": index into `changed` (a span the National Archives marks as
    changed by an amendment), "unc": the scans' readings of a word they
    could not settle ("lib": true where the text has the Anti-Federalist
    Library's reading, accepted unchecked; decision 56), and "fix": a word a person corrected against the page
    image ({"was": the scans' word, "by": their GitHub login}; decision 48). Paragraphs are separated by a blank line in the text,
    lines by a single newline.
    """
    text = segment["text"]
    n = len(text)
    em = [False] * n
    chg: list[int | None] = [None] * n
    unc: list[int | None] = [None] * n
    fix: list[int | None] = [None] * n
    spans = segment.get("uncertain", [])
    fixed = segment.get("corrected", [])
    for idx, c in enumerate(fixed):
        for i in range(c["start"], c["end"]):
            fix[i] = idx
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
        while j < n and text[j] != "\n" and em[j] == em[i] and chg[j] == chg[i] and unc[j] == unc[i] and fix[j] == fix[i]:
            j += 1
        run: dict = {"t": text[i:j]}
        if em[i]:
            run["em"] = True
        if chg[i] is not None:
            run["chg"] = chg[i]
        if unc[i] is not None:
            run["unc"] = spans[unc[i]]["readings"]
            if spans[unc[i]].get("accepted"):
                run["lib"] = True  # the Anti-Federalist Library's reading, not yet checked (decision 56)
        if fix[i] is not None:
            run["fix"] = {"by": fixed[fix[i]]["by"], "was": fixed[fix[i]]["was"]}
        paras[-1][-1].append(run)
        i = j
    return paras


# ------------------------------------------------------------ structure


def work_url(wid: str, settings: dict | None = None) -> str:
    return f"/{(settings or WORKS)[wid]['slug']}/"


def part_slug(work: dict, division_ref: str) -> str:
    return division_ref[len(work["ref_prefix"]) + 1:].lower()


# A part longer than this (bytes of text) is shown on several pages, split
# at paragraphs into nearly equal sheets, so each page stays inside the HTML
# budget (tools/check_site.py; decision 15): the longest days of the 1866
# Senate debate. Refs do not change; their URLs name the page they are on.
SHEET_TEXT_BYTES = 90_000


def sheets(segments: list[dict]) -> list[list[dict]]:
    """A part's passages, in sheets of nearly equal length."""
    sizes = [len(x["text"].encode()) for x in segments]
    total = sum(sizes)
    n = -(-total // SHEET_TEXT_BYTES)
    if n <= 1 or any(x.get("kind") == "footnote" for x in segments):
        return [segments]
    out, at = [[]], 0
    for seg, size in zip(segments, sizes):
        if out[-1] and at >= total * len(out) / n and len(out) < n:
            out.append([])
        out[-1].append(seg)
        at += size
    return out


def sheet_url(page: str, k: int) -> str:
    return page if k == 1 else f"{page}{k}/"


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
        self.settings = {**WORKS, **debate_settings(corpus), **case_settings(corpus)}
        self.works = [corpus.works[w] for w in sorted(self.settings, key=lambda k: self.settings[k]["order"])
                      if w in corpus.works]
        missing = set(corpus.works) - set(self.settings)
        if missing:
            raise ValueError(f"works without site settings in tools/site_data.py: {sorted(missing)}")
        self.ref_urls: dict[str, str] = {}
        self._plan_urls()
        self.clause_refs = {s["ref"] for s in founding_passages(corpus, ("constitution", "amendments"))}
        # Amendment -> the passages whose text the National Archives marks as
        # changed by it (`changed_by`), so the amendment can link back to them.
        self.changes: dict[str, list[str]] = {}
        for ref, seg in corpus.segments.items():
            for c in seg.get("changed_by", []):
                if ref not in self.changes.setdefault(c["amendment"], []):
                    self.changes[c["amendment"]].append(ref)

    # Every segment and division gets a URL before any page is built, so
    # links between works resolve regardless of build order.
    def _plan_urls(self) -> None:
        for work in self.works:
            wid = work["id"]
            base = work_url(wid, self.settings)
            self.ref_urls[work["ref_prefix"]] = base
            tops = [d for d in work.get("divisions", []) if d["level"] == 1]
            for d in work.get("divisions", []):
                if d["ref"] == work["ref_prefix"]:
                    continue  # a single piece's one division is the whole page
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
            if self.settings[wid]["paged"]:
                for t in tops:
                    page = f"{base}{part_slug(work, t['ref'])}/"
                    for k, sheet in enumerate(sheets(self._part_segments(work, t)), 1):
                        for x in sheet:
                            self.ref_urls[x["ref"]] = f"{sheet_url(page, k)}#{x['ref']}"
        # A retired ref's URL is its own anchor, inside the passage it was merged into.
        for ref, into in self.corpus.retired.items():
            if into in self.ref_urls:
                self.ref_urls[ref] = self.ref_urls[into].rsplit("#", 1)[0] + f"#{ref}"

    def url_for(self, ref: str) -> str | None:
        """URL of any ref. A parent ref with no division of its own (rare)
        points at the first passage under it."""
        if ref in self.ref_urls:
            return self.ref_urls[ref]
        first = next((r for r in self.corpus.segments if r.startswith(ref + ".")), None)
        return self.ref_urls.get(first) if first else None

    @staticmethod
    def _part_segments(work: dict, top: dict) -> list[dict]:
        return [s for s in work["segments"] if s["ref"].startswith(top["ref"] + ".")]

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
        # The cases that interpret a clause come last, in date order (their labels end with the year).
        conns.sort(key=lambda e: (e["type"] == "interprets", e["other_label"][-5:-1] if e["type"] == "interprets" else ""))
        block = {
            "changed": changed,
            "clause_url": clause_url(s["ref"]) if s["ref"] in self.clause_refs else None,
            "connections": conns,
            "gutter": gutter(s["ref"], work, s),
            "label": s.get("label", s["ref"]),
            "paras": runs_for(s, changed),
            "ref": s["ref"],
            "type": "passage",
        }
        if s.get("kind"):
            block["kind"] = s["kind"]
        aliases = sorted(r for r, into in self.corpus.retired.items() if into == s["ref"])
        if aliases:
            block["aliases"] = aliases  # retired refs merged into this passage keep an anchor here
        if s.get("scan"):
            leaves = s["scan"]["leaves"]
            # Pages, or for a book printed in numbered columns (the Annals of
            # Congress) its columns.
            pages = s.get("pages") or s.get("columns", [])
            block["scan"] = {"pages": pages, "unit": "col." if s.get("columns") else "p.",
                             "url": scan_url(s["scan"]["item"], leaves[0], s["scan"].get("site", "archive.org"),
                                             s["scan"])}
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
                if self.changes.get(d["ref"]):
                    h["changes"] = [{"label": label_for(self.corpus, r), "ref": r, "url": self.url_for(r)}
                                    for r in self.changes[d["ref"]]]
                # Links to the article or amendment as a whole (a case the
                # Constitution Annotated cites under all of Amendment XIV).
                whole = self._conns(d["ref"]) if d["ref"] not in self.corpus.segments else []
                if whole:
                    h["whole"] = whole
                blocks.append(h)
            blocks.append(self._passage(work, s))
        return blocks

    def _toc(self, work: dict, levels: tuple[int, ...]) -> list[dict]:
        """Contents in reading order: the divisions at `levels`, each with
        links to its own passages when it has several (an article's
        clauses, a state's signers), and the passages that stand outside
        any division (the Preamble, the Declaration's paragraphs)."""
        divs = [d for d in work.get("divisions", []) if d["level"] in levels]
        segs = [s for s in work["segments"] if s.get("kind") != "footnote"]

        def owner(ref: str) -> str | None:
            # The deepest listed division the passage belongs to.
            best = None
            for d in divs:
                if ref.startswith(d["ref"] + ".") and (best is None or len(d["ref"]) > len(best)):
                    best = d["ref"]
            return best

        owned: dict[str, list[dict]] = {}
        for s in segs:
            owned.setdefault(owner(s["ref"]), []).append(s)
        out: list[dict] = []
        placed: set[str] = set()
        for s in segs:
            o = owner(s["ref"])
            if o is None:
                out.append({"kind": "passage", "level": 1, **self._toc_passage(s)})
            elif o not in placed:
                # Every division above the passage's own, then its own, in order.
                for d in divs:
                    if d["ref"] not in placed and (o == d["ref"] or o.startswith(d["ref"] + ".")):
                        placed.add(d["ref"])
                        entry = {"kind": "division", "label": d["label"], "level": d["level"], "ref": d["ref"],
                                 "url": self.url_for(d["ref"])}
                        mine = owned.get(d["ref"], [])
                        if len(mine) > 1:
                            entry["passages"] = [self._toc_passage(x) for x in mine]
                        out.append(entry)
        return out

    def _toc_passage(self, s: dict) -> dict:
        """A passage in the contents: its number or name, and its opening words."""
        last = s.get("label", s["ref"]).split(", ")[-1].split(": ")[-1]
        n = re.sub(r"^(?:Clause|Section|¶)\s*", "", last)
        words = s["text"].split()
        snippet = " ".join(words[:10]) + ("…" if len(words) > 10 else "")
        return {"n": n, "ref": s["ref"], "snippet": snippet, "url": self.url_for(s["ref"])}

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
        for key in ("salutation", "signature", "title"):
            if d.get(key) and (key != "title" or key in unc):
                out[key] = marked_runs(d[key], unc.get(key, []))
        return out

    def build(self) -> tuple[dict, dict[str, dict]]:
        pages: dict[str, dict] = {}
        works_out = []
        cases_out = []
        for work in self.works:
            wid = work["id"]
            cfg = self.settings[wid]
            if cfg["collection"] == "cases":
                page = self._case_page(work)
                pages[page["id"]] = page
                cases_out.append(page["case"])
                continue
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
                "part_name": PARTS.get(wid, "essays"),
                "url": work_url(wid, self.settings),
            }
            if cfg.get("summary"):
                info["summary"] = cfg["summary"]
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
                    "toc": self._toc(work, () if single else (1, 2)),
                    "url": info["url"],
                    "work": self._work_ref(info),
                }
                if single:
                    d = work["divisions"][0]
                    pages[pid]["division"] = {"header": self._header(d), "label": d["label"], "ref": d["ref"]}
                    pages[pid]["notes"] = self._blocks(work, [s for s in work["segments"] if s.get("kind") == "footnote"], ())
            else:
                parts = []
                ids = []
                for i, d in enumerate(tops):
                    segs = self._part_segments(work, d)
                    body = [s for s in segs if s.get("kind") != "footnote"]
                    notes = [s for s in segs if s.get("kind") == "footnote"]
                    pid = f"{wid}-{part_slug(work, d['ref'])}"
                    # Where a day of a debate in Congress is printed ("Annals of
                    # Congress, cols. 440–468", "Congressional Globe, pp. 2458–2470").
                    printed = None
                    if cfg.get("printed_in") and body:
                        cols = [c for s in body for c in s.get("columns", [])]
                        at = cols or [p for s in body for p in s.get("pages", [])]
                        span = at[0] if at[0] == at[-1] else f"{at[0]}–{at[-1]}"
                        unit = ("cols." if at[0] != at[-1] else "col.") if cols else ("pp." if at[0] != at[-1] else "p.")
                        printed = f"{cfg['printed_in']}, {unit} {span}"
                    part = {
                        "attribution": self._attribution(d.get("attribution")),
                        "printed": printed,
                        "date": d.get("date"),
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
                    split = sheets(segs)
                    for k, sheet in enumerate(split, 1):
                        spid = pid if k == 1 else f"{pid}-{k}"
                        ids.append(spid)
                        shown = [s for s in sheet if s.get("kind") != "footnote"]
                        here = {**part, "passages": len(shown), "url": sheet_url(part["url"], k),
                                "words": sum(len(s["text"].split()) for s in shown)}
                        if len(split) > 1:
                            here["sheet"] = {"n": k, "of": len(split),
                                             "urls": [sheet_url(part["url"], n) for n in range(1, len(split) + 1)]}
                        pages[spid] = {
                            "blocks": self._blocks(work, shown, ()),
                            "toc_passages": [self._toc_passage(x) for x in shown],
                            "division": {
                                **here,
                                "header": self._header(d),
                                "notes": [n["text"] for n in d.get("notes", [])],
                                "salutation": d.get("salutation") if k == 1 else None,
                                "signature": d.get("signature") if k == len(split) else None,
                                "variants": d.get("variants", []) if k == len(split) else [],
                            },
                            "id": spid,
                            "kind": "part",
                            "notes": self._blocks(work, notes, ()),
                            # A day of a debate in Congress is named by its date and house.
                            "title": (f"{'The Senate' if work['ref_prefix'].startswith('Senate') else 'The House'}, {d['label']}"
                                      if cfg["collection"] == "congress"
                                      else f"{d['label']}" + (f": {d['title']}" if d.get("title") else ""))
                            + (f" ({k} of {len(split)})" if len(split) > 1 else ""),
                            "url": here["url"],
                            "work": self._work_ref(info),
                        }
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

        congress = [w for w in works_out if w["collection"] == "congress"]
        if congress:
            pages["congress"] = {
                "groups": [{"label": g, "works": [w["id"] for w in congress if self.settings[w["id"]].get("group") == g]}
                           for g in CONGRESS_GROUPS],
                "id": "congress", "kind": "congress", "title": "Debates in Congress", "url": "/congress/",
            }

        pages.update(self._clause_pages())

        if cases_out:
            pages["cases"] = {"cases": cases_out, "id": "cases", "kind": "cases", "title": "Supreme Court Cases",
                              "url": "/cases/"}

        site = {
            "pages": [{"id": p["id"], "kind": p["kind"], "url": p["url"]} for p in pages.values()],
            "stats": {
                "connections": sum(len(v) for v in self.link_index["by_ref"].values()) // 2,
                "cases": len(cases_out),
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

    def _conns(self, ref: str) -> list[dict]:
        """The connections of a ref, each with its far end's URL, and for a
        case its date and citation; cases in date order after the rest."""
        out = []
        for e in self.link_index["by_ref"].get(ref, []):
            c = {**e, "other_url": self.url_for(e["other"])}
            if e["other"].startswith("Case."):
                doc = self.corpus.works.get(case_root(e["other"]).split(".")[1], {})
                c["case"] = {k: doc[k] for k in ("date", "us_cite", "docket") if doc.get(k)}
            out.append(c)
        out.sort(key=lambda c: ("case" in c, c.get("case", {}).get("date", "")))
        return out

    # A clause page's groups of connections, by where the far end is.
    CLAUSE_GROUPS = (
        ("federalist", "The Federalist and Federalist essays"),
        ("anti", "Anti-Federalist essays"),
        ("other", "Other writings"),
        ("congress", "Debates in Congress"),
        ("cases", "The Supreme Court"),
        ("founding", "The founding documents"),
    )

    def _clause_pages(self) -> dict[str, dict]:
        """A page per clause of the Constitution and section of an amendment
        (decision 52): its text, then what reaches it, grouped: the founding
        debate by side, the debates in Congress, and the cases whose
        Constitution Annotated essays cite it, oldest first. Links to the
        article or amendment as a whole follow, then the clauses either side."""
        segs = founding_passages(self.corpus, ("constitution", "amendments"))
        pages = {}
        for i, seg in enumerate(segs):
            ref = seg["ref"]
            work = self.corpus.works[self.corpus.segment_work[ref]]
            groups = []
            conns = self._conns(ref)
            for key, label in self.CLAUSE_GROUPS:
                items = [c for c in conns if ("cases" if "case" in c else map_side(self.corpus, work_key(self.corpus, c["other"]))) == key]
                if items:
                    groups.append({"id": key, "items": items, "label": label})
            parts = ref.split(".")
            # The article or amendment, and section, this clause is under (for crumbs and links to the whole).
            above = [".".join(parts[:k]) for k in range(2, len(parts)) if ".".join(parts[:k]) in self.corpus.divisions]
            whole = [{"label": label_for(self.corpus, a), "ref": a, "url": self.url_for(a), "items": self._conns(a)}
                     for a in above if self._conns(a)]
            near = lambda s: {"label": s["label"], "url": clause_url(s["ref"])}  # noqa: E731
            block = self._passage(work, seg)
            pages[f"clause-{ref}"] = {
                "clause": {"changed": block["changed"], "label": seg["label"], "paras": block["paras"],
                           "ref": ref, "url": self.url_for(ref)},
                "counts": {g["id"]: len(g["items"]) for g in groups},
                "crumbs": [{"label": work["title"], "url": work_url(work["id"], self.settings)}]
                + [{"label": label_for(self.corpus, a), "url": self.url_for(a)} for a in above],
                "groups": groups,
                "id": f"clause-{ref}",
                "kind": "clause",
                "next": near(segs[i + 1]) if i + 1 < len(segs) else None,
                "prev": near(segs[i - 1]) if i > 0 else None,
                "title": seg["label"],
                "url": clause_url(ref),
                "whole": whole,
                "work": {"id": work["id"], "title": work["title"], "url": work_url(work["id"], self.settings)},
            }
        return pages

    # Fields of a case file (cases/) that its page shows as they are.
    CASE_FIELDS = ("chosen_because", "conan_citation", "courtlistener_name", "courtlistener_url", "date", "docket",
                   "court_print", "loc_url", "pdf_first_page", "pdf_url", "syllabus_note", "us_cite")

    def _case_page(self, work: dict) -> dict:
        """A case's page: its details, the syllabus as printed (one passage
        per paragraph, each linked to its page of the scan), and the links
        that start or end at the case as a whole: the provisions the
        Constitution Annotated's essays cite it under, and overrulings."""
        wid, ref = work["id"], work["ref_prefix"]
        url = work_url(wid, self.settings)
        # A provision the case is cited under opens on its clause page.
        conns = [{**e, "other_url": clause_url(e["other"]) if e["other"] in self.clause_refs else self.url_for(e["other"])}
                 for e in self.link_index["by_ref"].get(ref, [])]
        overruled = ref in self.link_index["overruled"]
        case = {k: work[k] for k in self.CASE_FIELDS if work.get(k)}
        case |= {"id": wid, "ref": ref, "title": work["title"], "url": url, "overruled": overruled,
                 "interprets": [{"label": c["other_label"], "ref": c["other"], "url": c["other_url"]}
                                for c in conns if c["type"] == "interprets" and c["direction"] == "out"],
                 "syllabus": sum(1 for s in work["segments"] if s.get("kind") == "syllabus")}
        blocks = []
        for s in work["segments"]:
            block = self._passage(work, s)
            if s.get("kind") == "syllabus" and work.get("pdf_url"):
                first = int(case.get("us_cite", "0 U.S. 0").split()[-1])
                index = s["page"] - first + work.get("pdf_first_page", 1)
                block["printed"] = {"page": s["page"], "url": f"{work['pdf_url']}#page={index}",
                                    "from": "the Supreme Court's PDF" if work.get("court_print")
                                    else "the Library of Congress scan"}
            blocks.append(block)
        return {
            "blocks": blocks,
            "case": case,
            "connections": conns,
            "edition": work["edition"],
            "id": f"case-{wid}",
            "kind": "case",
            "overruled_by": [c for c in conns if c["type"] == "overrules" and c["direction"] == "in"],
            "overrules": [c for c in conns if c["type"] == "overrules" and c["direction"] == "out"],
            "title": work["title"],
            "url": url,
        }

    @staticmethod
    def _work_ref(info: dict) -> dict:
        return {"id": info["id"], "short": info["short"], "title": info["title"], "url": info["url"]}

    @staticmethod
    def _nav(page: dict) -> dict:
        d = page["division"]
        sheet = f" ({d['sheet']['n']} of {d['sheet']['of']})" if d.get("sheet") else ""
        return {"label": d["label"] + sheet, "title": d.get("title"), "url": page["url"]}


def build(corpus: Corpus, links: list[dict]) -> tuple[dict, dict[str, dict], dict[str, dict], dict[str, dict]]:
    b = SiteBuilder(corpus, links)
    site, pages = b.build()
    refs = {ref: {"label": label_for(corpus, ref), "url": url} for ref, url in sorted(b.ref_urls.items())}
    page_refs = {
        pid: [blk["ref"] for blk in p.get("blocks", []) + p.get("notes", []) if blk["type"] == "passage"]
        + ([p["case"]["ref"]] if p["kind"] == "case" else [])  # a case's own links are to the whole case
        for pid, p in pages.items() if p["kind"] in ("work", "part", "case")
    }
    graphs = build_graph(links, corpus, b.url_for, page_refs, {w: s["short"] for w, s in b.settings.items()})
    return site, pages, refs, graphs


# ------------------------------------------------------------ connection previews

PREVIEW_CHARS = 1500  # a preview's stretch of a longer passage; the rest is read on its page
PREVIEW_SNAP = 250    # how far a preview's ends move to begin or end at a sentence


def window(text: str, quote: str | None = None) -> dict:
    """The stretch of a passage a preview shows: all of it if short, else
    about PREVIEW_CHARS centred on the quoted words (from the start when
    there are none), beginning and ending at a sentence where one is near,
    else at a word. {"text", "cut_before", "cut_after"}."""
    if len(text) <= PREVIEW_CHARS:
        return {"text": text}
    at = text.find(quote) if quote else -1
    middle = at + len(quote) // 2 if at >= 0 else 0
    lo = max(0, min(middle - PREVIEW_CHARS // 2, len(text) - PREVIEW_CHARS))
    hi = min(len(text), lo + PREVIEW_CHARS)
    if at >= 0:  # never cut through the quoted words
        lo, hi = min(lo, at), max(hi, at + len(quote))
    if lo > 0:
        starts = [m.end() for m in re.finditer(r"[.?!:;]\s+|\n+", text[lo:lo + PREVIEW_SNAP])]
        lo = lo + starts[0] if starts and (at < 0 or lo + starts[0] <= at) else text.find(" ", lo) + 1 or lo
    if hi < len(text):
        stops = [m.end() for m in re.finditer(r"[.?!](?=\s)", text[max(lo, hi - PREVIEW_SNAP):hi])]
        base = max(lo, hi - PREVIEW_SNAP)
        hi = base + stops[-1] if stops and (at < 0 or base + stops[-1] >= at + len(quote)) else (text.rfind(" ", lo, hi) if text.rfind(" ", lo, hi) > lo else hi)
    out = {"text": text[lo:hi].strip()}
    if lo > 0:
        out["cut_before"] = True
    if hi < len(text):
        out["cut_after"] = True
    return out


def preview_of(corpus: Corpus, ref: str, refs: dict[str, dict], quote: str | None = None) -> dict | None:
    """What the panel shows when a reader previews a connection: the linked
    passage around the quoted words (`window`); for a whole case, its date,
    citation and first paragraph of syllabus; for a whole essay or article,
    its first passage."""
    info = refs.get(ref, {"label": label_for(corpus, ref), "url": None})
    out = {"label": info["label"], "url": info["url"]}
    if ref in corpus.segments:
        return out | window(corpus.segments[ref]["text"], quote)
    case = next((w for w in corpus.works.values() if w.get("ref_prefix") == ref and ref.startswith("Case.")), None)
    if case:
        first = next((x for x in case.get("segments", []) if x.get("kind") == "syllabus"), None)
        out |= {"case": {k: case[k] for k in ("date", "us_cite", "docket") if case.get(k)}}
        if first:
            out |= window(first["text"]) | {"more": len(case["segments"]) - 1, "note": "From the syllabus as printed"}
        else:
            out["note"] = case.get("syllabus_note", "")
        return out
    under = corpus.passages(ref)
    if not under:
        return None
    return out | window(under[0]["text"]) | {"more": len(under) - 1, "note": "The first passage"}


def build_previews(corpus: Corpus, pages: dict[str, dict], refs: dict[str, dict]) -> dict[str, dict]:
    """Preview files, one per passage with connections: link id -> the
    linked passage around that link's quote. The reader fetches a passage's
    file the first time a preview of one of its connections is opened, so
    even the busiest clause costs one small request."""
    out: dict[str, dict] = {}
    for page in pages.values():
        if page["kind"] not in ("work", "part", "case"):
            continue
        for b in page.get("blocks", []) + page.get("notes", []):
            conns = b.get("connections") if b["type"] == "passage" else b.get("whole")  # a heading: links to the whole
            if not conns:
                continue
            previews = {}
            for c in conns:
                pv = preview_of(corpus, c["other"], refs, c.get("other_quote"))
                if pv:
                    previews[c["id"]] = pv
            if previews:
                out[b["ref"]] = previews
    return out


# ------------------------------------------------------------ overview map

# Which side of the debate a linked work is on, as the map colors it.
MAP_SIDES = ("federalist", "anti", "other", "congress", "founding")
MAP_KINDS = {"quotes": "cite", "cites": "cite", "implements": "cite", "responds_to": "answer", "rebuts": "answer",
             "shared_theme": "theme", "interprets": "case", "overrules": "case"}


def map_side(corpus: Corpus, wid: str) -> str:
    doc = corpus.works.get(wid, {})
    if wid in FOUNDING:
        return "founding"
    if wid == "federalist" or doc.get("position") == "federalist":
        return "federalist"
    if doc.get("position") == "anti":
        return "anti"
    if doc.get("ref_prefix", "").startswith(("House1", "Senate1")):
        return "congress"
    return "other"


def founding_passages(corpus: Corpus, works: tuple[str, ...] = ("declaration", "constitution", "amendments")) -> list[dict]:
    """The founding documents' own text, passage by passage in reading order:
    not the Declaration's heading, the signers, or the notes after Article VII."""
    out = []
    for wid in works:
        for seg in corpus.works.get(wid, {}).get("segments", []):
            parts = seg["ref"].split(".")
            if wid == "declaration" and not parts[1].isdigit():
                continue
            if wid == "constitution" and not (parts[1].isdigit() or parts[1] == "Preamble"):
                continue
            out.append(seg)
    return out


def clause_url(ref: str) -> str | None:
    """A clause page's URL, which mirrors its ref: Constitution.1.8.18 ->
    /constitution/1/8/18/, Amendment.14.1 -> /amendments/14/1/."""
    head, _, rest = ref.partition(".")
    base = {"Constitution": "/constitution/", "Amendment": "/amendments/"}.get(head)
    return f"{base}{rest.lower().replace('.', '/')}/" if base and rest else None


def build_map(corpus: Corpus, links: list[dict], refs: dict[str, dict], shorts: dict[str, str]) -> dict:
    """The overview map (/map/): the founding documents as a spine, passage
    by passage in reading order, with the links that reach each passage from
    the debate (by side, kind and review status) and the cases that
    interpret it (by year); links between the debate's works, as arcs; and
    how much of each work has been linked, so the map does not overclaim."""
    spine, at = [], {}
    for seg in founding_passages(corpus):
        ref = seg["ref"]
        parts = ref.split(".")
        group = ("Declaration" if parts[0] == "Declaration" else "Preamble" if parts[1] == "Preamble"
                 else f"Amendment {parts[1]}" if parts[0] == "Amendment" else f"Article {roman(int(parts[1]))}")
        at[ref] = len(spine)
        # A clause opens its own page; the Declaration's paragraphs open in the reader.
        spine.append({"group": group, "label": refs.get(ref, {}).get("label", ref), "ref": ref,
                      "short": short_label(refs.get(ref, {}).get("label", ref)),
                      "url": clause_url(ref) or refs.get(ref, {}).get("url")})

    def spot(ref: str) -> int | None:
        """The spine passage a link end reaches: itself, or the first passage of a whole article or amendment."""
        if ref in at:
            return at[ref]
        return next((at[r["ref"]] for r in corpus.passages(ref) if r["ref"] in at), None)

    live = [l for l in links if l.get("status") != "rejected"]
    overruled = {case_root(l["to"]) for l in live if l.get("type") == "overrules"}
    cases: dict[str, dict] = {}
    marks, arcs = [], {}
    for l in sorted(live, key=lambda x: x["id"]):
        a, b = spot(l["from"]), spot(l["to"])
        reviewed = 1 if l["status"] == "reviewed" else 0
        kind = MAP_KINDS.get(l["type"], "cite")
        if (a is None) == (b is None):
            if a is None:  # between two works of the debate: an arc
                wa, wb = work_key(corpus, l["from"]), work_key(corpus, l["to"])
                if wa != wb and not wa.isdigit() and not wb.isdigit():
                    arc = arcs.setdefault((wa, wb, kind), {"from": wa, "kind": kind, "n": 0, "reviewed": 0, "to": wb})
                    arc["n"] += 1
                    arc["reviewed"] += reviewed
            continue
        i, far = (a, l["to"]) if a is not None else (b, l["from"])
        wid = work_key(corpus, far)
        if far.startswith("Case."):
            root = case_root(far)
            doc = corpus.works.get(root.split(".")[1], {})
            cases.setdefault(root, {"label": doc.get("title", root), "overruled": root in overruled,
                                    "url": refs.get(root, {}).get("url"), "year": str(doc.get("date", ""))[:4]})
            marks.append([i, "case", kind, reviewed, root])
        else:
            marks.append([i, map_side(corpus, wid), kind, reviewed, wid])
    # Each case once per passage, in date order.
    seen, debate, by_case = set(), [], []
    for m in marks:
        if m[1] == "case":
            if (m[0], m[4]) not in seen:
                seen.add((m[0], m[4]))
                by_case.append(m)
        else:
            debate.append(m)
    by_case.sort(key=lambda m: (m[0], cases[m[4]]["year"], m[4]))

    works = {}
    for wid, doc in corpus.works.items():
        if wid in FOUNDING or doc.get("ref_prefix", "").startswith("Case."):
            continue
        tops = [d for d in doc.get("divisions", []) if d.get("level") == 1] or [doc]
        works[wid] = {"short": shorts.get(wid, wid), "side": map_side(corpus, wid), "title": doc["title"],
                      "parts": len(tops), "linked_parts": 0, "url": refs.get(doc.get("ref_prefix", ""), {}).get("url")}
    touched: dict[str, set] = {}
    for l in live:
        for end in (l["from"], l["to"]):
            wid = work_key(corpus, end)
            if wid in works:
                doc = corpus.works[wid]
                tops = [d["ref"] for d in doc.get("divisions", []) if d.get("level") == 1]
                top = next((t for t in tops if end == t or end.startswith(t + ".")), None if tops else wid)
                if top:  # a link to a whole series names no one part of it
                    touched.setdefault(wid, set()).add(top)
    for wid, tops in touched.items():
        works[wid]["linked_parts"] = len(tops)
    # Totals per passage, for the table shown without JavaScript and for screen readers.
    for item in spine:
        item["totals"] = {side: 0 for side in ("federalist", "anti", "congress", "other", "cases")}
    for m in debate:
        if m[1] in spine[m[0]]["totals"]:
            spine[m[0]]["totals"][m[1]] += 1
    for m in by_case:
        spine[m[0]]["totals"]["cases"] += 1
    return {
        "arcs": sorted(arcs.values(), key=lambda x: (x["from"], x["to"], x["kind"])),
        "cases": dict(sorted(cases.items())),
        "debate": debate,        # [spine index, side, kind, reviewed, work]
        "interprets": by_case,   # [spine index, "case", kind, reviewed, case ref]
        "spine": spine,
        "works": dict(sorted(works.items())),
    }


def roman(n: int) -> str:
    return ["", "I", "II", "III", "IV", "V", "VI", "VII"][n] if n < 8 else str(n)


# ------------------------------------------------------------ review page

REVIEW_GROUPS = [
    ("fed-const-", "The Federalist → the Constitution", "Run 1: each paper's citations and quotations of the Constitution."),
    ("fed-deb-", "The Federalist → the ratification debate", "Publius's notes naming debate writers."),
    ("deb-", "The ratification debate", "Run 2: each essay's links to the Constitution, the Declaration and other essays."),
    ("cong-", "Debates in Congress", "Run 4: each day's quotations and citations of the Constitution, and the "
     "words of the proposals under debate found in the amendments as ratified."),
    ("conan-", "Supreme Court cases", "Imported from the Constitution Annotated (2022): the provisions whose essays "
     "cite each case, and its table of overruled decisions. Check each against the source it names."),
]
CONFIDENCE_ORDER = ("high", "medium", "low")
IMPORTED_BATCHES = {"conan-interprets": "Cases → the provisions their essays cite them under",
                    "conan-overrules": "Cases → the cases they overrule"}


def build_review(corpus: Corpus, proposed: list[tuple[str, dict]], refs: dict[str, dict]) -> tuple[dict, dict[str, dict]]:
    """The review page's data: every suggested link, grouped by batch (one
    linker run), with both passages' text so a reviewer can judge it.
    Decisions are recorded through a GitHub issue (tools/links.py apply)."""
    def end(ref: str) -> dict:
        info = refs.get(ref, {"label": label_for(corpus, ref), "url": None})
        out = {"label": info["label"], "ref": ref, "url": info["url"]}
        if ref in corpus.segments:
            out["text"] = corpus.segments[ref]["text"]
        else:
            out["parts"] = len(corpus.passages(ref))  # a whole essay or series: the reviewer opens it
        return out

    by_batch: dict[str, list[dict]] = {}
    for batch, rec in proposed:
        if rec.get("status") != "suggested":
            continue
        item = {k: rec[k] for k in ("id", "type", "confidence", "rationale") if rec.get(k)}
        for k in ("from_quote", "to_quote"):
            if rec.get(k):
                item[k] = rec[k]
        item["from"], item["to"] = end(rec["from"]), end(rec["to"])
        by_batch.setdefault(batch, []).append(item)

    def batch_label(batch: str, items: list[dict]) -> str:
        if batch in IMPORTED_BATCHES:
            return IMPORTED_BATCHES[batch]
        first = items[0]["from"]["ref"]
        top = next((d for d in corpus.divisions if first == d or first.startswith(d + ".")), first)
        label = label_for(corpus, top) if top in corpus.divisions else items[0]["from"]["label"]
        if "-in-" in batch:  # a run for the passages that name one writer ("deb-brutus-in-cato-5")
            label += f", naming {items[0]['to']['label'].split(' ')[0]}"
        if batch.startswith("cong-"):  # a day of a debate in Congress: say which ("House debates, 1866: May 8, 1866")
            work = next((w for w in corpus.works.values() if first.startswith(w.get("ref_prefix", "?") + ".")), None)
            if work:
                label = f"{work.get('short', work['title'])}: {label}"
        return label

    groups = []
    for prefix, label, note in REVIEW_GROUPS:
        names = [b for b in by_batch if b.startswith(prefix)]
        names.sort(key=lambda b: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", b)])
        if names:
            groups.append({"id": prefix.rstrip("-"), "label": label, "note": note, "batches": [
                {"batch": b, "count": len(by_batch[b]), "ids": [i["id"] for i in by_batch[b]],
                 "by_confidence": {c: [i["id"] for i in by_batch[b] if i["confidence"] == c] for c in CONFIDENCE_ORDER},
                 "label": batch_label(b, by_batch[b])} for b in names]})
    # Within a batch, high-confidence links first, so a reviewer can take them first (stable within each level).
    batches = {b: {"batch": b, "label": batch_label(b, items),
                   "links": sorted(items, key=lambda i: CONFIDENCE_ORDER.index(i["confidence"]))}
               for b, items in by_batch.items()}
    repo = read_json(ROOT / "site" / "site.config.json")["repo"]
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", repo):
        raise ValueError(f"site.config.json: repo must be owner/name, not {repo!r}")
    index = {"by_confidence": {c: sum(1 for items in by_batch.values() for i in items if i["confidence"] == c)
                               for c in CONFIDENCE_ORDER},
             "groups": groups, "repo": repo, "total": sum(len(v) for v in by_batch.values())}
    return index, batches


# ------------------------------------------------------------ errata page

ERRATA_CONTEXT = 12  # words of the passage shown each side of an uncertain word


def build_errata(corpus: Corpus, refs: dict[str, dict]) -> tuple[dict, dict[str, dict]]:
    """The errata page's data: every word the scans could not settle, by
    work, with the words around it, each scan's reading and the page images,
    so a maintainer can read the word off the page. Decisions are recorded
    through a GitHub issue (tools/errata.py apply; decision 48)."""
    def words_before(text: str) -> str:
        w = text.split(" ")
        return ("…" if len(w) > ERRATA_CONTEXT else "") + " ".join(w[-ERRATA_CONTEXT:])

    def words_after(text: str) -> str:
        w = text.split(" ")
        return " ".join(w[:ERRATA_CONTEXT]) + ("…" if len(w) > ERRATA_CONTEXT else "")

    works, per_work = [], {}
    for wid, work in corpus.works.items():
        items, corrected = [], 0
        for seg in work.get("segments", []):
            spans, scan = seg.get("uncertain", []), seg.get("scan")
            corrected += len(seg.get("corrected", []))
            if not spans or not scan:
                continue
            site = scan.get("site", "archive.org")
            pages = [{"image": scan_image(scan["item"], leaf, site, scan), "url": scan_url(scan["item"], leaf, site, scan)}
                     for leaf in scan["leaves"]]
            info = refs.get(seg["ref"], {"label": seg.get("label", seg["ref"]), "url": None})
            text = seg["text"]
            items.append({"label": info["label"], "pages": pages, "ref": seg["ref"], "url": info["url"], "words": [
                {"after": words_after(text[u["end"]:].replace("\n", " ")),
                 "before": words_before(text[:u["start"]].replace("\n", " ")),
                 "index": i, "readings": u["readings"], "was": text[u["start"]:u["end"]],
                 **({"suggestion": u["suggestion"]} if u.get("suggestion") else {}),
                 **({"accepted": True} if u.get("accepted") else {})}
                for i, u in enumerate(spans)]})
        if not items and not corrected:
            continue
        per_work[wid] = {"id": wid, "passages": items, "title": work["title"]}
        works.append({"corrected": corrected, "edition": work.get("edition", {}).get("name", ""), "id": wid,
                      "passages": len(items), "title": work["title"],
                      "words": sum(len(i["words"]) for i in items)})
    works.sort(key=lambda w: w["title"])
    repo = read_json(ROOT / "site" / "site.config.json")["repo"]
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", repo):
        raise ValueError(f"site.config.json: repo must be owner/name, not {repo!r}")
    index = {"corrected": sum(w["corrected"] for w in works), "repo": repo,
             "total": sum(w["words"] for w in works), "works": works}
    return index, per_work


def main() -> None:
    from tools.verify import load_links

    corpus = load_corpus()
    links = [rec for _, _, rec in load_links()]
    site, pages, refs, graphs = build(corpus, links)
    if OUT.exists():
        shutil.rmtree(OUT)
    write_json(OUT / "site.json", site)
    write_json(OUT / "refs.json", refs)
    previews = build_previews(corpus, pages, refs)
    for pid, page in pages.items():
        write_json(OUT / "pages" / f"{pid}.json", page)
    for pid, graph in graphs.items():
        write_json(OUT / "graph" / f"{pid}.json", graph)
    for name, shard in previews.items():
        write_json(OUT / "preview" / f"{name}.json", shard)
    proposed = [(path.stem, rec) for path, _, rec in load_links() if path.parent.name == "proposed"]
    review, batches = build_review(corpus, proposed, refs)
    write_json(OUT / "review" / "index.json", review)
    for name, batch in batches.items():
        write_json(OUT / "review" / f"{name}.json", batch)
    write_json(OUT / "map.json", build_map(corpus, links, refs, {w: s["short"] for w, s in SiteBuilder(corpus, links).settings.items()}))
    errata, errata_works = build_errata(corpus, refs)
    write_json(OUT / "errata" / "index.json", errata)
    for wid, data in errata_works.items():
        write_json(OUT / "errata" / f"{wid}.json", data)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(pages)} pages, {len(refs)} refs")


if __name__ == "__main__":
    main()
