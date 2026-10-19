"""The Anti-Federalist Library (antifederalists.org) as a tie-breaker
between scans (decision 55).

The Library is a CC0 website whose texts are Markdown files in a public
GitHub repository, pinned here to one commit. It names no source, and its
editorial marks (`[sic]`, `[,]`, conjectures with "?") show it was copied
from a modern edition, so it is never a source of text. It is used only
where our scans disagree, or where no scan corroborates a word:

  * where the scans' readings of a word disagree and the vote cannot settle
    it, a reading whose letters the Library shares is chosen (the scan's
    own spelling of it), and the word is settled;
  * where no reading agrees with the Library, the text is not changed: the
    word stays uncertain, and the Library's reading is recorded with it as
    a `suggestion` for a person to check against the page image
    (`/errata/`);
  * in works whose scans are of the printing the Library follows (Brutus
    V-XVI, Patrick Henry's speeches), a settled word the Library reads
    differently is also marked uncertain, with the suggestion
    (`strict`).

The Library never votes, never adds a word, and its words never count as
known words. `importers/ocr.py` (`consensus`) applies these rules; this
module fetches the files, reads them as plain text and lines them up with
a run of a scan's words.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from importers.ocr import Reference, align
from tools.common import load_manifest, read_raw_text

REPO = "seven-obelisks/antifederalists"
COMMIT = "6424aff9c3eaba736da37863922bec85a03f8700"
RAW_URL = "https://raw.githubusercontent.com/{repo}/{commit}/content/{path}"
LICENSE = ("CC0 1.0 (the Anti-Federalist Library's site footer: \"The Anti-Federalist Library is marked CC0 1.0\"; "
           "the repository has no licence file and names no source for its texts). Used only as a tie-breaker "
           "between scans, never as text (docs/decisions.md 55).")

# The Library's pages for our works, by series and essay (or speech) id.
# Centinel: the pages titled "Centinel XII" (centinel13) and "Centinel XV"
# (centinel16) carry XIII and XVI by their text. Not used: Cato (pages
# duplicated or cut short), Centinel II-IV (excerpts), Brutus XI (no scan).
PAGES: dict[str, dict[str, str]] = {
    "Brutus": {str(n): f"papers/brutus/brutus{n}.md" for n in range(1, 17) if n != 11},
    "Agrippa": {str(n): f"papers/agrippa/agrippa{n}.md" for n in range(1, 12)},
    "FederalFarmer": {str(n): f"papers/farmer/farmer{n}.md" for n in range(1, 6)},
    "Centinel": {str(n): f"papers/centinel/centinel{n}.md" for n in [1, *range(5, 19)]},
    "Henry": {f"henry{n}": f"speeches/henry/henry{n}.md" for n in range(1, 25)},
}


def source_id(path: str) -> str:
    """The manifest id of a Library file: "afl-brutus5"."""
    return "afl-" + path.rsplit("/", 1)[-1].removesuffix(".md")


def page_for(series: str, essay: str) -> str | None:
    """The manifest id of the Library's page for an essay, if there is one."""
    path = PAGES.get(series, {}).get(essay)
    return source_id(path) if path else None


def plain_text(markdown: str) -> str:
    """The words of a Library page: the front matter, the date and
    salutation headings (`#####`, `######`) and Markdown marks are dropped,
    and so are the editor's bracketed insertions (`[sic]`, `[,]`, `[that]`)
    and page numbers (`{141}`), which the printed page does not have. Soft
    hyphens and diaereses are removed."""
    parts = markdown.split("---", 2)
    body = parts[2] if markdown.startswith("---") and len(parts) == 3 else markdown
    lines = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^>\s*", "", line)
        lines.append(line)
    text = "\n".join(lines)
    # The editor's insertions and page numbers ("[sic]", "{141}").
    text = re.sub(r"\[[^\]\n]*\]|\{[^}\n]*\}", " ", text)
    text = text.replace("*", "").replace("­", "").replace("‐", "-")
    # A diaeresis the edition adds ("reëlected") is not in the print.
    text = "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
    return re.sub(r"[ \t]+", " ", text)


@lru_cache(maxsize=None)
def reference(sid: str) -> Reference:
    return Reference("library", plain_text(read_raw_text(sid)))


def readings(tokens: list[str], sid: str | None) -> list[str | None]:
    """The Library's reading of each of a run of a scan's words (None where
    it has none: it does not print the word, or the two could not be lined
    up there; "" where it reads this word together with the one before)."""
    if not sid or not tokens:
        return [None] * len(tokens)
    aligned = align(tokens, [reference(sid)], {})
    return [r.get("library") for r in aligned]


def source_ids(series: str, essays: list[str]) -> list[str]:
    return sorted({sid for e in essays if (sid := page_for(series, e))})


# ------------------------------------------------------------ fetching


def cmd_fetch() -> None:
    """Record the Library's Markdown files, at the pinned commit, as raw sources."""
    from tools.fetch import add_source
    have = {e["id"] for e in load_manifest()}
    for series, pages in PAGES.items():
        for essay, path in pages.items():
            sid = source_id(path)
            if sid in have:
                continue
            add_source(sid, RAW_URL.format(repo=REPO, commit=COMMIT, path=path), LICENSE,
                       f"The Anti-Federalist Library (github.com/{REPO}, commit {COMMIT}), content/{path}: "
                       f"its text of {series} {essay}, as Markdown.", ext=".md")
            print(sid, flush=True)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["fetch"]:
        cmd_fetch()
