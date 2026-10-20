# Res Publica

A free, open-source library of America's founding texts, where every passage
has a permanent reference and every connection between passages records who
made it, why, and whether a person has reviewed it. Static site, no server,
no accounts. Live at <https://respublicalibrary.org>.

See [`PLAN.md`](PLAN.md) for the full plan and [`CLAUDE.md`](CLAUDE.md) for
the rules every contributor (human or agent) follows.

## Status

| Phase | State |
|---|---|
| 0. Setup | Done: Makefile, stdlib-only Python tools, `make verify`, Astro site with CSP, CI with pinned actions, deploy to Cloudflare (respublicalibrary.org), free-tier budgets, MIT + CC BY-SA 4.0. |
| 1. Constitution | Done: Constitution and all 27 amendments imported from National Archives transcriptions; every clause renders with its ref. The Declaration of Independence added the same way (each grievance its own passage), and Congress's 1789 Joint Resolution proposing twelve amendments (each article its own passage). Two works the Declaration's language draws on (decision 67): Thomas Paine's *Common Sense* (the first edition, Philadelphia, January 1776) and John Locke's Second Treatise of Government (the first edition, London, 1690; refs by Locke's own sections), from the Text Creation Partnership's CC0 transcriptions, checked word by word against Internet Archive scans of the same printings, with differences marked uncertain. |
| 2. Federalist | Done: all 85 papers from Project Gutenberg eBook #18, with paragraph refs, footnotes and attribution (disputed papers marked). |
| 3. Explicit links | Linked: 289 suggested links from 51 Federalist papers to 73 clauses of the Constitution (81 quotations, 208 citations), awaiting human review. See [`docs/linking.md`](docs/linking.md). |
| 4. Connections panel and graph | Done: the panel (a bottom sheet on phones) lists each passage's connections; "Graph" opens a two-hop graph of them (force layout with zoom, pan and drag; d3), filterable by link type, side (founding documents, Federalist, Anti-Federalist) and review status. |
| 5. Ratification debate | Imported: 22 works (about 287k words) from Ford's *Essays* (every section), Ford's *Pamphlets* (the Federal Farmer), McMaster and Stone (Centinel I–XXIV and the Dissent of the Pennsylvania Minority, with its fourteen proposed amendments), the Massachusetts convention's *Debates* (1856; Brutus I–IV), the *New-York Journal* itself (Brutus V–XVI but XI, from the Library of Congress's single scan, about 14% of words marked uncertain) and Elliot's *Debates* (Patrick Henry's twenty-four speeches in the Virginia convention), both sides, read from scans by OCR consensus with uncertain words marked (method: [`docs/ocr.md`](docs/ocr.md)). The debates of nine state ratifying conventions (Massachusetts, Connecticut, New Hampshire, New York, Pennsylvania, Maryland, Virginia, North and South Carolina; about 641,000 words, 110 days and two undated pieces) from the Library of Congress's typed transcription of Elliot's *Debates*, vols. 2–4, checked word by word against scans of the same printing, with about 750 words (one in 850) marked uncertain where the scans read another word; the same transcription now breaks ties for Henry's speeches before the Anti-Federalist Library (decision 68). Debates in Congress (`/congress/`): the House of Representatives' 1789 debate on the amendments (twelve days, from Madison's speech of June 8) from the Annals of Congress, read from two scans and a Tesseract reading of the first (decision 46); both houses' proceedings on the Eleventh Amendment (1794) and the Twelfth (the attempt of 1802 and the debates of 1803, about 180,000 words, six works) from volumes 4, 11 and 13 of the Annals, each read from three readings, only the pages needed kept (decision 60); both houses' 1866 debates on the Fourteenth Amendment (fourteen days, about 250,000 words) from the Congressional Globe, read from the UNT Digital Library's OCR and checked against Internet Archive scans of two other copies (decisions 47 and 58); and, the same way, both houses' debates on the Thirteenth Amendment (1864–65, 25 days, about 470,000 words, three works) and the Fifteenth (1869, 29 days, about 410,000 words, two works) (decision 57); and both houses' proceedings on the Sixteenth to Nineteenth Amendments (1909–19, 56 days, about 834,000 words, eleven works) from the bound Congressional Record, read from the text layer of govinfo.gov's scans and checked against the Internet Archive's microfilm, about 4% of words marked uncertain (decision 61); and, the same way, the Twentieth to Twenty-sixth Amendments (1932–71, 52 days, about 1,371,000 words, fourteen works, about 1.4% marked uncertain; decision 62). The Twenty-seventh's proposing debate is the House's of 1789. The Anti-Federalist Library's text breaks ties between scans (decision 55), and on the owner's decision its 3,041 suggested readings are in the text, still marked as unchecked until read off the page image on the errata page (decision 56). Brutus XI has no scan and is not imported. The rest of Ford's *Pamphlets* is next. See [`docs/editions.md`](docs/editions.md). |
| 6. Debate links and review | Linked: 453 suggested links from 18 debate works and The Federalist: 366 to 75 clauses of the Constitution, 2 to the Declaration and 85 between essays (responses, rebuttals, quotations and citations, such as Cato and Caesar's exchange, Luther Martin and the Landholder's, and the essays that point readers to Brutus), checked by a second agent and awaiting human review. A review page (`/review/`) lets a maintainer approve or reject links in batches and records the decisions through a GitHub issue. See [`docs/linking.md`](docs/linking.md), "Run 2" and "Reviewing links". |
| 7. Landmark cases | Imported: 232 Supreme Court cases chosen by fixed rules from the 2022 Constitution Annotated (decisions 41–43 and 53), each keyed by its CourtListener cluster, with a page of its own (`/cases/`): the syllabus as printed in the United States Reports for 202 of them, read from the Library of Congress scans or, for nine recent cases, the Supreme Court's own PDFs (decision 54), and a link to the full opinion on CourtListener. 356 suggested `interprets` links (a case to the provisions whose essays cite it on two or more pages) and 60 `overrules` links from the official table of overruled decisions, awaiting review; clauses list the cases that interpret them, in date order, with overruled cases marked. See [`docs/editions.md`](docs/editions.md) and decision 49. Five syllabi the reader cannot yet follow are left out, and each case says why. |
| 8. Search | Pagefind full-text search plus "jump to" any ref. Source sheets not started. |
| 9–10 | Not started. |

## The site

A reader built around passages: pick any passage to see its permanent ref,
copy a link or the text, and see its connections in a side panel (a bottom
sheet on phones), with a preview of each linked passage to read it in
place. Contents that reach every clause and paragraph (a slide-out
drawer on narrow screens; it follows the passage being read), `j`/`k` to move
between passages,
`/` or Ctrl/⌘+K to search (matching passages appear as you type; Enter opens a
full results page with every matching passage, filterable by text and author)
or jump ("Fed 10", "1.8.3", "Amendment 14"), light
and dark themes, adjustable text size and line spacing (remembered in the browser), The
Federalist's papers filterable by author, a page for each Supreme Court case
(`/cases/`) with its syllabus as printed, the provisions it is cited under and
any overruling, a page for each clause of the Constitution and each section of an amendment (`/constitution/1/8/18/`) gathering the debate's links and the cases on it, a map of every link and case along the founding documents (`/map/`), a review page for maintainers (`/review/`), and an errata page (`/errata/`) on which they read uncertain words off the page images. Reading settings ("Aa" in the header: text size for the library's texts everywhere, line spacing, theme), "Where you've been" (a history of the places read, with Back, Forward and Clear, and a "Back to …" button after any jump) and "Continue reading" on the home page and each work's page are kept only in the reader's browser. Every page works without JavaScript except those two; the map shows its counts as a table.

