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
                 r"|^Opinion of the Court|^Statement of the Case|^Counsel for"
                 r"|^T(HE|he) (case|facts) (is|are) stated\b")   # "THE case is stated in the opinion."
# A paragraph that matches any of these, and all after it, are not syllabus:
# counsel, the lineup of the Justices' opinions, notes of separate opinions.
AFTER = re.compile(r"argued(?: the cause| for|$)|submitted (on )?(the|a|his|their) briefs?|\bon (the|his|their) briefs?\b"
                   r"|\bamic(i|us) curiae,? (urging|filed|in support)|^Mr\. [A-Z]|^Messrs\.|\bpost, p\. ?\d+"
                   r"|\bfiled (a |an )?(\w+ )*opinions?\b|^For (the )?(\w+ )*opinions? of"
                   r"|\bfor (appellants?|appellees?|petitioners?|respondents?|plaintiffs? in error|defendants? in error)( in [^.]*)?\.$|\bpost,$")
# A printer's mark at the foot of a page: "S994084 0-52---41".
PRINTER_MARK = re.compile(r"^\S*\d{5,}\S*( [\d-]+)?$|^\d+-\d+-+\d+$"
                          # the slug at the head of each page of a preliminary print:
                          # "554US2 Unit: $U71 [01-05-13 17:53:27] PAGES PGT: OPIN"
                          r"|^\d+US\d\S* Unit: ")
# A speck the OCR read as a mark of its own: no letter or figure, a few points wide.
SPECK_WIDTH = 6
SHEET = 16  # pages to a printed sheet: pages 1, 17, 33, ... begin one
NOTE = re.compile(r"^[*†‡]|^\S?N[Oo][Tt][Ee]:")    # a footnote ("*Together with No. 2, ...")
RUNNING_HEAD = re.compile(r"^(\d+ )?Syllabus\.?( \d+ U\. ?S\.)?$|^Cite as: \d+ U\. ?S\. \d+ \(\d{4}\)( \d+)?$|^VOL\. [CLXVI]+")
# More of the dates: "Reargued October 22-23, 1958." or "March 31, 1958.*" on a line of its own,
# or the year alone ("1977").
DATE_MORE = re.compile(r"\b(Argued|Reargued|Decided|Submitted|reargument|Opinion announced)\b"
                       r"|^[A-Z][a-z]+\.? \d{1,2}(-\d+)?, \d{4}\.?\*?$|^(?=[a-z\d]).*(\d{1,2}, \d{4}\.|\d{4}\.-)"
                       r"|^\d{4}\.?\*?$")
# Where no opinion has a majority throughout, the syllabus goes on after the
# judgment line with what each opinion concluded, a part to each: "JUSTICE
# WHITE delivered the opinion of the Court with respect to Part II,
# concluding that ...". The Justice's title comes before the name, unlike the
# lineup that follows the syllabus ("WHITE, J., delivered the opinion ...").
PART_HEAD = re.compile(r"^(\d+\. )?(THE CHIEF JUSTICE|(CHIEF )?JUSTICE [A-Z][A-Z'’]+|(Chief )?Justice [A-Z][a-z'’]+\w*)"
                       r"( and (JUSTICE|Justice) [A-Z][\w'’]+)?,? (delivered|announced)\b")
CONCLUDING = re.compile(r"\bconclud(ing|ed)\b")
HEAD_GAP = 30                   # running heads: within this of the page's top line
# In the volumes that print no dates (to 1882) the running head is one line,
# with no subhead under it, and the small type of a syllabus can follow it
# within HEAD_GAP: only the top line is the head.
HEAD_GAP_UNDATED = 3


@dataclass
class Paragraph:
    text: str
    page: int           # the printed page it starts on


DATE_PAGES = 2  # the case's dates are on its first page (an "Argued" later on is in the opinion)
SYLLABUS_PAGES = 24  # the syllabus, with the counsel after it, fits in the first pages (McConnell: 19)


@lru_cache(maxsize=None)
def _pages(volume: int, page: int) -> list[list[Line]]:
    return pdf_lines(raw_path(source_id(volume, page)), max_pages=SYLLABUS_PAGES)


