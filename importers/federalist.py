"""Import The Federalist from Project Gutenberg eBook #18.

Input (sources/manifest.json id): gutenberg-federalist-18
Output: texts/federalist.json

Each paper's heading block gives its number, title, newspaper line(s) and
the edition's attribution. The salutation and the closing "PUBLIUS" are
kept as paper metadata; the paragraphs between them are numbered from 1.
Footnotes become segments Federalist.{paper}.fn{n}.

The only transformations are structural (see docs/editions.md):
  * hard-wrapped lines are joined with a single space;
  * the edition's _underscore_ italics are removed from the text and
    recorded as character spans in `emphasis`;
  * in Nos. 40-59, where the e-text lost most of its paragraph breaks,
    a paragraph is split where the 1788 McLean edition (Evans-TCP N16444,
    source tcp-evans-n16444) starts a new one (decision 70). The break is
    found by aligning the two texts word by word; only its position comes
    from McLean. No paragraph is joined and no word is taken from McLean.
Wording, spelling and punctuation are untouched.
"""

from __future__ import annotations

import datetime as dt
import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from pathlib import Path

from importers.tcp import TEI, load, tag
from tools.common import TEXTS_DIR, collapse_ws, read_raw_text, roman_to_int, write_json

SOURCE_ID = "gutenberg-federalist-18"
MCLEAN_ID = "tcp-evans-n16444"
# The papers whose paragraph breaks the e-text lost (decision 70). Elsewhere
# the e-text's paragraphs match McLean's but for a few differences in both
# directions, which are the editions' own and are left alone.
RESTORED = range(40, 60)

AUTHORS = {
    "HAMILTON": {"kind": "single", "names": ["Alexander Hamilton"]},
    "MADISON": {"kind": "single", "names": ["James Madison"]},
    "JAY": {"kind": "single", "names": ["John Jay"]},
    "HAMILTON AND MADISON": {"kind": "joint", "names": ["Alexander Hamilton", "James Madison"]},
    "HAMILTON OR MADISON": {"kind": "disputed", "names": ["Alexander Hamilton", "James Madison"]},
}
PUBLICATION = re.compile(r"^(From|For) (the |McLEAN)", re.I)  # "McLEAN" and "MCLEAN" both occur
DATE_LINE = re.compile(r"^(?:(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,? )?[A-Z][a-z]+ \d{1,2}, \d{4}\.?$")
FOOTNOTE = re.compile(r"^ ?\[(\d+)\] ?(.*)$")
EDITOR_NOTE = re.compile(r"^\*?\(?There are two slightly different versions of No\. 70 included here\.\)?$")
UNDERSCORE = re.compile(r"_([^_]+)_")


