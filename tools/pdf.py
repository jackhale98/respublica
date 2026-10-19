"""Text from PDF files, with the standard library only.

    from tools.pdf import pdf_lines
    for page in pdf_lines(path):          # one list per page
        for line in page:                 # top to bottom
            print(line.y, line.x0, line.size, line.text)

Enough of PDF for the government PDFs this project reads (govinfo's
Constitution Annotated, the Supreme Court's opinions): cross-reference tables and streams, compressed
object streams, Flate with PNG predictors, the page tree with inherited
resources, the text operators, and the standard security handler's RC4
encryption with an empty user password (a PDF anyone may open, with
permissions set: the Supreme Court's opinions). Characters come from each font's
ToUnicode map (or its encoding); positions come from the text and graphics
matrices, so text can be put back into lines and columns. It does not
render anything, and it fails loudly on what it does not understand.
"""

from __future__ import annotations

import hashlib
import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path


class PDFError(ValueError):
    pass


# ------------------------------------------------------------ objects


@dataclass(frozen=True)
class Ref:
    num: int
    gen: int


class Name(str):
    pass


@dataclass
class Stream:
    dict: dict
    raw: bytes

    def data(self) -> bytes:
        filters = self.dict.get("Filter")
        parms = self.dict.get("DecodeParms")
        if filters is None:
            return self.raw
        if not isinstance(filters, list):
            filters, parms = [filters], [parms]
        elif not isinstance(parms, list):
            parms = [parms] * len(filters)
        out = self.raw
        for f, p in zip(filters, parms):
            if f in ("FlateDecode", "Fl"):
                out = _inflate(out)
                if isinstance(p, dict) and p.get("Predictor", 1) >= 10:
                    out = _png_unpredict(out, p.get("Columns", 1) * p.get("Colors", 1) * p.get("BitsPerComponent", 8) // 8)
            else:
                raise PDFError(f"unsupported filter {f}")
        return out


def _inflate(data: bytes) -> bytes:
    d = zlib.decompressobj()
    try:
        return d.decompress(data) + d.flush()
    except zlib.error:
        # Some writers end a stream with stray bytes; keep what decoded.
        return d.decompress(data[:-1]) if len(data) > 1 else b""


def _png_unpredict(data: bytes, columns: int) -> bytes:
    row = columns + 1
    prev = bytearray(columns)
    out = bytearray()
    for i in range(0, len(data) - row + 1, row):
        kind, cur = data[i], bytearray(data[i + 1:i + row])
        for j in range(columns):
            left = cur[j - 1] if j else 0
            up, ul = prev[j], (prev[j - 1] if j else 0)
            if kind == 1:
                cur[j] = (cur[j] + left) & 255
            elif kind == 2:
                cur[j] = (cur[j] + up) & 255
            elif kind == 3:
                cur[j] = (cur[j] + (left + up) // 2) & 255
            elif kind == 4:
                p = left + up - ul
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - ul)
                cur[j] = (cur[j] + (left if pa <= pb and pa <= pc else up if pb <= pc else ul)) & 255
        out += cur
        prev = cur
    return bytes(out)


WS = b" \t\r\n\f\x00"
DELIM = b"()<>[]{}/%"
TOKEN = re.compile(rb"\s*(?:%[^\r\n]*[\r\n]\s*)*")


class Lexer:
    """Reads PDF objects from bytes, starting at `pos`."""

    def __init__(self, data: bytes, pos: int = 0):
        self.data, self.pos = data, pos

    def skip(self) -> None:
        d, n = self.data, len(self.data)
        while self.pos < n:
            c = d[self.pos]
            if c in WS:
                self.pos += 1
            elif c == 37:  # %
                while self.pos < n and d[self.pos] not in b"\r\n":
                    self.pos += 1
            else:
                break

    def word(self) -> bytes:
        self.skip()
        start = self.pos
        d, n = self.data, len(self.data)
        while self.pos < n and d[self.pos] not in WS and d[self.pos] not in DELIM:
            self.pos += 1
        return d[start:self.pos]

    def obj(self):
        self.skip()
        d = self.data
        if self.pos >= len(d):
            raise PDFError("unexpected end of data")
        c = d[self.pos:self.pos + 1]
        if c == b"/":
            self.pos += 1
            return Name(_name(self.word()))
        if c == b"(":
            return self.literal()
        if d[self.pos:self.pos + 2] == b"<<":
            self.pos += 2
            out = {}
            while True:
                self.skip()
                if d[self.pos:self.pos + 2] == b">>":
                    self.pos += 2
                    break
                key = self.obj()
                out[str(key)] = self.obj()
            self.skip()
            if d[self.pos:self.pos + 6] == b"stream":
                return self.stream(out)
            return out
        if c == b"<":
            end = d.index(b">", self.pos)
            hexs = re.sub(rb"\s", b"", d[self.pos + 1:end])
            self.pos = end + 1
            return bytes.fromhex((hexs + b"0" * (len(hexs) % 2)).decode())
        if c == b"[":
            self.pos += 1
            out = []
            while True:
                self.skip()
                if d[self.pos:self.pos + 1] == b"]":
                    self.pos += 1
                    return out
                out.append(self.obj())
        w = self.word()
        if not w:
            raise PDFError(f"unexpected {d[self.pos:self.pos + 10]!r}")
        if w == b"true":
            return True
        if w == b"false":
            return False
        if w == b"null":
            return None
        if re.fullmatch(rb"[+-]?\d+", w):
            # "n g R" is a reference.
            save = self.pos
            g = self.word()
            if re.fullmatch(rb"\d+", g):
                r = self.word()
                if r == b"R":
                    return Ref(int(w), int(g))
            self.pos = save
            return int(w)
        if re.fullmatch(rb"[+-]?(\d+\.?\d*|\.\d+)", w):
            return float(w)
        return Operator(w.decode("latin-1"))

    def literal(self) -> bytes:
        d = self.data
        self.pos += 1
        depth, out = 1, bytearray()
        while True:
            c = d[self.pos]
            self.pos += 1
            if c == 92:  # backslash
                e = d[self.pos]
                self.pos += 1
                if e in b"nrtbf":
                    out.append({110: 10, 114: 13, 116: 9, 98: 8, 102: 12}[e])
                elif 48 <= e <= 55:
                    digits = bytes([e])
                    while len(digits) < 3 and 48 <= d[self.pos] <= 55:
                        digits += d[self.pos:self.pos + 1]
                        self.pos += 1
                    out.append(int(digits, 8) & 255)
                elif e in b"\r\n":
                    if e == 13 and d[self.pos:self.pos + 1] == b"\n":
                        self.pos += 1
                else:
                    out.append(e)
            elif c == 40:
                depth += 1
                out.append(c)
            elif c == 41:
                depth -= 1
                if depth == 0:
                    return bytes(out)
                out.append(c)
            else:
                out.append(c)

    def stream(self, d: dict) -> Stream:
        self.pos += 6
        if self.data[self.pos:self.pos + 2] == b"\r\n":
            self.pos += 2
        elif self.data[self.pos:self.pos + 1] in (b"\n", b"\r"):
            self.pos += 1
        length = d.get("Length")
        if isinstance(length, Ref):
            length = self.resolve(length) if hasattr(self, "resolve") else None
        if isinstance(length, int):
            raw = self.data[self.pos:self.pos + length]
            self.pos += length
        else:
            end = self.data.index(b"endstream", self.pos)
            raw = self.data[self.pos:end].rstrip(b"\r\n")
            self.pos = end
        end = self.data.find(b"endstream", self.pos)
        if end >= 0:
            self.pos = end + 9
        return Stream(d, raw)


class Operator(str):
    pass


# The standard security handler (PDF 1.7, 7.6.3), RC4 only, revisions 2 to 4,
# for a file with an empty user password: what readers do to open it.
_PAD = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")


def _rc4(key: bytes, data: bytes) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) & 255
        s[i], s[j] = s[j], s[i]
    out = bytearray(len(data))
    i = j = 0
    for k, byte in enumerate(data):
        i = (i + 1) & 255
        j = (j + s[i]) & 255
        s[i], s[j] = s[j], s[i]
        out[k] = byte ^ s[(s[i] + s[j]) & 255]
    return bytes(out)


