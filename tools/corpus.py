"""Load texts/ and cases/ into one ref index, shared by verify and the site build."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tools.common import CASES_DIR, TEXTS_DIR, read_json


@dataclass
class Corpus:
    works: dict[str, dict] = field(default_factory=dict)       # work id -> document
    files: dict[str, Path] = field(default_factory=dict)       # work id -> file
    segments: dict[str, dict] = field(default_factory=dict)    # ref -> segment
    segment_work: dict[str, str] = field(default_factory=dict)  # ref -> work id
    divisions: dict[str, dict] = field(default_factory=dict)   # ref -> division
    duplicate_refs: list[str] = field(default_factory=list)
    retired: dict[str, str] = field(default_factory=dict)       # retired ref -> the ref it was merged into
    prefixes: set[str] = field(default_factory=set)            # every dot-boundary prefix of a segment ref

    def exists(self, ref: str) -> bool:
        """A ref exists if it is a segment, a division, a work prefix,
        or a dot-boundary prefix of some segment (e.g. Constitution.1.8)."""
        return ref in self.segments or ref in self.divisions or ref in self.prefixes

    def passages(self, ref: str) -> list[dict]:
        """Segments a ref covers: itself, or every segment under it."""
        if ref in self.segments:
            return [self.segments[ref]]
        prefix = ref + "."
        return [s for r, s in self.segments.items() if r.startswith(prefix)]


def load_corpus(texts_dir: Path = TEXTS_DIR, cases_dir: Path = CASES_DIR) -> Corpus:
    c = Corpus()
    files = sorted(texts_dir.glob("*.json")) + sorted(cases_dir.glob("*.json"))
    for path in files:
        doc = read_json(path)
        wid = doc.get("id", path.stem)
        c.works[wid] = doc
        c.files[wid] = path
        if doc.get("ref_prefix"):
            c.prefixes.add(doc["ref_prefix"])  # a work's own ref, even with no passages (a case without a syllabus)
        for d in doc.get("divisions", []):
            c.divisions[d["ref"]] = d
        for r in doc.get("retired", []):
            c.retired[r["ref"]] = r["merged_into"]
        for s in doc.get("segments", []):
            ref = s.get("ref")
            if ref in c.segments:
                c.duplicate_refs.append(ref)
            c.segments[ref] = s
            c.segment_work[ref] = wid
            parts = ref.split(".")
            for i in range(1, len(parts)):
                c.prefixes.add(".".join(parts[:i]))
    return c
