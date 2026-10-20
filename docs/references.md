# References

Every passage has a ref: a dotted, human-readable name that never changes once
published. Corrections go through `docs/errata.md`, never renumbering.

A ref names either a **segment** (a stored passage) or a **parent** (any
dot-boundary prefix of a segment ref, such as `Constitution.1.8` or
`Federalist.10`). Links may point at either; a quote on a link to a parent
must appear in one of the segments under it.

Numbers in refs are a convention of this project, not part of any text.

## Declaration of Independence (`texts/declaration.json`)

From the National Archives transcription of the Stone Engraving.

- `Declaration.Heading`: the two lines above the text ("In Congress, July 4,
  1776" and "The unanimous Declaration of the thirteen united States of
  America,"), one per line.
- `Declaration.{n}`: the paragraphs as the transcription sets them,
  numbered from 1 ("When in the Course of human events…"). Each grievance is
  its own paragraph there, so `Declaration.2` is "We hold these truths…",
  `Declaration.3`–`Declaration.29` are the grievances ("He has…", "For…"),
  and `Declaration.32` is the closing resolution ("We, therefore…").
- `Declaration.Signers.{n}`: each group of signatures, numbered in the
  transcription's order (Georgia first, Matthew Thornton of New Hampshire
  last). Some states appear twice, as on the engraving (John Hancock's
  signature is its own group), so groups are numbered rather than named; the
  state is in each passage's `state` field and label.

## Constitution (`texts/constitution.json`)

Source: National Archives transcription of the engrossed parchment.

| Ref | Covers |
|---|---|
| `Constitution.Preamble` | The Preamble |
| `Constitution.{article}.{section}.{clause}` | Articles I–IV, which have sections |
| `Constitution.{article}.{clause}` | Articles V–VII, which have no sections |
| `Constitution.Interlineations` | The note on interlined words ("The Word, "the," being interlined…") |
| `Constitution.Attestation` | "Attest William Jackson Secretary" |
| `Constitution.Closing` | "done in Convention by the Unanimous Consent…" |
| `Constitution.Signers.President` | Washington's signature block |
| `Constitution.Signers.{State}` | One state's signatures, state name without spaces (e.g. `Constitution.Signers.NewHampshire`) |

Articles and sections are numbered from the transcription's own headings
("Article. I.", "Section. 8."). **A clause is one paragraph of the National
Archives transcription**, counted from 1 within its section (or within its
article, for Articles V–VII). This matches the clause numbering commonly used
by Constitution Annotated, e.g. Article I, Section 8 has 18 clauses, so
`Constitution.1.8.3` is the Commerce Clause and `Constitution.1.8.18` the
Necessary and Proper Clause. The importer fails if Article I, Section 8 does not
yield 18 clauses.

Article VII has one clause, `Constitution.7.1`. The paragraphs after it on the
parchment are the closing matter listed above, not clauses.

Signature blocks keep the names line by line as transcribed. The state order is
the order of the National Archives page.

## Amendments (`texts/amendments.json`)

Sources: National Archives transcriptions of the Bill of Rights (Amendments
I–X, "in their original form") and of Amendments XI–XXVII.

| Ref | Covers |
|---|---|
| `Amendment.{n}.{section}` | An amendment with numbered sections (XIII–XV, XVIII, XX–XXVI) |
| `Amendment.{n}.{clause}` | An amendment without section headings: one ref per paragraph, from 1 |

So every single-paragraph amendment is `Amendment.{n}.1` (e.g. `Amendment.1.1`),
and Amendment XVII's three paragraphs are `Amendment.17.1`–`Amendment.17.3`.
`Amendment.{n}` is the parent ref for the whole amendment.

A section with more than one paragraph (XXIII §1, XXV §4) is one segment; its
paragraphs are separated by a blank line in the text.

## The Joint Resolution of 1789 (`texts/joint-resolution-1789.json`)

Source: the National Archives transcription of the enrolled original, on its
Bill of Rights page.

