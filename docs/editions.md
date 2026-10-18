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

## Declaration of Independence

- Source: National Archives, "Declaration of Independence: A Transcription"
  (`nara-declaration`), a transcription of the Stone Engraving of the
  parchment; NARA notes that its spelling and punctuation reflect the
  original ("Brittish", "compleat", "harrass").
- The title, set in bold at the head of the first paragraph, is moved with
  the date line into `Declaration.Heading`; nothing else is changed.
- Importer: `importers/nara.py` (`import_declaration`).

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
- The 1789 Joint Resolution proposing twelve articles, on the same page, is
  its own work (`texts/joint-resolution-1789.json`): the heading line, the
  preamble, the resolving clause, the twelve articles and the attestation,
  as transcribed (including "Article the first..." with its three periods).
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

## The ratification debate

Imported by `importers/ratification.py` (phase 5) from four public-domain
compilations, read from the Internet Archive's scans. Modern compilations
(Storing, 1981; Borden, 1965) are not candidates because of copyright.

| Book | Scans used | Imported |
|---|---|---|
| Paul Leicester Ford, ed., *Essays on the Constitution of the United States* (Brooklyn, 1892) | layout and words: `essaysonconstitu00forduoft` (DjVu XML); checked against the OCR text of `EssaysOnTheConstitutionOfTheUnitedStates` and `essaysonconstit00fordgoog` | every section: Cassius, Agrippa, Gerry's replies to A Landholder, A Landholder, William Williams's letter, A Countryman, A Citizen of New Haven, Cato, Caesar, Sydney, Cursory Remarks, Caution, A Friend to the Constitution, Luther Martin, A Plain Dealer, Hugh Williamson's Remarks, A Steady and Open Republican |
| Paul Leicester Ford, ed., *Pamphlets on the Constitution of the United States* (Brooklyn, 1888) | `cu31924020874099` (DjVu XML); checked against `pamphletsoncons00fordgoog` | Letters from the Federal Farmer (I–V) so far |
| John Bach McMaster and Frederick D. Stone, eds., *Pennsylvania and the Federal Constitution, 1787–1788* (Lancaster, 1888) | `cu31924030454387` (DjVu XML); checked against `pennsylvaniafede00hist` | Centinel I–XXIV (chapter VII); the Address and Reasons of Dissent of the Minority of the Convention of Pennsylvania (chapter VI, pp. 454–482: from the title to the twenty-one signatures; the editors' introduction before it and the yeas and nays of the final vote after it, printed in columns OCR reads out of order, are not imported) |
| *Debates and Proceedings in the Convention of the Commonwealth of Massachusetts, held in the year 1788* (Boston, 1856) | `debatesproceedin00mass` (DjVu XML); checked against `debatesproceedin00massrich`, `debatesandproce03convgoog` and `cu31924032635546` | Brutus I–IV ("Spirit of the Press", pp. 366–398) |

**Method.** The text is read from the scans by OCR consensus: one scan's
layout and words, checked word by word against the OCR of other copies of
the same edition, with a vote under strict rules, and words no rule settles
marked uncertain with every scan's reading. No word is typed. The full
method, its measured accuracy, its limits and the review process are in
[`docs/ocr.md`](ocr.md).

**Structure.** Each section runs from its title page to the page before the
next; essays start at their printed headings, and the printed numeral must
match the essay's id. Ford's own introductory notes before each series are
not imported; his footnotes are, as notes. Details in `docs/ocr.md`, step 4.

**Attribution** follows each section's title page in the edition ("Written
by George Clinton", "Accredited to James Winthrop"), or the place in the
edition named in the work's `attribution.source` (Centinel: Ford's
bibliography, *Essays*, p. 415). The 1856 *Debates* print Brutus without
an attribution; Ford's note to Webster's *The Weakness of Brutus Exposed*
(*Pamphlets*, p. 117: "Brutus was the signature (of Thomas Treadwell, of
Suffolk County, N. Y.?)") suggests Thomas Treadwell, with a query, and that
is what is recorded ("Thomas Treadwell?"). Several of these attributions are disputed
by later scholars (Cato, Caesar, the Federal Farmer among them); Res Publica
records what the edition says and makes no claim of its own.

**Side.** `position` (`anti`, `federalist`, `other`) is Res Publica's
grouping, not the editors'. William Williams's letter (he defended his
conduct but voted to ratify) is `other`.

**Not yet imported:**

- **Brutus V–XVI.** The 1856 *Debates* reprint only I–IV, from the Boston
  *Independent Chronicle*; that reprint's text (I–IV, with the 1856 editors'
  modern spelling) is what is imported, under the *New-York Journal* dates
  of first publication. The original Greenleaf printing of 13 essays is in
  the Library of Congress's Chronicling America (II, III and XI are not
  online), but there is only one scan of each page and its OCR is poor, so
  the consensus method cannot be used; every line would need correcting
  against the image. Adding it is a new upstream source and waits on the
  project owner.
- **The Federal Farmer's *Additional Letters* (1788).** The only copies found
  are 1962 facsimile reprints, lending-only.
- The rest of Ford's *Pamphlets* (the Columbian Patriot, Jay, Webster, Coxe,
  Wilson's speech, Fabius, Aristides, Randolph, Mason's Objections, Marcus,
  Civis, A Plebeian): planned. That scan has missing pages and bracketed
  original page numbers that need handling first.

## Debates in Congress

