# Reading texts from scans: OCR by consensus

Some texts have no accurate digital edition in the public domain. The essays
and letters of the ratification debate are the first: they exist only in
nineteenth-century printed collections, scanned by libraries. This document
explains how Res Publica turns those scans into text without typing a word,
what the output records, what can still go wrong, and how a person reviews
and corrects it. Decision 27 in `docs/decisions.md` records why; the editions
used are in `docs/editions.md`.

Code: `importers/ocr.py` (the general method) and
`importers/ratification.py` with `importers/ratification_series.py` (the
books and series); `importers/elliot.py` (Patrick Henry, Elliot's
*Debates*); `importers/nyjournal.py` (Brutus V–XVI, one newspaper scan);
`importers/library.py` (the Anti-Federalist Library as a tie-breaker);
`importers/independence.py` with `importers/parallel.py` (the road to
independence: the Journals of the Continental Congress and Ford's
*Writings of Thomas Jefferson*, pages printed in parallel columns);
`importers/tcp.py` with `importers/paine.py`, `importers/locke.py` and
`importers/independence.py` (a typed transcription as the text, checked
against scans: see "A transcription as the text" below; the 1775
Declaration of the Causes and the Virginia Declaration of Rights, decision
66, are read the same way); `importers/amem.py` with
`importers/conventions.py` (the Library of Congress's typed Elliot: Henry's
tie-breaker, and the text of the state ratifying conventions).
Tests: `tests/test_ocr.py`, `tests/test_library.py`, `tests/test_tcp.py`,
`tests/test_independence.py`, `tests/test_conventions.py`.

## The idea in one paragraph

Optical character recognition (OCR) misreads old type: "tliis" for "this",
"S136" for "2136", italic "w" as "zv". But different scans of the same
printed book, made from different physical copies, usually misread
*different* words. So one scan supplies the page layout and a first reading of
every word; the OCR of one or two other scans of the same edition is lined up
against it word by word; and where the scans disagree, a vote with strict
rules picks a reading. Every word in the output is a reading some scan made.
Where no rule settles a word, the main scan's reading is kept and the word is
marked **uncertain**, with every scan's reading saved beside it, for a person
to check against the page image.

## Inputs

For each book, in `sources/raw/` (downloaded by `tools/fetch.py`, listed in
`sources/manifest.json` with URL, date and checksum):

- **Primary scan: DjVu XML** (`*_djvu.xml` from the Internet Archive). It
  gives every page, paragraph, line and word, with each word's box on the
  page. Layout comes only from this file.
- **Reference scans: plain OCR text** (`*_djvu.txt`) of other copies of the
  same printed edition. They supply second (and third) readings.

| Book | Primary | References |
|---|---|---|
| Ford, *Essays on the Constitution* (1892) | `ia-ford-essays-1892-toronto-xml` | `-brittle-txt`, `-google-txt` (two) |
| Ford, *Pamphlets on the Constitution* (1888) | `ia-ford-pamphlets-1888-cornell-xml` | `-google-txt` (one) |
| McMaster and Stone, *Pennsylvania and the Federal Constitution* (1888) | `ia-mcmaster-stone-1888-cornell-xml` | `-pitt-txt` (one) |
| *Debates and Proceedings in the Convention of Massachusetts* (1856) | `ia-mass-debates-1856-nypl-xml` | `-uc-txt`, `-google-txt`, `-cornell-txt` (three) |
| Annals of Congress, vol. 1 (1834) | `ia-annals-1834-v1-google-xml` | `-microfilm-xml`, and Tesseract's reading of the primary's page images (two) |
| Annals of Congress, vols. 4, 11 and 13 (1849–52) | the pages needed of the microfilm (vol. 4) or a Google scan (vols. 11, 13): `ia-part-annals-v{n}-{scan}-…` | the other scans' pages (vol. 4: the Google scan and Tesseract's reading of its page images; vols. 11 and 13: a second Google scan and the microfilm) (two) |
| *Congressional Record*, bound edition, vols. 44, 47, 48, 55, 56 and 58 (1909–19), and 75, 76, 93, 106, 108, 111 and 117 (1932–71) | govinfo's text layer of its scans, one PDF per house per day (`govinfo-crecb-{granule}`) | the Internet Archive's page-indexed OCR of a microfilm of the same part (`ia-record-{part}-text`) (one) |
| Elliot's *Debates*, vol. 3 (standard pagination; 1907 printing) | `ia-elliot-v3-1907-toronto-xml` | `ia-elliot-v3-1876-cornell-txt`, `-1861-google-txt`, `-1836-google-txt` (three) |
| *The New-York Journal* (1787–88), Brutus V–XVI | the Library of Congress's ALTO XML (`loc-nyjournal-{date}-p{n}-alto`) | none: one scan (see "One scan" below) |
| *Journals of the Continental Congress*, vols. 1, 4 and 5 (1904–06) | the University of California's scan of each volume (`ia-road-jcc-v{n}-uc-xml`) | two or three other copies of each, read from their DjVu XML like the main scan (`ia-road-jcc-v{n}-{copy}-xml`) |
| Ford, *Writings of Thomas Jefferson*, vol. 2 (1893) | `ia-road-ford-v2-uc-xml` | `-harvard-xml`, `-ucgoogle-xml` (two) |

