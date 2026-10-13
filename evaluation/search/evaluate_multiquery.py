#!/usr/bin/env python3
"""Evaluate frozen multi-query lexical retrieval with Reciprocal Rank Fusion."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable

import evaluate
import provenance

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


def load_expansion_queries(path: pathlib.Path, gold: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    expansion_data = json.loads(path.read_text())
    expansion_queries = expansion_data.get("queries") or {}
    missing = [case["id"] for case in gold["cases"] if case["id"] not in expansion_queries]
    if missing:
        raise ValueError(f"missing frozen expansions for: {', '.join(missing)}")
    return expansion_data, expansion_queries


def retrieve_multiquery(
    case: dict[str, Any],
    expansion_queries: dict[str, list[str]],
    *,
    timeout: float = 30.0,
    rrf_constant: int = 60,
    depth: int = 200,
    provider: str = "local",
    api_url: str = evaluate.DEFAULT_API_URL,
    serving: dict[str, Any] | None = None,
    api_retries: int = 0,
    api_workers: int = 1,
    api_search_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str], list[str]]:
    if api_workers <= 0:
        raise ValueError("api_workers must be positive")
    formulations = [case["query"], *expansion_queries[case["id"]]]
    compiled: list[str] = []
    query_specs: list[str] = []
    payload_bytes = 0
    request_elapsed_ms = 0.0
    physical_api_requests = 0
    coalesced_api_hits = 0
    seen_queries: set[str] = set()
    for formulation in formulations:
        query = evaluate.compile_query(formulation, "normalized_path_content_v1")
        if query in seen_queries:
            continue
        seen_queries.add(query)
        compiled.append(query)
        query_specs.append(query)

    def run_query(query: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if provider == "local":
            results, runtime = evaluate.local_search(query, timeout)
        elif provider == "api":
            search = api_search_fn or evaluate.api_search
            results, runtime = search(
                query,
                timeout,
                api_url,
                serving or evaluate.serving_options(whole=False),
                retries=api_retries,
            )
        else:
            raise ValueError(f"unknown retrieval provider: {provider}")
        return results, runtime

    started = time.perf_counter()
    if provider == "api" and api_workers > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(api_workers, len(query_specs))) as executor:
            futures = [executor.submit(run_query, query) for query in query_specs]
            completed = [future.result() for future in futures]
    else:
        completed = [run_query(query) for query in query_specs]
    elapsed_ms = (time.perf_counter() - started) * 1000

    rankings: list[list[dict[str, Any]]] = []
    for results, runtime in completed:
        rankings.append(results)
        request_elapsed_ms += runtime["elapsed_ms"]
        payload_bytes += runtime["payload_bytes"]
        if provider == "api":
            physical_api_requests += int(runtime.get("physical_api_requests", 1))
            coalesced_api_hits += int(runtime.get("coalesced_api_hits", 0))
    fused = rrf_fuse(rankings, constant=rrf_constant, depth=depth)
    runtime = {
        "elapsed_ms": elapsed_ms,
        "request_elapsed_ms": request_elapsed_ms,
        "payload_bytes": payload_bytes,
        "returned_files": len(fused),
        "retrieval_queries": len(rankings),
        "physical_api_requests": physical_api_requests if provider == "api" else 0,
        "coalesced_api_hits": coalesced_api_hits if provider == "api" else 0,
        "api_workers": api_workers if provider == "api" else 1,
    }
    return fused, runtime, formulations, compiled


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=pathlib.Path, default=evaluate.DEFAULT_GOLD)
    parser.add_argument("--expansions", type=pathlib.Path, default=DEFAULT_EXPANSIONS)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--provider", choices=("local", "api"), default="local")
    parser.add_argument("--api-url", default=evaluate.DEFAULT_API_URL)
    parser.add_argument("--rrf-constant", type=int, default=60)
    parser.add_argument("--depth", type=int, default=200)
    parser.add_argument("--api-workers", type=int, default=1)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    if args.api_workers <= 0:
        print("ERROR: api workers must be positive", file=sys.stderr)
        return 2

    if args.provider == "local" and (
        not evaluate.INDEX_DIR.is_dir() or not any(evaluate.INDEX_DIR.glob("*.zoekt"))
    ):
        print("ERROR: local .zoekt index is unavailable", file=sys.stderr)
        return 2
    serving = evaluate.serving_options(whole=False) if args.provider == "api" else None
    api_index_before = (
        evaluate.api_index_fingerprint(args.api_url, args.timeout)
        if args.provider == "api"
        else None
    )

    gold = evaluate.load_gold(args.gold)
    errors = evaluate.validate_gold(gold)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 2
    try:
        expansion_data, expansion_queries = load_expansion_queries(args.expansions, gold)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    scored_cases: list[dict[str, Any]] = []
    for case in gold["cases"]:
        fused, runtime, formulations, compiled = retrieve_multiquery(
            case,
            expansion_queries,
            timeout=args.timeout,
            rrf_constant=args.rrf_constant,
            depth=args.depth,
            provider=args.provider,
            api_url=args.api_url,
            serving=serving,
            api_workers=args.api_workers,
        )
        scored = evaluate.score_case(case, fused, " MULTIQUERY ".join(compiled), runtime)
        scored["formulations"] = formulations
        scored_cases.append(scored)

    repo_state = provenance.repository_state(ROOT)
    if args.provider == "api":
        api_index_after = evaluate.api_index_fingerprint(args.api_url, args.timeout)
        if api_index_after != api_index_before:
            print("ERROR: published API index changed during evaluation", file=sys.stderr)
            return 2
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_git_commit": repo_state["commit"],
        "repository_state": repo_state,
        "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
        "query_config_sha256": evaluate.query_config_sha256(),
        "serving_config_sha256": evaluate.serving_config_sha256(),
        "expansions_sha256": hashlib.sha256(args.expansions.read_bytes()).hexdigest(),
        "expansion_model": expansion_data.get("model"),
        "expansion_prompt_version": expansion_data.get("prompt_version"),
        "variant": "gemini_multiquery_rrf_v1",
        "provider": args.provider,
        "api_url": args.api_url if args.provider == "api" else None,
        "serving_options": serving,
        "rrf_constant": args.rrf_constant,
        "fusion_depth": args.depth,
        "api_workers": args.api_workers if args.provider == "api" else 1,
        "index": evaluate.index_fingerprint() if args.provider == "local" else api_index_before,
        "retrieval_engine": evaluate.retrieval_engine_fingerprint() if args.provider == "local" else None,
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
