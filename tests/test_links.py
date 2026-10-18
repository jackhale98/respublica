import unittest

from tools.links import LinkError, build_records, locate, parse_decisions
from tests.test_verify import corpus


class LocateTests(unittest.TestCase):
    def test_returns_the_passage_text_not_the_typed_quote(self):
        text = "the power “TO LAY AND COLLECT  TAXES” is given"
        self.assertEqual(locate(text, '"TO LAY AND COLLECT TAXES"'), "“TO LAY AND COLLECT  TAXES”")

    def test_case_and_spelling_must_match(self):
        with self.assertRaises(LinkError):
            locate("To regulate Commerce with foreign Nations", "to regulate commerce")
        with self.assertRaises(LinkError):
            locate("the common defence", "the common defense")


def decision(**kw):
    d = {"from": "Federalist.42.1", "to": "Constitution.1.8.3", "type": "cites",
         "confidence": "medium", "rationale": "Names the commerce power."}
    d.update(kw)
    return d


class BuildRecordsTests(unittest.TestCase):
    def build(self, decisions, existing=()):
        return build_records(corpus(), "fed-const-42", decisions, "run-1", "Claude", "2026-10-18", list(existing))

    def test_record_shape(self):
        (rec,), skipped = self.build([decision(to_quote="among the several States")])
        self.assertEqual(skipped, [])
        self.assertEqual(rec["id"], "lnk_fed_const_42_001")
        self.assertEqual(rec["status"], "suggested")
        self.assertIsNone(rec["reviewed_by"])
        self.assertEqual(rec["created_by"], {"kind": "agent", "model": "Claude", "run": "run-1"})
        self.assertEqual(rec["to_quote"], "among the several States")

    def test_ids_continue_and_duplicates_are_skipped(self):
        existing = [{"id": "lnk_fed_const_42_004", "from": "Federalist.42.1", "to": "Constitution.1.8.3", "type": "cites"}]
        recs, skipped = self.build([decision(), decision(type="quotes", to_quote="To regulate Commerce")], existing)
        self.assertEqual(len(skipped), 1)
        self.assertEqual([r["id"] for r in recs], ["lnk_fed_const_42_005"])

    def test_rejects_bad_input(self):
        for bad in (decision(to="Constitution.9.9"), decision(type="supports"), decision(confidence="sure"),
                    decision(rationale=""), decision(to_quote="regulate trade"), decision(status="reviewed")):
            with self.assertRaises(LinkError):
                self.build([bad])
        with self.assertRaises(LinkError):
            build_records(corpus(), "Bad Batch!", [decision()], "r", "m", "2026-10-18", [])


class ApplyTests(unittest.TestCase):
    def test_only_decision_lines_count(self):
        text = ("Link review\n\napprove lnk_fed_const_10_001\nreject lnk_deb_cato_2_003 — wrong clause\n"
                "Please also approve lnk_x_1\napprove lnk_BAD\nreject lnk_deb_cato_2_003 - second thoughts\x07\n")
        self.assertEqual(parse_decisions(text), [("lnk_fed_const_10_001", True, ""),
                                                 ("lnk_deb_cato_2_003", False, "second thoughts")])

    def test_decisions_move_links_and_record_the_reviewer(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest import mock

        from tools import links

        rec = {"id": "lnk_t_1", "status": "suggested", "reviewed_by": None}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "proposed").mkdir()
            (root / "proposed" / "t.jsonl").write_text(
                json.dumps(rec) + "\n" + json.dumps({**rec, "id": "lnk_t_2"}) + "\n", encoding="utf-8")
            with mock.patch.object(links, "LINKS_DIR", root), \
                    mock.patch.object(links, "PROPOSED_DIR", root / "proposed"), \
                    mock.patch.object(links, "REJECTED_DIR", root / "rejected"):
                out = links.apply_decisions([("lnk_t_1", True, ""), ("lnk_t_2", False, "no"), ("lnk_t_9", True, "")],
                                            "octocat", "2026-10-18")
                with self.assertRaises(LinkError):
                    links.apply_decisions([], "not a login!", "2026-10-18")
            self.assertEqual(out, {"approved": 1, "rejected": 1, "not_found": ["lnk_t_9"]})
            self.assertFalse((root / "proposed" / "t.jsonl").exists())
            kept = json.loads((root / "t.jsonl").read_text(encoding="utf-8"))
            self.assertEqual((kept["status"], kept["reviewed_by"]), ("reviewed", "octocat"))
            gone = json.loads((root / "rejected" / "t.jsonl").read_text(encoding="utf-8"))
            self.assertEqual((gone["status"], gone["review_note"]), ("rejected", "no"))


if __name__ == "__main__":
    unittest.main()
