import unittest
from unittest import mock

from importers import corrections
from tools import errata


def spans_for(text, *words):
    out = []
    for w in words:
        at = text.index(w)
        out.append({"end": at + len(w), "readings": {}, "start": at})
    return out


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.text = "Mr. Madison rose, and reminded the House tlm^his was the day that he had namelUor bringing"
        self.spans = spans_for(self.text, "tlm^his", "namelUor")

    def run_with(self, decisions):
        with mock.patch.object(corrections, "for_ref", lambda ref: decisions):
            return corrections.apply("House1789.Jun8.1", self.text, self.spans)

    def test_a_correction_replaces_the_word_and_moves_the_marks_after_it(self):
        text, spans, fixed = self.run_with([{"at": "2026-10-19", "by": "jack", "index": 0, "now": "this",
                                             "ref": "House1789.Jun8.1", "was": "tlm^his"}])
        self.assertIn("House this was", text)
        self.assertEqual(len(spans), 1)
        self.assertEqual(text[spans[0]["start"]:spans[0]["end"]], "namelUor")
        self.assertEqual(text[fixed[0]["start"]:fixed[0]["end"]], "this")
        self.assertEqual(fixed[0]["was"], "tlm^his")

    def test_confirming_a_reading_keeps_the_word(self):
        text, spans, fixed = self.run_with([{"at": "2026-10-19", "by": "jack", "index": 1, "now": "namelUor",
                                             "ref": "House1789.Jun8.1", "was": "namelUor"}])
        self.assertEqual(text, self.text)
        self.assertEqual(len(spans), 1)
        self.assertEqual(len(fixed), 1)

    def test_a_word_found_at_another_place_among_the_marks(self):
        text, _, fixed = self.run_with([{"at": "2026-10-19", "by": "jack", "index": 5, "now": "named for",
                                         "ref": "House1789.Jun8.1", "was": "namelUor"}])
        self.assertIn("had named for bringing", text)

    def test_a_correction_that_no_longer_matches_stops_the_import(self):
        with self.assertRaises(corrections.CorrectionError):
            self.run_with([{"at": "2026-10-19", "by": "jack", "index": 0, "now": "this",
                            "ref": "House1789.Jun8.1", "was": "somethingelse"}])


class IssueTests(unittest.TestCase):
    def test_lines_of_an_errata_review_issue(self):
        body = "\n".join([
            "Corrections from the Res Publica errata page.",
            "",
            'correct House1789.Jun8.1 0 "tlm^his" "this"',
            'correct House1789.Jun8.1 1 "namelUor" "named \\"for\\""',
            'correct House1789.Jun8.1 x "a" "b"',
            'correct House1789.Jun8.1 2 "\'^|is" "   "',
        ])
        decisions, bad = errata.parse(body)
        self.assertEqual([d["now"] for d in decisions], ["this", 'named "for"'])
        self.assertEqual(decisions[0], {"index": 0, "now": "this", "ref": "House1789.Jun8.1", "was": "tlm^his"})
        self.assertEqual(len(bad), 2)  # no index, and nothing typed


if __name__ == "__main__":
    unittest.main()
