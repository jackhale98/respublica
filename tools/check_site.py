"""Check the built site in site/dist (run after `astro build`).

    python -m tools.check_site

Enforces the security baseline and completeness:
  * every page has a Content Security Policy meta tag without unsafe-* or
    third-party sources;
  * no third-party scripts or stylesheets, no inline event handlers, no
    style attributes, and every absolute URL in a page is http(s);
  * every internal link points to a page that exists, and every #fragment
    to an id on that page;
  * every segment ref in texts/ and cases/ is rendered as an element id;
  * the build stays inside the free-tier budgets below.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

from tools.common import ROOT, is_safe_url, parse_html
from tools.corpus import load_corpus

DIST = ROOT / "site" / "dist"
# The path the site is served under ("" or e.g. "/respublica"); see site/site.config.json.
BASE = json.loads((ROOT / "site" / "site.config.json").read_text(encoding="utf-8")).get("base", "").rstrip("/")
URL_ATTRS = ("href", "src", "action", "formaction", "poster", "srcset", "data")
# <link rel> values that load a resource (others, like canonical, only name a URL).
RESOURCE_RELS = {"stylesheet", "preload", "modulepreload", "prefetch", "icon", "apple-touch-icon", "manifest"}
# The only CSP source beyond 'self' and hashes: Pagefind compiles WebAssembly.
ALLOWED_UNSAFE = {"'wasm-unsafe-eval'"}
# The only third-party sources: the errata page shows page images from the
# Internet Archive and the UNT Digital Library (images only; decision 48).
PAGE_IMAGES = {"/errata/": "img-src 'self' https://archive.org https://*.us.archive.org https://digital.library.unt.edu "
                          "https://tile.loc.gov"}

# Free-tier budgets (docs/decisions.md 15, 44). Cloudflare static assets:
# 20,000 files and 25 MiB per file on the free plan. Budgets sit well inside
# so growth is caught early.
BUDGET_TOTAL_BYTES = 250 * 2**20
BUDGET_FILES = 10_000
BUDGET_FILE_BYTES = 5 * 2**20
BUDGET_PAGE_HTML_BYTES = 400 * 2**10
# The about page lists every source, one line each; the owner allows it more
# (decision 72). Its own budget, so growth there is still caught.
BUDGET_PAGE_HTML_OVERRIDES = {"/about/": 450 * 2**10}
BUDGET_PAGE_JS_BYTES = 60 * 2**10     # scripts a page loads up front (search loads on demand)


def page_url(path: Path) -> str:
    """The URL a built file is served at, including the base path."""
    rel = path.relative_to(DIST).as_posix()
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    return f"{BASE}/{rel}"


def to_file(url_path: str) -> Path | None:
    """The built file behind a served path, or None if it is outside the base path."""
    if not url_path.startswith(BASE + "/"):
        return None
    return DIST / url_path[len(BASE) + 1:]


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
            allowed = PAGE_IMAGES.get(url[len(BASE):] if url.startswith(BASE) else url)
            if allowed:
                csp = ";".join(d for d in csp.split(";") if d.strip() != allowed)
            unsafe = set(re.findall(r"'[a-z-]*unsafe-[a-z-]*'", csp)) - ALLOWED_UNSAFE
            if unsafe or re.search(r"(https?:|\*|data:|blob:)", csp):
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
        file = to_file(target)
        if file is None:
            errors.append(f"{src}: internal link {href} is outside the base path {BASE or '/'}")
            continue
        if target.startswith(f"{BASE}/_astro/"):
            if not file.exists():
                errors.append(f"{src}: missing asset {target}")
            continue
        if not target.endswith("/") and not file.exists():
            target += "/"
        if target not in ids:
            errors.append(f"{src}: link to missing page {href}")
        elif frag and urllib.parse.unquote(frag) not in ids[target]:
            errors.append(f"{src}: link to missing anchor {href}")

    errors.extend(check_budgets(pages))

    all_ids = set().union(*ids.values()) if ids else set()
    corpus = load_corpus()
    for ref in corpus.segments:
        if ref not in all_ids:
            errors.append(f"segment {ref} is not rendered on any page")
    return errors


def check_budgets(pages: list[Path]) -> list[str]:
    errors = []
    files = [f for f in DIST.rglob("*") if f.is_file()]
    total = sum(f.stat().st_size for f in files)
    if total > BUDGET_TOTAL_BYTES:
        errors.append(f"budget: site is {total / 2**20:.1f} MB (budget {BUDGET_TOTAL_BYTES // 2**20} MB)")
    if len(files) > BUDGET_FILES:
        errors.append(f"budget: site has {len(files)} files (budget {BUDGET_FILES})")
    for f in files:
        if f.stat().st_size > BUDGET_FILE_BYTES:
            errors.append(f"budget: {f.relative_to(DIST)} is {f.stat().st_size / 2**20:.1f} MB (budget {BUDGET_FILE_BYTES // 2**20} MB)")
    for path in pages:
        size = path.stat().st_size
        budget = BUDGET_PAGE_HTML_OVERRIDES.get(page_url(path), BUDGET_PAGE_HTML_BYTES)
        if size > budget:
            errors.append(f"budget: {page_url(path)} HTML is {size // 1024} KB (budget {budget // 1024} KB)")
        root = parse_html(path.read_text(encoding="utf-8"))
        js = 0
        for n in root.find_all("script"):
            src = n.attrs.get("src")
            f = to_file(src) if src else None
            if f is not None:
                if f.exists():
                    js += f.stat().st_size + _imports_size(f)
        if js > BUDGET_PAGE_JS_BYTES:
            errors.append(f"budget: {page_url(path)} loads {js // 1024} KB of JavaScript (budget {BUDGET_PAGE_JS_BYTES // 1024} KB)")
    return errors


def _imports_size(path: Path, seen: set | None = None) -> int:
    """Size of modules a script statically imports (dynamic imports load on demand)."""
    seen = seen if seen is not None else set()
    total = 0
    text = path.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"""(?:^|[;\n}])\s*import\s*(?:[^'"()]*?from\s*)?["']([^"']+)["']""", text):
        target = (path.parent / m.group(1)).resolve() if m.group(1).startswith(".") else to_file(m.group(1))
        if target is not None and target.exists() and target not in seen:
            seen.add(target)
            total += target.stat().st_size + _imports_size(target, seen)
    return total


def _check_url(page: str, node, attr: str, value: str, links: list) -> list[str]:
    errs = []
    candidates = [v.strip().split()[0] for v in value.split(",")] if attr == "srcset" else [value]
    for v in candidates:
        scheme = urllib.parse.urlsplit(v).scheme
        if scheme or v.startswith("//"):
            if not is_safe_url(v):
                errs.append(f"{page}: unsafe URL in <{node.tag} {attr}>: {v!r}")
            elif node.tag in ("script", "img", "iframe", "object", "embed", "source") or (
                    node.tag == "link" and set(node.attrs.get("rel", "").lower().split()) & RESOURCE_RELS):
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