With two references a word can be outvoted 2 to 1; with one, disagreements
are ties and depend on the tie rules below, so those books have
proportionally more uncertain words.

**Our own OCR as a reading** (decision 46). Where only two scans of a
printing can be found, the primary scan's page images (a raw source) can be
read with Tesseract for a third reading. It is run once
(`python -m importers.annals ocr`, single-threaded so a rerun gives the same
words), and its word boxes are kept in `sources/ocr/` with a record in
`sources/ocr/manifest.json`: the Tesseract and language-data package
versions, the command, and the raw images (id and sha256) it read. Importers
read the kept file; `make verify` checks the record but never runs
Tesseract. The Internet Archive's own OCR of newer scans is also Tesseract,
so a Tesseract reading and such a scan share confusions: in the Annals,
their agreement alone never makes a word known (`annals.independent`).

**Two-column books** (the Annals, `importers/annals.py`): each page is split
into its columns before the steps below. The gutter is found from the lines
that sit in one column; a line OCR read across both columns is split word
by word at it; the running head gives the column numbers, which are checked
against the pages around them as page numbers are.

**A text layer as the main scan** (the Congressional Record,
`importers/record.py`, decision 61). govinfo serves the bound Record as
scans whose OCR is an invisible text layer in the PDF, one word drawn at a
time. `tools/pdf.py` (`pdf_words`) reads each word and where it is drawn;
the words are put into lines by their baselines (a gap as wide as a gutter
ends a line) and measured in pixels at 300 dpi, so the steps below apply
unchanged; pages are split into two columns as the Globe's are into three.
The reference is the Internet Archive's OCR of a microfilm of the same
part, cut into the same printed pages with its page index and the page
numbers it read (`importers/record.py`, `microfilm`); with one reference,
every disagreement is a tie (see the rules below).

## Step 1: layout (`parse_djvu_xml`, `classify`, `blocks`)

1. **Pages, paragraphs, lines, words** are read from the XML. A page's scan
   number ("leaf") is kept on every passage, so the site can link to the page
   image (`https://archive.org/details/{item}/page/n{leaf - 1}`).
2. **Paragraphs OCR ran together are split** where print shows a new
   paragraph: a line that stops short of the right margin followed by a line
   indented as a paragraph is (verse, indented further, is not split line by
   line), or a line in smaller type starting with a note mark (text, then a
   footnote).
3. **Page furniture is set aside:**
   - *Running heads*: a short single line at the top of the page that holds a
     page number, is set in capitals, or repeats (letters only) the top line
     of a nearby page. The page number in it, when read, becomes the page's
     printed number. A head OCR read as two blocks on one line ("1788.]" |
     "SPIRIT OF THE PRESS. 383"), or ran into the paragraph below it, is
     also set aside.
   - *Folios*: a page number at the foot ("( 247 )"), or any line of a few
     characters alone at the very bottom (OCR reads small figures as "('56)"),
     unless it holds a word and a period (a signature, "Brutus."; a short
     note, "† Ibid.").
   - *Signature marks*: the printer's sheet number ("40") at the foot of a
     page, even where OCR made it the last line of the paragraph above.
   - *Plates*: a page with no running head, no page number and fewer than 25
     words (a portrait and its caption) is skipped.
   - *Page numbers* (`settle_folios`): a number read on a page counts only
     if it fits the pages around it (its offset from the scan's page count
     is the one most pages within ten read). Any other page, misread ("1"
     for 16, "41" for 413, two pages read "53" and "57" for 153 and 157) or
     unnumbered, takes its number from the nearest confirmed page. These are
     the page numbers a passage records.
