"""John Locke, the Second Treatise of Government ("An Essay Concerning the
True Original, Extent and End of Civil Government"), from the Text Creation
Partnership's transcription of the first edition, London, 1690 (decision 67).

Text: EEBO-TCP A48901 (Wing L2766), Two Treatises of Government (London:
Awnsham Churchill, 1690), keyed from the Early English Books images of the
Union Theological Seminary's copy (`importers/tcp.py`); only the second
treatise, "Book II", is imported. Checked word by word against the Internet
Archive's scans of two copies of the same printing: the University of
Illinois's copy (its page images are the passages' scans) and a microfilm in
the Early English Books series.

Locke is English; the work is in the library as a source the Declaration's
language draws on, and nothing more is said about its influence.

Refs: `Locke.{chapter}.{section}`, Locke's own numbered sections (§ 1 to
§ 243; this printing has no § 21, which later editions add), each in the
chapter it is printed in; a section of several paragraphs is one passage,
its paragraphs separated by a blank line. Notes printed in the margin:
`Locke.{chapter}.fn{k}` (docs/references.md).

    python -m importers.locke fetch   # record the raw sources (once)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from importers import corrections, tcp
from importers.ratification import clean_vocabulary
from tools.common import TEXTS_DIR, roman_to_int, write_json

WORK_ID = "locke-second-treatise"
PREFIX = "Locke"
TITLE = "The Second Treatise of Government"

TCP_ID = "A48901"
TCP_COMMIT = "6259832fa2e82b4ebfbffee2ceee6865a9fffae7"
TCP_SOURCE = "tcp-a48901"
SCAN_ITEM = "twotreatisesofgo00lock_1"
SCAN_SOURCE = "ia-decl-locke-1690-illinois-xml"
FILM_ITEM = "bim_early-english-books-1641-1700_two-treatises-of-governm_locke-john_1690"
FILM_SOURCE = "ia-decl-locke-1690-microfilm-txt"

SOURCES = [
    (TCP_SOURCE, tcp.tcp_url(TCP_ID, TCP_COMMIT), tcp.TCP_LICENSE,
     f"Text Creation Partnership, EEBO-TCP {TCP_ID} (Wing L2766), TEI P5 XML at commit {TCP_COMMIT} of "
     f"github.com/textcreationpartnership/{TCP_ID}: John Locke, Two treatises of government (London: Awnsham "
     "Churchill, 1690), keyed from the Early English Books images of the Union Theological Seminary Library's "
     "copy.", ".xml"),
    (SCAN_SOURCE, tcp.ia_url(SCAN_ITEM, "_djvu.xml"), tcp.IA_LICENSE,
     f"Internet Archive item {SCAN_ITEM}: the University of Illinois Urbana-Champaign's copy of Two treatises of "
     "government (London: A. Churchill, 1690), 271 [i.e. 467] p.; DjVu XML of the OCR.", ".xml"),
    (FILM_SOURCE, tcp.ia_url(FILM_ITEM, "_djvu.txt"), tcp.IA_LICENSE,
     f"Internet Archive item {FILM_ITEM}: a microfilm of Two treatises of government (London, 1690) in the Early "
     "English Books series; the OCR text (Tesseract).", ".txt"),
]

CHAPTER = re.compile(r"^CHAP\.\s+([IVXL]+)\.\s*(.*)$")


class ImportError_(RuntimeError):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ImportError_(msg)


def chapters() -> list[tuple[int, str, list[tuple[str, list[tcp.Block]]]]]:
    """(number, title, items) for each chapter of Book II. An item is a
    section, ("section", its blocks: the paragraph that opens with its
    number, then any paragraphs or list items before the next), or a note
    printed in the margin beside it, ("note", [block])."""
    root = tcp.load(TCP_SOURCE)
    books = [d for d in root.iter(f"{tcp.TEI}div") if d.get("type") == "book"]
    _expect([b.get("n") for b in books] == ["1", "2"], "expected Books I and II")
    walker = tcp.Walker()
    heads, out = [], []
    for child in books[1]:
        t = tcp.tag(child)
        if t == "pb":
            walker.page = child.get("n") or None
        elif t == "head":
            heads.append(" ".join("".join(child.itertext()).split()))
        elif t == "div" and child.get("type") == "chapter":
            bs = walker.blocks(child)
            m = CHAPTER.match(bs[0].text) if bs and bs[0].kind == "head" else None
            _expect(bool(m), f"chapter {child.get('n')}: no heading 'CHAP. …' ({bs[0].text if bs else None!r})")
            number = roman_to_int(m.group(1))
            _expect(str(number) == child.get("n") == str(len(out) + 1),
                    f"chapter {child.get('n')}: numbered {m.group(1)}")
            items: list[tuple[str, list[tcp.Block]]] = []
            for b in bs[1:]:
                if b.kind == "note":
                    items.append(("note", [b]))
                    continue
                if b.kind == "trailer" and b is bs[-1] and number == 19 and b.text == "FINIS.":
                    continue  # the end of the book, not imported
                _expect(b.kind == "p", f"chapter {number}: an unexpected {b.kind}: {b.text[:60]!r}")
                if b.n:
                    _expect(b.tokens[0] == f"{b.n}.", f"§ {b.n}: the paragraph opens {b.tokens[0]!r}")
                    items.append(("section", [b]))
                else:
                    last = next((x for x in reversed(items) if x[0] == "section"), None)
                    _expect(last is not None, f"chapter {number}: text before its first section")
                    last[1].append(b)
            out.append((number, m.group(2), items))
        else:
            raise ImportError_(f"Book II: an unexpected <{t}>")
    _expect(heads == ["AN ESSAY Concerning the True Oringinal, Extent and End OF CIVIL GOVERNMENT.", "BOOK. II."],
            f"Book II's headings are not as expected: {heads}")
    numbers = [int(bs[0].n) for _, _, items in out for kind, bs in items if kind == "section"]
    _expect(numbers == [n for n in range(1, 244) if n != 21], "the sections are not §§ 1–243 without § 21")
    return out


# The first edition names no author; the TCP's record of it (Wing L2766) does.
ATTRIBUTION = {"byline": "Attributed to John Locke", "kind": "single", "names": ["John Locke"],
               "source": "the TCP's record of the printing (Wing L2766: \"Attributed to John Locke. Cf. DNB.\")"}


def build(chs, found, by_page) -> dict:
    head = tcp.header(tcp.load(TCP_SOURCE))
    divisions, segments, previous = [], [], []
    for number, title, items in chs:
        numeral = roman(number)
        base = f"{PREFIX}.{number}"
        divisions.append({"attribution": ATTRIBUTION, "label": f"Chapter {numeral}", "level": 1, "ref": base,
                          **({"title": title} if title else {})})
        notes = 0
        for kind, blocks in items:
            if kind == "note":
                notes += 1
                ref, label = f"{base}.fn{notes}", f"Second Treatise, ch. {numeral}, note {notes}"
            else:
                ref, label = f"{base}.{blocks[0].n}", f"Second Treatise, § {blocks[0].n}"
            texts, spans, leaves, pages, offset = [], [], [], [], 0
            for b in blocks:
                sp, lv = found[id(b)]
                spans += [{**s, "end": s["end"] + offset, "start": s["start"] + offset} for s in sp]
                texts.append(b.text)
                offset += len(b.text) + 2
                previous = tcp.leaves_for(b, lv, by_page, previous)
                leaves += [x for x in previous if x not in leaves]
                pages += [p for p in b.pages if p not in pages]
            text, spans, fixed = corrections.apply(ref, "\n\n".join(texts), spans)
            seg = {"label": label, "pages": pages, "ref": ref, "scan": {"item": SCAN_ITEM, "leaves": sorted(leaves)},
                   "text": text}
            if kind == "note":
                seg["kind"] = "footnote"
            if spans:
                seg["uncertain"] = spans
            if fixed:
                seg["corrected"] = fixed
            segments.append(seg)
    return {
        "attribution": ATTRIBUTION,
        "date": "1690",
        "divisions": divisions,
        "edition": {
            "name": "Two Treatises of Government (London: Awnsham Churchill, 1690), first edition, Book II",
            "notes": (f"[John Locke], Two Treatises of Government (London: Printed for Awnsham Churchill, 1690), the "
                      f"first edition ({head['extent'].strip()}), Book II, \"An Essay Concerning the True Original, "
                      "Extent and End of Civil Government\" (as the TCP gives its heading, \"Oringinal\"): its "
                      "nineteen chapters, §§ 1–243 (this printing has no § 21; later editions add one), with the "
                      "notes printed in the margin. Text: the Text Creation Partnership's transcription, EEBO-TCP "
                      f"{head['tcp']} ({head['catalogue']}), keyed from the Early English Books images and released "
                      "under CC0; it gives the long s as a round s, joins words broken at a line end, gives "
                      "abbreviations it expands in full, and marks letters it could not read with \"•\" (those "
                      "words are marked as uncertain). Checked word by word against the OCR of two other copies "
                      "of this printing on the Internet Archive, the University of Illinois's (whose page images "
                      "each passage links to) and a microfilm; where they read another word, or none, the word is "
                      "marked as uncertain and the transcription's reading kept. Locke was English; the work is in "
                      "the library as a source the Declaration of Independence's language draws on. "
                      "See docs/editions.md."),
        },
        "id": WORK_ID,
        "ref_prefix": PREFIX,
        "segments": segments,
        "short": "Locke, Second Treatise",
        "source_ids": [TCP_SOURCE, SCAN_SOURCE, FILM_SOURCE],
        "title": TITLE,
    }


def roman(n: int) -> str:
    out = ""
    for v, s in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += s
            n -= v
    return out


def prepare():
    chs = chapters()
    every = [b for _, _, items in chs for _, bs in items for b in bs]
    scan = tcp.Scan.from_xml("illinois", SCAN_ITEM, SCAN_SOURCE)
    film = tcp.Scan.from_text("microfilm", FILM_SOURCE)
    clean = clean_vocabulary()
    checked = tcp.check(every, [scan, film], tcp.vocabulary(clean, every), {tcp.fkey(w) for w in clean})
    found = {id(b): checked[i] for i, b in enumerate(every)}
    return chs, found, tcp.page_leaves(every, scan)


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
