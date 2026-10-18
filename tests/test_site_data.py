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
        cls.site, cls.pages, cls.refs, cls.graphs = build(cls.corpus, [])

    def test_permanent_url_scheme(self):
        self.assertEqual(self.refs["Constitution.1.8.3"]["url"], "/constitution/#Constitution.1.8.3")
        self.assertEqual(self.refs["Amendment.14.1"]["url"], "/amendments/#Amendment.14.1")
        self.assertEqual(self.refs["Federalist.10"]["url"], "/federalist/10/")
        self.assertEqual(self.refs["Federalist.10.4"]["url"], "/federalist/10/#Federalist.10.4")
        self.assertEqual(self.refs["Federalist.6.fn1"]["url"], "/federalist/6/#Federalist.6.fn1")
        self.assertEqual(self.refs["Caution"]["url"], "/caution/")  # a single piece is its own page
        # A retired ref keeps a URL, an anchor inside the passage it was merged into.
        self.assertEqual(self.refs["Cassius.4.5"]["url"], "/cassius/4/#Cassius.4.5")

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


class GraphTests(unittest.TestCase):
    def test_short_labels(self):
        from tools.site_data import short_label
        self.assertEqual(short_label("Article I, Section 8, Clause 18"), "Art. I §8 cl. 18")
        self.assertEqual(short_label("Declaration of Independence, ¶ 2"), "Decl. ¶2")
        self.assertEqual(short_label("Article VI, Clause 2"), "Art. VI cl. 2")
        self.assertEqual(short_label("Federalist No. 44, ¶ 4"), "Fed. 44 ¶4")
        self.assertEqual(short_label("Federalist No. 59, note 1"), "Fed. 59 n.1")
        self.assertEqual(short_label("Amendment XIV, Section 1"), "Amend. XIV §1")

    def test_two_hop_neighborhood_and_rejected_links(self):
        corpus = load_corpus()
        def link(i, frm, to, status="suggested"):
            return {"id": f"lnk_t_{i}", "from": frm, "to": to, "type": "cites", "status": status,
                    "confidence": "high", "rationale": "r", "created_by": {"kind": "human"}}
        links = [link(1, "Federalist.33.1", "Constitution.1.8.18"),
                 link(2, "Federalist.44.4", "Constitution.1.8.18"),
                 link(3, "Federalist.44.4", "Constitution.6.2"),
                 link(4, "Federalist.10.1", "Constitution.1.8.3"),
                 link(5, "Federalist.33.7", "Constitution.6.2", status="rejected")]
        _, _, _, graphs = build(corpus, links)
        g = graphs["federalist-33"]
        # 33.1 -> 1.8.18 (hop 1) -> 44.4 (hop 2); 44.4 -> 6.2 would be a third hop, so it is left out.
        self.assertEqual({e["id"] for e in g["edges"]}, {"lnk_t_1", "lnk_t_2"})
        self.assertIn("Federalist.44.4", g["nodes"])
        self.assertEqual(g["nodes"]["Constitution.1.8.18"]["work"], "constitution")
        self.assertEqual(graphs["federalist-10"]["edges"][0]["id"], "lnk_t_4")
        self.assertEqual(graphs["federalist-1"], {"edges": [], "nodes": {}})
