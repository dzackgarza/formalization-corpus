#!/usr/bin/env python3
"""Evaluate a fielded-Zoekt + corpus-FTS5 lexical candidate union.

This SQ2 experiment replaces the expensive frozen multi-query complement with
the independent corpus-wide SQLite FTS5/BM25 first stage.  Candidate generation
uses no relevance judgments: a bounded prefix from each first-stage ranking is
interleaved and deduplicated, then the existing candidate-content evidence
ranker combines path, full-content, local-content, and first-stage rank evidence.

The corpus FTS5 service is still an experimental server-local database, so the
reported latency is a component sum: public Zoekt API retrieval, server-local
SQLite query time, candidate-content fetch, and local reranking.  It does not
claim production network latency for an FTS5 serving endpoint that does not yet
exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any

import evaluate
import provenance
from evaluate_corpus_fts5 import DEFAULT_REMOTE_DB, remote_query_batch
from evaluate_fielded_fts5 import (
    ApiContentCache,
    fetch_candidate_contents,
    fts5_match_query,
    fts5_rerank,
)
from evaluate_fielded_lexical import retrieve_fielded


ROOT = pathlib.Path(__file__).resolve().parents[2]


def balanced_pair_union(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
    *,
    first_name: str,
    second_name: str,
    per_retriever_depth: int,
) -> list[dict[str, Any]]:
    """Interleave bounded ranked prefixes and preserve both source ranks."""

    if per_retriever_depth <= 0:
        raise ValueError("per-retriever depth must be positive")
    if not first_name or not second_name or first_name == second_name:
        raise ValueError("candidate source names must be distinct and nonempty")

    result: list[dict[str, Any]] = []
    positions: dict[tuple[str, str], int] = {}
    for rank in range(per_retriever_depth):
        for source, ranking in ((first_name, first), (second_name, second)):
            if rank >= len(ranking):
                continue
            original = ranking[rank]
            key = (str(original.get("Repository", "")), str(original.get("FileName", "")))
            existing = positions.get(key)
            if existing is None:
                item = dict(original)
                item["CandidateSources"] = [source]
                item["CandidateSourceRanks"] = {source: rank + 1}
                item["CandidateUnionRank"] = len(result) + 1
                positions[key] = len(result)
                result.append(item)
            else:
                item = result[existing]
                item["CandidateSources"].append(source)
                item["CandidateSourceRanks"][source] = rank + 1
    return result


def add_pair_rank_evidence(
    reranked: list[dict[str, Any]],
    *,
    channels: tuple[str, ...],
    rrf_constant: int,
) -> list[dict[str, Any]]:
    """Add named first-stage rank channels to evidence-RRF scores."""

    if rrf_constant <= 0:
        raise ValueError("RRF constant must be positive")
    allowed = set(channels)
    if not allowed or len(allowed) != len(channels):
        raise ValueError("first-stage channels must be nonempty and distinct")

    fused: list[dict[str, Any]] = []
    for original in reranked:
        item = dict(original)
        source_ranks = item.get("CandidateSourceRanks") or {}
        retrieval_score = sum(
            1.0 / (rrf_constant + int(rank))
            for source, rank in source_ranks.items()
            if source in allowed
        )
        item["Score"] = float(item.get("Score", 0.0)) + retrieval_score
        item["SecondStage"] = "sqlite_fts5_plus_first_stage_rank_rrf"
        item["FirstStageRankEvidence"] = dict(source_ranks)
        fused.append(item)
    fused.sort(
        key=lambda item: (
            -float(item["Score"]),
            int(item.get("CandidateUnionRank", 10**9)),
            str(item.get("Repository", "")),
            str(item.get("FileName", "")),
        )
    )
    return fused


def rank_by_pair_rank_evidence(
    candidates: list[dict[str, Any]],
    *,
    channels: tuple[str, ...],
    rrf_constant: int,
) -> list[dict[str, Any]]:
    """Rank a candidate union using only qrel-independent first-stage ranks."""

    if rrf_constant <= 0:
        raise ValueError("RRF constant must be positive")
    allowed = set(channels)
    if not allowed or len(allowed) != len(channels):
        raise ValueError("first-stage channels must be nonempty and distinct")

    ranked: list[dict[str, Any]] = []
    for original in candidates:
        item = dict(original)
        source_ranks = item.get("CandidateSourceRanks") or {}
        score = sum(
            1.0 / (rrf_constant + int(rank))
            for source, rank in source_ranks.items()
            if source in allowed
        )
        item["Score"] = score
        item["FirstStageRankScore"] = score
        item["FirstStageRankEvidence"] = dict(source_ranks)
        ranked.append(item)
    ranked.sort(
        key=lambda item: (
            -float(item["FirstStageRankScore"]),
            int(item.get("CandidateUnionRank", 10**9)),
            str(item.get("Repository", "")),
            str(item.get("FileName", "")),
        )
    )
    return ranked


def add_source_hierarchy_rank(
    candidates: list[dict[str, Any]],
    *,
    base_channels: tuple[str, ...],
    rrf_constant: int,
    channel_name: str = "source-hierarchy",
) -> list[dict[str, Any]]:
    """Add a repository-rank channel derived only from file-level ranks.

    Each repository is represented by its best file rank in every named base
    channel.  Those ranks are fused with equal-weight reciprocal-rank fusion,
    repositories are ranked by the resulting score, and that repository rank is
    attached to every candidate from the source.  No qrels or source contents
    enter the construction.
    """

    if rrf_constant <= 0:
        raise ValueError("RRF constant must be positive")
    allowed = set(base_channels)
    if not allowed or len(allowed) != len(base_channels):
        raise ValueError("base source-rank channels must be nonempty and distinct")
    if not channel_name or channel_name in allowed:
        raise ValueError("source-rank channel name must be distinct and nonempty")

    best_ranks: dict[str, dict[str, int]] = {}
    best_union_rank: dict[str, int] = {}
    for item in candidates:
        repository = str(item.get("Repository", ""))
        source_ranks = item.get("CandidateSourceRanks") or {}
        repository_ranks = best_ranks.setdefault(repository, {})
        for source, rank in source_ranks.items():
            if source not in allowed:
                continue
            numeric_rank = int(rank)
            previous = repository_ranks.get(source)
            if previous is None or numeric_rank < previous:
                repository_ranks[source] = numeric_rank
        union_rank = int(item.get("CandidateUnionRank", 10**9))
        best_union_rank[repository] = min(
            best_union_rank.get(repository, union_rank), union_rank
        )

    scored_sources: list[tuple[float, int, str]] = []
    for repository, ranks in best_ranks.items():
        score = sum(1.0 / (rrf_constant + rank) for rank in ranks.values())
        scored_sources.append((-score, best_union_rank[repository], repository))
    scored_sources.sort()
    repository_rank = {
        repository: rank
        for rank, (_, _, repository) in enumerate(scored_sources, start=1)
    }
    repository_score = {
        repository: -negative_score
        for negative_score, _, repository in scored_sources
    }

    enriched: list[dict[str, Any]] = []
    for original in candidates:
        item = dict(original)
        repository = str(item.get("Repository", ""))
        source_ranks = dict(item.get("CandidateSourceRanks") or {})
        source_ranks[channel_name] = repository_rank[repository]
        item["CandidateSourceRanks"] = source_ranks
        item["SourceHierarchyRank"] = repository_rank[repository]
        item["SourceHierarchyScore"] = repository_score[repository]
        item["SourceHierarchyBestFileRanks"] = dict(best_ranks[repository])
        enriched.append(item)
    return enriched


def prefilter_by_pair_rank_evidence(
    candidates: list[dict[str, Any]],
    *,
    channels: tuple[str, str],
    rrf_constant: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Bound second-stage work using only qrel-independent first-stage ranks."""

    if limit <= 0:
        raise ValueError("prefilter limit must be positive")
    return rank_by_pair_rank_evidence(
        candidates,
        channels=channels,
        rrf_constant=rrf_constant,
    )[:limit]


