"""The road to independence (decision 66): importers/independence.py, the TCP
reader (importers/tcp.py) and pages printed in parallel columns
(importers/parallel.py)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from importers import independence, parallel, tcp
from importers.ocr import Block, Line, Page, Para, Word
from tools.common import TEXTS_DIR

TEI = """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="declaration"><pb facs="unknown:014550_0001_X"/>
<head>A DECLARATION</head>
<p>Our Forefather <gap reason="illegible" extent="3 letters"><desc>&#8226;&#8226;&#8226;</desc></gap>abitants left
their native Land, at the Ex<g ref="char:EOLhyphen"/>pence of their Blood, tho'
<figure><head>A View of BOSTON</head><p>J TURNER</p></figure>
of Right make <q>Laws to bind us</q> and all Danger o<gap reason="illegible" extent="1 letter"><desc>&#8226;</desc></gap>
<g ref="char:punc">&#9642;</g></p>
<pb facs="unknown:014550_0002_Y"/>
<p n="2">2d. That all power is ve&#383;ted in the people.</p>
<closer><signed>By Order of CONGRESS, JOHN HANCOCK, President.</signed>
<dateline>PHILADELPHIA, <date>July 6th, 1775.</date></dateline></closer>
</div></body></text></TEI>"""


class TcpTests(unittest.TestCase):
    """The broadside's TEI read by the shared reader (importers/tcp.py)."""

    def blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.xml"
            path.write_text(TEI, encoding="utf-8")
            with mock.patch.object(tcp, "raw_path", lambda sid: path):
                return independence.typed_blocks(independence.Typed("x", "N1", "Evans 1", "declaration", "a printing"))

    def test_paragraphs_and_kinds(self):
        bs = self.blocks()
        self.assertEqual([b.kind for b in bs], ["head", "p", "p", "closer"])
        self.assertEqual(bs[3].text, "By Order of CONGRESS, JOHN HANCOCK, President. PHILADELPHIA, July 6th, 1775.")

    def test_line_end_hyphen_rejoined_and_figure_left_out(self):
        text = self.blocks()[1].text
        self.assertIn("at the Expence of", text)
        self.assertNotIn("BOSTON", text)
        self.assertIn("tho' of Right make Laws to bind us and", text)

    def test_gaps_are_kept_as_keyed_and_marked(self):
        b = self.blocks()[1]
        self.assertEqual([b.tokens[i] for i in sorted(b.gaps)], ["•••abitants", "o•", "▪"])
        spans = independence.gap_spans(b)
        self.assertEqual(spans[0]["readings"], {"tcp": "•••abitants"})
        self.assertEqual(b.text[spans[0]["start"]:spans[0]["end"]], "•••abitants")

    def test_word_broken_after_a_gap_is_rejoined(self):
        b = tcp.to_block("the m\x03•••••\x04 \x07ry ſhould", "p", None)
        self.assertEqual(b.tokens, ["the", "m•••••ry", "ſhould"])
        self.assertEqual(b.gaps, {1})

    def test_long_s_kept(self):
        self.assertIn("veſted", self.blocks()[2].text)


def line(text: str, x0: int, y: int, w: int = 30) -> Line:
    words, x = [], x0
    for t in text.split():
        words.append(Word(t, x, y, x + w * len(t), y + 40, 90))
        x += w * len(t) + w
    return Line(words)


class ParallelTests(unittest.TestCase):
    def test_right_column_kept_left_dropped(self):
        rows = [(f"left draft {k} words here", f"right text {k} words here") for k in range(8)]
        lines = []
        for k, (a, b) in enumerate(rows):
            lines += [line(a, 100, 300 + 60 * k), line(b, 1100, 300 + 60 * k)]
        page = Page(5, 2000, 3000, [Para(lines, 5)], "64", "64")
        zones = parallel.right_column(page)
        text = " ".join(l.text for z in zones for p in z.paras for l in p.lines)
        self.assertIn("right text 0", text)
        self.assertNotIn("left", text)

    def test_full_width_lines_above_the_columns_kept(self):
        top = [line("The Congress met according to adjournment and came into the following", 100, 200, 22)]
        cols = []
        for k in range(8):
            cols += [line(f"draft line {k} of it", 100, 400 + 60 * k), line(f"adopted line {k} of it", 1100, 400 + 60 * k)]
        page = Page(5, 2000, 3000, [Para(top, 5), Para(cols, 5)], "63", "63")
        zones = parallel.right_column(page, columns_from=r"draft\s+line\s+0")
        self.assertEqual(zones[0].paras[0].lines[0].text, top[0].text)
        right = " ".join(l.text for p in zones[1].paras for l in p.lines)
        self.assertTrue(right.startswith("adopted line 0") and "draft" not in right)

    def test_page_of_right_column_only(self):
        lines = [line(f"suitable quarters {k} for officers", 1000, 300 + 60 * k) for k in range(6)]
        page = Page(9, 2000, 3000, [Para(lines, 9)], "73", "73")
        zones = parallel.right_column(page)
        self.assertEqual(sum(len(p.lines) for z in zones for p in z.paras), 6)

    def test_hanging_indent_begins_a_paragraph(self):
        lines = [line("tyranny ;", 100, 100), line("by putting his negative on laws", 100, 160),
                 line("the most wholesome & neces-", 150, 220), line("sary for ye public good ;", 150, 280),
                 line("heretofore entrusted with the", 100, 340)]
        page = Page(1, 800, 3000, [Para(lines, 1)], "8", "8")
        paras = parallel.outdented(page, page.paras, clauses=True)
        self.assertEqual([p.lines[0].text for p in paras], ["tyranny ;", "by putting his negative on laws"])
        self.assertTrue(paras[1].starts)


