# Decisions

Append new entries at the end, in number order. Don't rewrite old entries;
add a new one that supersedes them.

## 1. Licenses (provisional)

Code is MIT; link data and editorial content in `links/` and `docs/` are
CC BY-SA 4.0; source texts are public domain. These are the plan's suggested
defaults, adopted so the repository has a license from the start. **The
project owner should confirm or replace them.** See `LICENSE-DATA.md`.

## 2. Python standard library only

Importers and tools use only the Python standard library (`html.parser`,
`urllib`, `json`, `unittest`). Nothing to pin or install, and no third-party
code runs over downloaded files. Revisit if PDF extraction (for 19th-century
scans) needs a library; ask first.

## 3. Raw sources are committed, and the manifest is the only list

Raw files live in git under `sources/raw/` so every import is reproducible
offline and checksums can be verified in CI. `sources/manifest.json` is the
only record of sources; `tools/fetch.py add` writes to it and `make fetch`
restores from it. If an upstream file changes, the restore refuses it.

## 4. Texts must be reproducible from raw files

`make verify` re-runs every importer and requires `texts/` to match byte for
byte. This is how the "texts come from code" rule is enforced: a hand edit to
`texts/` fails verification.

## 5. Constitution numbering

A clause is one paragraph of the National Archives transcription within its
section. This gives Constitution Annotated's familiar numbers (18 clauses in
Article I, Section 8; Commerce Clause `Constitution.1.8.3`). Articles V–VII
have no sections and use `Constitution.{article}.{clause}`. Closing matter and
signatures get named refs. Details: `docs/references.md`.

## 6. Amendment numbering

`Amendment.{n}.{section}` where the amendment has section headings; otherwise
`Amendment.{n}.{paragraph}`. Single-paragraph amendments are `Amendment.{n}.1`
so every amendment segment has the same shape. A multi-paragraph section is
one segment.

## 7. National Archives editorial matter is data, not text

Hyperlinks from Constitution text to later amendments become `changed_by`
records. Dates, "Note:" lines and footnotes on the amendments page become
`notes` on each amendment's division. Brackets and asterisks inside amendment
text are kept as transcribed.

## 8. Federalist base edition: Project Gutenberg eBook #18 (provisional)

Compared the plan's candidates on downloaded files:

- **Gutenberg #18** marks disputed papers ("HAMILTON OR MADISON") and joint
  ones, keeps footnotes, italics and newspaper datelines, and has clean
  blank-line paragraphing. It prints No. 70 twice.
- **Gutenberg #1404** has no disputed attributions: its bylines give 49–58
  and 62–63 to MADISON, and 18–20 to "MADISON, with HAMILTON".
- **Avalon Project** No. 10 matches #18 in wording and paragraphing, including
  the typo "wellconstructed", so it adds no independent evidence for this text.
- **Library of Congress** was not evaluated.

Chose #18. It is still an e-text, not a page-image transcription, so
differences from the newspaper printings and the McLean edition remain to be
documented. **A human should confirm this choice before Federalist refs are
treated as published.**

## 9. Federalist structure

Paragraphs are numbered from 1 after the salutation; the heading, newspaper
line, attribution, salutation and "PUBLIUS." are metadata. Footnotes are
`Federalist.{paper}.fn{n}`. The first printed version of No. 70 is the base
text; the second is kept as a variant.

## 10. Italics as spans

Italic markup is removed from `text` and kept as `emphasis` spans, so that
quotes match the words alone and the site can still render italics.

## 11. Parent refs

A link may point at a parent ref (`Constitution.1.8`, `Federalist.10`). A
quote on such a link must be found in one of the segments under it.

## 12. Site: Astro with built-in CSP

The site uses Astro's `security.csp` option, which writes a CSP meta tag with
hashes for Astro's own scripts and styles; everything else must come from
`'self'`. Stylesheets are never inlined. `tools/check_site.py` checks the
built pages. Astro is pinned to 7.3.5 (7.4.0 was three days old when the
site was set up).

## 13. One page per paper for long works

Works with more than 300 segments (currently only The Federalist) get one
page per top-level division; shorter works are one page each. Every segment's
element id is its ref, so `/texts/constitution/#Constitution.1.8.3` links to a
clause.

## 14. Licenses and Federalist edition confirmed

The project owner confirmed decision 1 (MIT for code, CC BY-SA 4.0 for link
data and editorial content) and decision 8 (Project Gutenberg eBook #18 as
the Federalist base edition) on 2026-10-18. Neither is provisional any more.

## 15. Hosting: GitHub Pages, with budgets well inside the free tier

The site is deployed to GitHub Pages by `.github/workflows/deploy.yml` on
every push to `main` (no secrets). GitHub Pages' published limits: sites up
to 1 GB, a soft 100 GB/month of bandwidth, repositories recommended under
1 GB, and files over 100 MB rejected. The site uses root-relative URLs, so it
must be served from the custom domain (`library.commonhall.org`), configured
in the repository's Pages settings.

Budgets, enforced in CI so growth is caught long before a limit:

| Where | Budget |
|---|---|
| Built site (`tools/check_site.py`) | 250 MB total, 10,000 files (half of Cloudflare Pages' 20,000 should we ever move), 5 MB per file, 400 KB of HTML per page, 60 KB of JavaScript loaded up front per page |
| Repository (`make verify`) | 40 MB per raw file, 300 MB of raw files in total, 20 MB per data file |

At launch the site is about 7 MB in about 250 files; a reader page is 13–17 KB
gzipped. Design rules that keep it that way: one page per work or paper (never
one per passage), opinions shown as linked passages and syllabus with a link to
CourtListener, per-page rather than per-ref data files for the graph view, and
text layers rather than page scans for raw sources.

## 16. Refs are locked

`refs.lock` lists every published ref. `make lock-refs` only adds; `make
verify` fails if a locked ref disappears. All 1,364 current refs are locked.

## 17. Site data comes from Python; permanent URLs

`tools/site_data.py` builds every page's structure (URLs, headings, text runs
with italics and amendment marks, connections) into `site/.data/`; Astro only
renders it. This keeps the rules in one tested place. URLs, which are as
permanent as refs (supersedes the `/texts/` URLs of decision 13):

| URL | Page |
|---|---|
| `/constitution/`, `/amendments/` | Whole work; each passage at `#{ref}` |
| `/federalist/` | Index of papers |
| `/federalist/{n}/` | One paper; each paragraph at `#{ref}` |
| `/data/refs.json` | Every ref with its label and URL |

## 18. Search: Pagefind with a custom interface

Pagefind 1.5.2 indexes the reader pages at build time. The site's own search
UI (palette on `/` or Ctrl/⌘+K, and `/search/`) parses "jump to" queries
("Fed 10", "1.8.3", "art 2 sec 1", "14th amendment") against
`/data/refs.json`, and maps Pagefind hits to the exact passage using the
position of the nearest element whose id is a ref. Results filter by work and
by author. Pagefind compiles WebAssembly, so the CSP allows
`'wasm-unsafe-eval'`, which permits WebAssembly compilation but not JavaScript
eval. `tools/check_site.py` rejects any other `unsafe-` source. Approved by
the project owner.

## 19. Graph view: our own SVG

The phase 4 graph view will be drawn with the site's own SVG code rather than
Cytoscape.js. A neighborhood is one or two hops (a few dozen nodes at most), so
no physics engine is needed, and it adds about 10 KB instead of about 350 KB of
third-party script. Approved by the project owner.

## 20. Design system shared with CommonHall

Colors, radii, shadows and type follow CommonHall's tokens (brand `#5b4cf0`,
violet-to-cyan gradient, Inter for interface text, Bricolage Grotesque for
headings) so the two sites read as one project. Texts are set in Source Serif 4.
All three fonts are OFL-licensed and self-hosted from pinned Fontsource
packages (weight-axis files only, about 50 KB each for Latin); no font or
script is loaded from another site. Light and dark themes follow the system,
with a toggle; the theme and text size are the only things stored in the
browser. Every page works without JavaScript: anchors, contents and
connections are plain HTML, and scripts only add the panel, drawer, search and
shortcuts.

## 21. Federalist author colors

Hamilton, Disputed, Joint, Madison, Jay, in that fixed order:
`#5b4cf0 #e87ba4 #eda100 #1baf7a #eb6834` (light) and
`#8b80ff #d55181 #c98500 #199e70 #d95926` (dark). Adjacent pairs pass
colorblind and normal-vision separation checks in both modes. Three light-mode
colors are below 3:1 contrast, so author colors always appear with a text
label, and the disputed segment of the authorship bar is also hatched.

## 22. Served from github.io until the subdomain is ready

Until DNS for `library.commonhall.org` is set up, the site is served at
<https://jackhale98.github.io/respublica/>, under the base path `/respublica`.
`site/site.config.json` holds the site's address and base path; Astro and
`tools/check_site.py` both read it. Templates apply the base path through
`href()`, scripts through `import.meta.env.BASE_URL`, and Pagefind through its
`baseUrl` option. Site data (`tools/site_data.py`, `/data/refs.json`) keeps
paths relative to the site root, so refs and their paths are unaffected by
where the site is hosted. Moving to the subdomain: set `"url"` to
`https://library.commonhall.org` and `"base"` to `""`, and add the custom
domain in the repository's Pages settings. This supersedes the custom-domain
requirement in decision 15.

## 23. Phase 3 method: code finds candidates, agents judge, humans review

Federalist → Constitution links were made in one run per paper
(`fed-const-{n}`), following [`linking.md`](linking.md):

1. `tools/candidates.py` lists hints: word sequences a paragraph shares with a
   clause that contain at least two or three words outside the 300 most common
   in The Federalist, and "clause … section … article" wording.
2. An agent reads the whole paper, judges each possible reference against the
   guide (quotation or unambiguous citation of a specific 1787 clause; never
   the Articles of Confederation, amendments, or general discussion), and
   writes a decisions file.
3. `tools/links.py propose` copies every quote from the passage text, assigns
   ids, refuses duplicates and writes only `suggested` links.
4. A separate agent checks a random sample plus every low-confidence link and
   reports to the human reviewer; it changes nothing.
5. Only a person marks links reviewed or rejected (`tools/links.py review`).

`created_by.model` records "Claude" without a version. Linkers also reported
suspected transcription errors in the base edition; each was confirmed in the
raw file and logged in `docs/errata.md` (errata 3–13).

## 24. Connection details load per page

With 289 links the Constitution page grew from 77 KB to 277 KB, because every
connection's rationale and quote was inlined. Pages now carry only a compact
list of connected passages (enough without JavaScript), and the panel loads
full details from `/data/conn/{page}.json` the first time a passage is
selected. The Constitution page is 122 KB (21 KB gzipped); its connection file
loads on demand. The graph view (phase 4) will use the same per-page files.