def _merge_fragments(lines: list[Line]) -> list[Line]:
    """OCR sometimes breaks one printed line into pieces a few points apart
    vertically ("2. The. statute and resolution" | "did not violate"); put
    them back together, left to right. A piece on the left that reads a
    little lower than the rest of its line ("have been" | "upheld, since it
    was ...") comes after it top to bottom, and goes in front of it."""
    out: list[Line] = []
    last_y = None  # baseline of the last piece joined
    for line in sorted(lines, key=lambda l: l.y):
        prev = out[-1] if out else None
        if prev and abs(line.y - last_y) <= 6 and line.x0 > prev.x0 + 20:
            out[-1] = Line(prev.y, prev.x0, line.x1, prev.size, f"{prev.text} {line.text}")
        elif prev and abs(line.y - last_y) <= 3 and line.x0 < prev.x0 - 10 and line.x1 <= prev.x0 + 15:
            out[-1] = Line(prev.y, line.x0, prev.x1, prev.size, f"{line.text} {prev.text}")
        else:
            out.append(line)
        last_y = line.y
    return out


# The case's name over the syllabus, in the volumes that print no dates
# ("REYNOLDS V. UNITED STATES."): a line set centered.
TITLE = re.compile(r"\b[vV]\. |^EX PARTE\b")
# A footnote's first line, marked with a figure or a sign that OCR may misread
# ("1 \"You are hereby ...", "&Several attempts ..." for "8 Several").
# A line with nothing but the pages of the opinion a paragraph refers to,
# which ends that paragraph and never starts one ("P. 135.", "Pp. 11-14.").
PAGE_REF = re.compile(r"^Pp?\. ?\d+([-–—]+\d+)?(, \d+([-–—]+\d+)?)*\.$")
FOOTNOTE = re.compile(r"^(\d{1,2} ?[\"“'A-Z]|[&§¶][A-Z])")


def _speck(line: Line) -> bool:
    return line.x1 - line.x0 <= SPECK_WIDTH and not any(c.isalnum() for c in line.text)


