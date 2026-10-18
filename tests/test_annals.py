import datetime as dt
import unittest

from importers.annals import Block, Spread, capitals, date_of, day_key, day_of, is_subject, settle_columns
from importers.columns import find_gutters, sides
from importers.ocr import Line, Page, Word


def words(*spec):
    """Words from (text, x0, x1) at one height."""
    return [Word(t, x0, 100, x1, 130, 90) for t, x0, x1 in spec]


def block(text):
    return Block(text, [1], ["1"])


class LayoutTests(unittest.TestCase):
    def test_a_narrow_line_goes_to_its_column(self):
        line = Line(words(("Mr.", 1900, 1960), ("Ames.", 1980, 2100)))
        self.assertEqual([s for s, _ in sides(line, [1850], span=3000)], [1])

    def test_a_line_read_across_both_columns_is_split_at_the_gutter(self):
        line = Line(words(("the", 300, 400), ("previous", 420, 1820), ("|", 1845, 1850), ("Mr.", 1870, 1960),
                          ("Mapison", 1980, 3200)))
        parts = sides(line, [1850], span=3000)
        self.assertEqual([(s, [w.text for w in ws]) for s, ws in parts],
                         [(0, ["the", "previous"]), (1, ["Mr.", "Mapison"])])

    def test_the_gutter_from_lines_within_a_column(self):
        left = [Line(words(("a", 300, 1700 + k))) for k in range(10)]
        right = [Line(words(("b", 1900 + k, 3300))) for k in range(10)]
        self.assertEqual(find_gutters(left + right, left=300, span=3000), [(1709 + 1901) / 2])
        across = [Line(words(("a", 300, 1700), ("b", 1720, 3300))) for _ in range(40)]
        self.assertIsNone(find_gutters(left + across, left=300, span=3000))  # one column, paragraph ends on the left

    def test_column_numbers_follow_the_pages_around_a_misread(self):
        spreads = [Spread(leaf, "", [Page(leaf, 1, 1), Page(leaf, 1, 1)], n)
                   for leaf, n in ((240, [435, 436]), (241, [437, 438]), (242, [4, 440]), (243, [441, 442]))]
        settle_columns(spreads)
        self.assertEqual([s.numbers for s in spreads], [[435, 436], [437, 438], [439, 440], [441, 442]])


class ItemTests(unittest.TestCase):
    def test_headings(self):
        self.assertTrue(capitals("AMENDMENTS TO THE CONSTITUTION."))
        self.assertTrue(capitals("ADJOURNMENT."))
        self.assertFalse(capitals("Mr. Madison rose, and reminded the House"))
        self.assertTrue(is_subject(block("AMRNDMENTS TO THE CONSTITUTION.")))
        self.assertFalse(is_subject(block("INDIAN TREATIES.")))

    def test_days_as_ocr_reads_them(self):
        for text in ("Monday, June 8.", "Ti RSDAY, July 21.", "Satl RDAY, August 23.", "Friday, August 91{",
                     "Thursday, Sept. 24.", "Wrdnesday, August 19. INDIAN TREATIES."):
            self.assertIsNotNone(day_of(block(text)), text)
        for text in ("Nbw York, August 7, 1789.", "The clause as amended being now agreed to."):
            self.assertIsNone(day_of(block(text)), text)

    def test_dates_are_checked_against_the_calendar(self):
        def date(text, previous=None):
            return date_of(day_of(block(text)), previous)
        self.assertEqual(date("Monday, June 8."), dt.date(1789, 6, 8))
        self.assertEqual(date("Ti RSDAY, July 21."), dt.date(1789, 7, 21))  # a Tuesday
        # August 23, 1789 was a Sunday: the Saturday after the previous day.
        self.assertEqual(date("Satl RDAY, August 23.", dt.date(1789, 8, 21)), dt.date(1789, 8, 22))
        self.assertEqual(date("Friday, August 91{", dt.date(1789, 8, 20)), dt.date(1789, 8, 21))
        self.assertIsNone(date("Friday, August 91{"))
        self.assertEqual(day_key(dt.date(1789, 8, 13)), "Aug13")


if __name__ == "__main__":
    unittest.main()