def _as_bytes(v) -> bytes:
    return v if isinstance(v, bytes) else str(v).encode("latin-1")


def _file_key(enc: dict, trailer: dict) -> bytes:
    if enc.get("Filter") != "Standard":
        raise PDFError(f"unsupported security handler {enc.get('Filter')}")
    v, r = enc.get("V", 0), enc.get("R", 2)
    if v == 4:
        cfm = enc.get("CF", {}).get(enc.get("StmF", "StdCF"), {}).get("CFM")
        if cfm != "V2":
            raise PDFError(f"unsupported crypt filter {cfm} (only RC4)")
    if r not in (2, 3, 4):
        raise PDFError(f"unsupported security handler revision {r}")
    n = 5 if r == 2 else enc.get("Length", 40) // 8
    ids = trailer.get("ID") or [b""]
    h = hashlib.md5(_PAD + _as_bytes(enc["O"])[:32] + (enc["P"] & 0xFFFFFFFF).to_bytes(4, "little") + _as_bytes(ids[0]))
    if r == 4 and enc.get("EncryptMetadata", True) is False:
        h.update(b"\xff\xff\xff\xff")
    key = h.digest()
    if r >= 3:
        for _ in range(50):
            key = hashlib.md5(key[:n]).digest()
    return key[:n]


