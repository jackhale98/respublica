import unittest

from importers.conan import CaseEntry, _pages_list, clause_ref

REFS = {"Constitution.1.8.3", "Constitution.1.1", "Constitution.1.1.1", "Constitution.1.2", "Constitution.6.2",
        "Constitution.5.1", "Amendment.1.1", "Amendment.14.1", "Amendment.14.2", "Constitution.Preamble"}


class ConanTests(unittest.TestCase):
    def test_essay_ids_to_refs(self):
        self.assertEqual(clause_ref("ArtI.S8.C3.2.1", REFS), "Constitution.1.8.3")
        self.assertEqual(clause_ref("ArtI.S1.6.5", REFS), "Constitution.1.1.1")  # a section of one clause
        self.assertEqual(clause_ref("ArtVI.C2.1", REFS), "Constitution.6.2")
        self.assertEqual(clause_ref("ArtV.3", REFS), "Constitution.5.1")
        self.assertEqual(clause_ref("Amdt1.7.2", REFS), "Amendment.1.1")
        self.assertEqual(clause_ref("Amdt14.S1.8.1", REFS), "Amendment.14.1")
        self.assertEqual(clause_ref("Pre.1", REFS), "Constitution.Preamble")
        self.assertIsNone(clause_ref("Appx.1.6", REFS))

    def test_page_lists(self):
        self.assertEqual(_pages_list("163, 168, 173–174, 1280"), [163, 168, 173, 174, 1280])

    def test_supreme_court_citations(self):
        self.assertTrue(CaseEntry("Brown v. Board of Education", "347 U.S. 483 (1954)", []).supreme_court)
        self.assertTrue(CaseEntry("Ableman v. Booth", "62 U.S. (21 How.) 506 (1859)", []).supreme_court)
        self.assertTrue(CaseEntry("Abbott v. Perez", "No. 17-586 (U.S. June 25, 2018)", []).supreme_court)
        self.assertFalse(CaseEntry("Aaron v. McKinley", "173 F. Supp. 944 (E.D. Ark. 1959)", []).supreme_court)


if __name__ == "__main__":
    unittest.main()
