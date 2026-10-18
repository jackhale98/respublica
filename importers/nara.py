"""Import the Constitution and its amendments from National Archives transcriptions.

Inputs (sources/manifest.json ids):
  nara-declaration        https://www.archives.gov/founding-docs/declaration-transcript
  nara-constitution       https://www.archives.gov/founding-docs/constitution-transcript
  nara-bill-of-rights     https://www.archives.gov/founding-docs/bill-of-rights-transcript
  nara-amendments-11-27   https://www.archives.gov/founding-docs/amendments-11-27

Outputs: texts/declaration.json, texts/constitution.json, texts/amendments.json

Numbering follows docs/references.md. The importer only segments the
transcription and collapses HTML whitespace; it never changes wording,
spelling, capitalization or punctuation.
"""

from __future__ import annotations

import re
from pathlib import Path

from tools.common import Node, TEXTS_DIR, collapse_ws, parse_html, read_raw_text, roman_to_int, write_json

DECLARATION_SRC = "nara-declaration"
CONSTITUTION_SRC = "nara-constitution"
BOR_SRC = "nara-bill-of-rights"
AMEND_SRC = "nara-amendments-11-27"

BLOCK_TAGS = ("h1", "h2", "h3", "h4", "p", "hr")
AMENDMENT_HREF = re.compile(r"amendments-11-27#toc-amendment-([ivxl]+)$", re.I)