def _object_key(key: bytes, num: int, gen: int) -> bytes:
    k = hashlib.md5(key + num.to_bytes(4, "little")[:3] + gen.to_bytes(4, "little")[:2]).digest()
    return k[:min(len(key) + 5, 16)]


def _name(b: bytes) -> str:
    return re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), b).decode("latin-1")


# ------------------------------------------------------------ document


class Document:
    def __init__(self, data: bytes):
        self.data = data
        self.xref: dict[int, tuple] = {}  # num -> ("f", offset) | ("s", objstm, index)
        self.trailer: dict = {}
        self._cache: dict[int, object] = {}
        self._objstm: dict[int, list] = {}
        start = data.rfind(b"startxref")
        if start < 0:
            raise PDFError("no startxref")
        offset = int(Lexer(data, start + 9).word())
        seen = set()
        while offset is not None and offset not in seen:
            seen.add(offset)
            offset = self._read_xref(offset)
        self._key: bytes | None = None
        if "Encrypt" in self.trailer:
            self._key = _file_key(self.get(self.trailer["Encrypt"]), self.trailer)

    def _read_xref(self, offset: int):
        lx = Lexer(self.data, offset)
        lx.skip()
        if self.data[lx.pos:lx.pos + 4] == b"xref":
            lx.pos += 4
            while True:
                lx.skip()
                if self.data[lx.pos:lx.pos + 7] == b"trailer":
                    lx.pos += 7
                    trailer = lx.obj()
                    break
                first, count = int(lx.word()), int(lx.word())
                lx.skip()
                for i in range(count):
                    line = self.data[lx.pos:lx.pos + 20]
                    lx.pos += 20
                    off, _, kind = line.split()[:3]
                    if kind == b"n" and first + i not in self.xref:
                        self.xref[first + i] = ("f", int(off))
        else:
            # A cross-reference stream: "n g obj << /Type /XRef … >> stream".
            lx.word(), lx.word(), lx.word()
            stream = lx.obj()
            if not isinstance(stream, Stream):
                raise PDFError("bad xref stream")
            trailer = stream.dict
            w = trailer["W"]
            index = trailer.get("Index", [0, trailer["Size"]])
            rows = stream.data()
            size = sum(w)
            pos = 0
            for first, count in zip(index[::2], index[1::2]):
                for i in range(count):
                    f = [int.from_bytes(rows[pos + sum(w[:k]):pos + sum(w[:k + 1])], "big") if w[k] else None
                         for k in range(3)]
                    pos += size
                    kind = 1 if f[0] is None else f[0]
                    num = first + i
                    if num in self.xref:
                        continue
                    if kind == 1:
                        self.xref[num] = ("f", f[1])
                    elif kind == 2:
                        self.xref[num] = ("s", f[1], f[2])
        for k, v in trailer.items():
            self.trailer.setdefault(k, v)
        return trailer.get("Prev")

    def get(self, obj):
        """Resolve a reference (once); other values pass through."""
        if not isinstance(obj, Ref):
            return obj
        if obj.num in self._cache:
            return self._cache[obj.num]
        entry = self.xref.get(obj.num)
        if entry is None:
            value = None
        elif entry[0] == "f":
            lx = Lexer(self.data, entry[1])
            lx.resolve = self.get
            num, gen, _ = lx.word(), lx.word(), lx.word()  # "n g obj"
            value = lx.obj()
            # Streams of an encrypted file are decrypted with the object's
            # own key (not cross-reference streams or unencrypted metadata).
            if self._key and isinstance(value, Stream) and value.dict.get("Type") not in ("XRef", "Metadata"):
                value = Stream(value.dict, _rc4(_object_key(self._key, int(num), int(gen)), value.raw))
        else:
            value = self._from_objstm(entry[1], entry[2])
        self._cache[obj.num] = value
        return value

    def _from_objstm(self, stm: int, index: int):
        if stm not in self._objstm:
            s = self.get(Ref(stm, 0))
            data = s.data()
            n, first = s.dict["N"], s.dict["First"]
            head = Lexer(data, 0)
            offsets = [(int(head.word()), int(head.word())) for _ in range(n)]
            objs = []
            for _, off in offsets:
                lx = Lexer(data, first + off)
                lx.resolve = self.get
                objs.append(lx.obj())
            self._objstm[stm] = objs
        return self._objstm[stm][index]

    def pages(self) -> list[dict]:
        root = self.get(self.trailer["Root"])
        out: list[dict] = []

        def walk(node, inherited):
            node = self.get(node)
            res = node.get("Resources", inherited.get("Resources"))
            box = node.get("MediaBox", inherited.get("MediaBox"))
            if node.get("Type") == "Pages" or "Kids" in node:
                for kid in self.get(node["Kids"]):
                    walk(kid, {"Resources": res, "MediaBox": box})
            else:
                out.append({**node, "Resources": res, "MediaBox": box})

        walk(root["Pages"], {})
        return out


