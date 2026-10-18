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
    recorded as character spans in `emphasis`.
Wording, spelling and punctuation are untouched.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from tools.common import TEXTS_DIR, collapse_ws, read_raw_text, roman_to_int, write_json

SOURCE_ID = "gutenberg-federalist-18"

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


def import_federalist() -> dict:
    papers = [_parse_paper(b) for b in _split_papers(read_raw_text(SOURCE_ID))]
    numbers = [p["number"] for p in papers]
    _expect(numbers == list(range(1, 71)) + [70] + list(range(71, 86)), "papers out of order")

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
            "notes": "See docs/editions.md. Paragraphing, footnotes, newspaper lines and attributions "
                     "follow the base edition. Italics are recorded as emphasis spans.",
        },
        "id": "federalist",
        "ref_prefix": "Federalist",
        "segments": segments,
        "source_ids": [SOURCE_ID],
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
