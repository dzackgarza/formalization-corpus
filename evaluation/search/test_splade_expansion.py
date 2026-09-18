import unittest

from evaluate_splade_expansion import expansion_from_embedding, stable_unique, usable_fts5_token


class FakeTokenizer:
    TOKENS = {
        1: "duality",
        2: "##ity",
        3: "[CLS]",
        4: "serre",
        5: "x-y",
        6: "a",
    }

    def id_to_token(self, token_id):
        return self.TOKENS[token_id]


class SpladeExpansionTests(unittest.TestCase):
    def test_usable_fts5_token_rejects_unfaithful_wordpieces(self):
        self.assertTrue(usable_fts5_token("duality"))
        self.assertTrue(usable_fts5_token("q2"))
        self.assertFalse(usable_fts5_token("##ity"))
        self.assertFalse(usable_fts5_token("[CLS]"))
        self.assertFalse(usable_fts5_token("x-y"))
        self.assertFalse(usable_fts5_token("a"))

    def test_expansion_is_weight_ordered_and_reports_drops(self):
        expansions, dropped = expansion_from_embedding(
            indices=[1, 2, 3, 4, 5, 6],
            values=[0.5, 2.0, 3.0, 1.5, 1.0, 0.2],
            tokenizer=FakeTokenizer(),
        )
        self.assertEqual([item["token"] for item in expansions], ["serre", "duality"])
        self.assertEqual([item["token_id"] for item in expansions], [4, 1])
        self.assertEqual(dropped, 4)

    def test_stable_unique_preserves_first_occurrence(self):
        self.assertEqual(stable_unique(["a", "b", "a", "c", "b"]), ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
