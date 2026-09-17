#!/usr/bin/env python3
"""Reproducible retrieval evaluation for the formalization corpus.

The default provider searches the local Zoekt shards directly.  The baseline
variant mirrors the public search page's current default query compilation:
every whitespace-delimited token is an ANDed content term, restricted to proof
source files, case-insensitively.

This script intentionally evaluates retrieval only.  Generation/answer quality
belongs in a separate downstream evaluation once retrieval is stable.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pathlib
import re
import statistics
import subprocess
import sys
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import provenance

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_GOLD = ROOT / "evaluation/search/gold.json"
DEFAULT_BASELINE = ROOT / "evaluation/search/baselines/frontend_lexical_v1.json"
QUERY_CONFIG = ROOT / "site/search-query.json"
ZOEKT = ROOT / "bin/zoekt"
INDEX_DIR = ROOT / ".zoekt"
FORMAL_FILES = r"\.(lean|v|agda|lagda(\.(md|rst|tex))?|thy|ml|hl|sml|sig|miz|mm|mm0|mm1|lisp|lsp|acl2|pvs|prf|elf)$"
K_VALUES = (1, 5, 10, 20, 50, 100, 200)
DEFAULT_API_URL = "https://formalization-corpus.dzackgarza.com/api/search"
FILTER_STATE = ROOT / "filtering/current.jsonl"


def load_gold(path: pathlib.Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if data.get("version") != 1 or not isinstance(data.get("cases"), list):
        raise ValueError(f"unsupported gold schema in {path}")
    return data


def source_rows() -> dict[str, dict[str, str]]:
    with (ROOT / "sources.tsv").open(newline="") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        return {pathlib.PurePosixPath(row["directory"]).name: row for row in rows}


@lru_cache(maxsize=None)
def catalogued_files(repository: str) -> frozenset[str]:
    """Return audited file paths for a source, including when its cache is ghosted."""
    index_path = ROOT / "filtering/repository-review/catalogue.jsonl"
    if not index_path.is_file():
        return frozenset()
    row = next(
        (json.loads(line) for line in index_path.read_text().splitlines()
         if line.strip() and json.loads(line).get("repository") == repository
         and json.loads(line).get("inventory_status", "active") == "active"),
        None,
    )
    if row is None:
        return frozenset()
    catalogue = json.loads((ROOT / row["catalogue_file"]).read_text())
    paths: set[str] = set()
    for unit in catalogue.get("work_units", []):
        manifest = ROOT / unit["files_manifest"]
        for line in manifest.read_text().splitlines():
            if line.strip():
                paths.add(str(json.loads(line)["path"]))
    return frozenset(paths)


def validate_gold(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sources = source_rows()
    seen_ids: set[str] = set()
    if not data["cases"]:
        errors.append("gold set has no cases")
    for case in data["cases"]:
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append("case missing nonempty id")
            continue
        if case_id in seen_ids:
            errors.append(f"duplicate case id: {case_id}")
        seen_ids.add(case_id)
        if not isinstance(case.get("query"), str) or not case["query"].strip():
            errors.append(f"{case_id}: missing query")
        judgments = case.get("judgments")
        if not isinstance(judgments, list) or not judgments:
            errors.append(f"{case_id}: needs at least one positive judgment")
            continue
        seen_targets: set[tuple[str, str]] = set()
        positive_judgments = 0
        for judgment in judgments:
            repo = judgment.get("repository")
            file_name = judgment.get("file")
            rel = judgment.get("relevance")
            if repo not in sources:
                errors.append(f"{case_id}: unknown repository {repo!r}")
                continue
            if not isinstance(file_name, str) or not file_name:
                errors.append(f"{case_id}: invalid file for {repo}")
                continue
            if not isinstance(rel, int) or not 0 <= rel <= 3:
                errors.append(f"{case_id}: relevance must be an integer 0..3")
            elif rel > 0:
                positive_judgments += 1
            key = (repo, file_name)
            if key in seen_targets:
                errors.append(f"{case_id}: duplicate judgment {repo}:{file_name}")
            seen_targets.add(key)
            local_path = ROOT / sources[repo]["directory"] / file_name
            if not local_path.is_file() and file_name not in catalogued_files(str(repo)):
                errors.append(
                    f"{case_id}: judged file is neither hydrated nor present in the committed audit manifest: {local_path}"
                )
        if positive_judgments == 0:
            errors.append(f"{case_id}: needs at least one positive judgment")
    return errors


def regex_escape(text: str) -> str:
    return re.sub(r"([.*+?^${}()|\[\]\\])", r"\\\1", text)


def quoted_pattern(pattern: str) -> str:
    return '"' + pattern.replace("\\", "\\\\").replace('"', '\\"') + '"'


def literal_terms(text: str) -> list[str]:
    terms: list[str] = []
    for match in re.finditer(r'"([^"]+)"|(\S+)', text):
        value = match.group(1) if match.group(1) is not None else match.group(2)
        if value:
            terms.append(f"content:{quoted_pattern(regex_escape(value))}")
    return terms


@lru_cache(maxsize=1)
def query_config() -> dict[str, Any]:
    data = json.loads(QUERY_CONFIG.read_text())
    if data.get("version") != 1:
        raise ValueError(f"unsupported query config version in {QUERY_CONFIG}")
    return data


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def query_semantics_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Configuration that changes query compilation, excluding serving budgets."""
    source = query_config() if config is None else config
    return {key: value for key, value in source.items() if key != "serving"}


