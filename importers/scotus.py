"""Recent cases as the Supreme Court itself publishes them (decision 54).

    python -m importers.scotus fetch      # download each PDF once (about 20 MB)

The Library of Congress has scanned the United States Reports to about
volume 578. For cases in later volumes the Court's own site has the
official text: the bound volumes (to 587 when this was written), the
preliminary prints of the volumes not yet bound, and, for recent terms, a
preliminary print of each case. Each is recorded as a raw source like
any other; the syllabus is read from it as from a Library of Congress scan
(`importers.usreports`), word for word. The Court's PDFs are encrypted with
an empty user password (anyone may open them); `tools.pdf` reads them.

`PRINTS` names, for each case, the PDF the Court's opinion list links to
for it (https://www.supremecourt.gov/opinions/slipopinion/{term}), or the
bound volume where the volume is now bound. A case is found in a volume by
its printed page (`locate`).
"""

from __future__ import annotations

import argparse
import re
import sys
from functools import lru_cache

from tools.common import load_manifest, raw_path
from tools.pdf import pdf_lines

SITE = "https://www.supremecourt.gov/opinions/"
LICENSE = "Public domain (U.S. Government work, 17 U.S.C. 105). Supreme Court of the United States."

# Case (as importers.conan keys it) -> (source id, path under SITE, what it is).
PRINTS = {
    "582 U.S. 47": ("scotus-582-bv", "boundvolumes/582BV.pdf", "United States Reports, volume 582 (bound volume)"),
    "585 U.S. 667": ("scotus-585-bv", "boundvolumes/585BV.pdf", "United States Reports, volume 585 (bound volume)"),
    "No. 16-1466": ("scotus-585-bv", "boundvolumes/585BV.pdf", "United States Reports, volume 585 (bound volume)"),
    "588 U.S. 684": ("scotus-588-pp2", "preliminaryprint/588US2PP_final.pdf",
                     "United States Reports, volume 588, part 2 (preliminary print)"),
    "No. 19-7": ("scotus-591-pp1", "preliminaryprint/591US1PP_web.pdf",
                 "United States Reports, volume 591, part 1 (preliminary print)"),
    "No. 19-715": ("scotus-591-pp2", "preliminaryprint/591US2PP_web.pdf",
                   "United States Reports, volume 591, part 2 (preliminary print)"),
    "No. 19-251": ("scotus-594-595", "20pdf/594us2r65_2co3.pdf", "594 U.S. 595 (preliminary print of the case)"),
    "No. 19-1392": ("scotus-597-215", "21pdf/597us1r58_gebh.pdf", "597 U.S. 215 (preliminary print of the case)"),
    "No. 21-418": ("scotus-597-507", "21pdf/597us2r62_d92h.pdf", "597 U.S. 507 (preliminary print of the case)"),
}
# The printed citation of each case above, where the case import knows it only by docket.
CITES = {"No. 16-1466": "585 U.S. 878", "No. 19-7": "591 U.S. 197", "No. 19-715": "591 U.S. 848",
         "No. 19-251": "594 U.S. 595", "No. 19-1392": "597 U.S. 215", "No. 21-418": "597 U.S. 507"}
# A running head's page number, first or last: "684 OCTOBER TERM, 2018",
# "Cite as: 588 U. S. 684 (2019) 685".
FOLIO = re.compile(r"^(\d{1,4})\s|\s(\d{1,4})$")


def print_for(key: str, cite: str | None = None) -> tuple[str, int] | None:
    """(source id, printed first page) of a case the Court's PDFs hold."""
    entry = PRINTS.get(key) or PRINTS.get(cite) or next((PRINTS[k] for k, c in CITES.items() if c == cite), None)
    if not entry:
        return None
    cite = cite or CITES.get(key, key)
    try:
        raw_path(entry[0])
    except KeyError:
        return None
    return entry[0], int(cite.split()[-1])


def folio(page) -> int | None:
    """The printed page number in a page's running head."""
    for line in page[:3]:
        m = FOLIO.search(line.text.strip())
        if m:
            return int(m.group(1) or m.group(2))
    return None


@lru_cache(maxsize=None)
def locate(source_id: str, printed: int) -> int:
    """The index (from 0) of the PDF page printed as `printed`: a guess from
    one page's running head, then checked; fails loudly if not found."""
    path = raw_path(source_id)
    guess = printed
    for _ in range(12):
        pages = pdf_lines(path, max_pages=1, start=max(0, guess))
        if not pages:  # past the end (a second part starts mid-volume): look earlier
            guess //= 2
            continue
        n = folio(pages[0])
        if n == printed:
            return guess
        guess = guess + (printed - n) if n is not None else guess + 1
    # A first page may print no folio in its head (the case's title page): look nearby.
    for i in range(max(0, guess - 3), guess + 4):
        pages = pdf_lines(path, max_pages=2, start=i)
        if len(pages) == 2 and folio(pages[1]) == printed + 1:
            return i
    raise ValueError(f"{source_id}: no page printed {printed}")


def cmd_fetch(_: argparse.Namespace) -> int:
    from tools.fetch import add_source
    have = {e["id"] for e in load_manifest()}
    for key, (sid, path, what) in PRINTS.items():
        if sid in have:
            continue
        cites = ", ".join(CITES.get(k, k) for k, v in PRINTS.items() if v[0] == sid)
        e = add_source(sid, SITE + path, LICENSE, ext=".pdf",
                       notes=f"{what}, as the Supreme Court publishes it; the case import reads {cites} "
                             "from it. Encrypted with an empty user password (anyone may open it).")
        have.add(sid)
        print(f"{key}: {e['path']}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m importers.scotus")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch", help="download the Court's PDFs for the cases in PRINTS")
    args = ap.parse_args(argv)
    return {"fetch": cmd_fetch}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