class ImportError_(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ImportError_(msg)


def _blocks_after_h1(root: Node, h1_text: str) -> list[Node]:
    """Block elements (h1-h4, p, hr) in document order inside the <section>
    that holds the page's main <h1>, starting after that <h1>."""
    h1 = next((n for n in root.find_all("h1") if n.text() == h1_text), None)
    _expect(h1 is not None, f"heading {h1_text!r} not found")
    section = h1.parent
    while section is not None and section.tag != "section":
        section = section.parent
    _expect(section is not None, "main <section> not found")
    blocks: list[Node] = []
    started = False
    for n in section.iter():
        if n is h1:
            started = True
            continue
        if started and n.tag in BLOCK_TAGS:
            blocks.append(n)
    return blocks


def _amendment_spans(p: Node) -> list[dict]:
    """NARA hyperlinks text that a later amendment changed. Record each
    linked span as data (the quote and the amendment it points to)."""
    spans = []
    for a in p.find_all("a"):
        m = AMENDMENT_HREF.search(a.attrs.get("href", ""))
        if m:
            spans.append({
                "amendment": f"Amendment.{roman_to_int(m.group(1))}",
                "quote": a.text(),
                "source_id": CONSTITUTION_SRC,
            })
    return spans


STATES = {
    "New Hampshire", "Massachusetts", "Rhode Island", "Connecticut", "New York", "New Jersey", "Pennsylvania",
    "Delaware", "Maryland", "Virginia", "North Carolina", "South Carolina", "Georgia",
}


def import_declaration() -> dict:
    """The Declaration of Independence, from the National Archives
    transcription of the Stone Engraving. Refs (docs/references.md):
    Declaration.Heading (the two lines above the text), Declaration.{n} for
    each paragraph as the transcription sets it (each grievance is its own
    paragraph there), and Declaration.Signers.{n} for each group of
    signatures, in the transcription's order."""
    root = parse_html(read_raw_text(DECLARATION_SRC))
    blocks = _blocks_after_h1(root, "Declaration of Independence: A Transcription")
    hr = next(i for i, b in enumerate(blocks) if b.tag == "hr")
    blocks = [b for b in blocks[hr + 1:] if b.tag == "p"]
    segments: list[dict] = []
    divisions: list[dict] = []

    _expect(blocks[0].text() == "In Congress, July 4, 1776", f"expected the date line, got {blocks[0].text()!r}")
    # The title is set in bold at the head of the first paragraph.
    first = blocks[1]
    strong = first.find_all("strong")
    _expect(bool(strong), "expected the title in bold at the head of the first paragraph")
    title = strong[0].text()
    full = first.text()
    _expect(full.startswith(title + " "), f"title {title!r} does not open the first paragraph")
    segments.append({"label": "Heading", "ref": "Declaration.Heading", "text": f"{blocks[0].text()}\n{title}"})
    paras = [full[len(title) + 1:]]

    i = 2
    while i < len(blocks) and blocks[i].text() not in STATES:
        t = blocks[i].text()
        if t:
            paras.append(t)
        i += 1
    for n, t in enumerate(paras, 1):
        segments.append({"label": f"Declaration of Independence, ¶ {n}", "ref": f"Declaration.{n}", "text": t})

    # Signatures: a state's name, then its signers, until the next state.
    divisions.append({"label": "Signatures", "level": 1, "ref": "Declaration.Signers"})
    groups: list[tuple[str, list[str]]] = []
    for b in blocks[i:]:
        t = b.text()
        if t == "Back to Main Declaration Page":
            break
        if not t:
            continue
        if t in STATES:
            groups.append((t, []))
        else:
            _expect(bool(groups), f"signer {t!r} before any state")
            groups[-1][1].append(t)
    for n, (state, names) in enumerate(groups, 1):
        _expect(bool(names), f"no signers under {state}")
        segments.append({"label": f"Signatures: {state}", "ref": f"Declaration.Signers.{n}", "state": state,
                         "text": "\n".join(names)})

    _expect(paras[1].startswith("We hold these truths to be self-evident"), "second paragraph should be 'We hold…'")
    _expect(paras[-1].startswith("We, therefore, the Representatives"), "last paragraph should be the resolution")
    _expect(sum(len(names) for _, names in groups) == 56, "expected 56 signers")
    return {
        "attribution": {"kind": "body", "names": ["Continental Congress"]},
        "date": "1776-07-04",
        "divisions": divisions,
        "edition": {
            "name": "National Archives transcription of the Stone Engraving of the parchment",
            "notes": "Spelling and punctuation follow the National Archives transcription, which reflects the "
                     "original. Paragraphs are as the transcription sets them: each grievance is its own "
                     "paragraph. Signatures are grouped by state in the transcription's order.",
        },
        "id": "declaration",
        "ref_prefix": "Declaration",
        "segments": segments,
        "source_ids": [DECLARATION_SRC],
        "title": "The Declaration of Independence",
    }


def import_constitution() -> dict:
    root = parse_html(read_raw_text(CONSTITUTION_SRC))
    blocks = _blocks_after_h1(root, "The Constitution of the United States: A Transcription")
    # The transcription proper starts after the first <hr> (before it: an editor's note).
    hr = next(i for i, b in enumerate(blocks) if b.tag == "hr")
    blocks = blocks[hr + 1:]

    segments: list[dict] = []
    divisions: list[dict] = []
    article = section = clause = None
    has_sections = False
    state = "preamble"
    signer_state = None

    def add(ref: str, label: str, node: Node, **extra) -> None:
        text = node.text()
        _expect(bool(text), f"empty text for {ref}")
        seg = {"label": label, "ref": ref, "text": text}
        spans = _amendment_spans(node)
        if spans:
            seg["changed_by"] = spans
        seg.update(extra)
        segments.append(seg)

    for b in blocks:
        t = b.text()
        if b.tag == "p" and t.startswith("For biographies of the non-signing delegates"):
            break
        if b.tag == "p" and not t:
            continue
        if state == "preamble":
            _expect(b.tag == "p" and t.startswith("We the People"), f"expected Preamble, got {t[:40]!r}")
            add("Constitution.Preamble", "Preamble", b)
            divisions.append({"label": "Preamble", "level": 1, "ref": "Constitution.Preamble"})
            state = "body"
            continue
        if b.tag == "h2":
            m = re.fullmatch(r"Article\.\s*([IVX]+)\.", t)
            _expect(m is not None, f"unexpected h2 {t!r}")
            article, section, clause, has_sections = roman_to_int(m.group(1)), None, 0, False
            divisions.append({"label": f"Article {m.group(1)}", "level": 1, "ref": f"Constitution.{article}"})
            continue
        if b.tag == "h3":
            m = re.fullmatch(r"Section\.\s*(\d+)\.", t)
            if m and state == "body":
                section, clause, has_sections = int(m.group(1)), 0, True
                divisions.append({
                    "label": f"Article {_roman(article)}, Section {section}",
                    "level": 2,
                    "ref": f"Constitution.{article}.{section}",
                })
                continue
            # A state name heading in the signature block.
            state = "signers"
        if state == "body" and b.tag == "p":
            if article == 7 and clause == 1:
                state = "closing"
            else:
                clause += 1
                if has_sections:
                    ref = f"Constitution.{article}.{section}.{clause}"
                    label = f"Article {_roman(article)}, Section {section}, Clause {clause}"
                else:
                    ref = f"Constitution.{article}.{clause}"
                    label = f"Article {_roman(article)}, Clause {clause}"
                add(ref, label, b)
                continue
        if state == "closing":
            if b.tag == "p" and t.startswith("The Word"):
                add("Constitution.Interlineations", "Note on interlineations", b)
            elif b.tag == "p" and t.startswith("Attest"):
                add("Constitution.Attestation", "Attestation", b)
            elif b.tag == "p" and t.startswith("done in Convention"):
                add("Constitution.Closing", "Closing", b)
            elif b.tag == "p" and "Washington" in t:
                add("Constitution.Signers.President", "Signature of the President of the Convention", b)
                divisions.append({"label": "Signatures", "level": 1, "ref": "Constitution.Signers"})
            else:
                raise ImportError_(f"unexpected block after Article VII: {t[:60]!r}")
            continue
        if state == "signers":
            if b.tag == "h3":
                signer_state = t
                continue
            _expect(b.tag == "p" and signer_state is not None, f"unexpected signer block {t[:40]!r}")
            key = re.sub(r"[^A-Za-z]", "", signer_state)
            add(f"Constitution.Signers.{key}", f"Signatures: {signer_state}", b, state=signer_state)
            signer_state = None
            continue
        raise ImportError_(f"unhandled block <{b.tag}> {t[:60]!r}")

    _expect(any(s["ref"] == "Constitution.1.8.18" for s in segments), "Article I, Section 8 should have 18 clauses")
    _expect(any(s["ref"] == "Constitution.7.1" for s in segments), "Article VII clause missing")

    return {
        "attribution": {"kind": "body", "names": ["Federal Convention"]},
        "date": "1787-09-17",
        "divisions": divisions,
        "edition": {
            "name": "National Archives transcription of the engrossed parchment",
            "notes": "Spelling and punctuation follow the National Archives transcription. "
                     "Spans that the National Archives marks as changed by a later amendment "
                     "are recorded in each segment's changed_by list.",
        },
        "id": "constitution",
        "ref_prefix": "Constitution",
        "segments": segments,
        "source_ids": [CONSTITUTION_SRC],
        "title": "The Constitution of the United States",
    }


def _roman(n: int) -> str:
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def _is_button(p: Node) -> bool:
    """NARA's navigation buttons ("Back to ...") end the transcription."""
    return any("btn" in a.attrs.get("class", "").split() for a in p.find_all("a"))


def _amendments_1_10() -> list[dict]:
    root = parse_html(read_raw_text(BOR_SRC))
    blocks = _blocks_after_h1(root, "The Bill of Rights: A Transcription")
    start = next(i for i, b in enumerate(blocks) if b.tag == "h2" and b.text() == "The U.S. Bill of Rights")
    out: list[dict] = []
    cur = None
    for b in blocks[start + 1:]:
        t = b.text()
        if b.tag == "h3":
            m = re.fullmatch(r"Amendment ([IVX]+)", t)
            _expect(m is not None, f"unexpected h3 {t!r}")
            cur = {"n": roman_to_int(m.group(1)), "numeral": m.group(1), "paragraphs": [], "sections": [],
                   "notes": [], "source_id": BOR_SRC}
            out.append(cur)
        elif b.tag == "p" and cur is not None and t:
            if _is_button(b):
                break
            cur["paragraphs"].append(t)
    _expect([a["n"] for a in out] == list(range(1, 11)), "expected Amendments I-X")
    return out


def _amendments_11_27() -> list[dict]:
    root = parse_html(read_raw_text(AMEND_SRC))
    h1 = root.find_all("h1")[0].text()
    blocks = _blocks_after_h1(root, h1)
    out: list[dict] = []
    cur = None
    sec = None
    for b in blocks:
        t = b.text()
        if b.tag in ("h2", "h3"):
            m = re.fullmatch(r"AMENDMENT ([IVXL]+)", t)
            if m:
                cur = {"n": roman_to_int(m.group(1)), "numeral": m.group(1), "paragraphs": [],
                       "sections": [], "notes": [], "source_id": AMEND_SRC}
                sec = None
                out.append(cur)
                continue
            m = re.fullmatch(r"Section (\d+)\.", t)
            _expect(m is not None and cur is not None, f"unexpected heading {t!r}")
            sec = {"n": int(m.group(1)), "paragraphs": []}
            _expect(sec["n"] == len(cur["sections"]) + 1, f"section out of order in {cur['numeral']}")
            cur["sections"].append(sec)
            continue
        if b.tag != "p" or cur is None or not t:
            continue
        if _is_button(b):
            break
        if "smaller" in b.attrs.get("class", "") or t.startswith("Note:") or t.startswith("*"):
            cur["notes"].append(t)
            continue
        (sec["paragraphs"] if sec else cur["paragraphs"]).append(t)
    _expect([a["n"] for a in out] == list(range(11, 28)), "expected Amendments XI-XXVII")
    return out


def import_amendments() -> dict:
    segments: list[dict] = []
    divisions: list[dict] = []
    for a in _amendments_1_10() + _amendments_11_27():
        n = a["n"]
        _expect(bool(a["paragraphs"]) != bool(a["sections"]), f"Amendment {n}: mixed sections and loose paragraphs")
        division = {"label": f"Amendment {a['numeral']}", "level": 1, "ref": f"Amendment.{n}"}
        if a["notes"]:
            division["notes"] = [{"source_id": a["source_id"], "text": x} for x in a["notes"]]
        divisions.append(division)
        if a["sections"]:
            for s in a["sections"]:
                _expect(bool(s["paragraphs"]), f"Amendment {n} section {s['n']} is empty")
                segments.append({
                    "label": f"Amendment {a['numeral']}, Section {s['n']}",
                    "ref": f"Amendment.{n}.{s['n']}",
                    "source_id": a["source_id"],
                    "text": "\n\n".join(s["paragraphs"]),
                })
        else:
            for i, para in enumerate(a["paragraphs"], 1):
                label = f"Amendment {a['numeral']}" + (f", Clause {i}" if len(a["paragraphs"]) > 1 else "")
                segments.append({
                    "label": label,
                    "ref": f"Amendment.{n}.{i}",
                    "source_id": a["source_id"],
                    "text": para,
                })
    return {
        "attribution": {"kind": "body", "names": ["Congress of the United States", "the States (ratification)"]},
        "date": "1791-12-15/1992-05-07",
        "divisions": divisions,
        "edition": {
            "name": "National Archives transcriptions of the Bill of Rights and Amendments XI-XXVII",
            "notes": "Amendments I-X follow the National Archives transcription of the first ten amendments "
                     "in their original form. Bracketing and asterisks in Amendments XII and XIV are the "
                     "National Archives' markers and are kept as transcribed; the matching notes are "
                     "stored on each amendment's division.",
        },
        "id": "amendments",
        "ref_prefix": "Amendment",
        "segments": segments,
        "source_ids": [BOR_SRC, AMEND_SRC],
        "title": "Amendments to the Constitution of the United States",
    }


def run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    paths = []
    for name, doc in (("declaration", import_declaration()), ("constitution", import_constitution()),
                      ("amendments", import_amendments())):
        path = out_dir / f"{name}.json"
        write_json(path, doc)
        paths.append(path)
    return paths


if __name__ == "__main__":
    for p in run():
        print(f"wrote {p}")
