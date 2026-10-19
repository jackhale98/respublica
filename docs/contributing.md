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
| `make import` | Runs every importer (`python -m importers`), each in a process of its own, writing `texts/` and `cases/` and `importers/outputs.json` (which files each importer writes and which raw sources it reads; decision 65). `python -m importers --only a,b` runs just those. |
| `make verify` | Runs the unit tests and every data check. Must pass before any task is finished. |
| `make lock-refs` | Adds any new refs to `refs.lock`. Run it when an importer adds passages. |
| `make build` | Builds the site data (`tools/site_data.py`), the site and its Pagefind search index into `site/dist/`, then checks the output. |
| `make dev` | Runs the site locally (search needs `make build`; the dev server has no index). |

CI runs `make verify` and `make build` on every pull request and every push to
`main`. The errata and link-review workflows run a narrower check before they
commit (decision 65): the errata workflow re-runs only the importers of the
corrected works (`python -m tools.scope`, `python -m tools.fetch --importers`,
`python -m tools.verify --importers`), the link review none, and both first
check that nothing outside those importers' outputs, `corrections/` and
`links/` changed. Every push to
`main` is built and deployed by Cloudflare to <https://respublicalibrary.org>
(`wrangler.jsonc`; build command `make build`, deploy command
`npx wrangler@4.147.0 deploy`; decision 44).

## Adding a raw source

Ask before adding a new upstream source. Then download it with the fetch tool,
which records the URL, date, sha256 and license:

```
python3 -m tools.fetch add --id my-source --url https://example.org/file.html \
    --license "Public domain (...)" --notes "What this file is"
```

Never edit files in `sources/raw/`. If an upstream file changes, record the
new version as a new source.

Importers add sources with `tools.fetch.add_source`. A source behind an API
token records `auth_env`, the name of the environment variable holding the
token (never the token); a source that answers a POST records its request
body as `post`; one fetched compressed records `encoding: gzip` and is kept as the server sent it (the UNT Digital Library's pages, decision 47). `make fetch` sends all three again when it restores a file.
Rate limits (HTTP 429) are waited out. Raw files too large for git (the U.S.
Reports scans and the Annals of Congress scans' DjVu XML,
`tools.common.UNTRACKED_RAW`) are listed in `.gitignore` and
the manifest; `make fetch` downloads them and CI caches them.

**OCR we run ourselves** (decision 46) is not a raw source: it is kept in
`sources/ocr/`, each file recorded in `sources/ocr/manifest.json` with the
Tesseract and language-data package versions, the command, and the raw
images (source id and sha256) it read. It is written by a command
(`python -m importers.annals ocr`), never by hand; importers read the kept
file, and CI never runs Tesseract. Install `tesseract-ocr` 5.3.4 (Ubuntu
24.04) only to rerun it.

## Writing an importer

- One module per source in `importers/`, exposing `run(out_dir) -> [paths]`,
  registered in `importers/__init__.py`. It writes to `texts/` unless it sets
  `OUT_DIR` (`importers/cases.py` writes `cases/`).
- Read raw files with `tools.common.read_raw_text(source_id)`; use the shared
  helpers in `tools/common.py` (HTTP, HTML parsing, whitespace, URL checks)
  rather than copying them.
- Check field names and structure against the real downloaded file before
  writing the parser.
- Fail loudly (raise) on anything unexpected, rather than guessing.
- Only the changes listed in `docs/editions.md` are allowed. Document the
  work's refs in `docs/references.md` and its edition in `docs/editions.md`.
- For a book that exists only as scans, don't write a new importer: add it
  to `importers/ratification_series.py`, which reads scans by OCR consensus
  (`docs/ocr.md`, "Adding a book or series").

## Reviewing texts read from scans

Words the scans could not settle are marked `uncertain`. To check them:

```sh
python3 -m tools.uncertain              # counts per work
python3 -m tools.uncertain cato --md    # checklist with page-image links
```

Record what the page shows on the errata page (`/errata/`), which sends it
as a GitHub issue that the errata workflow records in `corrections/`; never
edit `texts/` or `corrections/` by hand. Some words also carry a
`suggestion`: the Anti-Federalist Library's reading, where no scan reads the
word so (decision 55). The page offers it as a choice marked "Anti-Federalist
Library: check the page"; choose it only if the page image shows it (it is
recorded like any typed correction). On the owner's decision, every such
suggestion was accepted unchecked (decision 56): the text has the Library's
reading and the word stays marked, with a choice "Anti-Federalist Library, in
the text now: check the page" that confirms it. Shared misreadings go in
`docs/errata.md`. See `docs/ocr.md`, "Reviewing and correcting".

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

