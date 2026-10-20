import json
import unittest

from tools.common import TEXTS_DIR


class FederalistImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((TEXTS_DIR / "federalist.json").read_text(encoding="utf-8"))

    def test_newspaper_lines_stay_out_of_titles(self):
        for d in self.doc["divisions"]:
            self.assertNotRegex(d["title"], r"(?i)\b(from|for) (the )?(mclean|independent journal|new york packet|daily advertiser)", d["ref"])

    def test_every_paper_but_58_has_a_newspaper_line(self):
        # The edition prints no newspaper line for No. 58.
        missing = [d["ref"] for d in self.doc["divisions"] if not d["publication"]]
        self.assertEqual(missing, ["Federalist.58"])

    def test_85_papers_with_disputed_attribution(self):
        self.assertEqual(len(self.doc["divisions"]), 85)
        disputed = [d["ref"] for d in self.doc["divisions"] if d["attribution"]["kind"] == "disputed"]
        self.assertEqual(len(disputed), 11)

    def test_paragraph_breaks_restored_in_40_to_59(self):
        # Decision 70: No. 51 was one paragraph in the e-text; McLean has ten.
        paras = [s["ref"] for s in self.doc["segments"] if s["ref"].startswith("Federalist.51.")
                 and s.get("kind") != "footnote"]
        self.assertEqual(len(paras), 10)
        old = {r["ref"]: r["now"] for r in self.doc["renumbered"]}
        self.assertEqual(old["Federalist.51.1"], [f"Federalist.51.{k}" for k in range(1, 11)])
        self.assertTrue(all(r["ref"].split(".")[1] in {str(n) for n in range(40, 60)} for r in self.doc["renumbered"]))


class RestoreBreaksTests(unittest.TestCase):
    """Toy strings, not source text: only break positions come from the second text."""

    def test_splits_where_the_other_text_breaks_keeping_these_words(self):
        from importers.federalist import restore_breaks
        ours = ["alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"]
        other = ["Alpha beta gamma delta epsilon zeta,", "eta theta iota kappa lambda mu"]
        paras, origin, report = restore_breaks(ours, other)
        self.assertEqual(paras, ["alpha beta gamma delta epsilon zeta", "eta theta iota kappa lambda mu"])
        self.assertEqual(origin, [0, 0])
        self.assertEqual([b["action"] for b in report], ["split"])

    def test_never_joins_and_skips_breaks_without_enough_context(self):
        from importers.federalist import restore_breaks
        ours = ["alpha beta gamma delta", "epsilon zeta eta theta iota"]
        other = ["alpha beta gamma delta epsilon zeta eta theta iota"]
        self.assertEqual(restore_breaks(ours, other)[0], ours)
        other = ["alpha beta gamma delta epsilon", "omega psi chi phi"]
        paras, _origin, report = restore_breaks(ours, other)
        self.assertEqual(paras, ours)
        self.assertEqual([b["action"] for b in report], ["unaligned"])

    def test_no_break_inside_italics(self):
        from importers.federalist import restore_breaks
        ours = ["alpha beta gamma _delta epsilon zeta eta_ theta iota kappa"]
        other = ["alpha beta gamma delta epsilon", "zeta eta theta iota kappa"]
        paras, _origin, report = restore_breaks(ours, other)
        self.assertEqual(paras, ours)
        self.assertEqual([b["action"] for b in report], ["inside italics"])


class DeclarationImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((TEXTS_DIR / "declaration.json").read_text(encoding="utf-8"))
        cls.refs = {s["ref"]: s for s in cls.doc["segments"]}

    def test_paragraphs(self):
        self.assertTrue(self.refs["Declaration.1"]["text"].startswith("When in the Course of human events"))
        self.assertTrue(self.refs["Declaration.2"]["text"].startswith("We hold these truths to be self-evident"))
        self.assertTrue(self.refs["Declaration.32"]["text"].startswith("We, therefore, the Representatives"))
        self.assertNotIn("Declaration.33", self.refs)

    def test_title_is_in_the_heading_not_the_first_paragraph(self):
        self.assertEqual(self.refs["Declaration.Heading"]["text"],
                         "In Congress, July 4, 1776\nThe unanimous Declaration of the thirteen united States of America,")

    def test_56_signers(self):
        signers = [s for r, s in self.refs.items() if r.startswith("Declaration.Signers.")]
        self.assertEqual(sum(len(s["text"].split("\n")) for s in signers), 56)
        self.assertEqual(self.refs["Declaration.Signers.4"]["text"], "John Hancock")


if __name__ == "__main__":
    unittest.main()