## Quick start

```
make verify     # unit tests + every data check (no installs needed; Python 3.13)
make build      # site + search index into site/dist (needs Node 22.22+), then checks it
make dev        # local preview (search needs make build)
```

`make fetch` restores raw sources from `sources/manifest.json` (run it
first in a fresh clone: the U.S. Reports scans, about 330 MB, and the
Congressional Record's govinfo PDFs, about 2.1 GB, are not in git), `make import` regenerates `texts/` and `cases/` from them, and
`make lock-refs` records new refs in `refs.lock`. Looking up new cases on
CourtListener (`python -m importers.courtlistener lookup`) needs an API
token in `COURTLISTENER_TOKEN`.

Deployment: the site is served at <https://respublicalibrary.org> by
Cloudflare, which builds this repository (`make build`) and deploys
`site/dist` on every push to `main` (`wrangler.jsonc`; response headers in
`site/public/_headers`). The address is set in `site/site.config.json`
(docs/decisions.md 44).

## Layout

```
sources/raw/        downloaded originals, never edited (scans too large for git, such as the U.S. Reports and the Congressional Record's PDFs, are kept out of it; `make fetch`)
sources/manifest.json
sources/ocr/        OCR we ran ourselves on raw page images, with a record of how (decision 46)
importers/          one module per source (nara.py, federalist.py, annals.py, cases.py, …)
texts/              importer output: constitution, amendments, federalist
refs.lock           every published ref (append-only)
cases/              importer output: one file per Supreme Court case
links/proposed/     machine-suggested links awaiting review
corrections/        words read off the page images by maintainers, applied by the importers
tools/              shared helpers, fetch, verify, refs, site data, site check
tests/              unit tests for helpers, checks and site data
site/               Astro app (renders site/.data from tools/site_data.py)
docs/               references, editions, ocr, contributing, decisions, errata
```

## Docs

- [`docs/references.md`](docs/references.md): the ref scheme, including edge cases.
- [`docs/editions.md`](docs/editions.md): base editions and what importers may change.
- [`docs/ocr.md`](docs/ocr.md): how texts are read from scans by OCR consensus (or, where the Text Creation Partnership has keyed a printing, checked against scans), how well it works, and how to review uncertain words.
- [`docs/contributing.md`](docs/contributing.md): pipeline, adding sources, link format, what verify checks.
- [`docs/decisions.md`](docs/decisions.md): numbered decision log.
- [`docs/handoff.md`](docs/handoff.md): where the work stands and what comes next, for a new session.
- [`docs/errata.md`](docs/errata.md): suspected source errors, flagged not fixed.

## License

Code: MIT (`LICENSE`). Link data and editorial content: CC BY-SA 4.0. Source
texts: public domain. See [`LICENSE-DATA.md`](LICENSE-DATA.md).
