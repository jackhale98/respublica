"""Pamphlets of the ratification debate from the Text Creation Partnership,
and its text of a 1788 reprint as a tie-breaker between scans (decision 69)."""

import json
import unittest
import xml.etree.ElementTree as ET

from importers import pamphlets, tcp
from importers.ocr import consensus
from tools.common import TEXTS_DIR
from tools.verify import check_uncertain

TEI = 'xmlns="http://www.tei-c.org/ns/1.0"'
KNOWN = {"the", "in", "to", "of", "form"}
WORKS = {w["work_id"]: w for w in pamphlets.WORKS}


def doc(work: str) -> dict:
    return json.loads((TEXTS_DIR / f"{work}.json").read_text(encoding="utf-8"))


def letter(xml: str) -> list[tcp.Block]:
    return tcp.Walker(letters=True).blocks(ET.fromstring(f"<div {TEI}>{xml}</div>"))


class ReaderTests(unittest.TestCase):
    def test_a_letters_opening_and_closing_are_read_apart(self):
        bs = letter('<head>To the PRINTER.</head><opener><dateline>December 2, 1787.</dateline>'
                    '<salute>SIR,</salute></opener><p>THE incloſed letter</p>'
                    '<closer><signed>M. SMITH,</signed></closer>')
        self.assertEqual([(b.kind, b.text) for b in bs], [("head", "To the PRINTER."), ("dateline", "December 2, 1787."),
                                                           ("salute", "SIR,"), ("p", "THE incloſed letter"),
                                                           ("signed", "M. SMITH,")])

    def test_a_gap_mark_with_a_space_stays_in_its_word(self):
        b = letter('<p>con<gap reason="illegible" extent="7 letters"><desc>〈7 letters〉</desc></gap> fully '
                   'd<gap reason="illegible"><desc>•</desc></gap>\n  <g ref="char:EOLunhyphen"/>ſign</p>')[0]
        self.assertEqual(b.tokens, ["con〈7 letters〉", "fully", "d•ſign"])
        self.assertEqual(tcp.gap_spans(b), [{"end": 14, "readings": {"tcp": "con〈7 letters〉"}, "start": 0},
                                            {"end": 27, "readings": {"tcp": "d•ſign"}, "start": 21}])

    def test_the_long_s_is_kept(self):
        self.assertEqual(letter("<p>Congreſs</p>")[0].text, "Congreſs")


class TieBreakTests(unittest.TestCase):
    def test_the_typed_text_chooses_among_the_scans_readings(self):
        words, unsettled = consensus([{"primary": "ii,", "pitt": "in"}], KNOWN, typed=("Evans-TCP N16599", ["in"]))
        self.assertEqual((words, unsettled), (["in"], []))

    def test_it_suggests_only_a_reading_of_the_scans_word(self):
        _, unsettled = consensus([{"primary": "yorw"}], KNOWN, typed=("Evans-TCP N16599", ["form"]))
        self.assertEqual([(u.suggestion, u.suggested_by) for u in unsettled], [("form", "Evans-TCP N16599")])
        _, unsettled = consensus([{"primary": "13.", "pitt": "12."}], KNOWN, typed=("Evans-TCP N16599", ["Twelfth."]))
        self.assertEqual([u.suggestion for u in unsettled], [None])

    def test_the_library_comes_first(self):
        _, unsettled = consensus([{"primary": "tbis"}], KNOWN, ["this"], typed=("Evans-TCP N16599", ["thiss"]))
        self.assertEqual([(u.suggestion, u.suggested_by) for u in unsettled], [("this", None)])

    def test_a_suggested_by_is_checked(self):
        span = {"start": 0, "end": 4, "readings": {"primary": "yorw"}, "suggestion": "form"}
        self.assertEqual(check_uncertain("x", "yorw", [{**span, "suggested_by": "Evans-TCP N16599"}]), [])
        self.assertTrue(check_uncertain("x", "yorw", [{**span, "suggested_by": "the Library"}]))

    def test_refs_and_paragraphs_did_not_change(self):
        # The tie-breaker changed words only (decision 69): every ref was published before.
        locked = set((TEXTS_DIR.parent / "refs.lock").read_text(encoding="utf-8").split())
        for wid in ("centinel", "pennsylvania-minority"):
            self.assertTrue({s["ref"] for s in doc(wid)["segments"]} <= locked)
        self.assertIn("letter 9th,", next(s["text"] for s in doc("centinel")["segments"] if s["ref"] == "Centinel.2.14"))


class PamphletTests(unittest.TestCase):
    def test_every_work_is_imported_from_its_tcp_text(self):
        for wid, w in WORKS.items():
            d = doc(wid)
            self.assertEqual(d["source_ids"], [tcp.source_id(w["tcp"])])
            self.assertIn(w["expect"]["evans"], d["edition"]["name"])
            self.assertTrue(d["segments"])

    def test_refs(self):
        refs = {s["ref"] for wid in WORKS for s in doc(wid)["segments"]}
        for ref in ("ColumbianPatriot.1", "JayAddress.38", "CoxeExamination.Preface.1", "CoxeExamination.4.1",
                    "WilsonSpeech.8", "Aristides.Dedication", "Aristides.1", "RandolphLetter.Letter.57",
                    "Monroe.Errata", "NativeOfVirginia.Article6.1", "NativeOfVirginia.Errata.18"):
            self.assertIn(ref, refs)

    def test_gaps_are_marked_never_filled(self):
        for wid in WORKS:
            for s in doc(wid)["segments"]:
                marked = [s["text"][u["start"]:u["end"]] for u in s.get("uncertain", [])]
                self.assertTrue(all(any(c in m for c in "•〈▪") for m in marked), s["ref"])
                for tok in s["text"].split():
                    if any(c in tok for c in "•〈▪"):
                        self.assertIn(tok, " ".join(marked), s["ref"])

    def test_a_letter_keeps_its_salutation_and_signature(self):
        d = {x["ref"]: x for x in doc("randolph-letter")["divisions"]}
        self.assertEqual(d["RandolphLetter.Letter"]["salutation"], "SIR,")
        self.assertTrue(d["RandolphLetter.Letter"]["signature"].startswith("EDMUND RANDOLPH."))
        self.assertEqual(doc("jay-address")["divisions"][0]["signature"], "A CITIZEN OF NEW-YORK.")

    def test_the_header_is_checked(self):
        bad = {**WORKS["jay-address"], "expect": {**WORKS["jay-address"]["expect"], "evans": "Evans 1"}}
        with self.assertRaises(pamphlets.ImportError_):
            pamphlets.check_header(bad)

    def test_attributions_cite_the_catalogue(self):
        for wid in ("columbian-patriot", "jay-address", "coxe-examination", "aristides", "monroe-observations",
                    "native-of-virginia"):
            self.assertIn("catalogue record of Evans-TCP", doc(wid)["attribution"]["source"])


if __name__ == "__main__":
    unittest.main()
