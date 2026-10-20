"""Thomas Paine, Common Sense (Philadelphia: R. Bell, January 1776), from the
Text Creation Partnership's transcription of the first edition (decision 67).

Text: Evans-TCP N11839 (Evans 14954), keyed from the Readex microprint of the
first edition, [4], 79, [1] p., "Printed, and Sold, by R. Bell, in
Third-Street", advertised January 9, 1776 (`importers/tcp.py`). Check: the
Internet Archive's scan of the John Carter Brown Library's copy of the same
printing (first edition, first issue: [4], 79, [1] p.), word by word; its
page images are the passages' scans.

What is imported: the Introduction and the four parts the title page lists
(I. Of the Origin and Design of Government in general ...; II. Of Monarchy
and Hereditary Succession; III. Thoughts on the present State of American
Affairs; IV. Of the present Ability of America ...), each from its heading
to its last paragraph, with Paine's two notes. Not imported: the title page,
the heading "COMMON SENSE." over part I, "FINIS." and the bookseller's
advertisement after it.

Refs: `CommonSense.Introduction.{paragraph}`, `CommonSense.{part}.{paragraph}`
(parts 1-4 as the title page numbers them), notes `CommonSense.{part}.fn{k}`
(docs/references.md).

    python -m importers.paine fetch   # record the raw sources (once)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from importers import corrections, tcp
from importers.ratification import clean_vocabulary
from tools.common import TEXTS_DIR, write_json

WORK_ID = "common-sense"
PREFIX = "CommonSense"
TITLE = "Common Sense"

TCP_ID = "N11839"
TCP_COMMIT = "912c6164422ec63813ac0bf282d86f6b7a31bca2"
TCP_SOURCE = "tcp-n11839"
SCAN_ITEM = "commonsenseaddre00pain_2"
SCAN_SOURCE = "ia-decl-paine-1776-jcb-xml"

SOURCES = [
    (TCP_SOURCE, tcp.tcp_url(TCP_ID, TCP_COMMIT), tcp.TCP_LICENSE,
     f"Text Creation Partnership, Evans-TCP {TCP_ID} (Evans 14954), TEI P5 XML at commit {TCP_COMMIT} of "
     f"github.com/textcreationpartnership/{TCP_ID}: Thomas Paine, Common sense (Philadelphia: R. Bell, 1776), "
     "the first edition, keyed from the Readex microprint.", ".xml"),
    (SCAN_SOURCE, tcp.ia_url(SCAN_ITEM, "_djvu.xml"), tcp.IA_LICENSE,
     f"Internet Archive item {SCAN_ITEM}: the John Carter Brown Library's copy of Common sense (Philadelphia: "
     "R. Bell, 1776), first edition, first issue ([4], 79, [1] p.); DjVu XML of the OCR (Tesseract).", ".xml"),
]

# The headings of the parts, as the TCP gives them (checked, so that a
# change in the text or in the reading of it stops the import).
PARTS = [
    ("Introduction", "Introduction", r"^INTRODUCTION\.$"),
    ("1", "I", r"^Of the Origin and Design of GOVERNMENT in general"),
    ("2", "II", r"^Of MONARCHY and hereditary succession\.$"),
    ("3", "III", r"^THOUGHTS, on the present STATE of AMERICAN AFFAIRS\.$"),
    ("4", "IV", r"^OF THE PRESENT ABILITY OF AMERICA"),
]


class ImportError_(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ImportError_(msg)


def units() -> list[tuple[str, str, tcp.Block, list[tcp.Block]]]:
    """(key, numeral, heading, blocks) for the Introduction and each part."""
    root = tcp.load(TCP_SOURCE)
    text = root.find(f"{tcp.TEI}text")
    front, body = text.find(f"{tcp.TEI}front"), text.find(f"{tcp.TEI}body")
    intro = [d for d in front if tcp.tag(d) == "div" and d.get("type") == "introduction"]
    main = [d for d in body if tcp.tag(d) == "div" and d.get("type") == "text"]
    _expect(len(intro) == 1 and len(main) == 1, "expected one introduction and one text division")
    walker = tcp.Walker()
    divs = [intro[0]]
    for child in main[0]:
        t = tcp.tag(child)
        if t == "div" and child.get("type") == "part":
            divs.append(child)
        elif t == "head":
            # The running title over part I ("COMMON SENSE."), not imported.
            before_part_one = all(tcp.tag(d) == "pb" for d in divs[1:])
            _expect(before_part_one and "".join(child.itertext()).strip() == "COMMON SENSE.",
                    f"an unexpected heading: {''.join(child.itertext())!r}")
        else:
            _expect(t == "pb", f"the text: an unexpected <{t}>")
            divs.append(child)  # a page break between the parts
    _expect(sum(1 for d in divs if tcp.tag(d) == "div") == 5, "expected the introduction and four parts")
    out = []
    parts = iter(PARTS)
    for div in divs:
        if tcp.tag(div) == "pb":
            walker.page = div.get("n") or None
            continue
        k, numeral, head_re = next(parts)
        bs = walker.blocks(div)
        _expect(bool(bs) and bs[0].kind == "head" and re.search(head_re, bs[0].text),
                f"{numeral}: the heading is not {head_re!r}: {bs[0].text if bs else None!r}")
        rest = bs[1:]
        if k == "4":
            _expect(rest[-1].kind == "trailer" and rest[-1].text == "FINIS.", "part IV: expected FINIS. at the end")
            rest = rest[:-1]
        _expect(all(b.kind in ("p", "note") for b in rest), f"{numeral}: an unexpected block")
        out.append((k, numeral, bs[0], rest))
    return out


# The first edition names no author; the TCP's record of it (Evans 14954) does.
ATTRIBUTION = {"byline": "Attributed to Thomas Paine", "kind": "single", "names": ["Thomas Paine"],
               "source": "the TCP's record of the printing (Evans 14954: \"Attributed to Thomas Paine in the "
                         "Dictionary of American biography\")"}


def build(us, found, by_page) -> dict:
    head = tcp.header(tcp.load(TCP_SOURCE))
    divisions, segments, previous = [], [], []
    for (k, numeral, heading, bs), blocks in zip(us, found):
        base = f"{PREFIX}.{k}"
        name = "Introduction" if k == "Introduction" else numeral
        divisions.append({"attribution": ATTRIBUTION, "label": name if k == "Introduction" else f"Part {numeral}",
                          "level": 1, "ref": base,
                          **({} if k == "Introduction" else {"title": heading.text})})
        paras = notes = 0
        for b, (spans, leaves) in zip(bs, blocks):
            if b.kind == "note":
                notes += 1
                ref, label = f"{base}.fn{notes}", f"Common Sense, {name}, note {notes}"
            else:
                paras += 1
                ref, label = f"{base}.{paras}", f"Common Sense, {name}, ¶ {paras}"
            text, spans, fixed = corrections.apply(ref, b.text, spans)
            previous = tcp.leaves_for(b, leaves, by_page, previous)
            seg = {"label": label, "pages": b.pages, "ref": ref, "scan": {"item": SCAN_ITEM, "leaves": previous},
                   "text": text}
            if b.kind == "note":
                seg["kind"] = "footnote"
            if spans:
                seg["uncertain"] = spans
            if fixed:
                seg["corrected"] = fixed
            segments.append(seg)
    pages = [int(p) for s in segments for p in s["pages"] if p.isdigit()]
    return {
        "attribution": ATTRIBUTION,
        "date": "1776-01",
        "divisions": divisions,
        "edition": {
            "name": "Common Sense; Addressed to the Inhabitants of America (Philadelphia: R. Bell, 1776), first edition",
            "notes": (f"[Thomas Paine], Common Sense (Philadelphia: Printed, and Sold, by R. Bell, in Third-Street, "
                      f"1776), the first edition, advertised January 9, 1776 ({head['extent'].strip(' ;')}): the "
                      f"Introduction and the four parts, pp. {min(pages)}–{max(pages)}. Text: the Text Creation "
                      f"Partnership's transcription, Evans-TCP {head['tcp']} ({head['catalogue']}), keyed from the "
                      "Readex microprint of this printing and released under CC0; it gives the long s as a round s, "
                      "and joins words broken at a line end. Checked word by word against the OCR of the John "
                      "Carter Brown Library's copy of the first edition, first issue, on the Internet Archive, whose "
                      "page images each passage links to; where the scan reads another word, or none, the word is "
                      "marked as uncertain and the transcription's reading kept. See docs/editions.md."),
        },
        "id": WORK_ID,
        "ref_prefix": PREFIX,
        "segments": segments,
        "short": "Common Sense",
        "source_ids": [TCP_SOURCE, SCAN_SOURCE],
        "title": TITLE,
    }


def prepare():
    us = units()
    every = [b for _, _, _, bs in us for b in bs]
    scan = tcp.Scan.from_xml("jcb", SCAN_ITEM, SCAN_SOURCE)
    clean = clean_vocabulary()
    found = tcp.check(every, [scan], tcp.vocabulary(clean, every), {tcp.fkey(w) for w in clean})
    by_page = tcp.page_leaves(every, scan)
    at, grouped = 0, []
    for _, _, _, bs in us:
        grouped.append([found[at + i] for i in range(len(bs))])
        at += len(bs)
    return us, grouped, by_page


def run(out_dir: Path = TEXTS_DIR) -> list[Path]:
    path = out_dir / f"{WORK_ID}.json"
    write_json(path, build(*prepare()))
    return [path]


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        tcp.fetch(SOURCES)
    else:
        for p in run():
            print(f"wrote {p}")
