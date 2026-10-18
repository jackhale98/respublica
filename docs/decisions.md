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

## 25. Search shows passages, and Enter shows all results

Readers reported that search jumped to the first hit instead of letting them
choose. Now:

- The search box shows the best matching passages as you type, each with its
  own excerpt; Enter opens `/search/?q=…`, which lists every matching passage
  grouped by text, with filters by text and (for The Federalist) by author.
  Arrow keys then Enter still open a single result.
- Pagefind ranks pages, so results are rebuilt per passage in the browser: a
  page's matched word positions are grouped by passage (each passage's element
  id is its ref) and each passage gets its own excerpt. A passage must contain
  every significant query word; exact phrases rank first, then words close
  together.
- The Constitution and the Amendments are each one long page, which page-level
  ranking underrates, so they are looked up directly for every query and
  listed first when they match; on equal matches the constitutional text
  ranks above writing about it.
- Connection-count badges are excluded from the index, and each paper's
  number is stored as Pagefind metadata so results read "Federalist No. 84: …".

## 26. Graph view

The passage panel's "Graph" button opens a dialog drawn by
`site/src/scripts/graph.ts` in plain SVG (decision 19):

- The selected passage is at the center; its direct connections sit on an
  inner ring, and their connections on an outer ring, fanned out behind the
  passage that leads to them. Up to 28 and 48 nodes are drawn; the count of
  any left out is shown.
- Nodes are colored by work (Constitution, Amendments, The Federalist; colors
  validated for color-vision deficiency in both themes) and always labeled.
  Edges point from the citing passage to the cited one; quotations are drawn
  thicker; suggested links are dashed.
- Filters: link type, work, and reviewed links only. Clicking or pressing
  Enter on a node shows its links and offers "Open passage" and "Center here".
- Data: `/data/graph/{page}.json`, built by `tools/site_data.py` with every
  link within two hops of the page's passages (rejected links excluded). One
  file per page, not per ref, keeps the file count low (decision 15). The
  largest, the Constitution's, is 74 KB and loads only when a graph is opened.


## 27. The ratification debate is read from scans, by consensus

No accurate public-domain digital text of the ratification essays exists, so
phase 5 reads them from OCR scans of three 1888–1892 compilations (Ford's
*Essays* and *Pamphlets*; McMaster and Stone). One scan's DjVu XML gives the
layout; other scans of the same printed edition check each word; a vote with
strict limits settles disagreements, and words it cannot settle are kept as
the main scan reads them and marked `uncertain`, with every reading, for a
human to check against the page image (docs/editions.md). The project owner
chose this over importing one scan as is, and over waiting for a hand-checked
transcription.

- Both sides are imported, grouped by `position`, which is Res Publica's
  label. Attributions are the editions' own.
- Every passage records its scan pages (`scan`), and the site links each
  paragraph to its page image on archive.org.
- Essay numbers follow the print; a number printed twice gets a letter
  (`Landholder.10b`, `Agrippa.15b`).
- Brutus is not imported: no public-domain printing was found.
- URLs: `/ratification/` lists the works; a series has one page per essay
  (`/cato/3/`), a single piece one page (`/caution/`).

## 28. Graph view drawn with d3, and a clearer connection badge

At the project owner's request (the graph "should be much more attractive",
and a library may be used), the graph view now uses d3 modules in place of
the hand-placed radial layout of decision 26 (which replaced decision 19's
"no library"):

- `d3-force` lays the graph out: the selected passage is fixed at the
  center, direct connections are pulled toward an inner ring and passages two
  steps away toward an outer one, with link, repulsion and collision forces
  so labels don't overlap. `d3-zoom` and `d3-drag` add pan, zoom (buttons,
  wheel, pinch) and dragging passages; double-click re-centers.
- Passages are drawn as label chips with a dot in their work's color; the
  center is larger, tinted and outlined in its color. Links are gentle arcs
  with arrowheads at the passage cited or quoted; quotations are thicker and
  tinted; suggested links are dashed. Hovering or selecting a passage lights
  its links (with their type) and fades the rest.
