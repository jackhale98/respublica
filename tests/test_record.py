import datetime as dt
import random
import re
import tempfile
import unittest
from pathlib import Path

from importers import record
from importers.ocr import NUMERAL_HEAD, Block
from tests.test_pdf import make_pdf
from tools import fetch
from tools.common import ROOT, UNTRACKED_FAMILIES, UNTRACKED_RAW
from tools.pdf import pdf_words
from tools.site_data import SHEET_HTML_BYTES, WORKS, scan_image, scan_url, sheets


def block(text, heading=True):
    return Block(text, [1], ["4105"], heading=heading)


class HeadingTests(unittest.TestCase):
    def test_item_headings_before_an_opening(self):
        opening = block("Mr. BORAH. I move that the Senate proceed to the consideration of", False)
        for text in ("ELECTION OF SENATORS BY DIRECT VOTE.", "INCOME 'r.AX---OONSTITUTION.AL AMENDMENT.",
                     ":ELECTION OF SENATORS BY DmECT VOTE."):
            self.assertTrue(record.is_heading(block(text), opening), text)

    def test_openings_as_ocr_reads_them(self):
        for text in ("Tbe VICE-PRESIDENT. The morning business is closed.", "1\\Ir. CULLOl\\I. I move that",
                     "' 'l'he Sen:at-e, ;as in :Committee of the Whole, resumed", "By Mr . KEYES:",
                     "Bills and joint resolutions were introduced, read the first time"):
            self.assertTrue(record.opens_item(block(text, False)), text)
        for text in ("Mr. Speaker, this brings me to a brief consideration", "IOLA, KANS., January 5, 1917.",
                     "TROY, KANS., Fe1JrtUJry 5, W11.", "DOCTRINE.", "Four bills against the interests of"):
            self.assertFalse(record.opens_item(block(text, False)), text)

    def test_what_is_not_an_item_heading(self):
        opening = block("Mr. KELLY of Pennsylvania. Mr. Speaker, the gentleman", False)
        for text in ("Mr. UNDERWOOD. I do.", "~ Ir. UNDERWOOD. I do.", "Mr. SUTHERLA1'1D. I do.", "CLAYTON].",
                     "By Mr. CRANE:", "D. A. HOLLINGSWORTH.", "CHAS. E. TOWNSEND.", "PORTLAND, OREG., July 30.",
                     "The VICE-PRESIDENT. No. 40."):
            self.assertFalse(record.is_heading(block(text), opening), text)
        self.assertFalse(record.is_heading(block("TAXES ON INCOMES.", heading=False), opening))

    def test_articles_and_roll_calls_stay_in_the_item(self):
        for text in ("YEAS-77.", "NOT VOTING-15.", '"ARTICLE I.', "ARl:ICLE -,", "ARTICLJ: -.", "ARTICLE -."):
            self.assertTrue(record.INNER.match(text), text)
        self.assertFalse(record.INNER.match("NATIONAL PROHIBITION."))

    def test_subject_headings_as_ocr_reads_them(self):
        cases = {16: ("TAX ON INCOMES.", "TAXES ON INCOJ'.IES.", "INCOME 'r.AX---OONSTITUTION.AL AMENDMENT."),
                 17: ("ELECTION OF SENATORS IlY DIRECT VOTE.", "ELECTION OF SENATORS DY POPULAR '\\'OTE.",
                      "DIBECT ELECTION OF SENATORS."),
                 18: ("NATION -WIDE PROHIBITION.", "-ATIOX.AJ~ PROHffiiTION.", "NATIONAL PROHIBmON~"),
                 19: ("WO~IAN SUFFRAGE.", "WO : ~LA . ~ SUFFRAGE.", "WOMAN strFFRAGE.")}
        for number, texts in cases.items():
            for text in texts:
                self.assertTrue(record.named_heading(block(text), record.AMENDMENTS[number].headings), text)
        self.assertFalse(record.named_heading(block("PROHIBITION IN PORTO RICO."), record.AMENDMENTS[18].headings))
        self.assertFalse(record.named_heading(block("EXECUTIVE SESSION."), record.AMENDMENTS[17].headings))

    def test_houses_and_datelines(self):
        self.assertEqual(record.house_of(block("SENATE.")), "Senate")
        self.assertEqual(record.house_of(block("HOUSE OF REPRESENTATIVES.")), "House")
        self.assertIsNone(record.house_of(block("House of Representatives, Washington, D. C.")))
        for text, date in (("MONDAY, July 12, 1909.", dt.date(1909, 7, 12)),
                           ("TrasnAY, May 16, 19 11.", dt.date(1911, 5, 16)),
                           ("Fnmu, Ap1·il ~6, 1912.", dt.date(1912, 4, 26)),
                           ("TUESDAY, Ap ' ril ~3, 191B .", dt.date(1912, 4, 23)),
                           ("~fO}o.TDAY, July ~3, 191!•", dt.date(1917, 7, 23))):
            self.assertTrue(record.is_dateline(block(text), date), text)
        # The next day's dateline is not this day's.
        self.assertFalse(record.is_dateline(block("SATIDIDAY, April ~7, 1912."), dt.date(1912, 4, 26)))


