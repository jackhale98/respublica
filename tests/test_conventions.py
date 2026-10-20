"""The Library of Congress's transcription of Elliot's Debates (importers/amem.py)
and the state ratifying conventions read from it (importers/conventions.py;
decision 68)."""

import datetime as dt
import json
import unittest

from importers import amem, conventions as cv
from importers.ocr import Reference, consensus
from tools.common import TEXTS_DIR
from tools.verify import check_uncertain

HEAD = """<?xml version="1.0" encoding="utf-8"?>
<tei2>
   <teiheader>
      <filedesc>
         <titlestmt><title>The Debates [Elliot's Debates, Volume 2] : a machine readable transcription.</title></titlestmt>
         <sourcedesc><copyright>Publication exempt from copyright protection; refer to accompanying matter.</copyright></sourcedesc>
      </filedesc>
      <encodingdesc><editorialdecl><p>An accuracy rate of 99.95 percent.</p></editorialdecl></encodingdesc>
   </teiheader>
   <text type="publication">
      <body>
"""
TAIL = """
      </body>
   </text>
</tei2>
"""

SAMPLE = HEAD + """         <div>
            <pageinfo><controlpgno entity="p00130000">0013</controlpgno><printpgno/></pageinfo>
            <head>DEBATES<lb/>
IN THE CONVENTION.</head>
            <stamped>PROPERTY OF<lb/>
LIBRARY</stamped>
            <p>
               <hi rend="italics">Thursday</hi>
, January 10.—The committee met in the 
<hi rend="italics">chamber</hi>
 of the house, and the in-<pageinfo>
                  <controlpgno entity="p00140002">0014</controlpgno>
                  <printpgno>2</printpgno>
               </pageinfo>
ference was drawn.<anchor id="n1">*</anchor>
 Then<lb/>
4 3<pageinfo>
                  <controlpgno entity="p00150003">0015</controlpgno>
                  <printpgno>3</printpgno>
               </pageinfo>
they voted as follows:—
<list type="simple">
                  <item><p>Mr. Adams, Yea.</p></item>
                  <item><p>Mr. Jones, Nay.</p></item>
               </list>
And so it passed.</p>
            <note anchor.ids="n1" place="bottom"><p>* See p. 1.</p></note>
         </div>""" + TAIL


class TranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.vol = amem.parse(SAMPLE, 2)

    def test_header(self):
        self.assertIn("Volume 2]", self.vol.title)
        self.assertTrue(self.vol.rights.startswith("Publication exempt from copyright protection"))

    def test_paragraphs_as_printed(self):
        texts = [p.text for p in self.vol.paras]
        self.assertEqual(texts[0], "DEBATES IN THE CONVENTION.")
        # The pretty-printer's line breaks around italics are not the book's;
        # a word broken across a page is rejoined; the signature mark ("4 3")
        # and the library stamp are left out.
        self.assertEqual(texts[1], "Thursday, January 10.—The committee met in the chamber of the house, and the "
                                   "inference was drawn.* Then they voted as follows:—")
        # A list inside a paragraph: its items are paragraphs, and the words after it a new one.
        self.assertEqual(texts[2:5], ["Mr. Adams, Yea.", "Mr. Jones, Nay.", "And so it passed."])
        self.assertEqual(self.vol.signature_marks, 1)
        self.assertNotIn("PROPERTY", " ".join(texts))

    def test_pages(self):
        # The first page is unnumbered: the next numbered page less one.
        self.assertEqual(self.vol.paras[0].pages, ["1"])
        self.assertEqual(self.vol.paras[1].pages, ["1", "2", "3"])

    def test_notes_follow_their_paragraph(self):
        note = self.vol.paras[-1]
        self.assertEqual((note.kind, note.text), ("note", "* See p. 1."))
        self.assertEqual(self.vol.paras[note.note_of].text, "And so it passed.")

    def test_an_unknown_element_stops_the_import(self):
        with self.assertRaises(amem.FormatError):
            amem.parse(HEAD + "<div><head>X</head><p>a <gap/> b</p></div>" + TAIL, 2)

    def test_plain_for_lining_up(self):
        self.assertEqual(amem.plain("reëlect the Achæan country—with"), "reelect the Achaean country — with")


def para(text: str, kind: str = "text") -> amem.Para:
    return amem.Para(kind, text, ["1"], 0)