| Ref | Covers |
|---|---|
| `Resolution1789.Heading` | "Congress of the United States begun and held at the City of New-York…" |
| `Resolution1789.1` | The preamble: "THE Conventions of a number of the States…" |
| `Resolution1789.2` | The resolving clause: "RESOLVED by the Senate and House…" |
| `Resolution1789.3` | "ARTICLES in addition to, and Amendment of the Constitution…" |
| `Resolution1789.Article.{n}` | "Article the first…" to "Article the twelfth…", `n` = 1–12 |
| `Resolution1789.Attest` | "ATTEST," and the three signatures |

The articles keep the 1789 numbering: Article the third is the First
Amendment, Article the twelfth the Tenth, and Article the second the
Twenty-seventh.

## The Federalist (`texts/federalist.json`)

Source: Project Gutenberg eBook #18 (see `docs/editions.md`).

| Ref | Covers |
|---|---|
| `Federalist.{paper}` | A whole paper (parent ref) |
| `Federalist.{paper}.{paragraph}` | A paragraph of the paper's body, from 1 |
| `Federalist.{paper}.fn{n}` | The edition's footnote `[n]` to that paper |

Paper numbers are the edition's ("No. X." is `Federalist.10`). The heading,
newspaper line, attribution, salutation ("To the People of the State of New
York:") and signature ("PUBLIUS.") are metadata on the paper and are **not**
counted as paragraphs. Paragraph 1 is the first paragraph after the salutation.
Paragraph boundaries are the edition's blank lines.

The edition prints No. 70 twice; refs `Federalist.70.*` number the first
version. The second is stored unsegmented on the paper as a variant.

## The ratification debate (`texts/{work}.json`)

Essays and letters imported by `importers/ratification.py` (series listed in
`importers/ratification_series.py`; editions in `docs/editions.md`).

- A series: `{Series}.{essay}.{paragraph}`, e.g. `Cato.3.2`, `FederalFarmer.3.2`,
  `Centinel.24.1`. The essay number is the number printed in its heading.
  Where the edition prints the same number twice, the second gets a letter:
  `Landholder.10b` (Ford prints two numbers X), `Agrippa.15b` (two numbers XV,
  and no XVI).
- A single essay or letter: `{Name}.{paragraph}`, e.g. `Caution.1`,
  `PlainDealer.3`.
- Footnotes: `{essay}.fn{k}` (`Cato.2.fn1`), numbered in order within the
  essay; for a single piece `{Name}.fn{k}`.
- The essay's heading lines (newspaper, number, date), salutation and
  signature are fields of the essay's division, not passages.
- Names are written without spaces: `Cato`, `Centinel`, `Agrippa`,
  `FederalFarmer`, `LutherMartin`, `GerryReply` (Elbridge Gerry's replies to
  A Landholder), `Landholder`, `Cassius`, `Caesar`, `Sydney`, `Countryman`,
  `CitizenOfNewHaven`, `CursoryRemarks`, `Caution`, `FriendToTheConstitution`,
  `PlainDealer`, `WilliamsonRemarks`, `SteadyAndOpenRepublican`,
  `WilliamsLetter`. `Brutus` is reserved for Brutus's essays.
- **Brutus** is one work from two printings: I–IV from the 1856 *Debates*,
  V–XVI from the *New-York Journal*, numbered by the printed numbers.
  `Brutus.11` is not used: Brutus XI has no scan (it stays free for that
  essay if one is found). XII and XIV were printed in two instalments; each
  is one essay, its paragraphs numbered through both (`Brutus.12.1` …), and
  each passage records the issue it is in (`scan.issue`).

### Pamphlets typed by the Text Creation Partnership

Imported by `importers/pamphlets.py` (decision 69) from Evans-TCP
transcriptions of the first printings. One prefix per work:
`ColumbianPatriot`, `JayAddress`, `CoxeExamination`, `WilsonSpeech`,
`Aristides`, `RandolphLetter`, `Monroe` (*Some Observations on the
Constitution*), `NativeOfVirginia`.

- A single piece: `{Name}.{paragraph}` from 1 (`ColumbianPatriot.1`,
  `JayAddress.21`, `WilsonSpeech.1`, `Aristides.1`, `Monroe.1`); notes
  `{Name}.fn{k}`. Matter printed before or after the text is a passage
  named for it: `Aristides.Dedication` (to Washington), `Monroe.Errata`
  (the printed errata, one line each).
- A pamphlet in parts: `{Name}.{part}.{paragraph}`, notes
  `{Name}.{part}.fn{k}`. Parts:
  - `CoxeExamination.Preface` ("To the Candid Reader") and
    `CoxeExamination.1` … `.4` (Numbers I–IV). James Wilson's speech,
    printed after them in the same pamphlet, is a work of its own,
    `WilsonSpeech`.
  - `RandolphLetter.Printer` (the letter to the printer),
    `RandolphLetter.Request` (the delegates' letter to Randolph of December
    2, 1787), `RandolphLetter.Reply` (his reply of December 10) and
    `RandolphLetter.Letter` (the letter of October 10, 1787), in the
    pamphlet's order.
  - `NativeOfVirginia.Observations` (the introduction, "Observations on
    the Federal Government"), `.Plan` (the Preamble and the author's remarks
    on it, under "Plan of the Federal Constitution"), `.Article1` …
    `.Article6` (his remarks on each article, the article's clauses quoted
    as paragraphs of their own, as printed), `.Note`, `.ToTheReader` and
    `.Errata` (each printed erratum a passage).
- Headings, date lines, salutations and signatures are fields of the
  division, as for the essays. The title pages are not imported.

### Patrick Henry in the Virginia convention (`texts/patrick-henry.json`)

Imported by `importers/elliot.py` from Elliot's *Debates*, vol. 3.

- `Henry.{day}`: one division per speech, named by the day as month and
  day (`Henry.Jun5`); a second or later speech that day takes a letter
  (`Henry.Jun14b`, `Henry.Jun14c`), as the debates in Congress do. The day
  is the speech's date; where Elliot's day heading is misprinted the date
  follows the 1836 printing (erratum 60, `Henry.Jun19`).
- `Henry.{day}.{paragraph}`: the paragraphs as Elliot prints them, from 1.
  The speaker's name ("Mr. HENRY.") stays in the first paragraph, as
  printed. Where a speech takes in another member's remarks (`Henry.Jun17`,
  `Henry.Jun23`, `Henry.Jun23b`), their paragraphs are numbered with
  Henry's, each opening with its speaker's name.
