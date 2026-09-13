#!/usr/bin/env python3
"""Evaluate frozen multi-query lexical retrieval with Reciprocal Rank Fusion."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
from datetime import datetime, timezone
from typing import Any

import evaluate

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_EXPANSIONS = ROOT / "evaluation/search/experiments/gemini_3_5_flash_lite_query_expansions_v1.json"


def rrf_fuse(rankings: list[list[dict[str, Any]]], constant: int = 60, depth: int = 200) -> list[dict[str, Any]]:
    scores: dict[tuple[str, str], float] = {}
    representatives: dict[tuple[str, str], dict[str, Any]] = {}
    appearances: dict[tuple[str, str], int] = {}
    for ranking in rankings:
        seen: set[tuple[str, str]] = set()
        for rank, item in enumerate(ranking[:depth], start=1):
            key = (item.get("Repository", ""), item.get("FileName", ""))
            if key in seen:
                continue
            seen.add(key)
            scores[key] = scores.get(key, 0.0) + 1.0 / (constant + rank)
            appearances[key] = appearances.get(key, 0) + 1
            representatives.setdefault(key, item)
    fused = []
    for key, score in scores.items():
        item = dict(representatives[key])
        item["Score"] = score
        item["RRFLists"] = appearances[key]
        fused.append(item)
    fused.sort(key=lambda item: (-float(item["Score"]), item.get("Repository", ""), item.get("FileName", "")))
    return fused


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=pathlib.Path, default=evaluate.DEFAULT_GOLD)
    parser.add_argument("--expansions", type=pathlib.Path, default=DEFAULT_EXPANSIONS)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--rrf-constant", type=int, default=60)
    parser.add_argument("--depth", type=int, default=200)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    gold = evaluate.load_gold(args.gold)
    errors = evaluate.validate_gold(gold)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 2
    expansion_data = json.loads(args.expansions.read_text())
    expansion_queries = expansion_data.get("queries") or {}
    missing = [case["id"] for case in gold["cases"] if case["id"] not in expansion_queries]
    if missing:
        print(f"ERROR: missing frozen expansions for: {', '.join(missing)}")
        return 2

    scored_cases: list[dict[str, Any]] = []
    for case in gold["cases"]:
        formulations = [case["query"], *expansion_queries[case["id"]]]
        compiled: list[str] = []
        rankings: list[list[dict[str, Any]]] = []
        elapsed_ms = 0.0
        payload_bytes = 0
        seen_queries: set[str] = set()
        for formulation in formulations:
            query = evaluate.compile_query(formulation, "normalized_path_content_v1")
            if query in seen_queries:
                continue
            seen_queries.add(query)
            results, runtime = evaluate.local_search(query, args.timeout)
            compiled.append(query)
            rankings.append(results)
            elapsed_ms += runtime["elapsed_ms"]
            payload_bytes += runtime["payload_bytes"]
        fused = rrf_fuse(rankings, constant=args.rrf_constant, depth=args.depth)
        runtime = {
            "elapsed_ms": elapsed_ms,
            "payload_bytes": payload_bytes,
            "returned_files": len(fused),
            "retrieval_queries": len(rankings),
        }
        scored = evaluate.score_case(case, fused, " MULTIQUERY ".join(compiled), runtime)
        scored["formulations"] = formulations
        scored_cases.append(scored)

    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
        "expansions_sha256": hashlib.sha256(args.expansions.read_bytes()).hexdigest(),
        "expansion_model": expansion_data.get("model"),
        "expansion_prompt_version": expansion_data.get("prompt_version"),
        "variant": "gemini_multiquery_rrf_v1",
        "provider": "local",
        "rrf_constant": args.rrf_constant,
        "fusion_depth": args.depth,
        "index": evaluate.index_fingerprint(),
        "metrics": evaluate.aggregate(scored_cases),
        "metrics_by_tag": evaluate.by_tag(scored_cases),
        "cases": scored_cases,
    }
    evaluate.print_summary(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
