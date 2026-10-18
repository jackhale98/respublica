import email.message
import io
import unittest
import urllib.error

from importers.cases import printed_name
from importers.courtlistener import CourtListenerError, clusters_for, docket_source, docket_url, match, printed_year
from importers.usreports import DATE_MORE, Paragraph, _finish, _merge_fragments, problems
from tools.common import _retry_after, auth_headers
from tools.pdf import Line


def cluster(cid, year="1954", name="Brown v. Board of Education"):
    return {"id": cid, "case_name": name, "date_filed": f"{year}-05-17", "absolute_url": f"/opinion/{cid}/x/"}


LOOKUP = [
    {"citation": "347 U.S. 483", "normalized_citations": ["347 U.S. 483"], "status": 200, "clusters": [cluster(105221)]},
    {"citation": "1 U.S. 1", "normalized_citations": ["1 U.S. 1"], "status": 404, "clusters": []},
    {"citation": "2 U.S. 2", "normalized_citations": ["2 U.S. 2"], "status": 300,
     "clusters": [cluster(1, "1790"), cluster(2, "1790")]},
]
RESPONSES = [
    ("courtlistener-citations-1", LOOKUP),
    ("courtlistener-scotus-19-1392", {"next": None, "results": [cluster(6481357, "2022", "Dobbs")]}),
]


class CourtListenerTests(unittest.TestCase):
    def test_docket_lookup(self):
        self.assertEqual(docket_source("No. 19-1392"), "courtlistener-scotus-19-1392")
        self.assertEqual(docket_url("No. 19-1392"),
                         "https://www.courtlistener.com/api/rest/v4/clusters/?docket__docket_number=19-1392&docket__court=scotus")
        with self.assertRaises(CourtListenerError):
            docket_url("347 U.S. 483")

    def test_printed_year(self):
        self.assertEqual(printed_year("Brown v. Board of Education, 347 U.S. 483 (1954)"), "1954")
        self.assertEqual(printed_year("Dobbs, No. 19-1392 (U.S. June 24, 2022)"), "2022")

    def test_match_one_cluster(self):
        m = match("347 U.S. 483", "Brown v. Board of Education, 347 U.S. 483 (1954)", RESPONSES)
        self.assertEqual((m.cluster["id"], m.source_id), (105221, "courtlistener-citations-1"))
        m = match("No. 19-1392", "Dobbs, No. 19-1392 (U.S. June 24, 2022)", RESPONSES)
        self.assertEqual(m.cluster["id"], 6481357)

    def test_several_clusters_by_name_year_and_citations(self):
        lookup = [{"citation": "3 U.S. 386", "normalized_citations": ["3 U.S. 386"], "status": 300, "clusters": [
            {**cluster(8403288, "1798", "Calder v. Wife"), "citation_count": 9},
            {**cluster(84695, "1798", "Calder v. Bull"), "citation_count": 1861}]},
                  {"citation": "109 U.S. 3", "normalized_citations": ["109 U.S. 3"], "status": 300, "clusters": [
            {**cluster(7890904, "1883", "United States v. Stanley"), "citation_count": 42},
            {**cluster(90897, "1883", "Civil Rights Cases"), "citation_count": 1001}]},
                  {"citation": "17 U.S. 122", "normalized_citations": ["17 U.S. 122"], "status": 300, "clusters": [
            {**cluster(6726666, "1819", "Sturges v. Crowninshield"), "citation_count": 65},
            {**cluster(85267, "1819", "Bank of Columbia v. Okely"), "citation_count": 671}]}]
        responses = [("courtlistener-citations-1", lookup)]
        m = match("3 U.S. 386", "Calder v. Bull, 3 U.S. (3 Dall.) 386 (1798)", responses)
        self.assertEqual(m.cluster["id"], 84695)
        self.assertIn("8403288", m.note)
        self.assertEqual(match("109 U.S. 3", "Civil Rights Cases, 109 U.S. 3 (1883)", responses).cluster["id"], 90897)
        # The other case filed under the citation is cited more, but its name is not the case's.
        self.assertEqual(match("17 U.S. 122", "Sturges v. Crowninshield, 17 U.S. (4 Wheat.) 122 (1819)",
                               responses).cluster["id"], 6726666)

    def test_match_fails_loudly(self):
        for key, name in (("1 U.S. 1", "A v. B, 1 U.S. 1 (1790)"),      # none
                          ("2 U.S. 2", "C v. D, 2 U.S. 2 (1790)"),      # several
                          ("347 U.S. 483", "Brown, 347 U.S. 483 (1955)"),  # wrong year
                          ("3 U.S. 3", "E v. F, 3 U.S. 3 (1791)")):     # never looked up
            with self.assertRaises(CourtListenerError, msg=key):
                match(key, name, RESPONSES)
        self.assertIsNone(clusters_for("3 U.S. 3", RESPONSES))


