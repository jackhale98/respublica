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

## Sources of the Declaration

Two works the Declaration's language draws on (decision 67). The library
records that, and says nothing more about their influence. Both are taken
from the **Text Creation Partnership** (TCP; the University of Michigan and
Oxford), which keyed early printed books by hand from page images and
released the texts under CC0 as TEI P5 XML. The TCP text is the text, not
OCR (`importers/tcp.py`):

- **What the TCP marks is kept as it marks it.** Words broken at a line end
  are joined (as the OCR importers do); abbreviations the TCP expands (the
  Latin "-que" in Locke's quotations from Barclay) are given expanded, as its
  `<ex>`; letters the keyers could not read are "•" and a stop they could
  not make out "▪", as the TCP displays them, and every such word is marked
  uncertain, never filled in. Superscripts are plain letters ("1o.").
  Italics are not kept.
- **The long s.** The TCP's keying rules give the long s as a round s, so
  these texts have a modern "s" where the printings have "ſ". Nothing else
  is modernized: "possitively", "encrease", "Iudge" are as the TCP keyed
  them.
- **The check against scans.** Each word is compared with the OCR of
  Internet Archive scans of the same printing, as the Anti-Federalist
  Library's text was compared with the scans (decision 55), the roles turned
  round: the TCP is the text, the scans only a check. Words are compared by
  their letters with the long s set aside ("s", "f" and "l" alike, which is
  how OCR reads the long s; "i"/"j" and "u"/"v" alike too, since OCR
  dictionaries regularize "Iudge"). Where no scan reads a word alike and a
  scan reads another real word there (a word of the clean texts or of the
  TCP text, not a piece of the TCP's word and not one of OCR's usual
  confusions in this type, "be" for "he", "the" for "she", "fall" for
  "shall"), or has no word there in a passage it otherwise reads cleanly, or
  has a word of the clean texts more, the word is marked uncertain with the
  TCP's reading (`tcp`) and the scans'; the TCP's word stays in the text. A
  scan's reading that is not a word is OCR noise. What the check cannot see:
  a slip that gives a word the check does not know, and the long s against
  "f" or "l" ("fame" for "same"), errata 131 and 133.
- **Scans.** Each passage records the scan whose page images it links to
  (`scan.leaves`), found where its words were read in that scan.

### Common Sense

- **Printing:** [Thomas Paine], *Common Sense; Addressed to the Inhabitants
  of America* (Philadelphia: Printed, and Sold, by R. Bell, in
  Third-Street, 1776), the first edition, advertised January 9, 1776
  ([4], 79, [1] p.). Published anonymously; the TCP's record attributes it
  to Paine (from the *Dictionary of American Biography*).
- **Text:** Evans-TCP N11839 (Evans 14954), keyed from the Readex microprint
  of this printing (`tcp-n11839`, pinned to a commit of
  github.com/textcreationpartnership/N11839).
- **Check:** the John Carter Brown Library's copy of the first edition, first
  issue (p. 63, line 13 ends "pedling politi-"), on the Internet Archive
  (`commonsenseaddre00pain_2`, its DjVu XML, `ia-decl-paine-1776-jcb-xml`);
  its page images are the passages'. No other scan of this printing was
  found: Bell's second edition (John Adams's copy, `commonsenseaddre00pain`)
  and third edition (`case_e211_.p128`, `commonsensewithw00pain_0`) were
  reset and revised ("would urge him from his work" in the first edition is
  "to quit his work" in both), and Bradford's enlarged edition of February
  14, 1776, and the American and British reprints are other texts, so none
  is used. The scan is a photograph of the bound copy: words outside the
  block of text (the marbled edges) are left out, and its lines are rebuilt
  from where the words stand (`tcp.printed_lines`).
- **What is imported:** the Introduction and the four parts, with Paine's
  two notes; not the title page, the running title over part I, "FINIS." or
  the bookseller's advertisement. Refs: `docs/references.md`.
- **Result:** 140 passages (2 notes), about 15,800 words, 61 marked
  uncertain (about 4 per thousand). The scan was lined up with 92% of the
  words, and read 89% with the same letters.
- Importer: `importers/paine.py`.

### Locke, the Second Treatise of Government

- **Printing:** [John Locke], *Two Treatises of Government* (London: Printed
  for Awnsham Churchill, 1690), the first edition (271 [i.e. 467] p.), Book
  II: "An Essay Concerning the True Original, Extent and End of Civil
  Government" (the TCP's heading reads "Oringinal"). Locke was English; the
  work is in the library as a source the Declaration's language draws on.
  Published anonymously; the TCP's record attributes it to Locke.
