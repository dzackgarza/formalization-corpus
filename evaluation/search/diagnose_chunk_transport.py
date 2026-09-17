#!/usr/bin/env python3
"""Paired same-index diagnostic for rank-only Zoekt transport.

The SQ2 first stage only consumes ranked file identities and scores; source
snippets are fetched separately for second-stage scoring.  This diagnostic
tests whether asking Zoekt to omit ``ChunkMatches`` changes the ordered first-
stage response when every other request option and the remote index are held
fixed.

Every unique request issued by the current fielded and frozen-multiquery first
stages is sent once with chunks and once without chunks.  Any first-pass
mismatch is immediately repeated twice in both modes so a stable option effect
can be distinguished from ordinary tie/order variation in the live service.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import statistics
import time
from datetime import datetime, timezone
from typing import Any

import evaluate
import provenance
from evaluate_fielded_lexical import compile_field_queries
from evaluate_multiquery import DEFAULT_EXPANSIONS, load_expansion_queries


def unique_first_stage_queries(
    gold: dict[str, Any], expansions: dict[str, list[str]]
) -> tuple[list[str], dict[str, list[dict[str, str]]]]:
    """Return the deterministic unique request population and its provenance."""

    origins: dict[str, list[dict[str, str]]] = {}
    for case in gold["cases"]:
        case_id = str(case["id"])
        for field, query in compile_field_queries(case["query"]).items():
            origins.setdefault(query, []).append(
                {"case": case_id, "kind": f"fielded:{field}"}
            )

        seen: set[str] = set()
        for formulation in [case["query"], *expansions[case_id]]:
            query = evaluate.compile_query(formulation, "normalized_path_content_v1")
            if query in seen:
                continue
            seen.add(query)
            origins.setdefault(query, []).append(
                {
                    "case": case_id,
                    "kind": "multiquery",
                    "formulation": formulation,
                }
            )
    return list(origins), origins


def ordered_rows(results: list[dict[str, Any]]) -> list[tuple[str, str, float]]:
    return [
        (
            str(item.get("Repository", "")),
            str(item.get("FileName", "")),
            float(item.get("Score", 0)),
        )
        for item in results
    ]


def compare_rankings(
    chunked: list[tuple[str, str, float]],
    chunkless: list[tuple[str, str, float]],
) -> dict[str, Any]:
    chunked_ids = [(repo, path) for repo, path, _ in chunked]
    chunkless_ids = [(repo, path) for repo, path, _ in chunkless]
    identities_equal = chunked_ids == chunkless_ids
    scores_equal = chunked == chunkless
    first_difference = None
    if not scores_equal:
        common = min(len(chunked), len(chunkless))
        first_difference = next(
            (index + 1 for index in range(common) if chunked[index] != chunkless[index]),
            common + 1 if len(chunked) != len(chunkless) else None,
        )
    return {
        "identities_equal": identities_equal,
        "scores_equal": scores_equal,
        "first_difference_rank": first_difference,
    }


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=pathlib.Path, default=evaluate.DEFAULT_GOLD)
    parser.add_argument("--expansions", type=pathlib.Path, default=DEFAULT_EXPANSIONS)
    parser.add_argument("--api-url", default=evaluate.DEFAULT_API_URL)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--depth", type=int, default=200)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--api-retries", type=int, default=2)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()

    if args.depth <= 0 or args.workers <= 0 or args.api_retries < 0:
        parser.error("depth/workers must be positive and api-retries nonnegative")

    gold = evaluate.load_gold(args.gold)
    expansion_data, expansions = load_expansion_queries(args.expansions, gold)
    queries, origins = unique_first_stage_queries(gold, expansions)
    serving = evaluate.serving_options(top=args.depth, whole=False)

    def run_one(query: str, chunks: bool) -> tuple[list[tuple[str, str, float]], dict[str, Any]]:
        results, runtime = evaluate.api_search(
            query,
            args.timeout,
            args.api_url,
            {**serving, "chunk_matches": chunks},
            retries=args.api_retries,
        )
        return ordered_rows(results), runtime

    def pair(number: int, query: str) -> dict[str, Any]:
        chunked, chunked_runtime = run_one(query, True)
        chunkless, chunkless_runtime = run_one(query, False)
        comparison = compare_rankings(chunked, chunkless)
        return {
            "number": number,
            "query": query,
            "chunked": chunked,
            "chunkless": chunkless,
            "chunked_runtime": chunked_runtime,
            "chunkless_runtime": chunkless_runtime,
            **comparison,
        }

    index_before = evaluate.api_index_fingerprint(args.api_url, args.timeout)
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(pair, number, query): number
            for number, query in enumerate(queries, start=1)
        }
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            rows.append(future.result())
            completed += 1
            if completed % 20 == 0 or completed == len(queries):
                print(f"paired {completed}/{len(queries)}", flush=True)
    rows.sort(key=lambda row: row["number"])

    index_after = evaluate.api_index_fingerprint(args.api_url, args.timeout)
    if index_after != index_before:
        raise RuntimeError("published API index changed during paired diagnostic")

    mismatches: list[dict[str, Any]] = []
    for row in rows:
        if row["scores_equal"]:
            continue
        repeats = []
        for _ in range(2):
            chunked, _ = run_one(row["query"], True)
            chunkless, _ = run_one(row["query"], False)
            repeats.append(
                {
                    **compare_rankings(chunked, chunkless),
                    "chunked_matches_first_chunked": chunked == row["chunked"],
                    "chunkless_matches_first_chunkless": chunkless == row["chunkless"],
                }
            )
        mismatches.append(
            {
                "number": row["number"],
                "query": row["query"],
                "origins": origins[row["query"]],
                "identities_equal": row["identities_equal"],
                "scores_equal": row["scores_equal"],
                "first_difference_rank": row["first_difference_rank"],
                "chunked_count": len(row["chunked"]),
                "chunkless_count": len(row["chunkless"]),
                "chunked_head": [list(item) for item in row["chunked"][:20]],
                "chunkless_head": [list(item) for item in row["chunkless"][:20]],
                "repeats": repeats,
            }
        )

    chunked_payloads = [float(row["chunked_runtime"]["payload_bytes"]) for row in rows]
    chunkless_payloads = [float(row["chunkless_runtime"]["payload_bytes"]) for row in rows]
    chunked_latencies = [float(row["chunked_runtime"]["elapsed_ms"]) for row in rows]
    chunkless_latencies = [float(row["chunkless_runtime"]["elapsed_ms"]) for row in rows]
    chunked_payload = sum(chunked_payloads)
    chunkless_payload = sum(chunkless_payloads)
    repo_state = provenance.repository_state(evaluate.ROOT)
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_git_commit": repo_state["commit"],
        "repository_state": repo_state,
        "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
        "query_config_sha256": evaluate.query_config_sha256(),
        "serving_config_sha256": evaluate.serving_config_sha256(),
        "result_role_state": evaluate.file_role_index().fingerprint(),
        "variant": "paired_first_stage_chunk_transport_v1",
        "provider": "api",
        "api_url": args.api_url,
        "index": index_before,
        "serving_options": serving,
        "expansion_model": expansion_data.get("model"),
        "expansion_prompt_version": expansion_data.get("prompt_version"),
        "expansions_sha256": hashlib.sha256(args.expansions.read_bytes()).hexdigest(),
        "diagnostic": {
            "workers": args.workers,
            "api_retries": args.api_retries,
            "unique_queries": len(queries),
            "paired_requests": 2 * len(queries),
            "repeat_requests": 4 * len(mismatches),
            "wall_ms": (time.perf_counter() - started) * 1000,
        },
        "metrics": {
            "unique_first_stage_queries": len(queries),
            "ordered_identity_mismatches": sum(
                not row["identities_equal"] for row in rows
            ),
            "ordered_score_mismatches": sum(not row["scores_equal"] for row in rows),
            "chunked_payload_bytes": chunked_payload,
            "chunkless_payload_bytes": chunkless_payload,
            "payload_reduction_fraction": (
                0.0 if chunked_payload == 0 else 1.0 - chunkless_payload / chunked_payload
            ),
            "chunked_latency_ms_mean": statistics.fmean(chunked_latencies),
            "chunkless_latency_ms_mean": statistics.fmean(chunkless_latencies),
            "chunked_latency_ms_p50": percentile(chunked_latencies, 0.50),
            "chunkless_latency_ms_p50": percentile(chunkless_latencies, 0.50),
            "chunked_latency_ms_p95": percentile(chunked_latencies, 0.95),
            "chunkless_latency_ms_p95": percentile(chunkless_latencies, 0.95),
        },
        "mismatches": mismatches,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["metrics"], indent=2, sort_keys=True))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