def retrieve_zoekt_first_stage(
    query: str,
    *,
    mode: str,
    timeout: float,
    api_url: str,
    serving: dict[str, Any],
    depth: int,
    rrf_constant: int,
    weights: dict[str, float],
    fields: tuple[str, ...],
    api_workers: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], str, dict[str, str]]:
    if mode == "fielded":
        results, runtime, field_queries = retrieve_fielded(
            query,
            timeout=timeout,
            provider="api",
            api_url=api_url,
            serving=serving,
            depth=depth,
            rrf_constant=rrf_constant,
            weights=weights,
            fields=fields,
            api_workers=api_workers,
        )
        return results, runtime, " FIELDED ".join(field_queries.values()), field_queries
    if mode == "lexical-v2":
        compiled = evaluate.compile_query(query, "frontend_lexical_v2")
        results, runtime = evaluate.api_search(compiled, timeout, api_url, serving)
        runtime = dict(runtime)
        runtime["retrieval_queries"] = 1
        runtime["physical_api_requests"] = 1
        return results, runtime, compiled, {}
    raise ValueError(f"unknown Zoekt first stage: {mode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=pathlib.Path, default=evaluate.DEFAULT_GOLD)
    parser.add_argument("--api-url", default=evaluate.DEFAULT_API_URL)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--depth", type=int, default=200)
    parser.add_argument("--per-retriever-depth", type=int, default=100)
    parser.add_argument("--content-rerank-depth", type=int)
    parser.add_argument("--fetch-workers", type=int, default=16)
    parser.add_argument(
        "--first-stage-api-workers",
        type=int,
        default=1,
        help="bounded concurrency across fielded Zoekt first-stage queries",
    )
    parser.add_argument(
        "--zoekt-first-stage",
        choices=("fielded", "lexical-v2"),
        default="fielded",
    )
    parser.add_argument("--rrf-constant", type=int, default=60)
    parser.add_argument("--evidence-rrf-constant", type=int, default=60)
    parser.add_argument(
        "--include-source-rank-channel",
        action="store_true",
        help=(
            "add one equal-weight repository-rank channel derived from each source's "
            "best ranks in the two independent first-stage retrievers"
        ),
    )
    parser.add_argument(
        "--second-stage-mode",
        choices=("evidence-rrf", "evidence-lines-rrf"),
        default="evidence-rrf",
        help="fixed deterministic FTS5 evidence representation used after candidate union",
    )
    parser.add_argument("--baseline-weight", type=float, default=2.0)
    parser.add_argument("--content-weight", type=float, default=1.0)
    parser.add_argument("--path-weight", type=float, default=1.0)
    parser.add_argument(
        "--zoekt-fields",
        default="baseline,content,path",
        help="comma-separated fielded Zoekt channels (baseline,content,path)",
    )
    parser.add_argument("--fts-host", default="zack@159.223.102.204")
    parser.add_argument(
        "--fts-remote-script",
        default="/home/zack/lean-corpus/experiments/corpus_fts5.py",
    )
    parser.add_argument(
        "--fts-remote-db",
        default=DEFAULT_REMOTE_DB,
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
        int(args.timeout),
    ) <= 0:
        print("ERROR: depths, workers, RRF constants, and timeout must be positive", file=sys.stderr)
        return 2
    if args.content_rerank_depth is not None and args.content_rerank_depth <= 0:
        print("ERROR: content rerank depth must be positive", file=sys.stderr)
        return 2
    weights = {
        "baseline": args.baseline_weight,
        "content": args.content_weight,
        "path": args.path_weight,
    }
    if any(weight <= 0 for weight in weights.values()):
        print("ERROR: first-stage field weights must be positive", file=sys.stderr)
        return 2
    zoekt_fields = tuple(field.strip() for field in args.zoekt_fields.split(",") if field.strip())
    allowed_fields = {"baseline", "content", "path"}
    if (
        not zoekt_fields
        or len(set(zoekt_fields)) != len(zoekt_fields)
        or not set(zoekt_fields) <= allowed_fields
    ):
        print(
            "ERROR: --zoekt-fields must be a nonempty unique subset of baseline,content,path",
            file=sys.stderr,
        )
        return 2
    if args.zoekt_first_stage != "fielded" and zoekt_fields != ("baseline", "content", "path"):
        print("ERROR: --zoekt-fields applies only to --zoekt-first-stage fielded", file=sys.stderr)
        return 2

    gold = evaluate.load_gold(args.gold)
    errors = evaluate.validate_gold(gold)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    fts_requests: list[dict[str, Any]] = []
    for case in gold["cases"]:
        terms, _ = evaluate.normalized_query_terms(case["query"])
        fts_requests.append({"id": case["id"], "terms": terms, "top": args.depth})
    try:
        fts_batch = remote_query_batch(
            fts_requests,
            host=args.fts_host,
            remote_script=args.fts_remote_script,
            remote_db=args.fts_remote_db,
            mode="bm25-all",
            rrf_constant=args.rrf_constant,
            timeout=max(args.timeout, 120.0),
        )
    except (RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    fts_by_id = {str(row["id"]): row for row in fts_batch["responses"]}
    expected_ids = {str(case["id"]) for case in gold["cases"]}
    if set(fts_by_id) != expected_ids:
        print("ERROR: remote FTS5 response IDs do not match gold cases", file=sys.stderr)
        return 2
    fts_index = fts_batch["index"]
    if not fts_index.get("complete"):
        print("ERROR: remote corpus FTS5 index is incomplete", file=sys.stderr)
        return 2

    serving = evaluate.serving_options(top=args.depth, whole=False)
    api_index_before = evaluate.api_index_fingerprint(args.api_url, args.timeout)
    if int(fts_index.get("document_count", -1)) != int(api_index_before.get("document_count", -2)):
        print(
            "ERROR: corpus FTS5 and canonical Zoekt document counts differ: "
            f"{fts_index.get('document_count')} != {api_index_before.get('document_count')}",
            file=sys.stderr,
        )
        return 2

    cache = ApiContentCache(api_url=args.api_url, timeout=args.timeout)
    scored_cases: list[dict[str, Any]] = []
    first_stage_scored_cases: list[dict[str, Any]] = []
    total_fetch_bytes = 0
    total_fetch_wall_ms = 0.0
    total_fetch_request_ms = 0.0
    zoekt_channel = "fielded" if args.zoekt_first_stage == "fielded" else "lexical-v2"

    for number, case in enumerate(gold["cases"], start=1):
        try:
            zoekt_results, zoekt_runtime, zoekt_compiled, field_queries = retrieve_zoekt_first_stage(
                case["query"],
                mode=args.zoekt_first_stage,
                timeout=args.timeout,
                api_url=args.api_url,
                serving=serving,
                depth=args.depth,
                rrf_constant=args.rrf_constant,
                weights=weights,
                fields=zoekt_fields,
                api_workers=args.first_stage_api_workers,
            )
            fts_response = fts_by_id[str(case["id"])]
            corpus_fts5 = list(fts_response["results"])
            candidates = balanced_pair_union(
                zoekt_results,
                corpus_fts5,
                first_name=zoekt_channel,
                second_name="corpus-fts5",
                per_retriever_depth=args.per_retriever_depth,
            )
            rank_channels = (zoekt_channel, "corpus-fts5")
            if args.include_source_rank_channel:
                candidates = add_source_hierarchy_rank(
                    candidates,
                    base_channels=rank_channels,
                    rrf_constant=args.evidence_rrf_constant,
                )
                rank_channels = (*rank_channels, "source-hierarchy")
            first_stage_ranking = rank_by_pair_rank_evidence(
                candidates,
                channels=rank_channels,
                rrf_constant=args.evidence_rrf_constant,
            )
            first_stage_runtime = {
                "elapsed_ms": float(zoekt_runtime["elapsed_ms"]) + float(fts_response["elapsed_ms"]),
                "payload_bytes": int(zoekt_runtime["payload_bytes"]),
                "returned_files": len(first_stage_ranking),
                "retrieval_queries": int(zoekt_runtime["retrieval_queries"]) + 1,
                "zoekt_api_requests": int(zoekt_runtime["physical_api_requests"]),
                "corpus_fts5_queries": 1,
            }
            first_stage_scored_cases.append(
                evaluate.score_case(
                    case,
                    first_stage_ranking,
                    f"{zoekt_compiled} CORPUS_FTS5_FIRST_STAGE_RRF",
                    first_stage_runtime,
                )
            )
            second_stage_candidates = candidates
            if args.content_rerank_depth is not None:
                second_stage_candidates = prefilter_by_pair_rank_evidence(
                    candidates,
                    channels=rank_channels,
                    rrf_constant=args.evidence_rrf_constant,
                    limit=args.content_rerank_depth,
                )
            contents, fetch_runtime = fetch_candidate_contents(
                second_stage_candidates,
                cache=cache,
                workers=args.fetch_workers,
            )
            rerank_started = time.perf_counter()
            reranked = fts5_rerank(
                case["query"],
                second_stage_candidates,
                contents,
                content_mode=args.second_stage_mode,
                evidence_rrf_constant=args.evidence_rrf_constant,
            )
            reranked = add_pair_rank_evidence(
                reranked,
                channels=rank_channels,
                rrf_constant=args.evidence_rrf_constant,
            )
            rerank_ms = (time.perf_counter() - rerank_started) * 1000
        except Exception as exc:
            print(f"ERROR {case['id']}: {exc}", file=sys.stderr)
            return 2

        total_fetch_bytes += int(fetch_runtime["fetch_payload_bytes"])
        total_fetch_wall_ms += float(fetch_runtime["fetch_wall_ms"])
        total_fetch_request_ms += float(fetch_runtime["fetch_request_ms"])
        fts_elapsed_ms = float(fts_response["elapsed_ms"])
        runtime = {
            "elapsed_ms": (
                float(zoekt_runtime["elapsed_ms"])
                + fts_elapsed_ms
                + float(fetch_runtime["fetch_wall_ms"])
                + rerank_ms
            ),
            "zoekt_retrieval_ms": float(zoekt_runtime["elapsed_ms"]),
            "corpus_fts5_retrieval_ms": fts_elapsed_ms,
            "fetch_wall_ms": float(fetch_runtime["fetch_wall_ms"]),
            "fetch_request_ms": float(fetch_runtime["fetch_request_ms"]),
            "rerank_ms": rerank_ms,
            "payload_bytes": int(zoekt_runtime["payload_bytes"])
            + int(fetch_runtime["fetch_payload_bytes"]),
            "returned_files": len(reranked),
            "retrieval_queries": int(zoekt_runtime["retrieval_queries"]) + 1,
            "zoekt_api_requests": int(zoekt_runtime["physical_api_requests"]),
            "corpus_fts5_queries": 1,
            "content_fetches": len(second_stage_candidates),
        }
        scored = evaluate.score_case(
            case,
            reranked,
            f"{zoekt_compiled} CORPUS_FTS5_UNION",
            runtime,
        )
        scored["zoekt_first_stage"] = args.zoekt_first_stage
        scored["zoekt_query"] = zoekt_compiled
        if field_queries:
            scored["field_queries"] = field_queries
        scored["candidate_union_size"] = len(candidates)
        scored["content_rerank_size"] = len(second_stage_candidates)
        scored["corpus_fts5_elapsed_ms"] = fts_elapsed_ms
        scored["second_stage_match_query"] = fts5_match_query(case["query"])
        scored_cases.append(scored)
        print(
            f"{number:02d}/{len(gold['cases'])} {case['id']} "
            f"candidates={len(candidates)} rerank={len(second_stage_candidates)} "
            f"owner={scored['first_owner_rank']} "
            f"relevant={scored['first_relevant_rank']}",
            flush=True,
        )

    api_index_after = evaluate.api_index_fingerprint(args.api_url, args.timeout)
    if api_index_after != api_index_before:
        print("ERROR: published API index changed during evaluation", file=sys.stderr)
        return 2

    repo_state = provenance.repository_state(ROOT)
    if args.zoekt_first_stage == "fielded":
        if zoekt_fields == ("baseline", "content", "path"):
            zoekt_variant = "zoekt_fielded_rrf_v1"
            variant_prefix = "fielded"
        else:
            field_suffix = "_".join(zoekt_fields)
            zoekt_variant = f"zoekt_fielded_{field_suffix}_rrf_v1"
            variant_prefix = f"fielded_{field_suffix}"
    else:
        zoekt_variant = "frontend_lexical_v2"
        variant_prefix = "lexical_v2"
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_git_commit": repo_state["commit"],
        "repository_state": repo_state,
        "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
        "query_config_sha256": evaluate.query_config_sha256(),
        "serving_config_sha256": evaluate.serving_config_sha256(),
        "variant": f"{variant_prefix}_corpus_fts5_union_"
        + ("source_rank_" if args.include_source_rank_channel else "")
        + (
            (
                "rank_prefilter_evidence_lines_rrf_v1"
                if args.second_stage_mode == "evidence-lines-rrf"
                else "rank_prefilter_evidence_rrf_v1"
            )
            if args.content_rerank_depth is not None
            else (
                "evidence_lines_rank_rrf_v1"
                if args.second_stage_mode == "evidence-lines-rrf"
                else "evidence_rank_rrf_v1"
            )
        ),
        "provider": "api+remote-sqlite-fts5",
        "api_url": args.api_url,
        "serving_options": serving,
        "first_stage": {
            "retrievers": [zoekt_variant, "sqlite_fts5_corpus_bm25_v1"],
            "zoekt_first_stage": args.zoekt_first_stage,
            "zoekt_fields": list(zoekt_fields) if args.zoekt_first_stage == "fielded" else None,
            "union": "rank-interleaved deduplicated bounded prefixes",
            "per_retriever_depth": args.per_retriever_depth,
            "field_weights": weights,
            "zoekt_api_workers": args.first_stage_api_workers,
            "rrf_constant": args.rrf_constant,
            "fusion_depth": args.depth,
            "source_rank_channel": (
                {
                    "name": "source-hierarchy",
                    "method": "repository best-file ranks fused by equal-weight RRF",
                    "base_channels": [zoekt_channel, "corpus-fts5"],
                    "rrf_constant": args.evidence_rrf_constant,
                }
                if args.include_source_rank_channel
                else None
            ),
        },
        "candidate_pool": 2 * args.per_retriever_depth,
        "second_stage": {
            "engine": "sqlite-fts5",
            "sqlite_version": sqlite3.sqlite_version,
            "tokenizer": "unicode61",
            "fields": [
                "humanized_path",
                "full_source_content",
                "query_matched_source_windows",
                *(
                    ["query_matched_source_lines"]
                    if args.second_stage_mode == "evidence-lines-rrf"
                    else []
                ),
            ],
            "content_mode": args.second_stage_mode,
            "matched_line_limit": 12
            if args.second_stage_mode == "evidence-lines-rrf"
            else None,
            "fusion": "equal-weight reciprocal-rank fusion",
            "fusion_rrf_constant": args.evidence_rrf_constant,
            "first_stage_rank_channels": [
                zoekt_channel,
                "corpus-fts5",
                *(["source-hierarchy"] if args.include_source_rank_channel else []),
            ],
            "prefilter": (
                {
                    "method": "first-stage-rank-rrf",
                    "limit": args.content_rerank_depth,
                    "rrf_constant": args.evidence_rrf_constant,
                }
                if args.content_rerank_depth is not None
                else None
            ),
        },
        "latency_scope": (
            "component sum: public Zoekt API + server-local corpus FTS5 query + "
            "candidate fetch + local rerank; excludes an unimplemented FTS5 network serving path"
        ),
        "fetch_workers": args.fetch_workers,
        "fetch_payload_bytes": total_fetch_bytes,
        "fetch_wall_ms": total_fetch_wall_ms,
        "fetch_request_ms": total_fetch_request_ms,
        "index": {
            "zoekt": api_index_before,
            "corpus_fts5": fts_index,
        },
        "retrieval_engine": {
            "corpus_fts5": {
                "name": "SQLite FTS5",
                "mode": "bm25-all",
                "tokenizer": fts_index.get("tokenizer"),
                "sqlite_version": fts_index.get("sqlite_version"),
            }
        },
        "result_role_state": evaluate.file_role_index().fingerprint(),
        "metrics": evaluate.aggregate(scored_cases),
        "metrics_by_tag": evaluate.by_tag(scored_cases),
        "first_stage_metrics": evaluate.aggregate(first_stage_scored_cases),
        "first_stage_metrics_by_tag": evaluate.by_tag(first_stage_scored_cases),
        "first_stage_cases": first_stage_scored_cases,
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