4. **Footnotes** are paragraphs at the foot of a page in smaller type than
   the page's text (type size is a line's tallest word; the page's text size
   is taken high in its range, since a long note can outnumber the text), or
   marked and signed by the editor ("* … — Ed."). A note must begin with a
   mark (`*`, `†`, and their OCR forms) unless it continues a note that
   stopped mid-sentence or at a colon; small type without a mark (a
   signature in small capitals, a quotation) stays text. A note that runs on
   to the next page is joined to its start.
5. **Paragraphs are rejoined** across a page break, or where OCR split one,
   when the line before runs to the right margin and the next line is not
   indented, or when a sentence plainly continues (the text so far has no
   closing punctuation and the next line starts in lower case: OCR drops a
   leading dash, "——a convention", and the line then looks indented). Also
   joined: a line set flush left that starts in lower case ("&c.—— / same
   art. sect. 8"), unless it follows a quotation in verse or is a roman
   numeral; a line starting with a dash after a full line (OCR drops the
   first of two dashes, "——In this case", so the line looks indented); an
   author's name set to the right under a quotation ("Pope." under an
   epigraph); and a heading of paragraph numbers set over several lines
   ("XXIII, SEC. 21 ; … / SEC. 21 ; …"). Otherwise large or centered lines
   (headings) never continue a paragraph.
6. **Words hyphenated at a line end** are rejoined ("consti-" + "tution").

## Step 2: alignment (`Reference`, `align`, `pair_similar`)

Each reference scan's text becomes a list of words (line-end hyphens
rejoined). For a run of the primary's words (an essay's heading and text in
one run; each footnote on its own, since footnotes sit in a different order
in page text):

1. **Locate** the run in the reference: up to 40 of its four-word sequences
   are looked up, and the start most of them agree on (at least two) wins,
   the nearest to where the last run ended on a tie.
2. **Match** words by their letters and figures (case and punctuation
   ignored), with Python's `difflib.SequenceMatcher`.
3. **Pair differing words carefully.** Where the scans differ, words are
   paired only when their letters are mostly alike (at least half), or when
   one or two words differ between runs of at least three that agree. A
   word one scan reads as two ("coinni unity" for "community", "there-" +
   "fore") is paired as a unit. A scan's piece of a word broken at a line or
   page end ("citi-" for "citizen", "serted" for "asserted") is not a
   reading. Running heads one scan has in its text are not taken for half a
   word.
4. **Reject a misplaced match.** If fewer than half the run's words match,
   that reference is not used for the run at all. (Without this, two scans
   misplaced in the same way once "outvoted" the primary and turned "the
   friends of the new government" into "the Citizens of …".)

The result, for every primary word, is its readings:
`{"primary": "tliis", "brittle": "this", "google": "this"}`. A reading of
`""` means a scan read this word together with the one before.

## Step 3: the vote (`vote`, `consensus`)

Readings are grouped by their letters and figures. A **known word** is one
found in the clean texts already in the library (the Constitution, the
amendments, The Federalist), or one that two scans read identically and
cleanly at the same place ("attested"). Figures are never known words.
Scans of different copies share some misreadings (the same OCR engine, the
same type), so an attested word that undoes to a clean word by one common
confusion is not known: "eflfect" (the ff ligature, for "effect"), "wliole"
(for "whole"); the confusions are `SHARED_CONFUSIONS` in `importers/ocr.py`.

1. **Majority.** The group most scans share wins: "tliis" / "this" / "this"
   gives "this".
2. **Ties.** A known word wins over a non-word if it looks like the main
   scan's reading ("tliis" against "this"). Between two known words, a word
   from the clean texts wins over one only the scans attest, when the main
   scan reads the clean word or both look like its reading, and the word
   has more than one letter ("of" against "oi", "and" against "aud"; not
   "i," against "r,"). Otherwise the word is unsettled.
3. **Within the winning group** (same letters, different marks), a cleanly
   printed reading is used: no stray marks (`^ | ~ _ { } < > \ /`, a doubled
   stop, an asterisk inside a word), and no two different stops together
   ("naturally,.") unless two scans read it so ("art.,", "&c.,"). Of those,
   one ending in the same marks as the main scan's is preferred ("January,"
   not "January"). A word read whole beats the same letters with a space in
   them only if it is a known word and the pieces are not words themselves
   ("com munity" becomes "community"; "a vast" does not become "avast").
   If every reading of the winning letters has stray marks, the word is
   unsettled.

