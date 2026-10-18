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

When unsure whether a reference is real, leave it out, or propose it with
`low` confidence and say exactly what is uncertain.

**Rationale:** one or two plain sentences saying how the paragraph points at
the clause: the words it quotes, or the number or name it uses. Do not explain
what the clause means, whether the paper's reading of it is right, or how
courts have read it.
