# Corrections

Words the scans could not settle, as a person read them off the page image
on the errata page (`/errata/`). One file per work, `{work}.jsonl`, one
decision per line:

```json
{"at": "2026-10-19", "by": "github-login", "index": 0, "now": "this", "ref": "House1789.Jun8.1", "was": "tlm^his"}
```

`was` is the uncertain word as the importer printed it, `index` its place
among the passage's uncertain words, and `now` what the page shows (the same
as `was` confirms the reading). The review workflow writes these lines from
an "Errata review" issue (`python -m tools.errata apply`); the importers
apply them (`importers/corrections.py`) and record each in the passage's
`corrected` list. Never write a line here by hand or by an agent: CLAUDE.md
rule 3 and docs/decisions.md 48.