Some words stay **unsettled whatever the count**, because a majority can be
wrong in predictable ways (each row was found by reading samples of the
vote's changes; see "How well it works"):

| Case | Example | Why |
|---|---|---|
| A cleanly printed known word against a different known word, which fewer than two other scans read, or which is not in the clean texts | "friends" vs "citizens" | a real word is not swapped for another on one scan's say, nor for a misreading the scans share ("aflirmative") |
| A cleanly printed known word against a non-word | "asserted" vs "CATO. serted" | the primary is kept, settled (the others picked up a running head) |
| Capitals where the main scan reads lower case | "Ciiuse" (the page: "Cause") vs "CASSIUS.", "CASSIUS." | a signature or heading lined up with the wrong word |
| A much shorter reading (under three quarters the length) | "prometers" vs "moters", "moters" | a piece of a word broken at a line end |
| Figures that differ | "2181)" vs "S181)", "S181)" | scans share confusions (2/S, 1/i), so a majority can be wrong |
| A word only the main scan has, not a known word | "legislatlve" | nothing corroborates it |
| Scans split the word differently | "deliver d" vs "delivered" | the page has "deliver'd"; OCR dictionaries regularize |
| A scan spells out an elision | "renown'd" vs "renowned" | the same regularization |

Two scans or more that agree on a word of the clean texts **overrule the
main scan** when it reads another known word (decision 59): "tho", "bo",
"arc", "lo" become "the", "be", "are", "to" where the other copies read
them so. If the main scan's word is a clean-text word too ("minority"
against "majority"), the majority's word is taken but stays marked
uncertain, for a person to check against the page.

An unsettled word keeps the main scan's reading. Words a scan read as one
are voted on together; if that vote fails, the scans that read them word by
word vote on each.

## The Anti-Federalist Library: a tie-breaker (`importers/library.py`)

Decision 55. The Anti-Federalist Library (antifederalists.org) prints
many of the same essays, as Markdown files in a public repository (pinned to
one commit; each file is a raw source). It is CC0, but it names no source,
and its bracketed insertions (`[sic]`, `[,]`, conjectures with "?") show it
was copied from a modern edition; it has OCR-like misreadings of its own
("fight" for "right", "discemable"). So it never votes and never supplies a
word. Its text (without front matter, headings, editorial brackets, page
numbers in braces and diaereses) is lined up with each essay's words like a
reference scan, and then, for each word (`ocr.tie_break`):

1. **A word the vote left unsettled** is settled if one of the scans' readings
   has the Library's letters: that scan's reading is taken, with its own
   spelling and marks (the one whose marks match the Library's, if several).
   If the main scan's reading has them, the word is kept and settled (the
   Library corroborates a reading no other scan had).
2. **If no scan's reading agrees**, nothing changes: the word stays
   uncertain, and the Library's reading is recorded with it as a
   `suggestion` for a person to check against the page image.
3. **Where the Library follows the printing the scans are of** (Elliot, the
   *New-York Journal*: `strict`), a settled word it reads differently is
   unsettled too, with the suggestion, unless two scans read it alike and it
   is a known word (four scans' "right" stands against the Library's
   "fight"). Figures are never known words, so four scans' "1" for "I" is
   left for a person. In the other works (later reprints, whose spelling
   differs from the Library's edition) a settled word is never touched.

The vote's own safeguards hold: the Library cannot choose a reading of more
or less than the main scan's word ("property" for "prop-" before "erty",
"that zest" for "thatzestof"), and a Library word that is a common OCR
confusion of a scan's reading and not a known word ("discemable" against
"discernable") is ignored. Works and pages used: `library.PAGES`.

**A typed reprint as a second tie-breaker** (decision 69). For the Dissent
of the Pennsylvania Minority and Centinel I–IX, the Text Creation
Partnership's typed text of a New York collection of 1788 that reprints
them (Evans-TCP N16599; `importers/tcp.py`, `reference`, `readings`) is
used the same way, never strictly, after the Library: it is asked only
about a word the vote and the Library have left unsettled with no
suggestion of the Library's. It can settle the word with a scan's reading
or corroborate the main scan's; where no scan reads it so, its reading is
the word's `suggestion`, with `suggested_by` naming it ("Evans-TCP
N16599"), but only where its letters are mostly a scan's (another printing
may word it otherwise: "Twelfth." against the scans' "12."). Words the
transcription could not read give no reading. Works and divisions used:
`typed` in `importers/ratification_series.py`.