- The modules are npm packages pinned to exact versions
  (`d3-force` 3.0.0, `d3-selection` 3.0.0, `d3-zoom` 3.0.0, `d3-drag` 3.0.0,
  `d3-transition` 3.0.1) and bundled into the graph script, which loads only
  when a reader opens the graph (72 KB, outside the per-page JavaScript
  budget, which counts scripts loaded up front). Nothing loads from another
  site; the CSP is unchanged.
- With reduced motion, the layout is computed before it is shown and
  nothing animates.

The connection count beside a passage is now a pill with a link icon at the
top right of its text, instead of a bare number under the paragraph number,
which read as a second paragraph number.

## 29. OCR consensus documented, and its vote tightened by sampling

`docs/ocr.md` is the reference for reading texts from scans: the method
step by step, what the output records, measured accuracy, known limits, the
review process (`python -m tools.uncertain`), and how to add a book.
`docs/editions.md` keeps only the editions and points there.

Reading random samples of the vote's corrections found wrong changes, and
each led to a rule: capitals from a misplaced signature never replace a
lower-case word; a much shorter reading (a line-end fragment) never replaces
a longer one; a join is taken only when it is a known word and the pieces
are not; two different stops together count as noise unless two scans agree;
a slash is a stray mark; and of readings with the same letters, the one
ending like the main scan's is preferred. With these, 116 of 120 sampled
changes were clearly right and none replaced a real word with a different
one; uncertain words rose from 459 to 611. The rules lean toward marking a
word uncertain over guessing.

## 30. Logo, app icons and the nib loader

The mark is a pen nib, for the pen that signed the founding texts; its
breather hole doubles as a node, for passages joined by links. It uses the
CommonHall gradient from `tokens.css`.

- `site/public/`: `logo.svg` (the mark), `favicon.svg` (lighter stops in dark
  mode), `favicon.ico` (16/32/48), `icon.svg` with `icon-192.png`,
  `icon-512.png`, `icon-maskable-512.png` (mark inside the maskable safe zone)
  and `apple-touch-icon.png`, all the mark on white. `site.webmanifest` uses
  relative URLs so it works under any `base`.
- `loader.svg` is the loading animation, in SVG with SMIL so it needs no
  script and runs inside an `<img>`: the nib springs up, inks a ring linking
  three nodes around its own resting place, lands, and the ink drains back
  into the breather hole. It starts and ends on the static mark. It replaces
  the "Searching…" and "Loading connections…" text-only states
  (`scripts/loader.ts`). Readers who prefer reduced motion get
  `loader-still.svg`, the resting frame, since CSS can't pause SMIL.
- Easter egg: pressing the footer logo (`components/LogoEgg.astro`) plays the
  same animation once. Its animations all begin with `#rpeggGo` and freeze
  on the resting pose; `site.ts` makes it a button only when JavaScript runs
  and motion is allowed, so without either it is just the logo.

## 31. Reader gestures and the place bar

- **Swipe for contents.** Where the contents are a drawer (below 80rem), a
  left-to-right swipe across the page opens them and a right-to-left swipe
  closes them. A swipe must be mostly horizontal, at least 70px, and quick;
  swipes that start within 24px of the left edge are left to the browser's
  own back gesture, and swipes in the passage panel, dialogs, tables or
  form fields are ignored.
