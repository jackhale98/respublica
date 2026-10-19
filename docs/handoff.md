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
founding documents, The Federalist, twenty-two works of the ratification
debate read from scans, about 740 suggested links awaiting review, the
connections panel and graph, search, and the review page.

**More of the debate** (decision 55): Brutus V–XVI (not XI, which has no
scan) from the *New-York Journal*'s single Library of Congress scan
(`importers/nyjournal.py`; about 14% of words marked uncertain, most with a
suggestion), and Patrick Henry's twenty-four speeches in the Virginia
convention from Elliot's *Debates* (`importers/elliot.py`, four scans,
under 0.1% uncertain). The Anti-Federalist Library is a tie-breaker only
(`importers/library.py`): it chose among scans' readings in Brutus I–IV,
Agrippa I–XI, the Federal Farmer I–V and Centinel I and V–XVIII (28 words),
and its readings appear on `/errata/` as suggestions. No links have been
proposed for the new texts yet; check the newspaper essays' paragraph
breaks first (erratum 63). Not imported, for want of a scan to check the
Library against: Old Whig, Maryland Farmer, Impartial Examiner, John
DeWitt, Philadelphiensis, Melancton Smith.

**Debates in Congress** (`/congress/`): the House's 1789 debate on the
amendments, from the Annals of Congress (`importers/annals.py`, decision
46), and both houses' 1866 debates on the Fourteenth Amendment, from the
Congressional Globe (`importers/globe.py`, decision 47). About 1% (1789),
1.3% (House, 1866) and 2.2% (Senate, 1866) of words are marked uncertain;
the Senate's June days have only a poor microfilm to check UNT's OCR
against. The Thirteenth (1864–65: `Senate1864`, `House1864`, `House1865`)
and Fifteenth Amendments (1869: `House1869`, `Senate1869`) are imported the
same way (decision 57), with page reading refined for those volumes (never
for 1866, whose refs are published); 1.9–4.6% of their words are marked
uncertain, worst on pp. 1318–1319 of 1864 (errata 40). Run 4 of the linking
guide (`docs/linking.md`) proposes links for these debates to the
Constitution and to the amendments; it has not been run on the 1864–65 and
1869 works yet. Open questions for the owner: the Senate's sitting of
January 30, 1869, is imported only up to the next heading ("Committee
Service"); whether its later debate that day on S. R. No. 8, printed
without a heading of its own, belongs too needs a look at pp. 733–741.

**Phase 7, Supreme Court cases: the first set is imported** (decision 49):

- 232 cases (`cases/`), chosen by the rules of decisions 41 to 43 and 53, each
  keyed by its CourtListener cluster (`importers/courtlistener.py`; the
  recorded lookups are raw sources), with a page at `/cases/{id}/` and an
  index at `/cases/`.
- The syllabus as printed in the U.S. Reports for 202 of them, read from the
  Library of Congress scans (`importers/usreports.py`, `importers/cases.py`),
  or for nine recent cases from the Supreme Court's PDFs (`importers/scotus.py`,
  decision 54; in git).
  The scans are kept out of git: run `make fetch` first in a fresh clone.
- 356 `interprets` and 60 `overrules` links, imported from the Constitution
  Annotated as suggestions (`importers/case_links.py`), on the review page
  under "Supreme Court cases".
- CourtListener allows the token 125 requests a day; the lookups use about a
  dozen. The token is read from `COURTLISTENER_TOKEN` and never stored.

## Next

0. **Read uncertain words off the scans** on `/errata/` (decision 48):
   about 5,700 words, most in the 1866 debates. Corrections come back
   through the errata workflow; agents never record them.
1. **Review the case links** on `/review/` ("Supreme Court cases"), checking
   a sample against the Constitution Annotated pages each link names.
2. **Syllabi not yet shown** (each case says why in `syllabus_note`):
   - 5 scans whose text layer the reader cannot yet follow: 294 U.S. 532 and
     362 U.S. 257 (a comma read where a full stop is printed), 392 U.S. 1 (an
     OCR speck), 307 U.S. 496 (an outdented line after a wider gap) and
     424 U.S. 1 (the judgment run into the list of opinions)
     (`python -m importers.usreports syllabus VOL PAGE` prints what it reads
     and the problem). Improve the reader, never type text.
   - *Townsend v. Sain* (372 U.S. 293): no syllabus found in the scan's text
     layer; look at why.
   - 21 decisions before volume 91 and 3 summary decisions have no syllabus
     by design. Later cases not yet scanned by the Library of Congress need
     their Court PDF added to `importers/scotus.py` (`PRINTS`).
3. **OCR in syllabi**: misreadings are copied, not fixed (rule 3); record
   suspected ones in `docs/errata.md` for a person to check against the
   page image the case page links to.
4. **Run 3: the debate and the Bill of Rights** (approved by the owner):
   `shared_theme` links from essays of the ratification debate to the
   amendment clauses that cover a guarantee the essay names (a free press,
   civil juries, searches, reserved powers; Federalist No. 84 on a bill of
   rights). Exact quotes on both sides; the rationale names the shared
   subject only, never that the essay caused the amendment. One run per
   essay, checked by a second agent, suggested for review. Write the
   criteria into `docs/linking.md` and a decision entry first.
5. **CourtListener quota**: the token's account also serves CommonHall,
   which uses about 110 of its 125 requests a day (CourtListener's Usage
   API: `/api/rest/v4/api-usage/`, which costs nothing). A second account
   is against CourtListener's terms; a Free Law Project membership raises
   the limit. Res Publica needs about a dozen requests per new set of cases.
## Starting a new session

Open a new session on this repository with the environment that holds the
token, and give it this prompt:

> Read docs/handoff.md, CLAUDE.md and PLAN.md, then continue phase 7
> (Supreme Court cases) from "Next". Run `make fetch` first. The
> CourtListener token is in the environment as COURTLISTENER_TOKEN. Deploy
> as before when each step is verified.
