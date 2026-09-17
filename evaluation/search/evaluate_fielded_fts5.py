#!/usr/bin/env python3
"""Rerank field-separated Zoekt candidates with SQLite FTS5 BM25.

This SQ2 experiment deliberately keeps candidate generation unchanged: the
three-channel Zoekt fielded retriever supplies a high-recall pool, then SQLite's
mature FTS5 implementation ranks that finite pool from two explicit fields:
humanized source path and full source text.  No relevance judgments enter the
ranker and no weights are tuned; both fields use FTS5's default BM25 weight.

Source caches may be dehydrated, so candidate text is read back from the exact
canonical public Zoekt shard through the search API.  The API index fingerprint
is checked before and after the complete evaluation.  A second experimental
content mode scores only bounded source windows around normalized query-term
matches; this tests whether local evidence avoids the broad-file bias observed
with full-file BM25 without changing candidate generation.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import evaluate
import provenance
from evaluate_fielded_lexical import retrieve_fielded
from evaluate_rerank import humanize_path

ROOT = pathlib.Path(__file__).resolve().parents[2]


def fts5_match_query(text: str) -> str:
    """Return a disjunctive FTS5 query from the shared normalized terms."""
    terms, _ = evaluate.normalized_query_terms(text)
    if not terms:
        return '"__formalization_corpus_no_terms__"'
    escaped = [term.replace('"', '""') for term in terms]
    return " OR ".join(f'"{term}"' for term in escaped)


def query_matched_windows(
    text: str,
    content: str,
    *,
    context_lines: int = 1,
    max_windows: int = 8,
) -> str:
    """Return bounded source windows around the strongest normalized-term hits.

    Anchors are ranked only by how many distinct normalized query terms occur on
    the line, with source order as the deterministic tiebreak.  Overlapping
    windows are merged implicitly by retaining each source line at most once.
    No relevance judgments enter this projection.
    """
    terms, _ = evaluate.normalized_query_terms(text)
    if not terms or not content:
        return ""
    folded_terms = [term.casefold() for term in terms]
    lines = content.splitlines()
    anchors: list[tuple[int, int]] = []
    for line_number, line in enumerate(lines):
        folded = line.casefold()
        matched = sum(term in folded for term in folded_terms)
        if matched:
            anchors.append((-matched, line_number))
    anchors.sort()

    selected: set[int] = set()
    for _, line_number in anchors[:max_windows]:
        start = max(0, line_number - context_lines)
        stop = min(len(lines), line_number + context_lines + 1)
        selected.update(range(start, stop))
    return "\n".join(lines[index] for index in sorted(selected))


def fts5_rerank(
    text: str,
    candidates: list[dict[str, Any]],
    contents: dict[tuple[str, str], str],
    *,
    content_mode: str = "full",
    evidence_rrf_constant: int = 60,
) -> list[dict[str, Any]]:
    """Rank a fixed candidate list with deterministic FTS5 evidence channels."""
    if content_mode not in {"full", "matched-windows", "evidence-rrf"}:
        raise ValueError(f"unsupported FTS5 content mode: {content_mode}")
    if evidence_rrf_constant <= 0:
        raise ValueError("evidence RRF constant must be positive")

    if content_mode == "evidence-rrf":
        return fts5_evidence_rrf_rerank(
            text,
            candidates,
            contents,
            rrf_constant=evidence_rrf_constant,
        )

    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE VIRTUAL TABLE docs USING fts5(path, content, tokenize='unicode61')")
        for rowid, item in enumerate(candidates, start=1):
            key = (item.get("Repository", ""), item.get("FileName", ""))
            content = contents.get(key, "")
            if content_mode == "matched-windows":
                content = query_matched_windows(text, content)
            db.execute(
                "INSERT INTO docs(rowid, path, content) VALUES (?, ?, ?)",
                (rowid, humanize_path(key[1]), content),
            )
        ranked_rows = db.execute(
            "SELECT rowid, bm25(docs) AS score FROM docs WHERE docs MATCH ? "
            "ORDER BY score ASC, rowid ASC",
            (fts5_match_query(text),),
        ).fetchall()
    finally:
        db.close()

    seen = set()
    ranked: list[dict[str, Any]] = []
    for rowid, score in ranked_rows:
        item = dict(candidates[int(rowid) - 1])
        # Evaluator convention is larger-is-better. FTS5 BM25 is smaller-is-better.
        item["Score"] = -float(score)
        item["SecondStage"] = f"sqlite_fts5_bm25_{content_mode}"
        ranked.append(item)
        seen.add(int(rowid))
    for rowid, original in enumerate(candidates, start=1):
        if rowid in seen:
            continue
        item = dict(original)
        item["Score"] = float("-inf")
        item["SecondStage"] = "sqlite_fts5_unmatched"
        ranked.append(item)
    return ranked


def fts5_evidence_rrf_rerank(
    text: str,
    candidates: list[dict[str, Any]],
    contents: dict[tuple[str, str], str],
    *,
    rrf_constant: int = 60,
) -> list[dict[str, Any]]:
    """Fuse path/identifier, broad-content, and local-content FTS5 rankings.

    Each channel is independently ranked by SQLite FTS5 BM25 and the resulting
    ranks are combined with equal-weight reciprocal-rank fusion.  This keeps the
    broad-file evidence that helped exact-name queries, adds bounded local
    evidence, and gives path/identifier evidence an explicit channel without
    calibrating incomparable BM25 scores or tuning field weights against qrels.
    """
    if rrf_constant <= 0:
        raise ValueError("RRF constant must be positive")

    db = sqlite3.connect(":memory:")
    try:
        for table in ("path_docs", "full_docs", "local_docs"):
            db.execute(
                f"CREATE VIRTUAL TABLE {table} USING fts5(text, tokenize='unicode61')"
            )
        for rowid, item in enumerate(candidates, start=1):
            key = (item.get("Repository", ""), item.get("FileName", ""))
            content = contents.get(key, "")
            values = {
                "path_docs": humanize_path(key[1]),
                "full_docs": content,
                "local_docs": query_matched_windows(text, content),
            }
            for table, value in values.items():
                db.execute(
                    f"INSERT INTO {table}(rowid, text) VALUES (?, ?)",
                    (rowid, value),
                )

        match_query = fts5_match_query(text)
        scores: dict[int, float] = {}
        evidence: dict[int, list[str]] = {}
        channel_names = {
            "path_docs": "path",
            "full_docs": "full-content",
            "local_docs": "matched-windows",
        }
        for table, channel in channel_names.items():
            rows = db.execute(
                f"SELECT rowid, bm25({table}) AS score FROM {table} "
                f"WHERE {table} MATCH ? ORDER BY score ASC, rowid ASC",
                (match_query,),
            ).fetchall()
            for rank, (rowid, _) in enumerate(rows, start=1):
                numeric_rowid = int(rowid)
                scores[numeric_rowid] = scores.get(numeric_rowid, 0.0) + 1.0 / (
                    rrf_constant + rank
                )
                evidence.setdefault(numeric_rowid, []).append(channel)
    finally:
        db.close()

    ranked: list[dict[str, Any]] = []
    for rowid, original in enumerate(candidates, start=1):
        item = dict(original)
        item["Score"] = scores.get(rowid, 0.0)
        item["SecondStage"] = "sqlite_fts5_evidence_rrf"
        item["SecondStageEvidence"] = evidence.get(rowid, [])
        item["SecondStageOriginalRank"] = rowid
        ranked.append(item)
    ranked.sort(
        key=lambda item: (
            -float(item["Score"]),
            int(item["SecondStageOriginalRank"]),
        )
    )
    return ranked


def _api_file_content_uncached(
    repository: str,
    file_name: str,
    *,
    api_url: str,
    timeout: float,
) -> tuple[str, int, float]:
    repo_pattern = evaluate.quoted_pattern(evaluate.regex_escape(repository))
    file_pattern = evaluate.quoted_pattern(evaluate.regex_escape(file_name))
    query = f"repo:{repo_pattern} file:{file_pattern}"
    payload = json.dumps(
        {
            "Q": query,
            "Opts": {"MaxDocDisplayCount": 2, "ChunkMatches": True, "Whole": True},
        }
    )
    started = time.perf_counter()
    proc = subprocess.run(
        [
            "curl", "-fsS", "--max-time", str(max(1, int(timeout))), api_url,
            "-H", "Content-Type: application/json", "-d", payload,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout + 2,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.decode(errors="replace").strip()
            or f"curl exited {proc.returncode} fetching {repository}:{file_name}"
        )
    response = json.loads(proc.stdout)
    files = (response.get("Result") or {}).get("Files") or []
    item = next(
        (
            row
            for row in files
            if row.get("Repository") == repository and row.get("FileName") == file_name
        ),
        None,
    )
    if item is None:
        raise RuntimeError(f"canonical index did not return {repository}:{file_name}")
    content = base64.b64decode(item.get("Content") or "").decode(errors="replace")
    return content, len(proc.stdout), elapsed_ms


class ApiContentCache:
    def __init__(self, *, api_url: str, timeout: float) -> None:
        self.api_url = api_url
        self.timeout = timeout
        self._lock = threading.Lock()
        self._values: dict[tuple[str, str], str] = {}

    def fetch(self, item: dict[str, Any]) -> tuple[tuple[str, str], str, int, float]:
        key = (item.get("Repository", ""), item.get("FileName", ""))
        with self._lock:
            cached = self._values.get(key)
        if cached is not None:
            return key, cached, 0, 0.0
        content, payload_bytes, elapsed_ms = _api_file_content_uncached(
            key[0], key[1], api_url=self.api_url, timeout=self.timeout
        )
        with self._lock:
            existing = self._values.setdefault(key, content)
        return key, existing, payload_bytes, elapsed_ms


def fetch_candidate_contents(
    candidates: list[dict[str, Any]],
    *,
    cache: ApiContentCache,
    workers: int,
) -> tuple[dict[tuple[str, str], str], dict[str, Any]]:
    started = time.perf_counter()
    contents: dict[tuple[str, str], str] = {}
    payload_bytes = 0
    request_ms = 0.0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for key, content, size, elapsed_ms in pool.map(cache.fetch, candidates):
            contents[key] = content
            payload_bytes += size
            request_ms += elapsed_ms
    return contents, {
        "fetch_wall_ms": (time.perf_counter() - started) * 1000,
        "fetch_request_ms": request_ms,
        "fetch_payload_bytes": payload_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=pathlib.Path, default=evaluate.DEFAULT_GOLD)
    parser.add_argument("--api-url", default=evaluate.DEFAULT_API_URL)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--depth", type=int, default=200)
    parser.add_argument("--candidate-pool", type=int, default=20)
    parser.add_argument("--fetch-workers", type=int, default=8)
    parser.add_argument(
        "--content-mode",
        choices=("full", "matched-windows", "evidence-rrf"),
        default="full",
    )
    parser.add_argument("--evidence-rrf-constant", type=int, default=60)
    parser.add_argument("--rrf-constant", type=int, default=60)
    parser.add_argument("--baseline-weight", type=float, default=2.0)
    parser.add_argument("--content-weight", type=float, default=1.0)
    parser.add_argument("--path-weight", type=float, default=1.0)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    if (
        args.depth <= 0
        or args.candidate_pool <= 0
        or args.fetch_workers <= 0
        or args.evidence_rrf_constant <= 0
    ):
        print(
            "ERROR: depth, candidate-pool, fetch-workers, and evidence-rrf-constant "
            "must be positive",
            file=sys.stderr,
        )
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

    serving = evaluate.serving_options(top=args.depth, whole=False)
    api_index_before = evaluate.api_index_fingerprint(args.api_url, args.timeout)
    cache = ApiContentCache(api_url=args.api_url, timeout=args.timeout)
    scored_cases: list[dict[str, Any]] = []
    total_fetch_bytes = 0
    total_fetch_wall_ms = 0.0
    total_fetch_request_ms = 0.0

    for number, case in enumerate(gold["cases"], start=1):
        try:
            first_stage, retrieval_runtime, queries = retrieve_fielded(
                case["query"],
                timeout=args.timeout,
                provider="api",
                api_url=args.api_url,
                serving=serving,
                depth=args.depth,
                rrf_constant=args.rrf_constant,
                weights=weights,
            )
            candidates = first_stage[: args.candidate_pool]
            contents, fetch_runtime = fetch_candidate_contents(
                candidates, cache=cache, workers=args.fetch_workers
            )
            rerank_started = time.perf_counter()
            reranked = fts5_rerank(
                case["query"],
                candidates,
                contents,
                content_mode=args.content_mode,
                evidence_rrf_constant=args.evidence_rrf_constant,
            )
            rerank_ms = (time.perf_counter() - rerank_started) * 1000
        except Exception as exc:
            print(f"ERROR {case['id']}: {exc}", file=sys.stderr)
            return 2

        total_fetch_bytes += int(fetch_runtime["fetch_payload_bytes"])
        total_fetch_wall_ms += float(fetch_runtime["fetch_wall_ms"])
        total_fetch_request_ms += float(fetch_runtime["fetch_request_ms"])
        runtime = {
            "elapsed_ms": retrieval_runtime["elapsed_ms"] + fetch_runtime["fetch_wall_ms"] + rerank_ms,
            "retrieval_ms": retrieval_runtime["elapsed_ms"],
            "fetch_wall_ms": fetch_runtime["fetch_wall_ms"],
            "fetch_request_ms": fetch_runtime["fetch_request_ms"],
            "rerank_ms": rerank_ms,
            "payload_bytes": retrieval_runtime["payload_bytes"] + fetch_runtime["fetch_payload_bytes"],
            "returned_files": len(reranked),
            "retrieval_queries": retrieval_runtime["retrieval_queries"],
            "content_fetches": len(candidates),
        }
        scored = evaluate.score_case(
            case,
            reranked,
            " FIELDED_RRF_FTS5_BM25 ".join(queries.values()),
            runtime,
        )
        scored["field_queries"] = queries
        scored["second_stage_match_query"] = fts5_match_query(case["query"])
        scored_cases.append(scored)
        print(
            f"{number:02d}/{len(gold['cases'])} {case['id']} "
            f"owner={scored['first_owner_rank']} relevant={scored['first_relevant_rank']}",
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
        "variant": (
            "zoekt_fielded_rrf_fts5_bm25_v1"
            if args.content_mode == "full"
            else (
                "zoekt_fielded_rrf_fts5_matched_windows_v1"
                if args.content_mode == "matched-windows"
                else "zoekt_fielded_rrf_fts5_evidence_rrf_v1"
            )
        ),
        "provider": "api+sqlite-fts5",
        "api_url": args.api_url,
        "serving_options": serving,
        "first_stage_field_weights": weights,
        "rrf_constant": args.rrf_constant,
        "fusion_depth": args.depth,
        "candidate_pool": args.candidate_pool,
        "second_stage": {
            "engine": "sqlite-fts5",
            "sqlite_version": sqlite3.sqlite_version,
            "tokenizer": "unicode61",
            "fields": [
                *(
                    ["humanized_path", "full_source_content", "query_matched_source_windows"]
                    if args.content_mode == "evidence-rrf"
                    else [
                        "humanized_path",
                        "full_source_content"
                        if args.content_mode == "full"
                        else "query_matched_source_windows",
                    ]
                ),
            ],
            "field_weights": None if args.content_mode == "evidence-rrf" else [1.0, 1.0],
            "match_semantics": "OR over shared normalized query terms",
            "content_mode": args.content_mode,
            "matched_window_context_lines": 1
            if args.content_mode in {"matched-windows", "evidence-rrf"}
            else None,
            "matched_window_limit": 8
            if args.content_mode in {"matched-windows", "evidence-rrf"}
            else None,
            "fusion": "equal-weight reciprocal-rank fusion"
            if args.content_mode == "evidence-rrf"
            else None,
            "fusion_rrf_constant": args.evidence_rrf_constant
            if args.content_mode == "evidence-rrf"
            else None,
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