Texts read from scans add, per passage, `pages` (printed page numbers),
`scan` (`{item, leaves}`; for a newspaper page in Chronicling America also
`site: "loc"`, `issue`, `image` and `regions`), `uncertain` (`[{start, end,
readings}]`, with `suggestion` where the Anti-Federalist Library reads the
word differently from every scan, or `accepted` (`{source: "library", by,
at}`) where the text has the Library's reading, accepted by the owner
unchecked, decision 56) and,
once a maintainer has corrected a word, `corrected` (`[{start, end, was, by,
at}]`, decision 48), and per work `position` and `short`; see `docs/ocr.md`, "What the output records".

`cases/{cluster_id}.json` has the same shape, with `ref_prefix`
`Case.{cluster_id}` and no divisions, plus the case's `date`, `us_cite` (or
`docket`), `courtlistener_url`, `loc_url` and `pdf_url` (for a syllabus from the Court's own PDF, also
`court_print`, what the PDF is, and `pdf_first_page`, the PDF page the case
starts on), `chosen_because`
(the rules that chose it), `conan_citation`, `courtlistener_match` (when
CourtListener gave several clusters) and, when no syllabus is shown,
`syllabus_note`. Its segments are the syllabus paragraphs (`kind:
"syllabus"`, with the printed `page`).

## Links

Linking criteria and tools are in [`linking.md`](linking.md). In short:

- Linkers write a decisions file and run `python3 -m tools.links propose`,
  which copies quotes from the text, assigns ids, refuses duplicates and
  writes `status: "suggested"` records to `links/proposed/{batch}.jsonl`.
  Never write link files by hand.
- One linker run covers one unit (for example, one Federalist paper), with
  its own batch file.
- Only a human reviews: on the site's review page (`/review/`), which sends
  decisions as a GitHub issue that the review workflow records under the
  author's GitHub login, or with `python3 -m tools.links review --reviewer
  NAME`. Each link moves to `links/{batch}.jsonl` (reviewed) or
  `links/rejected/{batch}.jsonl` (rejected, kept so it is not proposed again).
  See `linking.md`, "Reviewing links". `python3 -m tools.links sample` prints
  a spot-check sheet.
- Suggested links appear on the site, labeled "Suggested" with a dashed border.

## What `make verify` checks

| Check | Rule |
|---|---|
| `budgets` | Raw files stay under 40 MB each and 300 MB in total in git (files kept out of git: 4 GiB in total, with no limit per file, and `.gitignore` must list them; CI caches each family of them under its own key); data files under 20 MB (decisions 15, 46, 49, 61). |
| `sources` | Every manifest entry has id, url, retrieved_at, sha256, license, notes and path; every raw file matches its sha256; every file in `sources/raw/` is in the manifest; every URL is http(s); `auth_env` names an environment variable; `encoding`, if any, is gzip; every file in `sources/ocr/` is recorded, matches its sha256, and names the raw images it was read from as they are in the manifest. |
| `texts` | Required fields; refs are unique and start with the work's `ref_prefix`; texts are non-empty and contain no markup; `source_ids` are in the manifest; emphasis spans are in range; every `changed_by` quote is in its text and names a real amendment; every division has segments; every URL field is http(s). For texts read from scans: each `uncertain` span lies in order inside its text (or its division's heading line, salutation or signature) and the text there is one of the scans' readings (or, for an `accepted` Library reading, the span names the owner's login and date), and a `suggestion` is one line that differs from it; `scan` names a valid archive.org item and page numbers; `kind` and `position` take known values; each `corrected` span lies in order inside its text, apart from the uncertain words, and names who corrected it and when. |
| `corrections` | Each file in `corrections/` is named after a work; each line has exactly at, by, index, now, ref, was, names a passage of that work, a GitHub login and a date, and gives one line of text. |
| `reproducible` | Re-runs every importer into a temporary directory and requires `texts/` and `cases/` to match byte for byte. Every file in them must come from an importer. |
| `refs` | Every ref in `refs.lock` still exists. Published refs are never dropped or renumbered. |
| `links` | Known keys and link types; ids match `lnk_…` and are unique across all files; both refs exist; quotes are exact substrings (whitespace and quote-mark style only); a rationale, or a source for imported links; `created_by` is complete; proposals are `suggested`; reviewed links name a reviewer; `overrules` links are case-to-case and cite a source; `interprets` links start from a case; URLs are http(s). |
| `overruled` | Every link touching an overruled case is flagged in the site's link data. |

Unit tests in `tests/` exercise these checks against bad records.

`make build` also runs `tools/check_site.py` on the built site: one strict
Content Security Policy per page (only `'self'`, hashes, and
`'wasm-unsafe-eval'` for search; the errata page alone may load page images
from the Internet Archive, UNT and the Library of Congress), no third-party or inline scripts, no inline
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
