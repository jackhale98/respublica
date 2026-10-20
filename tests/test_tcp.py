"""Texts from the Text Creation Partnership checked against scans (decision
67): Paine's Common Sense and Locke's Second Treatise."""

import json
import unittest
import xml.etree.ElementTree as ET

from importers import tcp
from tools.common import TEXTS_DIR
from tools.verify import check_uncertain

TEI = 'xmlns="http://www.tei-c.org/ns/1.0"'
KNOWN = {tcp.fkey(w) for w in ("the", "he", "be", "let", "lot", "ear", "car", "all", "mankind", "of", "rights",
                               "and", "subject", "to", "power", "a", "new", "found")}


def doc(work: str) -> dict:
    return json.loads((TEXTS_DIR / f"{work}.json").read_text(encoding="utf-8"))


def blocks(xml: str) -> list[tcp.Block]:
    return tcp.Walker().blocks(ET.fromstring(f"<div {TEI}>{xml}</div>"))


def scan(text: str) -> tcp.Scan:
    words = tcp.scan_tokens(text)
    return tcp.Scan("scan", None, words, [1] * len(words))


def spans(text: str, scan_text: str) -> list[dict]:
    b = blocks(f"<p>{text}</p>")
    return tcp.check(b, [scan(scan_text)], KNOWN, KNOWN)[0][0]


class TeiTests(unittest.TestCase):
    def test_words_broken_at_a_line_end_are_joined_across_a_page(self):
        b = blocks('<p>the Defen<g ref="char:EOLhyphen"/>\n<pb n="4"/>\nders thereof</p>')[0]
        self.assertEqual(b.text, "the Defenders thereof")
        self.assertEqual(b.pages, ["4"])
        self.assertEqual(b.page_of, [None, None, "4"])

    def test_a_page_break_between_words(self):
        b = blocks('<pb n="2"/><p>which bound\n<pb n="3"/>\nthem together</p>')[0]
        self.assertEqual((b.pages, b.page_of), (["2", "3"], ["2", "2", "3", "3"]))

    def test_an_unnumbered_page_has_no_printed_number(self):
        b = blocks('<pb n="9"/><p>one <pb facs="x"/> two</p>')[0]
        self.assertEqual((b.pages, b.page_of), (["9"], ["9", None]))

    def test_gaps_are_kept_as_the_tcp_marks_them_and_marked(self):
        b = blocks('<p>Alt<gap reason="illegible" extent="1 letter"><desc>•</desc></gap>r casus for'
                   '<g ref="char:punc">▪</g> and</p>')[0]
        self.assertEqual(b.text, "Alt•r casus for▪ and")
        self.assertEqual(b.gaps, {0, 2})

    def test_expansions_give_the_tcp_reading(self):
        b = blocks("<p>corpus<expan><am><g ref=\"char:abque\"/></am><ex>que</ex></expan> ordinis</p>")[0]
        self.assertEqual(b.text, "corpusque ordinis")

    def test_notes_follow_their_paragraph(self):
        bs = blocks('<p n="7">7. some <note n="*" place="bottom">A note.</note> Massanello</p><p>next</p>')
        self.assertEqual([(b.kind, b.text, b.n) for b in bs],
                         [("p", "7. some Massanello", "7"), ("note", "A note.", "*"), ("p", "next", None)])

    def test_a_section_that_begins_inside_a_quotation(self):
        bs = blocks('<p n="235">235. Barclay: <q><p>Quid ergo</p><p n="236">236. Alter casus</p></q> Englished.</p>')
        self.assertEqual([(b.n, b.text) for b in bs],
                         [("235", "235. Barclay: Quid ergo"), ("236", "236. Alter casus Englished.")])

    def test_an_unknown_element_stops_the_import(self):
        with self.assertRaises(ValueError):
            blocks("<p><table/></p>")


