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