- **Why this printing:** the TCP's transcription of it exists (the owner's
  choice of method, decision 67), and it is the first edition. Later
  editions revise the text: the 1764 edition Thomas Hollis prepared from
  Locke's last corrections (three scans of it are on the Internet Archive)
  has a § 21, "To avoid this state of war …", which this printing lacks.
- **Text:** EEBO-TCP A48901 (Wing L2766), keyed from the Early English Books
  images of the Union Theological Seminary Library's copy (`tcp-a48901`,
  pinned to a commit of github.com/textcreationpartnership/A48901). Only
  Book II is imported.
- **Check:** two copies of this printing on the Internet Archive: the
  University of Illinois's (`twotreatisesofgo00lock_1`, DjVu XML,
  `ia-decl-locke-1690-illinois-xml`; its page images are the passages') and
  a microfilm in the Early English Books series
  (`bim_early-english-books-1641-1700_two-treatises-of-governm_locke-john_1690`,
  OCR text, `ia-decl-locke-1690-microfilm-txt`). The Illinois scan was lined
  up with 95% of the words and the microfilm with 80%; 2% were lined up with
  neither.
- **What is imported:** the nineteen chapters, Locke's numbered sections
  §§ 1–243 (no § 21), and the nine notes printed in the margin (Hooker's
  words); not Book II's headings, "FINIS." or Book I. A section of several
  paragraphs is one passage. Refs: `docs/references.md`.
- **Result:** 251 passages (242 sections, 9 notes), about 53,500 words, 162
  marked uncertain (about 3 per thousand), among them the words with
  letters the TCP could not read.
- Importer: `importers/locke.py`.

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

## The road to independence, 1774–1776

Seven works on the way to the Declaration (decision 66), imported by
`importers/independence.py` and shown together at `/independence/`. Where
the Text Creation Partnership has keyed a printing of the time (Evans-TCP,
American imprints to 1800; released under CC0), its transcription is the
text (`importers/tcp.py`); where it has not, the text is read from scans by
OCR consensus (`docs/ocr.md`). The 1904–06 Library of Congress edition of
the Journals is not in Evans, and no Evans-TCP text prints the 1774 resolves,
the May 1776 resolutions, the Lee Resolution or the Journals of July 1776;
Jefferson's draft was first printed by Ford in 1893.

| Work | Printing | Source | Imported |
|---|---|---|---|
| The Declaration and Resolves (October 14, 1774) | *Journals of the Continental Congress, 1774–1789*, ed. Worthington C. Ford, vol. 1 (Washington, 1904), pp. 63–73 | `journalsofcontin01unit` (DjVu XML); checked against `journalscontine08statgoog` and `journals-of-the-continental-congress-1774-1789-vol-1-1774` | The day's entry and the resolutions as adopted, which the Journals print in the right-hand column beside John Sullivan's draft (left out); the editor's note on the day's debates and his note that the paragraph on non-importation "was struck out" |
| A Declaration … Setting forth the Causes and Necessity of their Taking up Arms (July 6, 1775) | the broadside sold at the printing-office in Portsmouth, N.H. [Daniel Fowle], 1775 (Evans 14550) | Evans-TCP N11512 (TEI) | The whole text, from the heading to the closing attestation; the woodcut view of Boston and its caption are left out. No scan of this printing was found, so the transcription is not cross-checked; its illegible letters and spans stay as the TCP marks them |
| The resolution of May 10, 1776 and its preamble of May 15 | Journals, vol. 4 (1906), pp. 342, 357–358 | `journalsofcontin04unit` (DjVu XML); checked against `journals-of-the-continental-congress-1774-1789-vol-4-jan-1-jun-4-1776`, `journalscontine00statgoog` and `journalscontine05statgoog` | The day's entries on the resolution and the preamble (May 10: from the report of the committee of the whole to the committee named to draft a preamble; May 15: from the preamble's consideration to the order to publish it), with the editor's note on the preamble |
| The Lee Resolution (June 7, 1776) | Journals, vol. 5 (1906), pp. 425–426 | `journalscontinen05unit` (DjVu XML); checked against `journalsofcontin05unit`, `journalscontine06conggoog` (which lacks these pages) and `journals-of-the-continental-congress-1774-1789-vol-5-june-5-oct-8-1776` | From "Certain resolutions respecting independency" to their referral to the next day, with the editor's note on Lee's manuscript |
| The Virginia Declaration of Rights (June 12, 1776) | *The Articles of Confederation; the Declaration of Rights; the Constitution of the Commonwealth …* (Richmond: Dixon and Holt, [1784 or 1785]), pp. 12–14 (Evans 18818) | Evans-TCP N15245 (TEI); checked against the OCR of the Internet Archive's scan of the same printing, `bim_eighteenth-century_the-articles-of-confeder_virginia-constitution_1784` | The heading and the sixteen articles |
| Jefferson's draft preamble for the Virginia constitution (June 1776) | Paul Leicester Ford, ed., *The Writings of Thomas Jefferson*, vol. 2 (New York: Putnam, 1893), pp. 7–13 | `writingsofthom02jeff` (DjVu XML); checked against `writingsthomasj01fordgoog` and `writingsthomasj09unkngoog` | The fair copy, from the bill's title to the end of the clause deposing the king, as Ford prints it in the right-hand column beside the first draft (left out), with Ford's note on the manuscripts |
| The proceedings on independence (July 2 and 4, 1776) | Journals, vol. 5 (1906), pp. 506–507, 510–516 | as for the Lee Resolution | July 2: from the resolution of independence to the order to consider the declaration the next day; July 4: from the committee of the whole's report to the orders for printing and proclaiming the Declaration, with its text, the signers and the editor's notes on them |

