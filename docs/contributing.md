# Contributing

Read `CLAUDE.md` first; its rules apply to people and agents alike.

## Setup

- Python 3.13 (`.python-version`). The Python tools use only the standard
  library, so there is nothing to install.
- Node 22.22.0 or later (`site/.nvmrc`) for the site. `make build` runs
  `npm ci` in `site/` the first time.

## Pipeline

| Command | What it does |
|---|---|
| `make fetch` | Restores any raw file listed in `sources/manifest.json` that is missing locally. Refuses a download whose checksum no longer matches. |
| `make import` | Runs every importer (`python -m importers`), writing `texts/`. |
| `make verify` | Runs the unit tests and every data check. Must pass before any task is finished. |
| `make lock-refs` | Adds any new refs to `refs.lock`. Run it when an importer adds passages. |
| `make build` | Builds the site data (`tools/site_data.py`), the site and its Pagefind search index into `site/dist/`, then checks the output. |
| `make dev` | Runs the site locally (search needs `make build`; the dev server has no index). |

CI runs `make verify` and `make build` on every pull request. Every push to
`main` also deploys `site/dist/` to GitHub Pages (`.github/workflows/deploy.yml`).

## Adding a raw source

Ask before adding a new upstream source. Then download it with the fetch tool,
which records the URL, date, sha256 and license:

```
python3 -m tools.fetch add --id my-source --url https://example.org/file.html \
    --license "Public domain (...)" --notes "What this file is"
```

Never edit files in `sources/raw/`. If an upstream file changes, record the
new version as a new source.

## Writing an importer

- One module per source in `importers/`, exposing `run(out_dir) -> [paths]`,
  registered in `importers/__init__.py`.
- Read raw files with `tools.common.read_raw_text(source_id)`; use the shared
  helpers in `tools/common.py` (HTTP, HTML parsing, whitespace, URL checks)
  rather than copying them.
- Check field names and structure against the real downloaded file before
  writing the parser.
- Fail loudly (raise) on anything unexpected, rather than guessing.
- Only the changes listed in `docs/editions.md` are allowed. Document the
  work's refs in `docs/references.md` and its edition in `docs/editions.md`.

## Text files

`texts/{work}.json`:

```json
{
  "id": "federalist",
  "title": "The Federalist",
  "ref_prefix": "Federalist",
  "attribution": {"kind": "pseudonym", "names": ["…"], "pseudonym": "Publius"},
  "date": "1787-11-20/1788-04-04",
  "edition": {"name": "…", "notes": "…"},
  "source_ids": ["gutenberg-federalist-18"],
  "divisions": [{"ref": "Federalist.10", "level": 1, "label": "…", "…": "…"}],
  "segments": [{"ref": "Federalist.10.1", "label": "…", "text": "…", "emphasis": [[0, 4]]}]
}
```

`attribution.kind` is one of `single`, `joint`, `disputed` (with the candidate
authors in `names`), `pseudonym` or `body`.

## Links

Linking criteria and tools are in [`linking.md`](linking.md). In short:

- Linkers write a decisions file and run `python3 -m tools.links propose`,
  which copies quotes from the text, assigns ids, refuses duplicates and
  writes `status: "suggested"` records to `links/proposed/{batch}.jsonl`.
  Never write link files by hand.
- One linker run covers one unit (for example, one Federalist paper), with
  its own batch file.
- Only a human reviews: `python3 -m tools.links review --reviewer NAME` moves
  each link to `links/{batch}.jsonl` (reviewed) or `links/rejected/{batch}.jsonl`
  (rejected, kept so it is not proposed again). `python3 -m tools.links sample`
  prints a spot-check sheet.
- Suggested links appear on the site, labeled "Suggested" with a dashed border.

## What `make verify` checks

| Check | Rule |
|---|---|
| `budgets` | Raw files stay under 40 MB each and 300 MB in total; data files under 20 MB (decision 15). |
| `sources` | Every manifest entry has id, url, retrieved_at, sha256, license, notes and path; every raw file matches its sha256; every file in `sources/raw/` is in the manifest; every URL is http(s). |
| `texts` | Required fields; refs are unique and start with the work's `ref_prefix`; texts are non-empty and contain no markup; `source_ids` are in the manifest; emphasis spans are in range; every `changed_by` quote is in its text and names a real amendment; every division has segments; every URL field is http(s). For texts read from scans: each `uncertain` span lies in order inside its text (or its division's heading line, salutation or signature) and the text there is one of the scans' readings; `scan` names a valid archive.org item and page numbers; `kind` and `position` take known values. |
| `reproducible` | Re-runs every importer into a temporary directory and requires `texts/` to match byte for byte. Every file in `texts/` must come from an importer. |
| `refs` | Every ref in `refs.lock` still exists. Published refs are never dropped or renumbered. |
| `links` | Known keys and link types; ids match `lnk_…` and are unique across all files; both refs exist; quotes are exact substrings (whitespace and quote-mark style only); a rationale, or a source for imported links; `created_by` is complete; proposals are `suggested`; reviewed links name a reviewer; `overrules` links are case-to-case and cite a source; `interprets` links start from a case; URLs are http(s). |
| `overruled` | Every link touching an overruled case is flagged in the site's link data. |

Unit tests in `tests/` exercise these checks against bad records.

`make build` also runs `tools/check_site.py` on the built site: one strict
Content Security Policy per page (only `'self'`, hashes, and
`'wasm-unsafe-eval'` for search), no third-party or inline scripts, no inline
event handlers or style attributes, only http(s) absolute URLs, no broken
internal links or anchors, every segment ref rendered on some page, and the
free-tier budgets of decision 15.

## The site

- `tools/site_data.py` turns `texts/`, `cases/` and `links/` into
  `site/.data/` (one JSON file per page, plus each page's two-hop link
  graph in `site/.data/graph/`). Page structure, URLs, text runs
  (italics, amendment marks) and how connections are shown are decided there
  and tested in `tests/test_site_data.py`. Astro only renders.
- URLs are permanent (decision 17). Every passage's element id is its ref.
- The site may be served under a base path (`site/site.config.json`). Never
  write a root-relative URL directly in a template or script: pass it through
  `href()` (templates) or the `BASE` constant (scripts). `tools/check_site.py`
  fails on any internal link outside the base path.
- Styles live in `site/src/styles/` (`tokens.css` holds the design tokens
  shared with CommonHall). Scripts live in `site/src/scripts/`; each is a
  progressive enhancement, and every page must work without JavaScript.
- No third-party scripts or fonts are loaded from other sites. Fonts come
  from pinned Fontsource packages. Ask before adding any dependency.
