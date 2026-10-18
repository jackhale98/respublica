import unittest

from importers.federalist import _emphasis, _paragraphs
from tools.common import check_url, collapse_ws, is_safe_url, normalize_for_match, parse_html, roman_to_int, UnsafeURLError


class URLTests(unittest.TestCase):
    def test_allows_http_and_https(self):
        self.assertTrue(is_safe_url("https://www.archives.gov/x"))
        self.assertTrue(is_safe_url("http://example.org"))

    def test_rejects_other_schemes(self):
        for url in ("javascript:alert(1)", "JAVASCRIPT:alert(1)", "data:text/html,x", "file:///etc/passwd",
                    "//example.org", "/relative", "https:///nohost", " https://x.org", "vbscript:x", ""):
            self.assertFalse(is_safe_url(url), url)
        with self.assertRaises(UnsafeURLError):
            check_url("javascript:alert(1)")


class TextTests(unittest.TestCase):
    def test_collapse_ws(self):
        self.assertEqual(collapse_ws("  a  b\n\tc "), "a b c")

    def test_normalize_only_touches_whitespace_and_quotes(self):
        self.assertEqual(normalize_for_match("“defence”  ’tis"), "\"defence\" 'tis")
        self.assertNotEqual(normalize_for_match("defence"), normalize_for_match("defense"))

    def test_roman(self):
        self.assertEqual([roman_to_int(x) for x in ("I", "IV", "IX", "XIV", "XLIX", "LXXXV")], [1, 4, 9, 14, 49, 85])
        with self.assertRaises(ValueError):
            roman_to_int("ABC")

    def test_html_text_keeps_br_as_newline(self):
        root = parse_html("<p><a href='x'>Geo: Read</a><br />\n  <a>John Dickinson</a></p>")
        self.assertEqual(root.find_all("p")[0].text(), "Geo: Read\nJohn Dickinson")


class FederalistParsingTests(unittest.TestCase):
    def test_paragraphs_join_wrapped_lines(self):
        self.assertEqual(_paragraphs(["one", "two", "", "", "three"]), ["one two", "three"])

    def test_emphasis_spans(self):
        text, spans = _emphasis("Aspasia, _vide_ Plutarch")
        self.assertEqual(text, "Aspasia, vide Plutarch")
        self.assertEqual([text[a:b] for a, b in spans], ["vide"])



class PinTests(unittest.TestCase):
    def test_node_version_pins_agree(self):
        # Cloudflare reads .node-version at the root; the site's tools read site/.nvmrc.
        from tools.common import ROOT
        self.assertEqual((ROOT / ".node-version").read_text().strip(), (ROOT / "site" / ".nvmrc").read_text().strip())

if __name__ == "__main__":
    unittest.main()
