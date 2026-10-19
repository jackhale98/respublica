"""The Anti-Federalist Library as a tie-breaker, Patrick Henry's speeches
from Elliot's Debates, and Brutus V-XVI from the New-York Journal."""

import json
import re
import unittest

from importers.library import plain_text
from importers.ocr import consensus, tie_break
from tools.common import TEXTS_DIR
from tools.verify import check_uncertain

KNOWN = {"the", "this", "he", "be", "had", "has", "of", "right", "property", "discernable", "i"}


def doc(work: str) -> dict:
    return json.loads((TEXTS_DIR / f"{work}.json").read_text(encoding="utf-8"))


class TieBreakTests(unittest.TestCase):
    def test_the_library_chooses_among_the_scans_readings(self):
        self.assertEqual(tie_break({"primary": "lie", "a": "he"}, "lie", False, "he", known=KNOWN), ("he", True, None))

    def test_it_takes_the_scans_spelling_and_marks(self):
        self.assertEqual(tie_break({"primary": "tliis,", "a": "this,"}, "tliis,", False, "this", known=KNOWN),
                         ("this,", True, None))

    def test_it_never_adds_a_word(self):
        # No scan reads "this": the text stays, and the Library's reading is a suggestion.
        self.assertEqual(tie_break({"primary": "tbis", "a": "tlns"}, "tbis", False, "this", known=KNOWN),
                         ("tbis", False, "this"))

    def test_it_corroborates_a_reading_no_other_scan_has(self):
        self.assertEqual(tie_break({"primary": "controul"}, "controul", False, "controul", known=KNOWN),
                         ("controul", True, None))

    def test_a_settled_word_stands_outside_strict_works(self):
        self.assertEqual(tie_break({"primary": "right", "a": "right"}, "right", True, "fight", known=KNOWN),
                         ("right", True, None))

    def test_strict_unsettles_a_weakly_read_word_only(self):
        # One scan: the Library's different reading leaves it for a person.
        self.assertEqual(tie_break({"primary": "fame"}, "fame", True, "same", True, KNOWN), ("fame", False, "same"))
        # Two scans agree on a known word: the Library has errors of its own.
        self.assertEqual(tie_break({"primary": "right", "a": "right"}, "right", True, "fight", True, KNOWN),
                         ("right", True, None))
        # ... but not on a figure read for a letter.
        self.assertEqual(tie_break({"primary": "1", "a": "1"}, "1", True, "I", True, KNOWN), ("1", False, "I"))

    def test_not_a_reading_of_part_of_the_word(self):
        # "prop-" before "erty": a scan's "property" is a reading of more than this word.
        self.assertEqual(tie_break({"primary": "prop-", "a": "property"}, "prop-", False, "property", known=KNOWN),
                         ("prop-", False, None))
        self.assertEqual(tie_break({"primary": "thatzestof", "a": "that zest"}, "thatzestof", False, "that zest",
                                   known=KNOWN), ("thatzestof", False, None))

    def test_the_librarys_own_misreadings_are_ignored(self):
        self.assertEqual(tie_break({"primary": "discernable", "a": "discemable"}, "discernable", False, "discemable",
                                   known=KNOWN), ("discernable", False, None))

    def test_consensus_records_the_suggestion(self):
        words, unsettled = consensus([{"primary": "the"}, {"primary": "tbis"}], KNOWN, ["the", "this"])
        self.assertEqual(words, ["the", "tbis"])
        self.assertEqual([(u.start, u.suggestion) for u in unsettled], [(1, "this")])

    def test_a_suggestion_is_checked(self):
        span = {"start": 0, "end": 4, "readings": {"primary": "tbis"}}
        self.assertEqual(check_uncertain("x", "tbis", [{**span, "suggestion": "this"}]), [])
        self.assertTrue(check_uncertain("x", "tbis", [{**span, "suggestion": "tbis"}]))
        self.assertTrue(check_uncertain("x", "tbis", [{**span, "suggestion": "a\nb"}]))


class LibraryTextTests(unittest.TestCase):
    def test_editorial_marks_are_dropped(self):
        md = "---\ntitle: X\n---\n\n##### June 5, 1788\n\n###### Mr. Chairman,\n\n>Mr. *Henry* said [sic] that {141} he reëlected [that] it.\n"
        self.assertEqual(plain_text(md).split(), "Mr. Henry said that he reelected it.".split())


class HenryImportTests(unittest.TestCase):
    def test_twenty_four_speeches(self):
        d = doc("patrick-henry")
        self.assertEqual(len(d["divisions"]), 24)
        self.assertEqual(d["divisions"][0]["ref"], "Henry.Jun5")
        self.assertIn("Henry.Jun14c", [x["ref"] for x in d["divisions"]])
        self.assertEqual(d["position"], "anti")

    def test_speeches_open_as_elliot_prints_them(self):
        segs = {s["ref"]: s["text"] for s in doc("patrick-henry")["segments"]}
        self.assertTrue(segs["Henry.Jun5.1"].startswith("Mr. HENRY. Mr. C"))
        # Where the Library's speech takes in another member's remarks, so does the import.
        self.assertTrue(segs["Henry.Jun23.1"].startswith("Mr. NICHOLAS informed the committee"))
        self.assertTrue(segs["Henry.Jun23b.1"].startswith("Mr. MARSHALL rose"))

    def test_page_furniture_is_not_text(self):
        for s in doc("patrick-henry")["segments"]:
            self.assertIsNone(re.search(r"\bDEBATES\.|\bVIRGINIA\.\s*\d|\bVO[LT]\.\s", s["text"]), s["ref"])


class NewYorkJournalImportTests(unittest.TestCase):
    def test_essays_five_to_sixteen_without_eleven(self):
        refs = [x["ref"] for x in doc("brutus")["divisions"]]
        self.assertEqual(refs, [f"Brutus.{n}" for n in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16]])

    def test_two_instalments_are_one_essay(self):
        d = {x["ref"]: x for x in doc("brutus")["divisions"]}
        self.assertEqual(d["Brutus.12"]["date"], "1788-02-07/1788-02-14")
        self.assertEqual(d["Brutus.14"]["date"], "1788-02-28/1788-03-06")

    def test_passages_point_at_the_newspaper_page(self):
        from tools.site_data import scan_image, scan_url
        seg = next(s for s in doc("brutus")["segments"] if s["ref"] == "Brutus.5.1")
        scan = seg["scan"]
        self.assertEqual((scan["site"], scan["item"], scan["issue"]), ("loc", "sn83030566", "1787-12-13"))
        self.assertEqual(scan_url(scan["item"], scan["leaves"][0], "loc", scan),
                         "https://www.loc.gov/resource/sn83030566/1787-12-13/ed-1/?sp=2")
        self.assertTrue(scan_image(scan["item"], scan["leaves"][0], "loc", scan).startswith(
            "https://tile.loc.gov/image-services/iiif/service:ndnp:dlc:"))

    def test_signatures_are_not_text(self):
        for s in doc("brutus")["segments"]:
            self.assertFalse(re.search(r"B\s?R\s?U\s?T\s?U\s?S\.?$", s["text"]), s["ref"])
