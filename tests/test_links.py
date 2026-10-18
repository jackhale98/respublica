import unittest

from tools.links import LinkError, build_records, locate
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


if __name__ == "__main__":
    unittest.main()
