# Picking up the work

For a person or an agent starting a new session on this repository. Read
`CLAUDE.md` (the rules), `PLAN.md` (the plan), the README's status table,
and `docs/decisions.md` (why things are as they are) first. This page says
where the work stands and what comes next.

## How the project owner works with agents

- **Deploys.** The owner has approved deploying after every finished task:
  run `make verify`, `make build` and a browser check of what changed, then
  push to `main` (Cloudflare then builds and deploys it to
  respublicalibrary.org). Agents work on their
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

**Phase 7, Supreme Court cases: the first set is imported** (decision 46):

- 213 cases (`cases/`), chosen by the rules of decisions 41 to 43, each
  keyed by its CourtListener cluster (`importers/courtlistener.py`; the
  recorded lookups are raw sources), with a page at `/cases/{id}/` and an
  index at `/cases/`.
- The syllabus as printed in the U.S. Reports for 156 of them, read from the
  Library of Congress scans (`importers/usreports.py`, `importers/cases.py`).
  The scans are kept out of git: run `make fetch` first in a fresh clone.
- 338 `interprets` and 39 `overrules` links, imported from the Constitution
  Annotated as suggestions (`importers/case_links.py`), on the review page
  under "Supreme Court cases".
- CourtListener allows the token 125 requests a day; the lookups use about a
  dozen. The token is read from `COURTLISTENER_TOKEN` and never stored.

## Next

1. **Review the case links** on `/review/` ("Supreme Court cases"), checking
   a sample against the Constitution Annotated pages each link names.
2. **Syllabi not yet shown** (each case says why in `syllabus_note`):
   - 25 scans whose text layer the reader could not follow
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
   - 21 decisions before volume 91 and 3 summary decisions have no syllabus
     by design; *Sessions v. Morales-Santana* (582 U.S. 47) is not yet in the
     Library of Congress collection.
3. **OCR in syllabi**: misreadings are copied, not fixed (rule 3); record
   suspected ones in `docs/errata.md` (entry 25 lists the first) for a
   person to check against the page image the case page links to.
4. **Links to whole provisions**: some `interprets` links point at an
   article or a whole amendment (`Amendment.14`, `Constitution.3`); they
   show on the case page but on no clause, since only passages list
   connections. Decide with the owner whether to show them on the heading.
5. **Connection preview** (approved by the owner): in the passage panel,
   a "Preview" toggle on each connection opens the linked passage's text in
   place (a case: its name, date and first syllabus paragraph), with "Show
   all" and "Go to passage". Data: one small file per page from
   `tools/site_data.py` with the far ends' text, fetched on first use. One
   preview open at a time; works by keyboard and on the phone sheet.
6. **Run 3: the debate and the Bill of Rights** (approved by the owner):
   `shared_theme` links from essays of the ratification debate to the
   amendment clauses that cover a guarantee the essay names (a free press,
   civil juries, searches, reserved powers; Federalist No. 84 on a bill of
   rights). Exact quotes on both sides; the rationale names the shared
   subject only, never that the essay caused the amendment. One run per
   essay, checked by a second agent, suggested for review. Write the
   criteria into `docs/linking.md` and a decision entry first.
7. **CourtListener quota**: the token's account also serves CommonHall,
   which uses about 110 of its 125 requests a day (CourtListener's Usage
   API: `/api/rest/v4/api-usage/`, which costs nothing). A second account
   is against CourtListener's terms; a Free Law Project membership raises
   the limit. Res Publica needs about a dozen requests per new set of cases.
8. **Clause pages** (PLAN.md, phase 7): today each clause's connections list
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
