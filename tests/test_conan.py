import unittest

from importers.conan import CaseEntry, _pages_list, clause_ref, landmark_cases, topic_of

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

    def test_topics(self):
        self.assertEqual(topic_of("Amdt14.S1.8.1.3"), "Amdt14.S1.8")
        self.assertEqual(topic_of("ArtI.S8.C3.2.1"), "ArtI.S8.C3.2")
        self.assertEqual(topic_of("Amdt1.7.2"), "Amdt1.7")

    def test_most_cited_case_in_each_topic(self):
        a = CaseEntry("A v. B", "1 U.S. 1 (1790)", [10, 11, 12, 13, 20])
        b = CaseEntry("C v. D", "2 U.S. 2 (1791)", [10, 11, 20, 21])
        lower = CaseEntry("E v. F", "3 F.2d 3 (2d Cir. 1925)", [10, 11, 12, 13, 14])
        pages = {p: ["Amdt1.7.1"] for p in (10, 11, 12, 13, 14)} | {20: ["Amdt4.3.1"], 21: ["Amdt4.3.2"]}
        self.assertEqual(landmark_cases([a, b, lower], pages), {"A v. B, 1 U.S. 1 (1790)": [("Amdt1.7", 4)]})

    def test_page_lists(self):
        self.assertEqual(_pages_list("163, 168, 173–174, 1280"), [163, 168, 173, 174, 1280])

    def test_supreme_court_citations(self):
        self.assertTrue(CaseEntry("Brown v. Board of Education", "347 U.S. 483 (1954)", []).supreme_court)
        self.assertTrue(CaseEntry("Ableman v. Booth", "62 U.S. (21 How.) 506 (1859)", []).supreme_court)
        self.assertTrue(CaseEntry("Abbott v. Perez", "No. 17-586 (U.S. June 25, 2018)", []).supreme_court)
        self.assertFalse(CaseEntry("Aaron v. McKinley", "173 F. Supp. 944 (E.D. Ark. 1959)", []).supreme_court)


if __name__ == "__main__":
    unittest.main()
