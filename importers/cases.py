"""Import the first set of Supreme Court cases into cases/.

Inputs (sources/manifest.json): the Constitution Annotated (conan-2022-*,
which cases and why), CourtListener's lookups (courtlistener-*, each case's
cluster: its ID, name, date and citation) and the Library of Congress scans
of the United States Reports (loc-usrep-*, the syllabus as printed).
Output: cases/{cluster_id}.json, one per case.

A case's refs are `Case.{cluster_id}` and, for the syllabus, one passage
per printed paragraph, `Case.{cluster_id}.syllabus.{n}` (docs/references.md).
The syllabus is copied as the scan's text layer reads it (rule 7: no
summaries of our own); where the reader cannot be sure it has the whole
syllabus in order (`importers.usreports.problems`), the case has none and
says why (`syllabus_note`). Opinion text is not imported: case pages link
to CourtListener for it (decision 49).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from tools.common import CASES_DIR, write_json

if TYPE_CHECKING:
    from importers import courtlistener

OUT_DIR = CASES_DIR
NAME_END = re.compile(r",? (?:\d+ U\.S\. |No\. ).*$")


def printed_name(name: str) -> str:
    """The case's name as the Constitution Annotated prints it, without the
    citation: "McCulloch v. Maryland, 17 U.S. (4 Wheat.) 316 (1819)" ->
    "McCulloch v. Maryland"."""
    return NAME_END.sub("", name).strip()


def case_date(cluster: dict, conan_year: str | None, printed) -> tuple[str, str]:
    """The case's date of decision and where it comes from (decision 49):

    1. the date printed in the United States Reports ("Decided December 18,
       1944."), when the scan's text reads it cleanly (`usreports.printed_dates`)
       and its year is within one of the year the Constitution Annotated prints;
    2. else CourtListener's date, when its year is the one the Constitution
       Annotated prints, or that is the year of the term the case is reported
       in and CourtListener's date falls in the year after (the December Term
       of 1866 ran into 1867: Ex parte Garland, decided January 14, 1867);
    3. else only the year the Constitution Annotated prints.
    """
    # A printed date's year must agree with the Constitution Annotated's within a year: with
    # no term read from the running heads, OCR's "1695" for "1895" would pass unchecked.
    if printed is not None and printed.decided and (
            not conan_year or abs(int(printed.decided[:4]) - int(conan_year)) <= 1):
        return printed.decided, "us_reports"
    filed = str(cluster.get("date_filed") or "")
    term = printed.term if printed is not None else None
    if conan_year and filed[:4] == conan_year:
        return filed, "courtlistener"
    if conan_year and term is not None and int(conan_year) == term and filed[:4] == str(term + 1):
        return filed, "courtlistener"
    if conan_year:
        return conan_year, "constitution_annotated"
    return filed, "courtlistener"


DATE_NOTES = {
    "us_reports": "Date of decision as printed in the United States Reports.",
    "courtlistener": "Date of decision from CourtListener (the United States Reports scan gives none that could be read).",
    "constitution_annotated": ("Year as the Constitution Annotated prints it; CourtListener's date ({filed}) "
                               "is in another year, and the United States Reports scan gives no date of decision "
                               "that could be read."),
}


def import_case(match: courtlistener.Match, reasons: list[str]) -> dict:
    from importers import courtlistener, usreports  # here, so `python -m importers.usreports` runs cleanly
    c = match.cluster
    cid = str(c["id"])
    prefix = f"Case.{cid}"
    title = printed_name(match.name)
    doc = {
        "id": cid,
        "title": title,
        "ref_prefix": prefix,
        "courtlistener_name": c["case_name"],
        "date": None,  # below, from the United States Reports where it prints one
        "courtlistener_url": courtlistener.SITE + c["absolute_url"],
        "chosen_because": reasons,
        "conan_citation": match.name,
        **({"courtlistener_match": match.note} if match.note else {}),
        "source_ids": [match.source_id],
        "segments": [],
    }
    cites = [f"{x['volume']} U.S. {x['page']}" for x in c.get("citations", []) if x.get("reporter") == "U.S."]
    m = usreports.US.fullmatch(match.key) or (usreports.US.fullmatch(cites[0]) if len(cites) == 1 else None)
    if m:
        doc["us_cite"] = m.group(0)
    if not usreports.US.fullmatch(match.key):
        doc["docket"] = match.key.removeprefix("No. ")
    edition = [f"Case details: CourtListener (Free Law Project), cluster {cid}."]
    printed = None
    if m:
        try:
            usreports.raw_path(usreports.source_id(int(m.group(1)), int(m.group(2))))
            printed = usreports.printed_dates(int(m.group(1)), int(m.group(2)))
        except KeyError:
            pass
    doc["date"], doc["date_source"] = case_date(c, courtlistener.printed_year(match.name), printed)
    if doc["date"] != c["date_filed"]:
        doc["courtlistener_date"] = c["date_filed"]
    edition.append(DATE_NOTES[doc["date_source"]].format(filed=c["date_filed"]))
    if not m:
        doc["syllabus_note"] = "Not yet in the bound volumes of the United States Reports."
    else:
        v, p = int(m.group(1)), int(m.group(2))
        sid = usreports.source_id(v, p)
        try:
            usreports.raw_path(sid)
        except KeyError:
            sid = None
        if v < usreports.FIRST_SYLLABUS_VOLUME:
            doc["syllabus_note"] = (f"Volume {v} is one of the early reports (before volume "
                                    f"{usreports.FIRST_SYLLABUS_VOLUME}), whose headnotes are the reporter's own.")
        elif sid is None:
            doc["syllabus_note"] = ("The Library of Congress has no scan of this decision on its own (summary "
                                    "decisions are printed in lists, and the latest volumes are not yet scanned).")
        if sid:
            doc["source_ids"].append(sid)
            doc["loc_url"] = usreports.ITEM_URL.format(v=v, p=p)
            doc["pdf_url"] = usreports.PDF_URL.format(v=v, p=p)
            edition.append(f"Syllabus: United States Reports, volume {v}, as printed, read from the text layer "
                           "of the Library of Congress scan (OCR in older volumes; not checked word by word).")
        if sid and v >= usreports.FIRST_SYLLABUS_VOLUME:
            paras = usreports.syllabus(v, p)
            trouble = usreports.problems(paras)
            if trouble:
                where = re.search(r"\(p\. (\d+)\)", trouble[0])
                doc["syllabus_note"] = ("No syllabus was found in the text layer of the scan." if not paras else
                                        "The text layer of the scan could not be read reliably: on p. "
                                        f"{where.group(1)} a paragraph seems to stop mid-sentence.")
            else:
                for n, para in enumerate(paras, 1):
                    doc["segments"].append({
                        "kind": "syllabus",
                        "label": f"{title}, syllabus ¶ {n}",
                        "page": para.page,
                        "ref": f"{prefix}.syllabus.{n}",
                        "text": para.text,
                    })
    doc["edition"] = {"name": "CourtListener and the United States Reports", "notes": " ".join(edition)}
    return doc


def run(out_dir: Path = CASES_DIR) -> list[Path]:
    from importers import courtlistener
    from importers.conan import first_set
    chosen = first_set()
    responses = courtlistener.recorded()
    paths = []
    for key, ch in sorted(chosen.items()):
        match = courtlistener.match(key, ch.name, responses)
        doc = import_case(match, ch.reasons)
        path = out_dir / f"{doc['id']}.json"
        if path in paths:
            raise courtlistener.CourtListenerError(f"two cases share cluster {doc['id']}")
        write_json(path, doc)
        paths.append(path)
    return paths


if __name__ == "__main__":
    for p in run():
        print(f"wrote {p}")