def _drop_signature(lines: list[Line], printed_page: int) -> list[Line]:
    """Without the signature mark at the foot of the first page of a printed
    sheet: the volume and the sheet's number ("VOL. CCIII-1", which OCR reads
    "Vol,. ccIlI -1 1"; "VOL. VIII. 10" read "'oVl Til. 10"). Taken only on
    a sheet's first page, as the page's last line, of a few words, the first
    with a V in it, and the last the number of the sheet."""
    if (printed_page - 1) % SHEET or not lines:
        return lines
    last = max(lines, key=lambda l: l.y)
    words = last.text.split()
    if len(words) <= 4 and "v" in words[0].lower() and words[-1].strip(".-—–") == str((printed_page - 1) // SHEET + 1):
        return [l for l in lines if l is not last]
    return lines


def _title(lines: list[Line]) -> int | None:
    """Where the case's name is printed on its first page, in the volumes
    whose syllabus follows the name with no dates between (before 1882):
    the first line below the running head that names the parties ("v.") and
    is set centered, well in from both sides of the text."""
    if not lines:
        return None
    top = lines[0].y
    below = [l for l in lines if l.y > top + HEAD_GAP]
    if not below:
        return None
    left, right = min(l.x0 for l in below), max(l.x1 for l in below)
    for k, line in enumerate(lines):
        a, b = line.x0 - left, right - line.x1
        if line.y > top + HEAD_GAP and TITLE.search(line.text) and a >= 30 and b >= 30 and abs(a - b) <= 25:
            return k
    return None


def _starts_lower(text: str) -> bool:
    """Whether a line begins with a small letter, past any specks before it ("-- from")."""
    return text.lstrip("-–—•·' ")[:1].islower()


def _mid_sentence(text: str) -> bool:
    """Whether a line stops mid-sentence; a word with a quote mark after
    it and no stop ("Clause to'") does too, OCR's reading of a speck."""
    return not (SENTENCE_END.search(text) or DISPOSITION.search(text)) or bool(re.search(r"[A-Za-z]['’]$", text))


def _continues(last: Line, last_full: bool, line: Line, prev: Line | None, right: float, leading: float) -> bool:
    """Whether a line that looks like the start of a paragraph (off the
    margin) carries on the one before it: the line before it is full and
    stops mid-sentence, and either this line begins with a small letter
    (a hanging indent's turnover, or the rest of a paragraph broken by the
    page) or, on the same page and at the usual spacing, it starts where
    the line before it starts (a turnover set deeper than the margin)."""
    if not _mid_sentence(last.text):
        return False
    lower = _starts_lower(line.text)
    if prev is None:  # the first line on a page, after the paragraph's last on the page before
        return last_full and lower
    if prev.x1 < right - 25 or line.y - prev.y > 1.5 * leading:
        return False
    return lower or abs(line.x0 - prev.x0) <= 3


def _carries_on(take: list[Line], line: Line) -> bool:
    """Whether a line read as larger type is the rest of a sentence: it
    begins with a small letter, at the usual spacing below a full line that
    stops mid-sentence (OCR reads the size of a line with italics in it a
    point or two large)."""
    if len(take) < 3 or not line.text[:1].islower() or not _mid_sentence(take[-1].text):
        return False
    gaps = sorted(b.y - a.y for a, b in zip(take, take[1:]))
    right = sorted(l.x1 for l in take)[len(take) // 2]
    return line.y - take[-1].y <= 1.5 * gaps[len(gaps) // 2] and take[-1].x1 >= right - 25


def _part_head(lines: list[Line], k: int) -> bool:
    """Whether line k begins a part of the syllabus for one opinion (PART_HEAD),
    which says within its first lines what the opinion concluded."""
    return bool(PART_HEAD.match(lines[k].text)) and bool(CONCLUDING.search(" ".join(l.text for l in lines[k:k + 4])))


def _next_item(lines: list[Line], line: Line) -> bool:
    """Whether a line on the margin starts the next numbered paragraph:
    "5. ..." after a paragraph numbered "4." that ends a sentence (the
    numbers of a hanging indent stand out from the margin, but at the head
    of a page with few lines the margin is theirs)."""
    m = re.match(r"(\d+)\. ", lines[0].text)
    return bool(m) and line.text.startswith(f"{int(m.group(1)) + 1}. ") and not _mid_sentence(lines[-1].text)


def syllabus(volume: int, page: int) -> list[Paragraph]:
    """The syllabus as printed: the paragraphs after the line with the
    case's dates ("Argued ... Decided ..."), set in smaller type than what
    follows, up to the counsel, the statement of the case or the opinion.
    In the first volumes, which print no dates, the paragraphs after the
    case's name, up to the larger type that follows them. Footnotes,
    running heads, folios and signature marks are left out; words broken
    at a line end are rejoined. Empty when the volume has no syllabus to
    read (before FIRST_SYLLABUS_VOLUME) or none is found."""
    if volume < FIRST_SYLLABUS_VOLUME:
        return []
    pages = [_merge_fragments([l for l in _drop_signature(pg, page + i)
                               if not l.text.strip().isdigit() and not PRINTER_MARK.match(l.text)
                               and not _speck(l)])
             for i, pg in enumerate(_pages(volume, page))]
    dated = any(DATE_LINE.search(l.text) for pg in pages[:DATE_PAGES] for l in pg)
    paras: list[tuple[int, list[Line]]] = []
    size = None  # the syllabus's type size, from its first lines
    started = ended = False
    last_full = False  # whether the last line taken runs the full measure
    for i, lines in enumerate(pages):
        if not started:
            if dated:
                at = next((k for k, l in enumerate(lines) if DATE_LINE.search(l.text)), None)
                if at is None:
                    continue
                while at + 1 < len(lines) and DATE_MORE.search(lines[at + 1].text):
                    at += 1
            else:  # no dates: the syllabus follows the case's name, on its first page
                at = _title(lines)
                if at is None:
                    return []
            lines, started = lines[at + 1:], True
            first = [l.size for l in lines[:5]]
            if not first:
                return []
            size = sorted(first)[len(first) // 2]
        elif lines:
            top = lines[0].y  # running heads: the lines at the head of the page
            lines = [l for l in lines if l.y > top + (HEAD_GAP if dated else HEAD_GAP_UNDATED)]
        # The syllabus on this page ends at larger type or at what follows it.
        take, ended = [], False
        big = [l.size >= size + 1.5 for l in lines]
        for k, line in enumerate(lines):
            if END.search(line.text) and (take or paras) and not _part_head(lines, k):
                ended = True
                break
            # Larger type, for two lines running (OCR misjudges a single line's size now and then),
            # unless the line plainly carries on a sentence the line before it left unfinished.
            if big[k] and (k + 1 == len(lines) or big[k + 1]) and not _carries_on(take, line):
                ended = True
                break
            take.append(line)
        body = [l for l in take if not RUNNING_HEAD.match(l.text)]
        # A footnote starts with its mark after a wider gap than the lines above it;
        # one marked with a figure, only where the line above it stops mid-sentence.
        gaps = sorted(b.y - a.y for a, b in zip(body, body[1:])) or [0]
        leading = gaps[len(gaps) // 2]
        note = next((k for k, l in enumerate(body)
                     if (NOTE.match(l.text) and (k == 0 or l.y - body[k - 1].y > 1.4 * leading))
                     or (k > 0 and FOOTNOTE.match(l.text) and l.y - body[k - 1].y > 1.25 * leading
                         and _mid_sentence(body[k - 1].text) and not JUDGMENT.search(l.text))), None)
        if note is not None:
            body = body[:note]  # footnotes run to the foot of the page
        if body:
            xs = [l.x0 for l in body]  # the margin: where most lines start, give or take skew
            margin = max(xs, key=lambda x: sum(abs(y - x) <= 3 for y in xs))
            right = sorted(l.x1 for l in body)[len(body) // 2]
            prev = None  # the line before, on this page
            for j, line in enumerate(body):
                # A paragraph starts on a line indented (or, for a hanging
                # indent, outdented) from the margin, or after a short line;
                # unless the line plainly carries on the one before it.
                new = not paras or abs(line.x0 - margin) > 6 or (prev is not None and prev.x1 < right - 25)
                if new and paras and (_continues(paras[-1][1][-1], last_full, line, prev, right, leading)
                                      or PAGE_REF.match(line.text)):
                    new = False
                elif not new and paras and _next_item(paras[-1][1], line):
                    new = True
                if new:
                    if END.search(line.text) and not _part_head(body, j):
                        ended = True
                        break
                    paras.append((page + i, [line]))
                else:
                    paras[-1][1].append(line)
                last_full = line.x1 >= right - 25
                prev = line
        if ended:
            break
    if not dated and not ended:
        return []  # without dates to start from, only a syllabus closed by the larger type after it
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
    parts = False  # past the judgment, in the parts for each opinion
    for n, lines in paras:
        text = ""
        for line in lines:
            t = re.sub(r"\s+", " ", line.text).strip()
            text = join_across(text, t) if text else t
        # The judgment line ("108 F. 2d 683, reversed.") closes the syllabus;
        # only another judgment line may follow it (one per case decided).
        # After it may come the parts for each opinion, up to the lineup.
        if out and JUDGMENT.search(out[-1].text) and PART_HEAD.match(text) and CONCLUDING.search(text):
            parts = True
        elif AFTER.search(text) or (not parts and out and JUDGMENT.search(out[-1].text)
                                    and not JUDGMENT.search(text)):
            if RUN_IN.search(text):
                out.append(Paragraph(text, n))  # paragraphs run together: left for problems() to refuse
            break
        out.append(Paragraph(text, n))
    return out


SENTENCE_END = re.compile(r"[.:;?!)\]\"'”’][^\w\s]{0,2}( [-•])?$|^Held\W?$|\bPp?\. \d+(-\d+)?$")
DISPOSITION = re.compile(r"\b(af+[ﬁi]?r?m?ed|aff?ied|reversed|remanded|vacated|dismissed|modified|granted|denied|"
                         r"overruled|answered|discharged|ordered)\b[^a-z]*$", re.I)


JUDGMENT = re.compile(r"^(No[s]?\. [\w ,-]+[,.] )?\d[^a-z]*\b[A-Z][\w.' ]*\d+.{0,120}\b(af+[ﬁi]?r?m?ed|reversed|remanded|vacated|"
                      r"dismissed|modified)\b[^a-z]{0,3}$|^(No\. .*)?(Affirmed|Reversed|Dismissed)\.$")


# A paragraph that leads into lettered or numbered parts with a dash
# ("... are beyond the powers of Congress, because-"), and the first part.
LEADS_IN = re.compile(r"[A-Za-z][-—–]$")
FIRST_PART = re.compile(r"^\((a|1|i)\) ")


# A judgment with the lineup of opinions or the counsel after it in one
# paragraph: the breaks between the last paragraphs were missed, and what
# came before the judgment may have run together too.
RUN_IN = re.compile(r"\d.{0,120}?\b(af+[ﬁi]?r?m?ed|reversed|remanded|vacated|dismissed|modified)( in part)?\.\s"
                    r".*(\bpost, pp?\. ?\d|\bJJ?\., (joined|filed|took)|argued the cause)")


def problems(paras: list[Paragraph]) -> list[str]:
    """Why a syllabus as read looks incomplete or out of order: a paragraph
    that stops mid-sentence (the text layer lost its order, or the end of
    the syllabus was missed), or a last paragraph that is neither a
    sentence nor the judgment ("74 N. J. L. 683, affirmed."). A paragraph
    may end with the dash that leads into its parts when the next paragraph
    is the first of them ("(a) ...")."""
    out = []
    if not paras:
        return ["no syllabus found"]
    for k, p in enumerate(paras, 1):
        if RUN_IN.search(p.text):
            out.append(f"paragraph {k} (p. {p.page}) runs the judgment into what follows it")
        elif not (SENTENCE_END.search(p.text) or (k == len(paras) and DISPOSITION.search(p.text))
                or (k < len(paras) and LEADS_IN.search(p.text) and FIRST_PART.match(paras[k].text))):
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