class ImportError_(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ImportError_(msg)


def _paragraphs(lines: list[str]) -> list[str]:
    """Split on blank lines; join wrapped lines with one space."""
    out, cur = [], []
    for line in lines + [""]:
        if line.strip():
            cur.append(line.strip())
        elif cur:
            out.append(" ".join(cur))
            cur = []
    return out


def _emphasis(text: str) -> tuple[str, list[list[int]]]:
    """Remove _italic_ markers; return plain text and [start, end) spans."""
    spans: list[list[int]] = []
    out: list[str] = []
    pos = 0
    length = 0
    for m in UNDERSCORE.finditer(text):
        before = text[pos:m.start()]
        out.append(before)
        length += len(before)
        inner = m.group(1)
        spans.append([length, length + len(inner)])
        out.append(inner)
        length += len(inner)
        pos = m.end()
    out.append(text[pos:])
    plain = "".join(out)
    _expect("_" not in plain, f"unpaired underscore in: {text[:80]!r}")
    return plain, spans


def _segment(ref: str, label: str, raw: str, **extra) -> dict:
    text, spans = _emphasis(collapse_ws(raw))
    seg = {"label": label, "ref": ref, "text": text}
    if spans:
        seg["emphasis"] = spans
    seg.update(extra)
    return seg


def _tei_text(el: ET.Element, out: list[str]) -> None:
    """Running text of a TEI element: notes left out, line-end hyphens joined."""
    name = tag(el)
    if name == "g":
        if el.get("ref") != "char:EOLhyphen":
            out.append(el.text or "")
    elif name == "gap":
        out.append(" \u25ca ")  # an illegible stretch: keeps words apart, matches nothing
    elif name == "lb":
        out.append(" ")
    elif name not in ("note", "pb"):
        out.append(el.text or "")
        for c in el:
            _tei_text(c, out)
    out.append(el.tail or "")


def mclean_paragraphs() -> dict[int, list[str]]:
    """McLean's paragraphs of each paper (Evans-TCP N16444), by paper number.

    A paragraph is a <p> (or a block quotation <q> standing outside one);
    consecutive verse lines <l> are one block. Headings, signatures and
    notes are left out. Used only to place paragraph breaks."""
    root = load(MCLEAN_ID)
    papers: dict[int, list[str]] = {}
    for div in root.iter(TEI + "div"):
        if div.get("type") != "number":
            continue
        paras: list[str] = []
        verse = False

        def walk(el: ET.Element) -> None:
            nonlocal verse
            name = tag(el)
            if name in ("head", "signed", "note", "pb"):
                return
            if name in ("p", "l") or (name == "q" and el.find(TEI + "p") is None):
                out = [el.text or ""]
                for c in el:
                    _tei_text(c, out)
                text = " ".join("".join(out).split())
                if name == "l" and verse:
                    paras[-1] += " " + text
                else:
                    paras.append(text)
                verse = name == "l"
                return
            for c in el:
                walk(c)

        for c in div:
            walk(c)
        n = int(div.get("n"))
        _expect(n not in papers and bool(paras), f"McLean: bad paper division {n}")
        papers[n] = paras
    _expect(sorted(papers) == list(range(1, 86)), "McLean: expected papers 1-85")
    return papers


def _key(tok: str) -> str:
    return re.sub(r"[^a-z0-9]", "", tok.lower().replace("\u017f", "s"))


# Alignment tokens: words, with dashes, and a stop (.:;?!) glued to the next
# word ("States:1."), as boundaries. Spans are character offsets.
_TOKEN = re.compile(r"[^\s\u2014\u2013-]+?(?:[.:;?!](?=[\u201c\"A-Z0-9])|(?=[\s\u2014\u2013-])|$)")


def _tokens(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), k) for m in _TOKEN.finditer(text) if (k := _key(m.group()))]


def _context(j: int, i: int, side: int, same: dict[int, int], aligned: dict[int, int]) -> bool:
    """Whether the six McLean words after (side 1) or before (side -1) word j
    align near e-text word i: three of them, two of them the same word."""
    def near(m: dict[int, int], k: int) -> bool:
        g = m.get(j + side * k)
        return g is not None and (i < g <= i + k + 2 if side > 0 else i - k - 3 <= g < i)
    return (sum(near(aligned, k) for k in range(1, 7)) >= 3
            and sum(near(same, k) for k in range(1, 7)) >= 2)


def restore_breaks(paras: list[str], mclean: list[str]) -> tuple[list[str], list[int], list[dict]]:
    """Split the e-text's paragraphs where McLean starts a paragraph.

    Both texts are aligned on normalized words (difflib). A McLean
    paragraph start is used when its first word aligns with a word of the
    e-text (the same word, or one read differently in its place), and on
    each side at least three of the six words next to it align with the
    words next to that one, at least two of them the same word (so a
    footnote marker, a respelt word or an illegible one does not stop it,
    but a passage the two editions word differently does). The e-text is
    split before the word that corresponds; its characters are kept
    exactly, only the white space at the break is dropped. A break that
    would fall inside an italic span is not made. Returns the paragraphs, the index of the
    e-text paragraph each comes from, and a report of each break made or
    passed over."""
    gk: list[str] = []
    gpos: list[tuple[int, int]] = []  # (paragraph, character offset)
    for pi, para in enumerate(paras):
        for start, _end, k in _tokens(para):
            gk.append(k)
            gpos.append((pi, start))
    mk: list[str] = []
    starts: list[int] = []
    for qi, para in enumerate(mclean):
        toks = _tokens(para)
        if qi and toks:
            starts.append(len(mk))
        mk.extend(k for _s, _e, k in toks)
    sm = SequenceMatcher(None, gk, mk, autojunk=False)
    m2g: dict[int, int] = {}    # McLean word -> e-text word, the same word
    loose: dict[int, int] = {}  # also a word read differently in the same place
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal" or (op == "replace" and a2 - a1 == b2 - b1):
            for k in range(b2 - b1):
                loose[b1 + k] = a1 + k
                if op == "equal":
                    m2g[b1 + k] = a1 + k
    cuts: dict[int, list[int]] = {}
    report: list[dict] = []
    for j in starts:
        i = loose.get(j)
        ctx = " ".join(mk[max(0, j - 5):j]) + " | " + " ".join(mk[j:j + 5])
        if i is None or not all(_context(j, i, side, m2g, loose) for side in (1, -1)):
            report.append({"action": "unaligned", "mclean": ctx})
            continue
        pi, off = gpos[i]
        if off == 0 or (i and gpos[i - 1][0] != pi):
            continue  # the e-text already breaks here
        head = paras[pi][:off]
        if head.count("_") % 2:
            report.append({"action": "inside italics", "mclean": ctx})
            continue
        cuts.setdefault(pi, []).append(off)
        report.append({"action": "split", "glued": not head[-1:].isspace(), "mclean": ctx,
                       "paragraph": pi + 1})
    out: list[str] = []
    origin: list[int] = []
    for pi, para in enumerate(paras):
        prev = 0
        for off in sorted(cuts.get(pi, [])) + [len(para)]:
            piece = para[prev:off].strip()
            _expect(bool(piece), f"empty paragraph from a McLean break in: {para[:60]!r}")
            out.append(piece)
            origin.append(pi)
            prev = off
    _expect("".join(out).replace(" ", "") == "".join(paras).replace(" ", ""),
            "restoring breaks changed the text")
    return out, origin, report