class TableTests(unittest.TestCase):
    def test_days(self):
        seen = set()
        for number, house, date, granule, pages in record.DAYS:
            self.assertIn(number, record.AMENDMENTS)
            self.assertIn(house, record.HOUSES)
            self.assertNotIn((house, date), seen)
            seen.add((house, date))
            self.assertTrue(record.index_pages(pages))
            session = record.session_of(granule)  # its part is in a session's list
            self.assertIn(session.year, (date.year, date.year + 1))
        for table in (record.EXTRA_HEADINGS, record.INSIDE, record.SPEECH_HEADINGS, record.ELSEWHERE,
                      record.RUNS_TO):
            self.assertTrue(set(table) <= seen, table)

    def test_index_pages(self):
        self.assertEqual(record.index_pages("306-309, 319"), [306, 307, 308, 309, 319])

    def test_ids_and_works(self):
        self.assertEqual(record.granule_id("GPO-CRECB-1909-pt4-v44-16-1"), "govinfo-crecb-1909-pt4-v44-16-1")
        self.assertEqual(record.package_of("GPO-CRECB-1909-pt4-v44-16-1"), "GPO-CRECB-1909-pt4-v44")
        self.assertEqual(record.ia_id("GPO-CRECB-1909-pt4-v44", "text"), "ia-record-1909-pt4-v44-text")
        for id_ in (record.granule_id("GPO-CRECB-1909-pt4-v44-16-1"), record.mods_id("GPO-CRECB-1909-pt4-v44"),
                    record.ia_id("GPO-CRECB-1909-pt4-v44", "text")):
            self.assertTrue(any(Path(id_ + ".x").match(p) for p in UNTRACKED_RAW), id_)
        w = record.work_of("Senate", record.SESSIONS["1917b"], record.AMENDMENTS[18])
        self.assertEqual((w["id"], w["prefix"]), ("senate-eighteenth-amendment-1917b", "Senate1917b"))
        self.assertEqual(w["short"], "Senate debates, 1917 (2d session)")
        # Every work has site settings in its amendment's group.
        for number, house, date, granule, _ in record.DAYS:
            wid = record.work_of(house, record.session_of(granule), record.AMENDMENTS[number])["id"]
            self.assertEqual(WORKS[wid]["collection"], "congress")
            self.assertIn(record.ORDINALS[number], WORKS[wid]["group"])