**The House's debate on amendments, 1789** (`texts/house-amendments-1789.json`,
`importers/annals.py`, decision 46) is imported from Joseph Gales, Sr.,
comp., *The Debates and Proceedings in the Congress of the United States*
(the Annals of Congress), volume 1 (Washington: Gales and Seaton, 1834), in
the printing whose running head reads "Gales & Seaton's History of Debates
in Congress". The Annals give the House's debates as reported (largely from
Thomas Lloyd's *Congressional Register*), often in the third person, not
word for word.

**What is imported** is fixed by the print: every item of the House's
proceedings in volume 1 headed "Amendments to the Constitution", from its
heading to the next item's heading, the next day's date, or "Adjourned."
That is twelve days, June 8 (Madison's speech proposing amendments) to
September 24, 1789, columns 440–948. Business of the same days under other
headings, and the Senate's proceedings, are not imported. The day's date is
its heading as printed, checked against the 1789 calendar (OCR misreads the
figures: "Satl RDAY, August 23" is Saturday the 22d).

**Scans.** The volume is printed in two numbered columns a page. Layout and
words come from the Google scan in the Internet Archive
(`debatesandproce00galegoog`, DjVu XML), split into its columns. Only one
other scan of this printing was found (`sim_united-states-congress-debates-and-proceedings_march-3-1789-march-3-1791_1`,
a microfilm, whose OCR reads each line across both columns; it is split at
the gutter word by word). With two scans, 2.2% of words stayed uncertain,
so the Google scan's page images were also read with Tesseract, as a third
reading (`sources/ocr/`, decision 46). The microfilm's OCR is Tesseract too,
so the two share its confusions ("Mapison" for "Madison" in small capitals):
their agreement alone never makes a word known to the vote. About 1.1% of
words stay uncertain, more than in the ratification debate's texts (0.05–
0.6%), mostly where all three readings differ or where only the two
Tesseract readings agree against the main scan; each is marked with every
reading. Running heads, column numbers and specks are left out; a line OCR
broke into pieces at the same height is joined again. The DjVu XML and page
images are kept out of git (`make fetch` downloads them).

## Supreme Court cases

**Which cases interpret which clause** come from the *Constitution of the
United States of America: Analysis and Interpretation* (the Constitution
Annotated), 2022 print edition, prepared by the Congressional Research
Service and published by the Government Publishing Office: govinfo package
`GPO-CONAN-2022`, granules 7–42 (the Preamble, each article and amendment,
and the Appendix), fetched as PDFs (`conan-2022-{n}`). It is a U.S.
Government work in the public domain. `importers/conan.py` reads it with
`tools/pdf.py`:

- the essays on each printed page, by their ids (`ArtI.S8.C3.2.1`), and so
  the clause each discusses (`Constitution.1.8.3`);
- the Table of Cases: each case cited and the pages that cite it (6,702
  entries, 6,270 of them Supreme Court decisions);
- the Table of Supreme Court Decisions Overruled by Subsequent Decisions
  (235 rows), the only source for `overrules` links.

**Which cases.** The first set is 213 cases chosen from the Constitution
Annotated by the rules of decisions 41 to 43 (`python -m importers.conan
--landmarks`).

**Identifiers and details** come from CourtListener (Free Law Project),
keyed by cluster ID as CommonHall does (`importers/courtlistener.py`). Each
case is looked up once by its U.S. Reports citation, through CourtListener's
citation lookup (several citations per request), or, for a decision the
Constitution Annotated cites as a slip opinion, by its docket number in the
Supreme Court. Every response is a raw source (`courtlistener-citations-{n}`,
`courtlistener-scotus-{docket}`), with the request body; the API token is
read from `COURTLISTENER_TOKEN` and never stored. A case with no cluster,
or one dated in another year than the Constitution Annotated prints, stops
the import. Where CourtListener gives several clusters for a citation (the
same decision imported twice from different sources, or another case filed
under it by mistake), the import keeps those whose first party is the
Constitution Annotated's and whose year is its year, then takes the one
other opinions cite most; the case file says so (`courtlistener_match`), and
a tie stops the import. The case's name is the Constitution Annotated's;
CourtListener's is kept as `courtlistener_name`. CourtListener's data is
offered free of known copyright restrictions.

**The syllabus** is copied as printed in the United States Reports, from the
Library of Congress's scan of each case (`loc-usrep-{volume}-{page}`, one PDF
per case, public domain; `importers/usreports.py`). It is the text layer of
the scan: optical character recognition for older volumes, so misreadings
("Amendfnent", "deteilnined" in *Brown*) are possible and are not corrected
(rule 3); recent volumes have born-digital text that drops the "fi" and "fl"
ligatures ("affrmed", and "fled" for "filed"). The reader takes the
paragraphs in smaller type after the line with the case's dates, up to the
counsel, the statement of the case or the opinion, and leaves out running
heads, footnotes ("*Together with No. 2 …") and printer's marks; words broken
at a line end are rejoined. Only these changes are made. A syllabus is read
from volume 91 (1875) on: the earlier, nominative reports carry the
reporters' own headnotes, often as marginal notes. Where a paragraph seems to
stop mid-sentence (the text layer is out of order, or the end was missed),
no syllabus is imported and the case says so (`syllabus_note`). The scans are
kept out of git (decision 47): `make fetch` downloads them.

**Opinions** are not imported; each case links to its opinion on
CourtListener (decision 47).