# ------------------------------------------------------------ fonts

# Glyph names likely in a font's /Differences, for fonts without ToUnicode.
GLYPHS = {
    "space": " ", "quoteright": "’", "quoteleft": "‘", "quotedblleft": "“", "quotedblright": "”",
    "endash": "–", "emdash": "—", "hyphen": "-", "bullet": "•", "section": "§", "paragraph": "¶",
    "fi": "fi", "fl": "fl", "ff": "ff", "ffi": "ffi", "ffl": "ffl", "dagger": "†", "daggerdbl": "‡",
    "ellipsis": "…", "periodcentered": "·", "quotesingle": "'", "minus": "-",
}


@dataclass
class Font:
    to_unicode: dict[int, str] = field(default_factory=dict)
    widths: dict[int, float] = field(default_factory=dict)
    default_width: float = 500.0
    two_byte: bool = False

    def decode(self, s: bytes) -> list[tuple[str, float]]:
        """(text, width in 1/1000 em) for each character code."""
        codes = [int.from_bytes(s[i:i + 2], "big") for i in range(0, len(s) - 1, 2)] if self.two_byte else list(s)
        out = []
        for c in codes:
            ch = self.to_unicode.get(c)
            if ch is None:
                ch = chr(c) if 32 <= c < 127 else ""
            out.append((ch, self.widths.get(c, self.default_width)))
        return out


_CMAPS: dict[bytes, dict[int, str]] = {}


def _parse_cmap(data: bytes) -> dict[int, str]:
    """A ToUnicode map. Parsed once per content: a scan's text layer (govinfo)
    gives every page its own copy of one map of 65,536 codes. The map
    returned is shared; callers must not change it."""
    key = hashlib.sha256(data).digest()
    if key not in _CMAPS:
        _CMAPS[key] = _read_cmap(data)
    return _CMAPS[key]


