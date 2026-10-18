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
to CourtListener for it (decision 43).
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
        "date": c["date_filed"],
        "courtlistener_url": courtlistener.SITE + c["absolute_url"],
        "chosen_because": reasons,
        "conan_citation": match.name,
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
    from importers.conan import essay_pages, landmark_cases, overruled, table_of_cases
    chosen = landmark_cases(table_of_cases(), essay_pages(), overruled())
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
