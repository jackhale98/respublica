import unittest

import datetime as dt

from importers.globe import (
    DAYS, GARBLED_HEAD, ITEM_START, MASTHEAD, SESSIONS, SIGNATURE, SPEAKER, SUBJECT, Block, WORKS, house_of, is_again,
    is_heading, is_subject, is_subject_heading, one_case, page_number, subject_of, unt_record,
)


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

    def test_page_number_is_not_the_year(self):
        self.assertEqual(page_number("1869. THE CONGRESSIONAL GLOBE. 1563", 1869), 1563)
        self.assertEqual(page_number("1314 THE CONGRESSIONAL GLOBE. March 28, 1864", 1864), 1314)
        self.assertEqual(page_number("1865. THE CONGRESSIONAL GLOBE. 1866", 1865), 1866)


class OtherAmendmentsTests(unittest.TestCase):
    """The Thirteenth (1864-65) and Fifteenth (1869) Amendments (decision 57)."""

    def test_subject_headings_as_ocr_reads_them(self):
        cases = {
            1864: ("AMENDMENT OF THE CONSTITUTION.", "AMENDMENTS TO TXIE CONSTITUTION.", "AMENDMENT TO TUB CONSTITUTION-.",
                   "AUOMTION OF BUAVL3UY.", "ABOLITION OF SLAVKRY.", "abolition of slavery."),
            1865: ("ABOLITION OF SLA.VJ511Y.", "ABOLITION OF SLAVERY AGAIN.", "ABOLITION OF SLAVERY-—-AGAIN."),
            1869: ("SUFFRAGE.", "J SUFFRAGE.", "suffrage.", "SUFFRAGE—AGAIN,", "RIGHTS OF CITIZENS.",
                   "SUFFRAGE CONSTITUTIONAL AMENDMENT.", "SUt'PRAUK CONSTITUTIONAL AMr.NDMBVr.",
                   "SUFFIIAGI5 COS8TUUTIONAL AMENDMENT."),
        }
        for year, texts in cases.items():
            for text in texts:
                self.assertTrue(is_subject(block(text), SESSIONS[year].headings, True), (year, text))

    def test_short_names_misread(self):
        self.assertTrue(is_subject(block("SUITKAGE."), SESSIONS[1869].headings, True))
        for text in ("CLAIMS 01' LOYAL CITIZENS.", "RIGHTS OF WOMEN.", "RIGHTS OF WOMEN IN THE DISTRICT."):
            self.assertFalse(is_subject(block(text), SESSIONS[1869].headings, True), text)
        self.assertTrue(is_subject_heading(block("SUFFRAGE, 4"), SESSIONS[1869].headings))

    def test_other_headings_are_not_the_subject(self):
        for text in ("FEMALE SUFFRAGE.", "SUFFRAGE IN THE DISTRICT OF COLUMBIA.", "CONSTITUTIONAL AMENDMENT.",
                     "EVENING SESSION.", "LOYALTY.", "SUFFRAGE IN THE TERRITORIES."):
            self.assertFalse(is_subject(block(text), SESSIONS[1869].headings + SESSIONS[1864].headings, True), text)

    def test_again(self):
        self.assertTrue(is_again(block("SUFFRAGE—AGAIN,"), "suffrage"))
        self.assertTrue(is_again(block("ABOLITION OF SLAVEKY AGAIN\"."), "abolitionofslavery"))
        self.assertTrue(is_again(block("heconstiiuction1—again."), "reconstruction"))
        self.assertFalse(is_again(block("SUFFRAGE."), "suffrage"))
        self.assertFalse(is_again(block("ABOLITION OF SLAVERY."), "abolitionofslavery"))
        self.assertEqual(subject_of(block("SUFFRAGE—AGAIN,"), SESSIONS[1869].headings), "suffrage")

    def test_subject_headings_ending_in_a_comma_or_a_stray_mark(self):
        for year, text in ((1869, "SUFFRAGE,"), (1869, "SUFFRAGE—AGAIN,"), (1865, "ABOLITION OF SLAVERY. Vf")):
            self.assertFalse(is_heading(block(text)), text)
            self.assertTrue(is_subject_heading(block(text), SESSIONS[year].headings), text)
        # Not another heading ending in a comma (1866: "INTERNAL REVENUE BILL.").
        self.assertFalse(is_subject_heading(block("ixteitnal ileyence but.,"), SESSIONS[1866].headings))

    def test_the_joint_resolutions_named(self):
        s13, s15 = SESSIONS[1864].subject, SESSIONS[1869].subject
        for text in ("proceeded to consider the joint resolution (S.No. 16) proposing amendments to the Constitution",
                     "the motion to reconsider the vote by which the House on the 15th of last June rejected a "
                     "joint resolution (S. No. 16)"):
            self.assertTrue(s13.search(text), text)
        for text in ("The joint resolution (H. R. No. 402) propos-", "the joint resolution (S. R. No. 8) proposing",
                     "The House resumes the consideration of House joint resolution No. 402, propos-"):
            self.assertTrue(s15.search(text), text)
        self.assertFalse(s15.search("40th Cong. 3d Sess.—No. 8."))
        self.assertFalse(s13.search("a bill (S. No. 166) to"))


class PageTests(unittest.TestCase):
    def test_signature_of_a_number(self):
        for text in ("40th Cong. 3d Sess.—No. 8.", "38th Cong. 2d Sess.—No. 13.", "39th Cong. 1st Sess —No 176."):
            self.assertTrue(SIGNATURE.match(text), text)
        self.assertFalse(SIGNATURE.match("the 39th Congress should"))

    def test_masthead_and_garbled_heads(self):
        self.assertTrue(MASTHEAD.search("THE OFFICIAL PROCEEDINGS OF CONGRESS, PUBLISHED BY JOHN C. RIVES"))
        self.assertFalse(MASTHEAD.search("the official proceedings of the convention"))
        self.assertTrue(GARBLED_HEAD.search("H34& MB (DONGrRESSIONATi GHOBEi March 80!"))

    def test_item_openings(self):
        for text in ("Mr. ASHLEY. I desire", "The SPEAKER. The next business", "On motion of Mr. GRIMES",
                     "A message from the Senate", "The House then resumed"):
            self.assertTrue(ITEM_START.match(text), text)
        for text in ("In these points are summed up", "The silent, flinty, scorched"):
            self.assertFalse(ITEM_START.match(text), text)


class TablesTests(unittest.TestCase):
    def test_every_day_is_in_a_session_and_a_work(self):
        for house, date, first, last in DAYS:
            self.assertIn(date.year, SESSIONS)
            self.assertIn((house, date.year), WORKS)
            self.assertLessEqual(first, last)
            unt_record(first, date.year)
            unt_record(last, date.year)

    def test_a_day_across_two_records(self):
        self.assertEqual(unt_record(752, 1869), "metadc30879")
        self.assertEqual(unt_record(754, 1869), "metadc30880")

    def test_days_in_order_without_repeats(self):
        keys = [(house, date) for house, date, _, _ in DAYS]
        self.assertEqual(len(keys), len(set(keys)))
        for year in SESSIONS:
            dates = [d for _, d, first, _ in DAYS if d.year == year]
            self.assertEqual(dates, sorted(dates))
        self.assertIn(("Senate", dt.date(1869, 1, 30)), keys)


if __name__ == "__main__":
    unittest.main()
