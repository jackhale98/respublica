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

    def test_contents_reach_every_clause_and_paragraph(self):
        decl = {t["ref"]: t for t in self.pages["declaration"]["toc"]}
        self.assertEqual(decl["Declaration.2"]["kind"], "passage")
        self.assertTrue(decl["Declaration.2"]["snippet"].startswith("We hold these truths"))
        self.assertEqual(len(decl["Declaration.Signers"]["passages"]), 15)
        const = {t["ref"]: t for t in self.pages["constitution"]["toc"]}
        self.assertEqual([p["n"] for p in const["Constitution.1.8"]["passages"]][-1], "18")
        self.assertEqual(const["Constitution.Preamble"]["kind"], "passage")
        self.assertEqual(self.pages["federalist-10"]["toc_passages"][0]["ref"], "Federalist.10.1")

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



class AmendmentBacklinkTests(unittest.TestCase):
    def test_amendments_link_back_to_the_text_they_change(self):
        corpus = load_corpus()
        site, pages, refs, graphs = build(corpus, [])
        heads = {b["ref"]: b for b in pages["amendments"]["blocks"] if b["type"] == "heading"}
        self.assertEqual([c["ref"] for c in heads["Amendment.17"]["changes"]], ["Constitution.1.3.1", "Constitution.1.3.2"])
        self.assertEqual(heads["Amendment.11"]["changes"][0]["url"], "/constitution/#Constitution.3.2.1")
        self.assertNotIn("changes", heads["Amendment.1"])


class ReviewTests(unittest.TestCase):
    def test_batches_by_confidence(self):
        from tools.corpus import load_corpus
        from tools.site_data import build_review
        corpus = load_corpus()
        mk = lambda n, conf: {"id": f"lnk_t_{n}", "from": "Federalist.10.1", "to": "Constitution.1.8.3", "type": "cites",
                              "confidence": conf, "status": "suggested", "rationale": "r"}
        proposed = [("fed-const-10", mk(1, "low")), ("fed-const-10", mk(2, "high")), ("fed-const-10", mk(3, "medium")),
                    ("fed-const-10", mk(4, "high"))]
        index, batches = build_review(corpus, proposed, {})
        self.assertEqual(index["by_confidence"], {"high": 2, "medium": 1, "low": 1})
        b = index["groups"][0]["batches"][0]
        self.assertEqual(b["by_confidence"], {"high": ["lnk_t_2", "lnk_t_4"], "medium": ["lnk_t_3"], "low": ["lnk_t_1"]})
        self.assertEqual([l["id"] for l in batches["fed-const-10"]["links"]], ["lnk_t_2", "lnk_t_4", "lnk_t_3", "lnk_t_1"])


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
        self.assertEqual(short_label("Brown v. Board of Education (1954)"), "Brown (1954)")
        self.assertEqual(short_label("Brown v. Board of Education, syllabus ¶ 2"), "Brown syl. ¶2")

    def test_case_pages(self):
        from tools.corpus import Corpus
        from tools.site_data import SiteBuilder, label_for
        c = Corpus()
        doc = {"id": "105221", "title": "Brown v. Board of Education", "ref_prefix": "Case.105221", "date": "1954-05-17",
               "us_cite": "347 U.S. 483", "pdf_url": "https://example.org/b.pdf", "chosen_because": ["cited on 11 pages"],
               "edition": {"name": "e", "notes": "n"}, "source_ids": [],
               "segments": [{"kind": "syllabus", "label": "Brown v. Board of Education, syllabus ¶ 1", "page": 484,
                             "ref": "Case.105221.syllabus.1", "text": "Segregation."}]}
        c.works["105221"], c.segments["Case.105221.syllabus.1"] = doc, doc["segments"][0]
        c.prefixes |= {"Case", "Case.105221"}
        self.assertEqual(label_for(c, "Case.105221"), "Brown v. Board of Education (1954)")
        link = {"id": "lnk_x", "from": "Case.2", "to": "Case.105221", "type": "overrules", "status": "suggested",
                "confidence": "high", "created_by": {"kind": "import"}, "source": "Table, p. 1."}
        site, pages = SiteBuilder(c, [link]).build()
        page = pages["case-105221"]
        self.assertEqual(page["url"], "/cases/105221/")
        self.assertTrue(page["case"]["overruled"])
        self.assertEqual(len(page["overruled_by"]), 1)
        self.assertEqual(page["blocks"][0]["printed"], {"page": 484, "url": "https://example.org/b.pdf#page=2"})
        self.assertEqual(site["stats"]["cases"], 1)
        self.assertEqual(pages["cases"]["cases"][0]["id"], "105221")

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


class SheetTests(unittest.TestCase):
    def test_a_long_part_is_split_at_paragraphs_into_near_equal_sheets(self):
        from tools.site_data import SHEET_TEXT_BYTES, sheets
        segs = [{"ref": f"X.1.{n}", "text": "w" * (SHEET_TEXT_BYTES // 10)} for n in range(1, 26)]
        out = sheets(segs)
        self.assertEqual(len(out), 3)
        self.assertEqual([x["ref"] for sheet in out for x in sheet], [x["ref"] for x in segs])
        self.assertTrue(all(7 <= len(sheet) <= 9 for sheet in out))

    def test_a_short_part_or_one_with_notes_stays_whole(self):
        from tools.site_data import SHEET_TEXT_BYTES, sheets
        self.assertEqual(len(sheets([{"ref": "X.1.1", "text": "short"}])), 1)
        long = [{"ref": f"X.1.{n}", "text": "w" * SHEET_TEXT_BYTES} for n in range(1, 4)]
        self.assertEqual(len(sheets(long + [{"kind": "footnote", "ref": "X.1.fn1", "text": "n"}])), 1)


class PreviewTests(unittest.TestCase):
    def test_a_long_passage_is_clipped_at_a_word(self):
        from tools.site_data import PREVIEW_CHARS, clip
        self.assertEqual(clip("Short."), {"text": "Short."})
        long = clip("word " * PREVIEW_CHARS)
        self.assertTrue(long["clipped"])
        self.assertTrue(long["text"].endswith("word …"))
        self.assertLessEqual(len(long["text"]), PREVIEW_CHARS + 2)
