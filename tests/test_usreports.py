"""The syllabus reader's rules for scans whose text layer is out of order or
laid out in the older styles (importers/usreports.py)."""

import unittest
from unittest import mock

from importers import usreports as u
from importers.usreports import Paragraph, problems
from tools.pdf import Line


def read(pages, volume=255, page=298):
    """The syllabus read from synthetic pages, as if from a scan."""
    with mock.patch.object(u, "_pages", lambda v, p: pages):
        return [(p.page, p.text) for p in u.syllabus(volume, page)]


class FragmentTests(unittest.TestCase):
    def test_a_left_piece_read_a_little_lower_goes_in_front(self):
        lines = u._merge_fragments([Line(112.8, 111, 369, 9, "4. The claim of privilege should"),
                                    Line(123.1, 144, 367, 9, "upheld, since it was evident"),
                                    Line(123.6, 102, 146, 9, "have been"),
                                    Line(134.0, 102, 369, 9, "in which it was asked.")])
        self.assertEqual([l.text for l in lines], ["4. The claim of privilege should",
                                                   "have been upheld, since it was evident",
                                                   "in which it was asked."])
        self.assertEqual(lines[1].x0, 102)

    def test_lines_a_full_line_apart_are_not_joined(self):
        lines = u._merge_fragments([Line(100, 144, 367, 9, "the first line"), Line(110, 102, 140, 9, "short")])
        self.assertEqual(len(lines), 2)


class MarkTests(unittest.TestCase):
    def test_signature_mark_on_the_first_page_of_a_sheet(self):
        body = Line(536, 58, 199, 8, "Held, that the charge was not improper.")
        mark = Line(546, 62, 182, 7, "'oVl Til. 10")  # "VOL. VIII.-10" on p. 145, the first page of sheet 10
        self.assertEqual(u._drop_signature([body, mark], 145), [body])
        self.assertEqual(u._drop_signature([body, mark], 146), [body, mark])   # not a sheet's first page
        self.assertEqual(u._drop_signature([body, mark], 161), [body, mark])   # sheet 11's: the number differs
        self.assertEqual(len(u._drop_signature([body, Line(556, 86, 303, 8, "Vol,. ccIlI -1 1")], 1)), 1)
        text = Line(546, 58, 199, 8, "Act of 1870, § 10")
        self.assertEqual(u._drop_signature([body, text], 145), [body, text])

    def test_specks_and_slugs(self):
        self.assertTrue(u._speck(Line(485, 366, 369.4, 6.8, "-")))
        self.assertFalse(u._speck(Line(485, 366, 369.4, 9, "a")))
        self.assertFalse(u._speck(Line(485, 300, 369.4, 9, "* * *")))
        self.assertTrue(u._starts_lower("-- from other States, transported them"))
        self.assertTrue(u.PRINTER_MARK.match("554US2 Unit: $U71 [01-05-13 17:53:27] PAGES PGT: OPIN"))

    def test_what_ends_the_syllabus(self):
        self.assertTrue(u.END.search("THE case is stated in the opinion."))
        self.assertFalse(u.END.search("the case is stated"))


