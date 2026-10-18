# Picking up the work

For a person or an agent starting a new session on this repository. Read
`CLAUDE.md` (the rules), `PLAN.md` (the plan), the README's status table,
and `docs/decisions.md` (why things are as they are) first. This page says
where the work stands and what comes next.

## How the project owner works with agents

- **Deploys.** The owner has approved deploying after every finished task:
  run `make verify`, `make build` and a browser check of what changed, then
  push to `main` (that deploys to GitHub Pages). Agents work on their
  session's branch and push the same commits to `main`.
- **Links.** Agents propose; only a person reviews (rule 4). The owner
  reviews on the site's review page (`/review/`), which records decisions
  through GitHub issues (`docs/linking.md`, "Reviewing links").
- **Refs before launch.** Refs are permanent (rule 6). Until launch the
  owner has allowed renumbering to fix import errors, case by case
  (decisions 36, 37); ask first. After launch, use retired refs
  (`docs/references.md`).
- **Ask first** before adding an upstream source, a third-party script, or
  a secret (CLAUDE.md).

## Where things stand

Phases 0–6 are done (the README's status table has the counts): the
founding documents, The Federalist, twenty works of the ratification
debate read from scans, about 740 suggested links awaiting review, the
connections panel and graph, search, and the review page.

**Phase 7, Supreme Court cases, is in progress:**

- Done: `tools/pdf.py` (PDF text with the standard library) and
  `importers/conan.py`, which reads the 2022 Constitution Annotated
  (`sources/raw/conan-2022-*.pdf`): the essays on each page and their
  clauses, the Table of Cases, and the table of overruled decisions.
- Done: the first set of cases, 189, by the rules of decisions 41 and 42
  (`python -m importers.conan --landmarks` lists them with the reason each
  was chosen).
- Waiting: CourtListener. Cases are keyed by CourtListener cluster ID
  (`Case.{cluster_id}`, CLAUDE.md). Its API needs a token, which the owner
  adds in the cloud environment's settings (Network secrets, or an
  environment variable `COURTLISTENER_TOKEN`); a new session picks it up.
  The token is used only by import scripts, never by the site.

## Next: phase 7, step by step

1. **Check the token** is available (`COURTLISTENER_TOKEN`), and check
   CourtListener's API field names against a real response before writing
   a parser (CLAUDE.md). Record each fetched response as a raw source with
   `tools/fetch.py` (URL, date, sha256, license), never the token itself.
2. **Find each case's cluster.** For each of the 189 cases, look up the
   cluster by its U.S. Reports citation (or docket number for slip
   opinions) with CourtListener's citation lookup; record the match and
   fail loudly on none or several.
3. **Import the cases** (`importers/courtlistener.py`, writing `cases/`):
   name, date, U.S. Reports citation, the official syllabus verbatim where
   one exists (rule 7: no characterizations), and the opinion's paragraphs
   as `Case.{id}.{n}` only if the owner wants opinion text on the site
   (PLAN.md: show linked passages and the syllabus, link to CourtListener
   for the rest). Document the refs in `docs/references.md` and the edition
   in `docs/editions.md`.
4. **Links**, written by code as `import` links with a `source`, proposed
   like any other:
   - `interprets`, case to clause: where the Constitution Annotated's
     essays on a clause cite the case (`citations_by_clause`), citing the
     essays and pages. Decide with the owner whether one page is enough.
   - `overrules`, case to case: from the table of overruled decisions,
     where both cases are in the library, citing the table.
5. **Site:** case pages, the "overruled" flag on links (the verify check
   already exists), and clause pages listing the cases that interpret a
   clause (PLAN.md, phase 7).

## Starting a new session

Open a new session on this repository with the environment that holds the
token, and give it this prompt:

> Read docs/handoff.md, CLAUDE.md and PLAN.md, then continue phase 7
> (Supreme Court cases) from "Next: phase 7, step by step". The
> CourtListener token is in the environment as COURTLISTENER_TOKEN. Deploy
> as before when each step is verified.