def query_config_sha256() -> str:
    return canonical_json_sha256(query_semantics_config())


def serving_config_sha256() -> str:
    return canonical_json_sha256(query_config().get("serving") or {})


def strip_intent_prefix(text: str, config: dict[str, Any]) -> str:
    trimmed = text.strip()
    lower = trimmed.casefold()
    for raw_prefix in sorted(config.get("intent_prefixes", []), key=len, reverse=True):
        prefix = raw_prefix.casefold()
        if lower == prefix:
            return ""
        if lower.startswith(prefix + " "):
            return trimmed[len(raw_prefix):].strip()
    return trimmed


def normalized_query_terms(text: str) -> tuple[list[str], str | None]:
    """Conservative natural-query normalization shared with the public frontend."""
    config = query_config()
    stopwords = set(config["stopwords"])
    proof_assistant_filters = config["proof_assistant_terms"]
    normalized = strip_intent_prefix(text, config)
    words = re.findall(r"[\w⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉ℚℤℝℂ∞+-]+", normalized, flags=re.UNICODE)
    proof_filter = None
    terms: list[str] = []
    for word in words:
        lower = word.casefold()
        if lower in proof_assistant_filters:
            proof_filter = proof_assistant_filters[lower]
            continue
        if lower in stopwords:
            continue
        terms.append(word)
    return terms, proof_filter


def compile_query(text: str, variant: str) -> str:
    if variant == "frontend_lexical_v1":
        parts = literal_terms(text)
        parts.append(f"file:{FORMAL_FILES}")
    elif variant in {
        "normalized_content_v1",
        "normalized_path_content_v1",
        "frontend_lexical_v2",
        "zoekt_bm25_v1",
    }:
        terms, proof_filter = normalized_query_terms(text)
        if variant == "normalized_content_v1":
            parts = [f"content:{quoted_pattern(regex_escape(term))}" for term in terms]
        else:
            parts = [quoted_pattern(regex_escape(term)) for term in terms]
        if not terms:
            parts.append('content:"$a"')
        parts.append(f"file:{proof_filter or FORMAL_FILES}")
    else:
        raise ValueError(f"unknown retrieval variant: {variant}")
    parts.append("case:no")
    return " ".join(parts)


