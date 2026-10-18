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


if __name__ == "__main__":
    unittest.main()