- **Place bar.** Scrolling back up a little (24px), once past the page
  heading, shows a slim bar under the header naming the page ("Federalist
  No. 10 · The Same Subject Continued…", "Constitution") and, on pages with
  headings, the division being read ("Article I, Section 9"). Scrolling down
  or returning to the top hides it. The bar opens the contents on narrow
  screens and scrolls to the division's heading on wide ones; a button goes
  back to the top. It is `inert` while hidden, absent without JavaScript,
  and does not animate for readers who prefer reduced motion.

## 32. The Declaration of Independence is a founding document

At the project owner's request, the Declaration is imported alongside the
Constitution, though it is not law: the library holds the founding texts,
and the Declaration is what The Federalist, the Anti-Federalists and the
Supreme Court argue from and cite. It comes from the same upstream as the
Constitution (the National Archives transcription), is listed first among
the founding documents (1776), and is linked like any other text, but links
to it are never `interprets`, which is for courts construing law.
Refs: `docs/references.md`.

## 33. Links in the ratification debate (run 2)

- **One run per essay.** Code lists the candidates in each essay (clause
  references, quotations of the Constitution and the Declaration, and the
  names of other writers in the library: `tools.candidates --ref`); an agent
  reads the essay and decides; `tools.links propose` writes the links. Every
  link is `suggested` until a person reviews it. The rules agents followed,
  including those settled during the run (references to a writer's own
  earlier numbers, bare mentions, editor's notes without an "Ed." mark), are
  in `docs/linking.md`, "Run 2".
- **Independent check.** A second agent, which did not write the links,
  checked every link between essays and a random sample of the links to the
  Constitution against both texts (151 links). Of those, 143 were sound;
  the 8 it found wrong or doubtful were removed or corrected before
  publishing (details in `docs/linking.md`). Everything is left for human
  review.
- **Signatures run into the text.** Linking showed signatures the importer
  had left at the end of an essay's last paragraph, sometimes with a place
  and date after them ("… oppression ? CenTinei,. Philadelphia, Nov. 30,
  1787."). The importer now moves such a signature (and the place and date
  after it) to the essay's signature when it starts a sentence. No ref
  changes; two passages lose their closing line. Other suspected errors the
  linkers saw are in `docs/errata.md` (16–23).
- **Graph colors by side.** With twenty works, one color per work cannot be
  told apart, so graph nodes are colored by group: founding documents, The
  Federalist and Federalist essays, Anti-Federalist essays, and other pieces
  (validated for color-vision deficiency in light and dark). The graph's
  "Show" filters use the same groups; each node still names its work.
- **Single pieces.** A link to a whole single piece (`Caution`) points at
  its page.

## 34. Brutus from the 1856 Massachusetts *Debates*

At the project owner's choice, Brutus I–IV are imported from *Debates and
Proceedings in the Convention of the Commonwealth of Massachusetts* (Boston,
1856), which reprints them from the Boston *Independent Chronicle* in its
"Spirit of the Press" section. It is a public-domain book on the Internet
Archive with four scans of the same edition, so it is read by OCR consensus
like the other debate texts (one primary, three references), with the same
fidelity. The original *New-York Journal* printing, in the Library of
Congress's Chronicling America, was not used: one scan per page, poor OCR,
and three essays missing. Brutus V–XVI wait on a source of that quality.

- **Text and dates.** The text is the 1856 reprint's (its editors
  regularized spelling; it has no newspaper headings or salutations). The
  work's dates are those of first publication in New York (October 18 to
  November 29, 1787), as for the other series.
- **Attribution.** The 1856 book gives none; Ford's note to Webster's reply
  (*Pamphlets*, 1888, p. 117) suggests Thomas Treadwell with a query, recorded as
  "Thomas Treadwell?".
- **Layout rules.** This book's running heads are often read as two blocks
  on one line, or run into the paragraph below; a per-book `split_heads`
  rule sets them aside. It is not applied to the earlier books, where it
  would join two published paragraphs of Cassius IV (erratum 17). A
  capitalized word and a period alone at the foot of a page ("Brutus.") is
  a signature, not a page number.

## 35. Joining a split paragraph: retired refs

The layout rule for running heads read as two blocks (decision 34) also
finds one in Ford's *Essays*, p. 17, where Cassius IV's fourth paragraph had
been imported as two (`Cassius.4.4` ending "blinded them with", `Cassius.4.5`
beginning "17 respect …"). At the project owner's decision the rule now
applies to every book, and the paragraph is whole again.

