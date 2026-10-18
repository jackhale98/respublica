# Res Publica

A free, open-source library of America's founding texts, where every passage
has a permanent reference and every connection between passages records who
made it, why, and whether a person has reviewed it. Static site, no server,
no accounts. Planned home: `library.commonhall.org`.

See [`PLAN.md`](PLAN.md) for the full plan and [`CLAUDE.md`](CLAUDE.md) for
the rules every contributor (human or agent) follows.

## Status

| Phase | State |
|---|---|
| 0. Setup | Done: Makefile, stdlib-only Python tools, `make verify`, Astro site with CSP, CI and GitHub Pages deploy with pinned actions, free-tier budgets, MIT + CC BY-SA 4.0. |
| 1. Constitution | Done: Constitution and all 27 amendments imported from National Archives transcriptions; every clause renders with its ref. The Declaration of Independence added the same way (each grievance its own passage). |
| 2. Federalist | Done: all 85 papers from Project Gutenberg eBook #18, with paragraph refs, footnotes and attribution (disputed papers marked). |
| 3. Explicit links | Linked: 289 suggested links from 51 Federalist papers to 73 clauses of the Constitution (81 quotations, 208 citations), awaiting human review. See [`docs/linking.md`](docs/linking.md). |
| 4. Connections panel and graph | Done: the panel (a bottom sheet on phones) lists each passage's connections; "Graph" opens a two-hop graph of them (force layout with zoom, pan and drag; d3), filterable by link type, side (founding documents, Federalist, Anti-Federalist) and review status. |
| 5. Ratification debate | Imported: 20 works (187k words) from Ford's *Essays* (every section), Ford's *Pamphlets* (the Federal Farmer), McMaster and Stone (Centinel I–XXIV) and the Massachusetts convention's *Debates* (1856; Brutus I–IV), both sides, read from scans by OCR consensus with uncertain words marked (method: [`docs/ocr.md`](docs/ocr.md)). Brutus V–XVI: only in the original newspaper (Library of Congress, poor OCR from a single scan), not yet imported. The rest of Ford's *Pamphlets* is next. See [`docs/editions.md`](docs/editions.md). |
| 6. Debate links and review | Linked: 453 suggested links from 18 debate works and The Federalist: 366 to 75 clauses of the Constitution, 2 to the Declaration and 85 between essays (responses, rebuttals, quotations and citations, such as Cato and Caesar's exchange, Luther Martin and the Landholder's, and the essays that point readers to Brutus), checked by a second agent and awaiting human review. A review page (`/review/`) lets a maintainer approve or reject links in batches and records the decisions through a GitHub issue. See [`docs/linking.md`](docs/linking.md), "Run 2" and "Reviewing links". |
| 7. Landmark cases | In progress: the 2022 Constitution Annotated is read from its PDFs (`importers/conan.py`): which clauses' essays cite each case, and the official table of overruled decisions. The first set is 213 cases (decisions 41–43). Importing them waits on a CourtListener API token. See [`docs/handoff.md`](docs/handoff.md). |
| 8. Search | Pagefind full-text search plus "jump to" any ref. Source sheets not started. |
| 9–10 | Not started. |

## The site

A reader built around passages: pick any passage to see its permanent ref,
copy a link or the text, and see its connections in a side panel (a bottom
sheet on phones). Contents that reach every clause and paragraph (a slide-out
drawer on narrow screens; it follows the passage being read), `j`/`k` to move
between passages,
`/` or Ctrl/⌘+K to search (matching passages appear as you type; Enter opens a
full results page with every matching passage, filterable by text and author)
or jump ("Fed 10", "1.8.3", "Amendment 14"), light
and dark themes, adjustable text size (remembered in the browser), The
Federalist's papers filterable by author, and a review page for maintainers
(`/review/`). Every page works without JavaScript except the review page.

## Quick start

```
make verify     # unit tests + every data check (no installs needed; Python 3.13)
make build      # site + search index into site/dist (needs Node 22.22+), then checks it
make dev        # local preview (search needs make build)
```

`make fetch` restores raw sources from `sources/manifest.json`,
`make import` regenerates `texts/` from them, and `make lock-refs` records
new refs in `refs.lock`.

Deployment: pushes to `main` publish to GitHub Pages, currently at
<https://jackhale98.github.io/respublica/>. The address is set in
`site/site.config.json`; moving to `library.commonhall.org` later means
setting `"url"` to that domain and `"base"` to `""` (docs/decisions.md 22).

## Layout

```
sources/raw/        downloaded originals, never edited
sources/manifest.json
importers/          one module per source (nara.py, federalist.py)
texts/              importer output: constitution, amendments, federalist
refs.lock           every published ref (append-only)
cases/              (phase 7)
links/proposed/     machine-suggested links awaiting review
tools/              shared helpers, fetch, verify, refs, site data, site check
tests/              unit tests for helpers, checks and site data
site/               Astro app (renders site/.data from tools/site_data.py)
docs/               references, editions, ocr, contributing, decisions, errata
```

## Docs

- [`docs/references.md`](docs/references.md): the ref scheme, including edge cases.
- [`docs/editions.md`](docs/editions.md): base editions and what importers may change.
- [`docs/ocr.md`](docs/ocr.md): how texts are read from scans by OCR consensus, how well it works, and how to review uncertain words.
- [`docs/contributing.md`](docs/contributing.md): pipeline, adding sources, link format, what verify checks.
- [`docs/decisions.md`](docs/decisions.md): numbered decision log.
- [`docs/handoff.md`](docs/handoff.md): where the work stands and what comes next, for a new session.
- [`docs/errata.md`](docs/errata.md): suspected source errors, flagged not fixed.

## License

Code: MIT (`LICENSE`). Link data and editorial content: CC BY-SA 4.0. Source
texts: public domain. See [`LICENSE-DATA.md`](LICENSE-DATA.md).
