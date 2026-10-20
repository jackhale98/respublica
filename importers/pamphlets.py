"""Import pamphlets of the ratification debate from the Text Creation
Partnership's typed transcriptions of their first printings (decision 69).

Inputs (sources/manifest.json ids): tcp-n16431, tcp-n16481, tcp-n16378,
tcp-n16445, tcp-n16126, tcp-n16546, tcp-n16547 (importers/tcp.py).
Outputs: texts/{work_id}.json, one per work (refs `{Name}.{paragraph}` for
a single piece, `{Name}.{part}.{paragraph}` for one in parts).

The TCP text is the text: nothing is typed, modernized or filled in. Words
holding something the keyers could not read are marked uncertain with the
transcription's own placeholder as the only reading. No scan of these
printings was found on the Internet Archive to check the transcription
against (docs/editions.md), so nothing else is marked.

Each work names the TCP file, the division of it each part comes from, and
what the TCP's header must say of the printing (its Evans number, imprint
and pages), which the import checks before it reads a word. A part's
headings and the date line before its salutation are its heading lines,
its salutation and its closing (signature, place and date) are fields of
its division, as in the other works of the debate; its paragraphs, list
items and quotations set apart are passages, and its notes are footnotes
(`{part}.fn{k}`). The title page is not imported (the work's title and
edition name the printing), nor the printer's "FINIS."
"""

from __future__ import annotations

import re
from pathlib import Path

from importers import corrections, tcp
from tools.common import TEXTS_DIR, write_json


