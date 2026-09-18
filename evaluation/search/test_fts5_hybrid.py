#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from evaluate_fts5_hybrid import (  # noqa: E402
    add_pair_rank_evidence,
    add_source_hierarchy_rank,
    balanced_pair_union,
    prefilter_by_pair_rank_evidence,
    project_source_local_order,
    rank_by_pair_rank_evidence,
    retrieve_zoekt_first_stage,
)


class Fts5HybridTests(unittest.TestCase):
    def test_balanced_pair_union_preserves_independent_source_ranks(self) -> None:
        fielded = [
            {"Repository": "r", "FileName": "a"},
            {"Repository": "r", "FileName": "shared"},
        ]
        fts5 = [
            {"Repository": "r", "FileName": "b"},
            {"Repository": "r", "FileName": "shared"},
        ]
        result = balanced_pair_union(
            fielded,
            fts5,
            first_name="fielded",
            second_name="corpus-fts5",
            per_retriever_depth=2,
        )
        self.assertEqual(
            [(item["Repository"], item["FileName"]) for item in result],
            [("r", "a"), ("r", "b"), ("r", "shared")],
        )
        self.assertEqual(
            result[2]["CandidateSourceRanks"],
            {"fielded": 2, "corpus-fts5": 2},
        )

    def test_source_local_projection_preserves_repository_slots(self) -> None:
        base = [
            {"Repository": "lean", "FileName": "a.lean", "Score": 10.0},
            {"Repository": "mizar", "FileName": "a.miz", "Score": 9.0},
            {"Repository": "lean", "FileName": "b.lean", "Score": 8.0},
            {"Repository": "mizar", "FileName": "b.miz", "Score": 7.0},
        ]
        preferred = [
            {"Repository": "lean", "FileName": "b.lean", "Score": 12.0},
            {"Repository": "mizar", "FileName": "a.miz", "Score": 9.0},
            {"Repository": "lean", "FileName": "a.lean", "Score": 6.0},
            {"Repository": "mizar", "FileName": "b.miz", "Score": 7.0},
        ]
        projected = project_source_local_order(base, preferred)
        self.assertEqual(
            [item["Repository"] for item in projected],
            [item["Repository"] for item in base],
        )
        self.assertEqual(
            [item["FileName"] for item in projected],
            ["b.lean", "a.miz", "a.lean", "b.miz"],
        )
        self.assertEqual([item["Score"] for item in projected], [10.0, 9.0, 8.0, 7.0])
        self.assertEqual(projected[0]["SourceLocalBaseItemRank"], 3)

    def test_source_local_projection_rejects_candidate_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            project_source_local_order(
                [{"Repository": "r", "FileName": "a"}],
                [{"Repository": "r", "FileName": "b"}],
            )

    def test_rank_evidence_rewards_support_from_both_first_stages(self) -> None:
        rows = [
            {
                "Repository": "r",
                "FileName": "single",
                "Score": 0.0,
                "CandidateUnionRank": 1,
                "CandidateSourceRanks": {"fielded": 1},
            },
            {
                "Repository": "r",
                "FileName": "both",
                "Score": 0.0,
                "CandidateUnionRank": 2,
                "CandidateSourceRanks": {"fielded": 2, "corpus-fts5": 2},
            },
        ]
        result = add_pair_rank_evidence(
            rows,
            channels=("fielded", "corpus-fts5"),
            rrf_constant=60,
        )
        self.assertEqual(result[0]["FileName"], "both")
        self.assertEqual(
            result[0]["FirstStageRankEvidence"],
            {"fielded": 2, "corpus-fts5": 2},
        )

    def test_prefilter_uses_both_first_stage_ranks_before_truncation(self) -> None:
        rows = [
            {
                "Repository": "r",
                "FileName": "fielded-only",
                "CandidateUnionRank": 1,
                "CandidateSourceRanks": {"fielded": 1},
            },
            {
                "Repository": "r",
                "FileName": "shared",
                "CandidateUnionRank": 2,
                "CandidateSourceRanks": {"fielded": 50, "corpus-fts5": 50},
            },
            {
                "Repository": "r",
                "FileName": "fts5-only",
                "CandidateUnionRank": 3,
                "CandidateSourceRanks": {"corpus-fts5": 10},
            },
        ]
        result = prefilter_by_pair_rank_evidence(
            rows,
            channels=("fielded", "corpus-fts5"),
            rrf_constant=60,
            limit=2,
        )
        self.assertEqual(
            [item["FileName"] for item in result],
            ["shared", "fielded-only"],
        )
        self.assertGreater(
            result[0]["FirstStageRankScore"],
            result[1]["FirstStageRankScore"],
        )

    def test_first_stage_ranking_is_complete_and_qrel_independent(self) -> None:
        rows = [
            {
                "Repository": "r",
                "FileName": "single",
                "CandidateUnionRank": 1,
                "CandidateSourceRanks": {"fielded": 1},
            },
            {
                "Repository": "r",
                "FileName": "both",
                "CandidateUnionRank": 2,
                "CandidateSourceRanks": {"fielded": 5, "corpus-fts5": 5},
            },
        ]
        result = rank_by_pair_rank_evidence(
            rows,
            channels=("fielded", "corpus-fts5"),
            rrf_constant=60,
        )
        self.assertEqual([item["FileName"] for item in result], ["both", "single"])
        self.assertEqual(len(result), len(rows))
        self.assertEqual(result[0]["Score"], result[0]["FirstStageRankScore"])
        self.assertEqual(
            result[0]["FirstStageRankEvidence"],
            {"fielded": 5, "corpus-fts5": 5},
        )

    def test_source_hierarchy_rank_uses_best_file_from_each_independent_channel(self) -> None:
        candidates = [
            {
                "Repository": "source-a",
                "FileName": "owner.lean",
                "CandidateUnionRank": 1,
                "CandidateSourceRanks": {"fielded": 2},
            },
            {
                "Repository": "source-b",
                "FileName": "mention.lean",
                "CandidateUnionRank": 2,
                "CandidateSourceRanks": {"fielded": 1},
            },
            {
                "Repository": "source-a",
                "FileName": "alternate.lean",
                "CandidateUnionRank": 3,
                "CandidateSourceRanks": {"corpus-fts5": 3},
            },
        ]
        enriched = add_source_hierarchy_rank(
            candidates,
            base_channels=("fielded", "corpus-fts5"),
            rrf_constant=60,
        )
        by_file = {item["FileName"]: item for item in enriched}
        self.assertEqual(by_file["owner.lean"]["SourceHierarchyRank"], 1)
        self.assertEqual(by_file["alternate.lean"]["SourceHierarchyRank"], 1)
        self.assertEqual(by_file["mention.lean"]["SourceHierarchyRank"], 2)
        self.assertEqual(
            by_file["owner.lean"]["SourceHierarchyBestFileRanks"],
            {"fielded": 2, "corpus-fts5": 3},
        )
        ranked = rank_by_pair_rank_evidence(
            enriched,
            channels=("fielded", "corpus-fts5", "source-hierarchy"),
            rrf_constant=60,
        )
        self.assertEqual(ranked[0]["FileName"], "owner.lean")

    @patch("evaluate_fts5_hybrid.retrieve_fielded")
    def test_fielded_first_stage_forwards_api_worker_bound(self, retrieve_fielded) -> None:
        retrieve_fielded.return_value = (
            [{"Repository": "r", "FileName": "a"}],
            {"physical_api_requests": 2},
            {"baseline": "baseline-query", "path": "path-query"},
        )
        results, runtime, compiled, queries = retrieve_zoekt_first_stage(
            "coherent sheaf",
            mode="fielded",
            timeout=60.0,
            api_url="https://example.invalid/api/search",
            serving={"max_doc_display_count": 200},
            depth=200,
            rrf_constant=60,
            weights={"baseline": 2.0, "content": 1.0, "path": 1.0},
            fields=("baseline", "path"),
            api_workers=2,
        )
        self.assertEqual(results[0]["FileName"], "a")
        self.assertEqual(runtime["physical_api_requests"], 2)
        self.assertEqual(queries, {"baseline": "baseline-query", "path": "path-query"})
        self.assertIn("baseline-query", compiled)
        self.assertEqual(retrieve_fielded.call_args.kwargs["api_workers"], 2)


if __name__ == "__main__":
    unittest.main()
