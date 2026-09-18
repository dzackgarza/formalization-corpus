#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from evaluate_fts5_hybrid import add_pair_rank_evidence, balanced_pair_union  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
