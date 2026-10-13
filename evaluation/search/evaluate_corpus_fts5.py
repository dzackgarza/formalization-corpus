#!/usr/bin/env python3
"""Evaluate the remote corpus-wide SQLite FTS5 first-stage index."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

import evaluate
import provenance


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_REMOTE_DB = "/home/zack/lean-corpus/experiments/corpus-fts5-v2.sqlite"


def add_fts5_source_hierarchy(
    results: list[dict[str, Any]], *, rrf_constant: int
) -> list[dict[str, Any]]:
    """Fuse one FTS5 file-rank channel with its qrel-independent source rank.

    The construction is the same fixed source-hierarchy mechanism used by the
    accepted hybrid lexical reference, but it is applied only to the single
    corpus-wide FTS5 stream.  It therefore adds no retrieval request and reads
    neither qrels nor source contents.
    """

    if rrf_constant <= 0:
        raise ValueError("RRF constant must be positive")

    best_file_rank: dict[str, int] = {}
    for file_rank, item in enumerate(results, start=1):
        repository = str(item.get("Repository", ""))
        best_file_rank[repository] = min(
            best_file_rank.get(repository, file_rank), file_rank
        )
    source_order = sorted(best_file_rank, key=lambda repo: (best_file_rank[repo], repo))
    source_rank = {repository: rank for rank, repository in enumerate(source_order, start=1)}

    ranked: list[dict[str, Any]] = []
    for file_rank, original in enumerate(results, start=1):
        item = dict(original)
        repository = str(item.get("Repository", ""))
        repository_rank = source_rank[repository]
        score = (1.0 / (rrf_constant + file_rank)) + (
            1.0 / (rrf_constant + repository_rank)
        )
        item["Score"] = score
        item["CandidateSources"] = ["corpus-fts5"]
        item["CandidateSourceRanks"] = {
            "corpus-fts5": file_rank,
            "source-hierarchy": repository_rank,
        }
        item["CandidateUnionRank"] = file_rank
        item["FirstStageRankScore"] = score
        item["FirstStageRankEvidence"] = dict(item["CandidateSourceRanks"])
        item["SourceHierarchyRank"] = repository_rank
        item["SourceHierarchyScore"] = 1.0 / (rrf_constant + repository_rank)
        item["SourceHierarchyBestFileRanks"] = {"corpus-fts5": best_file_rank[repository]}
        ranked.append(item)
    ranked.sort(
        key=lambda item: (
            -float(item["FirstStageRankScore"]),
            int(item["CandidateUnionRank"]),
            str(item.get("Repository", "")),
            str(item.get("FileName", "")),
        )
    )
    return ranked


def remote_query_batch(
    requests: list[dict[str, Any]],
    *,
    host: str,
    remote_script: str,
    remote_db: str,
    mode: str,
    rrf_constant: int,
    timeout: float,
) -> dict[str, Any]:
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        host,
        "python3",
        remote_script,
        "query-batch",
        "--db",
        remote_db,
        "--mode",
        mode,
        "--rrf-constant",
        str(rrf_constant),
    ]
    try:
        proc = subprocess.run(
            command,
            input=json.dumps(requests).encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"remote FTS5 evaluation timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.decode("utf-8", "replace").strip()
            or f"remote FTS5 query exited {proc.returncode}"
        )
    return json.loads(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=pathlib.Path, default=evaluate.DEFAULT_GOLD)
    parser.add_argument("--host", default="zack@159.223.102.204")
    parser.add_argument(
        "--remote-script", default="/home/zack/lean-corpus/experiments/corpus_fts5.py"
    )
    parser.add_argument(
        "--remote-db", default=DEFAULT_REMOTE_DB
    )
    parser.add_argument(
        "--mode",
        choices=("bm25-all", "bm25-path-prefix-rrf", "fielded-rrf"),
        default="bm25-all",
    )
    parser.add_argument("--depth", type=int, default=200)
    parser.add_argument("--rrf-constant", type=int, default=60)
    parser.add_argument(
        "--source-hierarchy",
        action="store_true",
        help=(
            "add the fixed repository-rank channel derived from the returned "
            "FTS5 file ranks before scoring"
        ),
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    if args.depth <= 0 or args.rrf_constant <= 0 or args.timeout <= 0:
        print("ERROR: depth, RRF constant, and timeout must be positive", file=sys.stderr)
        return 2

    gold = evaluate.load_gold(args.gold)
    errors = evaluate.validate_gold(gold)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    requests: list[dict[str, Any]] = []
    for case in gold["cases"]:
        terms, _ = evaluate.normalized_query_terms(case["query"])
        requests.append({"id": case["id"], "terms": terms, "top": args.depth})

    try:
        remote = remote_query_batch(
            requests,
            host=args.host,
            remote_script=args.remote_script,
            remote_db=args.remote_db,
            mode=args.mode,
            rrf_constant=args.rrf_constant,
            timeout=args.timeout,
        )
    except (RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    by_id = {str(row["id"]): row for row in remote["responses"]}
    if set(by_id) != {case["id"] for case in gold["cases"]}:
        print("ERROR: remote FTS5 response IDs do not match gold cases", file=sys.stderr)
        return 2

    scored_cases: list[dict[str, Any]] = []
    for case in gold["cases"]:
        response = by_id[case["id"]]
        terms, _ = evaluate.normalized_query_terms(case["query"])
        results = list(response["results"])
        if args.source_hierarchy:
            results = add_fts5_source_hierarchy(
                results,
                rrf_constant=args.rrf_constant,
            )
        runtime = {
            "elapsed_ms": float(response["elapsed_ms"]),
            "payload_bytes": 0,
            "returned_files": len(results),
            "retrieval_queries": {"bm25-all": 1, "bm25-path-prefix-rrf": 2, "fielded-rrf": 3}[args.mode],
        }
        scored = evaluate.score_case(
            case,
            results,
            " SQLITE_FTS5 ".join(terms),
            runtime,
        )
        scored_cases.append(scored)
        print(
            f"{case['id']} owner={scored['first_owner_rank']} "
            f"relevant={scored['first_relevant_rank']} latency_ms={runtime['elapsed_ms']:.2f}",
            flush=True,
        )

    repo_state = provenance.repository_state(ROOT)
    variant = {
        "bm25-all": "sqlite_fts5_corpus_bm25_v1",
        "bm25-path-prefix-rrf": "sqlite_fts5_corpus_bm25_path_prefix_rrf_v1",
        "fielded-rrf": "sqlite_fts5_corpus_fielded_rrf_v1",
    }[args.mode]
    if args.source_hierarchy:
        variant = variant.removesuffix("_v1") + "_source_hierarchy_rrf_v1"
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_git_commit": repo_state["commit"],
        "repository_state": repo_state,
        "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
        "query_config_sha256": evaluate.query_config_sha256(),
        "serving_config_sha256": None,
        "variant": variant,
        "provider": "remote-sqlite-fts5",
        "index": remote["index"],
        "retrieval_engine": {
            "name": "SQLite FTS5",
            "mode": args.mode,
            "rrf_constant": args.rrf_constant if args.mode != "bm25-all" else None,
            "fields": ["source", "path", "content"],
            "tokenizer": remote["index"].get("tokenizer"),
            "sqlite_version": remote["index"].get("sqlite_version"),
            "source_rank_channel": (
                {
                    "name": "source-hierarchy",
                    "method": "repository best-file rank fused by equal-weight RRF",
                    "base_channels": ["corpus-fts5"],
                    "rrf_constant": args.rrf_constant,
                }
                if args.source_hierarchy
                else None
            ),
        },
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
