#!/usr/bin/env python3
"""Build a TREC-style relevance-judgment pool from independent retrieval runs."""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import defaultdict
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_GOLD = ROOT / "evaluation/search/gold.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=pathlib.Path)
    parser.add_argument("--gold", type=pathlib.Path, default=DEFAULT_GOLD)
    parser.add_argument("--depth", type=int, default=10)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()

    gold = json.loads(args.gold.read_text())
    gold_cases = {case["id"]: case for case in gold["cases"]}
    existing: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for cid, case in gold_cases.items():
        existing[cid] = {
            (j["repository"], j["file"]): j for j in case["judgments"]
        }

    pool: dict[str, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    run_meta = []
    expected_index = None
    expected_gold = None
    for report_path in args.reports:
        report = json.loads(report_path.read_text())
        if expected_index is None:
            expected_index = report.get("index")
            expected_gold = report.get("gold_sha256")
        if report.get("index") != expected_index:
            raise SystemExit(f"index mismatch: {report_path}")
        if report.get("gold_sha256") != expected_gold:
            raise SystemExit(f"gold mismatch: {report_path}")
        run = report["variant"]
        run_meta.append({"variant": run, "path": str(report_path), "depth": args.depth})
        for case in report["cases"]:
            cid = case["id"]
            if cid not in gold_cases:
                raise SystemExit(f"unknown case {cid} in {report_path}")
            for result in case["top_results"][: args.depth]:
                key = (result["repository"], result["file"])
                entry = pool[cid].setdefault(
                    key,
                    {
                        "repository": key[0],
                        "file": key[1],
                        "runs": {},
                        "judgment": existing[cid].get(key),
                    },
                )
                entry["runs"][run] = result["rank"]

    cases = []
    judged_relevant = 0
    judged_nonrelevant = 0
    unjudged = 0
    for cid, case in gold_cases.items():
        candidates = list(pool[cid].values())
        candidates.sort(
            key=lambda item: (
                min(item["runs"].values()),
                -len(item["runs"]),
                item["repository"],
                item["file"],
            )
        )
        for item in candidates:
            if item["judgment"] is None:
                unjudged += 1
            elif item["judgment"]["relevance"] == 0:
                judged_nonrelevant += 1
            else:
                judged_relevant += 1
        cases.append(
            {
                "id": cid,
                "query": case["query"],
                "candidates": candidates,
            }
        )

    output = {
        "schema_version": 1,
        "gold_sha256": expected_gold,
        "index": expected_index,
        "pool_depth_per_run": args.depth,
        "runs": run_meta,
        "summary": {
            "queries": len(cases),
            "candidates": judged_relevant + judged_nonrelevant + unjudged,
            "already_judged": judged_relevant + judged_nonrelevant,
            "judged_relevant": judged_relevant,
            "judged_nonrelevant": judged_nonrelevant,
            "unjudged": unjudged,
        },
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(
        f"{args.output}: {len(cases)} queries, "
        f"{judged_relevant + judged_nonrelevant + unjudged} pooled candidates, "
        f"{judged_relevant} relevant, {judged_nonrelevant} nonrelevant, "
        f"{unjudged} awaiting judgment"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
