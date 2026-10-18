import json
import unittest

from importers.ocr import Block, Reference, align, attested, consensus, fragment, join_tokens, pair_similar, plain, vote
from importers.ratification import number_of, numeral_reads_as, split_greetings
from tools.common import TEXTS_DIR
from tools.verify import check_uncertain

KNOWN = {"the", "this", "friends", "citizens", "your", "our", "asserted", "will", "community", "unity", "no"}


class VoteTests(unittest.TestCase):
    def test_majority_corrects_a_misreading(self):
        self.assertEqual(vote({"primary": "tliis", "a": "this", "b": "this"}, KNOWN), ("this", True))

    def test_tie_goes_to_a_known_word_like_the_primary(self):
        self.assertEqual(vote({"primary": "tliis", "a": "this"}, KNOWN), ("this", True))

    def test_tie_with_an_unlike_known_word_is_unsettled(self):
        self.assertEqual(vote({"primary": "(ISrumlaer", "a": "(Timber"}, KNOWN | {"timber"}), ("(ISrumlaer", False))

    def test_a_clean_known_word_is_never_replaced_by_another(self):
        self.assertEqual(vote({"primary": "friends", "a": "Citizens", "b": "Citizens"}, KNOWN), ("friends", False))

    def test_but_a_garbled_one_is(self):
        self.assertEqual(vote({"primary": ")our", "a": "your", "b": "your"}, KNOWN), ("your", True))

    def test_known_word_is_not_replaced_by_a_non_word(self):
        self.assertEqual(vote({"primary": "asserted", "a": "CATO. serted", "b": "CATO. serted"}, KNOWN),
                         ("asserted", True))

    def test_figures_that_differ_stay_unsettled(self):
        self.assertEqual(vote({"primary": "2181)", "a": "S181)", "b": "S181)"}, KNOWN), ("2181)", False))

    def test_a_word_only_the_primary_has_must_be_known(self):
        self.assertEqual(vote({"primary": "legislatlve"}, KNOWN), ("legislatlve", False))
        self.assertEqual(vote({"primary": "the"}, KNOWN), ("the", True))

    def test_an_elided_reading_is_not_spelled_out_by_vote(self):
        word, settled = vote({"primary": "renozvn'd", "a": "renown' d", "b": "renowned"}, KNOWN | {"renowned"})
        self.assertEqual((word, settled), ("renozvn'd", False))

    def test_capitals_do_not_replace_a_lower_case_word(self):
        self.assertEqual(vote({"primary": "Ciiuse", "a": "CASSIUS.", "b": "CASSIUS."}, KNOWN | {"cassius"}),
                         ("Ciiuse", False))

    def test_a_fragment_does_not_replace_a_longer_word(self):
        self.assertEqual(vote({"primary": "prometers", "a": "moters", "b": "moters"}, KNOWN | {"moters"}),
                         ("prometers", False))

    def test_two_stops_stand_when_two_scans_agree(self):
        self.assertEqual(vote({"primary": "art.,", "a": "art.,", "b": "art,"}, KNOWN | {"art"}), ("art.,", True))
        self.assertEqual(vote({"primary": "junto^", "a": "junto.,"}, KNOWN), ("junto^", False))

    def test_punctuation_follows_the_main_scan_when_a_scan_agrees(self):
        self.assertEqual(vote({"primary": "fanuary,", "a": "January", "b": "January,"}, KNOWN | {"january"}),
                         ("January,", True))

    def test_a_join_needs_a_known_clean_word(self):
        self.assertEqual(vote({"primary": "a vast", "a": "avast", "b": "a"}, KNOWN), ("a vast", True))
        self.assertEqual(vote({"primary": "us a", "a": "usa"}, KNOWN | {"us", "a", "usa"}), ("us a", True))
        self.assertEqual(vote({"primary": "of conspiracy.", "b": "of.conspiracy."}, KNOWN),
                         ("of conspiracy.", True))

    def test_only_stray_readings_stay_unsettled(self):
        self.assertEqual(vote({"primary": "naturally^", "a": "naturally,."}, KNOWN), ("naturally^", False))

    def test_stray_marks_lose_to_a_clean_reading_of_the_same_letters(self):
        self.assertEqual(vote({"primary": "the^", "a": "the"}, KNOWN), ("the", True))


class ConsensusTests(unittest.TestCase):
    def test_a_word_split_by_ocr_is_voted_on_once_and_kept_for_a_human(self):
        readings = [{"primary": "coinni", "a": "community", "b": "community"},
                    {"primary": "unity", "a": "", "b": ""}]
        words, unsettled = consensus(readings, KNOWN)
        self.assertEqual(words, ["coinni unity"])
        self.assertEqual(len(unsettled), 1)

    def test_a_word_split_by_a_space_is_rejoined(self):
        readings = [{"primary": "com", "a": "community", "b": "community"},
                    {"primary": "munity", "a": "", "b": ""}]
        self.assertEqual(consensus(readings, KNOWN), (["community"], []))

    def test_attested_needs_two_clean_identical_readings(self):
        self.assertEqual(attested([{"primary": "wil)", "a": "wil)", "b": "will"}]), set())
        self.assertEqual(attested([{"primary": "renown", "a": "renown"}]), {"renown"})
        self.assertEqual(attested([{"primary": "citi-", "a": "citi-"}]), set())