class ParagraphTests(unittest.TestCase):
    def test_a_line_carries_on_one_left_unfinished(self):
        prev = Line(100, 64, 330, 9, "the Constitution, Slaughter House Cases, and the")
        # A turnover set deeper than the margin, or one beginning with a small letter.
        self.assertTrue(u._continues(prev, True, Line(111, 64, 200, 9, "Fourteenth Amendment."), prev, 330, 11))
        self.assertTrue(u._continues(prev, True, Line(111, 50, 300, 9, "felony, which existed"), prev, 330, 11))
        # Not after a sentence, a short line or a wide gap; not an outdented capital.
        done = Line(100, 64, 330, 9, "the Constitution. P. 12.")
        self.assertFalse(u._continues(done, True, Line(111, 64, 300, 9, "The next"), done, 330, 11))
        short = Line(100, 64, 200, 9, "and the")
        self.assertFalse(u._continues(short, False, Line(111, 64, 300, 9, "the next"), short, 330, 11))
        self.assertFalse(u._continues(prev, True, Line(130, 64, 300, 9, "the next"), prev, 330, 11))
        self.assertFalse(u._continues(prev, True, Line(111, 50, 300, 9, "The next"), prev, 330, 11))
        # At the head of a page: only a line beginning with a small letter.
        self.assertTrue(u._continues(prev, True, Line(80, 42, 300, 9, "and privileges of citizens"), None, 330, 11))
        self.assertFalse(u._continues(prev, True, Line(80, 42, 300, 9, "And privileges"), None, 330, 11))

    def test_a_quote_mark_after_a_word_is_not_a_stop(self):
        self.assertTrue(u._mid_sentence("under the Necessary and Proper Clause to'"))
        self.assertFalse(u._mid_sentence("as \"in his discretion.\""))

    def test_the_next_numbered_paragraph(self):
        four = [Line(500, 56, 330, 10, "4. Under the Constitution, compulsion is"),
                Line(511, 64, 330, 10, "not a permissible means. P. 640.")]
        self.assertTrue(u._next_item(four, Line(86, 54, 325, 10, "5. Minersville v. Gobitis, overruled; Ham-")))
        self.assertFalse(u._next_item(four, Line(86, 54, 325, 10, "6. Something else")))
        self.assertFalse(u._next_item(four[:1], Line(86, 54, 325, 10, "5. Minersville")))  # four stops mid-sentence

    def test_a_line_read_as_larger_type_that_finishes_a_sentence(self):
        take = [Line(220, 37, 313, 9, "State law, and Congress has the power to pass laws."),
                Line(230, 37, 191, 9, "free exercise of this right."),
                Line(240, 25, 314, 9, "Although the Fifteenth Amendment gives no right"),
                Line(250, 37, 313, 9, "to vote, yet there are cases, some stated by the")]
        self.assertTrue(u._carries_on(take, Line(260, 38, 303, 10, "court, in which it confers that right.")))
        self.assertFalse(u._carries_on(take, Line(260, 38, 303, 10, "Petition for a writ of habeas corpus")))
        self.assertFalse(u._carries_on(take, Line(290, 38, 303, 10, "court, in which it confers that right.")))
        done = take[:2] + [Line(240, 25, 314, 9, "Congress may regulate the times of elections.")]
        self.assertFalse(u._carries_on(done, Line(250, 38, 303, 10, "court, in which")))  # after a sentence

    def test_a_page_reference_never_starts_a_paragraph(self):
        for line in ("P. 135.", "Pp. 11-14.", "Pp. 642, 632."):
            self.assertTrue(u.PAGE_REF.match(line), line)
        self.assertFalse(u.PAGE_REF.match("P. 135. The next holding."))


