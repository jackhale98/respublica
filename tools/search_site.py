"""Build the Pagefind search index for site/dist (run after `astro build`).

    python -m tools.search_site

Pagefind indexes a copy of the pages in which the long s (ſ) is an s, so
"Congress" finds the pamphlets' "Congreſs" (decision 74). The pages
themselves keep the long s as printed; only the index, and so the search
results' excerpts, read "s". Pages without a long s are linked into the
copy, not rewritten.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.common import ROOT

SITE = ROOT / "site"
DIST = SITE / "dist"


def fold(text: str) -> str:
    return text.replace("ſ", "s")


def mirror(dest: Path) -> int:
    """The site's HTML pages under dest, with the long s folded; returns how
    many pages were folded."""
    folded = 0
    for page in DIST.rglob("*.html"):
        if page.is_relative_to(DIST / "pagefind"):
            continue
        out = dest / page.relative_to(DIST)
        out.parent.mkdir(parents=True, exist_ok=True)
        text = page.read_text(encoding="utf-8")
        if "ſ" in text:
            out.write_text(fold(text), encoding="utf-8")
            folded += 1
        else:
            os.link(page, out)
    return folded


def main() -> int:
    if not DIST.exists():
        print("site/dist is missing: run astro build first", file=sys.stderr)
        return 1
    shutil.rmtree(DIST / "pagefind", ignore_errors=True)
    with tempfile.TemporaryDirectory(dir=SITE) as tmp:
        folded = mirror(Path(tmp))
        print(f"search: {folded} pages with a long s folded for the index")
        return subprocess.run(["npx", "pagefind", "--site", tmp, "--output-path", str(DIST / "pagefind")],
                              cwd=SITE).returncode


if __name__ == "__main__":
    sys.exit(main())
