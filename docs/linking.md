# Linking guide

How links are proposed. Every linker (agent or person) follows this; a human
reviews the results. Read `CLAUDE.md` first: links are proposals until a
person reviews them, quotes are copied by code, and no link characterizes
what a clause or case means.

## Tools

| Command | Use |
|---|---|
| `python3 -m tools.show Federalist.10` | Print every passage of a paper (or any ref) with its ref. |
| `python3 -m tools.show Constitution.1.8` | Print the clauses under a ref. |
| `python3 -m tools.candidates --paper 10` | Code-found hints for one paper: word overlaps with clauses, and "section … of the … article" wording. Hints only. |
| `python3 -m tools.links propose --batch B --decisions FILE --run R` | Turn a decisions file into `suggested` links in `links/proposed/B.jsonl`. |
| `python3 -m tools.links sample --n 20` | Print a spot-check sheet for a human. |
| `python3 -m tools.links review --reviewer NAME` | **Humans only.** Mark links reviewed or rejected. |
| `python3 -m tools.links apply --reviewer LOGIN --text FILE` | **A human's decisions** from a review issue; run by the review workflow, never by an agent. |

A decisions file is a JSON list:

```json
[
  {
    "from": "Federalist.33.1",
    "to": "Constitution.1.8.18",
    "type": "quotes",
    "confidence": "high",
    "from_quote": "to make all laws which shall be NECESSARY and PROPER",
    "to_quote": "To make all Laws which shall be necessary and proper",
    "rationale": "The paragraph quotes the last clause of Article I, Section 8, which it names as \"the last clause of the eighth section of the first article.\""
  }
]
```

`propose` finds each quote in its passage (ignoring only differences of
whitespace and curly/straight quote marks), stores the passage's own text, and
fails if a quote is not there. Copy quotes from `tools.show` output exactly,
including capitals; never reconstruct them from memory.

## Reviewing links

Suggested links become reviewed only by a person. Two ways:

- **The review page** (`/review/`, linked in the site footer). Every
  suggested link, grouped by linker run, with both passages and the quoted
  words marked, high-confidence links first in each batch. A filter shows
  one confidence level at a time (each batch shows its count per level), so
  the high-confidence links can be taken first; with a level chosen,
  "Approve the undecided" approves only the links of that level. Approve or
  reject each one (with an optional note); the page
  keeps your choices in this browser until you send them. **Send to GitHub**
  opens a new issue titled "Link review" whose body lists one decision per
  line (`approve lnk_…`, `reject lnk_… — note`), at most 150 per issue; submit
  it. The review workflow (`.github/workflows/review.yml`) then checks that
  the issue's author has write access to the repository, records each
  decision with `tools.links apply` under that GitHub login (`reviewed_by`,
  `reviewed_at`, and `review_note` if given), runs `make verify`, commits to
  `main` (Cloudflare then rebuilds and redeploys the site), and comments on and
  closes the issue.
  Issues from anyone else change nothing. It uses only the workflow's own
  token; no secrets.
- **The command line**: `python3 -m tools.links review --reviewer NAME`.

Approved links move to `links/{batch}.jsonl` and show as reviewed on the
site; rejected ones move to `links/rejected/{batch}.jsonl`, so they are not
proposed again.

## Run 1: The Federalist → the Constitution (phase 3)

One run per paper: batch `fed-const-{n}`, run id `fed-const-{n}-{date}`.
Links go from a Federalist paragraph or footnote to the Constitution as signed
in 1787. Never link to an amendment (none existed when the papers were
written).

**Link when the paragraph points at a specific provision:**

| Type | When | Quotes | Confidence |
|---|---|---|---|
| `quotes` | The paragraph reproduces the wording of a clause, usually in quotation marks or capitals. | `from_quote`: the quoted words as printed in the paper. `to_quote`: the matching words of the clause. | `high` if verbatim and the clause is unambiguous. |
| `cites` | The paragraph identifies a provision without quoting it at length: by number ("the second section of the first article") or by naming it so specifically that only one clause fits ("the power of granting letters of marque"). | `from_quote`: the identifying words. `to_quote` only if a short phrase of the clause is echoed. | `high` for a numbered reference; `medium` for unambiguous naming. |

- Target the most specific ref: a clause (`Constitution.1.8.18`). If the paper
  names a whole section ("the tenth section of the first article"), target the
  section (`Constitution.1.10`). If it names several clauses, make one link per
  clause.
- A footnote that cites a provision is linked from the footnote
  (`Federalist.59.fn1`).
