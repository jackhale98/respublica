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
| `make build` | Builds link data for the site, builds the site into `site/dist/`, and checks the output. |
| `make dev` | Runs the site locally. |

CI runs `make verify` and `make build` on every pull request.

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

Agents write proposals to `links/proposed/{batch}.jsonl`, one JSON object per
line, using the record format in `PLAN.md`. A proposal must have
`status: "suggested"`, a `rationale`, a `confidence`, and `created_by` with
`kind`, `model` and `run`. Copy any `from_quote` / `to_quote` from the text
file programmatically. Only a human sets `status: "reviewed"` (with
`reviewed_by`) or `"rejected"`.

One linker run covers one unit (for example, one Federalist paper).

## What `make verify` checks

| Check | Rule |
|---|---|
| `sources` | Every manifest entry has id, url, retrieved_at, sha256, license, notes and path; every raw file matches its sha256; every file in `sources/raw/` is in the manifest; every URL is http(s). |
| `texts` | Required fields; refs are unique and start with the work's `ref_prefix`; texts are non-empty and contain no markup; `source_ids` are in the manifest; emphasis spans are in range; every `changed_by` quote is in its text and names a real amendment; every division has segments; every URL field is http(s). |
| `reproducible` | Re-runs every importer into a temporary directory and requires `texts/` to match byte for byte. Every file in `texts/` must come from an importer. |
| `links` | Known keys and link types; ids match `lnk_…` and are unique across all files; both refs exist; quotes are exact substrings (whitespace and quote-mark style only); a rationale, or a source for imported links; `created_by` is complete; proposals are `suggested`; reviewed links name a reviewer; `overrules` links are case-to-case and cite a source; `interprets` links start from a case; URLs are http(s). |
| `overruled` | Every link touching an overruled case is flagged in the site's link data. |

Unit tests in `tests/` exercise these checks against bad records.

`make build` also runs `tools/check_site.py` on the built site: one strict
Content Security Policy per page, no third-party or inline scripts, no inline
event handlers or style attributes, only http(s) absolute URLs, no broken
internal links or anchors, and every segment ref rendered on some page.
