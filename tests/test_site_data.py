import unittest

from tools.corpus import load_corpus
from tools.site_data import build, runs_for


class RunsTests(unittest.TestCase):
    def test_emphasis_changed_and_breaks(self):
        seg = {"text": "Ab cd\nef\n\ngh", "emphasis": [[3, 5]]}
        changed = [{"start": 0, "end": 2}]
        paras = runs_for(seg, changed)
        self.assertEqual(paras, [
            [[{"t": "Ab", "chg": 0}, {"t": " "}, {"t": "cd", "em": True}], [{"t": "ef"}]],
            [[{"t": "gh"}]],
        ])

    def test_runs_rebuild_the_text_exactly(self):
        corpus = load_corpus()
        for ref in ("Constitution.1.2.3", "Federalist.6.fn1", "Amendment.23.1", "Constitution.Signers.Delaware"):
            seg = corpus.segments[ref]
            paras = runs_for(seg, [])
            rebuilt = "\n\n".join("\n".join("".join(r["t"] for r in line) for line in p) for p in paras)
            self.assertEqual(rebuilt, seg["text"], ref)


class SiteStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = load_corpus()
        cls.site, cls.pages, cls.refs = build(cls.corpus, [])

    def test_permanent_url_scheme(self):
        self.assertEqual(self.refs["Constitution.1.8.3"]["url"], "/constitution/#Constitution.1.8.3")
        self.assertEqual(self.refs["Amendment.14.1"]["url"], "/amendments/#Amendment.14.1")
        self.assertEqual(self.refs["Federalist.10"]["url"], "/federalist/10/")
        self.assertEqual(self.refs["Federalist.10.4"]["url"], "/federalist/10/#Federalist.10.4")
        self.assertEqual(self.refs["Federalist.6.fn1"]["url"], "/federalist/6/#Federalist.6.fn1")

    def test_every_segment_has_a_url(self):
        for ref in self.corpus.segments:
            self.assertIn(ref, self.refs)

    def test_every_passage_is_on_exactly_one_page(self):
        seen = {}
        for pid, page in self.pages.items():
            for b in page.get("blocks", []) + page.get("notes", []):
                if b["type"] == "passage":
                    self.assertNotIn(b["ref"], seen, f"{b['ref']} on {pid} and {seen.get(b['ref'])}")
                    seen[b["ref"]] = pid
        self.assertEqual(set(seen), set(self.corpus.segments))

    def test_no_heading_anchor_duplicates_a_passage(self):
        for page in self.pages.values():
            ids = [b.get("anchor") for b in page.get("blocks", []) if b["type"] == "heading" and b.get("anchor")]
            ids += [b["ref"] for b in page.get("blocks", []) + page.get("notes", []) if b["type"] == "passage"]
            self.assertEqual(len(ids), len(set(ids)), page["id"])

    def test_federalist_pager(self):
        self.assertIsNone(self.pages["federalist-1"]["prev"])
        self.assertEqual(self.pages["federalist-10"]["next"]["url"], "/federalist/11/")
        self.assertIsNone(self.pages["federalist-85"]["next"])


if __name__ == "__main__":
    unittest.main()
