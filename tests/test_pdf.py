import tempfile
import unittest
import zlib
from pathlib import Path

from tools.pdf import Lexer, Ref, _parse_cmap, pdf_lines


def make_pdf(content: bytes, compress: bool = True) -> bytes:
    """A one-page PDF with a WinAnsi Helvetica font and the given content."""
    stream = zlib.compress(content) if compress else content
    filt = b"/Filter /FlateDecode " if compress else b""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 /MediaBox [0 0 612 792] >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< " + filt + b"/Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding"
        b" /FirstChar 32 /LastChar 126 /Widths [" + b" ".join([b"500"] * 95) + b"] >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


class PdfTests(unittest.TestCase):
    def read(self, content: bytes, compress: bool = True):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.pdf"
            path.write_bytes(make_pdf(content, compress))
            return pdf_lines(path)

    def test_lines_in_reading_order(self):
        pages = self.read(b"BT /F1 10 Tf 72 700 Td (Second line) Tj 0 30 Td (First line) Tj ET")
        self.assertEqual([l.text for l in pages[0]], ["First line", "Second line"])
        self.assertAlmostEqual(pages[0][0].y, 792 - 730)
        self.assertEqual(pages[0][0].size, 10)

    def test_words_from_positioning_and_encoding(self):
        # A wide TJ gap and a WinAnsi apostrophe (0x92).
        pages = self.read(b"BT /F1 10 Tf 72 700 Td [(Ass\\222n) -300 (v.)] TJ ET", compress=False)
        self.assertEqual(pages[0][0].text, "Ass’n v.")

    def test_wide_character_spacing_separates_words(self):
        pages = self.read(b"BT /F1 10 Tf 72 700 Td 4 Tc (1H) Tj ET")
        self.assertEqual(pages[0][0].text, "1 H")

    def test_lexer(self):
        lx = Lexer(b"<< /A [1 2.5 (a\\(b\\)) <4142>] /B 3 0 R /C#20D true >>")
        self.assertEqual(lx.obj(), {"A": [1, 2.5, b"a(b)", b"AB"], "B": Ref(3, 0), "C D": True})

    def test_tounicode_map(self):
        cmap = b"beginbfchar <01> <0041> endbfchar beginbfrange <02> <04> <0061> endbfrange"
        self.assertEqual(_parse_cmap(cmap), {1: "A", 2: "a", 3: "b", 4: "c"})


if __name__ == "__main__":
    unittest.main()