class ImporterHelperTests(unittest.TestCase):
    def test_spaced_hyphen_rejoined_only_into_a_known_word(self):
        clean = {"independence", "hampshire"}
        self.assertEqual(independence.rejoin("the declaration on independ - ence.", clean),
                         "the declaration on independence.")
        self.assertEqual(independence.rejoin("New Hamp - shire", clean), "New Hampshire")
        self.assertEqual(independence.rejoin("our f rou - tiers", clean), "our f rou - tiers")

    def test_note_cut_from_its_block_and_followed_overleaf(self):
        every = [Block("' Ward objected to the part. ^ The first draft was Sullivan's.", [10], ["63"], "note"),
                 Block("* Another note.", [10], ["63"], "note"),
                 Block("and so it ends here.", [11], ["64"], "note")]
        note = independence.cut_note(every, independence.Note(63, r"The\s+first\s+draft", r"ends\s+here\."), 10, 10)
        self.assertEqual(note.text, "^ The first draft was Sullivan's. and so it ends here.")
        self.assertEqual(every[0].text, "' Ward objected to the part.")
        self.assertEqual(every[1].text, "* Another note.")


class ImportedTextTests(unittest.TestCase):
    @staticmethod
    def doc(name):
        return json.loads((TEXTS_DIR / f"{name}.json").read_text(encoding="utf-8"))

    def refs(self, name):
        return [s["ref"] for s in self.doc(name)["segments"]]

    def test_virginia_rights_has_its_sixteen_articles(self):
        refs = self.refs("virginia-declaration-of-rights")
        self.assertEqual(refs, ["VirginiaRights.Heading"] + [f"VirginiaRights.{n}" for n in range(1, 17)])
        segs = {s["ref"]: s for s in self.doc("virginia-declaration-of-rights")["segments"]}
        self.assertTrue(segs["VirginiaRights.16"]["text"].startswith("16th. That religion"))

    def test_causes_from_the_broadside(self):
        segs = self.doc("causes-1775")["segments"]
        self.assertEqual(segs[0]["ref"], "Causes1775.Heading")
        self.assertEqual(segs[-1]["ref"], "Causes1775.Closing")
        self.assertTrue(segs[1]["text"].startswith("IF it was possible for Men"))

    def test_resolves_from_the_right_column(self):
        segs = self.doc("resolves-1774")["segments"]
        body = [s for s in segs if s.get("kind") != "footnote"]
        self.assertTrue(body[1]["text"].startswith("Whereas, since the close of the last war"))
        self.assertTrue(body[-1]["text"].endswith("already entered into."))
        self.assertFalse(any("accession of the present King" in s["text"] for s in segs))  # Sullivan's draft

    def test_lee_resolution_and_july_proceedings(self):
        lee = [s["text"] for s in self.doc("lee-resolution-1776")["segments"]]
        self.assertTrue(lee[1].startswith("Resolved, That these United Colonies are, and of right ought to be"))
        refs = self.refs("independence-1776")
        self.assertIn("Independence1776.Jul2.2", refs)
        self.assertIn("Independence1776.Jul4.fn1", refs)

    def test_jefferson_fair_copy_ends_with_the_deposing_clause(self):
        body = [s for s in self.doc("jefferson-virginia-preamble-1776")["segments"] if s.get("kind") != "footnote"]
        self.assertTrue(body[-1]["text"].endswith("within this colony."))
        self.assertFalse(any("Be it therefore enacted by the authority of the people that the said George the third"
                             in s["text"] for s in body))  # the first draft, on the left


if __name__ == "__main__":
    unittest.main()