**Patrick Henry: the Library of Congress's Elliot first** (decision 68).
For Henry's speeches the tie-breaker's reading of each word is the Library
of Congress's typed transcription of the same volume and pages
(`importers/amem.py`), where it lines up with the word, and the
Anti-Federalist Library's only where it does not; the rules above are the
same (`strict`). A suggestion records whose it is (`suggested_by: "loc"`),
and only the Anti-Federalist Library's are taken in bulk by
`tools.errata accept-library`. `python -m importers.elliot loc-report`
lists every word the scans settled that the transcription reads otherwise
(erratum 150).

## One scan: the New-York Journal (`importers/nyjournal.py`)

Brutus V–XVI exist only in the original newspaper, scanned once by the
Library of Congress (Chronicling America). Its OCR is ALTO XML: each word,
its box and the engine's confidence (`WC`). Pages are split into columns
(text blocks that share most of their width), columns into paragraphs
(an indented line after a short one, a centred line, a line with a large
initial), and paragraphs rejoined across columns and pages when the column
ends with a full line or mid-sentence. The essay runs from the newspaper's
line and heading to the signature ("BRUTUS.", or "(To be continued.)" for a
first instalment).

With one scan there is nothing to vote with. Each word's only reading is
the OCR's; it is settled when it is a known word read with confidence 0.5
or more, or when the Library reads it the same way; otherwise it is marked
uncertain, with the Library's reading as a suggestion where it differs.
The long s, which OCR reads as "f" or "l" ("fyflem" for "system"), is never
changed into "s": that would be typing text. Each passage links to its
newspaper page at the Library of Congress, and the errata page shows the
part of the page the paragraph fills (`scan.regions`).

## Two texts side by side: the right column (`importers/parallel.py`)

The Journals print the Declaration and Resolves of 1774 in the right-hand
column beside John Sullivan's draft, and Ford prints the fair copy of
Jefferson's proposed constitution beside his first draft (decision 66). On
the pages the importer's configuration lists (`independence.BOOKS`,
`columns`), each scan's page is cut before the steps above:

1. The page's running head and printer's signature mark are set aside, and
   the editor's notes found: in the Journals by their smaller type at the
   foot of the page (`parallel.mark_notes`; the notes' marks are superscript
   figures, which OCR reads as "'" or "^", not the marks of step 1); in Ford,
   whose notes are set nearly as large as the text, from the line a pattern
   in the configuration names (`notes_from`) to the foot of the page.
2. Full-width lines above the columns (the day's proceedings before the
   resolutions) are kept; the columns begin at the first line, or at the line
   a pattern names (`columns_from`).
3. The gutter is found from the lines that sit in one column
   (`columns.find_gutters`), or, on a page with few of them, is the middle of
   the page's text. Each word goes to the column its first letter is in: some
   scans' word boxes take in the space after the word and reach across the
   gutter. A page whose lines all lie right of its middle (the left column has
   ended) is all right column.
4. The right column becomes a page of its own; its paragraphs are found as in
   step 1, and in Ford also by the hanging indent of Jefferson's charges
   against the king (`parallel.outdented`).

The reference scans are cut the same way, so each copy's text is the right
column only: the drafts beside it, which share many words with it, are never
taken for it. A reference's notes are kept apart from its text, so a passage
is never matched with a note that quotes it. Each part's paragraphs are
found in the other scans together, sixty words at a time, so that a short
paragraph has context and a passage that runs over a page break is matched
on both sides of it.

## A transcription as the text: the TCP (`importers/tcp.py`)