class ReadTests(unittest.TestCase):
    def test_footnote_of_the_case_before_and_a_page_break(self):
        pages = [
            [Line(43, 148, 261, 10, "OCTOBER TERM, 1920."),
             Line(203, 126, 278, 11, "GOULED v. UNITED STATES."),
             Line(263, 84, 323, 9, "No. 250. Argued January 4, 1921.-Decided February 28, 1921."),
             Line(286, 73, 343, 9, "1. The Fourth and Fifth Amendments are to be liberally construed."),
             Line(297, 81, 108, 9, "P. 303."),
             Line(308, 72, 338, 9, "2. The Fourth Amendment permits of searches and seizures under"),
             Line(326, 82, 342, 9, '1 "You are hereby enjoined from requiring from the plaintiff or his'),
             Line(337, 73, 342, 9, 'agents payment of the license tax until the further orders of the court."')],
            [Line(42, 108, 251, 11, "GOULED v. UNITED STATES."),
             Line(62, 49, 251, 9, "298. Argument for the United States."),
             Line(83, 56, 316, 9, "valid search warrants, when justified by an interest of the public."),
             Line(94, 56, 100, 9, "P. 308."),
             Line(105, 48, 300, 9, "3. Papers lawfully obtained may be used as evidence. P. 311."),
             Line(116, 48, 150, 9, "255 F. 2d 1, affirmed."),
             Line(140, 57, 218, 11, "Mr. Charles E. Hughes for petitioner, with whom"),
             Line(153, 47, 314, 11, "Mr. Martin Littleton was on the brief.")],
        ]
        self.assertEqual(read(pages), [
            (298, "1. The Fourth and Fifth Amendments are to be liberally construed. P. 303."),
            (298, "2. The Fourth Amendment permits of searches and seizures under valid search warrants, "
                  "when justified by an interest of the public. P. 308."),
            (299, "3. Papers lawfully obtained may be used as evidence. P. 311."),
            (299, "255 F. 2d 1, affirmed."),
        ])

    def test_a_volume_without_dates_reads_from_the_case_name(self):
        pages = [
            [Line(39, 60, 338, 10, "542 UNITED STATES v. CRUIKSHANK ET AL. [Sup. Ct."),
             Line(83, 105, 289, 11, "UNITED STATES v. CRUIKSHANK ET AL."),
             Line(102, 63, 340, 8, "1. Citizens are the members of the political community to which"),
             Line(111, 80, 340, 8, "they belong. They are the people who compose the community, and"),
             Line(121, 80, 337, 8, "who, in their associated capacity, have established or submitted"),
             Line(130, 80, 339, 8, "themselves to the dominion of a government for the promotion of"),
             Line(140, 80, 200, 8, "their general welfare."),
             Line(149, 62, 343, 8, "2. There is in our political system a government of each of the")],
            # The small type follows the one-line running head closely.
            [Line(45, 30, 307, 10, "Oct. 1875.] UNITED STATES v. CRUIKSHANK ET AL. 543"),
             Line(65, 51, 311, 7, "several States, and a government of the United States. Each is"),
             Line(75, 51, 135, 7, "distinct from the others."),
             Line(98, 53, 326, 10, "ERROR to the Circuit Court of the United States for the"),
             Line(110, 43, 148, 10, "District of Louisiana.")],
        ]
        paras = read(pages, 92, 542)
        self.assertEqual([p for p, _ in paras], [542, 542])
        self.assertTrue(paras[0][1].startswith("1. Citizens are") and paras[0][1].endswith("general welfare."))
        self.assertEqual(paras[1][1], "2. There is in our political system a government of each of the several "
                                      "States, and a government of the United States. Each is distinct from the others.")

    def test_without_dates_or_a_case_name_nothing_is_read(self):
        pages = [[Line(39, 60, 338, 10, "542 UNITED STATES v. CRUIKSHANK. [Sup. Ct."),
                  Line(102, 63, 340, 8, "1. Citizens are the members of the political community.")]]
        self.assertEqual(read(pages, 92, 542), [])

    def test_without_dates_a_syllabus_must_end_at_larger_type(self):
        pages = [[Line(39, 60, 338, 10, "542 UNITED STATES v. CRUIKSHANK. [Sup. Ct."),
                  Line(83, 105, 289, 11, "UNITED STATES v. CRUIKSHANK ET AL."),
                  Line(102, 63, 340, 8, "1. Citizens are the members of the political community.")]]
        self.assertEqual(read(pages, 92, 542), [])


class ProblemTests(unittest.TestCase):
    def test_a_dash_that_leads_into_lettered_parts(self):
        lead = Paragraph("(2) The provisions of the Act are beyond the powers of Congress, because-", 239)
        part = Paragraph("(a) The Constitution grants to Congress no general power. P. 289.", 239)
        self.assertEqual(problems([lead, part]), [])
        self.assertEqual(len(problems([lead, Paragraph("The Constitution grants no power. P. 289.", 239)])), 1)
        self.assertEqual(len(problems([lead])), 1)

    def test_a_judgment_run_into_the_lineup_is_refused(self):
        run = ("5. The Commission's composition violates Art. II. Pp. 109-143. No. 75-436, 519 F. 2d 821, "
               "affirmed in part and reversed in part. Per curiam opinion. BURGER, C. J., post, p. 235, filed an "
               "opinion concurring in part.")
        kept = u._finish([(4, [Line(1, 50, 300, 9, "4. Subtitle H is constitutional. Pp. 85-109.")]),
                          (4, [Line(2, 50, 300, 9, run)])])
        self.assertEqual(len(kept), 2)  # kept for problems() to see, not dropped as the lineup
        self.assertIn("runs the judgment", problems(kept)[0])
        # The lineup on its own after the judgment is left out, as before.
        kept = u._finish([(4, [Line(1, 50, 300, 9, "4. Subtitle H is constitutional. Pp. 85-109.")]),
                          (4, [Line(2, 50, 300, 9, "519 F. 2d 821, affirmed.")]),
                          (4, [Line(3, 50, 300, 9, "BURGER, C. J., post, p. 235, filed an opinion.")])])
        self.assertEqual([p.text for p in kept], ["4. Subtitle H is constitutional. Pp. 85-109.",
                                                  "519 F. 2d 821, affirmed."])
        self.assertEqual(problems(kept), [])


if __name__ == "__main__":
    unittest.main()