def _read_cmap(data: bytes) -> dict[int, str]:
    out: dict[int, str] = {}

    def text(h: bytes) -> str:
        return bytes.fromhex(h.decode()).decode("utf-16-be", "replace")

    for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
            out[int(src, 16)] = text(dst)
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for lo, hi, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]*>|\[[^\]]*\])", block):
            lo, hi = int(lo, 16), int(hi, 16)
            if dst.startswith(b"["):
                for i, h in enumerate(re.findall(rb"<([0-9A-Fa-f]*)>", dst)):
                    out[lo + i] = text(h)
            else:
                h = dst[1:-1]
                base = bytes.fromhex(h.decode())
                for i in range(hi - lo + 1):
                    b = bytearray(base)
                    b[-1] = (b[-1] + i) & 255
                    out[lo + i] = bytes(b).decode("utf-16-be", "replace")
    return out


def load_font(doc: Document, fd) -> Font:
    fd = doc.get(fd)
    f = Font()
    sub = fd.get("Subtype")
    if sub == "Type0":
        f.two_byte = True
        desc = doc.get(doc.get(fd["DescendantFonts"])[0])
        f.default_width = desc.get("DW", 1000)
        w = doc.get(desc.get("W", []))
        i = 0
        while i < len(w):
            first = doc.get(w[i])
            nxt = doc.get(w[i + 1])
            if isinstance(nxt, list):
                for k, width in enumerate(nxt):
                    f.widths[first + k] = doc.get(width)
                i += 2
            else:
                for c in range(first, nxt + 1):
                    f.widths[c] = doc.get(w[i + 2])
                i += 3
    else:
        first = fd.get("FirstChar", 0)
        for k, width in enumerate(doc.get(fd.get("Widths", [])) or []):
            f.widths[first + k] = doc.get(width)
        desc = doc.get(fd.get("FontDescriptor")) or {}
        f.default_width = doc.get(desc.get("MissingWidth", 500)) if isinstance(desc, dict) else 500
        enc = doc.get(fd.get("Encoding"))
        base = enc.get("BaseEncoding") if isinstance(enc, dict) else enc
        codec = {"WinAnsiEncoding": "cp1252", "MacRomanEncoding": "mac_roman"}.get(str(base), "latin-1")
        for code in range(32, 256):
            try:
                f.to_unicode[code] = bytes([code]).decode(codec)
            except UnicodeDecodeError:
                pass
        if str(base) not in ("WinAnsiEncoding", "MacRomanEncoding"):
            f.to_unicode.update({0x27: "’", 0x60: "‘"})  # StandardEncoding's quotes
        if isinstance(enc, dict):
            code = 0
            for item in doc.get(enc.get("Differences", [])):
                if isinstance(item, int):
                    code = item
                else:
                    name = str(item)
                    ch = GLYPHS.get(name) or (name if len(name) == 1 else None)
                    if ch is None and re.fullmatch(r"uni[0-9A-F]{4}", name):
                        ch = chr(int(name[3:], 16))
                    if ch is not None:
                        f.to_unicode[code] = ch
                    code += 1
    tu = doc.get(fd.get("ToUnicode"))
    if isinstance(tu, Stream):
        cmap = _parse_cmap(tu.data())
        if f.to_unicode:
            f.to_unicode.update(cmap)
        else:
            f.to_unicode = cmap  # shared, never changed
    return f


# ------------------------------------------------------------ text


@dataclass
class Glyphs:
    x: float
    y: float
    size: float
    text: str
    x1: float


@dataclass
class Line:
    y: float      # baseline, from the top of the page
    x0: float
    x1: float
    size: float
    text: str


