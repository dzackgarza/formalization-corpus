#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate  # noqa: E402
from evaluate_multiquery import rrf_fuse  # noqa: E402
from evaluate_rerank import bounded_excerpt, humanize_path  # noqa: E402


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

    def test_frontend_and_evaluator_share_normalization_contract(self) -> None:
        queries = [
            "Is Serre duality for coherent sheaves already formalized?",
            "does Lean have the Bruhat Tits tree?",
            "Jordan canonical form of a linear operator",
            "Yoneda lemma for univalent categories in Rocq",
            "dyadic Hilbert symbol over Q2",
        ]
        script = r"""
const fs = require('fs');
const q = require('./site/search-query.js');
const config = JSON.parse(fs.readFileSync('./site/search-query.json', 'utf8'));
const queries = JSON.parse(process.argv[1]);
process.stdout.write(JSON.stringify(queries.map(text => q.normalizedQueryTerms(text, config))));
"""
        output = subprocess.check_output(
            ["node", "-e", script, json.dumps(queries)],
            cwd=HERE.parents[1],
            text=True,
        )
        javascript = json.loads(output)
        python = [
            {"terms": terms, "proofFilter": proof_filter}
            for terms, proof_filter in map(evaluate.normalized_query_terms, queries)
        ]
        self.assertEqual(javascript, python)

    def test_frontend_v2_does_not_turn_intent_only_text_into_match_all(self) -> None:
        compiled = evaluate.compile_query("is this already formalized?", "frontend_lexical_v2")
        self.assertIn('content:"$a"', compiled)

    def test_normalized_query_removes_intent_words_and_detects_proof_assistant(self) -> None:
        terms, proof_filter = evaluate.normalized_query_terms(
            "does Lean have the Jordan canonical form theorem?"
        )
        self.assertEqual(terms, ["Jordan", "canonical", "form", "theorem"])
        self.assertEqual(proof_filter, r"\.lean$")

    def test_mathematical_words_are_not_global_stopwords(self) -> None:
        terms, _ = evaluate.normalized_query_terms(
            "formal group law proof irrelevance existence construction"
        )
        self.assertEqual(
            terms,
            ["formal", "group", "law", "proof", "irrelevance", "existence", "construction"],
        )
        prefixed, _ = evaluate.normalized_query_terms(
            "formal proof of the Feit Thompson odd order theorem"
        )
        self.assertEqual(prefixed, ["Feit", "Thompson", "odd", "order", "theorem"])
        definition, _ = evaluate.normalized_query_terms("definition of formal group law")
        self.assertEqual(definition, ["formal", "group", "law"])
        lean4_terms, lean4_filter = evaluate.normalized_query_terms("does Lean4 have formal group laws")
        self.assertEqual(lean4_terms, ["formal", "group", "laws"])
        self.assertEqual(lean4_filter, r"\.lean$")
        hol4_terms, hol4_filter = evaluate.normalized_query_terms("HOL4 Jordan curve theorem")
        self.assertEqual(hol4_terms, ["Jordan", "curve", "theorem"])
        self.assertEqual(hol4_filter, r"\.(sml|sig)$")

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

    def test_explicit_negative_judgment_is_not_relevant_or_source_hit(self) -> None:
        case = {
            "id": "toy",
            "query": "toy",
            "tags": [],
            "judgments": [
                {"repository": "good", "file": "owner", "relevance": 3},
                {"repository": "bad", "file": "reviewed-negative", "relevance": 0},
            ],
        }
        scored = evaluate.score_case(
            case,
            [{"Repository": "bad", "FileName": "reviewed-negative", "Score": 10}],
            "toy",
            {"elapsed_ms": 1.0, "payload_bytes": 1},
        )
        self.assertEqual(scored["per_k"]["1"]["hit"], 0)
        self.assertEqual(scored["per_k"]["1"]["source_hit"], 0)
        self.assertEqual(scored["reciprocal_rank"], 0.0)

    def test_rerank_projection_humanizes_paths_and_removes_import_boilerplate(self) -> None:
        self.assertIn(
            "Jordan Normal Form",
            humanize_path("LeanEval/LinearAlgebra/JordanNormalForm.lean"),
        )
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "x.lean"
            path.write_text(
                "import Foo\npublic import Bar\n/-- direct owner -/\ntheorem owner : True := by trivial\n"
            )
            excerpt = bounded_excerpt(path, max_lines=20, max_chars=1000)
        self.assertNotIn("import Foo", excerpt)
        self.assertNotIn("public import Bar", excerpt)
        self.assertIn("theorem owner", excerpt)

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
            "gold_sha256": "gold",
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

    def test_compare_requires_same_gold_hash(self) -> None:
        base = {
            "gold_sha256": "a",
            "index": {"metadata_sha256": "same"},
            "metrics": {},
        }
        current = copy.deepcopy(base)
        current["gold_sha256"] = "b"
        problems = evaluate.compare_reports(current, base, 0)
        self.assertEqual(len(problems), 1)
        self.assertIn("gold-set hash differs", problems[0])


if __name__ == "__main__":
    unittest.main()
