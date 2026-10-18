"""Check the built site in site/dist (run after `astro build`).

    python -m tools.check_site

Enforces the security baseline and completeness:
  * every page has a Content Security Policy meta tag without unsafe-* or
    third-party sources;
  * no third-party scripts or stylesheets, no inline event handlers, no
    style attributes, and every absolute URL in a page is http(s);
  * every internal link points to a page that exists, and every #fragment
    to an id on that page;
  * every segment ref in texts/ and cases/ is rendered as an element id.
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

from tools.common import ROOT, is_safe_url, parse_html
from tools.corpus import load_corpus

DIST = ROOT / "site" / "dist"
URL_ATTRS = ("href", "src", "action", "formaction", "poster", "srcset", "data")


def page_url(path: Path) -> str:
    rel = path.relative_to(DIST).as_posix()
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    return "/" + rel


def check() -> list[str]:
    errors: list[str] = []
    if not DIST.exists():
        return ["site/dist does not exist; run the site build first"]
    pages = sorted(DIST.rglob("*.html"))
    ids: dict[str, set[str]] = {}
    links: list[tuple[str, str]] = []
    for path in pages:
        url = page_url(path)
        root = parse_html(path.read_text(encoding="utf-8"))
        page_ids = {n.attrs["id"] for n in root.iter() if "id" in n.attrs}
        ids[url] = page_ids

        metas = [n for n in root.find_all("meta") if n.attrs.get("http-equiv", "").lower() == "content-security-policy"]
        if len(metas) != 1:
            errors.append(f"{url}: expected one CSP meta tag, found {len(metas)}")
        else:
            csp = metas[0].attrs.get("content", "")
            if "unsafe-" in csp or re.search(r"(https?:|\*|data:|blob:)", csp):
                errors.append(f"{url}: CSP allows unsafe or third-party sources: {csp}")
            for directive in ("default-src 'self'", "object-src 'none'", "base-uri 'self'"):
                if directive not in csp:
                    errors.append(f"{url}: CSP is missing {directive}")

        for n in root.iter():
            for attr, value in n.attrs.items():
                if attr.startswith("on"):
                    errors.append(f"{url}: inline event handler {attr} on <{n.tag}>")
                if attr == "style":
                    errors.append(f"{url}: style attribute on <{n.tag}>")
                if attr in URL_ATTRS and value:
                    errors.extend(_check_url(url, n, attr, value, links))
            if n.tag == "script" and "src" not in n.attrs and n.raw_text().strip():
                errors.append(f"{url}: inline <script>")

    for src, href in links:
        target, _, frag = href.partition("#")
        target = urllib.parse.urljoin(src, target) if target else src
        target = urllib.parse.urlsplit(target).path
        if target.startswith("/_astro/"):
            if not (DIST / target.lstrip("/")).exists():
                errors.append(f"{src}: missing asset {target}")
            continue
        if not target.endswith("/") and not (DIST / target.lstrip("/")).exists():
            target += "/"
        if target not in ids:
            errors.append(f"{src}: link to missing page {href}")
        elif frag and urllib.parse.unquote(frag) not in ids[target]:
            errors.append(f"{src}: link to missing anchor {href}")

    all_ids = set().union(*ids.values()) if ids else set()
    corpus = load_corpus()
    for ref in corpus.segments:
        if ref not in all_ids:
            errors.append(f"segment {ref} is not rendered on any page")
    return errors


def _check_url(page: str, node, attr: str, value: str, links: list) -> list[str]:
    errs = []
    candidates = [v.strip().split()[0] for v in value.split(",")] if attr == "srcset" else [value]
    for v in candidates:
        scheme = urllib.parse.urlsplit(v).scheme
        if scheme or v.startswith("//"):
            if not is_safe_url(v):
                errs.append(f"{page}: unsafe URL in <{node.tag} {attr}>: {v!r}")
            elif node.tag in ("script", "link", "img", "iframe", "object", "embed", "source"):
                errs.append(f"{page}: third-party resource in <{node.tag} {attr}>: {v}")
        elif node.tag == "a" and attr == "href":
            links.append((page, v))
    return errs


def main() -> int:
    errors = check()
    for e in errors[:200]:
        print(f"  - {e}")
    if len(errors) > 200:
        print(f"  ... and {len(errors) - 200} more")
    print(f"[site] {'ok' if not errors else f'{len(errors)} error(s)'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