def index_fingerprint() -> dict[str, Any]:
    shards = sorted(INDEX_DIR.glob("*.zoekt"))
    h = hashlib.sha256()
    total = 0
    latest_ns = 0
    for shard in shards:
        st = shard.stat()
        total += st.st_size
        latest_ns = max(latest_ns, st.st_mtime_ns)
        h.update(f"{shard.name}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())
    return {
        "shard_count": len(shards),
        "total_bytes": total,
        "latest_mtime_ns": latest_ns,
        "metadata_sha256": h.hexdigest(),
    }


def retrieval_engine_fingerprint() -> dict[str, Any]:
    state: dict[str, Any] = {}
    if ZOEKT.is_file():
        h = hashlib.sha256()
        with ZOEKT.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(block)
        state["zoekt_binary_sha256"] = h.hexdigest()
    source = ROOT / "tools" / "sourcegraph__zoekt"
    if (source / ".git").exists():
        try:
            state["zoekt_source_commit"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=source, text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            pass
    return state


def local_search(query: str, timeout: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not ZOEKT.is_file():
        raise FileNotFoundError(f"missing local search binary: {ZOEKT}")
    started = time.perf_counter()
    proc = subprocess.run(
        [str(ZOEKT), "-index_dir", str(INDEX_DIR), "-jsonl", query],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or f"zoekt exited {proc.returncode}")
    results = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    return results, {
        "elapsed_ms": elapsed_ms,
        "payload_bytes": len(proc.stdout),
        "returned_files": len(results),
    }


@lru_cache(maxsize=1)
def file_role_index():
    server_root = str(ROOT / "server")
    if server_root not in sys.path:
        sys.path.insert(0, server_root)
    from formalization_api.roles import FileRoleIndex

    return FileRoleIndex.from_path(FILTER_STATE)


def apply_result_roles(
    results: list[dict[str, Any]], *, variant: str, provider: str
) -> list[dict[str, Any]]:
    # The API applies the same transform server-side.  Only the local provider
    # needs to reproduce it here.  Keep normalized_path_content_v1 as the raw
    # Zoekt control even though it compiles the same lexical query as v2.
    if provider == "local" and variant == "frontend_lexical_v2":
        return file_role_index().rerank_files(results)
    return results


def serving_options(
    *,
    top: int | None = None,
    shard_max_match_count: int | None = None,
    total_max_match_count: int | None = None,
    whole: bool | None = None,
    use_bm25_scoring: bool | None = None,
) -> dict[str, Any]:
    configured = query_config().get("serving") or {}
    resolved = {
        "max_doc_display_count": int(
            configured.get("max_doc_display_count", 60) if top is None else top
        ),
        "shard_max_match_count": int(
            configured.get("shard_max_match_count", 0)
            if shard_max_match_count is None
            else shard_max_match_count
        ),
        "total_max_match_count": int(
            configured.get("total_max_match_count", 0)
            if total_max_match_count is None
            else total_max_match_count
        ),
        "whole": bool(configured.get("whole", True) if whole is None else whole),
        "use_bm25_scoring": bool(use_bm25_scoring) if use_bm25_scoring is not None else False,
    }
    if resolved["max_doc_display_count"] <= 0:
        raise ValueError("max_doc_display_count must be positive")
    if resolved["shard_max_match_count"] < 0 or resolved["total_max_match_count"] < 0:
        raise ValueError("search match-count budgets must be nonnegative")
    return resolved


def api_search(
    query: str,
    timeout: float,
    api_url: str,
    serving: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    opts: dict[str, Any] = {
        "MaxDocDisplayCount": serving["max_doc_display_count"],
        "ChunkMatches": True,
        "Whole": serving["whole"],
    }
    if serving.get("use_bm25_scoring"):
        opts["UseBM25Scoring"] = True
    if serving["shard_max_match_count"] > 0:
        opts["ShardMaxMatchCount"] = serving["shard_max_match_count"]
    if serving["total_max_match_count"] > 0:
        opts["TotalMaxMatchCount"] = serving["total_max_match_count"]
    payload = json.dumps({"Q": query, "Opts": opts})
    started = time.perf_counter()
    proc = subprocess.run(
        [
            "curl", "-fsS", "--max-time", str(max(1, int(math.ceil(timeout)))),
            api_url,
            "-H", "Content-Type: application/json", "-d", payload,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout + 2,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or f"curl exited {proc.returncode}")
    response = json.loads(proc.stdout)
    result = response.get("Result") or {}
    files = result.get("Files") or []
    normalized = [
        {
            "Repository": item.get("Repository", ""),
            "FileName": item.get("FileName", ""),
            "Score": item.get("Score", 0),
        }
        for item in files
    ]
    return normalized, {
        "elapsed_ms": elapsed_ms,
        "payload_bytes": len(proc.stdout),
        "returned_files": len(normalized),
        "reported_file_count": result.get("FileCount", len(normalized)),
        "server_duration_ns": result.get("Duration"),
    }


def api_index_fingerprint_from_list(payload: dict[str, Any]) -> dict[str, Any]:
    """Fingerprint the exact public Zoekt state exposed by ``/api/list``."""
    rows: list[dict[str, Any]] = []
    repo_list = payload.get("List") or {}
    for entry in repo_list.get("Repos") or []:
        repository = entry.get("Repository") or {}
        metadata = entry.get("IndexMetadata") or {}
        stats = entry.get("Stats") or {}
        rows.append(
            {
                "repository": repository.get("Name", ""),
                "index_options": repository.get("IndexOptions"),
                "index_metadata": {
                    key: metadata.get(key)
                    for key in (
                        "ID",
                        "IndexFormatVersion",
                        "IndexFeatureVersion",
                        "IndexMinReaderVersion",
                        "IndexTime",
                        "PlainASCII",
                        "LanguageMap",
                        "ZoektVersion",
                    )
                },
                "stats": {
                    key: stats.get(key)
                    for key in (
                        "Shards",
                        "Documents",
                        "IndexBytes",
                        "ContentBytes",
                        "NewLinesCount",
                    )
                },
            }
        )
    rows.sort(key=lambda row: row["repository"])
    return {
        "kind": "api-list-v1",
        "repository_count": len(rows),
        "shard_count": sum(int(row["stats"].get("Shards") or 0) for row in rows),
        "document_count": sum(int(row["stats"].get("Documents") or 0) for row in rows),
        "index_bytes": sum(int(row["stats"].get("IndexBytes") or 0) for row in rows),
        "metadata_sha256": canonical_json_sha256(rows),
    }


def api_index_fingerprint(api_url: str, timeout: float) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(api_url)
    path = parsed.path
    if path.endswith("/api/search"):
        path = path[: -len("/api/search")] + "/api/list"
    elif path.endswith("/search"):
        path = path[: -len("/search")] + "/list"
    else:
        raise ValueError(f"cannot derive API list endpoint from {api_url!r}")
    list_url = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
    )
    proc = subprocess.run(
        [
            "curl",
            "-fsS",
            "--max-time",
            str(max(1, int(math.ceil(timeout)))),
            list_url,
            "-H",
            "Content-Type: application/json",
            "-d",
            '{"Q":""}',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout + 2,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.decode(errors="replace").strip()
            or f"curl exited {proc.returncode}"
        )
    return api_index_fingerprint_from_list(json.loads(proc.stdout))


def judgment_map(case: dict[str, Any]) -> dict[tuple[str, str], int]:
    return {(j["repository"], j["file"]): j["relevance"] for j in case["judgments"]}


def dcg(relevances: list[int], k: int) -> float:
    value = 0.0
    for rank, relevance in enumerate(relevances[:k], start=1):
        value += (2**relevance - 1) / math.log2(rank + 1)
    return value


def score_case(case: dict[str, Any], results: list[dict[str, Any]], compiled_query: str, runtime: dict[str, Any]) -> dict[str, Any]:
    judgments = judgment_map(case)
    gold_sources = {repo for (repo, _), rel in judgments.items() if rel > 0}
    ranked_relevance: list[int] = []
    ranked_keys: list[tuple[str, str]] = []
    for item in results:
        key = (item.get("Repository", ""), item.get("FileName", ""))
        ranked_keys.append(key)
        ranked_relevance.append(judgments.get(key, 0))

    relevant_gold = {key for key, rel in judgments.items() if rel > 0}
    owner_gold = {key for key, rel in judgments.items() if rel == 3}
    first_relevant = next((i + 1 for i, rel in enumerate(ranked_relevance) if rel > 0), None)
    first_owner = next((i + 1 for i, rel in enumerate(ranked_relevance) if rel == 3), None)
    per_k: dict[str, Any] = {}
    ideal = sorted((rel for rel in judgments.values() if rel > 0), reverse=True)
    for k in K_VALUES:
        top_keys = ranked_keys[:k]
        top_rels = ranked_relevance[:k]
        retrieved_gold = relevant_gold.intersection(top_keys)
        ideal_dcg = dcg(ideal, k)
        per_k[str(k)] = {
            "hit": int(any(rel > 0 for rel in top_rels)),
            "owner_hit": int(any(rel == 3 for rel in top_rels)),
            "source_hit": int(any(repo in gold_sources for repo, _ in top_keys)),
            "gold_recall": len(retrieved_gold) / len(relevant_gold),
            "ndcg": dcg(top_rels, k) / ideal_dcg if ideal_dcg else 0.0,
        }

    return {
        "id": case["id"],
        "query": case["query"],
        "tags": case.get("tags", []),
        "compiled_query": compiled_query,
        "result_count": len(results),
        "first_relevant_rank": first_relevant,
        "first_owner_rank": first_owner,
        "reciprocal_rank": 1 / first_relevant if first_relevant else 0.0,
        "owner_reciprocal_rank": 1 / first_owner if first_owner else 0.0,
        "per_k": per_k,
        "runtime": runtime,
        "top_results": [
            {
                "rank": i + 1,
                "repository": item.get("Repository", ""),
                "file": item.get("FileName", ""),
                "score": item.get("Score", 0),
                "relevance": ranked_relevance[i],
            }
            for i, item in enumerate(results[:20])
        ],
    }


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    if not cases:
        return {}
    n = len(cases)
    metrics: dict[str, Any] = {
        "queries": n,
        "zero_result_rate": sum(case["result_count"] == 0 for case in cases) / n,
        "mrr": statistics.fmean(case["reciprocal_rank"] for case in cases),
        "owner_mrr": statistics.fmean(case["owner_reciprocal_rank"] for case in cases),
    }
    for k in K_VALUES:
        key = str(k)
        metrics[f"hit@{k}"] = statistics.fmean(case["per_k"][key]["hit"] for case in cases)
        metrics[f"owner_hit@{k}"] = statistics.fmean(case["per_k"][key]["owner_hit"] for case in cases)
        metrics[f"source_hit@{k}"] = statistics.fmean(case["per_k"][key]["source_hit"] for case in cases)
        metrics[f"gold_recall@{k}"] = statistics.fmean(case["per_k"][key]["gold_recall"] for case in cases)
        metrics[f"ndcg@{k}"] = statistics.fmean(case["per_k"][key]["ndcg"] for case in cases)
    latencies = [case["runtime"]["elapsed_ms"] for case in cases]
    payloads = [float(case["runtime"]["payload_bytes"]) for case in cases]
    metrics.update(
        {
            "latency_ms_mean": statistics.fmean(latencies),
            "latency_ms_p50": percentile(latencies, 0.50),
            "latency_ms_p95": percentile(latencies, 0.95),
            "payload_bytes_mean": statistics.fmean(payloads),
            "payload_bytes_p95": percentile(payloads, 0.95),
        }
    )
    return metrics


def by_tag(cases: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        for tag in case.get("tags", []):
            groups[tag].append(case)
    return {tag: aggregate(items) for tag, items in sorted(groups.items())}


def compare_reports(current: dict[str, Any], baseline: dict[str, Any], tolerance: float) -> list[str]:
    problems: list[str] = []
    if current.get("gold_sha256") != baseline.get("gold_sha256"):
        problems.append("gold-set hash differs; regenerate both runs against the same relevance judgments before comparing")
        return problems
    if current.get("index") != baseline.get("index"):
        problems.append("index fingerprint differs; do not attribute score changes to retrieval code until the index change is reviewed")
        return problems
    if current.get("query_config_sha256") != baseline.get("query_config_sha256"):
        problems.append("query-normalization config differs; regenerate and review the retrieval baseline before comparing scores")
        return problems
    if current.get("result_role_state") != baseline.get("result_role_state"):
        problems.append("result-role state differs; regenerate and review the retrieval baseline before comparing scores")
        return problems
    if current.get("provider") == "api" or baseline.get("provider") == "api":
        if current.get("serving_options") != baseline.get("serving_options"):
            problems.append("API serving options differ; treat serving-budget changes as retrieval experiments")
            return problems
    keys = [
        "hit@1", "hit@5", "hit@10", "hit@20",
        "owner_hit@1", "owner_hit@5", "owner_hit@10", "owner_hit@20",
        "mrr", "owner_mrr", "ndcg@10", "ndcg@20",
    ]
    for key in keys:
        before = float(baseline["metrics"][key])
        after = float(current["metrics"][key])
        if after + tolerance < before:
            problems.append(f"{key} regressed: {before:.4f} -> {after:.4f}")
    return problems


def print_summary(report: dict[str, Any]) -> None:
    m = report["metrics"]
    print(f"variant={report['variant']} provider={report['provider']} queries={m['queries']}")
    print(
        "  ".join(
            [
                f"Hit@1={m['hit@1']:.3f}",
                f"Hit@5={m['hit@5']:.3f}",
                f"Hit@10={m['hit@10']:.3f}",
                f"Hit@20={m['hit@20']:.3f}",
                f"MRR={m['mrr']:.3f}",
                f"nDCG@10={m['ndcg@10']:.3f}",
                f"zero={m['zero_result_rate']:.3f}",
            ]
        )
    )
    print(
        f"latency p50={m['latency_ms_p50']:.1f}ms p95={m['latency_ms_p95']:.1f}ms "
        f"payload p95={m['payload_bytes_p95'] / 1024:.1f}KiB"
    )
    misses = [case for case in report["cases"] if not case["per_k"]["20"]["hit"]]
    if misses:
        print("misses@20:")
        for case in misses:
            print(f"  {case['id']}: {case['query']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=pathlib.Path, default=DEFAULT_GOLD)
    parser.add_argument("--variant", default="frontend_lexical_v1")
    parser.add_argument("--provider", choices=("local", "api"), default="local")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--api-top", type=int)
    parser.add_argument("--api-shard-max-match-count", type=int)
    parser.add_argument("--api-total-max-match-count", type=int)
    parser.add_argument(
        "--api-bm25",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable Zoekt's built-in BM25 scorer for API retrieval.",
    )
    parser.add_argument(
        "--api-whole",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--compare", type=pathlib.Path)
    parser.add_argument("--tolerance", type=float, default=1e-12)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    gold = load_gold(args.gold)
    errors = validate_gold(gold)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if args.validate_only:
        print(f"gold ok: {len(gold['cases'])} cases, {sum(len(c['judgments']) for c in gold['cases'])} judgments")
        return 0

    if args.provider == "local" and (not INDEX_DIR.is_dir() or not any(INDEX_DIR.glob("*.zoekt"))):
        print("ERROR: local .zoekt index is unavailable; build or materialize it before running retrieval evals", file=sys.stderr)
        return 2
    if args.provider == "local" and args.variant == "zoekt_bm25_v1":
        print("ERROR: zoekt_bm25_v1 currently requires --provider api", file=sys.stderr)
        return 2

    api_bm25 = args.api_bm25
    if api_bm25 is None and args.variant == "zoekt_bm25_v1":
        api_bm25 = True

    resolved_serving = serving_options(
        top=args.api_top,
        shard_max_match_count=args.api_shard_max_match_count,
        total_max_match_count=args.api_total_max_match_count,
        whole=args.api_whole,
        use_bm25_scoring=api_bm25,
    )
    api_index_before = (
        api_index_fingerprint(args.api_url, args.timeout)
        if args.provider == "api"
        else None
    )

    scored_cases: list[dict[str, Any]] = []
    for case in gold["cases"]:
        compiled = compile_query(case["query"], args.variant)
        try:
            if args.provider == "local":
                results, runtime = local_search(compiled, args.timeout)
            else:
                results, runtime = api_search(
                    compiled,
                    args.timeout,
                    args.api_url,
                    resolved_serving,
                )
            results = apply_result_roles(results, variant=args.variant, provider=args.provider)
        except Exception as exc:
            print(f"ERROR {case['id']}: {exc}", file=sys.stderr)
            return 2
        scored_cases.append(score_case(case, results, compiled, runtime))

    repo_state = provenance.repository_state(ROOT)
    if args.provider == "api":
        api_index_after = api_index_fingerprint(args.api_url, args.timeout)
        if api_index_after != api_index_before:
            print("ERROR: published API index changed during evaluation", file=sys.stderr)
            return 2
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_git_commit": repo_state["commit"],
        "repository_state": repo_state,
        "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
        "query_config_sha256": query_config_sha256(),
        "serving_config_sha256": serving_config_sha256(),
        "variant": args.variant,
        "provider": args.provider,
        "api_url": args.api_url if args.provider == "api" else None,
        "serving_options": resolved_serving if args.provider == "api" else None,
        "index": index_fingerprint() if args.provider == "local" else api_index_before,
        "retrieval_engine": retrieval_engine_fingerprint() if args.provider == "local" else None,
        "result_role_state": file_role_index().fingerprint(),
        "metrics": aggregate(scored_cases),
        "metrics_by_tag": by_tag(scored_cases),
        "cases": scored_cases,
    }
    print_summary(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.output}")
    if args.compare:
        baseline = json.loads(args.compare.read_text())
        problems = compare_reports(report, baseline, args.tolerance)
        if problems:
            for problem in problems:
                print(f"REGRESSION: {problem}", file=sys.stderr)
            return 1
        print(f"no measured regression versus {args.compare}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
