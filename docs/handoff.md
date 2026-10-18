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

**Phase 7, Supreme Court cases: the first set is imported** (decision 44):

- 189 cases (`cases/`), chosen by the rules of decisions 41 to 43, each
  keyed by its CourtListener cluster (`importers/courtlistener.py`; the
  recorded lookups are raw sources), with a page at `/cases/{id}/` and an
  index at `/cases/`.
- The syllabus as printed in the U.S. Reports for 126 of them, read from the
  Library of Congress scans (`importers/usreports.py`, `importers/cases.py`).
  The scans are kept out of git: run `make fetch` first in a fresh clone.
- 308 `interprets` and 39 `overrules` links, imported from the Constitution
  Annotated as suggestions (`importers/case_links.py`), on the review page
  under "Supreme Court cases".
- CourtListener allows the token 125 requests a day; the lookups use about a
  dozen. The token is read from `COURTLISTENER_TOKEN` and never stored.

## Next

1. **Review the case links** on `/review/` ("Supreme Court cases"), checking
   a sample against the Constitution Annotated pages each link names.
2. **Syllabi not yet shown** (each case says why in `syllabus_note`):
   - 36 scans whose text layer the reader could not follow
     (`python -m importers.usreports syllabus VOL PAGE` prints what it reads
     and the problem). Most are hanging-indent headnotes of 1880–1940 or
     pages whose OCR lines are out of order; improve the reader, never type
     text.
   - 7 recent decisions (Dobbs, Kennedy v. Bremerton, …) not yet in the
     Library of Congress collection: the owner approved taking their
     syllabus from CourtListener's text of the slip opinion (an opinion
     request per case), but that text drops the hyphen where a word breaks
     at a line end ("electioneer ing", "corpora tion"), so it cannot be
     rejoined without guessing. Reading the Court's slip-opinion PDF itself
     (supremecourt.gov) would need the owner's approval as a new source.
   - 20 decisions before volume 91 and 3 summary decisions have no syllabus
     by design.
3. **OCR in syllabi**: misreadings are copied, not fixed (rule 3); record
   suspected ones in `docs/errata.md` (entry 25 lists the first) for a
   person to check against the page image the case page links to.
4. **Links to whole provisions**: some `interprets` links point at an
   article or a whole amendment (`Amendment.14`, `Constitution.3`); they
   show on the case page but on no clause, since only passages list
   connections. Decide with the owner whether to show them on the heading.
5. **Clause pages** (PLAN.md, phase 7): today each clause's connections list
   the cases that interpret it, in date order, with overruled cases marked.
   A page per clause bringing together the founding debate and the cases is
   still to build.

## Starting a new session

Open a new session on this repository with the environment that holds the
token, and give it this prompt:

> Read docs/handoff.md, CLAUDE.md and PLAN.md, then continue phase 7
> (Supreme Court cases) from "Next". Run `make fetch` first. The
> CourtListener token is in the environment as COURTLISTENER_TOKEN. Deploy
> as before when each step is verified.
