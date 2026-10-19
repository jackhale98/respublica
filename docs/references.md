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