def _split_papers(text: str) -> list[list[str]]:
    lines = text.split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("*** START OF THE PROJECT GUTENBERG EBOOK"))
    end = next(i for i, l in enumerate(lines) if l.startswith("*** END OF THE PROJECT GUTENBERG EBOOK"))
    body = lines[start + 1:end]
    heads = [i for i, l in enumerate(body) if l == "THE FEDERALIST."]
    _expect(len(heads) == 86, f"expected 86 paper headings (85 papers, No. 70 twice), found {len(heads)}")
    return [body[h:(heads[k + 1] if k + 1 < len(heads) else len(body))] for k, h in enumerate(heads)]


def _parse_paper(block: list[str]) -> dict:
    _expect(block[0] == "THE FEDERALIST.", "paper must start with THE FEDERALIST.")
    sal_i = next(i for i, l in enumerate(block) if l.startswith("To the People of the State of New York"))
    pub_i = next(i for i, l in enumerate(block) if l.strip() in ("PUBLIUS.", "PUBLIUS"))
    head = [l.strip() for l in block[1:sal_i] if l.strip()]

    m = re.fullmatch(r"No\. ([IVXL]+)\.", head[0])
    _expect(m is not None, f"bad number line {head[0]!r}")
    number = roman_to_int(m.group(1))
    _expect(head[-1] in AUTHORS, f"No. {number}: unknown attribution {head[-1]!r}")
    byline = head[-1]

    notes, title_lines, publication = [], [], []
    for l in head[1:-1]:
        if EDITOR_NOTE.match(l):
            notes.append(l)
        elif PUBLICATION.match(l) or (publication and DATE_LINE.match(l)):
            publication.append(l)
        else:
            _expect(not publication, f"No. {number}: title line after publication line: {l!r}")
            title_lines.append(l)
    _expect(bool(title_lines), f"No. {number}: no title")

    paras = _paragraphs(block[sal_i + 1:pub_i])
    tail = _paragraphs(block[pub_i + 1:])
    footnotes: list[tuple[str, str]] = []
    for t in tail:
        if EDITOR_NOTE.match(t):
            notes.append(t)
            continue
        fm = FOOTNOTE.match(t)
        _expect(fm is not None, f"No. {number}: unexpected text after PUBLIUS: {t[:60]!r}")
        footnotes.append((fm.group(1), fm.group(2)))

    return {
        "byline": byline,
        "footnotes": footnotes,
        "notes": notes,
        "number": number,
        "numeral": m.group(1),
        "paragraphs": paras,
        "publication": publication,
        "salutation": block[sal_i].strip(),
        "signature": block[pub_i].strip(),
        "title": " ".join(title_lines),
    }


