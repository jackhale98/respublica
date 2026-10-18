# Res Publica — Implementation Plan

A free, open-source, Sefaria-style library of America's founding texts, where every passage shows what it cites, what cites it, who argued against it, and how the courts have read it since.

**Primary reader:** curious general readers exploring on their own.
**Hosting:** static site, no server, no accounts.
**Sister site:** [CommonHall](https://commonhall.org) tracks government today; Res Publica is the library behind it. See [CommonHall integration](#commonhall-integration).

---

## Principles

1. **Texts come from code, never from model output.** Every word of a source text reaches the repo through an importer script that runs on a downloaded original. Agents write and fix importers; they never type, retype, or "clean up" text by hand.
2. **Every link has provenance.** Each connection records who or what made it, why, and whether a human has reviewed it. Machine-suggested links are labeled as such on the site.
3. **Code checks every claim.** Quotes are verified by exact match against canonical text. Refs are verified to exist. Raw sources are verified by checksum.
4. **Plain files in git.** Texts, links, and source manifests are JSON/JSONL, so every change is diffable and reviewable.
5. **Editions are explicit.** Each work names its base edition and source; original spelling is preserved.
6. **No legal summaries written by agents.** What a case held, and whether it is still good law, comes from a cited source (the opinion, its official syllabus, or Constitution Annotated), quoted or recorded as data. Agents may find connections; they don't characterize holdings.

---

## Corpus

### Founding texts (v1)

| Work | Planned source | Notes |
|---|---|---|
| Constitution (1787) | National Archives transcription | Preserves original spelling ("Pensylvania", "defence") |
| Bill of Rights & Amendments 11–27 | National Archives transcriptions | |
| The Federalist (85 papers) | Base edition TBD (candidates: Project Gutenberg, Avalon Project, Library of Congress) | Choose one base edition and document differences from newspaper printings. Papers 49–58 and 62–63 have disputed authorship (Hamilton/Madison). |
| Anti-Federalist essays (Brutus, Federal Farmer, Cato, Centinel, etc.) | **Research task** | Storing's and Borden's compilations are modern editions and likely under copyright. Find public-domain sources: original printings, or 19th-century compilations such as Paul Leicester Ford's *Pamphlets on the Constitution* (1888) and *Essays on the Constitution* (1892), to be verified for contents. |

### Supreme Court cases (v1.5)

A curated set of about 50–100 landmark cases to start, linked to the clauses they interpret.

| Data | Source | Notes |
|---|---|---|
| Which cases interpret which clause | Constitution Annotated (Congress.gov, a public-domain government work) | Import its citations with code; this gives expert-curated links without agents guessing. |
| Case metadata and opinion text | CourtListener (Free Law Project) | Key every case by CourtListener cluster ID, the same key CommonHall uses. Store U.S. Reports citation for display. |
| Syllabus | The opinion's official syllabus, word for word | Where one exists (not for the earliest cases). |
| Status (overruled, abrogated) | Recorded as a sourced link, e.g. `Brown → Plessy: overrules`, with the citation for that fact | Shown prominently on every link to an overruled case. |

Federal opinions are public domain. Opinion text is long, so the site shows linked passages and the syllabus, and links to CourtListener for the full opinion.

### Statutes (later)

Major laws that implement a clause directly (the Judiciary Act of 1789, the Civil Rights Acts), from govinfo.gov or the U.S. Code's official XML. Not in v1.

---

## Reference scheme

Refs are stable, human-readable, and never renumbered once published.

- `Constitution.Preamble`
- `Constitution.{article}.{section}.{clause}`, e.g. `Constitution.1.8.3` (Commerce Clause)
- `Amendment.{n}.{section}`, e.g. `Amendment.14.1`
- `Federalist.{paper}.{paragraph}`, e.g. `Federalist.10.4`
- `{Series}.{essay}.{paragraph}` for Anti-Federalist works, e.g. `Brutus.1.4`, `FederalFarmer.3.2`
- `Case.{courtlistener_cluster_id}` for a whole case; `Case.{cluster_id}.{paragraph}` for a paragraph of the majority opinion

Clause numbering is a convention, not part of the text, so document it in `docs/references.md`. Corrections after publication go through an errata log, not renumbering.

---

## Data model

```
sources/
  raw/                     downloaded originals, never edited
  manifest.json            [{id, url, retrieved_at, sha256, license, notes}]
importers/                 one Python script per source
texts/
  {work}.json              {id, title, attribution, date, edition, source_ids, segments: [{ref, text}]}
cases/
  {cluster_id}.json        {id, name, us_cite, date, courtlistener_url, syllabus, segments}
links/
  proposed/*.jsonl         agent output awaiting verification/review
  {batch}.jsonl            accepted links
tools/verify/              checks run locally and in CI
site/                      Astro app
docs/                      references.md, editions.md, contributing.md, decisions.md
```

**Link record**

```json
{
  "id": "lnk_000123",
  "from": "Federalist.10.4",
  "to": "Brutus.1.12",
  "type": "rebuts",
  "from_quote": "optional exact substring of the from-passage",
  "to_quote": "optional exact substring of the to-passage",
  "rationale": "one or two sentences",
  "source": "optional citation for links imported from a reference work, e.g. Constitution Annotated",
  "created_by": {"kind": "agent | human | import", "model": "…", "run": "…"},
  "created_at": "2026-10-18",
  "confidence": "high | medium | low",
  "status": "suggested | reviewed | rejected",
  "reviewed_by": null
}
```

**Link types:** `quotes`, `cites`, `responds_to`, `rebuts`, `shared_theme`, `interprets` (case → clause), `overrules` (case → case), `implements` (statute → clause, later).

Links imported by code from a reference work (`created_by.kind: "import"`) carry a `source` and can be published as reviewed once a sample is spot-checked.

**Attribution** supports `"disputed"` with the candidate authors listed.

---

## Pipeline

`fetch → import → verify → build`, each a single command (e.g. `make fetch`, `make import`, `make verify`, `make build`).

**Verify checks**
- Every raw file matches its manifest checksum.
- Every ref in `links/` exists in `texts/` or `cases/`.
- Every `from_quote` / `to_quote` is an exact substring of its passage, after a documented normalization limited to whitespace and quote-mark style. No spelling normalization.
- Every link has `created_by`, `status`, and a `rationale` (or a `source` for imported links).
- No duplicate link IDs.
- Every URL stored in data is `http:` or `https:`.
- Every link to an overruled case is flagged so the site can show it.

CI (GitHub Actions) runs `make verify` on every pull request; a failing check blocks the merge.

---

## Site

- **Library:** browse works and tables of contents.
- **Reader:** the text, with a connections panel beside it; open any connected passage side by side.
- **Graph view (per passage):** the selected passage at the center with its connections one or two hops out. Nodes colored by work (cases in their own color), edges styled by link type, suggested links dashed. Clicking a node opens that passage in the side panel. Filters for link type, work, and reviewed-only.
  - Neighborhoods are precomputed at build time as small JSON files per ref, so the page stays static and fast.
  - Candidate library: Cytoscape.js.
  - Later: a corpus-wide overview of link density between works (for example, Federalist ↔ Brutus), similar to Sefaria's visualizations.
- **Clause pages:** for each clause, the founding debate and the cases that interpret it, in date order, with overruled cases marked.
- **Source sheets:** collect passages and notes; stored in the browser, shareable as a compressed link, exportable/importable as JSON.
- **Search:** Pagefind (static, no server).
- **About / Editions:** sources, editions, methods, and how machine-suggested links work.

Mobile-first layout; the connections panel becomes a bottom sheet on phones.

**Security baseline (from the CommonHall review):**
- Only `http:`/`https:` URLs, enforced at import and at render.
- A strict Content Security Policy (a meta tag per page, with the hashes of its scripts; framing and other headers from the host).
- No third-party scripts loaded into pages.
- Browser storage holds only source sheets and preferences, never anything sensitive.

---

## CommonHall integration

The two sites stay separate codebases, joined by shared IDs.

- **Hosting:** Res Publica gets its own repo and its own domain, <https://respublicalibrary.org>, served by Cloudflare (docs/decisions.md 44).
- **Shared keys:** Supreme Court cases are keyed by CourtListener cluster ID on both sites. Clauses use Res Publica refs (`Constitution.1.8.3`).
- **Res Publica publishes a static index** at build time, e.g. `api/clauses.json` (clause ref → title, URL) and `api/cases.json` (cluster ID → clauses it interprets). No server needed.
- **CommonHall reads that index** in its nightly build. A new Supreme Court decision page can then show "This case interprets: the Commerce Clause → read the founding debate", whenever Constitution Annotated or CourtListener citations connect it.
- **Later, in the other direction:** clause pages could link to current CommonHall bills or cases touching that clause.
- **Design:** share CommonHall's typography and colors so the two feel like one project.

---

## Phases

Each phase ends with `make verify` passing.

0. **Setup.** Astro site, Python environment, Makefile, CI (actions pinned to commit SHAs), license, `CLAUDE.md`, CSP.
1. **Constitution.** Fetch, import, reader page. *Done when every clause renders with its ref.*
2. **Federalist.** Choose and document the base edition; import all 85 papers with paragraph refs and attribution.
3. **Explicit links.** Agents find direct citations from the Federalist to the Constitution, one paper per run, in parallel. Code verifies; a human spot-checks a sample.
4. **Connections panel and graph view.**
5. **Anti-Federalist sourcing.** Research public-domain sources, record findings in `docs/editions.md`, then write importers.
6. **Thematic links and review.** Agents propose `responds_to` / `rebuts` / `shared_theme` links. A simple review tool (CLI or dev-only page) marks them reviewed or rejected.
7. **Landmark cases.** Import Constitution Annotated's case-to-clause citations for the landmark set; fetch case data from CourtListener; record overrulings with sources; build clause pages.
8. **Source sheets and search.**
9. **Launch.** About page, accessibility pass, deploy at `library.commonhall.org`.
10. **CommonHall bridge.** Publish the static index; add "interprets" links on CommonHall's Supreme Court pages.

---

## Agent workflow

- **Importer agents** write and debug importer scripts. They do not edit files in `texts/` or `cases/` directly.
- **Linker agents** take one work section at a time (for example, one Federalist paper) and write proposals to `links/proposed/`.
- **Verification** is code, not an agent.
- **Review** is a human, optionally assisted by a separate agent that did not make the proposal.
- **Docs stay in step with code.** When a change alters behavior, the same change updates the docs, and `docs/decisions.md` gets a new entry appended at the end in number order. (The CommonHall review found duplicated README paragraphs and job tables that no longer matched the code, a common result of several agents editing in parallel.)

---

## Open decisions

- License for code (e.g. MIT, matching CommonHall) and for link data and editorial content (e.g. CC BY-SA 4.0). Source texts and court opinions are public domain.
- Federalist base edition.
- Constitution clause-numbering convention. Consider matching Constitution Annotated's numbering so its citations import cleanly.
- Which landmark cases make the first set, and how that choice is made neutrally (for example, starting from Constitution Annotated's most-cited cases per clause rather than a hand-picked list).
