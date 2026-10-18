"""Print passages with their refs: python -m tools.show Federalist.10 [Constitution.1.8 ...]

A ref prints itself or every passage under it. Use it to read a text before
linking; never retype what it prints into a link (tools.links copies quotes).
"""

import sys

from tools.corpus import load_corpus


def main(refs: list[str]) -> int:
    if not refs:
        print(__doc__)
        return 2
    corpus = load_corpus()
    for ref in refs:
        if ref in corpus.divisions:
            d = corpus.divisions[ref]
            print(f"# {d.get('label', ref)}" + (f": {d['title']}" if d.get("title") else ""))
        passages = corpus.passages(ref)
        if not passages:
            print(f"(no passages for {ref})")
        for p in passages:
            print(f"\n[{p['ref']}]\n{p['text']}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
