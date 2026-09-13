#!/usr/bin/env python3
from __future__ import annotations

import copy
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate  # noqa: E402
from evaluate_multiquery import rrf_fuse  # noqa: E402


class SearchEvaluationTests(unittest.TestCase):
    def test_frontend_v1_compiler_preserves_current_strict_behavior(self) -> None:
        compiled = evaluate.compile_query(
            "Is Serre duality formalized?", "frontend_lexical_v1"
        )
        self.assertIn('content:"Is"', compiled)
        self.assertIn('content:"Serre"', compiled)
        self.assertIn('content:"duality"', compiled)
        self.assertIn('content:"formalized\\\\?"', compiled)
        self.assertIn("file:", compiled)
        self.assertTrue(compiled.endswith("case:no"))

    def test_normalized_query_removes_intent_words_and_detects_proof_assistant(self) -> None:
        terms, proof_filter = evaluate.normalized_query_terms(
            "does Lean have the Jordan canonical form theorem?"
        )
        self.assertEqual(terms, ["Jordan", "canonical", "form"])
        self.assertEqual(proof_filter, r"\.lean$")

    def test_score_case_tracks_first_owner_and_graded_metrics(self) -> None:
        case = {
            "id": "toy",
            "query": "toy",
            "tags": [],
            "judgments": [
                {"repository": "r", "file": "owner", "relevance": 3},
                {"repository": "r", "file": "alternate", "relevance": 2},
            ],
        }
        results = [
            {"Repository": "x", "FileName": "noise", "Score": 9},
            {"Repository": "r", "FileName": "alternate", "Score": 8},
            {"Repository": "r", "FileName": "owner", "Score": 7},
        ]
        scored = evaluate.score_case(
            case, results, "toy", {"elapsed_ms": 1.0, "payload_bytes": 1}
        )
        self.assertEqual(scored["first_relevant_rank"], 2)
        self.assertEqual(scored["first_owner_rank"], 3)
        self.assertAlmostEqual(scored["reciprocal_rank"], 0.5)
        self.assertEqual(scored["per_k"]["1"]["hit"], 0)
        self.assertEqual(scored["per_k"]["5"]["hit"], 1)
        self.assertEqual(scored["per_k"]["5"]["owner_hit"], 1)
        self.assertAlmostEqual(scored["per_k"]["5"]["gold_recall"], 1.0)
        self.assertGreater(scored["per_k"]["5"]["ndcg"], 0)
        self.assertLess(scored["per_k"]["5"]["ndcg"], 1)

    def test_aggregate_does_not_use_sparse_judgments_as_precision(self) -> None:
        case = {
            "id": "toy",
            "query": "toy",
            "tags": [],
            "judgments": [{"repository": "r", "file": "owner", "relevance": 3}],
        }
        scored = evaluate.score_case(
            case,
            [
                {"Repository": "unknown", "FileName": "possibly-relevant", "Score": 10},
                {"Repository": "r", "FileName": "owner", "Score": 9},
            ],
            "toy",
            {"elapsed_ms": 1.0, "payload_bytes": 1},
        )
        metrics = evaluate.aggregate([scored])
        self.assertNotIn("precision@1", metrics)
        self.assertEqual(metrics["hit@5"], 1)

    def test_rrf_rewards_results_supported_by_multiple_runs(self) -> None:
        fused = rrf_fuse([
            [
                {"Repository": "r", "FileName": "a", "Score": 9},
                {"Repository": "r", "FileName": "b", "Score": 8},
            ],
            [
                {"Repository": "r", "FileName": "b", "Score": 9},
                {"Repository": "r", "FileName": "c", "Score": 8},
            ],
        ])
        self.assertEqual(fused[0]["FileName"], "b")
        self.assertEqual(fused[0]["RRFLists"], 2)

    def test_compare_requires_same_index_fingerprint(self) -> None:
        base = {
            "index": {"metadata_sha256": "a"},
            "metrics": {
                "hit@1": 1, "hit@5": 1, "hit@10": 1, "hit@20": 1,
                "owner_hit@1": 1, "owner_hit@5": 1,
                "owner_hit@10": 1, "owner_hit@20": 1,
                "mrr": 1, "owner_mrr": 1, "ndcg@10": 1, "ndcg@20": 1,
            },
        }
        current = copy.deepcopy(base)
        current["index"] = {"metadata_sha256": "b"}
        problems = evaluate.compare_reports(current, base, 0)
        self.assertEqual(len(problems), 1)
        self.assertIn("index fingerprint differs", problems[0])


if __name__ == "__main__":
    unittest.main()