def _mul(a, b):
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def page_text(doc: Document, page: dict, fonts_cache: dict) -> tuple[list[Glyphs], float]:
    """Positioned runs of text on one page, and the page height."""
    res = doc.get(page.get("Resources")) or {}
    font_dict = doc.get(res.get("Font")) or {}
    box = [doc.get(v) for v in doc.get(page.get("MediaBox") or [0, 0, 612, 792])]
    height = box[3] - box[1]
    contents = doc.get(page.get("Contents"))
    parts = contents if isinstance(contents, list) else [contents]
    data = b"\n".join(doc.get(p).data() for p in parts if p is not None)

    def font(name):
        ref = font_dict.get(name)
        key = ref.num if isinstance(ref, Ref) else id(ref)
        if key not in fonts_cache:
            fonts_cache[key] = load_font(doc, ref) if ref is not None else Font()
        return fonts_cache[key]

    out: list[Glyphs] = []
    ctm = [1, 0, 0, 1, 0, 0]
    stack = []
    tm = lm = [1, 0, 0, 1, 0, 0]
    cur, size, tc, tw, th, tl, rise = Font(), 0.0, 0.0, 0.0, 1.0, 0.0, 0.0
    operands: list = []
    lx = Lexer(data)

    def show(s: bytes):
        nonlocal tm
        trm = _mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm))
        x, y = trm[4], trm[5]
        scale = abs(trm[3]) or abs(trm[0]) or size
        text = []
        adv = 0.0
        # Character spacing of a quarter em or more separates words: some
        # writers space small capitals that way ("(1H)Tj" with Tc .41).
        wide = size and tc / size >= 0.25
        for i, (ch, w) in enumerate(cur.decode(s)):
            if wide and i and ch != " " and text[-1] != " ":
                text.append(" ")
            text.append(ch)
            step = (w / 1000 * size + tc + (tw if ch == " " else 0)) * th
            adv += step
        tm = _mul([1, 0, 0, 1, adv, 0], tm)
        end = _mul([1, 0, 0, 1, adv, 0], [1, 0, 0, 1, 0, 0])
        x1 = _mul(_mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm)), [1, 0, 0, 1, 0, 0])[4]
        if text:
            out.append(Glyphs(x, height - y, scale, "".join(text), x1))
        return end

    while True:
        lx.skip()
        if lx.pos >= len(data):
            break
        if data[lx.pos:lx.pos + 2] == b"BI":  # inline image: skip to EI
            end = data.find(b"EI", lx.pos + 2)
            lx.pos = (end + 2) if end >= 0 else len(data)
            operands = []
            continue
        try:
            tok = lx.obj()
        except (PDFError, ValueError, IndexError):
            lx.pos += 1
            operands = []
            continue
        if not isinstance(tok, Operator):
            operands.append(tok)
            continue
        op = str(tok)
        o = operands
        operands = []
        if op == "q":
            stack.append(ctm)
        elif op == "Q":
            ctm = stack.pop() if stack else [1, 0, 0, 1, 0, 0]
        elif op == "cm" and len(o) == 6:
            ctm = _mul([float(v) for v in o], ctm)
        elif op == "BT":
            tm = lm = [1, 0, 0, 1, 0, 0]
        elif op == "Tf" and len(o) == 2:
            cur, size = font(str(o[0])), float(o[1])
        elif op == "Tc" and o:
            tc = float(o[0])
        elif op == "Tw" and o:
            tw = float(o[0])
        elif op == "Tz" and o:
            th = float(o[0]) / 100
        elif op == "TL" and o:
            tl = float(o[0])
        elif op == "Ts" and o:
            rise = float(o[0])
        elif op == "Tm" and len(o) == 6:
            tm = lm = [float(v) for v in o]
        elif op in ("Td", "TD") and len(o) == 2:
            if op == "TD":
                tl = -float(o[1])
            tm = lm = _mul([1, 0, 0, 1, float(o[0]), float(o[1])], lm)
        elif op == "T*":
            tm = lm = _mul([1, 0, 0, 1, 0, -tl], lm)
        elif op == "Tj" and o:
            show(o[0])
        elif op in ("'", '"') and o:
            if op == '"':
                tw, tc = float(o[0]), float(o[1])
            tm = lm = _mul([1, 0, 0, 1, 0, -tl], lm)
            show(o[-1])
        elif op == "TJ" and o:
            for item in o[0]:
                if isinstance(item, bytes):
                    show(item)
                elif isinstance(item, (int, float)):
                    shift = -item / 1000 * size * th
                    tm = _mul([1, 0, 0, 1, shift, 0], tm)
                    if item < -180:  # a gap wide enough to be a space
                        out.append(Glyphs(0, 0, 0, "\x00", 0))
    return out, height


