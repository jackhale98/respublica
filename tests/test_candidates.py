import unittest

from tools.candidates import STRUCTURAL, candidates_for_paper
from tools.corpus import load_corpus


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = load_corpus()

    def test_quoted_clauses_are_found(self):
        found = {(c["from"], c["to"]) for c in candidates_for_paper(self.corpus, 33) if c["kind"] == "overlap"}
        self.assertIn(("Federalist.33.1", "Constitution.1.8.18"), found)
        self.assertIn(("Federalist.33.1", "Constitution.6.2"), found)

    def test_stock_phrases_are_not_candidates(self):
        # "of the United States" alone must not make a paragraph a candidate.
        for c in candidates_for_paper(self.corpus, 33):
            if c["kind"] == "overlap":
                self.assertGreaterEqual(c["distinctive_words"], 2, c)

    def test_structural_wording(self):
        for text in ("the last clause of the eighth section of the first article",
                     "the second clause of the sixth article",
                     "1st clause, 4th section, of the 1st article"):
            self.assertTrue(STRUCTURAL.search(text), text)


if __name__ == "__main__":
    unittest.main()
