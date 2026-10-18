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
books and series). Tests: `tests/test_ocr.py`.

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

With two references a word can be outvoted 2 to 1; with one, disagreements
are ties and depend on the tie rules below, so those books have
proportionally more uncertain words.

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
| A cleanly printed known word against a different known word | "friends" vs "citizens" | a real word is never silently swapped for another |
| A cleanly printed known word against a non-word | "asserted" vs "CATO. serted" | the primary is kept, settled (the others picked up a running head) |
| Capitals where the main scan reads lower case | "Ciiuse" (the page: "Cause") vs "CASSIUS.", "CASSIUS." | a signature or heading lined up with the wrong word |
| A much shorter reading (under three quarters the length) | "prometers" vs "moters", "moters" | a piece of a word broken at a line end |
| Figures that differ | "2181)" vs "S181)", "S181)" | scans share confusions (2/S, 1/i), so a majority can be wrong |
| A word only the main scan has, not a known word | "legislatlve" | nothing corroborates it |
| Scans split the word differently | "deliver d" vs "delivered" | the page has "deliver'd"; OCR dictionaries regularize |
| A scan spells out an elision | "renown'd" vs "renowned" | the same regularization |

An unsettled word keeps the main scan's reading. Words a scan read as one
are voted on together; if that vote fails, the scans that read them word by
word vote on each.

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

On the site, uncertain words are underlined with dots; selecting a paragraph
shows each scan's reading and a link to the page image.

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

1. List what needs checking:

   ```
   python -m tools.uncertain                 # counts per work
   python -m tools.uncertain cato --md       # a checklist with page-image links
   ```

2. Check each word against the page image. Most uncertain words are clear on
   the page.
3. Record what the page shows in `docs/errata.md`: the ref, the text as
   imported, what the page prints, the page, and who checked it. Also record
   errors that are *not* marked uncertain (shared misreadings) when you see
   them.
4. Corrections are never typed into `texts/`. A confirmed correction is
   applied by the importer, from a list that names each erratum, and is
   logged on the passage. That list does not exist yet; it will be added with
   the first confirmed correction (rule 3 in `CLAUDE.md`).

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