class CheckTests(unittest.TestCase):
    def test_the_long_s_compares_alike(self):
        for read in ("fubject", "ſubject", "lubject"):
            self.assertEqual(tcp.fkey(read), tcp.fkey("subject"))
        self.assertEqual(tcp.fkey("Iudge"), tcp.fkey("Judge"))

    def test_agreement_and_ocr_noise_settle_the_word(self):
        self.assertEqual(spans("the Rights of all Mankind", "the Rights of all Mankind"), [])
        self.assertEqual(spans("the Rights of all Mankind", "the Riglits of all Mankind"), [])

    def test_another_real_word_is_marked_and_the_tcp_kept(self):
        self.assertEqual(spans("one two three four lot their business be done now",
                               "one two three four let their business be done now"),
                         [{"end": 22, "readings": {"scan": "let", "tcp": "lot"}, "start": 19}])

    def test_a_word_the_scan_lacks_is_marked(self):
        # The TCP has "the" more than the printed page (Introduction, first edition).
        out = spans("War against natural Rights of all the Mankind, and extirpating Defenders thereof",
                    "War against natural Rights of all Mankind, and extirpating Defenders thereof")
        self.assertEqual([(s["start"], s["readings"]) for s in out], [(34, {"scan": "", "tcp": "the"})])

    def test_ocr_confusions_and_pieces_of_words_are_noise(self):
        self.assertEqual(spans("one two three he said it was so", "one two three be said it was so"), [])
        self.assertEqual(spans("one two three emigrants into society now", "one two three grants into society now"), [])

    def test_two_words_read_as_one_agree(self):
        self.assertEqual(spans("one two three a new one four five", "one two three anew one four five"), [])

    def test_a_gap_is_always_marked(self):
        out = tcp.check(blocks('<p>one Alt<gap reason="illegible"><desc>•</desc></gap>r two</p>'), [scan("x y z")],
                        KNOWN, KNOWN)[0][0]
        self.assertEqual(out, [{"end": 9, "readings": {"tcp": "Alt•r"}, "start": 4}])

    def test_verify_accepts_the_tcp_reading_in_place_of_a_scans(self):
        span = {"start": 0, "end": 3, "readings": {"tcp": "lot", "scan": "let"}}
        self.assertEqual(check_uncertain("x", "lot", [span]), [])
        self.assertTrue(check_uncertain("x", "lot", [{**span, "readings": {"tcp": "lot", "primary": "lot"}}]))


class CommonSenseImportTests(unittest.TestCase):
    def test_the_introduction_and_four_parts(self):
        d = doc("common-sense")
        self.assertEqual([x["ref"] for x in d["divisions"]],
                         ["CommonSense.Introduction", "CommonSense.1", "CommonSense.2", "CommonSense.3", "CommonSense.4"])
        segs = {s["ref"]: s for s in d["segments"]}
        self.assertTrue(segs["CommonSense.Introduction.1"]["text"].startswith("PERHAPS the Sentiments"))
        self.assertTrue(segs["CommonSense.1.1"]["text"].startswith("SOME writers have so confounded society"))
        self.assertEqual([r for r in segs if ".fn" in r], ["CommonSense.3.fn1", "CommonSense.4.fn1"])

    def test_the_first_edition_reading(self):
        # "urge him from his work" (Bell's later printings: "to quit his work").
        text = next(s["text"] for s in doc("common-sense")["segments"] if s["ref"] == "CommonSense.1.3")
        self.assertIn("would urge him from his work", text)

    def test_passages_point_at_the_jcb_scan(self):
        for s in doc("common-sense")["segments"]:
            self.assertEqual(s["scan"]["item"], "commonsenseaddre00pain_2")
            self.assertTrue(s["scan"]["leaves"])


class LockeImportTests(unittest.TestCase):
    def test_nineteen_chapters_and_lockes_sections(self):
        d = doc("locke-second-treatise")
        self.assertEqual(len(d["divisions"]), 19)
        refs = [s["ref"] for s in d["segments"] if s.get("kind") != "footnote"]
        self.assertEqual(refs[:4], ["Locke.1.1", "Locke.1.2", "Locke.1.3", "Locke.2.4"])
        self.assertEqual(refs[-1], "Locke.19.243")
        self.assertNotIn("Locke.3.21", refs)  # the 1690 printing has no section 21
        self.assertEqual(len(refs), 242)

    def test_a_section_of_several_paragraphs_is_one_passage(self):
        text = next(s["text"] for s in doc("locke-second-treatise")["segments"] if s["ref"] == "Locke.2.4")
        self.assertTrue(text.startswith("4. TO understand Political Power"))
        self.assertIn("\n\nA State also of Equality", text)

    def test_gaps_are_marked_uncertain(self):
        for s in doc("locke-second-treatise")["segments"]:
            unsure = {(u["start"], u["end"]) for u in s.get("uncertain", [])}
            for k, ch in enumerate(s["text"]):
                if ch in "•▪":
                    self.assertTrue(any(a <= k < b for a, b in unsure), f"{s['ref']}: {ch} at {k}")