**What the importer does not change.** The Journals' editorial marks are
kept as OCR reads them: words the editor printed between double bars
(entries of the rough journal) and his bracketed names
("Mr. J[ohn] Adams"). Ford prints Jefferson's deletions struck through, his
own insertions in brackets and his conjectures in italics; OCR reads struck
words as words, so the fair copy's text holds Jefferson's deletions without
a mark (erratum 113). The TCP's transcriptions keep the printings' spelling,
the long s ("ſ", where the TCP keys it) and their punctuation; letters the keyers could not read
are their placeholders (`•`, `〈…〉`, `▪`), marked uncertain and never filled
in (decision 66). Their TEI markup (quotations, highlighting) is removed
(rule 2 above), and a word the TEI marks as broken at a line's end
(`char:EOLhyphen`) is rejoined without its hyphen, as the OCR importers
rejoin a hyphenated word; in the OCR, a line-end hyphen read apart from its
word ("independ - ence.") is rejoined only where the whole is a word of the
clean texts.

**Not imported.** The other column on the parallel pages (Sullivan's draft
of the resolves; Jefferson's first draft); the Journals' other business on
the same days; the 1775 declaration's drafts by Jefferson and Dickinson,
which the Journals print beside its final form (vol. 2, pp. 128–157), since
the text comes from the broadside; the Virginia printing's other contents
(the Articles of Confederation, the state constitution, the treaty).

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
  from the newspaper printings are not yet documented (for McLean, see
  below).
- **Footnotes.** 66 footnotes, as `Federalist.{paper}.fn{n}`. Footnote markers
  such as `[1]` stay in the paragraph text where the edition prints them.
- **Paragraphing, and the 1788 McLean edition** (decision 70). The e-text
  lost most of its paragraph breaks in Nos. 40–59: No. 51 was one paragraph
  of 1,911 words, No. 59 one, No. 40 two. The breaks there are restored from
  *The Federalist* (New York: J. and A. M'Lean, 1788), 2 vols., in the Text
  Creation Partnership's typed transcription (Evans-TCP N16444, Evans 21127;
  source `tcp-evans-n16444`, CC0). Only break positions are taken from it:
  - The importer aligns each paper's words with McLean's (difflib on
    normalized words: case, punctuation and the long s ignored) and splits an
    e-text paragraph before the word that corresponds to the first word of a
    McLean paragraph, when the words on both sides of it align (at least three
    of the six on each side, two of them the same word). The words, spelling
    and punctuation stay the e-text's; only the space at the break goes.
  - In two places the e-text runs a numbered clause on after a colon with no
    space ("powers:1.", "States:1."); the break falls between the colon and the
    figure, and no character is lost.
  - No paragraph is joined. The e-text's own breaks stay, including 56 in this
    stretch that McLean does not have, many of them mid-sentence
    (`docs/errata.md`, erratum 200).
  - Three McLean breaks are not made because the editions word the passage
    differently there (Nos. 44 and 56; erratum 201).

  | No. | Paragraphs before | After | McLean |
  |---|---|---|---|
  | 40 | 2 | 19 | 19 |
  | 41 | 5 | 27 | 25 |
  | 42 | 6 | 23 | 21 |
  | 43 | 6 | 35 | 31 |
  | 44 | 6 | 29 | 28 |
  | 45 | 7 | 17 | 11 |
  | 46 | 8 | 18 | 11 |
  | 47 | 7 | 25 | 21 |
  | 48 | 6 | 19 | 16 |
  | 49 | 4 | 13 | 11 |
  | 50 | 6 | 12 | 11 |
  | 51 | 1 | 10 | 10 |
  | 52 | 5 | 13 | 9 |
  | 53 | 3 | 12 | 11 |
  | 54 | 4 | 14 | 11 |
  | 55 | 8 | 15 | 9 |
  | 56 | 3 | 9 | 9 |
  | 57 | 8 | 27 | 21 |
  | 58 | 2 | 16 | 15 |
  | 59 | 1 | 10 | 10 |
  | **40–59** | **98** | **363** | **310** |

  265 breaks were added; the work has 1,269 body paragraphs (1,004 before).
  Outside Nos. 40–59 the e-text's paragraphs match McLean's almost
  everywhere, and the few differences go both ways (the e-text has more
  paragraphs than McLean in Nos. 6, 29, 38, 39, 62, 66 and 84). The only
  McLean breaks that the alignment would add there are in No. 3 (where the
  e-text begins paragraphs with "Because", a revision of Jay's text), No. 8
  (¶9), No. 70 (¶23; the e-text's second version of No. 70 lacks it too) and
  No. 81 (¶1, a quoted clause set apart, and two in ¶13). These look like the
  editions' own paragraphing, not lost breaks, and are left alone.
- **McLean as evidence.** McLean is not the e-text's source: about 12 words in
  1,000 differ, most of them spelling ("defence", "shewn") but some of them
  revisions (acts/votes, always/commonly, deciding/determining). Its readings bear on errata 6–9
  and are recorded there; no wording is taken from it.
- Importer: `importers/federalist.py`.

## The ratification debate

Imported by `importers/ratification.py` (phase 5) from four public-domain
compilations, read from the Internet Archive's scans, and (Brutus V–XVI) from
the original newspaper; Patrick Henry's speeches by `importers/elliot.py`
from Elliot's *Debates*, and the debates of the state ratifying conventions
by `importers/conventions.py` from the Library of Congress's typed
transcription of Elliot (see "The state ratifying conventions" below). Modern compilations (Storing, 1981; Borden, 1965)
are not candidates because of copyright.

| Book | Scans used | Imported |
|---|---|---|
| Paul Leicester Ford, ed., *Essays on the Constitution of the United States* (Brooklyn, 1892) | layout and words: `essaysonconstitu00forduoft` (DjVu XML); checked against the OCR text of `EssaysOnTheConstitutionOfTheUnitedStates` and `essaysonconstit00fordgoog` | every section: Cassius, Agrippa, Gerry's replies to A Landholder, A Landholder, William Williams's letter, A Countryman, A Citizen of New Haven, Cato, Caesar, Sydney, Cursory Remarks, Caution, A Friend to the Constitution, Luther Martin, A Plain Dealer, Hugh Williamson's Remarks, A Steady and Open Republican |
| Paul Leicester Ford, ed., *Pamphlets on the Constitution of the United States* (Brooklyn, 1888) | `cu31924020874099` (DjVu XML); checked against `pamphletsoncons00fordgoog` | Letters from the Federal Farmer (I–V) so far |
| John Bach McMaster and Frederick D. Stone, eds., *Pennsylvania and the Federal Constitution, 1787–1788* (Lancaster, 1888) | `cu31924030454387` (DjVu XML); checked against `pennsylvaniafede00hist` | Centinel I–XXIV (chapter VII); the Address and Reasons of Dissent of the Minority of the Convention of Pennsylvania (chapter VI, pp. 454–482: from the title to the twenty-one signatures; the editors' introduction before it and the yeas and nays of the final vote after it, printed in columns OCR reads out of order, are not imported) |
| *Debates and Proceedings in the Convention of the Commonwealth of Massachusetts, held in the year 1788* (Boston, 1856) | `debatesproceedin00mass` (DjVu XML); checked against `debatesproceedin00massrich`, `debatesandproce03convgoog` and `cu31924032635546` | Brutus I–IV ("Spirit of the Press", pp. 366–398) |
| *The New-York Journal, and Weekly Register* (New York: Thomas Greenleaf), December 13, 1787 to April 10, 1788 | the Library of Congress's scans in Chronicling America (LCCN sn83030566): each page's ALTO XML (words, boxes, confidence), pages 2 and 3 of thirteen issues; one scan only | Brutus V–X and XII–XVI, as first printed (XII and XIV in two instalments each) |
| Jonathan Elliot, ed., *The Debates in the Several State Conventions on the Adoption of the Federal Constitution*, vol. 3 (2nd ed., standard pagination; Philadelphia: Lippincott, 1907 printing) | `debatesinseveral03elliuoft` (DjVu XML); checked against `cu31924024573820` (1876), `debatesinsevera08convgoog` (1861) and `debatesinsevera12elligoog` (1836), all of the same pagination | Patrick Henry's speeches in the Virginia convention, June 5–25, 1788 (the twenty-four the Anti-Federalist Library prints, pp. 43–652) |
| Elliot, *Debates*, vols. 2–4 (2nd ed., Washington, 1836): the Library of Congress's typed transcription (`lled002`–`lled004`, 1997) | the text is the transcription, not OCR; checked against `debatesinseveral02elliuoft`, `debatesinseveral03elliuoft` (with the three other vol. 3 scans above) and `debatesinseveral04elliuoft` (1907 printing, the same pagination) | the state ratifying conventions: Massachusetts, Connecticut, New Hampshire, New York, Pennsylvania, Maryland (vol. 2, pp. 1–556), Virginia (vol. 3, pp. 1–663), North Carolina and South Carolina (vol. 4, pp. 1–341) |

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

**The Library of Congress's Elliot as Henry's tie-breaker** (decision 68).
The Library of Congress's typed transcription of vol. 3 (the standard
pagination; see "The state ratifying conventions") is a strict tie-breaker
before the Anti-Federalist Library: where it lines up with a word, its
reading is the one used to choose among the scans' readings (never to add
one), and the Anti-Federalist Library's only where it does not line up. A
settled word it reads otherwise is left as the scans read it (marked
uncertain where fewer than two scans read it so or it is not a known word,
as `strict` always did); every such word is listed in erratum 150, since
both sides have errors there: unmarked OCR slips in our text ("tning",
"agam") and the transcription's keying slips ("fight" for "right",
"cheek" for "check").

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

## The state ratifying conventions

Imported by `importers/conventions.py` (decision 68), nine works, one per
convention as Elliot prints it, from Jonathan Elliot, ed., *The Debates in
the Several State Conventions on the Adoption of the Federal Constitution*
(2nd ed., Washington, 1836; the standard pagination the Lippincott
printings keep):

| Work | Elliot | Days |
|---|---|---|
| `massachusetts-convention-1788` | vol. 2, pp. 1–183 | 24, January 9 – February 7, 1788 |
| `connecticut-convention-1788` | vol. 2, pp. 185–202 ("Fragment of the Debates") | 3, January 4–9, 1788 |
| `new-hampshire-convention-1788` | vol. 2, pp. 203–204 (one speech, undated) | a single piece |
| `new-york-convention-1788` | vol. 2, pp. 205–414 | 24, June 17 – July 26, 1788 |
| `pennsylvania-convention-1787` | vol. 2, pp. 415–546 | 14, November 20 – December 11, 1787, and the Harrisburg meeting of September 3, 1788 |
| `maryland-convention-1788` | vol. 2, pp. 547–556 ("A Fragment of Facts", the minority's address of April 21, 1788) | a single piece |
| `virginia-convention-1788` | vol. 3, pp. 1–663 | 23, June 2–27, 1788 |
| `north-carolina-convention-1788` | vol. 4, pp. 1–252 | 12, July 21 – August 2, 1788 |
| `south-carolina-convention-1788` | vol. 4, pp. 253–341 (the House of Representatives, then the convention) | 10, January 16–19 and May 12–23, 1788 |

**The text** is the Library of Congress's typed transcription of each
volume ("A Century of Lawmaking for a New Nation", American Memory, 1997;
`lled002`–`lled004` at tile.loc.gov), keyed by hand to "an accuracy rate of
99.95 percent or greater", as XML with the printed page numbers. It is in
the public domain (the file's header: "Publication exempt from copyright
protection"; the collection's rights page: "in the public domain and ...
free to use and reuse"). `importers/amem.py` reads it. No word is changed;
only the file's own layout is undone: the line breaks its pretty-printer put
around italics ("Thursday\n, January"), the printer's signature marks keyed
at the foot of pages ("42", "4 3"), the library stamp on the first page,
and three words keyed broken across a page ("in-" and "ference"), which are
rejoined. A table is its cells in the file's order. The transcription has
no marks for illegible words or gaps; it prints the reporter's bracketed
remarks in angle brackets ("〈Here Mr. Madison spoke too low to be
understood.〉") in a few places, kept as it has them.

**Division.** Each work runs from the paragraph after the section's
heading to the last before the next section, and is divided by day at the
paragraph that begins the day as Elliot prints it ("Thursday, January
10.—The committee …", "Tuesday, June 3, 1788."). The importer lists every
day and the words that begin it, checks each weekday against the calendar,
and stops if it finds another dateline. Where the day's heading has another
date than the day's, the ref follows the weekday and the order of the days,
and the day carries a note: Pennsylvania's "Friday, November 25" (the 23d;
the scan reads "23", so the slip is the transcription's) and "Wednesday,
October 28" (November 28; the scan prints it so), New York's "1738" and
"1783" (1788; the transcription's slips), and Virginia's second "Wednesday,
June 18" (June 19; erratum 60). Every printed paragraph is a passage,
datelines, headings ("AYES.") and each line of a vote list too, with the
speaker's name as printed. Elliot's footnotes follow their paragraph as
notes. A heading over a day (South Carolina's "DEBATES IN CONVENTION.",
Connecticut's "Collected from contemporary publications …") is that day's
first paragraph.

**The check against the scans.** Every word is lined up with the Internet
Archive's scan of the 1907 Lippincott printing of the same volume (the
University of Toronto's copies; for Virginia, also the 1876, 1861 and 1836
scans Henry's speeches are read from). First the pagination: the first
words of every paragraph must be on the scan's page of the number the
transcription gives (4,109 of 4,116 paragraphs; in the rest the scan misread
the first words). Then each word: where most of the scans read another
word than the transcription (marks and capitals aside), and the scans'
word is a known word (the clean texts' vocabulary and words the
transcription and a scan read alike elsewhere), or a number, and not one of
the shared OCR confusions ("rn" for "m"), the transcription's word is kept
and marked uncertain, with its reading as `primary` (shown on `/errata/` as
"Library of Congress transcription") and each scan's. Where the scans read
something that is not a word, it is taken for OCR noise and not marked;
where they split two against two, nothing is marked. So a keying slip that
gives a real word the scans also misread, or a scan reading the check does
not know, is missed (erratum 151).

**Not imported:** vol. 1 (the Journal of the Federal Convention, Luther
Martin's letter, Yates's minutes) and the rest of vol. 4 (the "Opinions" of
Congress, 1789–1836, and the Virginia and Kentucky resolutions).

## The ratification debate: not yet imported

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

**The Sixteenth to Nineteenth Amendments, 1909–1919**
(`importers/record.py`, decision 61) are imported from the bound edition of
the *Congressional Record: Containing the Proceedings and Debates* of each
Congress (Washington: Government Printing Office): volume 44 (61st
Congress, 1st session, 1909), 47 and 48 (62nd Congress, 1st and 2d
sessions, 1911–12), 55 and 56 (65th Congress, 1st and 2d sessions,
1917–18) and 58 (66th Congress, 1st session, 1919). Eleven works, one per
house and session:

| Amendment | Joint resolution | Works (`texts/…`) | Days |
|---|---|---|---|
| Sixteenth | S. J. Res. 40 | `senate-sixteenth-amendment-1909`, `house-sixteenth-amendment-1909` | Senate July 3, 5; House July 12, 1909 |
| Seventeenth | H. J. Res. 39 | `house-seventeenth-amendment-1911`, `senate-seventeenth-amendment-1911`, `senate-seventeenth-amendment-1912`, `house-seventeenth-amendment-1912` | House April 13 – July 15, 1911 (5 days); Senate April 17 – July 14, 1911 (26 days); Senate April 17, 23, 1912; House April 26, May 13, 1912 |
| Eighteenth | S. J. Res. 17 | `senate-eighteenth-amendment-1917`, `house-eighteenth-amendment-1917b`, `senate-eighteenth-amendment-1917b` | Senate July 9 – August 1, 1917 (8 days); House December 15, 17; Senate December 18, 1917 |
| Nineteenth | H. J. Res. 1 | `house-nineteenth-amendment-1919`, `senate-nineteenth-amendment-1919` | House May 21; Senate May 23 – June 4, 1919 (6 days) |

**What is imported** is fixed by the print and by the Record's own index.
The days are those the volume's History of Bills and Resolutions lists for
the joint resolution, with the pages it gives (`DAYS`). On each, every item
of the house's proceedings headed with the resolution's subject ("Taxes on
Incomes", "Election of Senators by Direct Vote", "National Prohibition",
"Woman Suffrage", and their variants, `Amendment.headings`) whose heading
or first paragraphs name the joint resolution, from its heading to the next
item's heading or the end of the house's day, procedural items included (a
report, a motion to take it up, a request to fix the time of a vote). Where
the index lists a page on which the house took the resolution up under
another heading, that item is included too (`EXTRA_HEADINGS`: the referral
and the debate on which committee should have it, April 17, 1911; the
minority's views presented, May 22, 1911; the debate on the Journal's record
of the Vice President's vote, June 13, 1911; and others), and where it was
laid before the Senate inside an item on other business and laid aside at
once, those paragraphs are an item of their own, without a heading
(`INSIDE`: May 22, 25 and 26, 1911; Watson's motion of June 3, 1919, under a
heading OCR did not read). The importer stops if a page the index gives is
in no item imported, and if an item runs on more than a page past the last
page the index gives for the day; the few exceptions are listed with the
reason (`ELSEWHERE`: the index's range runs over other business on June
13, 1911, and July 30, 1917; `RUNS_TO`: Newlands spoke on the trusts while
the joint resolution was before the Senate, May 16, 1911). Speeches printed
in the Appendix by leave are not imported. The Twenty-seventh Amendment is
not imported from the Record: it was proposed in 1789 (the House's debate is
`House1789`), and the concurrent resolutions of May 1992 that declared it
ratified are not debates on proposing an amendment.

**Scans.** govinfo.gov (the Government Publishing Office) serves the bound
edition as 150 ppi scans with an OCR text layer, one PDF per house per day
(`govinfo-crecb-{granule}`), and each part's MODS record
(`govinfo-crecb-{part}-mods`), which gives each day's printed pages. Words
and layout come from the text layer (`tools/pdf.py`, `pdf_words`), read in
two columns as the Globe is read in three (running heads, sheet signatures
"XLIV—277" and specks left out; a page set in one column read as one). They
are checked against the Internet Archive's OCR of a microfilm of the same
bound part (`sim_congressional-record…`; its page-indexed OCR text, its
page index and the printed page number it read on each page:
`ia-record-{part}-text`, `-pageindex`, `-pages`), in runs of about 200
words. Each passage links to its page in govinfo's PDF; the errata page
shows the microfilm's page image, since govinfo serves none. All of these
files are kept out of git (`make fetch` restores them).

**Reading the page.** An item heading is a line set as a heading in
capitals before an item's opening (a speaker's name in capitals, a message,
the business taken up, a routine formula), as OCR reads them ("Tbe
VICE-PRESIDENT.", "1\Ir. CULLOM."). Not item headings: a speaker's words
("Mr. UNDERWOOD. I do."), the end of a paragraph set apart ("[Mr. /
CLAYTON]."), "By Mr. SMOOT:" in a list of bills, a roll call's lists, the
article of a joint resolution read to the house, the title of a document
printed in the debate (after its source in brackets, after a paragraph
ending in a colon, before a letter's place and date), a letter's signature,
and the headings of the sections a speech is printed in (when no item opens
after them; a few are listed, `SPEECH_HEADINGS`). The day begins at the
house's name and dateline (or the dateline alone, July 31, 1917), read
however OCR garbled them ("Fnmu, Ap1·il ~6, 1912.").

**Quality.** The text layer reads the 1909–1912 volumes about as well as
UNT reads the Globe; the 1917 volumes much worse. About 3–5% of words are
marked uncertain (2.9% in the Senate's 1909 debate, 3.5–5.3% for the
Seventeenth Amendment, 4.8% in the Senate's 1917 debate and 7.0% in the
House's, 3.7–4.2% in 1919); each is marked with both readings. Where the
OCR ran lines of two columns into each other, words of one paragraph can
stand in another (errata 100–102). Run `python -m tools.uncertain` for the
current counts.

**The Twentieth to Twenty-sixth Amendments, 1932–1971**
(`importers/record.py`, decision 62) are imported from the same bound
edition in the same way: volumes 75 and 76 (72nd Congress, 1932–33), 93
(80th, 1947), 106 (86th, 1960), 108 (87th, 1962), 111 (89th, 1965) and 117
(92nd, 1971). Fourteen works, one per house and session:

| Amendment | Joint resolution | Works (`texts/…`) | Days |
|---|---|---|---|
| Twentieth | S. J. Res. 14 | `senate-twentieth-amendment-1932`, `house-twentieth-amendment-1932` | Senate January 6, February 17, March 2; House February 12 – March 1, 1932 (6 days) |
| Twenty-first | S. J. Res. 211 | `senate-twenty-first-amendment-1933`, `house-twenty-first-amendment-1933` | Senate February 13–16; House February 20, 1933 |
| Twenty-second | H. J. Res. 27 | `house-twenty-second-amendment-1947`, `senate-twenty-second-amendment-1947` | House February 6, March 21; Senate March 3–12, 1947 (5 days) |
| Twenty-third | S. J. Res. 39 | `senate-twenty-third-amendment-1960`, `house-twenty-third-amendment-1960` | Senate January 26 – February 2 (5 days), June 16; House June 14, 1960 |
| Twenty-fourth | S. J. Res. 29 | `senate-twenty-fourth-amendment-1962`, `house-twenty-fourth-amendment-1962` | Senate March 14–27 (11 days); House August 27, 1962 |
| Twenty-fifth | S. J. Res. 1 | `senate-twenty-fifth-amendment-1965`, `house-twenty-fifth-amendment-1965` | Senate February 18 – July 6 (5 days); House April 13 – June 30, 1965 (4 days) |
| Twenty-sixth | S. J. Res. 7 | `senate-twenty-sixth-amendment-1971`, `house-twenty-sixth-amendment-1971` | Senate March 9–10; House March 23, 1971 |

Some resolutions were taken up under headings that do not name their
subject: S. J. Res. 29 was a bill to make Alexander Hamilton's house a
national monument, whose text the Senate replaced with the amendment ("The
Alexander Hamilton National Monument—Amendment to the Constitution Dealing
with Poll Taxes"); S. J. Res. 39 was first an amendment on filling
vacancies in the House. Where a house debated its own resolution and then
passed the other house's in its place (House, June 14, 1960, and March 23,
1971), the whole item is imported.

**What differs from 1909–19.** The later volumes set item headings in
capitals without a full stop, over one to three lines, often filling the
column; they print the sections of long speeches, inserted statements,
"QUORUM CALL", "AMENDMENT OFFERED BY MR. …" and similar headings inside a
debate; and from 1947 they are set in three columns with narrow gutters.
The importer therefore, for these volumes only (`Session.later`): splits a
text-layer line at a gutter where the baselines differ; takes a line in
capitals after a sentence's end for a heading, joins a heading's lines
(not a signature, a date or a speaker's line); lets a heading end in a year
("… BILL, 1948"); treats quorum calls, amendments offered, parliamentary
inquiries and conference reports as headings inside an item
(`LATER_INNER`); ends an item at a routine opening whose heading OCR lost
("By unanimous consent, the following routine business was transacted";
`LATER_ROUTINE`); begins the day where the house met ("The Senate met at
…"), since the masthead in display type is often not read; and splits a
page whose text layer runs lines across the gutters where equal columns
would be. Speeches printed in sections are listed by their pages
(`SPEECH_PAGES`), headings that begin another item without an opening read
after them by name (`OTHER_HEADINGS`). From 1947 the index gives the page
each day's debate begins on rather than its range, so `RUNS_TO` lists, for
each such day, the page the debate runs to (read off the page: the next
item's heading or the recess).

**Quality.** About 1,371,000 words, 18,700 (14 per thousand) marked uncertain:
the text layer of these volumes is much better than that of 1909–19. From
4.5 per thousand (the Senate, 1965) to 23 (both houses, 1947) and 47 (the
Senate, 1971, whose debate prints long tables: four in five of its marked
words are figures and leader dots). About 7,500 of the marked words are
figures, and about 11,000 have no microfilm reading (tables, roll calls,
and lines the two OCRs read in different orders). Lines of a heading can be
read apart from it (errata 104–105).

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
