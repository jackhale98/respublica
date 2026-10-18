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
