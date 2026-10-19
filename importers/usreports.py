"""Cases as printed in the United States Reports (Library of Congress scans).

    python -m importers.usreports fetch      # download each case's PDF once (about 320 MB)
    python -m importers.usreports syllabus 347 483

The Library of Congress publishes every case of volumes 1 to about 578 as
a PDF of the printed pages, with a text layer (OCR for older volumes). The
case import takes the official syllabus from it, word for word.

The PDFs are too large to keep in git (decision 49): the manifest records
each one (URL, date, sha256, license) and `make fetch` downloads them;
.gitignore keeps them out of commits.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from importers.ocr import join_across
from tools.common import load_manifest, raw_path
from tools.pdf import Line, pdf_lines

LICENSE = "Public domain (U.S. Government work, 17 U.S.C. 105). Library of Congress, United States Reports collection."
PDF_URL = ("https://tile.loc.gov/storage-services/service/ll/usrep/"
           "usrep{v:03d}/usrep{v:03d}{p:03d}/usrep{v:03d}{p:03d}.pdf")
ITEM_URL = "https://www.loc.gov/item/usrep{v:03d}{p:03d}/"
US = re.compile(r"(\d+) U\.S\. (\d+)")


def source_id(volume: int, page: int) -> str:
    return f"loc-usrep-{volume}-{page}"


# ------------------------------------------------------------ syllabus

# Volumes 1-90 are the nominative reports (Dallas to Wallace), whose
# headnotes are each reporter's own and often printed as marginal notes;
# a syllabus is read from volume 91 (1875) on (decision 49).
FIRST_SYLLABUS_VOLUME = 91
DATE_LINE = re.compile(r"\b(Argued|Submitted|Decided|Reargued)\b")
# A paragraph that starts any of these ends the syllabus.
END = re.compile(r"delivered the opinion|announced the judgment|^PER CURIAM|^Per Curiam|argued the cause"
                 r"|^Opinion of the Court|^Statement of the Case|^Counsel for")
# A paragraph that matches any of these, and all after it, are not syllabus:
# counsel, the lineup of the Justices' opinions, notes of separate opinions.
AFTER = re.compile(r"argued(?: the| for|$)|submitted (on )?(the|a|his|their) briefs?|\bon (the|his|their) briefs?\b"
                   r"|\bamic(i|us) curiae,? (urging|filed|in support)|^Mr\. [A-Z]|^Messrs\.|\bpost, p\. ?\d+"
                   r"|\bfiled (a |an )?(\w+ )*opinions?\b|^For (the )?(\w+ )*opinions? of"
                   r"|\bfor (appellants?|appellees?|petitioners?|respondents?|plaintiffs? in error|defendants? in error)( in [^.]*)?\.$|\bpost,$")
# A printer's mark at the foot of a page: "S994084 0-52---41".
PRINTER_MARK = re.compile(r"^\S*\d{5,}\S*( [\d-]+)?$|^\d+-\d+-+\d+$")
NOTE = re.compile(r"^[*†‡]|^\S?N[Oo][Tt][Ee]:")    # a footnote ("*Together with No. 2, ...")
RUNNING_HEAD = re.compile(r"^(\d+ )?Syllabus\.?( \d+ U\. ?S\.)?$|^Cite as: \d+ U\. ?S\. \d+ \(\d{4}\)( \d+)?$|^VOL\. [CLXVI]+")
# More of the dates: "Reargued October 22-23, 1958." or "March 31, 1958.*" on a line of its own,
# or the year alone ("1977").
DATE_MORE = re.compile(r"\b(Argued|Reargued|Decided|Submitted|reargument|Opinion announced)\b"
                       r"|^[A-Z][a-z]+\.? \d{1,2}(-\d+)?, \d{4}\.?\*?$|^(?=[a-z\d]).*(\d{1,2}, \d{4}\.|\d{4}\.-)"
                       r"|^\d{4}\.?\*?$")
HEAD_GAP = 30                   # running heads: within this of the page's top line


@dataclass
class Paragraph:
    text: str
    page: int           # the printed page it starts on


SYLLABUS_PAGES = 12  # the syllabus, with the counsel after it, fits in the first pages


@lru_cache(maxsize=None)
def _pages(volume: int, page: int) -> list[list[Line]]:
    return pdf_lines(raw_path(source_id(volume, page)), max_pages=SYLLABUS_PAGES)


def _merge_fragments(lines: list[Line]) -> list[Line]:
    """OCR sometimes breaks one printed line into pieces a few points apart
    vertically ("2. The. statute and resolution" | "did not violate"); put
    them back together, left to right."""
    out: list[Line] = []
    last_y = None  # baseline of the last piece joined
    for line in sorted(lines, key=lambda l: l.y):
        prev = out[-1] if out else None
        if prev and abs(line.y - last_y) <= 6 and line.x0 > prev.x0 + 20:
            out[-1] = Line(prev.y, prev.x0, line.x1, prev.size, f"{prev.text} {line.text}")
        else:
            out.append(line)
        last_y = line.y
    return out


def syllabus(volume: int, page: int) -> list[Paragraph]:
    """The syllabus as printed: the paragraphs after the line with the
    case's dates ("Argued ... Decided ..."), set in smaller type than what
    follows, up to the counsel, the statement of the case or the opinion.
    Footnotes, running heads and folios are left out; words broken at a
    line end are rejoined. Empty when the volume has no syllabus to read
    (before FIRST_SYLLABUS_VOLUME) or none is found."""
    if volume < FIRST_SYLLABUS_VOLUME:
        return []
    paras: list[tuple[int, list[Line]]] = []
    size = None  # the syllabus's type size, from its first lines
    started = False
    for i, pg in enumerate(_pages(volume, page)):
        lines = _merge_fragments([l for l in pg if not l.text.strip().isdigit() and not PRINTER_MARK.match(l.text)])
        if not started:
            at = next((k for k, l in enumerate(lines) if DATE_LINE.search(l.text)), None)
            if at is None:
                continue
            while at + 1 < len(lines) and DATE_MORE.search(lines[at + 1].text):
                at += 1
            lines, started = lines[at + 1:], True
            first = [l.size for l in lines[:5]]
            if not first:
                return []
            size = sorted(first)[len(first) // 2]
        elif lines:
            top = lines[0].y  # running heads: the lines at the head of the page
            lines = [l for l in lines if l.y > top + HEAD_GAP]
        # The syllabus on this page ends at larger type or at what follows it.
        take, ended = [], False
        big = [l.size >= size + 1.5 for l in lines]
        for k, line in enumerate(lines):
            # Larger type, for two lines running (OCR misjudges a single line's size now and then).
            if (big[k] and (k + 1 == len(lines) or big[k + 1])) or (END.search(line.text) and (take or paras)):
                ended = True
                break
            take.append(line)
        body = [l for l in take if not RUNNING_HEAD.match(l.text)]
        # A footnote starts with its mark after a wider gap than the lines above it.
        gaps = sorted(b.y - a.y for a, b in zip(body, body[1:])) or [0]
        leading = gaps[len(gaps) // 2]
        note = next((k for k, l in enumerate(body) if NOTE.match(l.text)
                     and (k == 0 or l.y - body[k - 1].y > 1.4 * leading)), None)
        if note is not None:
            body = body[:note]  # footnotes run to the foot of the page
        if body:
            xs = [l.x0 for l in body]  # the margin: where most lines start, give or take skew
            margin = max(xs, key=lambda x: sum(abs(y - x) <= 3 for y in xs))
            right = sorted(l.x1 for l in body)[len(body) // 2]
            prev = None  # the line before, on this page
            for line in body:
                # A paragraph starts on a line indented (or, for a hanging
                # indent, outdented) from the margin, or after a short line.
                if not paras or abs(line.x0 - margin) > 6 or (prev is not None and prev.x1 < right - 25):
                    if END.search(line.text):
                        ended = True
                        break
                    paras.append((page + i, [line]))
                else:
                    paras[-1][1].append(line)
                prev = line
        if ended:
            break
    return _finish(paras)


MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
# The date of decision in the case's dates ("Decided March 3d, 1884."); a
# decision announced without one ("Opinion and judgments announced May 31,
# 1955."). The month must be read exactly; OCR's "Jantary" is not guessed at.
DECIDED = re.compile(r"\b(?:Decided|announced),?\s+([A-Z][a-z]+)\.?\s*(\d{1,2})(?:st|nd|rd|th|d)?,\s*(\d{4})\b")
# The term in the running heads: "OCTOBER TERM, 1944.", "DEOEMBER TERM, 1862.", "Oct. 1875.]".
TERM = re.compile(r"\bTER\w*[,.]?\s+(\d{4})\b|^(?:Oct|Dec)\w*\.?\s+(\d{4})\.?\s*[\])]")


@dataclass
class PrintedDates:
    decided: str | None     # ISO date of decision, as printed, if read cleanly and in the term
    term: int | None        # the year of the term the case is reported in
    line: str               # the case's dates as printed ("" when there are none)


def printed_dates(volume: int, page: int) -> PrintedDates:
    """The dates the United States Reports print for a case: its term, from
    the running heads, and its date of decision, from the line of the case's
    dates (the one the syllabus follows). A date of decision is kept only if
    its month reads as a month and its year is the term's or the next (OCR
    reads "1295" for "1895")."""
    pages = _pages(volume, page)[:3]
    years = Counter(int(m.group(1) or m.group(2)) for pg in pages for l in pg for m in [TERM.search(l.text)] if m)
    term = years.most_common(1)[0][0] if years else None
    dates = ""
    for pg in pages:
        # Lines of figures are kept here: a page's folio is never next to the dates, a year alone can be ("1977").
        lines = _merge_fragments([l for l in pg if not PRINTER_MARK.match(l.text)])
        at = next((k for k, l in enumerate(lines) if DATE_LINE.search(l.text)), None)
        if at is None:
            continue
        block = [lines[at].text]
        while at + 1 < len(lines) and DATE_MORE.search(lines[at + 1].text):
            at += 1
            block.append(lines[at].text)
        dates = " ".join(block)
        break
    decided = None
    m = DECIDED.search(dates)
    if m and m.group(1) in MONTHS and 1 <= int(m.group(2)) <= 31:
        year = int(m.group(3))
        if term is None or year in (term, term + 1):
            decided = f"{year:04d}-{MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}"
    return PrintedDates(decided, term, dates)


def _finish(paras: list[tuple[int, list[Line]]]) -> list[Paragraph]:
    out = []
    for n, lines in paras:
        text = ""
        for line in lines:
            t = re.sub(r"\s+", " ", line.text).strip()
            text = join_across(text, t) if text else t
        # The judgment line ("108 F. 2d 683, reversed.") closes the syllabus;
        # only another judgment line may follow it (one per case decided).
        if AFTER.search(text) or (out and JUDGMENT.search(out[-1].text) and not JUDGMENT.search(text)):
            break
        out.append(Paragraph(text, n))
    return out


SENTENCE_END = re.compile(r"[.:;?!)\]\"'”’][^\w\s]{0,2}( -)?$|^Held\W?$|\bPp?\. \d+(-\d+)?$")
DISPOSITION = re.compile(r"\b(af+[ﬁi]?r?m?ed|aff?ied|reversed|remanded|vacated|dismissed|modified|granted|denied|"
                         r"overruled|answered|discharged|ordered)\b[^a-z]*$", re.I)


JUDGMENT = re.compile(r"^(No[s]?\. [\w ,-]+[,.] )?\d[^a-z]*\b[A-Z][\w.' ]*\d+.{0,120}\b(af+[ﬁi]?r?m?ed|reversed|remanded|vacated|"
                      r"dismissed|modified)\b[^a-z]{0,3}$|^(No\. .*)?(Affirmed|Reversed|Dismissed)\.$")


def problems(paras: list[Paragraph]) -> list[str]:
    """Why a syllabus as read looks incomplete or out of order: a paragraph
    that stops mid-sentence (the text layer lost its order, or the end of
    the syllabus was missed), or a last paragraph that is neither a
    sentence nor the judgment ("74 N. J. L. 683, affirmed.")."""
    out = []
    if not paras:
        return ["no syllabus found"]
    for k, p in enumerate(paras, 1):
        if not (SENTENCE_END.search(p.text) or (k == len(paras) and DISPOSITION.search(p.text))):
            out.append(f"paragraph {k} (p. {p.page}) stops mid-sentence: …{p.text[-50:]!r}")
    return out


def cmd_syllabus(args: argparse.Namespace) -> int:
    paras = syllabus(args.volume, args.page)
    for para in paras:
        print(f"[p. {para.page}] {para.text}\n")
    for problem in problems(paras):
        print(f"problem: {problem}")
    return 0


def cmd_fetch(_: argparse.Namespace) -> int:
    import urllib.error

    from importers.courtlistener import landmarks
    from tools.fetch import add_source
    have = {e["id"] for e in load_manifest()}
    missing = []
    for key, name in landmarks().items():
        m = US.fullmatch(key)
        if not m:
            continue  # a slip opinion: not yet in the bound volumes
        v, p = int(m.group(1)), int(m.group(2))
        if source_id(v, p) in have:
            continue
        try:
            e = add_source(source_id(v, p), PDF_URL.format(v=v, p=p), LICENSE, ext=".pdf",
                           notes=f"United States Reports, {key}: {name}, as printed (Library of Congress scan, "
                                 f"{ITEM_URL.format(v=v, p=p)}).")
        except urllib.error.HTTPError as err:
            missing.append(f"{key} ({name}): HTTP {err.code}")
            continue
        print(f"{key}: {e['path']}", flush=True)
    for m in missing:
        print(f"no PDF: {m}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m importers.usreports")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch", help="download each case's PDF from the Library of Congress")
    sy = sub.add_parser("syllabus", help="print a case's syllabus as read from its PDF")
    sy.add_argument("volume", type=int)
    sy.add_argument("page", type=int)
    args = ap.parse_args(argv)
    return {"fetch": cmd_fetch, "syllabus": cmd_syllabus}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