class AlignTests(unittest.TestCase):
    def test_pairs_only_alike_words(self):
        self.assertEqual(pair_similar(["coinni", "unity"], ["community"]), [([0, 1], [0])])
        self.assertEqual(pair_similar(["friends"], ["Northampton"]), [])

    def test_running_heads_are_not_half_a_word(self):
        self.assertEqual(pair_similar(["asserted"], ["CATO.", "serted"]), [([0], [1])])

    def test_fragments(self):
        self.assertTrue(fragment("citi-", "citizen"))
        self.assertTrue(fragment("serted", "asserted"))
        self.assertFalse(fragment("Citizens", "citizen"))

    def test_join_tokens(self):
        self.assertEqual(join_tokens(["there-", "fore"]), "therefore")
        self.assertEqual(join_tokens(["deliver", "d"]), "deliver d")

    def test_misplaced_reference_is_not_used(self):
        ref = Reference("a", "one two three four five six seven eight nine ten " * 3
                        + "alpha beta gamma delta epsilon zeta eta theta")
        out = align("alpha beta gamma delta epsilon zeta eta theta".split(), [ref], {})
        self.assertTrue(all(r.get("a") == r["primary"] for r in out))
        out = align("lorem ipsum dolor sit amet consectetur adipiscing elit".split(), [ref], {})
        self.assertTrue(all("a" not in r for r in out))

    def test_plain(self):
        self.assertTrue(plain('"The'))
        self.assertFalse(plain("wil)"))
        self.assertFalse(plain("b}-"))


class StructureTests(unittest.TestCase):
    def test_numerals_as_ocr_reads_them(self):
        self.assertEqual(number_of("XVII."), 17)
        self.assertEqual(number_of("l!"), 2)
        self.assertTrue(numeral_reads_as("VL", 6))
        self.assertTrue(numeral_reads_as("VHI", 8))
        self.assertTrue(numeral_reads_as("XL", 11))
        self.assertTrue(numeral_reads_as("lY", 4))
        self.assertFalse(numeral_reads_as("IX", 8))

    def test_signature_run_into_the_last_paragraph(self):
        from importers.ratification import structure
        series = {"signature": "Centinel."}
        body = "A long first paragraph of the essay, which goes on for a while."
        e = structure(series, "5", [Block(body, [1], []), Block("What would this be ? CenTinei,. Philadelphia, Nov. 30, 1787.", [2], [])])
        self.assertEqual(e.inline_tokens, 5)
        e = structure({"signature": "Caesar."}, "1", [Block(body, [1], []), Block("He will very probably be followed by Caesar. October 15, 1787.", [2], [])])
        self.assertEqual(e.inline_tokens, 0)

    def test_greeting_on_the_date_line(self):
        out = split_greetings([Block("October 9, 1787. Dear Sir,", [1], [])])
        self.assertEqual([b.text for b in out], ["October 9, 1787.", "Dear Sir,"])


class UncertainCheckTests(unittest.TestCase):
    def test_span_must_hold_a_reading(self):
        self.assertEqual(check_uncertain("x", "a tliis b", [{"start": 2, "end": 7, "readings": {"primary": "tliis"}}]), [])
        self.assertTrue(check_uncertain("x", "a this b", [{"start": 2, "end": 6, "readings": {"primary": "tliis"}}]))
        self.assertTrue(check_uncertain("x", "a b", [{"start": 2, "end": 9, "readings": {"primary": "b"}}]))


class ReviewSheetTests(unittest.TestCase):
    def test_every_uncertain_word_is_listed_with_a_page_image(self):
        from tools.uncertain import entries
        doc = json.loads((TEXTS_DIR / "cato.json").read_text(encoding="utf-8"))
        listed = entries(doc)
        expected = sum(len(s.get("uncertain", [])) for s in doc["segments"]) + sum(
            len(v) for d in doc["divisions"] for v in d.get("uncertain", {}).values())
        self.assertEqual(len(listed), expected)
        self.assertTrue(all(e["url"].startswith("https://archive.org/details/") for e in listed))


class RatificationImportTests(unittest.TestCase):
    def test_series_essay_counts(self):
        expect = {"cato": 7, "agrippa": 18, "centinel": 24, "landholder": 14, "federal-farmer": 5, "brutus": 4}
        for wid, n in expect.items():
            doc = json.loads((TEXTS_DIR / f"{wid}.json").read_text(encoding="utf-8"))
            self.assertEqual(len(doc["divisions"]), n, wid)

    def test_a_retired_paragraph_number_is_not_reused(self):
        doc = json.loads((TEXTS_DIR / "cassius.json").read_text(encoding="utf-8"))
        refs = {s["ref"]: s for s in doc["segments"]}
        self.assertNotIn("Cassius.4.5", refs)
        self.assertIn("Cassius.4.6", refs)
        self.assertIn("respect to their best interests", refs["Cassius.4.4"]["text"])
        self.assertEqual(doc["retired"][0]["merged_into"], "Cassius.4.4")

    def test_duplicate_printed_numbers_get_letters(self):
        doc = json.loads((TEXTS_DIR / "landholder.json").read_text(encoding="utf-8"))
        self.assertIn("Landholder.10b", [d["ref"] for d in doc["divisions"]])


if __name__ == "__main__":
    unittest.main()