- The same words can appear in more than one clause ("ambassadors, other
  public ministers and consuls" is in Article II, Section 2 and Article III,
  Section 2). Read the paragraph and pick the clause it is discussing; if you
  cannot tell, leave it out.

**Do not link:**

- general discussion of a subject (taxation, the judiciary, the militia) that
  does not point at a specific provision;
- references to the Articles of Confederation ("the second article of the
  Confederation"), to state constitutions, or to British law;
- references to "the Constitution" or "the plan" as a whole;
- thematic resemblance. Thematic links are a later, separate run.

**Confidence, consistently:**

- `high`: a verbatim quotation of the clause, or a reference by number.
- `medium`: the paragraph describes or names the provision so specifically
  that only one clause fits, even though it neither quotes nor numbers it
  (for example, the Senate "chosen by the State legislatures" for
  `Constitution.1.3.1`).
- `low`: only when there is a real doubt that the paragraph refers to the
  clause at all, and the rationale must say what the doubt is. "It does not
  name or quote the clause" is not a doubt; that is what `medium` covers.

When a reference is doubtful, prefer leaving it out. Two shapes in
particular are usually not links: a phrase that merely matches a clause's
wording ("the supreme law of the land" used in a general argument), and a
recap of a conclusion reached in an earlier paper.

**Rationale:** one or two plain sentences saying how the paragraph points at
the clause: the words it quotes, or the number or name it uses. Do not explain
what the clause means, whether the paper's reading of it is right, or how
courts have read it.

## Run 2: the ratification debate (phase 6)

One run per essay (or per single piece): batch `deb-{work}-{essay}` (for
example `deb-cato-3`, `deb-landholder-10b`, `deb-caution`), run id
`deb-{work}-{essay}-{date}`. A second set of runs covers The Federalist's
references to debate writers: batch `fed-deb-{n}`.

Use `python3 -m tools.show Cato.3` (it prints the essay's newspaper, date,
address and signature as well as its paragraphs) and
`python3 -m tools.candidates --ref Cato.3`.

**Three kinds of link, all from the essay's own text:**

1. **Essay → the Constitution** (`quotes`, `cites`): exactly as in run 1.
   The essays were written about the Constitution as signed in 1787, so never
   link to an amendment. The essays also discuss the Articles of
   Confederation, state constitutions and the plans of the Convention; none of
   those is a link.
2. **Essay → the Declaration of Independence** (`quotes`, `cites`): when the
   paragraph quotes the Declaration's words ("unalienable rights", "consent
   of the governed" used as a quotation, not as a common phrase) or names it.
   Target the paragraph quoted (`Declaration.2`). Never `interprets`.
3. **Essay → another essay or The Federalist** (`responds_to`, `rebuts`,
   `cites`, `quotes`): when the text itself names the other writer or piece.
   - `responds_to`: the essay answers a named writer or piece ("a writer
     under the signature of CAESAR, in Mr. Child's paper", a letter addressed
     "To the Honourable Luther Martin").
   - `rebuts`: only when the paragraph explicitly sets out to refute a
     specific argument of the other writer, which it states.
   - `cites`: the paragraph refers the reader to the other piece ("See
     CATO, No. V.").
   - `quotes`: the paragraph reproduces the other writer's words, and they are
     in the library: `to_quote` must be found in the target passage, so find
     the passage with `tools.show` first.
   - Target the most specific ref the text supports: a paragraph if it quotes
     one, an essay (`Caesar.1`) if it names or dates one, the series
     (`Caesar`) if it names only the writer.
   - A response must come after what it answers: check the dates printed in
     each essay's heading (and `series_dates` in the candidates).
   - Writers or pieces not in the library (Gerry's objections, Wilson's
     speech, Mason's objections, Brutus if not imported) are not links.
   - A writer's reference to an earlier number of the same series is a
     `cites` (or `quotes`) link when it identifies one paper ("my last
     paper", "the Gazette of the 23d instant", "In my seventeenth number").
     General recaps ("in two former papers") are not links.
   - A piece identified only by a description ("an anonymous writer") or by
     words it quotes without naming its author is not a link.
   - A bare mention of a writer in a list (Centinel naming "the patriotic
     essays of … Cato" among papers kept from the post) is at most `cites`,
     `medium`.
   - A paragraph that both reproduces and refutes another writer's words
     gets two links, `quotes` and `rebuts`.
   - The same clause may be linked from several paragraphs of one essay
     when each paragraph names it.
   - A clause named inside a quotation from a writer not in the library
     (Wilson's speech quoted by A Friend to the Constitution) may be linked
     from the quoting paragraph at `medium`, saying so in the rationale.

**Never link from an editor's note.** Notes ending "— Ed." (in any OCR form:
"Ed.", "EJ.", "£d.") are Paul Leicester Ford's or McMaster and Stone's, not
the essay's, even when they say what the essay answers. So are notes without
that mark that plainly speak for the editor: citations of modern editions
("Printed in Ford's Pamphlets…", "Cf. Papers of James Madison"), corrections
("This is an error"), identifications ("Luther Martin. See his Genuine
Information…"), and notes ending in an OCR form of "Ed." such as "— IN".
Notes by the essay's author (the Landholder's own notes, for example) can be
linked from.

**Uncertain words.** Texts read from scans mark words the scans disagree on
(`uncertain`). A quote may include them (it is copied from the passage as
it stands), but say so in the rationale if the link depends on one.

Confidence and rationale follow run 1. For links between essays: `high` when
the text names the writer or piece and the target is unambiguous; `medium`
when it names the writer but the essay meant has to be worked out from dates
or subject; `low` only with a stated doubt.

**Results.** 67 runs (one per essay, plus three for The Federalist's notes
naming debate writers) proposed 410 links: 331 to 74 clauses of the
Constitution, 2 to the Declaration, and 77 between essays (14 `responds_to`,
8 `rebuts`, the rest `quotes` and `cites`); 216 `high`, 194 `medium`. A
second agent checked all 81 links between essays and a random sample of 70
links to the Constitution against both texts. It found 4 wrong (two general
recaps of earlier numbers, a piece named only by description, and a bare
mention at `high`) and 4 doubtful (a section number without its article, a
quotation describing a Convention draft rather than the signed text, a
rationale explaining a clause, and a response named only in the paper's
note); all eight were removed or corrected before publishing.

**Brutus.** After Brutus I–IV were imported (decision 34), nine more runs
linked them (`deb-brutus-1` … `-4`) and the essays that name Brutus
(`deb-brutus-in-{source}`: Cato V, Centinel III, IX and XIV, A Countryman
II), proposing 45 links. The same check covered all 45: one was removed (a
low-confidence link to the Declaration from Brutus II, whose "most solemn
declarations" may mean the state declarations of rights) and one rationale
reworded. Run 2 now stands at 453 links (two identical links merged when
Federal Farmer III's split paragraph was joined): 366 to 75 clauses, 2 to the
Declaration, 85 between essays.

## Run 4: the debates in Congress → the Constitution and the amendments

One run per item (one day's item of a house's proceedings, `House1789.Jun8`,
`Senate1866.May23`): batch `cong-{ref}` in lower case with the dot as a
dash (`cong-house1789-jun8`), run id `cong-{ref}-{date}`. Two passes, in
this order, each over every item:

1. **Debate → the Constitution** (`quotes`, `cites`): exactly as in run 1.
   Use `python3 -m tools.candidates --ref House1789.Jun8`. The target is the
   Constitution as it stood when the debate took place: for 1789 the text as
   signed; for 1864–65, 1866 and 1869 also the amendments then in force (the
   Eleventh and Twelfth; from 1866 the Thirteenth; in 1869 the Fourteenth),
   which a speaker may quote or name ("the amendment abolishing slavery" is
   `cites` `Amendment.13.1` at `medium`). References
   to state constitutions, the Articles of Confederation, bills before
   Congress or the rules of either house are not links.
2. **Debate → the amendment under debate** (`quotes` only), with
   `python3 -m tools.candidates --ref … --amendments`. A paragraph that gives
   the words of the proposal being debated (Madison's proposals, the
   committee's report, a motion to amend, the joint resolution's sections)
   is linked to the clause of the ratified amendment, or of the 1789 Joint
   Resolution's articles, only where at least eight consecutive words of it
   appear there unchanged (spelling and capitals aside): `from_quote` the
   words in the paragraph, `to_quote` the same words in the clause, both
   copied by code. `high` when the run of words is the substance of the
   clause (a guarantee, not a phrase like "the United States"); otherwise
   leave it out. The rationale says that the paragraph gives the words of a
   proposal and that they appear in the clause; never that the proposal
   "became" the clause, or why the wording changed. Paraphrase, discussion
   of a proposal by its number ("the fourth proposition"), and a speaker's
   view of what a clause means are not links.

**Do not link** a speaker's argument to the clause it is about; links
record quotation and citation, not subject. **Never link from** the Globe's
or the Annals' own notes or the record of votes ("yeas and nays").

Confidence and rationale follow run 1. Every run is checked by a second
agent against both texts before it is proposed, as in run 2.

**Notes from the runs on 1794–1919** (October 2026), followed in those runs:

- **The Constitution "as it stood"** includes every amendment ratified by the
  day of the debate: 1–15 for 1909–12, 1–17 for 1917, 1–18 for 1919. A
  quote or citation of one of those is pass 1; the amendment under debate is
  pass 2.

- **A whole amendment named.** An amendment of one section, named by
  number, cites that section at `high` ("the tenth amendment"); one of
  several sections cites the section the context picks out, at `medium`
  ("the amendment abolishing slavery" is `Amendment.13.1`). A bare "the
  fourteenth amendment" with nothing that picks out a section is not a link,
  nor is a mention in an account of an amendment's ratification.
- **"Section N" without its article** is linked only when the article was
  named just before, at `medium`.
- **Misnumbered references.** Speakers often misnumber ("the first section
  of the fourth article" for Article IV, section 2). Where the words quote
  or unmistakably describe a clause, link that clause at `medium` (or
  `high` if quoted verbatim) and note the misnumber in the rationale.
- **Proposals that rewrite a clause.** A proposal that says "the third
  paragraph of the first section of the second article … shall be amended
  to read" `cites` that clause; its new wording is not a quote of it, and a
  draft that repeats the existing clause is linked to it only where it
  explicitly quotes the existing text. Its wording is linked in pass 2 to
  the ratified amendment under the eight-word rule.
- **Pass 2 and "substance".** A run counts as the substance of the clause
  when it states the guarantee or rule the amendment makes (for the Twelfth,
  the electoral rules: counting, quorum, the majority, the three highest,
  the Vice President acting). Speakers reading the proposal's words in
  debate, and motions to strike out or insert words, are pass-2 links like
  the Clerk's reading. "The right of citizens of the United States to vote"
  alone is accepted as substance for the Fifteenth and Nineteenth, at
  `high`; reviewers may reject it. So is an enforcement section ("power to
  enforce this article by appropriate legislation"), following the 1866
  links to `Amendment.14.5`. The eight words must be unbroken in the text
  as stored: a word OCR split ("elect e d") breaks the run. A run that
  needs a word marked uncertain, read as another scan reads it, is at most
  `medium`, and the rationale says so.
- **Pass 1 never targets the amendment under debate**: until ratified it is
  a proposal, reached only by pass 2's exact runs.
- **Article V** is linked from each paragraph that names it ("the fifth
  article", "the amendatory clause"), not from a generic "amend the
  Constitution in the mode it provides".
- **Clauses cited inside other proposals** (the Crittenden articles, a
  substitute): `high` in the proposer's own text, `medium` when a speaker
  reads someone else's proposal.
- **Who may be linked from.** The Speaker's rulings and the Clerk's readings
  may be; vote tallies and the reporter's narration of how a question was
  decided may not. A reporter's parenthesis ("here he cited the
  Constitution") is the Annals' own note. Documents a member reads or prints
  in the record (reports, statutes, editorials, state resolutions, court
  opinions) may be linked from where they quote or cite a clause, and the
  rationale says whose words they are.
- **The 1789 Joint Resolution.** A speaker naming one of its twelve articles
  ("the first of the twelve amendments") cites `Resolution1789.Article.{n}`.
- **Quotes are cut from the segment text** in `texts/`, never from
  `tools.show`'s printout, which can render an uncertain word differently.

## Imported links: Supreme Court cases (phase 7)

Links between cases and the Constitution are not proposed by a linker but
imported by code from the Constitution Annotated (2022 print edition), with
`created_by.kind: "import"` and a `source` naming the pages they come from
(`python -m importers.case_links`, decision 49):

- `links/proposed/conan-interprets.jsonl`: a case `interprets` a provision
  when the Constitution Annotated's essays on that provision cite it on at
  least two printed pages. The source lists the essays and pages; confidence
  is high from four pages, medium below. The link records where the essays
  cite the case, not what the case held.
- `links/proposed/conan-overrules.jsonl`: one `overrules` link per row of the
  Table of Supreme Court Decisions Overruled by Subsequent Decisions where
  both decisions are in the library, citing the table's page.

They are suggested like any other link and appear on the review page under
"Supreme Court cases". To review one, open the source it names: the essays'
pages in the Constitution Annotated (govinfo `GPO-CONAN-2022`). Running the
import again keeps each link's id and date and never proposes again a link a
person has decided.

