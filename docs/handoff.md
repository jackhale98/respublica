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

**More of the debate** (decision 56): Brutus V–XVI (not XI, which has no
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
against. Run 4 of the linking guide (`docs/linking.md`) proposes their
links to the Constitution and to the amendments. Next in this line: the
Thirteenth and Fifteenth Amendments in the Globe, by the same rule.

**Phase 7, Supreme Court cases: the first set is imported** (decision 49):

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

0. **Read uncertain words off the scans** on `/errata/` (decision 48):
   about 5,700 words, most in the 1866 debates. Corrections come back
   through the errata workflow; agents never record them.
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
