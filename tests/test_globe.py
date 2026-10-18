import unittest

from importers.globe import SPEAKER, SUBJECT, Block, house_of, is_heading, is_subject, one_case, page_number


def block(text, heading=True):
    return Block(text, [1], ["2459"], heading=heading)


class HeadingTests(unittest.TestCase):
    def test_small_capitals_in_either_case(self):
        for text in ("RECONSTRUCTION AGAIN.", "reconstruction.", "merchants' national bank of washington."):
            self.assertTrue(one_case(text), text)
            self.assertTrue(is_heading(block(text)), text)

    def test_sentences_verse_and_bill_titles_are_not_headings(self):
        for text in ("The motion was agreed to.", "Too feeble implements to bind.", "Article—.",
                     "Constitution of the United States."):
            self.assertFalse(is_heading(block(text)), text)
        self.assertFalse(is_heading(block("reconstruction.", heading=False)))  # not set as a heading

    def test_the_subject_as_ocr_reads_it(self):
        for text in ("RECONSTRUCTION.", "reconstruction again'.", "JtEOONSTJIUCTION.", "reconttiuotion.",
                     "heconstiiuction1—again."):
            self.assertTrue(is_subject(block(text)), text)
        for text in ("MESSAGE FROM THE SENATE.", "EVENING SESSIONS.", "CONSTITUTIONAL AMENDMENT."):
            self.assertFalse(is_subject(block(text)), text)

    def test_houses(self):
        self.assertEqual(house_of(block("HOUSE OP REPRESENTATIVES.")), "House")
        self.assertEqual(house_of(block("rN SENATE.")), "Senate")
        self.assertIsNone(house_of(block("A message from the House of Representatives, by Mr. McPherson.")))

    def test_the_joint_resolution_named(self):
        for text in ("resumed the consideration of the joint resolution (II. It. No. 127) proposing",
                     "the consideration of the constitutional amendment reported by the joint committee",
                     "the consideration of the joint resolution reported by the committee on reconstruction"):
            self.assertTrue(SUBJECT.search(text), text)
        self.assertFalse(SUBJECT.search("a substitute for the bill (H. R. No. 543) to restore the States"))


class LayoutTests(unittest.TestCase):
    def test_speakers(self):
        for text in ("Mr. STEVENS. I object.", "Mr.^ HOWARD. Mr. President", "The SPEAKER. Six minutes.",
                     "The PRESIDENT pro tempore. The Senator"):
            self.assertTrue(SPEAKER.match(text), text)
        self.assertFalse(SPEAKER.match("The committee are not ignorant of the fact"))

    def test_page_number_from_the_head(self):
        self.assertEqual(page_number("2459 THE CONGRESSIONAL GLOBE. May 8,"), 2459)
        self.assertEqual(page_number("1866. THE CONGRESSIONAL GLOBE. 2459"), 2459)
        self.assertIsNone(page_number("THE CONGRESSIONAL GLOBE."))


if __name__ == "__main__":
    unittest.main()
