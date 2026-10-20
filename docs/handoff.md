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

**The state ratifying conventions** (decision 68): nine works
(`importers/conventions.py`), Massachusetts, Connecticut, New Hampshire,
New York, Pennsylvania and Maryland (Elliot vol. 2), Virginia (vol. 3) and
North and South Carolina (vol. 4), about 641,000 words, divided by day
(refs `Virginia1788.Jun5.{n}`), in a group of their own on
`/ratification/`. The text is the Library of Congress's typed
transcription (`importers/amem.py`; public domain, as its header and the
collection's rights page say), checked word by word against the Internet
Archive's scans of the 1907 printing; about 750 words are marked uncertain
where the scans read another word, many of them the transcription's own
keying slips ("fights" for "rights", "mast" for "must"), some OCR
misreadings ("be"/"he"). The same transcription is now Henry's
tie-breaker, before the Anti-Federalist Library: one word changed, and the
72 words the scans settled that it reads otherwise are erratum 150. Its
raw files and the vol. 2 and 4 scans are kept out of git (families `lled`,
`iaelliot`). No links proposed yet. The importer stops on any dateline not
in its list of days: check the page before adding one.

**Sources of the Declaration** (decision 67): Paine's *Common Sense*
(first edition, R. Bell, January 1776; `importers/paine.py`) and Locke's
Second Treatise (first edition, 1690, Book II; `importers/locke.py`), a
page per part or chapter in a collection of its own ("sources"), with
home-page cards.
The text is the Text Creation Partnership's CC0 transcription
(`importers/tcp.py`), checked word by word against Internet Archive scans
of the same printing (one for Paine, two for Locke); 61 and 162 words are
marked uncertain, mostly OCR misreadings, some the transcription's slips
(errata 130–133: "the car" for "the ear" was missed by the check). Refs
`CommonSense.{part}.{n}`, `Locke.{chapter}.{section}` (no § 21 in 1690).
No links proposed yet. Where the Continental Congress documents get a
section of their own, these two may move into it (`tools/site_data.py`,
their `collection`).

**Debates in Congress** (`/congress/`): the House's 1789 debate on the
amendments, from the Annals of Congress (`importers/annals.py`, decision
46); both houses' proceedings on the Eleventh Amendment (1794) and the
Twelfth (1802 and 1803), from volumes 4, 11 and 13 of the Annals (decision
60; about 2%, under 1% and about 3% of words marked uncertain; the 1803
Google scans are small and their OCR poor, so `/errata/` has about 5,300
words from them; `python -m importers.annals fetch` keeps only the pages
needed, as byte ranges); and both houses' 1866 debates on the Fourteenth Amendment, from the
Congressional Globe (`importers/globe.py`, decision 47). About 1% (1789)
and 1.2% (House and Senate, 1866) of words are marked uncertain; since
decision 58 the June days of 1866 are checked against the Lincoln
Financial Foundation copy's part 4 (`congressionalglo00unit`), with the
microfilm as a third reading. Since decision 59 two copies that agree on a
clean-text word overrule UNT's OCR ("tho" -> "the"; erratum 65), which
settled about 200 words across the library and marked about 100 more
where one real word replaced another, for a person to check. Joining a
vote's tally to the last name in the copies' text (`Session.tallies`) is
applied only to 1866; the 1864–65 and 1869 copies split tallies the same
way and would gain from it, which changes those texts. The Thirteenth (1864–65: `Senate1864`, `House1864`, `House1865`)
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

**The Congressional Record** (`importers/record.py`, decisions 61 and 62):
both houses' proceedings on the Sixteenth to Twenty-sixth Amendments
(1909–71, twenty-five works, `Senate1909` … `House1971`), from the text layer of
govinfo.gov's scans of the bound Record, one PDF per house per day, checked
against the Internet Archive's microfilm (whose page images the errata page
shows). The days are those the Record's own index lists; the importer
checks that every page it gives is in an item imported. About 4% of words
are marked uncertain in 1909–19 (7% in the House's December 1917 debate,
whose volume the OCR reads worst; errata 100–103), about 1.4% in 1932–71
(errata 104–105). The volumes from 1932 are read by rules of their own
(`Session.later`), and from 1947, where the index gives only the page a
day's debate begins on, each day lists the page it runs to (`RUNS_TO`):
check the page before adding one. The govinfo PDFs, about 2.1 GB, are
kept out of git (the budget for such files is 4 GiB since decision 61; CI
caches each family under its own key). To add a day or an amendment: find
the joint resolution in the volume's History of Bills and Resolutions,
the day's granule in the part's MODS record (`printPageRange`), add it to
`DAYS` (and the part's microfilm to `SESSIONS`), `python -m importers.record
fetch`, then run the importer and read what it stops on. The Twenty-seventh
Amendment is left out (its proposing debate is `House1789`). Links have not
been proposed for these works yet.

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
   about 91,100 words in all (`python -m tools.uncertain`), 2,953 of them
   in the 1866 debates. Corrections come back
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
