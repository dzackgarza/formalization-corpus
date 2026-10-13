#!/usr/bin/env python3
"""Evaluate SPLADE++ query expansion against the corpus-wide FTS5 index.

This is an SQ2 first-stage experiment, not a full SPLADE document index.  A
mature SPLADE++ sparse encoder supplies qrel-independent query expansions;
the existing complete corpus-wide SQLite FTS5/BM25 index supplies document
statistics and candidate retrieval.  Original normalized query terms are
retained so WordPiece-only dimensions cannot erase exact mathematical names.

The report names this mechanism explicitly as query expansion.  It must not be
interpreted as evidence about a full SPLADE dot-product index, whose documents
would also be encoded by the sparse model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Iterable

import evaluate
import provenance
from evaluate_corpus_fts5 import DEFAULT_REMOTE_DB, remote_query_batch


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "prithivida/Splade_PP_en_v1"
_LEXICAL_TOKEN = re.compile(r"[0-9A-Za-z]+\Z")


def usable_fts5_token(token: str | None) -> bool:
    """Whether one WordPiece vocabulary item is a faithful FTS5 whole token."""

    return bool(
        token
        and len(token) >= 2
        and not token.startswith("[")
        and not token.startswith("##")
        and _LEXICAL_TOKEN.fullmatch(token)
    )


def stable_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def expansion_from_embedding(
    *,
    indices: Iterable[int],
    values: Iterable[float],
    tokenizer: Any,
) -> tuple[list[dict[str, Any]], int]:
    """Convert a SPLADE sparse vector to usable full-token expansions.

    SPLADE dimensions are BERT WordPieces.  SQLite's ``unicode61`` tokenizer
    cannot represent continuation markers such as ``##tion`` faithfully, so
    this bridge keeps only complete alphanumeric vocabulary items.  The full
    vector remains represented by counts in the report; no qrels are consulted.
    """

    weighted = sorted(
        ((int(index), float(weight)) for index, weight in zip(indices, values)),
        key=lambda pair: (-pair[1], pair[0]),
    )
    expansions: list[dict[str, Any]] = []
    dropped = 0
    seen: set[str] = set()
    for token_id, weight in weighted:
        token = tokenizer.id_to_token(token_id)
        if not usable_fts5_token(token):
            dropped += 1
            continue
        token = str(token).lower()
        if token in seen:
            continue
        seen.add(token)
        expansions.append({"token": token, "weight": weight, "token_id": token_id})
    return expansions, dropped


def _model_sha256(model: Any) -> str | None:
    model_dir = getattr(getattr(model, "model", None), "_model_dir", None)
    if model_dir is None:
        return None
    path = pathlib.Path(model_dir) / "model.onnx"
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=pathlib.Path, default=evaluate.DEFAULT_GOLD)
    parser.add_argument("--host", default="zack@159.223.102.204")
    parser.add_argument(
        "--remote-script", default="/home/zack/lean-corpus/experiments/corpus_fts5.py"
    )
    parser.add_argument("--remote-db", default=DEFAULT_REMOTE_DB)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--model-cache", type=pathlib.Path)
    parser.add_argument("--depth", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    if args.depth <= 0 or args.timeout <= 0:
        print("ERROR: depth and timeout must be positive", file=sys.stderr)
        return 2

    gold = evaluate.load_gold(args.gold)
    errors = evaluate.validate_gold(gold)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    try:
        import fastembed
        from fastembed import SparseTextEmbedding
    except ImportError:
        print(
            "ERROR: this experiment requires fastembed (validated with fastembed==0.8.0)",
            file=sys.stderr,
        )
        return 2

    model_kwargs: dict[str, Any] = {"model_name": args.model}
    if args.model_cache is not None:
        model_kwargs["cache_dir"] = str(args.model_cache)
    try:
        model = SparseTextEmbedding(**model_kwargs)
    except Exception as exc:
        print(f"ERROR: failed to load sparse model {args.model!r}: {exc}", file=sys.stderr)
        return 2

    tokenizer = model.model.tokenizer
    requests: list[dict[str, Any]] = []
    query_records: dict[str, dict[str, Any]] = {}
    for case in gold["cases"]:
        original_terms, _ = evaluate.normalized_query_terms(case["query"])
        started = time.perf_counter()
        try:
            embedding = next(iter(model.embed([case["query"]], batch_size=1)))
        except Exception as exc:
            print(f"ERROR: SPLADE encoding failed for {case['id']}: {exc}", file=sys.stderr)
            return 2
        encoding_ms = (time.perf_counter() - started) * 1000
        expansions, dropped = expansion_from_embedding(
            indices=embedding.indices,
            values=embedding.values,
            tokenizer=tokenizer,
        )
        learned_terms = [item["token"] for item in expansions]
        terms = stable_unique([term.lower() for term in original_terms] + learned_terms)
        requests.append({"id": case["id"], "terms": terms, "top": args.depth})
        query_records[case["id"]] = {
            "original_terms": original_terms,
            "learned_expansions": expansions,
            "fts5_terms": terms,
            "sparse_dimensions": len(embedding.indices),
            "dropped_non_full_wordpiece_dimensions": dropped,
            "encoding_ms": encoding_ms,
        }

    try:
        remote = remote_query_batch(
            requests,
            host=args.host,
            remote_script=args.remote_script,
            remote_db=args.remote_db,
            mode="bm25-all",
            rrf_constant=60,
            timeout=args.timeout,
        )
    except (RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    by_id = {str(row["id"]): row for row in remote["responses"]}
    expected_ids = {str(case["id"]) for case in gold["cases"]}
    if set(by_id) != expected_ids:
        print("ERROR: remote FTS5 response IDs do not match gold cases", file=sys.stderr)
        return 2
    if not remote["index"].get("complete"):
        print("ERROR: remote corpus FTS5 index is incomplete", file=sys.stderr)
        return 2

    scored_cases: list[dict[str, Any]] = []
    for case in gold["cases"]:
        response = by_id[str(case["id"])]
        query_record = query_records[case["id"]]
        runtime = {
            "elapsed_ms": float(response["elapsed_ms"]) + float(query_record["encoding_ms"]),
            "encoding_ms": float(query_record["encoding_ms"]),
            "retrieval_ms": float(response["elapsed_ms"]),
            "payload_bytes": 0,
            "returned_files": len(response["results"]),
            "retrieval_queries": 1,
        }
        scored = evaluate.score_case(
            case,
            list(response["results"]),
            " SPLADE_EXPANDED_FTS5 ".join(query_record["fts5_terms"]),
            runtime,
        )
        scored["splade_query"] = query_record
        scored_cases.append(scored)
        print(
            f"{case['id']} terms={len(query_record['fts5_terms'])} "
            f"owner={scored['first_owner_rank']} relevant={scored['first_relevant_rank']} "
            f"latency_ms={runtime['elapsed_ms']:.2f}",
            flush=True,
        )

    repo_state = provenance.repository_state(ROOT)
    model_description = getattr(model.model, "model_description", None)
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_git_commit": repo_state["commit"],
        "repository_state": repo_state,
        "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
        "query_config_sha256": evaluate.query_config_sha256(),
        "serving_config_sha256": None,
        "variant": "spladepp_query_expansion_sqlite_fts5_bm25_v1",
        "provider": "local-fastembed+remote-sqlite-fts5",
        "index": remote["index"],
        "learned_sparse": {
            "scope": "query expansion only; documents use corpus FTS5/BM25, not SPLADE vectors",
            "model": args.model,
            "model_source": str(getattr(getattr(model_description, "sources", None), "hf", "")),
            "model_sha256": _model_sha256(model),
            "fastembed_version": getattr(fastembed, "__version__", None),
            "vocab_size": getattr(model_description, "vocab_size", None),
            "input_truncation_tokens": 128,
            "bridge": (
                "retain normalized lexical query terms and add every positive SPLADE dimension "
                "that is already a complete alphanumeric WordPiece; no qrel-derived threshold"
            ),
        },
        "retrieval_engine": {
            "name": "SQLite FTS5",
            "mode": "bm25-all",
            "fields": ["source", "path", "content"],
            "tokenizer": remote["index"].get("tokenizer"),
            "sqlite_version": remote["index"].get("sqlite_version"),
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
