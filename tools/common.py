"""Shared helpers for importers and tools.

Everything that more than one importer or tool needs lives here: paths,
HTTP fetching, checksums, URL scheme checks, JSON I/O, whitespace and
quote normalization, and a small HTML tree builder. Do not copy these
into individual importers.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "sources"
RAW_DIR = SOURCES_DIR / "raw"
MANIFEST_PATH = SOURCES_DIR / "manifest.json"
TEXTS_DIR = ROOT / "texts"
CASES_DIR = ROOT / "cases"
LINKS_DIR = ROOT / "links"

USER_AGENT = "ResPublicaFetcher/0.1 (+https://library.commonhall.org)"
ALLOWED_SCHEMES = ("http", "https")


# ---------------------------------------------------------------- URLs


class UnsafeURLError(ValueError):
    pass


def is_safe_url(url: str) -> bool:
    """True only for absolute http: or https: URLs with a host."""
    if not isinstance(url, str) or url != url.strip():
        return False
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme in ALLOWED_SCHEMES and bool(parsed.netloc)


def check_url(url: str) -> str:
    """Return url unchanged, or raise if its scheme is not http/https."""
    if not is_safe_url(url):
        raise UnsafeURLError(f"refusing non-http(s) URL: {url!r}")
    return url


# ---------------------------------------------------------------- HTTP


def fetch_bytes(url: str, timeout: int = 60, attempts: int = 4) -> bytes:
    """GET a URL, retrying transient network errors with backoff.
    Redirects to a non-http(s) URL are refused."""
    check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                check_url(resp.geturl())
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt + 1 == attempts:
                raise
            time.sleep(2 ** (attempt + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt + 1 == attempts:
                raise
            time.sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")


# ---------------------------------------------------------------- files


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def dumps_json(obj: Any) -> str:
    """Pretty-printed JSON with sorted keys and a trailing newline."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_json(obj), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> Iterator[tuple[int, Any]]:
    """Yield (line_number, record) for each non-blank line."""
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if line.strip():
                yield n, json.loads(line)


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    return read_json(MANIFEST_PATH)


def raw_path(source_id: str) -> Path:
    """Path of the raw file for a manifest entry."""
    for entry in load_manifest():
        if entry["id"] == source_id:
            return ROOT / entry["path"]
    raise KeyError(f"source {source_id!r} is not in sources/manifest.json")


def read_raw_text(source_id: str) -> str:
    """Decode a raw file as UTF-8 and convert CRLF/CR line ends to LF."""
    text = raw_path(source_id).read_bytes().decode("utf-8")
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


# ---------------------------------------------------------------- text

_WS = re.compile(r"[ \t\n\r\f\v      ]+")
_QUOTES = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
})


def collapse_ws(s: str) -> str:
    """Collapse runs of whitespace (including no-break space) to one space."""
    return _WS.sub(" ", s).strip()


def normalize_for_match(s: str) -> str:
    """The only normalization allowed when matching quotes against text:
    whitespace runs and curly/straight quote-mark style. No spelling changes."""
    return collapse_ws(s.translate(_QUOTES))


_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(s: str) -> int:
    s = s.upper()
    if not s or any(c not in _ROMAN for c in s):
        raise ValueError(f"not a Roman numeral: {s!r}")
    total = 0
    for i, c in enumerate(s):
        v = _ROMAN[c]
        if i + 1 < len(s) and _ROMAN[s[i + 1]] > v:
            total -= v
        else:
            total += v
    return total


# ---------------------------------------------------------------- HTML

_VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node | str"] = field(default_factory=list)
    parent: "Node | None" = None

    def iter(self) -> Iterator["Node"]:
        """All element descendants (including self) in document order."""
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.iter()

    def find_all(self, *tags: str) -> list["Node"]:
        return [n for n in self.iter() if n.tag in tags]

    def raw_text(self) -> str:
        """Concatenated text with <br> as a newline; no normalization."""
        out: list[str] = []
        for c in self.children:
            if isinstance(c, str):
                out.append(c)
            elif c.tag == "br":
                out.append("\n")
            elif c.tag not in ("script", "style"):
                out.append(c.raw_text())
        return "".join(out)

    def text(self) -> str:
        """Text with whitespace collapsed; <br> kept as a newline."""
        lines = self.raw_text().split("\n")
        return "\n".join(x for x in (collapse_ws(l) for l in lines) if x)


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, parent=self.cur)
        self.cur.children.append(node)
        if tag not in _VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, {k: (v or "") for k, v in attrs}, parent=self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse_html(html: str) -> Node:
    b = _TreeBuilder()
    b.feed(html)
    b.close()
    return b.root
