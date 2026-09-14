#!/usr/bin/env python3
"""Append-only scientific record for search-quality work.

Measurements are copied into immutable timestamped artifacts under ``runs/`` and
summarized in ``ledger.jsonl``.  Observations, hypotheses, decisions and anomalies
use the same ledger and can cite measurement record IDs as evidence.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import shutil
import sys
from typing import Any

from provenance import repository_state

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEARCH = ROOT / "evaluation" / "search"
LEDGER = SEARCH / "ledger.jsonl"
RUNS = SEARCH / "runs"

KEY_METRICS = (
    "owner_hit@1",
    "owner_hit@5",
    "owner_hit@10",
    "owner_hit@20",
    "hit@1",
    "hit@5",
    "hit@10",
    "hit@20",
    "source_hit@10",
    "gold_recall@10",
    "mrr",
    "owner_mrr",
    "ndcg@10",
    "zero_result_rate",
    "latency_ms_p50",
    "latency_ms_p95",
    "formal_source_files",
    "nonformal_materialized_files",
    "lean_files",
    "lean_import_aggregators",
    "lean_import_aggregator_rate",
    "lean_exact_duplicate_files",
    "lean_exact_duplicate_file_rate",
    "lean_cross_source_duplicate_files",
    "lean_cross_source_duplicate_file_rate",
    "top10_import_aggregator_slots",
    "top10_roadmap_suggested_slots",
    "top10_vendored_slots",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_ledger() -> list[dict[str, Any]]:
    if not LEDGER.exists():
        return []
    records = []
    for lineno, line in enumerate(LEDGER.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{LEDGER}:{lineno}: invalid JSON: {exc}") from exc
    return records


def append_record(record: dict[str, Any]) -> None:
    existing = load_ledger()
    ids = {item.get("record_id") for item in existing}
    if record["record_id"] in ids:
        raise ValueError(f"duplicate ledger record_id: {record['record_id']}")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def compact_timestamp(value: str) -> str:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-") or "unnamed"


def measurement_record(
    report_path: pathlib.Path,
    *,
    stage: str,
    note: str | None,
    allow_dirty: bool,
    historical: bool,
) -> dict[str, Any]:
    raw = report_path.read_bytes()
    report = json.loads(raw)
    required = ("created_at", "corpus_git_commit", "variant", "gold_sha256")
    missing = [key for key in required if key not in report]
    if missing:
        raise ValueError(f"report lacks required fields: {', '.join(missing)}")

    report_state = report.get("repository_state")
    if report_state and not report_state.get("worktree_clean", False) and not allow_dirty:
        raise ValueError("report was produced from a dirty worktree; pass --allow-dirty only for an explicitly noncanonical run")

    current = repository_state(ROOT)
    if not historical:
        if report["corpus_git_commit"] != current["commit"]:
            raise ValueError(
                "report commit differs from current HEAD; use --historical only when backfilling an already-completed run"
            )
        if not current["worktree_clean"] and not allow_dirty:
            raise ValueError("current worktree is dirty; commit the experiment before archiving its measurement")

    report_sha = sha256_bytes(raw)
    timestamp = compact_timestamp(report["created_at"])
    variant = safe_name(str(report["variant"]))
    short_commit = str(report["corpus_git_commit"])[:8]
    record_id = f"M-{timestamp}-{variant}-{report_sha[:8]}"
    artifact_name = f"{timestamp}__{variant}__{short_commit}__{report_sha[:8]}.json"
    artifact = RUNS / artifact_name
    RUNS.mkdir(parents=True, exist_ok=True)
    if artifact.exists():
        if sha256_bytes(artifact.read_bytes()) != report_sha:
            raise ValueError(f"immutable run artifact collision: {artifact}")
    else:
        shutil.copyfile(report_path, artifact)

    if "metrics" in report:
        metrics = {key: report["metrics"][key] for key in KEY_METRICS if key in report["metrics"]}
    elif "summary" in report and "rank_cutoff" in report:
        k = int(report["rank_cutoff"])
        summary = report["summary"]
        metrics = {
            f"success@{k}": summary["single_run_success"]["mean"],
            f"owner_success@{k}": summary["single_run_owner_success"]["mean"],
        }
        for r, values in summary.get("pass_at_r", {}).items():
            metrics[f"pass@{r}[success@{k}]"] = values["success"]["mean"]
            metrics[f"pass@{r}[owner_success@{k}]"] = values["owner_success"]["mean"]
    else:
        raise ValueError("report has neither ordinary metrics nor repeated-run summary")
    config_keys = (
        "provider",
        "rrf_constant",
        "fusion_depth",
        "candidate_pool",
        "rerank_model",
        "expansion_model",
        "expansion_prompt_version",
        "document_projection_version",
        "search_units",
        "runs",
        "rank_cutoff",
        "pass_trial_counts",
        "bootstrap",
        "api_url",
        "serving_options",
    )
    config = {key: report[key] for key in config_keys if key in report}
    return {
        "schema_version": 1,
        "record_type": "measurement",
        "record_id": record_id,
        "observed_at": report["created_at"],
        "recorded_at": utc_now(),
        "stage": stage,
        "variant": report["variant"],
        "provider": report.get("provider"),
        "corpus_git_commit": report["corpus_git_commit"],
        "repository_state": report_state,
        "provenance_level": "full" if report_state else "legacy-report",
        "gold_sha256": report["gold_sha256"],
        "query_config_sha256": report.get("query_config_sha256"),
        "serving_config_sha256": report.get("serving_config_sha256"),
        "index": report.get("index"),
        "artifact": str(artifact.relative_to(ROOT)),
        "artifact_sha256": report_sha,
        "retrieval_engine": report.get("retrieval_engine"),
        "metrics": metrics,
        "configuration": config,
        "note": note,
    }


def note_record(category: str, text: str, evidence: list[str], tags: list[str]) -> dict[str, Any]:
    state = repository_state(ROOT)
    timestamp = utc_now()
    digest = hashlib.sha256((category + "\0" + text + "\0" + timestamp).encode()).hexdigest()[:8]
    prefix = {"observation": "O", "hypothesis": "H", "decision": "D", "anomaly": "A"}[category]
    return {
        "schema_version": 1,
        "record_type": category,
        "record_id": f"{prefix}-{compact_timestamp(timestamp)}-{digest}",
        "observed_at": timestamp,
        "recorded_at": timestamp,
        "corpus_git_commit": state["commit"],
        "repository_state": state,
        "evidence": evidence,
        "tags": tags,
        "text": text,
    }


def validate() -> list[str]:
    errors: list[str] = []
    records = load_ledger()
    ids: set[str] = set()
    known: set[str] = set()
    for number, record in enumerate(records, start=1):
        rid = record.get("record_id")
        if not isinstance(rid, str) or not rid:
            errors.append(f"ledger line {number}: missing record_id")
            continue
        if rid in ids:
            errors.append(f"ledger line {number}: duplicate record_id {rid}")
        ids.add(rid)
        if record.get("record_type") == "measurement":
            artifact_rel = record.get("artifact")
            expected = record.get("artifact_sha256")
            if not artifact_rel or not expected:
                errors.append(f"{rid}: measurement lacks artifact/hash")
            else:
                artifact = ROOT / artifact_rel
                if not artifact.is_file():
                    errors.append(f"{rid}: missing artifact {artifact_rel}")
                elif sha256_bytes(artifact.read_bytes()) != expected:
                    errors.append(f"{rid}: artifact hash mismatch")
        for evidence in record.get("evidence", []):
            if evidence not in known:
                errors.append(f"{rid}: evidence {evidence} must refer to an earlier ledger record")
        known.add(rid)
    return errors


def show() -> None:
    for record in load_ledger():
        rid = record["record_id"]
        kind = record["record_type"]
        when = record["observed_at"]
        if kind == "measurement":
            metrics = record.get("metrics", {})
            print(
                f"{when} {rid} measurement {record.get('variant')} "
                f"owner@10={metrics.get('owner_hit@10')} hit@10={metrics.get('hit@10')}"
            )
        else:
            print(f"{when} {rid} {kind}: {record.get('text', '')}")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="archive a report and append a measurement record")
    run.add_argument("report", type=pathlib.Path)
    run.add_argument("--stage", choices=("baseline", "candidate", "production", "diagnostic"), required=True)
    run.add_argument("--note")
    run.add_argument("--allow-dirty", action="store_true")
    run.add_argument("--historical", action="store_true")

    note = sub.add_parser("note", help="append an observation/hypothesis/decision/anomaly")
    note.add_argument("category", choices=("observation", "hypothesis", "decision", "anomaly"))
    note.add_argument("text")
    note.add_argument("--evidence", action="append", default=[])
    note.add_argument("--tag", action="append", default=[])

    sub.add_parser("validate")
    sub.add_parser("show")
    args = parser.parse_args()

    try:
        if args.command == "run":
            record = measurement_record(
                args.report,
                stage=args.stage,
                note=args.note,
                allow_dirty=args.allow_dirty,
                historical=args.historical,
            )
            append_record(record)
            print(record["record_id"])
        elif args.command == "note":
            record = note_record(args.category, args.text, args.evidence, args.tag)
            append_record(record)
            print(record["record_id"])
        elif args.command == "validate":
            errors = validate()
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print(f"lab log ok: {len(load_ledger())} records")
        else:
            show()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
