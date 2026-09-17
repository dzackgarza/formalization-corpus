#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate  # noqa: E402
import evaluate_repeated  # noqa: E402
from evaluate_fielded_lexical import compile_field_queries, weighted_rrf_fuse  # noqa: E402
from evaluate_fielded_fts5 import (  # noqa: E402
    fts5_match_query,
    fts5_rerank,
    query_matched_windows,
)
from evaluate_multiquery import retrieve_multiquery, rrf_fuse  # noqa: E402
from evaluate_rerank import bounded_excerpt, humanize_path  # noqa: E402
from evaluate_union_fts5 import balanced_union  # noqa: E402


class SearchEvaluationTests(unittest.TestCase):

    def test_gold_validation_accepts_catalogued_file_when_source_cache_is_ghosted(self) -> None:
        gold = {
            "version": 1,
            "cases": [
                {
                    "id": "ghost-source",
                    "query": "flat module",
                    "judgments": [
                        {
                            "repository": "CBirkbeck__AINTLIB",
                            "file": "Common/Common.lean",
                            "relevance": 3,
                        }
                    ],
                }
            ],
        }
        with mock.patch.object(
            evaluate,
            "source_rows",
            return_value={"CBirkbeck__AINTLIB": {"directory": "definitely-missing-cache"}},
        ):
            self.assertEqual(evaluate.validate_gold(gold), [])

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

    def test_zoekt_bm25_uses_the_same_query_semantics_as_frontend_v2(self) -> None:
        text = "does Lean have the Jordan canonical form theorem?"
        self.assertEqual(
            evaluate.compile_query(text, "zoekt_bm25_v1"),
            evaluate.compile_query(text, "frontend_lexical_v2"),
        )

    def test_fielded_query_separates_path_and_content_evidence(self) -> None:
        queries = compile_field_queries("does Lean have the Jordan canonical form theorem?")
        self.assertEqual(
            queries["baseline"],
            evaluate.compile_query(
                "does Lean have the Jordan canonical form theorem?",
                "normalized_path_content_v1",
            ),
        )
        self.assertIn('content:"Jordan"', queries["content"])
        self.assertIn('content:"canonical"', queries["content"])
        self.assertIn('file:"Jordan" or file:"canonical"', queries["path"])
        self.assertIn(r"file:\.lean$", queries["path"])

    def test_weighted_rrf_rewards_cross_field_evidence(self) -> None:
        rankings = [
            ("baseline", 2.0, [{"Repository": "r", "FileName": "a"}]),
            (
                "content",
                1.0,
                [
                    {"Repository": "r", "FileName": "b"},
                    {"Repository": "r", "FileName": "a"},
                ],
            ),
            ("path", 1.0, [{"Repository": "r", "FileName": "b"}]),
        ]
        fused = weighted_rrf_fuse(rankings, constant=60, depth=200)
        self.assertEqual(fused[0]["FileName"], "a")
        self.assertEqual(fused[0]["RRFFields"], ["baseline", "content"])

    def test_fts5_second_stage_uses_shared_normalized_query_terms(self) -> None:
        self.assertEqual(
            fts5_match_query("does Lean have the Jordan canonical form theorem?"),
            '"Jordan" OR "canonical" OR "form" OR "theorem"',
        )

    def test_fts5_second_stage_can_promote_direct_owner_from_fixed_pool(self) -> None:
        candidates = [
            {
                "Repository": "r",
                "FileName": "Linear/JordanAlgebra.lean",
                "Score": 2.0,
            },
            {
                "Repository": "r",
                "FileName": "Linear/JordanNormalForm.lean",
                "Score": 1.0,
            },
        ]
        contents = {
            ("r", "Linear/JordanAlgebra.lean"): "Jordan algebra multiplication identity",
            ("r", "Linear/JordanNormalForm.lean"): (
                "Jordan canonical form theorem for a linear operator"
            ),
        }
        reranked = fts5_rerank(
            "Jordan canonical form of a linear operator", candidates, contents
        )
        self.assertEqual(reranked[0]["FileName"], "Linear/JordanNormalForm.lean")
        self.assertEqual(reranked[0]["SecondStage"], "sqlite_fts5_bm25_full")

    def test_fts5_matched_windows_keep_local_query_evidence(self) -> None:
        content = "\n".join(
            [
                "namespace Example",
                "supporting material",
                "theorem unrelated : True := by trivial",
                "more support",
                "theorem jordanCanonicalForm : True := by",
                "  -- Jordan canonical form for a linear operator",
                "  trivial",
                "tail material",
            ]
        )
        excerpt = query_matched_windows(
            "Jordan canonical form of a linear operator", content
        )
        self.assertIn("jordanCanonicalForm", excerpt)
        self.assertIn("Jordan canonical form for a linear operator", excerpt)
        self.assertIn("trivial", excerpt)
        self.assertNotIn("namespace Example", excerpt)

    def test_fts5_matched_windows_mode_is_recorded_on_results(self) -> None:
        candidates = [{"Repository": "r", "FileName": "Jordan.lean", "Score": 1.0}]
        contents = {
            ("r", "Jordan.lean"): "theorem jordan : True := by -- Jordan canonical form\ntrivial"
        }
        reranked = fts5_rerank(
            "Jordan canonical form", candidates, contents, content_mode="matched-windows"
        )
        self.assertEqual(reranked[0]["SecondStage"], "sqlite_fts5_bm25_matched-windows")

    def test_fts5_evidence_rrf_combines_path_broad_and_local_rankings(self) -> None:
        candidates = [
            {
                "Repository": "r",
                "FileName": "Linear/JordanAlgebra.lean",
                "Score": 3.0,
            },
            {
                "Repository": "r",
                "FileName": "Linear/JordanCanonicalForm.lean",
                "Score": 2.0,
            },
            {
                "Repository": "r",
                "FileName": "Linear/CanonicalMaps.lean",
                "Score": 1.0,
            },
        ]
        contents = {
            ("r", "Linear/JordanAlgebra.lean"): "Jordan algebra Jordan algebra Jordan algebra",
            ("r", "Linear/JordanCanonicalForm.lean"): (
                "theorem jordanCanonicalForm : True := by\n"
                "  -- Jordan canonical form for a linear operator\n"
                "  trivial"
            ),
            ("r", "Linear/CanonicalMaps.lean"): "canonical linear map theorem",
        }
        reranked = fts5_rerank(
            "Jordan canonical form of a linear operator",
            candidates,
            contents,
            content_mode="evidence-rrf",
        )
        self.assertEqual(reranked[0]["FileName"], "Linear/JordanCanonicalForm.lean")
        self.assertEqual(reranked[0]["SecondStage"], "sqlite_fts5_evidence_rrf")
        self.assertEqual(
            reranked[0]["SecondStageEvidence"],
            ["path", "full-content", "matched-windows"],
        )

    def test_fts5_evidence_rrf_preserves_first_stage_order_for_unmatched_candidates(self) -> None:
        candidates = [
            {"Repository": "r", "FileName": "A.lean", "Score": 2.0},
            {"Repository": "r", "FileName": "B.lean", "Score": 1.0},
        ]
        contents = {
            ("r", "A.lean"): "alpha",
            ("r", "B.lean"): "beta",
        }
        reranked = fts5_rerank(
            "Jordan canonical form",
            candidates,
            contents,
            content_mode="evidence-rrf",
        )
        self.assertEqual([item["FileName"] for item in reranked], ["A.lean", "B.lean"])

    def test_balanced_union_preserves_bounded_recall_from_both_retrievers(self) -> None:
        fielded = [
            {"Repository": "r", "FileName": "shared.lean", "Score": 3.0},
            {"Repository": "r", "FileName": "fielded-owner.lean", "Score": 2.0},
            {"Repository": "r", "FileName": "fielded-tail.lean", "Score": 1.0},
        ]
        multiquery = [
            {"Repository": "r", "FileName": "shared.lean", "Score": 4.0},
            {"Repository": "r", "FileName": "multi-owner.lean", "Score": 2.0},
            {"Repository": "r", "FileName": "multi-tail.lean", "Score": 1.0},
        ]
        union = balanced_union(fielded, multiquery, per_retriever_depth=2)
        self.assertEqual(
            [item["FileName"] for item in union],
            ["shared.lean", "fielded-owner.lean", "multi-owner.lean"],
        )
        self.assertEqual(union[0]["CandidateSources"], ["fielded", "multiquery"])
        self.assertEqual(
            union[0]["CandidateSourceRanks"],
            {"fielded": 1, "multiquery": 1},
        )
        self.assertEqual(union[1]["CandidateUnionRank"], 2)

    def test_query_compiler_does_not_hide_acl2_sys_proof_metadata(self) -> None:
        for variant in ("frontend_lexical_v1", "frontend_lexical_v2", "normalized_path_content_v1"):
            compiled = evaluate.compile_query("generated induction scheme", variant)
            self.assertNotIn(r"-file:(^|/)\.sys/", compiled)

    def test_serving_options_default_to_shared_frontend_config(self) -> None:
        serving = evaluate.serving_options()
        self.assertEqual(serving["max_doc_display_count"], 60)
        self.assertEqual(serving["shard_max_match_count"], 10000)
        self.assertEqual(serving["total_max_match_count"], 0)
        self.assertTrue(serving["whole"])

    def test_serving_options_can_override_internal_candidate_budgets(self) -> None:
        serving = evaluate.serving_options(
            top=60,
            shard_max_match_count=500,
            total_max_match_count=100000,
            whole=False,
            use_bm25_scoring=True,
        )
        self.assertEqual(serving["max_doc_display_count"], 60)
        self.assertEqual(serving["shard_max_match_count"], 500)
        self.assertEqual(serving["total_max_match_count"], 100000)
        self.assertFalse(serving["whole"])
        self.assertTrue(serving["use_bm25_scoring"])

    def test_api_index_fingerprint_ignores_list_order_but_tracks_index_state(self) -> None:
        def payload(order: list[str], *, documents: int = 10) -> dict:
            entries = []
            for name in order:
                entries.append(
                    {
                        "Repository": {"Name": name, "IndexOptions": "opts"},
                        "IndexMetadata": {
                            "ID": f"id-{name}",
                            "IndexFormatVersion": 16,
                            "IndexFeatureVersion": 12,
                            "IndexMinReaderVersion": 10,
                            "IndexTime": "2026-09-17T00:00:00Z",
                            "PlainASCII": False,
                            "LanguageMap": {"Lean": 1},
                            "ZoektVersion": "",
                        },
                        "Stats": {
                            "Shards": 1,
                            "Documents": documents,
                            "IndexBytes": 100,
                            "ContentBytes": 200,
                            "NewLinesCount": 300,
                        },
                    }
                )
            return {"List": {"Repos": entries}}

        left = evaluate.api_index_fingerprint_from_list(payload(["b", "a"]))
        right = evaluate.api_index_fingerprint_from_list(payload(["a", "b"]))
        changed = evaluate.api_index_fingerprint_from_list(payload(["a", "b"], documents=11))
        self.assertEqual(left, right)
        self.assertNotEqual(left["metadata_sha256"], changed["metadata_sha256"])
        self.assertEqual(left["repository_count"], 2)
        self.assertEqual(left["document_count"], 20)

    def test_query_semantics_hash_excludes_serving_budget(self) -> None:
        left = {
            "version": 1,
            "stopwords": ["the"],
            "proof_assistant_terms": {"lean": r"\.lean$"},
            "intent_prefixes": ["find"],
            "serving": {"max_doc_display_count": 60, "shard_max_match_count": 0},
        }
        right = copy.deepcopy(left)
        right["serving"]["shard_max_match_count"] = 10000
        self.assertEqual(
            evaluate.canonical_json_sha256(evaluate.query_semantics_config(left)),
            evaluate.canonical_json_sha256(evaluate.query_semantics_config(right)),
        )
        self.assertNotEqual(
            evaluate.canonical_json_sha256(left["serving"]),
            evaluate.canonical_json_sha256(right["serving"]),
        )

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
        pvs_terms, pvs_filter = evaluate.normalized_query_terms("PVS sound polynomial bound")
        self.assertEqual(pvs_terms, ["sound", "polynomial", "bound"])
        self.assertEqual(pvs_filter, r"\.(pvs|prf)$")

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

    def test_multiquery_can_retrieve_from_public_api_provider(self) -> None:
        case = {"id": "toy", "query": "toy theorem"}
        expansions = {"toy": ["toy result"]}
        calls: list[str] = []

        def api_search(query: str, timeout: float, api_url: str, serving: dict) -> tuple[list[dict], dict]:
            calls.append(query)
            result = {
                "Repository": "r",
                "FileName": "owner.lean" if "theorem" in query else "alternate.lean",
                "Score": 1,
            }
            return [result], {"elapsed_ms": 1.0, "payload_bytes": 1, "returned_files": 1}

        with mock.patch.object(evaluate, "api_search", side_effect=api_search):
            fused, runtime, formulations, _ = retrieve_multiquery(
                case,
                expansions,
                provider="api",
                api_url="https://example.test/api/search",
                serving=evaluate.serving_options(whole=False),
            )
        self.assertEqual(formulations, ["toy theorem", "toy result"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(runtime["retrieval_queries"], 2)
        self.assertEqual({item["FileName"] for item in fused}, {"owner.lean", "alternate.lean"})

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

    def test_compare_requires_same_result_role_state(self) -> None:
        metrics = {
            "hit@1": 1, "hit@5": 1, "hit@10": 1, "hit@20": 1,
            "owner_hit@1": 1, "owner_hit@5": 1,
            "owner_hit@10": 1, "owner_hit@20": 1,
            "mrr": 1, "owner_mrr": 1, "ndcg@10": 1, "ndcg@20": 1,
        }
        base = {
            "gold_sha256": "gold",
            "index": {"metadata_sha256": "same"},
            "query_config_sha256": "query",
            "result_role_state": {"navigation_count": 1, "navigation_sha256": "a"},
            "metrics": metrics,
        }
        current = copy.deepcopy(base)
        current["result_role_state"] = {"navigation_count": 2, "navigation_sha256": "b"}
        problems = evaluate.compare_reports(current, base, 0)
        self.assertEqual(len(problems), 1)
        self.assertIn("result-role state differs", problems[0])

    def test_pass_at_r_uses_unbiased_finite_sample_estimator(self) -> None:
        self.assertEqual(evaluate_repeated.pass_at_r(4, 0, 2), 0.0)
        self.assertEqual(evaluate_repeated.pass_at_r(4, 4, 2), 1.0)
        self.assertAlmostEqual(evaluate_repeated.pass_at_r(4, 2, 2), 5 / 6)

    def test_repeated_evaluation_separates_rank_cutoff_from_trial_count(self) -> None:
        def report(owner_hits: list[int]) -> dict:
            cases = []
            for i, owner_hit in enumerate(owner_hits):
                cases.append(
                    {
                        "id": f"q{i}",
                        "query": f"query {i}",
                        "reciprocal_rank": float(owner_hit),
                        "owner_reciprocal_rank": float(owner_hit),
                        "per_k": {
                            "10": {"hit": owner_hit, "owner_hit": owner_hit, "ndcg": float(owner_hit)}
                        },
                    }
                )
            return {
                "variant": "stochastic-toy",
                "provider": "toy",
                "gold_sha256": "gold",
                "query_config_sha256": "query",
                "index": {"metadata_sha256": "same"},
                "cases": cases,
            }

        result = evaluate_repeated.aggregate_repeated(
            [report([1, 0]), report([0, 0]), report([1, 0]), report([0, 1])],
            rank_cutoff=10,
            pass_r=(1, 2, 4),
            bootstrap_samples=0,
        )
        self.assertEqual(result["rank_cutoff"], 10)
        self.assertEqual(result["runs"], 4)
        self.assertAlmostEqual(result["summary"]["single_run_owner_success"]["mean"], 3 / 8)
        # q0 succeeds in 2/4 runs, so Pass@2 is 5/6; q1 succeeds in 1/4,
        # so Pass@2 is 1/2.  Aggregate over the two information needs.
        self.assertAlmostEqual(
            result["summary"]["pass_at_r"]["2"]["owner_success"]["mean"],
            (5 / 6 + 1 / 2) / 2,
        )


if __name__ == "__main__":
    unittest.main()