Rule 6 still holds: no ref is renumbered. `Cassius.4.5` is **retired**: the
work lists it with the passage it was merged into and why, the number is
never reused, the paragraphs after it keep their refs (`Cassius.4.6` …),
it stays in `refs.lock`, and its URL leads to an anchor inside
`Cassius.4.4`. Nothing linked to it. The mechanism is general
(`docs/references.md`, "Retired refs"), but each use needs an erratum and a
decision like this one.

## 36. Renumbering before launch

The site has not launched, so the project owner chose to renumber Cassius
IV rather than retire `Cassius.4.5` (decision 35): the joined paragraph is
`Cassius.4.4`, the paragraphs after it move up by one (the old 4.6 is now
4.5), and `Cassius.4.16`, which no longer exists, was removed from
`refs.lock` at the owner's direction. No link pointed into Cassius IV.

After launch, rule 6 applies without exception and such a correction uses
retired refs (`docs/references.md`). The mechanism stays in place for that.

## 37. Split paragraphs and page numbers, checked against the page images

At the project owner's request (before launch), the paragraph splits in
errata 16–21 were checked against the page images, and the importer's
layout rules fixed where they went wrong (`docs/ocr.md`, step 1):

- **Printer's signature marks** ("37" … "40" at the foot of McMaster and
  Stone's pages) are page furniture, not words of the text.
