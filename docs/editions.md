# Editions

Each work names one base edition. Text is imported by code from a raw file in
`sources/raw/` (recorded in `sources/manifest.json`) and is never edited by
hand. Suspected errors in a base edition go in `docs/errata.md`.

## What importers may change

Only these structural changes are allowed, and each importer documents which
it uses:

1. **Whitespace.** HTML whitespace and hard-wrapped lines are collapsed to
   single spaces. Line breaks that carry meaning (`<br>` in signature blocks)
   become `\n`; paragraph breaks inside one segment become a blank line.
2. **Markup.** HTML tags and plain-text markup (Project Gutenberg's
   `_underscores_` for italics) are removed from `text`. Italics are kept as
   `emphasis` character spans; National Archives hyperlinks to amendments are
   kept as `changed_by` records.
3. **Segmentation.** Splitting a text into refs (see `docs/references.md`) and
   moving headings, datelines, salutations and signatures into metadata.

Spelling, capitalization, punctuation and wording are never changed.

Quotes in links are matched against the text after normalizing only whitespace
and quote-mark style (curly vs straight). See `tools/common.py`,
`normalize_for_match`.

## Constitution

- **Base:** National Archives, "The Constitution of the United States: A
  Transcription" (source `nara-constitution`). It transcribes the parchment
  engrossed by Jacob Shallus; the Archives note that spelling and punctuation
  reflect the original ("chuse", "Pensylvania", "defence").
- The Archives hyperlink passages later changed by an amendment. The importer
  records each linked span and its amendment in the segment's `changed_by`.
  It does not mark what the change was; that is the amendment's text.
- Importer: `importers/nara.py`.

## Amendments

- **Base:** National Archives transcriptions of the Bill of Rights (source
  `nara-bill-of-rights`, section "The U.S. Bill of Rights": the first ten
  amendments "in their original form") and of Amendments XI–XXVII (source
  `nara-amendments-11-27`).
- The 1789 Joint Resolution proposing twelve articles is on the same page but
  is not imported yet.
- The Archives' editorial matter for each amendment (dates passed and
  ratified, "Note:" lines, and footnotes such as "*Superseded by section 3 of
  the 20th amendment.") is stored verbatim as `notes` on the amendment's
  division, not as amendment text.
- The Archives' brackets and asterisks inside Amendments XII and XIV mark
  superseded or changed text. They are kept as transcribed.
- Importer: `importers/nara.py`.

## The Federalist

- **Base:** Project Gutenberg eBook #18, *The Federalist Papers* (source
  `gutenberg-federalist-18`). Chosen in decision 8 of `docs/decisions.md` and
  confirmed by the project owner in decision 14.
- **What it gives:** all 85 papers, each with the edition's newspaper line
  (e.g. "From the New York Packet. Friday, November 23, 1787."), an
  attribution byline, footnotes, and italics.
- **Attribution.** The byline is stored verbatim (`attribution.byline`) and
  mapped to a structured attribution:

  | Edition byline | Papers | Stored as |
  |---|---|---|
  | HAMILTON | 51 papers | `single` |
  | MADISON | 15 papers | `single` |
  | JAY | 2–5, 64 | `single` |
  | HAMILTON AND MADISON | 18–20 | `joint` |
  | HAMILTON OR MADISON | 49–57, 62, 63 | `disputed`, with both names |

  The plan lists 49–58 and 62–63 as disputed. This edition marks No. 58 as
  MADISON. The site shows the edition's byline, and the difference is left
  for a human to decide (see `docs/errata.md`).
- **Two versions of No. 70.** The edition prints No. 70 twice, with the note
  "(There are two slightly different versions of No. 70 included here.)".
  The first version is the base text (`Federalist.70.*`, 23 paragraphs). The
  second (24 paragraphs) is stored unsegmented under `variants` on the
  paper's division.
- **Newspaper lines.** 35 papers have a newspaper line without a date (e.g.
  "For the Independent Journal."); the edition gives no date for them.
- **Lineage.** The Avalon Project's text of No. 10 matches this edition in
  wording and paragraphing, including the same typo ("wellconstructed"), so
  the two appear to descend from the same e-text. Neither is a page-image
  transcription of the newspapers or the 1788 McLean edition; differences
  from the newspaper printings are not yet documented.
- **Footnotes.** 66 footnotes, as `Federalist.{paper}.fn{n}`. Footnote markers
  such as `[1]` stay in the paragraph text where the edition prints them.
- Importer: `importers/federalist.py`.

## Anti-Federalist essays

Research (phase 5, October 2026). Nothing is imported yet; the choices below
are waiting on the project owner. Modern compilations (Storing, 1981; Borden,
1965) are not candidates because of copyright.

**Reachable from the build environment:** the Internet Archive (scans with
OCR text, marked not in copyright where noted). HathiTrust and the Library of
Congress block automated requests, so they cannot be pipeline sources.

**What the public-domain compilations contain** (checked against the OCR
text of each scan, not from memory):

| Source | Anti-Federalist contents | Internet Archive scans |
|---|---|---|
| Paul Leicester Ford, ed., *Essays on the Constitution of the United States* (Brooklyn, 1892) | Agrippa I–XVIII (attributed by Ford to James Winthrop); Cato I–VII (George Clinton); Sydney I–II (Robert Yates); letters of Luther Martin; A Plain Dealer (Spencer Roane); Elbridge Gerry's replies to "A Landholder"; William Williams's letter to "A Landholder"; Samuel Chase's letter of "Caution" | `essaysonconstitu00forduoft` (University of Toronto, marked not in copyright), `EssaysOnTheConstitutionOfTheUnitedStates`, `essaysonconstit00fordgoog` |
| Paul Leicester Ford, ed., *Pamphlets on the Constitution of the United States* (Brooklyn, 1888) | Letters of a Federal Farmer, the 1787 *Observations* (five letters; Ford attributes them to Richard Henry Lee); A Plebeian (Melancton Smith); George Mason's *Objections*; the "Columbian Patriot" *Observations* (Ford attributes it to Elbridge Gerry; the attribution should be checked before publishing) | `cu31924020874099` (Cornell), `pamphletsoncons00fordgoog` |
| John Bach McMaster and Frederick D. Stone, eds., *Pennsylvania and the Federal Constitution, 1787–1788* (1888) | Letters of Centinel I–XXIV (chapter VII, pp. 565–700); the editors say the author "cannot be known" | `cu31924030454387` (Cornell), `pennsylvaniafede00hist` |

Both Ford volumes also contain Federalist-side pieces (A Landholder,
A Countryman, Fabius, Noah Webster, Tench Coxe, James Wilson's speech, and
others), which could be imported alongside.

**Not found in any public-domain digitized source:**

- **Brutus** (sixteen essays in the *New-York Journal*, 1787–88). It is in
  neither Ford volume nor McMaster and Stone; no 1787–88 issues of the
  *New-York Journal* are on the Internet Archive; and the issues of the
  *American Museum* checked do not reprint it.
- **The Federal Farmer's *Additional Letters* (1788).** The only copies found
  are 1962 facsimile reprints, lending-only.

**OCR quality.** The scans' OCR is usable but imperfect: misread "ff"
ligatures ("eflFect"), broken words, and stray marks. Comparing the three
independent OCR texts of Ford's *Essays* on Cato I (924 words), each pair
disagrees in about 14 places. Where two of the three agree, the agreed
reading was correct in every case checked (including original spellings
such as "analize"); where all three differ, the word needs a human check
against the page image.