class ScanTests(unittest.TestCase):
    def test_govinfo_pages_and_microfilm_images(self):
        scan = {"item": "GPO-CRECB-1909-pt4-v44-16-1", "leaves": [6, 7], "site": "govinfo",
                "microfilm": {"item": "sim_congressional-record_june-17-july-13-1909_44", "leaves": [380, 381]}}
        self.assertEqual(scan_url(scan["item"], 7, "govinfo", scan),
                         "https://www.govinfo.gov/content/pkg/GPO-CRECB-1909-pt4-v44/pdf/"
                         "GPO-CRECB-1909-pt4-v44-16-1.pdf#page=7")
        self.assertEqual(scan_image(scan["item"], 7, "govinfo", scan),
                         "https://archive.org/download/sim_congressional-record_june-17-july-13-1909_44/page/n380_w1200.jpg")
        with self.assertRaises(ValueError):
            scan_url("javascript:alert(1)", 1, "govinfo", scan)


class SheetTests(unittest.TestCase):
    def test_record_works_are_split_by_their_html(self):
        # Many short passages with marked words: light text, heavy pages.
        segs = [{"ref": f"House1909.Jul12.{n}", "text": "Mr. PAYNE. I do.",
                 "uncertain": [{"start": 0, "end": 3, "readings": {"microfilm": "Mr.", "primary": "l\\Ir."}}]}
                for n in range(1, 801)]
        self.assertEqual(len(sheets(segs)), 1)
        split = sheets(segs, by_html=True)
        self.assertGreater(len(split), 1)
        self.assertEqual(sum(len(s) for s in split), 800)
        for sheet in split:
            self.assertLess(len(sheet) * 1100, SHEET_HTML_BYTES)
        for wid, cfg in WORKS.items():
            self.assertEqual(cfg.get("sheet_by_html", False), cfg.get("printed_in") == "Congressional Record", wid)


class PdfWordsTests(unittest.TestCase):
    def test_words_and_their_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.pdf"
            path.write_bytes(make_pdf(b"BT /F1 10 Tf 72 700 Td (Two words) Tj ET"))
            page = pdf_words(path)[0]
        self.assertEqual([w.text for w in page.words], ["Two", "words"])
        self.assertLess(page.words[0].x1, page.words[1].x)
        self.assertAlmostEqual(page.words[0].y, 92)


class NumeralHeadTests(unittest.TestCase):
    """`ocr.NUMERAL_HEAD` with possessive runs matches what it matched before,
    without exponential time on a table of figures (the Congressional Record)."""

    def test_same_matches(self):
        old = re.compile(r"(?i)^(?:(?:[ivxlc]+|\d+|sec|six|to|and|inclusive)[.,;]*\s*|;\s*)+$")
        parts = ["i", "v", "x", "l", "c", "1", "2", "0", "sec", "six", "to", "and", "inclusive", ".", ",", ";", " ",
                 "a", "s", "n"]
        rng = random.Random(0)
        for _ in range(20000):
            s = "".join(rng.choice(parts) for _ in range(rng.randint(0, 7)))
            self.assertEqual(bool(old.match(s)), bool(NUMERAL_HEAD.match(s)), s)

    def test_a_table_of_figures_is_quick(self):
        line = "50 2,035 ,000 s 1 , 758,000 19 1 ,570,000 a 478,000 229 31 90,784,000 69,230,000 31 12,955,000"
        self.assertIsNone(NUMERAL_HEAD.match(line))  # (took minutes before)


class CacheTests(unittest.TestCase):
    def test_every_family_has_a_key_and_a_cache_in_each_workflow(self):
        keys = fetch.cache_keys()
        self.assertEqual(set(keys), set(UNTRACKED_FAMILIES))
        for wf in ("ci.yml", "errata.yml", "review.yml"):
            text = (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")
            for name, pattern in UNTRACKED_FAMILIES.items():
                self.assertIn(f"path: sources/raw/{pattern}", text, (wf, name))
                self.assertIn(f"key: raw-{name}-${{{{ steps.raw-keys.outputs.{name} }}}}", text, (wf, name))
        # No family's key prefix is another's (restore-keys match by prefix).
        for a in UNTRACKED_FAMILIES:
            for b in UNTRACKED_FAMILIES:
                self.assertFalse(a != b and f"raw-{b}-".startswith(f"raw-{a}-"), (a, b))


if __name__ == "__main__":
    unittest.main()