- Notes, if any: `Henry.{day}.fn{k}`.

## Sources of the Declaration

Texts from the Text Creation Partnership's transcriptions, checked against
scans (decision 67).

### Common Sense (`texts/common-sense.json`)

Thomas Paine's pamphlet, first edition (Philadelphia: R. Bell, 1776),
imported by `importers/paine.py`.

- `CommonSense.Introduction`, `CommonSense.1` … `CommonSense.4`: the
  Introduction and the four parts, numbered as the title page numbers its
  subjects (I. "Of the Origin and Design of Government in general …", II.
  "Of Monarchy and Hereditary Succession", III. "Thoughts on the present
  State of American Affairs", IV. "Of the present Ability of America …").
  The part's printed heading is the division's `title`.
- `CommonSense.{part}.{paragraph}`: the paragraphs, numbered from 1 in each
  part (`CommonSense.Introduction.1` is "PERHAPS the Sentiments …").
  Quotations set apart from the text (Dragonetti, in part III) are
  paragraphs, numbered with the rest.
- `CommonSense.{part}.fn{k}`: Paine's notes, numbered within the part
  (`CommonSense.3.fn1`, on Massanello).
- The title page, the running title "COMMON SENSE." over part I, "FINIS."
  and the bookseller's advertisement are not passages.

### Locke, the Second Treatise (`texts/locke-second-treatise.json`)

Book II of John Locke's *Two Treatises of Government*, first edition
(London, 1690), imported by `importers/locke.py`. The prefix `Locke` is
the Second Treatise's; the First Treatise, if imported, needs another.

- `Locke.{chapter}`: the nineteen chapters, numbered as printed ("CHAP.
  II."); the chapter's title ("Of the State of Nature.") is the division's
  `title` (chapter I has none).
- `Locke.{chapter}.{section}`: Locke's own numbered sections, the usual way
  to cite the work (`Locke.2.4` is § 4, "TO understand Political Power …").
  The section number is Locke's, not counted within the chapter, so the
  sections run from `Locke.1.1` to `Locke.19.243`. A section of several
  paragraphs (or with a list, as § 1) is one passage, its paragraphs
  separated by a blank line, as for the amendments. This printing has no
  § 21 (later editions add one), so there is no `Locke.3.21`; were it
  imported from another printing it would take that ref. § 236 begins
  inside Barclay's Latin, which the printing sets inside § 235.
- `Locke.{chapter}.fn{k}`: the notes printed in the margin (Hooker's
  words), numbered within the chapter.

## Debates in Congress

### The Bill of Rights, 1789 (`texts/house-amendments-1789.json`)

The House of Representatives' proceedings on amendments to the
Constitution, 1789, imported by `importers/annals.py` from the Annals of
Congress (decision 46).

- `House1789.{day}`: one division per day, named by its date as month and
  day: `House1789.Jun8`, `House1789.Aug13`, `House1789.Sep24`. The date is
  the day's heading as printed, checked against the 1789 calendar.
- `House1789.{day}.{paragraph}`: the paragraphs of the day's item headed
  "Amendments to the Constitution", numbered from 1 after the heading
  (`House1789.Jun8.1` is "Mr. Madison rose, and reminded the House…").
- Footnotes, if any: `House1789.{day}.fn{k}`.
- The printed heading of the item is the division's `title`; each passage
  records the printed columns it is on (`columns`), since the Annals number
  columns, not pages.

### The Fourteenth Amendment, 1866 (`texts/house-fourteenth-amendment-1866.json`, `texts/senate-fourteenth-amendment-1866.json`)

Each house's debate on the joint resolution (H. R. No. 127) proposing the
Fourteenth Amendment, imported by `importers/globe.py` from the
Congressional Globe (decision 47).

- `House1866.{day}` and `Senate1866.{day}`: one division per item, named by
  its date (`Senate1866.May23`). A second item of the same day takes a
  letter: `House1866.May8b`, `House1866.May8c`.
- `House1866.{day}.{paragraph}`: the item's paragraphs, numbered from 1 after
  its heading. Each records the printed pages it is on (`pages`).
- The item's printed heading ("RECONSTRUCTION AGAIN.") is the division's
  `title`.

### The Thirteenth and Fifteenth Amendments, 1864–65 and 1869

Each house's debate on the joint resolutions proposing the Thirteenth
Amendment (S. No. 16) and the Fifteenth (H. R. No. 402, S. R. No. 8),
imported by `importers/globe.py` from the Congressional Globe (decision 57),
one work per house and session, with refs as for 1866:

| Work | Prefix | Days |
|---|---|---|
| `texts/senate-thirteenth-amendment-1864.json` | `Senate1864` | February 17 – April 8, 1864 |
| `texts/house-thirteenth-amendment-1864.json` | `House1864` | May 31 – June 28, 1864 |
| `texts/house-thirteenth-amendment-1865.json` | `House1865` | January 6 – 31, 1865 |
| `texts/house-fifteenth-amendment-1869.json` | `House1869` | January 11 – February 25, 1869 |
| `texts/senate-fifteenth-amendment-1869.json` | `Senate1869` | January 21 – February 26, 1869 |

- `House1864.May31`, `House1864.May31b`, …: one division per item, named by
  its date; `House1864.May31.{paragraph}` its paragraphs.
- An item printed without a heading of its own (the Senate's sitting of
  January 30, 1869, where the joint resolution is taken up inside an item on
  other business) has no `title`; it begins at the paragraph that takes the
  joint resolution up.
- Headings inside a speech ("LOYALTY.", in Yeaman's speech of January 9,
  1865) are paragraphs of the item, numbered with the rest.

### The Eleventh and Twelfth Amendments, 1794 and 1802–03

Each house's proceedings on the resolutions proposing the Eleventh
Amendment (1794) and the Twelfth (1802, and 1803), imported by
`importers/annals.py` from the Annals of Congress, volumes 4, 11 and 13
(decision 60), one work per house and Congress, with refs as for 1789:

| Work | Prefix | Days |
|---|---|---|
| `texts/senate-eleventh-amendment-1794.json` | `Senate1794` | January 2 – March 12, 1794 |
| `texts/house-eleventh-amendment-1794.json` | `House1794` | January 15 – March 12, 1794 |
| `texts/senate-twelfth-amendment-1802.json` | `Senate1802` | April 12 – May 3, 1802 |
| `texts/house-twelfth-amendment-1802.json` | `House1802` | February 19 – May 1, 1802 |
| `texts/senate-twelfth-amendment-1803.json` | `Senate1803` | October 21 – December 16, 1803 |
| `texts/house-twelfth-amendment-1803.json` | `House1803` | October 17 – December 12, 1803 |

- `Senate1803.Oct22`, `Senate1803.Oct22.{paragraph}`: one division per item,
  named by its date; a second item of the same day takes a letter
  (`Senate1802.May3b`, `House1803.Oct27b`). Each passage records the printed
  columns it is on (`columns`).
- An item printed under the subject's heading ("AMENDMENT TO THE
  CONSTITUTION.") has that heading as its `title`; its paragraphs are
  numbered from 1 after it.
- An item printed without a heading (all of the Senate's proceedings of 1794
  and 1802, which the Annals print as a journal, and the paragraphs in which
  a house received, read, referred or postponed the resolution) has no
  `title`; its paragraphs are numbered from the one that takes the
  resolution up to the last before the house turns to other business.

### The Sixteenth to Nineteenth Amendments, 1909–1919

Each house's proceedings on the joint resolutions proposing the Sixteenth
to Nineteenth Amendments, imported by `importers/record.py` from the bound
Congressional Record (decision 61), one work per house and session, named
by the year the session met in; a second session that met in the same year
takes the letter `b` (the 65th Congress's second session, December 1917):

| Work | Prefix | Days |
|---|---|---|
| `texts/senate-sixteenth-amendment-1909.json` | `Senate1909` | July 3 – 5, 1909 |
| `texts/house-sixteenth-amendment-1909.json` | `House1909` | July 12, 1909 |
| `texts/house-seventeenth-amendment-1911.json` | `House1911` | April 13 – July 15, 1911 |
| `texts/senate-seventeenth-amendment-1911.json` | `Senate1911` | April 17 – July 14, 1911 |
| `texts/senate-seventeenth-amendment-1912.json` | `Senate1912` | April 17 – 23, 1912 |
| `texts/house-seventeenth-amendment-1912.json` | `House1912` | April 26 – May 13, 1912 |
| `texts/senate-eighteenth-amendment-1917.json` | `Senate1917` | July 9 – August 1, 1917 |
| `texts/house-eighteenth-amendment-1917b.json` | `House1917b` | December 15 – 17, 1917 |
| `texts/senate-eighteenth-amendment-1917b.json` | `Senate1917b` | December 18, 1917 |
| `texts/house-nineteenth-amendment-1919.json` | `House1919` | May 21, 1919 |
| `texts/senate-nineteenth-amendment-1919.json` | `Senate1919` | May 23 – June 4, 1919 |

None of these prefixes is used by another work (`House1789`, `House1794`,
`Senate1794`, `House1802`, `Senate1802`, `House1803`, `Senate1803`,
`House1864`, `Senate1864`, `House1865`, `House1866`, `Senate1866`,
`House1869`, `Senate1869`).

- `Senate1909.Jul5`, `Senate1909.Jul5b`, …: one division per item, named by
  its date; a second item of the same day takes a letter.
  `Senate1909.Jul5.{paragraph}` its paragraphs, numbered from 1 after the
  heading; each records the printed pages it is on (`pages`) and its pages
  in govinfo's PDF of the day (`scan.leaves`) and in the microfilm
  (`scan.microfilm.leaves`).
- The item's printed heading ("TAXES ON INCOMES.") is the division's
  `title`. An item in which a house took the joint resolution up inside an
  item on other business (May 22, 25 and 26, 1911) or under a heading OCR
  did not read (June 3, 1919) has no `title`; it begins at the paragraph
  that takes the resolution up.
- Headings of the sections of a speech, roll calls, and the titles,
  places, dates and signatures of documents printed in the debate are
  paragraphs of the item, numbered with the rest.

### The Twentieth to Twenty-sixth Amendments, 1932–1971

The same importer and scheme (decision 62), one work per house and
session:

| Work | Prefix | Days |
|---|---|---|
| `texts/senate-twentieth-amendment-1932.json` | `Senate1932` | January 6 – March 2, 1932 |
| `texts/house-twentieth-amendment-1932.json` | `House1932` | February 12 – March 1, 1932 |
| `texts/senate-twenty-first-amendment-1933.json` | `Senate1933` | February 13 – 16, 1933 |
| `texts/house-twenty-first-amendment-1933.json` | `House1933` | February 20, 1933 |
| `texts/house-twenty-second-amendment-1947.json` | `House1947` | February 6 – March 21, 1947 |
| `texts/senate-twenty-second-amendment-1947.json` | `Senate1947` | March 3 – 12, 1947 |
| `texts/senate-twenty-third-amendment-1960.json` | `Senate1960` | January 26 – June 16, 1960 |
| `texts/house-twenty-third-amendment-1960.json` | `House1960` | June 14, 1960 |
| `texts/senate-twenty-fourth-amendment-1962.json` | `Senate1962` | March 14 – 27, 1962 |
| `texts/house-twenty-fourth-amendment-1962.json` | `House1962` | August 27, 1962 |
| `texts/senate-twenty-fifth-amendment-1965.json` | `Senate1965` | February 18 – July 6, 1965 |
| `texts/house-twenty-fifth-amendment-1965.json` | `House1965` | April 13 – June 30, 1965 |
| `texts/senate-twenty-sixth-amendment-1971.json` | `Senate1971` | March 9 – 10, 1971 |
| `texts/house-twenty-sixth-amendment-1971.json` | `House1971` | March 23, 1971 |

No other work uses these prefixes. Headings printed inside an item (a quorum
call, an amendment offered, a conference report, the sections of a speech)
are paragraphs of the item, as above.

## Retired refs

Once the site has launched, a correction that joins two passages wrongly
imported as one (a paragraph split at a page break, for example) never
renumbers: the second ref is **retired**, never reused, and the passages
after it keep their numbers. Each needs an erratum and a decision by the
project owner.

- The importer's series configuration names it (`"retired": {"X.4.5":
  "X.4.4"}` with a `retired_reason`), and the work's file lists it:
  `"retired": [{"ref", "merged_into", "reason"}]`.
- It stays in `refs.lock`. `make verify` accepts it there only while the
  passage it was merged into exists, and fails if the ref is used again.
- Links may not point at it.
- Its URL still works: the site keeps an anchor with its id inside the
  passage it was merged into.

Before launch, the project owner may instead approve renumbering, and the
refs that no longer exist are removed from `refs.lock` (decisions 36 and
37).

## Cases (`cases/{cluster_id}.json`)

- `Case.{courtlistener_cluster_id}`: a whole case (`Case.105221`, *Brown v.
  Board of Education*). The cluster ID is CourtListener's, the key CommonHall
  also uses. Links to a case as a whole (`interprets`, `overrules`) use this
  ref; it exists even when the case has no passages.
- `Case.{cluster_id}.syllabus.{n}`: the *n*th paragraph of the syllabus as
  printed in the United States Reports, counting from 1 (`Case.105221.syllabus.1`).
  A paragraph is what the printed page sets as one: an indented or outdented
  first line, or a line after a short one. Each records the printed page it
  starts on (`page`).
- `Case.{cluster_id}.{paragraph}`: reserved for paragraphs of the majority
  opinion, which are not imported (decision 49).

A case whose syllabus could not be read reliably has no syllabus refs yet;
when the syllabus is imported later, its refs are new, not renumbered.
