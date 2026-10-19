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


class LaterVolumeTests(unittest.TestCase):
    """The Eleventh and Twelfth Amendments (decision 59)."""

    def test_running_heads_as_ocr_reads_them(self):
        from importers.annals import is_subject_row, is_title_row
        for text in ("19 HISTORY OF CONGRESS. 20", "HISXORT OF CONaRBSS.", "mSTORT OP CONGRESS."):
            self.assertTrue(is_title_row(text), text)
        self.assertFalse(is_title_row("Mr. Clinton said that, as the resolution was"))
        for text in ("NOTEMBER, 1803. Amendment to the Contliiution. Sbnatb.", "H. OP R. Aiitendment to the CorutUtUion.",
                     "Dbobmber. 1 ATrtmdment to the Coiutitutitm. H. OP R.", "Semite."):
            self.assertTrue(is_subject_row(text), text)
        for text in ("AMENDMENT TO THE CONSTITUTION.", "desire the concurrence of the Senate. They in-",
                     "Thursday, January 12."):
            self.assertFalse(is_subject_row(text), text)

    def test_column_numbers_hold_against_a_run_of_misread_figures(self):
        from importers.annals import settle_runs
        # OCR reads 5 as 6 in a stretch of pages (613 for 513, 616 for 516):
        # the numbers before it keep the run's offset.
        reads = {250: [487, 488], 251: [489, None], 252: [None, 492], 253: [493, 494], 254: [495, None],
                 255: [None, 498], 256: [499, 500], 257: [501, None], 258: [None, 504], 263: [613, None],
                 264: [None, 616], 265: [None, 618], 266: [519, None], 267: [621, None]}
        spreads = [Spread(leaf, "", [], n) for leaf, n in reads.items()]
        settle_runs(spreads)
        self.assertEqual([s.numbers for s in spreads if s.leaf in (263, 267)], [[513, 514], [521, 522]])

    def test_days_as_ocr_reads_them(self):
        from importers.annals import ANY_DAY, day_score, looks_like_day, starts_with_day

        def score(text, date):
            return day_score(ANY_DAY.match(text), date)
        # "TcESDAY, November 23," is Tuesday the 22d, not Wednesday the 23d.
        self.assertGreater(score("TcESDAY, November 23,", dt.date(1803, 11, 22)),
                           score("TcESDAY, November 23,", dt.date(1803, 11, 23)))
        self.assertGreater(score("Wednesday, November 23.", dt.date(1803, 11, 23)), 2)
        self.assertGreater(score("Satohdat May 1.", dt.date(1802, 5, 1)), 0)
        self.assertEqual(score("Monday, November 23.", dt.date(1803, 10, 23)), 0)
        self.assertTrue(looks_like_day("tlLosoi.1, December 12."))
        self.assertFalse(looks_like_day("Oct. 21, 1803. TH. JEFFERSON."))
        self.assertTrue(starts_with_day("THDRBOaY, October 37. Another member, to wit"))
        self.assertFalse(starts_with_day("Resolved, That the Senate will, on the 13th instant"))

    def test_opening_words_are_found_where_ocr_misread_some(self):
        from importers.annals import find_words
        b = block("October, 1803. Ordered, Thai the lesolution a^e«d to yesterday, in the form of")
        self.assertEqual(find_words(b, "Ordered, That the resolution agreed to yesterday"), 2)
        # Only where a paragraph could begin, not inside a sentence.
        self.assertIsNone(find_words(block("on the bill, entitled An act further"), "The bill, entitled"))
        self.assertIsNone(find_words(
            block("The Senate took into consideration the amendment of the House of Representatives to their"),
            "The Senate took into consideration the resolution of the House of Representatives of the 1st of May"))

    def test_same_engine_readings_count_once_for_vocabulary(self):
        from importers.annals import independent_of
        from importers.ocr import attested
        readings = [{"primary": "Mapison", "nypl": "Madlson", "tesseract": "Mapison"}]
        self.assertEqual(attested(independent_of(readings, ("primary", "tesseract"))), set())
        self.assertEqual(attested(readings), {"mapison"})


if __name__ == "__main__":
    unittest.main()