def import_federalist(report: dict | None = None) -> dict:
    papers = [_parse_paper(b) for b in _split_papers(read_raw_text(SOURCE_ID))]
    numbers = [p["number"] for p in papers]
    _expect(numbers == list(range(1, 71)) + [70] + list(range(71, 86)), "papers out of order")
    mclean = mclean_paragraphs()
    renumbered: list[dict] = []
    for p in papers[:70] + papers[71:]:  # not the unsegmented second No. 70
        if p["number"] in RESTORED:
            n = p["number"]
            before = len(p["paragraphs"])
            p["paragraphs"], origin, found = restore_breaks(p["paragraphs"], mclean[n])
            # The refs these paragraphs had before decision 70, and where their text is now.
            for k in range(before):
                now = [f"Federalist.{n}.{i}" for i, o in enumerate(origin, 1) if o == k]
                if now != [f"Federalist.{n}.{k + 1}"]:
                    renumbered.append({"decision": 70, "now": now, "ref": f"Federalist.{n}.{k + 1}"})
            if report is not None:
                report[p["number"]] = {"before": before, "after": len(p["paragraphs"]),
                                       "mclean": len(mclean[p["number"]]), "breaks": found}

    # The edition prints two versions of No. 70; the first is the base text.
    # The second is kept, unsegmented, as `variants` on the division.
    second_70 = papers.pop(70)
    _expect(second_70["number"] == 70, "expected second No. 70 at position 71")

    divisions: list[dict] = []
    segments: list[dict] = []
    for p in papers:
        n = p["number"]
        div = {
            "attribution": {**AUTHORS[p["byline"]], "byline": p["byline"]},
            "label": f"Federalist No. {n}",
            "level": 1,
            "numeral": p["numeral"],
            "publication": p["publication"],
            "ref": f"Federalist.{n}",
            "salutation": p["salutation"],
            "signature": p["signature"],
            "title": p["title"],
        }
        if p["notes"]:
            div["notes"] = [{"source_id": SOURCE_ID, "text": t} for t in p["notes"]]
        if n == 70:
            div["variants"] = [{
                "note": "Second version of No. 70 as printed in the base edition; not segmented.",
                "paragraphs": [_emphasis(collapse_ws(x))[0] for x in second_70["paragraphs"]],
                "publication": second_70["publication"],
            }]
        divisions.append(div)
        for i, para in enumerate(p["paragraphs"], 1):
            segments.append(_segment(f"Federalist.{n}.{i}", f"Federalist No. {n}, ¶ {i}", para))
        seen = set()
        for num, body in p["footnotes"]:
            _expect(num not in seen, f"No. {n}: duplicate footnote {num}")
            seen.add(num)
            segments.append(_segment(f"Federalist.{n}.fn{num}", f"Federalist No. {n}, note {num}", body,
                                     kind="footnote"))

    return {
        "attribution": {"kind": "pseudonym", "names": ["Alexander Hamilton", "James Madison", "John Jay"],
                        "pseudonym": "Publius"},
        "date": _date_range(divisions),
        "divisions": divisions,
        "edition": {
            "name": "Project Gutenberg eBook #18",
            "notes": "See docs/editions.md. Wording, footnotes, newspaper lines and attributions "
                     "follow the base edition, and so does its paragraphing, except that in Nos. 40-59, "
                     "where the e-text lost paragraph breaks, the breaks of the 1788 McLean edition "
                     "(Evans-TCP N16444) are restored (decision 70). Italics are recorded as emphasis spans.",
        },
        "id": "federalist",
        "ref_prefix": "Federalist",
        "renumbered": renumbered,
        "segments": segments,
        "source_ids": [SOURCE_ID, MCLEAN_ID],
        "title": "The Federalist",
    }


def _date_range(divisions: list[dict]) -> str:
    """Earliest/latest dates printed in the edition's newspaper lines."""
    found = []
    for d in divisions:
        for line in d["publication"]:
            m = re.search(r"([A-Z][a-z]+) (\d{1,2}), (\d{4})", line)
            if m:
                found.append(dt.datetime.strptime(" ".join(m.groups()), "%B %d %Y").date())
    _expect(bool(found), "no dated publication lines")
    return f"{min(found).isoformat()}/{max(found).isoformat()}"


def run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    path = out_dir / "federalist.json"
    write_json(path, import_federalist())
    return [path]


if __name__ == "__main__":
    for p in run():
        print(f"wrote {p}")