Decision 67. Where the Text Creation Partnership has keyed the printing by
hand (CC0, TEI P5), its transcription is the text and the scans only check
it: Paine's *Common Sense* (1776) and Locke's Second Treatise (1690). No
vote is held. Each of the transcription's words is lined up with the OCR of
one or two scans of the same printing, compared by its letters with the
long s set aside ("s", "f" and "l" compare alike), and marked uncertain,
with the transcription's reading (`tcp`) beside the scans', where no scan
reads it alike and a scan reads another real word there, lacks it where it
reads the words around cleanly, or has a word more; letters the keyers
could not read ("•") are always marked. The transcription's word is never
replaced. A scan photographed in its binding (the John Carter Brown
Library's) has its words outside the block of text dropped and its lines
rebuilt from where the words stand. The rules and what they cannot see are
in `docs/editions.md`, "Sources of the Declaration".

Seven pamphlets of the ratification debate (decision 69,
`importers/pamphlets.py`) are imported from Evans-TCP transcriptions of
their first printings the same way, but no scan of those printings was
found, so only the words holding letters the keyers could not read are
marked (`docs/editions.md`, "Pamphlets typed by the Text Creation
Partnership"). Those words are not on `/errata/`, which needs a page image.

**The Library of Congress's Elliot** (decision 68) is the text of the state
ratifying conventions in the same way (`importers/conventions.py`): each
word of the transcription is lined up with the Internet Archive's scans of
the 1907 printing of the same volume, one scan for vols. 2 and 4, four for
vol. 3, and marked uncertain, with the transcription's reading as `primary`
beside the scans', where most of the scans read another known word (or a
number) and it is not a shared OCR confusion; scan readings that are not
words are OCR noise, counted but not marked, and where the scans split
evenly nothing is marked. A word only one scan reads with a known word's
letters is still marked: with one scan, an OCR misreading that makes a word
("be" for "he") cannot be told from a keying slip, so both are left for a
person. Before that, the importer checks that the pagination is the same
(the first words of each paragraph are on the scan's page of that number).
Details in `docs/editions.md`, "The state ratifying conventions".

## Step 4: structure (`ratification.py`)

Each series lists, in `ratification_series.py`, its book, the printed pages
from its title page to the page before the next section, a pattern for its
essay headings ("CATO, III."), its signature, attribution and side.

- Pages map to scan leaves by the book's usual offset, corrected by printed
  page numbers that agree with their neighbours (plates shift the offset).
- Essays start at their headings. The printed numeral must match the essay's
  id; OCR's usual misreadings of numerals are allowed ("VL" for VI, "VHI"
  for VIII, "XL" for XI). Where the edition prints a number twice, the series
  lists ids with a letter (`Landholder.10b`), checked against the page image.
- Short lines before the salutation are the essay's heading lines
  (newspaper, number, date); a greeting printed on the date's line is split
  off. Short lines after the last paragraph (signature, place, date,
  "(To be continued.)", "Your's, &c.") are its signature, including a
  signature run into the end of the last paragraph, with any place and date
  after it, when it starts a sentence ("… oppression ? CenTinei,.
  Philadelphia, Nov. 30, 1787.").

## What the output records

In `texts/{work}.json` (validated by `make verify`, see
`docs/contributing.md`):

```json
{
  "ref": "Cato.2.1",
  "text": "… plan of pozver deliver d down …",
  "pages": ["250"],
  "scan": {"item": "essaysonconstitu00forduoft", "leaves": [262]},
  "uncertain": [
    {"start": 79, "end": 88,
     "readings": {"brittle": "delivered", "google": "delivered", "primary": "deliver d"}}
  ]
}
```

- `uncertain` spans are character offsets into `text`; verify checks that
  each lies inside the text, in order, and that the text there is one of the
  scans' readings.
- A division (essay) has the same `uncertain` map for its heading lines,
  salutation and signature, keyed `publication.0`, `salutation`, `signature`.
- `pages` are the printed page numbers read on the passage's pages (some are
  missing where OCR misread them); `scan.leaves` are always present.

- `suggestion` on an uncertain span: the Anti-Federalist Library's reading,
  where no scan's reading agrees with it. Verify checks it is one line and
  differs from the text. With `suggested_by`, it is another tie-breaker's
  reading instead: a typed text's ("Evans-TCP N16599", decision 69) or the
  Library of Congress's Elliot ("loc", decision 68); `python -m tools.errata
  accept-library` leaves those for a person.
- `accepted` on an uncertain span (`{source: "library", by, at}`): the text
  has the Library's reading there, accepted by the project owner without a
  check against the page (decision 56); the span keeps the scans' readings
  and stays marked until a person confirms or overrules it.
- `corrected` lists the words a maintainer read off the page image
  (`start`, `end` in the corrected text, the scans' word `was`, and `by` and
  `at`); see "Reviewing and correcting".

On the site, uncertain words are underlined with dots; selecting a paragraph
shows each scan's reading and a link to the page image. Corrected words are
underlined with a plain line.

## How well it works

At the October 2026 import: 19 works, about 177,000 words (Brutus, added
later, is below).

- **Corrections.** The vote changed 1,133 words from the main scan's
  reading. Random samples of these changes were read one by one, and each
  wrong change found led to a rule above (the "Cause"/"CASSIUS.",
  "prometers"/"moters", "a vast"/"avast" and "January,"/"January" rows came
  from this). In the last two samples, 120 changes after all the rules, 116
  were clearly right ("tliis" to "this", ")'ou" to "you", "Ge7itlemeii," to
  "Gentlemen,"); the other four swapped one garbled reading for another
  ("otherlmust" for "otherjmust") or dropped a comma. None replaced a real
  word with a different one.
- **Uncertain words.** 611 are marked, about 3.5 per thousand words (from
  1 to 11 per thousand by work; short pieces with display-type newspaper
  headings run highest). Run `python -m tools.uncertain` for current counts.
- **Brutus I–IV** (the 1856 *Debates*, three reference scans, clean book
  type, no newspaper headings): about 13,200 words with 13 marked, 1 per
  thousand, most of them a misreading two scans share elsewhere in the book
  ("wliole") against the others' "whole", which the rules leave for a
  person.
- **Paragraphs.** Spot checks of paragraph breaks against page images found
  them right on the pages checked, after the fixes in step 1.
- **The Anti-Federalist Library as a tie-breaker** (October 2026), in
  Brutus I–IV, Agrippa I–XI, the Federal Farmer I–V and Centinel I and
  V–XVIII: 28 words changed to another scan's reading (each checked:
  "lie" to "he", "tlie powers" to "the powers", "30,cxx)" to "30,000"), 5
  more settled as the main scan read them, and 25 left uncertain with a
  suggestion. Nothing else in those texts changed.
- **Patrick Henry** (Elliot, four scans): about 57,700 words with 50
  marked, under 1 per thousand, 23 of them with a suggestion.
- **Brutus V–XVI** (one newspaper scan): about 28,800 words with about
  4,040 marked, 140 per thousand, about 3,000 of them with the Library's
  reading as a suggestion (about 500 of those differ only by the long s).
- **The Library's readings accepted** (decision 56): all 3,041 suggestions
  (2,994 in Brutus, 22 in Henry, 25 in the older works) are now in the text,
  still marked as unchecked.
- **The Annals of Congress** (1834, small type in two columns; one other
  scan and a Tesseract reading): about 53,000 words with 562 marked, 11 per
  thousand. With the two scans alone it was 22 per thousand.
- **The Congressional Globe, 1866** (UNT's OCR, checked against the Lincoln
  Financial Foundation copy and, for part 4, a microfilm; decision 58):
  about 106,000 words in the House's debate with 1,249 marked (12 per
  thousand) and 146,000 in the Senate's with 1,704 (12 per thousand).
  Before the Lincoln copy's part 4 was added the June days had only the
  microfilm, and it was 1,404 (13 per thousand) and 3,271 (22 per
  thousand). The new vote changed about 1,300 runs of words, most a
  misreading put right ("tho" to "the" 124 times, "Slates" to "States",
  "aud" to "and"); errata 64 and 65 list the words it made worse or
  left marked against two agreeing copies.
- **The Annals of Congress, volumes 4, 11 and 13** (decision 60): about
  1,760 words (1794) with 35 marked, 20 per thousand; about 5,230 (1802)
  with 24 marked, 5 per thousand; about 171,300 (1803) with 5,278 marked,
  31 per thousand (after decision 59's vote), where both Google scans are small and share their OCR
  engine's misreadings ("ihe", "lo", "Slates"), so their agreement does not
  make a word known.

- **The Congressional Record, 1909–19** (decision 61; govinfo's text layer,
  checked against a microfilm's OCR): about 834,000 words with 36,600
  marked, 44 per thousand; from 29 per thousand (the Senate, 1909) to 70
  (the House, December 1917, whose volume the OCR reads worst). About 90–95%
  of words have a reading from the microfilm; the rest (names in roll
  calls, lines the two OCRs read in different orders) keep govinfo's
  reading alone.
- **The road to independence** (decision 66): the Journals of the
  Continental Congress, three or four copies a volume: about 4,600 words with
  36 marked (8 per thousand), most of them the editor's double bars around
  entries of the rough journal, figures, and the signers' abbreviated names;
  Ford's *Writings of Jefferson*, three copies: about 1,860 words with 14
  marked. Nearly every word has a reading from another copy (99–100% from at
  least one; the Michigan copy of vol. 5 lacks pp. 425–426). The two TCP
  transcriptions: the Declaration of Rights, 883 words with 10 marked (4 of
  them the keyers' gaps, 6 where the scan of the same printing reads another
  word); the Declaration of the Causes, 2,567 words with 11 gaps.

- **The Congressional Record, 1932–71** (decision 62; the same method):
  about 1,371,000 words with 18,700 marked, 14 per thousand; from 4.5 (the
  Senate, 1965) to 23 (1947) and 47 (the Senate, 1971, whose debate prints
  long tables). About 7,500 of the marked words are figures.

- **The TCP texts** (decision 67; the transcription is the text, the scans
  a check): *Common Sense*, about 15,800 words with 61 marked, 4 per
  thousand, against one scan that was lined up with 92% of the words;
  Locke's Second Treatise, about 53,500 words with 162 marked, 3 per
  thousand, against two scans (95% and 80% of the words; 2% with neither).
  Most marks are OCR misreadings of real words ("dear" for "clear"); some
  are the transcription's slips (errata 130–133).

The rules lean toward marking a word uncertain rather than guessing: a
wrong word that looks settled is worse than a right word with a dotted
underline.

**What it cannot catch:**

- *Misreadings every scan shares.* All three scans read Cato II's date as
  "October ii" (old-style "11"); such words look settled. Errata 14 and 15
  record the ones found so far.
- *Display type.* Newspaper headings ("(Number 2136)") are read worst; most
  of their words end up uncertain or wrong.
- *Regularized spellings* where only one scan disagrees and the other two
  agree on a modern spelling.
- *Words the main scan dropped.* The vote decides among the main scan's
  words; a word it omitted entirely (Cato V's salutation, erratum 14) is not
  restored.
- *Italics* are not recorded, unlike The Federalist.

## Reviewing and correcting

1. Open the errata page (`/errata/`, for maintainers). It lists every word
   the scans could not settle, by work, with the words around it, each
   scan's reading, the Anti-Federalist Library's suggestion where there is
   one (marked as such: no scan reads it), and the page images (select an
   image to zoom). From the
   command line:

   ```
   python -m tools.uncertain                 # counts per work
   python -m tools.uncertain cato --md       # a checklist with page-image links
   ```

2. Check each word against the page image. Pick the reading the page shows,
   or type what is printed (old spelling and punctuation, as printed). Leave
   a word you cannot read.
3. Choose **Send to GitHub** and submit the issue. The errata workflow
   (`.github/workflows/errata.yml`, people with write access only) records
   each correction in `corrections/{work}.jsonl` under your GitHub login
   (`python -m tools.errata apply`), updates link quotes that contain the
   word, re-runs the importers and `make verify`, and commits.
4. Corrections are never typed into `texts/`. The importers apply them
   (`importers/corrections.py`): the word is replaced, its uncertain mark
   dropped, and the change logged in the passage's `corrected` list (who,
   when, and what the scans read). On the site a corrected word is
   underlined. A correction that no longer matches its passage stops the
   import (decision 48).
5. Errors that are *not* marked uncertain (shared misreadings), wrong
   paragraph breaks and attributions go in `docs/errata.md`.

Refs are locked once published (`refs.lock`). A correction to a word never
changes refs; a wrong paragraph break found later is recorded as an erratum
and needs a decision, as for The Federalist.

## Adding a book or series

1. Find scans of the *same printed edition* on the Internet Archive: one with
   DjVu XML (the primary) and at least one other copy's OCR text. Add them
   with `tools/fetch.py add` (ask first: a new upstream source).
2. Add the book to `BOOKS` and each series to `SERIES` in
   `importers/ratification_series.py`: pages from its title page to the page
   before the next section, the heading pattern (use `NUM` for the numeral),
   the signature, and the attribution in the edition's own words, with
   `attribution.source` if it comes from elsewhere in the edition.
3. Run `python -m importers` and look at the structure of each essay
   (heading lines, salutation, first and last paragraph, signature, notes).
   The importer stops with a clear message if an essay heading is missing,
   numbered out of order, or extra.
4. Check paragraph breaks and any doubtful headings against page images,
   then `make lock-refs` and `make verify`.
5. Document the edition in `docs/editions.md` and the refs in
   `docs/references.md`.
