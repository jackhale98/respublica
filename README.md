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
| 0. Setup | Done: Makefile, stdlib-only Python tools, `make verify`, Astro site with CSP, CI with pinned actions, licenses (provisional). |
| 1. Constitution | Done: Constitution and all 27 amendments imported from National Archives transcriptions; every clause renders with its ref. |
| 2. Federalist | Imported: all 85 papers from Project Gutenberg eBook #18, with paragraph refs, footnotes and attribution (disputed papers marked). Base edition awaits human confirmation (`docs/decisions.md` #8). |
| 3–10 | Not started. |

## Quick start

```
make verify     # unit tests + every data check (no installs needed; Python 3.13)
make build      # site into site/dist (needs Node 22.22+), then checks it
make dev        # local preview
```

`make fetch` restores raw sources from `sources/manifest.json`, and
`make import` regenerates `texts/` from them.

## Layout

```
sources/raw/        downloaded originals, never edited
sources/manifest.json
importers/          one module per source (nara.py, federalist.py)
texts/              importer output: constitution, amendments, federalist
cases/              (phase 7)
links/proposed/     machine-suggested links awaiting review
tools/              shared helpers, fetch, verify, site data, site check
tests/              unit tests for helpers and checks
site/               Astro app
docs/               references, editions, contributing, decisions, errata
```

## Docs

- [`docs/references.md`](docs/references.md): the ref scheme, including edge cases.
- [`docs/editions.md`](docs/editions.md): base editions and what importers may change.
- [`docs/contributing.md`](docs/contributing.md): pipeline, adding sources, link format, what verify checks.
- [`docs/decisions.md`](docs/decisions.md): numbered decision log.
- [`docs/errata.md`](docs/errata.md): suspected source errors, flagged not fixed.

## License

Code: MIT (`LICENSE`). Link data and editorial content: CC BY-SA 4.0. Source
texts: public domain. See [`LICENSE-DATA.md`](LICENSE-DATA.md).
