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

**Never link from an editor's note.** Notes ending "— Ed." (in any OCR form:
"Ed.", "EJ.", "£d.") are Paul Leicester Ford's or McMaster and Stone's, not
the essay's, even when they say what the essay answers. Notes by the essay's
author (the Landholder's own notes, for example) can be linked from.

**Uncertain words.** Texts read from scans mark words the scans disagree on
(`uncertain`). A quote may include them (it is copied from the passage as
it stands), but say so in the rationale if the link depends on one.

Confidence and rationale follow run 1. For links between essays: `high` when
the text names the writer or piece and the target is unambiguous; `medium`
when it names the writer but the essay meant has to be worked out from dates
or subject; `low` only with a stated doubt.