class ImportError_(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ImportError_(msg)


# A part: the division it comes from (front, body or back matter; the TEI
# division's type; which of that type, from 0), its ref ("" for the one part
# of a single piece), label and numeral (shown on the work's page; "" for
# none; the label's last word if not given). `lead`: a division whose headings are the
# part's first heading lines (a pamphlet's caption title over its first
# number). `extra`: a division read as one passage (a dedication, a list
# of errata), named by `ref`, before (`at: "start"`) or after the text.
# The four members of the House of Delegates who sent Randolph's letter to
# the printer, as they sign their letters.
SMITH = {"byline": "M. Smith, Charles M. Thruston, John H. Briggs, Mann Page, jun.", "kind": "body",
         "names": ["M. Smith, Charles M. Thruston, John H. Briggs and Mann Page, jun."],
         "source": "their signatures, pp. [1]-[2] (Evans-TCP N16126)"}

WORKS = [
    {
        "tcp": "N16431", "work_id": "columbian-patriot", "slug": "ColumbianPatriot",
        "title": "Observations on the New Constitution, and on the Foederal and State Conventions",
        "short": "A Columbian Patriot", "position": "anti", "date": "1788",
        "expect": {"evans": "Evans 21112", "publisher": "Boston, printed, New-York re-printed [by Thomas Greenleaf]",
                   "date": "1788", "pages": 22},
        "attribution": {"byline": "By a Columbian Patriot (the title page); attributed to Mercy Otis Warren",
                        "kind": "pseudonym", "names": ["Mercy Otis Warren"], "pseudonym": "A Columbian Patriot",
                        "source": "the catalogue record of Evans-TCP N16431: \"Attributed to Mercy Otis Warren in: "
                                  "Warren, Charles. 'Elbridge Gerry, James Warren, Mercy Warren and the ratification "
                                  "of the federal Constitution in Massachusetts.' Proceedings of the Massachusetts "
                                  "Historical Society 64 (1932): 143-164. Commonly attributed to Elbridge Gerry.\""},
        "parts": [{"div": ("body", "text", 0), "ref": "", "label": "A Columbian Patriot"}],
    },
    {
        "tcp": "N16481", "work_id": "jay-address", "slug": "JayAddress",
        "title": "An Address to the People of the State of New-York, on the Subject of the Constitution",
        "short": "A Citizen of New-York", "position": "federalist", "date": "1788",
        "expect": {"evans": "Evans 21175", "publisher": "Printed by Samuel and John Loudon", "date": "1788",
                   "pages": 19},
        "attribution": {"byline": "A Citizen of New-York (the signature, p. 19); attributed to John Jay",
                        "kind": "pseudonym", "names": ["John Jay"], "pseudonym": "A Citizen of New-York",
                        "source": "the catalogue record of Evans-TCP N16481: \"Attribution to John Jay and publication "
                                  "date supplied in: Ford, Paul Leicester. Bibliography and reference list of the "
                                  "history and literature relating to the adoption of the Constitution of the United "
                                  "States 1787-8. Brooklyn, N.Y. : 1896, p. 22.\""},
        "parts": [{"div": ("body", "address", 0), "ref": "", "label": "A Citizen of New-York"}],
    },
    {
        "tcp": "N16378", "work_id": "coxe-examination", "slug": "CoxeExamination",
        "title": "An Examination of the Constitution for the United States of America",
        "short": "An American Citizen", "position": "federalist", "date": "1788",
        "expect": {"evans": "Evans 21028", "publisher": "Printed by Zachariah Poulson, Junr.", "date": "1788",
                   "pages": 33},
        "attribution": {"byline": "By an American Citizen (the title page); attributed to Tench Coxe",
                        "kind": "pseudonym", "names": ["Tench Coxe"], "pseudonym": "An American Citizen",
                        "source": "the catalogue record of Evans-TCP N16378: \"Attributed to Tench Coxe by Evans.\""},
        "parts": [
            {"div": ("front", "to_the_reader", 0), "ref": "Preface", "label": "To the Candid Reader", "numeral": ""},
            *({"div": ("body", "part", k), "ref": str(k + 1), "label": f"Number {r}", "numeral": r,
               **({"lead": ("body", "text", 0)} if k == 0 else {})} for k, r in enumerate(["I", "II", "III", "IV"])),
        ],
    },
    {
        # Printed in the same pamphlet, after Coxe's four numbers (pp. [25]-33).
        "tcp": "N16378", "work_id": "wilson-speech", "slug": "WilsonSpeech",
        "title": "Substance of an Address to a Meeting of the Citizens of Philadelphia",
        "short": "James Wilson's Speech", "position": "federalist", "date": "1787-10-06",
        "expect": {"evans": "Evans 21028", "publisher": "Printed by Zachariah Poulson, Junr.", "date": "1788",
                   "pages": 33},
        "attribution": {"byline": "Delivered, October sixth, MDCCLXXXVII, by the Honorable James Wilson, Esquire",
                        "kind": "single", "names": ["James Wilson"],
                        "source": "the heading of the speech, p. [25], in Coxe's pamphlet (Evans-TCP N16378)"},
        "parts": [{"div": ("body", "speech", 0), "ref": "", "label": "James Wilson's Speech"}],
    },
    {
        "tcp": "N16445", "work_id": "aristides", "slug": "Aristides",
        "title": "Remarks on the Proposed Plan of a Federal Government",
        "short": "Aristides", "position": "federalist", "date": "1788-01-01",
        "expect": {"evans": "Evans 21131", "publisher": "Printed by Frederick Green", "date": "1788", "pages": 42},
        "attribution": {"byline": "By Aristides (the title page and the signature); attributed to Alexander Contee "
                                  "Hanson", "kind": "pseudonym", "names": ["Alexander Contee Hanson"],
                        "pseudonym": "Aristides",
                        "source": "the catalogue record of Evans-TCP N16445: \"Signed on p. 42: Aristides. Annapolis, "
                                  "January 1, 1788. Attributed to Hanson in the Dictionary of American biography.\""},
        "parts": [{"div": ("body", "text", 0), "ref": "", "label": "Aristides",
                   "extra": [{"div": ("front", "dedication", 0), "ref": "Dedication", "label": "dedication",
                              "at": "start"}]}],
    },
    {
        "tcp": "N16126", "work_id": "randolph-letter", "slug": "RandolphLetter",
        "title": "A Letter of His Excellency Edmund Randolph, Esquire, on the Federal Constitution",
        "short": "Edmund Randolph", "position": "other", "date": "1787-10-10",
        "expect": {"evans": "Evans 20669", "publisher": "Printed by Augustine Davis", "date": "1787", "pages": 16},
        "attribution": {"byline": "Edmund Randolph", "kind": "single", "names": ["Edmund Randolph"],
                        "source": "the heading of the letter, p. [3], and its signature, p. 16 (Evans-TCP N16126)"},
        "parts": [
            {"div": ("front", "to_printer", 0), "ref": "Printer", "label": "To the Printer", "numeral": "",
             "attribution": SMITH},
            {"div": ("front", "letter", 0), "ref": "Request", "label": "Letter of December 2, 1787", "numeral": "",
             "attribution": SMITH},
            {"div": ("front", "letter", 1), "ref": "Reply", "label": "Reply of December 10, 1787", "numeral": ""},
            {"div": ("body", "letter", 0), "ref": "Letter", "label": "Letter of October 10, 1787", "numeral": ""},
        ],
    },
    {
        "tcp": "N16546", "work_id": "monroe-observations", "slug": "Monroe",
        "title": "Some Observations on the Constitution",
        "short": "James Monroe", "position": "anti", "date": "1788",
        "expect": {"evans": "Evans 21263", "publisher": "s.n.", "date": "1788", "pages": 24},
        "attribution": {"byline": "Attributed to James Monroe", "kind": "single", "names": ["James Monroe"],
                        "source": "the catalogue record of Evans-TCP N16546, whose author heading is \"Monroe, James, "
                                  "1758-1831\": \"The only known copy, held by the Library of Congress, lacks the title "
                                  "page. Title from caption title.\" \"Imprint supplied by Evans\""},
        "parts": [{"div": ("body", "text", 0), "ref": "", "label": "James Monroe",
                   "extra": [{"div": ("back", "errata", 0), "ref": "Errata", "label": "errata", "at": "end"}]}],
    },
    {
        "tcp": "N16547", "work_id": "native-of-virginia", "slug": "NativeOfVirginia",
        "title": "Observations upon the Proposed Plan of Federal Government",
        "short": "A Native of Virginia", "position": "federalist", "date": "1788",
        "expect": {"evans": "Evans 21264", "publisher": "Printed by Hunter and Prentis", "date": "1788", "pages": 64},
        "attribution": {"byline": "By a Native of Virginia (the title page); attributed to James Monroe by Evans",
                        "kind": "pseudonym", "names": ["James Monroe"], "pseudonym": "A Native of Virginia",
                        "source": "the catalogue record of Evans-TCP N16547: \"Attributed to James Monroe by Evans.\""},
        "parts": [
            {"div": ("body", "text", 0), "ref": "Observations", "label": "Observations", "numeral": ""},
            {"div": ("body", "discussion_of_constitution", 0), "ref": "Plan", "label": "Plan of the Constitution",
             "numeral": ""},
            *({"div": ("body", "article", k), "ref": f"Article{k + 1}", "label": f"Article {r}", "numeral": r}
              for k, r in enumerate(["I", "II", "III", "IV", "V", "VI"])),
            {"div": ("body", "note", 0), "ref": "Note", "label": "Note", "numeral": ""},
            {"div": ("body", "to_the_reader", 0), "ref": "ToTheReader", "label": "To the Reader", "numeral": ""},
            {"div": ("back", "errata", 0), "ref": "Errata", "label": "Errata", "numeral": ""},
        ],
    },
]

FINIS = re.compile(r"^FINIS\.?$")


def check_header(work: dict) -> dict:
    """The TCP header must name this printing, and its pages must all be there."""
    sid = tcp.source_id(work["tcp"])
    root = tcp.load(sid)
    h = tcp.header(root)
    want = work["expect"]
    _expect(h["tcp"] == work["tcp"], f"{sid}: the header's TCP number is {h['tcp']!r}")
    _expect(h["catalogue"] == want["evans"], f"{sid}: the header's Evans number is {h['catalogue']!r}")
    _expect(want["publisher"] in h["publisher"], f"{sid}: the imprint reads {h['publisher']!r}")
    _expect(want["date"] in h["date"], f"{sid}: the date reads {h['date']!r}")
    _expect(h["extent"].startswith(f"{want['pages']}"), f"{sid}: the extent reads {h['extent']!r}")
    _expect("Creative Commons 0 1.0 Universal" in h["licence"], f"{sid}: the licence reads {h['licence']!r}")
    # Every page has a page break, in order: between two numbered pages, as
    # many breaks as their numbers are apart; the last numbered page is the
    # last the catalogue counts.
    pbs = [pb.get("n") or "" for pb in root.find(f"{tcp.TEI}text").iter(f"{tcp.TEI}pb")]
    numbered = [(i, int(n)) for i, n in enumerate(pbs) if n.isdigit()]
    _expect(all(b[1] - a[1] == b[0] - a[0] for a, b in zip(numbered, numbered[1:]))
            and numbered[-1][1] == want["pages"], f"{sid}: pages missing or out of order: {pbs}")
    return h


def find(divs: list[tcp.Division], sel: tuple[str, str, int]) -> tcp.Division:
    part, kind, k = sel
    found = [d for d in divs if d.part == part and d.type == kind]
    _expect(k < len(found), f"no division {sel}")
    return found[k]


def joined(blocks: list[tcp.Block], sep: str = " ") -> tuple[str, list[dict]]:
    """Blocks as one line (or, with sep "\\n", a line each), with the words
    holding a gap as uncertain spans."""
    parts, spans, at = [], [], 0
    for b in blocks:
        spans += [{**s, "end": s["end"] + at, "start": s["start"] + at} for s in tcp.gap_spans(b)]
        parts.append(b.text)
        at += len(b.text) + len(sep)
    return sep.join(parts), spans


def segment(ref: str, label: str, blocks: list[tcp.Block], kind: str | None = None) -> dict:
    text, spans = joined(blocks, "\n")
    text, spans, fixed = corrections.apply(ref, text, spans)
    pages = list(dict.fromkeys(p for b in blocks for p in b.pages))
    seg = {"label": label, "pages": pages, "ref": ref, "text": text}
    if kind:
        seg["kind"] = kind
    if spans:
        seg["uncertain"] = spans
    if fixed:
        seg["corrected"] = fixed
    return seg


def read_part(work: dict, divs: list[tcp.Division], part: dict) -> tuple[dict, list[dict]]:
    """A part's division and its passages."""
    d = find(divs, part["div"])
    single = part["ref"] == ""
    base = work["slug"] if single else f"{work['slug']}.{part['ref']}"
    label = part["label"] if single else f"{work['short']}, {part['label']}"
    heads = [b for b in find(divs, part["lead"]).blocks() if b.kind == "head"] if part.get("lead") else []
    salute, body, closing, notes = [], [], [], []
    for b in d.blocks():
        if b.kind == "note":
            notes.append(b)
        elif b.kind in ("head", "dateline") and not body:
            heads.append(b)  # (a date line above or under the salutation)
        elif b.kind == "salute" and not body:
            salute.append(b)
        elif b.kind == "p" or (b.kind == "head" and body):
            _expect(not closing, f"{base}: text after the signature: {b.text[:60]!r}")
            body.append(b)
        elif b.kind in ("signed", "dateline", "salute") or (b.kind == "trailer" and not FINIS.match(b.text)):
            closing.append(b)
        elif b.kind == "trailer":
            continue  # the printer's "FINIS."
        else:
            raise ImportError_(f"{base}: a {b.kind} block where it was not expected: {b.text[:60]!r}")
    _expect(bool(body), f"{base}: no paragraphs")
    division = {"attribution": part.get("attribution", work["attribution"]), "label": label, "level": 1,
                "publication": [], "ref": base}
    if "numeral" in part:
        division["numeral"] = part["numeral"]
    unsettled: dict[str, list[dict]] = {}
    for i, h in enumerate(heads):
        text, sp = joined([h])
        division["publication"].append(text)
        if sp:
            unsettled[f"publication.{i}"] = sp
    for name, bs in (("salutation", salute), ("signature", closing)):
        if bs:
            division[name], sp = joined(bs)
            if sp:
                unsettled[name] = sp
    if unsettled:
        division["uncertain"] = unsettled
    segments = []
    for x in part.get("extra", []):
        if x["at"] == "start":
            segments.append(segment(f"{base}.{x['ref']}", f"{label}, {x['label']}", find(divs, x["div"]).blocks()))
    segments += [segment(f"{base}.{n}", f"{label}, ¶ {n}", [b]) for n, b in enumerate(body, 1)]
    for x in part.get("extra", []):
        if x["at"] == "end":
            segments.append(segment(f"{base}.{x['ref']}", f"{label}, {x['label']}", find(divs, x["div"]).blocks()))
    segments += [segment(f"{base}.fn{k}", f"{label}, note {k}", [b], "footnote") for k, b in enumerate(notes, 1)]
    return division, segments


def imprint(h: dict) -> str:
    """The printing as the TCP header gives it."""
    place = h["place"].rstrip(" :,")
    publisher = h["publisher"].rstrip(" ,")
    return f"{place}: {publisher}{' ' if publisher.endswith('.') else ', '}{h['date'].rstrip(' .')}"


def build(work: dict) -> dict:
    h = check_header(work)
    sid = tcp.source_id(work["tcp"])
    divs = tcp.divisions(tcp.load(sid))
    divisions, segments = [], []
    for part in work["parts"]:
        d, segs = read_part(work, divs, part)
        divisions.append(d)
        segments += segs
    words = sum(len(s["text"].split()) for s in segments)
    gaps = sum(len(s.get("uncertain", [])) for s in segments)
    name = f"{work['title']} ({imprint(h)}), {h['catalogue']}"
    edition = {"name": name,
               "notes": f"{name}: the Text Creation Partnership's typed transcription, Evans-TCP {h['tcp']} "
                        f"({tcp.REPO_URL.format(tcp=h['tcp'])}), CC0. The transcription is the text, with the printing's "
                        "spelling and the long s (ſ) as keyed; words holding letters the transcribers could not read "
                        f"are marked as uncertain, with their marks (• a letter, 〈◊〉 a word) ({gaps} in {words} words). "
                        "No scan of this printing was found to check the transcription against. See docs/editions.md."}
    return {
        "attribution": work["attribution"],
        "date": work["date"],
        "divisions": divisions,
        "edition": edition,
        "id": work["work_id"],
        "position": work["position"],
        "ref_prefix": work["slug"],
        "segments": segments,
        "short": work["short"],
        "source_ids": [sid],
        "title": work["title"],
    }


def run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    paths = []
    for work in WORKS:
        path = out_dir / f"{work['work_id']}.json"
        write_json(path, build(work))
        paths.append(path)
    return paths


if __name__ == "__main__":
    for p in run():
        print(f"wrote {p}")
