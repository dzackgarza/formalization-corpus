#!/usr/bin/env python3
"""Evaluate a field-separated Zoekt lexical candidate with weighted RRF.

This candidate deliberately keeps retrieval inside Zoekt rather than inventing a
new term scorer.  It queries three existing lexical views independently:

* the deployed path-or-content conjunction;
* a strict content-only conjunction;
* a relaxed path channel requiring at least one normalized mathematical term.

The ranked lists are combined with weighted Reciprocal Rank Fusion.  This tests
whether explicit field separation can recover direct-owner files that the
single Zoekt ranking buries or excludes, while retaining the deployed lexical
query as the dominant signal.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable

import evaluate
import provenance

ROOT = pathlib.Path(__file__).resolve().parents[2]


def compile_field_queries(text: str) -> dict[str, str]:
    terms, proof_filter = evaluate.normalized_query_terms(text)
    formal_filter = proof_filter or evaluate.FORMAL_FILES
    if not terms:
        fallback = f'content:"$a" file:{formal_filter} case:no'
        return {"baseline": fallback, "content": fallback, "path": fallback}

    escaped = [evaluate.quoted_pattern(evaluate.regex_escape(term)) for term in terms]
    baseline = evaluate.compile_query(text, "normalized_path_content_v1")
    content = " ".join(
        [*(f"content:{term}" for term in escaped), f"file:{formal_filter}", "case:no"]
    )
    path_any = " or ".join(f"file:{term}" for term in escaped)
    path = f"({path_any}) file:{formal_filter} case:no"
    return {"baseline": baseline, "content": content, "path": path}


def weighted_rrf_fuse(
    rankings: list[tuple[str, float, list[dict[str, Any]]]],
    *,
    constant: int = 60,
    depth: int = 200,
) -> list[dict[str, Any]]:
    scores: dict[tuple[str, str], float] = {}
    representatives: dict[tuple[str, str], dict[str, Any]] = {}
    fields: dict[tuple[str, str], list[str]] = {}
    for field, weight, ranking in rankings:
        seen: set[tuple[str, str]] = set()
        for rank, item in enumerate(ranking[:depth], start=1):
            key = (item.get("Repository", ""), item.get("FileName", ""))
            if key in seen:
                continue
            seen.add(key)
            scores[key] = scores.get(key, 0.0) + weight / (constant + rank)
            representatives.setdefault(key, item)
            fields.setdefault(key, []).append(field)

    fused: list[dict[str, Any]] = []
    for key, score in scores.items():
        item = dict(representatives[key])
        item["Score"] = score
        item["RRFFields"] = fields[key]
        fused.append(item)
    fused.sort(
        key=lambda item: (
            -float(item["Score"]),
            item.get("Repository", ""),
            item.get("FileName", ""),
        )
    )
    return fused


def retrieve_fielded(
    text: str,
    *,
    timeout: float,
    provider: str,
    api_url: str,
    serving: dict[str, Any] | None,
    depth: int,
    rrf_constant: int,
    weights: dict[str, float],
    api_retries: int = 0,
    api_workers: int = 1,
    api_search_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    if api_workers <= 0:
        raise ValueError("api_workers must be positive")
    queries = compile_field_queries(text)
    rankings: list[tuple[str, float, list[dict[str, Any]]]] = []
    request_elapsed_ms = 0.0
    payload_bytes = 0
    physical_api_requests = 0
    coalesced_api_hits = 0
    fields = ("baseline", "content", "path")

    def run_field(field: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        query = queries[field]
        if provider == "local":
            results, runtime = evaluate.local_search(query, timeout)
        elif provider == "api":
            search = api_search_fn or evaluate.api_search
            results, runtime = search(
                query,
                timeout,
                api_url,
                serving or evaluate.serving_options(top=depth, whole=False),
                retries=api_retries,
            )
        else:
            raise ValueError(f"unknown retrieval provider: {provider}")
        return field, results, runtime

    started = time.perf_counter()
    if provider == "api" and api_workers > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(api_workers, len(fields))) as executor:
            futures = {field: executor.submit(run_field, field) for field in fields}
            completed = [futures[field].result() for field in fields]
    else:
        completed = [run_field(field) for field in fields]
    elapsed_ms = (time.perf_counter() - started) * 1000

    for field, results, runtime in completed:
        rankings.append((field, weights[field], results))
        request_elapsed_ms += runtime["elapsed_ms"]
        payload_bytes += runtime["payload_bytes"]
        if provider == "api":
            physical_api_requests += int(runtime.get("physical_api_requests", 1))
            coalesced_api_hits += int(runtime.get("coalesced_api_hits", 0))

    fused = weighted_rrf_fuse(rankings, constant=rrf_constant, depth=depth)
    return fused, {
        "elapsed_ms": elapsed_ms,
        "request_elapsed_ms": request_elapsed_ms,
        "payload_bytes": payload_bytes,
        "returned_files": len(fused),
        "retrieval_queries": len(rankings),
        "physical_api_requests": physical_api_requests if provider == "api" else 0,
        "coalesced_api_hits": coalesced_api_hits if provider == "api" else 0,
        "api_workers": api_workers if provider == "api" else 1,
    }, queries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=pathlib.Path, default=evaluate.DEFAULT_GOLD)
    parser.add_argument("--provider", choices=("local", "api"), default="local")
    parser.add_argument("--api-url", default=evaluate.DEFAULT_API_URL)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--depth", type=int, default=200)
    parser.add_argument("--rrf-constant", type=int, default=60)
    parser.add_argument("--baseline-weight", type=float, default=2.0)
    parser.add_argument("--content-weight", type=float, default=1.0)
    parser.add_argument("--path-weight", type=float, default=1.0)
    parser.add_argument("--api-workers", type=int, default=1)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    if args.depth <= 0:
        print("ERROR: depth must be positive", file=sys.stderr)
        return 2
    if args.api_workers <= 0:
        print("ERROR: api workers must be positive", file=sys.stderr)
        return 2
    weights = {
        "baseline": args.baseline_weight,
        "content": args.content_weight,
        "path": args.path_weight,
    }
    if any(weight <= 0 for weight in weights.values()):
        print("ERROR: field weights must be positive", file=sys.stderr)
        return 2
    if args.provider == "local" and (
        not evaluate.INDEX_DIR.is_dir() or not any(evaluate.INDEX_DIR.glob("*.zoekt"))
    ):
        print("ERROR: local .zoekt index is unavailable", file=sys.stderr)
        return 2

    gold = evaluate.load_gold(args.gold)
    errors = evaluate.validate_gold(gold)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    serving = (
        evaluate.serving_options(top=args.depth, whole=False)
        if args.provider == "api"
        else None
    )
    api_index_before = (
        evaluate.api_index_fingerprint(args.api_url, args.timeout)
        if args.provider == "api"
        else None
    )

    scored_cases: list[dict[str, Any]] = []
    for case in gold["cases"]:
        try:
            results, runtime, queries = retrieve_fielded(
                case["query"],
                timeout=args.timeout,
                provider=args.provider,
                api_url=args.api_url,
                serving=serving,
                depth=args.depth,
                rrf_constant=args.rrf_constant,
                weights=weights,
                api_workers=args.api_workers,
            )
        except Exception as exc:
            print(f"ERROR {case['id']}: {exc}", file=sys.stderr)
            return 2
        scored = evaluate.score_case(
            case,
            results,
            " FIELDED_RRF ".join(queries.values()),
            runtime,
        )
        scored["field_queries"] = queries
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
        "variant": "zoekt_fielded_rrf_v1",
        "provider": args.provider,
        "api_url": args.api_url if args.provider == "api" else None,
        "serving_options": serving,
        "field_weights": weights,
        "api_workers": args.api_workers if args.provider == "api" else 1,
        "rrf_constant": args.rrf_constant,
        "fusion_depth": args.depth,
        "index": evaluate.index_fingerprint() if args.provider == "local" else api_index_before,
        "retrieval_engine": evaluate.retrieval_engine_fingerprint() if args.provider == "local" else None,
        "result_role_state": evaluate.file_role_index().fingerprint(),
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