class SyllabusTests(unittest.TestCase):
    def test_printed_name(self):
        self.assertEqual(printed_name("McCulloch v. Maryland, 17 U.S. (4 Wheat.) 316 (1819)"), "McCulloch v. Maryland")
        self.assertEqual(printed_name("Dobbs v. Jackson, No. 19-1392 (U.S. June 24, 2022)"), "Dobbs v. Jackson")

    def test_paragraphs_rejoin_hyphens_and_stop_at_counsel(self):
        paras = _finish([
            (483, [Line(1, 50, 300, 9, "Segregation of children in public schools denies the equal pro-"),
                   Line(2, 50, 200, 9, "tection of the laws. Pp. 486-496.")]),
            (484, [Line(3, 50, 300, 10, "Robert L. Carter argued the cause for appellants.")]),
        ])
        self.assertEqual([(p.page, p.text) for p in paras],
                         [(483, "Segregation of children in public schools denies the equal protection of the laws. Pp. 486-496.")])

    def test_fragments_of_one_line_are_joined(self):
        lines = _merge_fragments([Line(493, 69, 180, 9, "2. The statute"), Line(496, 195, 300, 9, "did not violate"),
                                  Line(509, 60, 300, 9, "the First Amendment.")])
        self.assertEqual([l.text for l in lines], ["2. The statute did not violate", "the First Amendment."])

    def test_problems(self):
        ok = [Paragraph("Held: The statute is void. Pp. 3-9.", 1), Paragraph("74 N. J. L. 683, affirmed", 2)]
        self.assertEqual(problems(ok), [])
        self.assertEqual(len(problems([Paragraph("The decision in Hurtado v. California that the", 1),
                                       Paragraph("Reversed.", 2)])), 1)
        self.assertEqual(problems([]), ["no syllabus found"])

    def test_date_lines(self):
        for line in ("7, 1932.", "ruary 17, 1936.", "1958.-Opinion announced September 29, 1958.", "March 31, 1958.*"):
            self.assertTrue(DATE_MORE.search(line), line)
        self.assertFalse(DATE_MORE.search("On May 5, 1960, petitioner was arrested"))


class FetchTests(unittest.TestCase):
    def test_retry_after(self):
        headers = email.message.Message()
        headers["Retry-After"] = "39"
        e = urllib.error.HTTPError("https://x.test/", 429, "throttled", headers, io.BytesIO(b""))
        self.assertEqual(_retry_after(e), 40)
        body = b'{"detail":"Request was throttled. Expected available in 12 seconds."}'
        e = urllib.error.HTTPError("https://x.test/", 429, "throttled", email.message.Message(), io.BytesIO(body))
        self.assertEqual(_retry_after(e), 13)

    def test_auth_headers_need_the_variable(self):
        import os
        os.environ["RP_TEST_TOKEN"] = "abc"
        self.assertEqual(auth_headers("RP_TEST_TOKEN"), {"Authorization": "Token abc"})
        del os.environ["RP_TEST_TOKEN"]
        with self.assertRaises(KeyError):
            auth_headers("RP_TEST_TOKEN")


if __name__ == "__main__":
    unittest.main()
