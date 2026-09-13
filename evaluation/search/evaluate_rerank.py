#!/usr/bin/env python3
"""Evaluate semantic reranking over the frozen multi-query RRF candidate pool.

No relevance judgments are sent to the reranker.  Candidate documents are a
fixed projection of source metadata, file path, and a bounded non-import source
excerpt.  The default model/candidate depth are experimental choices recorded in
the output report; this script does not alter production search behavior.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

import evaluate
from evaluate_multiquery import (
    DEFAULT_EXPANSIONS,
    load_expansion_queries,
    retrieve_multiquery,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
COHERE_RERANK_URL = "https://api.cohere.com/v2/rerank"
DOCUMENT_PROJECTION_VERSION = 1


def source_rows() -> dict[str, dict[str, str]]:
    with (ROOT / "sources.tsv").open(newline="") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        return {pathlib.PurePosixPath(row["directory"]).name: row for row in rows}


def public_source_name(row: dict[str, str]) -> str:
    url = row["url"].rstrip("/").removesuffix(".git")
    if "github.com/" in url:
        return url.split("github.com/", 1)[1]
    if "gitlab" in url and "://" in url:
        return url.split("/", 3)[-1]
    if row["proof_assistant"] == "mizar":
        return "Mizar Mathematical Library"
    return pathlib.PurePosixPath(row["directory"]).name.replace("__", "/")


def humanize_path(path: str) -> str:
    text = path.replace("/", " / ").replace("_", " ").replace("-", " ")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def bounded_excerpt(path: pathlib.Path, *, max_lines: int, max_chars: int) -> str:
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return ""
    kept: list[str] = []
    chars = 0
    for line in text.splitlines()[:max_lines]:
        stripped = line.lstrip()
        if stripped.startswith(("import ", "public import ")):
            continue
        remaining = max_chars - chars
        if remaining <= 0:
            break
        piece = line[:remaining]
        kept.append(piece)
        chars += len(piece) + 1
    return "\n".join(kept)[:max_chars]


def rerank_document(
    result: dict[str, Any],
    rows: dict[str, dict[str, str]],
    *,
    max_lines: int,
    max_chars: int,
) -> str:
    repository = result.get("Repository", "")
    file_name = result.get("FileName", "")
    row = rows[repository]
    path = ROOT / row["directory"] / file_name
    excerpt = bounded_excerpt(path, max_lines=max_lines, max_chars=max_chars)
    return (
        f"source: {public_source_name(row)}\n"
        f"proof_assistant: {row['proof_assistant']}\n"
        f"file: {file_name}\n"
        f"path_terms: {humanize_path(file_name)}\n"
        f"content:\n{excerpt}"
    )


def cohere_rerank(
    query: str,
    candidates: list[dict[str, Any]],
    documents: list[str],
    *,
    api_key: str,
    model: str,
    max_tokens_per_doc: int,
    timeout: float,
    retries: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.dumps(
        {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": len(documents),
            "max_tokens_per_doc": max_tokens_per_doc,
        }
    ).encode()
    request = urllib.request.Request(
        COHERE_RERANK_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.perf_counter()
    response_data: dict[str, Any] | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_data = json.loads(response.read())
            break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            if exc.code == 429 and attempt < retries:
                time.sleep(min(20.0, 2.0 * (attempt + 1)))
                continue
            raise RuntimeError(f"Cohere rerank HTTP {exc.code}: {body[:500]}") from exc
    if response_data is None:
        raise RuntimeError("Cohere rerank returned no response")
    elapsed_ms = (time.perf_counter() - started) * 1000
    reranked: list[dict[str, Any]] = []
    for result in response_data.get("results") or []:
        index = int(result["index"])
        item = dict(candidates[index])
        item["Score"] = float(result["relevance_score"])
        reranked.append(item)
    billed_units = (
        (response_data.get("meta") or {}).get("billed_units") or {}
    ).get("search_units", 0)
    return reranked, {
        "rerank_ms": elapsed_ms,
        "search_units": billed_units,
        "rerank_request_bytes": len(payload),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=pathlib.Path, default=evaluate.DEFAULT_GOLD)
    parser.add_argument("--expansions", type=pathlib.Path, default=DEFAULT_EXPANSIONS)
    parser.add_argument("--candidate-pool", type=int, default=30)
    parser.add_argument("--model", default="rerank-v4.0-fast")
    parser.add_argument("--api-key-env", default="COHERE_API_KEY")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--rrf-constant", type=int, default=60)
    parser.add_argument("--fusion-depth", type=int, default=200)
    parser.add_argument("--max-tokens-per-doc", type=int, default=3000)
    parser.add_argument("--excerpt-lines", type=int, default=300)
    parser.add_argument("--excerpt-chars", type=int, default=12000)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    if args.candidate_pool < 1:
        print("ERROR: --candidate-pool must be positive")
        return 2
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"ERROR: environment variable {args.api_key_env} is not set")
        return 2

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
    rows = source_rows()

    scored_cases: list[dict[str, Any]] = []
    total_units = 0
    for number, case in enumerate(gold["cases"], start=1):
        fused, retrieval_runtime, formulations, compiled = retrieve_multiquery(
            case,
            expansion_queries,
            timeout=min(args.timeout, 30.0),
            rrf_constant=args.rrf_constant,
            depth=args.fusion_depth,
        )
        candidates = fused[: args.candidate_pool]
        documents = [
            rerank_document(
                item,
                rows,
                max_lines=args.excerpt_lines,
                max_chars=args.excerpt_chars,
            )
            for item in candidates
        ]
        reranked, rerank_runtime = cohere_rerank(
            case["query"],
            candidates,
            documents,
            api_key=api_key,
            model=args.model,
            max_tokens_per_doc=args.max_tokens_per_doc,
            timeout=args.timeout,
            retries=args.retries,
        )
        total_units += int(rerank_runtime["search_units"] or 0)
        runtime = {
            "elapsed_ms": retrieval_runtime["elapsed_ms"] + rerank_runtime["rerank_ms"],
            "retrieval_ms": retrieval_runtime["elapsed_ms"],
            "rerank_ms": rerank_runtime["rerank_ms"],
            "payload_bytes": retrieval_runtime["payload_bytes"]
            + sum(len(document.encode()) for document in documents),
            "returned_files": len(reranked),
            "retrieval_queries": retrieval_runtime["retrieval_queries"],
            "search_units": rerank_runtime["search_units"],
            "rerank_request_bytes": rerank_runtime["rerank_request_bytes"],
        }
        scored = evaluate.score_case(
            case,
            reranked,
            " MULTIQUERY_RRF_COHERE_RERANK ".join(compiled),
            runtime,
        )
        scored["formulations"] = formulations
        scored_cases.append(scored)
        print(
            f"{number:02d}/{len(gold['cases'])} {case['id']} "
            f"owner={scored['first_owner_rank']} relevant={scored['first_relevant_rank']} "
            f"units={rerank_runtime['search_units']}",
            flush=True,
        )

    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
        "expansions_sha256": hashlib.sha256(args.expansions.read_bytes()).hexdigest(),
        "source_table_sha256": hashlib.sha256((ROOT / "sources.tsv").read_bytes()).hexdigest(),
        "expansion_model": expansion_data.get("model"),
        "expansion_prompt_version": expansion_data.get("prompt_version"),
        "variant": "gemini_multiquery_rrf_cohere_v4_fast_v1",
        "provider": "local+cohere",
        "rerank_model": args.model,
        "candidate_pool": args.candidate_pool,
        "rrf_constant": args.rrf_constant,
        "fusion_depth": args.fusion_depth,
        "document_projection_version": DOCUMENT_PROJECTION_VERSION,
        "document_projection": {
            "excerpt_lines": args.excerpt_lines,
            "excerpt_chars": args.excerpt_chars,
            "max_tokens_per_doc": args.max_tokens_per_doc,
            "imports_removed": True,
            "fields": ["source", "proof_assistant", "file", "path_terms", "content"],
        },
        "index": evaluate.index_fingerprint(),
        "search_units": total_units,
        "metrics": evaluate.aggregate(scored_cases),
        "metrics_by_tag": evaluate.by_tag(scored_cases),
        "cases": scored_cases,
    }
    evaluate.print_summary(report)
    print(f"Cohere search units: {total_units}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
