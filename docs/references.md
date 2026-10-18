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
refs that no longer exist are removed from `refs.lock` (decision 36:
Cassius IV).

## Cases (planned)

`Case.{courtlistener_cluster_id}` for a whole case and
`Case.{cluster_id}.{paragraph}` for a paragraph of the majority opinion.
