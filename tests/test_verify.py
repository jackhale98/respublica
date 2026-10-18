import unittest

from tools.corpus import Corpus
from tools.site_data import build_link_index
from tools.verify import check_link


def corpus() -> Corpus:
    c = Corpus()
    segs = {
        "Constitution.1.8.3": "To regulate Commerce with foreign Nations, and among the several States",
        "Federalist.42.1": "The second class of powers “lodged in the general government”",
        "Case.1.1": "Opinion text.",
        "Case.2.1": "Later opinion text.",
    }
    for ref, text in segs.items():
        c.segments[ref] = {"ref": ref, "text": text, "label": ref}
        parts = ref.split(".")
        for i in range(1, len(parts)):
            c.prefixes.add(".".join(parts[:i]))
    return c


def link(**kw) -> dict:
    base = {
        "id": "lnk_test_1",
        "from": "Federalist.42.1",
        "to": "Constitution.1.8.3",
        "type": "cites",
        "rationale": "Paragraph discusses the commerce power.",
        "created_by": {"kind": "agent", "model": "m", "run": "r"},
        "created_at": "2026-10-18",
        "confidence": "medium",
        "status": "suggested",
        "reviewed_by": None,
    }
    base.update(kw)
    return base


class LinkChecks(unittest.TestCase):
    def test_valid_link(self):
        self.assertEqual(check_link(link(to_quote="To regulate Commerce"), corpus(), proposed=True), [])

    def test_quote_normalizes_only_whitespace_and_quote_marks(self):
        ok = link(from_quote='"lodged  in the general government"')
        self.assertEqual(check_link(ok, corpus(), proposed=True), [])
        bad = link(to_quote="To regulate commerce")  # case differs
        self.assertTrue(check_link(bad, corpus(), proposed=True))

    def test_parent_ref_quote(self):
        self.assertEqual(check_link(link(to="Constitution.1.8", to_quote="among the several States"), corpus(), True), [])

    def test_missing_ref(self):
        self.assertTrue(any("does not exist" in e for e in check_link(link(to="Constitution.9.9.9"), corpus(), True)))

    def test_proposed_must_be_suggested(self):
        errs = check_link(link(status="reviewed", reviewed_by="someone"), corpus(), proposed=True)
        self.assertTrue(any("must have status 'suggested'" in e for e in errs))

    def test_needs_rationale(self):
        self.assertTrue(check_link(link(rationale=""), corpus(), True))
        imported = link(rationale=None, source="Constitution Annotated", created_by={"kind": "import"})
        self.assertEqual(check_link(imported, corpus(), False), [])

    def test_agent_needs_model_and_run(self):
        self.assertTrue(check_link(link(created_by={"kind": "agent"}), corpus(), True))

    def test_unknown_type_and_keys(self):
        self.assertTrue(check_link(link(type="supports"), corpus(), True))
        self.assertTrue(check_link(link(holding="x"), corpus(), True))

    def test_bad_url(self):
        self.assertTrue(check_link(link(source="javascript:alert(1)"), corpus(), True))

    def test_overrules_needs_source_and_cases(self):
        rec = link(**{"from": "Case.2", "to": "Case.1", "type": "overrules"})
        self.assertTrue(any("cite a source" in e for e in check_link(rec, corpus(), True)))
        rec["source"] = "Citation for the overruling"
        self.assertEqual(check_link(rec, corpus(), True), [])


class OverruledFlag(unittest.TestCase):
    def test_links_to_overruled_case_are_flagged(self):
        links = [
            link(id="lnk_a", **{"from": "Case.2", "to": "Case.1", "type": "overrules", "source": "s"}),
            link(id="lnk_b", **{"from": "Case.1.1", "to": "Constitution.1.8.3", "type": "interprets"}),
        ]
        idx = build_link_index(links, corpus())
        entry = next(e for e in idx["by_ref"]["Constitution.1.8.3"] if e["id"] == "lnk_b")
        self.assertTrue(entry["other_overruled"])

    def test_rejected_links_are_dropped(self):
        idx = build_link_index([link(status="rejected")], corpus())
        self.assertEqual(idx["by_ref"], {})


if __name__ == "__main__":
    unittest.main()
