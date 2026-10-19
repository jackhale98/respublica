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
compilations, read from the Internet Archive's scans, and (Brutus V–XVI) from
the original newspaper; Patrick Henry's speeches by `importers/elliot.py`
from Elliot's *Debates*. Modern compilations (Storing, 1981; Borden, 1965)
are not candidates because of copyright.

| Book | Scans used | Imported |
|---|---|---|
| Paul Leicester Ford, ed., *Essays on the Constitution of the United States* (Brooklyn, 1892) | layout and words: `essaysonconstitu00forduoft` (DjVu XML); checked against the OCR text of `EssaysOnTheConstitutionOfTheUnitedStates` and `essaysonconstit00fordgoog` | every section: Cassius, Agrippa, Gerry's replies to A Landholder, A Landholder, William Williams's letter, A Countryman, A Citizen of New Haven, Cato, Caesar, Sydney, Cursory Remarks, Caution, A Friend to the Constitution, Luther Martin, A Plain Dealer, Hugh Williamson's Remarks, A Steady and Open Republican |
| Paul Leicester Ford, ed., *Pamphlets on the Constitution of the United States* (Brooklyn, 1888) | `cu31924020874099` (DjVu XML); checked against `pamphletsoncons00fordgoog` | Letters from the Federal Farmer (I–V) so far |
| John Bach McMaster and Frederick D. Stone, eds., *Pennsylvania and the Federal Constitution, 1787–1788* (Lancaster, 1888) | `cu31924030454387` (DjVu XML); checked against `pennsylvaniafede00hist` | Centinel I–XXIV (chapter VII); the Address and Reasons of Dissent of the Minority of the Convention of Pennsylvania (chapter VI, pp. 454–482: from the title to the twenty-one signatures; the editors' introduction before it and the yeas and nays of the final vote after it, printed in columns OCR reads out of order, are not imported) |
| *Debates and Proceedings in the Convention of the Commonwealth of Massachusetts, held in the year 1788* (Boston, 1856) | `debatesproceedin00mass` (DjVu XML); checked against `debatesproceedin00massrich`, `debatesandproce03convgoog` and `cu31924032635546` | Brutus I–IV ("Spirit of the Press", pp. 366–398) |
| *The New-York Journal, and Weekly Register* (New York: Thomas Greenleaf), December 13, 1787 to April 10, 1788 | the Library of Congress's scans in Chronicling America (LCCN sn83030566): each page's ALTO XML (words, boxes, confidence), pages 2 and 3 of thirteen issues; one scan only | Brutus V–X and XII–XVI, as first printed (XII and XIV in two instalments each) |
| Jonathan Elliot, ed., *The Debates in the Several State Conventions on the Adoption of the Federal Constitution*, vol. 3 (2nd ed., standard pagination; Philadelphia: Lippincott, 1907 printing) | `debatesinseveral03elliuoft` (DjVu XML); checked against `cu31924024573820` (1876), `debatesinsevera08convgoog` (1861) and `debatesinsevera12elligoog` (1836), all of the same pagination | Patrick Henry's speeches in the Virginia convention, June 5–25, 1788 (the twenty-four the Anti-Federalist Library prints, pp. 43–652) |

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

**Brutus.** I–IV come from the 1856 *Debates*, which reprint only those
four from the Boston *Independent Chronicle* (with the 1856 editors' modern
spelling), under the *New-York Journal* dates of first publication. V–X and
XII–XVI come from the *New-York Journal* itself, in Chronicling America
(decision 55): the essay from the newspaper's line ("For the New-York Journal,
&c.") and heading ("BRUTUS, No. V.") to the signature, with the long s and
the newspaper's spelling as printed. There is one scan of each page and its
OCR is poor (about one word in seven differs from the Anti-Federalist
Library's text, the long s read as "f" or "l" most often), so the consensus
method cannot vote: a word is settled when the OCR reads it with confidence
(ALTO word confidence 0.5 or more) and it is a known word, or when the
Anti-Federalist Library reads it the same way; every other word is marked
uncertain, with the Library's reading as a suggestion where it differs.
About 140 words in a thousand are marked. **Brutus XI** (January 31, 1788)
is not imported: that issue is not in Chronicling America, and its text is
not taken from anywhere else. XII and XIV, printed in two instalments, are
one essay each: the first instalment's heading lines, both instalments'
paragraphs, numbered through, and the second's signature; the "(To be
continued.)" and "[Continued from last Thursday's paper.]" lines between
them are not kept. Each passage links to its page at the Library of
Congress.

**Patrick Henry** (`importers/elliot.py`). The speeches are those the
Anti-Federalist Library prints, each as Elliot prints it, from the paragraph
that opens it (the speaker's name in capitals) to the next speaker or the
next day's heading. Three take in other members' remarks as the Library's
do (George Nicholas on June 17 and June 23, John Marshall on June 23), with
the speakers named as Elliot names them; nothing is trimmed. The
reporter's notes in brackets stay in the text as printed. About 20 shorter
remarks of Henry's that the Library does not print are not imported. Two
printings both call themselves Elliot's second edition of 1836: the
standard (Lippincott) pagination, used here, and a separate setting
"printed on the Pennsylvania Avenue" (UNC's scans, `debatesofseveral03unse`),
whose pages differ and which is never mixed in. The 1861–1907 printings
head the day of Henry's June 19 speech "Wednesday, June 18" a second time
(erratum 60).

**The Anti-Federalist Library as a tie-breaker** (decision 55). The
Library (antifederalists.org; its Markdown at
github.com/seven-obelisks/antifederalists, pinned to one commit and kept as
raw sources) is CC0 but names no source and was probably copied from a
modern edition, with editorial brackets and its own misreadings. It never
supplies text. Where the scans' readings of a word disagree and the vote
cannot settle it, a reading with the Library's letters is chosen; where no
scan's reading agrees, the word stays uncertain and the Library's reading
is shown on `/errata/` as a suggestion to check against the page image
(`docs/ocr.md`, "The Anti-Federalist Library"). It is used for Brutus I–XVI,
Agrippa I–XI, the Federal Farmer I–V, Centinel I and V–XVIII and Henry's
speeches; not for Cato (its pages are duplicated or cut short) or Centinel
II–IV (excerpts).

**Not yet imported:**

- **Old Whig, Maryland Farmer, Impartial Examiner, John DeWitt,
  Philadelphiensis, Melancton Smith.** The Anti-Federalist Library has them,
  but no scan of their first printings was found to check it against (the
  New-York Journal reprinted only some of Philadelphiensis; the Library's
  Melancton Smith follows Childs's 1788 report, not Elliot), and the Library
  is not a source of text.
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

**The Eleventh and Twelfth Amendments, 1794 and 1802–03**
(`texts/senate-eleventh-amendment-1794.json`,
`texts/house-eleventh-amendment-1794.json`,
`texts/senate-twelfth-amendment-1802.json`,
`texts/house-twelfth-amendment-1802.json`,
`texts/senate-twelfth-amendment-1803.json`,
`texts/house-twelfth-amendment-1803.json`, `importers/annals.py`, decision
60) are imported from the same series: volume 4 (Third Congress; Gales and
Seaton, 1849), volume 11 (Seventh Congress; 1851) and volume 13 (Eighth
Congress, first session; 1852, as the microfilm's title page reads). In
each house: every item headed "Amendment(s) to the Constitution", and the
paragraphs, printed without that heading, in which the house offered,
read, referred, postponed or voted on the resolution, or asked the
President to send the amendment to the States. The Senate's proceedings of
1794 and 1802 are printed as a journal, without headings. The items are
listed in the importer (`ENTRIES`). In 1794: the Senate, January 2, 13, 14
and March 12; the House, January 15, 16, March 4 (headed) and March 12. In
1802: the Senate, April 12–15 and May 3 (two items); the House, February 19
and May 1 (headed). In 1803: the Senate, 17 days from October 21 (Mr.
Clinton's motion) to December 16, with the long debate of November 23 to
December 2; the House, 14 days from October 17 (Mr. Dawson's resolution) to
December 12. Not imported: messages that only report the other house's
action, a State legislature's resolutions laid before a house, and the
other amendments taken up on the same days (the bank officers' amendment,
1794; districts for Electors, 1802; re-eligibility to the presidency, 1803).

**Scans.** Volume 4: the Internet Archive's microfilm scan
(`sim_united-states-congress-debates-and-proceedings_december-2-1793-march-3-1795_2`)
gives layout and words; it is read against the Google scan of the New York
Public Library's copy (`debatesandproce18galegoog`, whose own OCR is poor)
and our Tesseract reading of that scan's page images. Volume 11: the Google
scan of the University of Michigan's copy (`debatesandproce09galegoog`),
read against the New York Public Library's (`debatesandproce24galegoog`)
and the microfilm. Volume 13: the Google scan of Harvard's copy
(`debatesandproce01unkngoog`), read against Michigan's
(`debatesandproce34galegoog`) and the microfilm (whose frames repeat and
overlap). Only the pages needed are kept, as byte ranges of each scan's
DjVu XML (`ia-part-annals-v{volume}-{scan}-{first}-{last}`, in git), and
the page images read with Tesseract one file a page
(`ia-page-annals-v4-nypl-{leaf}`); `python -m importers.annals fetch`
finds them. The two Google scans' OCR shares its misreadings, so their
agreement alone never makes a word known. About 2% of words are marked
uncertain in 1794, under 1% in 1802, and about 3% in 1803.

**The Fourteenth Amendment debates, 1866**
(`texts/house-fourteenth-amendment-1866.json`,
`texts/senate-fourteenth-amendment-1866.json`, `importers/globe.py`,
decision 47) are imported from *The Congressional Globe: Containing the
Debates and Proceedings of the First Session of the Thirty-Ninth Congress*
(Washington: F. & J. Rives, 1866), parts 3 and 4: in each house, every item
headed "Reconstruction" (or "Reconstruction again") in which it took up the
joint resolution (H. R. No. 127) proposing the amendment, from the House's
debate of May 8 to its vote on the Senate's amendments on June 13. The Globe
gives the debates as reported; some speeches it prints only in its Appendix
("His remarks will be found in the Appendix"), which is not imported.

The Globe prints three columns to a page in small type. Words and layout
come from the University of North Texas Digital Library's OCR of its copy
(`unt-globe-1866-p{page}-words` and `-text`, one pair per page), matched
word for word and split into columns. They are checked against the
Internet Archive's scans of two other copies: the Lincoln Financial Foundation Collection's
(parts 3 and 4, OCR text: `congressionalglo7393unit` to page 2880 and
`congressionalglo00unit` from page 2881, read as one copy) and, for part 4
only, a microfilm (DjVu XML, read column by column). Each word is in at
least one reading; words they could not settle are marked as uncertain. The
microfilm's OCR is poor; on the pages of part 4 it is a third reading
beside the Lincoln copy's (decision 58), so the Senate's June days and the
House's vote of June 13 are corroborated about as well as May's. In the
copies' text a vote's tally set apart from the last name ("and Wright—
37.") is joined to it, as UNT's OCR reads it.

**The Thirteenth Amendment debates, 1864–65**
(`texts/senate-thirteenth-amendment-1864.json`,
`texts/house-thirteenth-amendment-1864.json`,
`texts/house-thirteenth-amendment-1865.json`, `importers/globe.py`,
decision 57) are imported from *The Congressional Globe: Containing the
Debates and Proceedings of the First Session of the Thirty-Eighth Congress*
(Washington: John C. Rives, 1864), parts 1, 2, 3 and 4, and *… of the
Second Session of the Thirty-Eighth Congress* (Washington: F. & J. Rives,
1865), part 1: in each house, every item headed with the subject of the
joint resolution (S. No. 16) proposing the amendment ("Amendment of the
Constitution", "Amendments to the Constitution", "Abolition of Slavery")
in which it took the joint resolution up, procedural items included (a
motion to fix a day, to postpone, to reconsider). The Senate's days run
from February 17 to its vote of April 8, 1864; the House's from May 31 to
June 28, 1864 (its vote of June 15 fell short of two thirds), and, on
James Ashley's motion to reconsider that vote, from January 6 to the vote of
January 31, 1865. The House's evening session of May 31, 1864, printed
under the heading "Evening Session", is included: the House sat that
evening to debate the joint resolution.

**The Fifteenth Amendment debates, 1869**
(`texts/house-fifteenth-amendment-1869.json`,
`texts/senate-fifteenth-amendment-1869.json`, decision 57) are imported
from *… of the Third Session of the Fortieth Congress* (Washington: F. & J.
Rives & Geo. A. Bailey, 1869), parts 1, 2 and 3: every item headed
"Suffrage", "Suffrage Constitutional Amendment" or "Rights of Citizens" in
which a house took up the joint resolutions proposing the amendment (H. R.
No. 402 and S. R. No. 8), from January 11 to the conference reports of
February 25 and 26, 1869, procedural items included. On January 30 the
Senate took up S. R. No. 8 inside an item on other business (the use of
the Capitol for the inaugural ball), without a heading of its own; that
sitting is included from the paragraph that takes it up.

Both are read as the 1866 debates are, from UNT's OCR (`unt-globe-1864-…`,
`unt-globe-1865-…`, `unt-globe-1869-…`). In 1864–65 the first page of each
number of the Globe (one page in sixteen) carries the number's masthead in
place of the running head, and UNT's catalogue leaves those pages
unlabelled; they are found between their neighbours and their masthead is
left out of the text, as is the number's signature at the foot of its first
page in 1869 ("40th Cong. 3d Sess.—No. 8."). A few speeches are printed in
sections with headings of their own (Yeaman's of January 9, 1865); those
headings stay in the item as paragraphs. The cross-check copies are the
Lincoln Financial Foundation Collection's scans of the 1864 and 1865
volumes (OCR text) and, for 1869, the only scan the Internet Archive has, a
microfilm (OCR text). Speeches the Globe prints only in its Appendix (Davis
and Howe in the Senate, 1864; Rollins of Missouri and Harding in the House)
are not imported.

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
Supreme Court. A decision filed under two docket numbers (decided with a
companion case: *Rucho v. Common Cause*, *Trump v. Mazars*) is found by a
search for its docket number, as the opinion filed on the date the
Constitution Annotated prints. Every response is a raw source
(`courtlistener-citations-{n}`, `courtlistener-scotus-{docket}`,
`courtlistener-search-dockets-{n}`), with the request body; the API token
is read from `COURTLISTENER_TOKEN` and never stored. A case with no
cluster, or one dated more than a year from the year the Constitution
Annotated prints, stops the import. Where CourtListener gives several clusters for a citation (the
same decision imported twice from different sources, or another case filed
under it by mistake), the import keeps those whose first party is the
Constitution Annotated's and whose year is its year, then takes the one
other opinions cite most; the case file says so (`courtlistener_match`), and
a tie stops the import. The case's name is the Constitution Annotated's;
CourtListener's is kept as `courtlistener_name`. CourtListener's data is
offered free of known copyright restrictions.

**The date of decision** is the one printed in the United States Reports
("Decided December 18, 1944."), read from the scan's text layer, when its
month reads as a month and its year is the year of the term the volume
prints or the next, and within a year of the year the Constitution
Annotated prints (OCR reads "1295" and "1695" for "1895"). CourtListener's date is
often that of a later order (a rehearing denied) or the first day of the
term, so it is used only where the scan gives no date that can be read (the
nominative reports print none), and only when its year is the one the
Constitution Annotated prints, or when that is the term's year and
CourtListener's date falls in the next (*Ex parte Garland*, December Term
1866, decided in January 1867). Otherwise the case gives only the year the
Constitution Annotated prints (the *Prize Cases*, 1863). Each case records
where its date comes from (`date_source`) and CourtListener's date when it
differs (`courtlistener_date`).

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
no syllabus is imported and the case says so (`syllabus_note`). Where no
opinion has a majority, the syllabus goes on past the judgment line through
each opinion's part ("JUSTICE X delivered the opinion of the Court …,
concluding that"), up to the list of who joined which opinion. The scans are
kept out of git (decision 49): `make fetch` downloads them.

For cases the Library of Congress has not scanned (volumes 582 on), the
syllabus is read the same way from the Supreme Court's own PDF
(`scotus-*`, `importers/scotus.py`, decision 54): the bound volume where the
volume is bound, else the preliminary print. Its text is born-digital and
drops the "fi" and "fl" ligatures as recent scans do. The case file names
the PDF (`pdf_url`) and its edition note says which print it is.

**Opinions** are not imported; each case links to its opinion on
CourtListener (decision 49).