def _lines(runs: list[Glyphs], column_gap: float | None = None) -> list[Line]:
    # A "\x00" run marks a wide TJ gap after the run before it.
    marked = []
    for r in runs:
        if r.text == "\x00":
            if marked:
                marked[-1] = Glyphs(marked[-1].x, marked[-1].y, marked[-1].size, marked[-1].text + " ", marked[-1].x1)
            continue
        if r.text.strip() or r.text == " ":
            marked.append(r)
    marked.sort(key=lambda r: (round(r.y, 1), r.x))
    lines: list[list[Glyphs]] = []
    for r in marked:
        if lines and abs(lines[-1][0].y - r.y) <= max(1.5, 0.3 * r.size):
            lines[-1].append(r)
        else:
            lines.append([r])
    if column_gap is not None:
        # Table cells: a gap wider than column_gap starts a new line.
        split = []
        for ln in lines:
            ln.sort(key=lambda r: r.x)
            cell = [ln[0]]
            for r in ln[1:]:
                if r.x - cell[-1].x1 > column_gap:
                    split.append(cell)
                    cell = []
                cell.append(r)
            split.append(cell)
        lines = split
    out = []
    for ln in lines:
        ln.sort(key=lambda r: r.x)
        text = ""
        last_x1 = None
        prev = ln[0]
        for r in ln:
            if last_x1 is not None and not text.endswith(" ") and not r.text.startswith(" "):
                gap = r.x - last_x1
                # A word space; or a note number in small type before the
                # note's text ("2 THE RECORDS …"), which is set close.
                marker = re.fullmatch(r"\d+", prev.text.strip()) and prev.size < 0.8 * r.size and gap > -0.5
                if gap > 0.15 * max(r.size, prev.size) or marker:
                    text += " "
            text += r.text
            last_x1 = r.x1
            prev = r
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out.append(Line(ln[0].y, ln[0].x, ln[-1].x1, max(r.size for r in ln), text))
    out.sort(key=lambda l: (l.y, l.x0))
    return out


@dataclass
class PageWords:
    width: float
    height: float
    words: list[Glyphs]  # one per word: x, x1 across; y the baseline from the top


def pdf_words(path: Path | str) -> list[PageWords]:
    """Every page's words with their positions, in the order the page draws
    them, for a scan's text layer (govinfo's bound Congressional Record),
    where each word is drawn on its own and the layout is read from where
    the words sit. A run of several words is split at its spaces, each word
    taking its share of the run's width by its number of characters; a
    word's right edge stops short of the next word on its line (the text
    layer's invisible font is wider than the print)."""
    doc = Document(Path(path).read_bytes())
    fonts: dict = {}
    out = []
    for page in doc.pages():
        runs, height = page_text(doc, page, fonts)
        box = [doc.get(v) for v in doc.get(page.get("MediaBox") or [0, 0, 612, 792])]
        words: list[Glyphs] = []
        for r in runs:
            text = r.text.replace("\x00", " ")
            if not text.strip():
                continue
            per = (r.x1 - r.x) / max(len(text), 1)
            for m in re.finditer(r"\S+", text):
                x0 = r.x + per * m.start()
                words.append(Glyphs(x0, r.y, r.size, m.group(), r.x + per * m.end()))
        for k, w in enumerate(words):
            nxt = words[k + 1] if k + 1 < len(words) else None
            if nxt is not None and abs(nxt.y - w.y) <= max(1.0, 0.3 * w.size) and w.x < nxt.x < w.x1:
                w.x1 = max(w.x + 0.5, nxt.x - 0.5)
        out.append(PageWords(box[2] - box[0], height, words))
    return out


def pdf_lines(path: Path | str, column_gap: float | None = None,
              max_pages: int | None = None, start: int = 0) -> list[list[Line]]:
    """Every page's text as lines, top to bottom (y grows downwards). With
    `column_gap` (in points), text separated by a wider gap on the same
    line comes out as separate lines (table cells), ordered by y, then x.
    With `max_pages`, only that many pages are read, from page `start`
    (counting from 0)."""
    doc = Document(Path(path).read_bytes())
    fonts: dict = {}
    pages = []
    for page in doc.pages()[start:start + max_pages if max_pages is not None else None]:
        runs, _ = page_text(doc, page, fonts)
        pages.append(_lines(runs, column_gap))
    return pages
