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

## 46. The House debates the amendments, 1789; our own OCR as a reading

The project owner asked for the debates in Congress on the amendments,
starting with the First Congress. The record is the Annals of Congress,
volume 1 (Gales and Seaton, 1834), read from the Internet Archive's scans
(`importers/annals.py`).

- **What is imported** is fixed by the print, not chosen: every item of the
  House's proceedings headed "Amendments to the Constitution", from that
  heading to the next heading, the next day or "Adjourned." (twelve days,
  June 8 to September 24, 1789). Refs are `House1789.{Mon}{day}.{paragraph}`
  (`docs/references.md`).
- **Two columns.** Pages are split into their numbered columns; passages
  record columns (`columns`), not pages, and the site cites "col.".
- **A third reading from our own OCR.** Only two scans of this printing
  could be found (HathiTrust and the Library of Congress refuse scripted
  access), and with two, 2.2% of words stayed uncertain, ten times the
  ratification texts. The owner chose to read the primary scan's page images
  with Tesseract 5.3.4 (Ubuntu's package, pinned) as a third reading. It is
  run once and kept in `sources/ocr/` with a record of the tool versions,
  the command and the raw images it read; `make verify` checks the record
  and never runs Tesseract, so CI needs no OCR. A rerun gives byte-identical
  output (single-threaded). It is not a raw source (rule 2 covers
  downloaded originals): it is derived, reproducible, and only votes.
- **Same engine, one vote for vocabulary.** The microfilm scan's own OCR is
  Tesseract too, and the two share confusions ("Mapison" for "Madison").
  Their agreement alone never makes a word known to the vote; where they
  outvote the main scan with a different real word ("finally" for "final"),
  the word stays uncertain for a person.
- Result: about 53,000 words, 1.06% uncertain, each marked with every
  reading.
- **Raw files kept out of git** (the scans' DjVu XML, 53 MB each, and the
  page images, 142 MB) count toward the 1 GB budget for such files only; the
  40 MB per-file budget is for files in git.
- **On the site** the debate is its own collection, "Debates in Congress":
  an index of the days (`/house-amendments-1789/`) and a page per day.

Later debates (the Congressional Globe for the Fourteenth Amendment, and so
on) would follow the same rule: the items printed under the amendment's
heading in each house.

## 47. The Fourteenth Amendment debates, 1866; UNT as a source

The project owner asked for the debates on the Fourteenth Amendment, and
approved the University of North Texas Digital Library as a new source.

- **What is imported** is fixed by the print: in the Congressional Globe,
  39th Congress, 1st session, every item of either house's proceedings from
  May 8 to June 13, 1866, headed "Reconstruction" or "Reconstruction again"
  whose first paragraphs take up the joint resolution (H. R. No. 127)
  proposing the amendment (by its number, as "the constitutional
  amendment", or as the joint resolution reported by the committee); an item
  headed "Reconstruction again" goes on with the day's item before it. Each
  item runs from its heading to the next heading or the end of that house's
  day. The days (fourteen) and their pages are listed in
  `importers/globe.py` and checked against the print. Two works, one per
  house: `House1866`, `Senate1866` (`docs/references.md`).
- **Sources.** The Internet Archive has part 3 (to page 2880) in a clean
  Lincoln Financial Foundation Collection scan (first recorded, wrongly, as
  the University of Michigan's; the source id keeps that name) and on microfilm, and part 4 (the Senate's last
  days, and the House's final vote) only on a microfilm whose OCR is badly
  garbled at this size. UNT has both parts with its own OCR. Layout and words
  come from UNT: its per-page word boxes (IIIF annotations, which drop
  punctuation) and its OCR text page (with punctuation), matched word for
  word. They are checked against the Lincoln Financial Foundation copy's OCR text (May) and the
  microfilm (June). UNT's pages are kept in git, gzip-compressed as UNT sends
  them (`encoding: gzip` in the manifest; the text pages carry a session
  token, so they could not be fetched again byte for byte).
- **Headings by layout and case.** UNT reads the Globe's small-capital
  headings in either case, so a heading is a line set apart (centred, or with
  space above and below) and printed in one case; lines of a bill or of verse
  printed in the debate start with a capital and are not headings.
- **On the site** both works join "Debates in Congress" (`/congress/`), which
  groups the debates by amendment. A day longer than 90,000 bytes of text
  (three of the Senate's) is shown on several pages, split at paragraphs
  (`/senate-fourteenth-amendment-1866/jun8/2/`), so that each page stays
  inside the HTML budget of decision 15. Refs do not change; each ref's URL
  names the page it is on.

## 48. Correcting words read from scans: the errata page

The project owner asked for a page, like the link review page, on which to
read uncertain words off the scans and record what is printed.

- **What is reviewed.** Every word the scans could not settle (`uncertain`
  in its passage), shown with the twelve words on either side, each scan's
  reading and the page images (`/errata/`). The maintainer picks a reading
  or types what the page prints. A reading picked as it stands confirms it.
- **Images from the libraries that hold the scans.** The errata page alone
  loads page images from the Internet Archive and the UNT Digital Library
  (its Content Security Policy allows those hosts for images only, and
  `tools/check_site.py` allows that on no other page). It is a page for
  maintainers; readers' pages still load nothing from elsewhere.
- **Recorded as link reviews are.** The page opens a GitHub issue titled
  "Errata review", one correction per line. A workflow
  (`.github/workflows/errata.yml`) runs only for an issue opened by someone
  with write access: `python -m tools.errata apply` appends each correction
  to `corrections/{work}.jsonl` under their GitHub login and date, updates
  any link quote that contains the old word (quotes must stay exact), re-runs
  the importers and `make verify`, and commits to main. Agents never record
  a correction (rule 3).
- **Applied by the importers.** A correction names the passage, the word as
  imported and its place among the passage's uncertain words. The importers
  (`importers/corrections.py`) replace the word, drop its uncertain mark and
  log the change in the passage's `corrected` list (who, when, the scans'
  word), so `texts/` stays exactly what the importers produce. A correction
  that no longer matches its passage (the scans were read again) stops the
  import for a person to look at again.
- **On the site** a corrected word is underlined, and its title says who
  corrected it and what the scans read. A correction never changes refs.
- **`docs/errata.md` stays** for what the page cannot show: misreadings the
  scans share, paragraph breaks and attributions.

## 49. Importing the first set of cases

The project owner chose, when phase 7 resumed with a CourtListener token:

- **No opinion text.** A case page shows the case's details, the syllabus as
  printed, the provisions its Constitution Annotated essays cite it under,
  and overrulings, and links to CourtListener for the opinion (PLAN.md).
  `Case.{id}.{n}` stays reserved for opinion paragraphs.
- **The syllabus from the United States Reports.** CourtListener has the
  official syllabus only in the text of recent slip opinions; its texts of
  older cases (from the Caselaw Access Project) leave it out. So the syllabus
  comes from a new source, the Library of Congress's public-domain scans of
  the U.S. Reports, one PDF per case, read from their text layer
  (`importers/usreports.py`). From volume 91 (1875) only: the nominative
  reports before it carry the reporters' own headnotes, often as marginal
  notes. The text layer is OCR in older volumes; it is copied, not
  corrected (rule 3), and each paragraph links to its page image. Where the
  reader cannot be sure it has the whole syllabus in order (a paragraph that
  stops mid-sentence), the case gets no syllabus and says why: 25 of the 181
  scans from volume 91 on, at first. They can be read later with new refs.
- **The scans stay out of git.** The 202 PDFs total about 330 MB, more than
  the repository's raw budget (decision 15). They are recorded in the
  manifest like any source, listed in `.gitignore`, restored by `make fetch`
  and cached in CI (`actions/cache`, pinned); the budget check counts them
  separately (1 GB).
- **`interprets` from two pages.** A case `interprets` a provision when the
  Constitution Annotated's essays on it cite the case on at least two
  printed pages (338 links for the 213 cases; one page would give about
  twice as many, many of them passing mentions). `overrules` links come only from the table of
  overruled decisions, where both cases are in the library. Both are
  imported by code as suggestions for a person to review.
- **Few API requests.** CourtListener allows the token 125 requests a day.
  Cases are found through its citation lookup, many citations per request,
  and slip opinions by docket number: about a dozen requests for 213 cases.
  Each response is a raw source with its request body; the token is never
  stored, only the name of the variable that holds it (`auth_env`).
- **Dates from the United States Reports.** CourtListener's dates are
  often those of a later order or the first day of a term (*Korematsu*: the
  date a rehearing was denied, in 1945; *Mapp v. Ohio*: October 9, 1961, for
  a decision of June 19). A case's date is the one the United States Reports
  print, read from the scan when it reads cleanly and its year agrees with
  the Constitution Annotated's within one (172 of the 213; *Pollock*'s scan
  reads "1695", and no term heading survived to catch it); else
  CourtListener's when its year agrees with the Constitution Annotated's (or
  with the term the case was decided in); else only the year the
  Constitution Annotated prints (the *Prize Cases*). The case file says
  which (`date_source`).
- **Decisions filed under two docket numbers.** CourtListener files a
  slip opinion decided with a companion case under both numbers ("18–422;
  18–726"), which its clusters API does not match; one search request found
  both (*Rucho*, *Trump v. Mazars*), and the case is the opinion filed on
  the date the Constitution Annotated prints.
- **When a citation has several clusters.** CourtListener holds some
  decisions twice (imported from different sources) and files a few cases
  under another's citation (*Bank of Columbia v. Okely* under *Sturges v.
  Crowninshield*'s 17 U.S. 122). A fixed rule chooses, never a person's pick:
  the clusters whose first party and year match the Constitution
  Annotated's, then the one other opinions cite most. The case file records
  the clusters passed over.

## 50. Reading a connection in place

The project owner asked to read a linked passage without leaving the page,
with a button to go to it.

- **In the panel, not a hover card, and only when asked.** Each connection
  in the panel is its kind, review status, the linked passage's name and
  the linked words in their sentence. **Preview** widens that to about
  1,500 characters of the linked passage centred on the quoted words
  (beginning and ending at a sentence where one is near), opened at them,
  with the reason the link was proposed and **Read it all** or **Go to
  passage**. One preview is open at a time. A case shows its citation, date
  and the first paragraph of its syllabus (or why it has none) and **Open
  the case**. A preview shows the linked passage only, not its own
  connections; the graph shows those. Buttons, not hover, so it works by
  keyboard, by touch and on the phone's bottom sheet.
- **One small file per passage.** `tools/site_data.py` writes
  `/data/preview/{ref}.json` for each passage with connections (link id ->
  preview; 898 files, 65 KB at most), fetched the first time a preview is
  opened there. A file per page would have been almost 1 MB for the
  Constitution.

## 51. The overview map

The project owner asked for a high-level view of the whole library: the
founding documents with every link coming off their clauses.

- **An aggregated map, not a force graph of every passage.** At `/map/`
  the Declaration, the Constitution and the amendments form a spine,
  passage by passage in reading order, grouped by article and amendment.
  Above each passage a stacked bar counts the links that reach it from the
  debates, by side (the Federalist side, the Anti-Federalists, the debates
  in Congress, other); below it, a dot for each case whose Constitution
  Annotated essays cite it, oldest nearest the spine, a ring for an
  overruled case. A link to a whole article or amendment counts at its
  first passage. An arc diagram below joins the debate's works that answer,
  rebut, quote or cite each other.
- **Drawn with d3,** the modules the graph already uses (selection,
  transition, and zoom, which loads when the pointer first reaches the map
  so the page stays inside its JavaScript budget): the spine pans and
  zooms on wide screens, naming each passage when zoomed in. Filters by
  side, cases and reviewed links move the bars rather than redraw them.
  With a mouse, hovering a passage shows its counts and cases and clicking
  opens it; arrow keys move along the spine.
- **On phones** the spine runs down the page in rows tall enough to tap,
  and the arcs run down the page too, the works named on the left. A tap
  shows the passage (or arc) in a card at the foot of the screen, with a
  button to open it, so nothing opens by accident while scrolling.
- **Data from Python.** `tools/site_data.py` (`build_map`) writes one file,
  `/data/map.json` (about 190 KB), with the totals per passage that the
  page also shows as a table, for readers without JavaScript and for
  screen readers.
- **It says what it does not show.** Links mark where linkers have looked,
  not where the founders argued most, and most are still suggestions. The
  page says how much of each work has been linked and which works have no
  links yet, and how many links a person has reviewed.

## 52. Clause pages

The project owner asked for the clause pages planned for phase 7.

- **A page per clause of the Constitution and per section of an
  amendment** (153), at a URL that mirrors its ref:
  `/constitution/1/8/18/` for `Constitution.1.8.18`,
  `/amendments/14/1/`, `/constitution/preamble/`. Refs still resolve to the
  passage in the reader; the clause page is a second place to read it.
- **What reaches the clause, grouped by where it comes from:** the
  Federalist side, the Anti-Federalists, other writings, the debates in
  Congress, the Supreme Court, and the founding documents. Each link shows
  its kind, whether a person has reviewed it, the linked words in their
  sentence and the reason it was proposed; each case its citation and date
  of decision, oldest first, with the source of the link. Nothing
  characterizes a holding (rule 7). Links to the article, section or
  amendment as a whole follow, then the clauses either side.
- **Links to a whole article or amendment** (a case the Constitution
  Annotated cites under all of Amendment XIV) also show at that heading in
  the reader, as the owner decided; links to a whole section at the
  section's heading. In the heading they are a count, like a passage's;
  selecting it opens them in the passage panel, with previews (without
  JavaScript, a closed list under the heading). A heading that is itself
  a passage (the Preamble) has no links of its own.
- **Ways in:** a "Clause page" button in the passage panel, the map, and
  each case's list of provisions, which now opens clause pages.
- **Built in Python** like every page (`tools/site_data.py`,
  `_clause_pages`), rendered by `ClauseView.astro`. Clause pages are not in
  the search index, so a search does not find each clause twice.


## 53. The first set of cases: what overrules them

The project owner noticed that *Plessy v. Ferguson* showed no overruling.
The Constitution Annotated's Table of Supreme Court Decisions Overruled by
Subsequent Decisions (2022, p. 2441) lists *Plessy* as overruled by *Bob
Jones University v. United States* (1983), not by *Brown v. Board of
Education*, which the table does not list as overruling any decision; the
library records overrulings only from that table (rule 7), so *Plessy*'s
overruling is *Bob Jones*'s. *Bob Jones* was not in the set, so no link was
made. One more rule, as fixed as the others:

6. every decision the table lists as overruling a case chosen by rules 1
   to 5. One step: what overrules a case added by this rule is not added.

It adds 19 decisions (*Bob Jones*, *Atkins v. Virginia*, *Ring v.
Arizona*, *Agostini v. Felton*, *Harper v. Virginia Board of Elections*,
*Wesberry v. Sanders*, *Benton v. Maryland*, *Escobedo v. Illinois*,
*Janus*, …), each with the reason it was chosen. They were looked up on
CourtListener with two requests and their scans fetched from the Library
of Congress like the others. The set is now 232 cases.


## 54. Syllabi from the Supreme Court's own PDFs, and syllabi with several opinions

The project owner approved supremecourt.gov as a source. The Library of
Congress has scanned the United States Reports to about volume 578, so nine
cases in the set (*Sessions v. Morales-Santana*, *Trump v. Hawaii*, *Janus*,
*Rucho*, *Seila Law*, *Trump v. Mazars*, *Americans for Prosperity
Foundation v. Bonta*, *Dobbs* and *Kennedy v. Bremerton*) had no syllabus.

- **The Court's PDFs.** Each is read from the PDF the Court publishes: the
  bound volume where the volume is bound (582, 585), else the preliminary
  print of the volume (588, 591) or of the case (594, 597)
  (`importers/scotus.py`, `PRINTS`). They are raw sources like any other
  (about 18 MB, kept in git), read by the same reader as the scans
  (`importers.usreports`, with a `source`), word for word; a case is found
  in a volume by the page number in its running heads. The PDFs are
  encrypted with an empty user password, which anyone may open;
  `tools/pdf.py` reads them (RC4). The Library of Congress scan, where there
  is one, comes first.
- **Opinions without a majority.** Where no opinion speaks for the Court
  throughout, the syllabus goes on after the judgment line with a part for
  each opinion ("JUSTICE WHITE delivered the opinion of the Court with
  respect to Parts I and II, concluding that …"). The reader had stopped at
  the judgment line, so eight published syllabi were cut short (455 U.S. 422,
  478 U.S. 109, 492 U.S. 302, 497 U.S. 639, 504 U.S. 555, 512 U.S. 622,
  561 U.S. 742, 567 U.S. 519), and *Adamson* (332 U.S. 46) was cut at
  "argued the" inside a holding. They now run to the list of who joined which
  opinion. Their published paragraphs are unchanged, with the same refs; the
  rest of the syllabus follows with new refs (rule 6). Up to 24 pages are
  read per case (*McConnell*'s syllabus runs to p. 110); dates are read from
  a case's first two pages only.
- **The reader's other changes** let it follow 20 of the 25 scans it
  had refused (hanging indents, lines read out of order, volumes before 1882
  that print no dates). 202 of the 232 cases now have a syllabus; five scans
  are still refused, and each case says why.

## 55. Brutus V–XVI, Patrick Henry, and the Anti-Federalist Library as a tie-breaker

The project owner decided, after the research on the Anti-Federalist
Library (antifederalists.org) and the original printings:

- **Brutus V–XVI from the New-York Journal.** Chronicling America (the
  Library of Congress) is approved as a source. Each page's OCR is read from
  its ALTO XML on tile.loc.gov (words, boxes, confidence); the page URLs are
  taken from each issue's record at loc.gov, paced for its rate limit. There
  is one scan, so nothing votes: a word is settled when it is a known word
  read with confidence (0.5 or more) or when the Library reads it alike;
  otherwise it is uncertain (about 14% of words). The essays join the
  existing Brutus work, `Brutus.{n}.{paragraph}`; XII and XIV, printed in two
  instalments, are one essay each. **Brutus XI** has no scan and is left
  out, and the work's notes say so; its text is not taken from anywhere
  else. The long s that OCR reads as "f" is never turned into "s" by code.
- **Patrick Henry from Elliot's Debates**, vol. 3, standard pagination: the
  Internet Archive's 1907 Lippincott scan with the 1876, 1861 and 1836
  copies of the same pagination as readings; never the separate
  "Pennsylvania Avenue" setting (UNC). The speeches imported are the
  twenty-four the Library prints, each as Elliot prints it; where the
  Library's speech takes in another member's remarks (June 17, June 23),
  the import keeps them with Elliot's speaker names. Refs `Henry.{Mon}{day}`
  as for the debates in Congress (`docs/references.md`).
- **The Library is a tie-breaker, never a source of text.** It is CC0, but
  names no source and was probably copied from a modern edition (it has
  editorial brackets and misreadings of its own). Its Markdown is pinned to
  commit 6424aff9 of github.com/seven-obelisks/antifederalists and kept as
  raw sources. Where the scans' readings of a word disagree, it may choose
  among them; where no scan reads it so, the text stays and its reading is
  recorded on the uncertain word as a `suggestion`, shown on `/errata/` for
  a person to check against the page image (a field, not a new mechanism:
  a chosen suggestion is recorded like any correction). In the newspaper
  and Elliot, whose printing the Library follows, a word only weakly read
  (one scan, or not a known word) that the Library reads differently is
  also left for a person. The rules are in `docs/ocr.md`.
- **Applied to existing works** where the Library's pages match ours:
  Brutus I–IV, Agrippa I–XI, the Federal Farmer I–V, Centinel I and
  V–XVIII (Centinel XIII and XVI from the pages the Library mislabels XII
  and XV). Not Cato (duplicated and cut-short pages) or Centinel II–IV
  (excerpts). No ref or paragraph changed; 28 words changed, each to
  another scan's reading (listed in the commit that made the change), 5
  uncertain marks were dropped where the Library agreed with the main scan,
  and the editions' notes say the Library was used.
- **Skipped:** Old Whig, Maryland Farmer, Impartial Examiner, John DeWitt,
  Philadelphiensis and Melancton Smith, for which no scan of the first
  printing was found to check the Library against.

## 56. Accepting the Anti-Federalist Library's readings

After the import of decision 55, the project owner chose to accept every
reading the Anti-Federalist Library suggests for a word the scans could not
settle (3,041 words: 2,994 in Brutus, most in Brutus V–XVI, 22 in Patrick
Henry's speeches, 16 in Centinel, 5 in the Federal Farmer and 4 in
Agrippa), rather than wait for each to be read off the page image. This is
an exception to rule 3, made by the owner, and it is kept visible:

- **Recorded as the owner's decision.** `python -m tools.errata
  accept-library --owner jackhale98` wrote one line per word to
  `corrections/{work}.jsonl`, with `"source": "library"`. The importers
  apply them (`importers/corrections.py`) like other corrections.
- **Still marked.** The word in the text is the Library's, but it stays
  among the passage's uncertain words with `accepted` (who accepted it,
  when) and the scans' readings. The reader shows it with a dashed
  underline and says the reading is the Library's, not yet checked against
  the page. The errata page still lists it, with a choice that confirms
  it; a person's decision on the word, recorded through the errata
  workflow as usual, replaces the Library's reading.
- **What it changes.** The Library modernizes the long s, so Brutus V–XVI
  now reads "legislative" where the newspaper prints it with a long s
  (OCR read "legiflative"); where the OCR read the long s correctly as "f"
  and the Library gave no suggestion, the text keeps "f". The Library's own
  errors (decision 55) can now be in the text, marked like the rest. One
  link quote that contained an accepted word was updated with it.

## 57. The Thirteenth and Fifteenth Amendments in the Congressional Globe

The project owner asked for the debates on the Thirteenth and Fifteenth
Amendments, read as the Fourteenth's are (decision 47), and decided two
questions the rule left open: items in which a house took up the joint
resolution without a heading on its subject are included (the House's
evening session of May 31, 1864; the Senate's sitting of January 30, 1869),
and so are procedural items under the subject heading (a motion to fix a
day, to postpone, to reconsider, a notice of an amendment, a conference
report filed).

- **What is imported.** Every item of either house's proceedings on the
  days listed in `importers/globe.py` (`DAYS`) headed with the subject of
  the joint resolution — "Amendment(s) of/to the Constitution" and
  "Abolition of Slavery" for S. No. 16 (1864–65); "Suffrage", "Suffrage
  Constitutional Amendment" and "Rights of Citizens" for H. R. No. 402 and
  S. R. No. 8 (1869) — whose first paragraphs name it, any later item that
  day under the same heading, and the two places above (`OPENINGS`). A
  notice of intent, a state legislature's resolutions, a message or a
  different joint resolution under a like heading is not imported; days
  with only such items are not listed.
- **Five works**, one per house and session: `Senate1864` (11 days,
  February 17 – April 8, 1864), `House1864` (5 days, May 31 – June 28,
  1864), `House1865` (9 days, January 6–31, 1865), `House1869` (11 days)
  and `Senate1869` (18 days), January 11 – February 26, 1869. They join
  "Debates in Congress" in two new groups. Refs as for 1866
  (`docs/references.md`).
- **Sources.** UNT's OCR of its copies (`unt-globe-{year}-p{page}-…`, 872
  pages, about 58 MB in git; the raw total stays well inside its budget).
  The cross-check copies are the Lincoln Financial Foundation Collection's
  scans (OCR text) for 1864–65 and, for 1869, the only scan the Internet
  Archive has, a microfilm (OCR text, which reads column by column here).
  They are kept out of git like the 1866 ones.
- **Reading the page, refined** for these sessions (`Session.refined`; not
  for 1866, whose refs are published and whose text does not change): the
  masthead on the first page of each number (1864–65; UNT leaves these
  pages unlabelled, so each is placed between its neighbours and checked
  to carry the masthead) and the number's signature at the foot ("40th
  Cong. 3d Sess.—No. 8.") are left out; a subject heading OCR ends with a
  comma, a speck or nothing is still a heading, and so is a line of small
  capitals set in a little from both margins; a heading may run over two
  lines; specks one or two dots wide (a column rule read as "j") are
  dropped; a lower-case line set apart that continues a sentence, a
  speaker's words, an article of a joint resolution and the signatures
  under a letter or report are not headings; "House of Representatives,"
  closing a letter does not end the day. Headings inside a speech
  (Yeaman's, January 9, 1865) stay in the item as paragraphs
  (`SPEECH_HEADINGS`), and one subject heading OCR misread past
  recognizing ("sn:i'F!i.u;K.", January 25, 1869) is named from the page
  image (`MISREAD_HEADINGS`). Each item is checked against the other copy
  in runs of about 200 words, since a day's opening formula ("The SPEAKER.
  The next business in order is …") recurs day after day.
- **Quality.** About 4.6% of words are marked uncertain in the Senate's
  1864 debate (UNT's OCR of pp. 1318–1319 is badly garbled), 2.1% (House,
  1864), 2.4% (House, 1865), 2.6% (House, 1869) and 1.9% (Senate, 1869).
  Misread headings and a dropped line are in `docs/errata.md` (40–45).
  Speeches the Globe prints only in its Appendix are not imported.
- **On the site**, a day is split into sheets by its text as before, or,
  where its uncertain words (each marked with every reading) would push the
  page past the HTML budget, by text and readings together
  (`SHEET_WEIGHT_BYTES`; only the Senate's March 28, 1864, so far; no 1866
  sheet changes). The about page lists the Globe's page-by-page UNT sources
  as one line per session instead of two lines per page.

## 58. The Lincoln copy's part 4 as a reading of the 1866 debates

The project owner approved adding the Internet Archive item
`congressionalglo00unit` as a reading of the 1866 debates on the pages of
part 4, where the only other copy was a microfilm whose OCR is poor.

- **What the item is**, checked against the downloaded files: its metadata
  names it "The congressional globe", volume "39th Congress, 1st session,
  pt. 4", contributed by the Lincoln Financial Foundation Collection
  (scanned at Indiana in 2011, the same set as part 3,
  `congressionalglo7393unit`). Its OCR text opens with the title page of
  the first session of the Thirty-Ninth Congress (F. & J. Rives) and the
  session's index, then runs from page 2881 to page 3840 (the page numbers
  in its scan data cover 2881–3840 without a gap), with the datelines of
  the days imported (May 30 to June 13, 1866). The metadata's date (1833)
  is the series'. It records no rights or licence statement; the volume
  was published in 1866 and is in the public domain in the USA, recorded
  as the other Globe copies are. Source `ia-globe-1866-pt4-lincoln-txt`,
  kept out of git like them and restored by `make fetch`.
- **Read as the Lincoln copy.** It is the same copy as part 3, so its
  readings go on the same key, `lincoln` ("Lincoln Foundation scan" on the
  site, already labelled in both `SCANS`); the two volumes are read as one
  stream in page order. No new key or label was needed.
- **The microfilm is kept as a third reading** on part 4's pages. With
  both, 1,249 (House) and 1,704 (Senate) words are marked uncertain; with
  the Lincoln copy alone, 1,324 and 1,792; before, 1,404 and 3,271. Where
  UNT's OCR and the Lincoln copy disagree, the microfilm sided with the
  Lincoln copy about 1,500 times and with UNT's about 1,050, settling words neither
  could alone ("fact^" against "facts", "Held" against "field",
  "Bingbam," against "Bingham,"). The cost: where the Lincoln copy and the
  microfilm agree against UNT's OCR on two words it knows ("the" against
  "tho"), the vote leaves UNT's reading, marked (408 words, erratum 65),
  where with the Lincoln copy alone the tie would go to the clean word.
  Those words are marked, each with both copies' reading, so a third vote
  costs fewer wrong-looking words overall than it saves.
- **Tallies.** The copies' OCR text sets a vote's tally apart from the
  last name ("and Wright— 37."), and the vote then dropped the count from
  UNT's "Wright—37."; in 1866 the importer joins them first
  (`Session.tallies`). That also restored eight tallies on part 3's pages
  dropped before. Not applied to 1864–65 and 1869, whose texts would
  change.
- **What changed.** Refs and paragraphs did not change. About 1,300 runs
  of words changed, most a misreading put right; the vocabulary the
  copies attest grew, so a few words on part 3's pages changed too
  ("ballot box" to "ballot-box", "o clock" to "o'clock"). Words made worse
  are in erratum 64; thirteen link quotes were brought in step with the
  new text by `tools.errata.update_quotes`. No correction applied to these
  works.
- **Open for the owner**: whether the vote should take two copies'
  clean word over the main scan's attested one (erratum 65). It would
  change every work read by consensus, so it is not done here.

## 59. Two scans can overrule the main scan

Decision 58 left 408 words in the 1866 debates showing the main scan's
misreading ("tho", "bo", "arc", "lo") although both other copies read the
right word: the vote never replaced a word it knew with another known word,
and words two scans read alike count as known. The project owner decided
that two scans can overrule a main scan (`importers/ocr.py`, `vote`):

- **The rule.** Where two scans or more agree on another word and it is a
  word of the clean texts, their reading replaces the main scan's, settled.
  Not when their word is known only because scans read it so: scans share
  misreadings, and the first trial took "aflirmative", "wich", "andif" and
  "tr" over the main scan's right words that way.
- **Real word against real word stays visible.** Where the main scan's word
  is a clean-text word too ("minority" against "majority", "be" against
  "he"), the majority's word is taken but stays marked uncertain, for a
  person to check against the page image.
- **The other safeguards hold:** figures, capitals read where the main
  scan has lower case, and much shorter readings still keep the main scan's
  word, unsettled.
- **What changed.** Re-importing every work read by consensus changed about 310
  places in ten works, no refs or paragraphs: 207 now settled (nearly all
  "tho", "bo", "arc", "lo", "ot", "m" become "the", "be", "are", "to",
  "of", "in"; "white" becomes "while" and "oar" "our" in the House's 1789
  debate) and 107 marked. Uncertain words fell from 1,703 to 1,569 in the
  Senate's 1866 debate and from 1,246 to 1,195 in the House's. Six link
  quotes that contained a changed word were carried over to the new text
  by code ("tho United States" now "the United States"; Cassius X "daring
  the life" now "during the life").

## 60. The Eleventh and Twelfth Amendments in the Annals of Congress

The project owner asked for the congressional proceedings on the Eleventh
Amendment (1794) and the Twelfth (1803, and the attempt of 1802), read as
the House's 1789 debate is (decision 46), from volumes 4, 11 and 13 of the
Annals of Congress.

- **What is imported.** In each house, every item printed under the
  amendment's heading ("Amendment(s) to the Constitution"), and, as for the
  Globe (decision 57), the paragraphs in which a house took the resolution
  up without that heading: offered it, read it, referred or postponed it,
  voted, and asked the President to send it to the States. The Senate's
  proceedings of 1794 and 1802 are printed as a journal, without headings,
  so all of them are of this kind. Messages that only tell one house what
  the other did, a State legislature's resolutions laid before a house,
  and other amendments taken up beside these (the bank officers' amendment
  of 1794, Bradley's motion for districts of April 16, 1802, the committee's
  resolution on re-eligibility of December 1803) are not imported. The
  items are listed in `importers/annals.py` (`ENTRIES`): the day, the
  printed columns, and, for an item without a heading, the first words of
  its first paragraph and of the one after it. Six works, one per house and
  Congress: `Senate1794`, `House1794`, `Senate1802`, `House1802`,
  `Senate1803`, `House1803` (`docs/references.md`).
- **Scans.** Volume 4: the Internet Archive's microfilm scan (whose OCR is
  far the better: about 88% of its words are dictionary words against 63%
  for the Google scan of the New York Public Library's copy) gives layout
  and words; it is checked against that Google scan's OCR and against our
  Tesseract reading of its page images (22 pages, as in decision 46), since
  with the two alone 4–10% of words stayed uncertain (`python -m
  importers.annals ocr later`). Volume 11: the Google
  scan of the University of Michigan's copy, checked against the New York
  Public Library's and the microfilm. Volume 13: the Google scan of
  Harvard's copy, checked against Michigan's and the microfilm. The
  microfilm of volume 13 repeats and overlaps frames, so it is never the
  main scan there. No other usable scan was found (the Internet Archive's
  1970s microfilm of volumes 1–4, `annalsofcongress01unit`, has unreadable
  OCR).
- **One engine.** The two Google scans' OCR shares its misreadings ("ihe",
  "lo", "Slates") as the Tesseract readings do; their agreement alone never
  makes a word known to the vote (`Volume.same_engine`).
- **Only the pages needed are kept**, each run of them a byte range of the
  scan's DjVu XML (`python -m importers.annals fetch`; `tools/fetch.py`
  records the `range` and `make fetch` asks for the same bytes and checks
  their sha256), and the page images one file a page. The whole files
  (about 55–65 MB each, eight of them) would have taken the raw files kept
  out of git past their 1 GB budget; the ranges, 61 MB of XML and 13 MB of
  images, are kept in git (the 300 MB budget). The other scans' pages are
  found by locating the main scan's paragraphs in them, not by their column
  numbers, which their OCR misreads too often.
- **Reading the page.** The running head is recognised by its letters
  ("HISXORT OF CONaRBSS", "H. OP R. Aiitendment to the CorutUtUion"),
  never a day's heading; Google's mark is left out; a heading OCR ran into
  a paragraph is set apart; column numbers are settled as runs over the
  whole scan (`settle_runs`), since OCR reads 5 as 6 in long stretches of
  volume 13; and a paragraph that runs onto the second column of a page
  records it (`blocks(by_number=True)`; not for 1789, whose published
  passages stay as they are).
- **Quality.** 2.0% of words are marked uncertain in 1794, 0.4–0.8% in
  1802, and 3.0–3.1% in 1803 (with decision 59's vote), where both Google scans are small and their
  OCR poor. Each is marked with every reading.

## 61. The Sixteenth to Nineteenth Amendments in the Congressional Record

The project owner approved govinfo.gov (the Government Publishing Office)
as a new source ("All, add govinfo") and asked for the floor proceedings on
the Sixteenth to Twenty-seventh Amendments from the bound Congressional
Record. A first look (October 2026) found the scans usable but too large for
the budget of raw files kept out of git, and the owner decided:

- **Storage.** The out-of-git raw budget is raised from 1 GiB (decision 49)
  to 4 GiB (`UNTRACKED_TOTAL_BUDGET` in `tools/verify`). govinfo serves the
  bound Record only as PDFs of whole days (about 300–450 KB a printed page;
  there is no page or text rendition), so the 16th–19th need about 600 MB
  and the 20th–26th about 1.7 GB more. The PDFs stay whole and out of git
  (`govinfo-crecb-*`), restored by `make fetch`, never byte ranges.
- **CI caches each family of such files under its own key**
  (`python -m tools.fetch cache-keys`, from that family's manifest entries:
  U.S. Reports, Annals, Globe, govinfo, the Record's microfilm OCR), so a
  new file of one family no longer saves every family's files again. The
  first run after this change fetches each family once.
- **The Twenty-seventh Amendment is left out.** It was proposed in 1789;
  that debate is `House1789`. In May 1992 each house only adopted a
  concurrent resolution declaring it ratified (S. Con. Res. 120, H. Con.
  Res. 320), which is not a debate on proposing an amendment.
- **Days and items** as for the Globe works (decision 57): on each day the
  volume's History of Bills and Resolutions lists for the joint resolution,
  every item under the resolution's heading, procedural ones too, and the
  places where the house took it up under another heading or inside an
  item on other business. Speeches printed in the Appendix by leave are
  left out, as with the Globe.
- **Works**, one per house per session, named by the year the session met
  in, a second session meeting in the same year taking `b`: `Senate1909`,
  `House1909`; `House1911`, `Senate1911`, `Senate1912`, `House1912`;
  `Senate1917`, `House1917b`, `Senate1917b`; `House1919`, `Senate1919`.

How it is done (`importers/record.py`):

- **Sources.** For each day, govinfo's PDF of the house's proceedings (a
  "granule"), whose OCR text layer gives words and layout
  (`tools/pdf.py`, `pdf_words`), and its part's MODS record, which gives the
  printed pages. The cross-check is the Internet Archive's OCR of a
  microfilm of the same bound part (`sim_congressional-record…`), taken as
  its page-indexed OCR text, its page index and the page numbers it read
  (3–4 MB a part, against 10–14 MB for its plain OCR text and 150 MB for its
  DjVu XML); its page images are the ones the errata page shows, since
  govinfo serves none. A passage's `scan` is govinfo's (`site: "govinfo"`,
  the granule and its pages) with the microfilm's leaves beside it; `make
  verify` checks there is one for each page.
- **The index decides the days, and checks the items.** The importer stops
  if a page the index gives for a day is in no item it imports, or if an
  item runs on more than a page past the last such page. Pages the index
  gives that hold no item on the resolution are listed with the reason
  (`ELSEWHERE`: the index's ranges for June 13, 1911, and July 30, 1917, run
  over other business), as is the one item that rightly runs on (`RUNS_TO`,
  May 16, 1911). Where the index's figures were read off its own OCR
  ("1!)25", "4Sll"), the day's pages in the MODS record settle them.
- **Reading the page** is described in `docs/editions.md`. Item headings
  and the headings of the sections of a speech are set alike; a heading
  ends an item only where an item opens after it, and a few speech headings
  that are followed by a speaker's name are listed (`SPEECH_HEADINGS`).
  Type size was tried and does not separate them (0.67 of the text's size
  for one item heading, 0.68 for one speech heading).
- **Shared code.** `globe.rejoin` (the Globe's rule for a lower-case line
  set apart) and `globe.paragraphs` are reused, not copied. Two fixes in
  shared code change no output: `ocr.NUMERAL_HEAD` takes runs of figures,
  stops and spaces whole (possessively), since a table of figures that does
  not match took exponential time (it matches exactly the same lines, which
  `tests/test_record.py` checks); and `tools/pdf.py` parses each distinct
  ToUnicode map once (govinfo's PDFs give every page its own copy of a map
  of 65,536 codes).
- **On the site** the works join "Debates in Congress" in four groups. A
  day's sheets are sized by an estimate of the HTML their passages make
  (`SHEET_HTML_BYTES`, `sheet_by_html` in `tools/site_data.py`, fitted to
  the built pages within 9 KB): many short passages and words marked with
  two readings made the first build's pages up to 626 KB against the 400
  KB budget. Other works keep their sheets and URLs.
- **Quality.** About 834,000 words, 44 per thousand marked uncertain (29 in
  the Senate's 1909 debate to 70 in the House's of December 1917, where the
  OCR is worst). With one reference every disagreement is a tie. Errata
  100–103 record words read across columns and misread headings.

The 20th–26th Amendments follow in the same way (`DAYS`), volume by volume.

## 62. The Twentieth to Twenty-sixth Amendments in the Congressional Record

The rest of the work approved in decision 61: each house's proceedings on
the joint resolutions proposing the Twentieth to Twenty-sixth Amendments,
from the bound Record (volumes 75, 76, 93, 106, 108, 111 and 117), with
the same sources (govinfo's PDFs, about 1.7 GB more out of git, and the
Internet Archive's microfilm OCR), the same rule for days and items, and
one work per house per session: `Senate1932`, `House1932`; `Senate1933`,
`House1933`; `House1947`, `Senate1947`; `Senate1960`, `House1960`;
`Senate1962`, `House1962`; `Senate1965`, `House1965`; `Senate1971`,
`House1971` (52 days, about 1,371,000 words).

- **The later volumes are read by rules of their own** (`Session.later`),
  so that the 1909–19 works, whose refs are locked, do not change. These
  volumes set headings in capitals without a full stop, over several lines;
  print quorum calls, amendments offered, conference reports and the
  sections of long speeches under headings inside a debate; and from 1947
  are set in three columns with narrow gutters. `docs/editions.md` lists
  the rules. The words the scans attest are counted apart for the two
  groups of volumes for the same reason.
- **The index gives where a day's debate begins, not its range** (from
  1947), so the check that no item runs more than a page past the index's
  last page would stop on every long day. Rather than drop the check, each
  such day lists the page its debate runs to (`RUNS_TO`), read off the
  page: the next item's heading or the recess. A heading OCR did not read
  still stops the importer unless the day's entry was checked.
- **Speeches printed in sections** are listed by their pages
  (`SPEECH_PAGES`) where their section headings would otherwise end the
  item (Sheppard on the League of Nations, February 14, 1933; Robertson,
  Fulbright and Douglas, 1962; the statements printed in the debate of
  March 10, 1971).
- **A resolution taken up under another subject.** S. J. Res. 29 (1962)
  was a bill on Alexander Hamilton's house and S. J. Res. 39 (1960) an
  amendment on filling vacancies in the House; their items are those under
  the headings the Record gives them. Where a house debated its own
  resolution and passed the other house's in its place (June 14, 1960;
  March 23, 1971), the whole item is imported. Speeches the Record prints
  under headings of their own outside the item (tributes after the vote,
  statements in morning business) are not.
- **Quality.** 18,700 words marked uncertain, 14 per thousand, far fewer
  than in 1909–19; about 7,500 are figures in tables. Errata 104–105 record
  heading lines read apart from their headings.
- **On the site** the works join "Debates in Congress" in seven groups. The
  about page lists govinfo's day PDFs as one line per volume and house, each
  day a link (`source_list`), to stay inside its HTML budget; a day split
  into sheets by HTML may now hold a footnote, shown on its own sheet.
- **Open: `/data/refs.json` is over its 5 MB budget** (7.5 MB with these
  works; the debates in Congress make up 7.3 MB of it). The check is not
  relaxed. Splitting the file, or leaving the debates' paragraph refs out of
  it, changes a lookup other sites use (decision 17's URL table, decision 18), so it waits
  for the project owner's decision; until then `make build` fails on it.