- **Paragraphs joined:** Centinel VIII (split at a signature mark), Federal
  Farmer III and IV (OCR dropped a leading "——"), Centinel VI's epigraph
  and its author, two of Sydney's numeral headings, and the Landholder's
  note in No. X (split at a colon). Each work's later passages were
  renumbered (Centinel VI and VIII, Federal Farmer III and IV, Sydney II,
  Landholder X's notes), the refs that no longer exist were removed from
  `refs.lock`, and the 59 suggested links on renumbered passages were
  re-proposed from their decisions files with the new refs (no link was
  lost; two identical links from the joined Federal Farmer paragraph became
  one).
- **Not errors:** Landholder IV and A Steady and Open Republican end
  mid-sentence in print, the sentence running on into the signature.
- **Page numbers** recorded on passages are now checked against the pages
  around them, so a misread number ("1" for 16) or a missing one is taken
  from its neighbours. 442 passages gained or corrected page numbers; no
  text changed.

## 38. Reviewing links through GitHub issues

Links need a person's review (CLAUDE.md rule 4), and reviewing hundreds one
at a time on the command line is slow. The site gets a review page
(`/review/`) that lists every suggested link by linker run, with both
passages, and sends the reviewer's decisions as a pre-filled GitHub issue.
A workflow records them.

- **Who counts.** Only an issue opened by someone with write access to the
  repository is applied (checked by the issue's author association and
  again through the API); anyone else's changes nothing and is closed with
  a note. The reviewer recorded is the issue author's GitHub login, so a
  review always names a real, accountable person.
- **No secrets, no server.** The site stays static; the workflow uses only
  its own `GITHUB_TOKEN`. Because a push made with that token does not start
  other workflows, it starts Deploy explicitly.
- **Untrusted input.** The issue body is read only for lines of the form
  `approve lnk_…` / `reject lnk_… — note`; it is passed to the tool through
  a file, never into a shell command; notes are stripped of control
  characters and limited to 500 characters; ids not still suggested are
  reported and skipped. Verify runs before anything is committed.
- **Page.** Decisions stay in the browser (localStorage) until sent; at most
  150 go in one issue (GitHub limits the length of a new-issue link). The
  page builds every element from data as text, never as HTML. It is the
  one page that needs JavaScript; the command line remains for anyone
  without it.
- Links may carry a `review_note`.


## 39. The Constitution Annotated as the source for case links

- **Source.** Case-to-clause links will be imported from the 2022 print
  edition of the Constitution Annotated (govinfo `GPO-CONAN-2022`), as
  PLAN.md proposes: an official, public-domain, expert-written source, so
  no agent judges what a case interprets. Overrulings come only from its
  Table of Supreme Court Decisions Overruled by Subsequent Decisions, which
  counts a decision as overruled only when a majority of the Court said so
  (rule 7). congress.gov blocks scripts, so the govinfo PDFs are used.
- **Reading PDFs.** `tools/pdf.py` extracts positioned text with the
  standard library (cross-reference and object streams, Flate, font
  encodings and ToUnicode maps, text matrices). Checked against
  `pdftotext` on Article I (about 340,000 words), 99.8% of words agree; the
  rest are small capitals in footnotes, which the case import does not use.
- **How a case meets a clause.** The Table of Cases gives the pages citing
  each case; each page's essays (from their running heads and headings)
  give the clauses. A case "is cited in the essays on" a clause when a page
  of those essays cites it; the count of such pages measures how much the
  essays discuss it. This is a fact about the Constitution Annotated, and
  links will say so in their source, never what the case held.
- **Open: the first set of cases.** Any rule built on these counts is
  neutral but has edges. For example, cases cited on 10 or more pages give
  97 cases, including *Brown v. Board of Education* (11) but not *Roe v.
  Wade* (9) or *Gideon v. Wainwright* (8). The project owner chooses the rule.

## 40. Contents down to the clause

The contents listed only divisions, so the Declaration (whose paragraphs
are not in any division) showed only "Signatures", and a clause could not
be reached from them. They now reach every passage, in reading order
(`tools/site_data.py`, `_toc`):

- Passages outside any division (the Preamble, the Declaration's
  paragraphs, a single essay's paragraphs) are entries of their own, with
  their number and opening words.
- A division with several passages of its own (an article's section, a
  state's signers) lists them as a row of small numbered links (the state's
  name for signers), whose opening words are the link's title and
  accessible name.
- On a Federalist paper or debate essay, the paper being read lists its
  paragraphs the same way.
- The highlight follows both the division and the passage being read.

## 41. The first set of cases: the most-cited case in each essay topic

The project owner chose the rule (decision 39 left it open). The
Constitution Annotated divides the essays on each clause into topics (the
id up to the first number under the clause: `Amdt1.7` freedom of speech,
`Amdt14.S1.8` equal protection, `ArtI.S8.C3.6` the commerce power's
modern doctrine). For each topic, the first set takes the Supreme Court
case cited on the most pages of that topic's essays (every case, if tied),
when that is at least four pages: 89 cases from 2022's edition
(`python -m importers.conan --landmarks`). The rule spreads the set across
the Constitution (religion, speech, search and seizure, the commerce power,
jurisdiction, …) and needs no one's judgment of importance. Its edges are
known: cases the essays discuss across many topics without leading any
(for example *Brown v. Board of Education*, *McCulloch v. Maryland*,
*Marbury v. Madison*) are not in it. More cases can be added later by a
further rule, never by hand.

## 42. The first set of cases, widened

The topic rule of decision 41 left out cases the essays discuss across many
topics without leading any one (*Brown*, *McCulloch*, *Marbury*). At the
project owner's request the first set is now the union of three rules
(`importers/conan.py`, `landmark_cases`), each applied to the 2022 edition
as printed:

1. the most-cited case in each essay topic (decision 41);
2. every Supreme Court case cited on 10 or more pages;
3. every decision that a case chosen by rule 1 or 2 overruled, according to
   the Table of Supreme Court Decisions Overruled by Subsequent Decisions
   (one step only, so the result does not depend on order).

That gives 189 cases, each listed with the rules that chose it. A decision
cited under two forms of citation (*McCulloch*: "17 U.S. (4 Wheat.) 316"
and "17 U.S. 316") counts once, by volume and page. The overruled table
and the Table of Cases print *Dobbs*'s docket number differently ("No.
19-1391", "No. 19-1392"), so an overruling case is also matched by name.

What the rules still leave out is the source's own view: the table
credits *Plessy v. Ferguson*'s overruling to *Bob Jones University v.
United States* (1983), not *Brown*, because it lists only explicit
statements by a majority of the Court; *Bob Jones* is not in the set, so
neither is *Plessy*. *Lochner v. New York* is cited on two pages and is
not in the table, so it is out too. *Korematsu* is in, as a decision the
table lists as overruled by *Trump v. Hawaii*.


## 43. The first set of cases: titles and discussed overrulings

At the project owner's request, two more rules, so that cases the
Constitution Annotated plainly treats as landmarks are in even when they
lead no topic (*Lochner v. New York*, *Plessy v. Ferguson*):

4. every Supreme Court case named in the title of an essay ("Liberty of
   Contract and *Lochner v. New York*", "*Marbury v. Madison* and Judicial
   Review"), matched exactly against the Table of Cases. A title naming
   *Brown v. Board of Education* names both decisions of that name, so
   *Brown II* (1955) is in too;
5. every decision the table of overruled decisions lists that is cited on
   five or more pages: overruled decisions the essays still discuss
   (*Plessy*, *Palko v. Connecticut*, *Breedlove v. Suttles*, …).

The set is now 213 cases, each listed with every rule that chose it.

## 44. Hosting: respublicalibrary.org on Cloudflare

The project owner bought `respublicalibrary.org` (on Cloudflare) rather than
using a CommonHall subdomain: the library has its own name, and a domain it
controls protects its permanent links from anything that happens to the
other site. It is served by Cloudflare instead of GitHub Pages
(supersedes decisions 15 and 22 on hosting; their budgets stand):

- **How.** A Cloudflare Worker named `respublica` with static assets and no
  code (`wrangler.jsonc`), connected to this repository: on every push to
  `main` Cloudflare runs `make build` and `npx wrangler@4.147.0 deploy`
  (both set in the Worker's build settings). The Node version is pinned in
  `.node-version` (the same as `site/.nvmrc`), Python by `.python-version`.
  No secret is stored in the repository. The review workflow no longer
  starts a deploy; its push to `main` is enough.
- **Why.** Real response headers (`site/public/_headers`): framing is
  refused (`frame-ancestors 'none'`, which a meta tag cannot set), HTTPS is
  enforced (HSTS), and content types are not sniffed. Each page keeps its
  own script-hash Content-Security-Policy in a meta tag. Hashed build files
  are cached for a year. Redirects are available when needed. No bandwidth
  caps.
- **Address.** `site/site.config.json`: `https://respublicalibrary.org`, no
  base path. The GitHub Pages deploy workflow is removed; the old
  github.io address should be unpublished in the repository's settings.
- **Not a database.** Links and texts stay as files in the repository,
  where every change is reviewed and verified; the site stays static
  (decision recorded at the owner's question about D1).

## 45. The Dissent of the Pennsylvania Minority; shared misreadings

The project owner asked for sources that frame the Bill of Rights. The
Address and Reasons of Dissent of the Minority of the Convention of
Pennsylvania (December 18, 1787), with its fourteen proposed amendments, is
printed in McMaster and Stone, the book Centinel comes from, so it is read
from the same scans by OCR consensus (`importers/ratification_series.py`).
Its title runs into the editors' note above it in the OCR
(`heading_ends_block`), it ends at its twenty-one signatures (`end_at`,
`signers`), and the yeas and nays printed after them are left out: a table
in columns, which OCR reads out of order.

Adding it changed words in other essays: the vote's vocabulary counts any
word two scans read identically, and the Dissent's two scans share
misreadings ("eflfect" for "effect", the ff ligature), which then tied with
the right word elsewhere (Brutus I). Two rules fix the cause (docs/ocr.md,
step 3): an attested word that one common OCR confusion turns into a clean
word is not counted as known, and on a tie a word from the clean texts beats
one only the scans attest. Re-importing every text with them changed only:
four misreadings corrected ("tho." "the", "wliole" "whole" twice, "liad"
"had"), Caesar II's signature read as "Caesar.", and ten words in
Centinel, the Landholder and Brutus no longer marked uncertain, each where
the other scan's reading was plainly garbled ("oi", "aud", "tight"). Every
change was checked word by word.
