#!/usr/bin/env python3
"""Evaluate the complementary fielded + frozen-multiquery lexical union.

The current SQ2 measurements show complementary direct-owner misses between the
field-separated lexical retriever and the frozen Gemini multi-query retriever.
This experiment keeps both first stages unchanged, takes a bounded prefix from
each ranked list, deduplicates their union, and applies the existing
judgment-independent SQLite FTS5 evidence ranker to that finite candidate set.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

import evaluate
import provenance
from evaluate_fielded_fts5 import (
    ApiContentCache,
    fetch_candidate_contents,
    fts5_match_query,
    fts5_rerank,
)
from evaluate_fielded_lexical import retrieve_fielded
from evaluate_multiquery import DEFAULT_EXPANSIONS, load_expansion_queries, retrieve_multiquery

ROOT = pathlib.Path(__file__).resolve().parents[2]


class CoalescingApiSearch:
    """Share identical API requests made by the two first-stage retrievers.

    The fielded baseline channel and the original frozen-multiquery formulation
    compile to the same Zoekt request.  Coalescing is therefore a transport-only
    optimization: every logical consumer sees the same ranked response, while
    network payload and physical-request accounting are charged once.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._futures: dict[tuple[str, str, str], concurrent.futures.Future] = {}

    @staticmethod
    def _key(query: str, api_url: str, serving: dict[str, Any]) -> tuple[str, str, str]:
        return (
            query,
            api_url,
            json.dumps(serving, sort_keys=True, separators=(",", ":")),
        )

    def __call__(
        self,
        query: str,
        timeout: float,
        api_url: str,
        serving: dict[str, Any],
        *,
        retries: int = 0,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        key = self._key(query, api_url, serving)
        started = time.perf_counter()
        with self._lock:
            future = self._futures.get(key)
            owner = future is None
            if owner:
                future = concurrent.futures.Future()
                self._futures[key] = future
        assert future is not None

        if owner:
            try:
                value = evaluate.api_search(
                    query,
                    timeout,
                    api_url,
                    serving,
                    retries=retries,
                )
            except BaseException as exc:
                future.set_exception(exc)
                raise
            future.set_result(value)
            results, original_runtime = value
            runtime = dict(original_runtime)
            runtime["physical_api_requests"] = 1
            runtime["coalesced_api_hits"] = 0
            return results, runtime

        results, original_runtime = future.result()
        runtime = dict(original_runtime)
        runtime["elapsed_ms"] = (time.perf_counter() - started) * 1000
        runtime["payload_bytes"] = 0
        runtime["physical_api_requests"] = 0
        runtime["coalesced_api_hits"] = 1
        return results, runtime


def balanced_union(
    fielded: list[dict[str, Any]],
    multiquery: list[dict[str, Any]],
    *,
    per_retriever_depth: int,
) -> list[dict[str, Any]]:
    """Interleave bounded prefixes while preserving provenance from both lists."""
    if per_retriever_depth <= 0:
        raise ValueError("per-retriever depth must be positive")

    result: list[dict[str, Any]] = []
    positions: dict[tuple[str, str], int] = {}
    for rank in range(per_retriever_depth):
        for source, ranking in (("fielded", fielded), ("multiquery", multiquery)):
            if rank >= len(ranking):
                continue
            original = ranking[rank]
            key = (original.get("Repository", ""), original.get("FileName", ""))
            existing_position = positions.get(key)
            if existing_position is None:
                item = dict(original)
                item["CandidateSources"] = [source]
                item["CandidateSourceRanks"] = {source: rank + 1}
                item["CandidateUnionRank"] = len(result) + 1
                positions[key] = len(result)
                result.append(item)
            else:
                item = result[existing_position]
                item["CandidateSources"].append(source)
                item["CandidateSourceRanks"][source] = rank + 1
    return result


def add_first_stage_rank_evidence(
    reranked: list[dict[str, Any]],
    *,
    rrf_constant: int = 60,
) -> list[dict[str, Any]]:
    """Add fielded/multiquery source ranks as two equal-weight RRF channels.

    ``fts5_rerank(..., content_mode="evidence-rrf")`` already stores in
    ``Score`` the equal-weight RRF sum from path, full-content, and local-content
    ranks.  The candidate union records each first-stage rank independently, so
    adding the corresponding reciprocal-rank terms gives a five-channel fusion
    without calibrating scores or consulting relevance judgments.
    """
    if rrf_constant <= 0:
        raise ValueError("RRF constant must be positive")
    fused: list[dict[str, Any]] = []
    for original in reranked:
        item = dict(original)
        source_ranks = item.get("CandidateSourceRanks") or {}
        retrieval_score = sum(
            1.0 / (rrf_constant + int(rank))
            for source, rank in source_ranks.items()
            if source in {"fielded", "multiquery"}
        )
        item["Score"] = float(item.get("Score", 0.0)) + retrieval_score
        item["SecondStage"] = "sqlite_fts5_plus_first_stage_rank_rrf"
        item["FirstStageRankEvidence"] = dict(source_ranks)
        fused.append(item)
    fused.sort(
        key=lambda item: (
            -float(item["Score"]),
            int(item.get("CandidateUnionRank", 10**9)),
            item.get("Repository", ""),
            item.get("FileName", ""),
        )
    )
    return fused


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=pathlib.Path, default=evaluate.DEFAULT_GOLD)
    parser.add_argument("--expansions", type=pathlib.Path, default=DEFAULT_EXPANSIONS)
    parser.add_argument("--api-url", default=evaluate.DEFAULT_API_URL)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--depth", type=int, default=200)
    parser.add_argument("--per-retriever-depth", type=int, default=50)
    parser.add_argument("--fetch-workers", type=int, default=8)
    parser.add_argument(
        "--first-stage-api-workers",
        type=int,
        default=1,
        help="bounded API concurrency inside each fielded/multiquery first stage",
    )
    parser.add_argument(
        "--api-retries",
        type=int,
        default=0,
        help="retry transient API transport failures this many times per search request",
    )
    parser.add_argument("--rrf-constant", type=int, default=60)
    parser.add_argument("--evidence-rrf-constant", type=int, default=60)
    parser.add_argument("--baseline-weight", type=float, default=2.0)
    parser.add_argument("--content-weight", type=float, default=1.0)
    parser.add_argument("--path-weight", type=float, default=1.0)
    parser.add_argument(
        "--include-first-stage-ranks",
        action="store_true",
        help="add fielded and multiquery source ranks as equal-weight RRF evidence channels",
    )
    parser.add_argument(
        "--parallel-first-stages",
        action="store_true",
        help="run the independent fielded and multiquery first stages concurrently",
    )
    parser.add_argument(
        "--coalesce-first-stage-requests",
        action="store_true",
        help="share identical API requests issued by the two first-stage retrievers",
    )
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    if min(
        args.depth,
        args.per_retriever_depth,
        args.fetch_workers,
        args.first_stage_api_workers,
        args.rrf_constant,
        args.evidence_rrf_constant,
    ) <= 0:
        print("ERROR: depths, workers, and RRF constants must be positive", file=sys.stderr)
        return 2
    if args.api_retries < 0:
        print("ERROR: api retries must be nonnegative", file=sys.stderr)
        return 2
    weights = {
        "baseline": args.baseline_weight,
        "content": args.content_weight,
        "path": args.path_weight,
    }
    if any(weight <= 0 for weight in weights.values()):
        print("ERROR: first-stage field weights must be positive", file=sys.stderr)
        return 2

    gold = evaluate.load_gold(args.gold)
    errors = evaluate.validate_gold(gold)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    try:
        expansion_data, expansion_queries = load_expansion_queries(args.expansions, gold)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    serving = evaluate.serving_options(top=args.depth, whole=False)
    api_index_before = evaluate.api_index_fingerprint(args.api_url, args.timeout)
    cache = ApiContentCache(api_url=args.api_url, timeout=args.timeout)
    scored_cases: list[dict[str, Any]] = []
    total_fetch_bytes = 0
    total_fetch_wall_ms = 0.0
    total_fetch_request_ms = 0.0
    total_first_stage_logical_queries = 0
    total_first_stage_physical_requests = 0
    total_first_stage_coalesced_hits = 0

    for number, case in enumerate(gold["cases"], start=1):
        shared_api_search = CoalescingApiSearch() if args.coalesce_first_stage_requests else None
        try:
            first_stage_started = time.perf_counter()
            if args.parallel_first_stages:
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    fielded_future = executor.submit(
                        retrieve_fielded,
                        case["query"],
                        timeout=args.timeout,
                        provider="api",
                        api_url=args.api_url,
                        serving=serving,
                        depth=args.depth,
                        rrf_constant=args.rrf_constant,
                        weights=weights,
                        api_retries=args.api_retries,
                        api_workers=args.first_stage_api_workers,
                        api_search_fn=shared_api_search,
                    )
                    multiquery_future = executor.submit(
                        retrieve_multiquery,
                        case,
                        expansion_queries,
                        timeout=args.timeout,
                        rrf_constant=args.rrf_constant,
                        depth=args.depth,
                        provider="api",
                        api_url=args.api_url,
                        serving=serving,
                        api_retries=args.api_retries,
                        api_workers=args.first_stage_api_workers,
                        api_search_fn=shared_api_search,
                    )
                    fielded, fielded_runtime, field_queries = fielded_future.result()
                    multiquery, multiquery_runtime, formulations, compiled = multiquery_future.result()
            else:
                fielded, fielded_runtime, field_queries = retrieve_fielded(
                    case["query"],
                    timeout=args.timeout,
                    provider="api",
                    api_url=args.api_url,
                    serving=serving,
                    depth=args.depth,
                    rrf_constant=args.rrf_constant,
                    weights=weights,
                    api_retries=args.api_retries,
                    api_workers=args.first_stage_api_workers,
                    api_search_fn=shared_api_search,
                )
                multiquery, multiquery_runtime, formulations, compiled = retrieve_multiquery(
                    case,
                    expansion_queries,
                    timeout=args.timeout,
                    rrf_constant=args.rrf_constant,
                    depth=args.depth,
                    provider="api",
                    api_url=args.api_url,
                    serving=serving,
                    api_retries=args.api_retries,
                    api_workers=args.first_stage_api_workers,
                    api_search_fn=shared_api_search,
                )
            first_stage_wall_ms = (time.perf_counter() - first_stage_started) * 1000
            candidates = balanced_union(
                fielded,
                multiquery,
                per_retriever_depth=args.per_retriever_depth,
            )
            contents, fetch_runtime = fetch_candidate_contents(
                candidates,
                cache=cache,
                workers=args.fetch_workers,
            )
            rerank_started = time.perf_counter()
            reranked = fts5_rerank(
                case["query"],
                candidates,
                contents,
                content_mode="evidence-rrf",
                evidence_rrf_constant=args.evidence_rrf_constant,
            )
            if args.include_first_stage_ranks:
                reranked = add_first_stage_rank_evidence(
                    reranked,
                    rrf_constant=args.evidence_rrf_constant,
                )
            rerank_ms = (time.perf_counter() - rerank_started) * 1000
        except Exception as exc:
            print(f"ERROR {case['id']}: {exc}", file=sys.stderr)
            return 2

        total_fetch_bytes += int(fetch_runtime["fetch_payload_bytes"])
        total_fetch_wall_ms += float(fetch_runtime["fetch_wall_ms"])
        total_fetch_request_ms += float(fetch_runtime["fetch_request_ms"])
        runtime = {
            "elapsed_ms": (
                first_stage_wall_ms
                + fetch_runtime["fetch_wall_ms"]
                + rerank_ms
            ),
            "first_stage_wall_ms": first_stage_wall_ms,
            "fielded_retrieval_ms": fielded_runtime["elapsed_ms"],
            "multiquery_retrieval_ms": multiquery_runtime["elapsed_ms"],
            "fetch_wall_ms": fetch_runtime["fetch_wall_ms"],
            "fetch_request_ms": fetch_runtime["fetch_request_ms"],
            "rerank_ms": rerank_ms,
            "payload_bytes": (
                fielded_runtime["payload_bytes"]
                + multiquery_runtime["payload_bytes"]
                + fetch_runtime["fetch_payload_bytes"]
            ),
            "returned_files": len(reranked),
            "retrieval_queries": (
                fielded_runtime["retrieval_queries"]
                + multiquery_runtime["retrieval_queries"]
            ),
            "physical_api_requests": (
                fielded_runtime["physical_api_requests"]
                + multiquery_runtime["physical_api_requests"]
            ),
            "coalesced_api_hits": (
                fielded_runtime["coalesced_api_hits"]
                + multiquery_runtime["coalesced_api_hits"]
            ),
            "content_fetches": len(candidates),
        }
        total_first_stage_logical_queries += int(runtime["retrieval_queries"])
        total_first_stage_physical_requests += int(runtime["physical_api_requests"])
        total_first_stage_coalesced_hits += int(runtime["coalesced_api_hits"])
        scored = evaluate.score_case(
            case,
            reranked,
            " FIELDED_MULTIQUERY_UNION ".join([*field_queries.values(), *compiled]),
            runtime,
        )
        scored["field_queries"] = field_queries
        scored["formulations"] = formulations
        scored["candidate_union_size"] = len(candidates)
        scored["second_stage_match_query"] = fts5_match_query(case["query"])
        scored_cases.append(scored)
        print(
            f"{number:02d}/{len(gold['cases'])} {case['id']} "
            f"candidates={len(candidates)} owner={scored['first_owner_rank']} "
            f"relevant={scored['first_relevant_rank']}",
            flush=True,
        )

    api_index_after = evaluate.api_index_fingerprint(args.api_url, args.timeout)
    if api_index_after != api_index_before:
        print("ERROR: published API index changed during evaluation", file=sys.stderr)
        return 2

    repo_state = provenance.repository_state(ROOT)
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
        "variant": (
            (
                "fielded_multiquery_union_fts5_plus_rank_evidence_rrf_coalesced_v1"
                if args.coalesce_first_stage_requests
                else "fielded_multiquery_union_fts5_plus_rank_evidence_rrf_parallel_v1"
                if args.parallel_first_stages
                else "fielded_multiquery_union_fts5_plus_rank_evidence_rrf_v1"
            )
            if args.include_first_stage_ranks
            else (
                "fielded_multiquery_union_fts5_evidence_rrf_parallel_v1"
                if args.parallel_first_stages
                else "fielded_multiquery_union_fts5_evidence_rrf_v1"
            )
        ),
        "provider": "api+sqlite-fts5",
        "api_url": args.api_url,
        "api_transport_retries": args.api_retries,
        "serving_options": serving,
        "first_stage": {
            "retrievers": ["zoekt_fielded_rrf_v1", "gemini_multiquery_rrf_v1"],
            "union": "rank-interleaved deduplicated bounded prefixes",
            "execution": "parallel" if args.parallel_first_stages else "serial",
            "coalesce_identical_requests": args.coalesce_first_stage_requests,
            "api_workers_per_retriever": args.first_stage_api_workers,
            "per_retriever_depth": args.per_retriever_depth,
            "field_weights": weights,
            "rrf_constant": args.rrf_constant,
            "fusion_depth": args.depth,
        },
        "candidate_pool": 2 * args.per_retriever_depth,
        "first_stage_request_counts": {
            "logical_queries": total_first_stage_logical_queries,
            "physical_api_requests": total_first_stage_physical_requests,
            "coalesced_api_hits": total_first_stage_coalesced_hits,
        },
        "second_stage": {
            "engine": "sqlite-fts5",
            "sqlite_version": sqlite3.sqlite_version,
            "tokenizer": "unicode61",
            "fields": [
                "humanized_path",
                "full_source_content",
                "query_matched_source_windows",
            ],
            "match_semantics": "OR over shared normalized query terms",
            "content_mode": "evidence-rrf",
            "matched_window_context_lines": 1,
            "matched_window_limit": 8,
            "fusion": "equal-weight reciprocal-rank fusion",
            "fusion_rrf_constant": args.evidence_rrf_constant,
            "first_stage_rank_channels": ["fielded", "multiquery"]
            if args.include_first_stage_ranks
            else [],
        },
        "fetch_workers": args.fetch_workers,
        "fetch_payload_bytes": total_fetch_bytes,
        "fetch_wall_ms": total_fetch_wall_ms,
        "fetch_request_ms": total_fetch_request_ms,
        "index": api_index_before,
        "retrieval_engine": None,
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