class DayTests(unittest.TestCase):
    def setUp(self):
        self.c = cv.Convention("x", "X1788", "X", "X", "X", 2, (0,), "X", (1, 2), (
            cv.Day(dt.date(1788, 1, 9), r"In Convention, January 9, 1788\.$"),
            cv.Day(dt.date(1788, 1, 10), r"Thursday, January 10"),
            cv.Day(dt.date(1788, 1, 12), r"Friday, January 12", printed="Friday, January 12")))

    def test_days(self):
        units = cv.split_days(self.c, [para("In Convention, January 9, 1788."), para("Met."),
                                       para("Thursday, January 10.—Met again."), para("Friday, January 12.—Met.")])
        self.assertEqual([(u.key, u.label, len(u.paras)) for u in units],
                         [("Jan9", "January 9, 1788", 2), ("Jan10", "January 10, 1788", 1),
                          ("Jan12", "January 12, 1788", 1)])
        self.assertEqual(units[2].printed, "Friday, January 12")

    def test_a_dateline_not_in_the_list_stops_the_import(self):
        with self.assertRaises(cv.ImportError_):
            cv.split_days(self.c, [para("In Convention, January 9, 1788."), para("Monday, January 11, 1788.—Met."),
                                   para("Thursday, January 10.—Met."), para("Friday, January 12.—Met.")])

    def test_the_weekday_must_be_the_dates(self):
        c = cv.Convention("x", "X1788", "X", "X", "X", 2, (0,), "X", (1, 2),
                          (cv.Day(dt.date(1788, 1, 10), r"Friday, January 10"),))
        with self.assertRaises(cv.ImportError_):
            cv.split_days(c, [para("Friday, January 10.—Met.")])

    def test_every_convention_lists_dates_in_order(self):
        for c in cv.CONVENTIONS:
            dates = [d.date for d in c.days]
            self.assertEqual(dates, sorted(dates), c.prefix)

    def test_dash_is_a_word(self):
        self.assertEqual([w[2] for w in cv.words_of("country—with the")], ["country", "—", "with", "the"])


class CrossCheckTests(unittest.TestCase):
    def check(self, loc: str, scan: str) -> list[dict]:
        p = para(loc)
        unit = cv.Unit("Jan9", "January 9, 1788", dt.date(1788, 1, 9), [p])
        known = {"the", "rights", "of", "men", "are", "to", "be", "secured", "by", "right", "fights", "law",
                 "and", "all", "free", "people", "must", "have", "them", "now", "we", "say"}
        got = cv.cross_check([unit], [Reference("toronto", scan)], known)
        return got.spans.get(id(p), [])

    def test_a_scans_other_word_is_marked_and_the_transcription_kept(self):
        loc = "We say now the fights of men are to be secured by law and all free people must have them."
        spans = self.check(loc, "We say now the rights of men are to be secured by law and all free people must have them.")
        self.assertEqual(spans, [{"end": 21, "readings": {"primary": "fights", "toronto": "rights"}, "start": 15}])
        self.assertEqual(check_uncertain("X", loc, spans), [])

    def test_ocr_noise_is_not_marked(self):
        loc = "We say now the rights of men are to be secured by law and all free people must have them."
        self.assertEqual(self.check(loc, "We say now the riglits of men are to be secured by law and all free "
                                         "people must have them."), [])

    def test_marks_and_capitals_are_not_differences(self):
        loc = "We say now the rights of men are to be secured by law and all free people must have them."
        self.assertEqual(self.check(loc, "We say now the Rights, of men are to be secured by law and all free "
                                         "people must have them"), [])


class SuggestedByTests(unittest.TestCase):
    def test_the_suggestion_records_whose_it_is(self):
        words, unsettled = consensus([{"primary": "tbis", "a": "tlns"}], {"this"}, ["this"], library_source=["loc"])
        self.assertEqual((unsettled[0].suggestion, unsettled[0].suggested_by), ("this", "loc"))


class WorkTests(unittest.TestCase):
    def test_the_works(self):
        for c in cv.CONVENTIONS:
            doc = json.loads((TEXTS_DIR / f"{c.work_id}.json").read_text(encoding="utf-8"))
            self.assertEqual(doc["ref_prefix"], c.prefix)
            self.assertEqual(len(doc["divisions"]), max(1, len(c.days)), c.prefix)
            self.assertIn("loc-lled-%03d-xml" % c.vol, doc["source_ids"])
            for s in doc["segments"]:
                for u in s.get("uncertain", []):
                    self.assertEqual(s["text"][u["start"]:u["end"]], u["readings"]["primary"])
                    self.assertGreater(len(u["readings"]), 1)  # always a scan's reading beside it

    def test_refs(self):
        doc = json.loads((TEXTS_DIR / "virginia-convention-1788.json").read_text(encoding="utf-8"))
        refs = [s["ref"] for s in doc["segments"]]
        self.assertEqual(refs[0], "Virginia1788.Jun2.1")
        self.assertTrue(doc["segments"][0]["text"].startswith("In Convention, Richmond, Monday, June 2, 1788."))
        # The second day headed "Wednesday, June 18" is the 19th (erratum 60).
        self.assertIn("Virginia1788.Jun19", [d["ref"] for d in doc["divisions"]])
        nh = json.loads((TEXTS_DIR / "new-hampshire-convention-1788.json").read_text(encoding="utf-8"))
        self.assertEqual(nh["segments"][0]["ref"], "NewHampshire1788.1")


if __name__ == "__main__":
    unittest.main()
