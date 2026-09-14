#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any

from filtering_lib import ROOT, source_revision, sources
from repository_review_lib import (
    BATCHES,
    BATCH_PRIMARY_FILE_TARGET,
    BATCH_UNIT_TARGET,
    CATALOGUE_INDEX,
    CATALOGUE_ROOT,
    FILES_ROOT,
    REVIEW_ID_RE,
    REVIEWS_ROOT,
    RULE_ID_RE,
    SCHEMA_VERSION,
    UNIT_ID_RE,
    active_decisions_by_file,
    catalogue_path,
    corpus_commit,
    dump_jsonl,
    latest_reviews,
    load_catalogue_index,
    load_review_history,
    load_unit_file_records,
    load_units,
    material_snapshot_sha256,
    partition_source,
    resolve_review_exclusions,
    review_path,
    selector_paths,
    source_records,
    unit_files_path,
    utc_now,
)


def relative(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


def source_summary(source: Any, records: list[Any], units: list[Any]) -> dict[str, Any]:
    source_snapshot = material_snapshot_sha256(records)
    totals = collections.Counter(record.current_primary_status for record in records)
    baseline = collections.Counter(record.baseline_primary_status for record in records)
    return {
        "schema_version": SCHEMA_VERSION,
        "repository": source.repository,
        "url": source.url,
        "directory": source.directory.as_posix(),
        "proof_assistant": source.proof_assistant,
        "transport": source.transport,
        "sync_group": source.sync_group,
        "discovered_via": source.discovered_via,
        "source_revision": source_revision(source),
        "source_snapshot_sha256": source_snapshot,
        "totals": {
            "files": len(records),
            "bytes": sum(record.size_bytes for record in records),
            "formal_source_files": sum(record.formal_source for record in records),
            "baseline_primary_retained": baseline["primary-retained"],
            "current_primary_retained": totals["primary-retained"],
            "current_primary_excluded": totals["primary-excluded"],
            "auxiliary_only": totals["auxiliary-only"],
            "unindexed_nonformal": totals["unindexed-nonformal"],
        },
        "work_units": [
            {
                "unit_id": unit.unit_id,
                "scope": {
                    "kind": unit.scope_kind,
                    "value": unit.scope_value,
                    "root_count": len(unit.scope_roots),
                    **({"roots": list(unit.scope_roots)} if unit.scope_kind in {"subtree", "subtree-bundle"} else {}),
                },
                "snapshot_sha256": unit.snapshot_sha256,
                "stats": unit.stats(),
                "files_manifest": relative(unit_files_path(source.repository, unit.unit_id)),
            }
            for unit in units
        ],
    }


def build() -> int:
    decisions = active_decisions_by_file()
    CATALOGUE_ROOT.mkdir(parents=True, exist_ok=True)
    FILES_ROOT.mkdir(parents=True, exist_ok=True)
    source_index: list[dict[str, Any]] = []
    live_catalogues: set[pathlib.Path] = set()
    live_manifests: set[pathlib.Path] = set()

    for number, source in enumerate(sources(), start=1):
        if not source.root.exists():
            raise SystemExit(f"missing hydrated source: {source.repository}")
        records = source_records(source, decisions)
        units = partition_source(source.repository, records)
        summary = source_summary(source, records, units)
        path = catalogue_path(source.repository)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        live_catalogues.add(path)
        for unit in units:
            manifest = unit_files_path(source.repository, unit.unit_id)
            dump_jsonl(manifest, (record.as_json() for record in unit.records))
            live_manifests.add(manifest)
        source_index.append(
            {
                "schema_version": SCHEMA_VERSION,
                "repository": source.repository,
                "proof_assistant": source.proof_assistant,
                "source_revision": summary["source_revision"],
                "source_snapshot_sha256": summary["source_snapshot_sha256"],
                "files": summary["totals"]["files"],
                "bytes": summary["totals"]["bytes"],
                "work_units": len(units),
                "catalogue_file": relative(path),
            }
        )
        if number % 100 == 0:
            print(f"catalogued {number} sources", file=sys.stderr)

    for path in CATALOGUE_ROOT.glob("*.json"):
        if path not in live_catalogues:
            path.unlink()
    for repository_dir in FILES_ROOT.iterdir() if FILES_ROOT.exists() else []:
        if not repository_dir.is_dir():
            continue
        for path in repository_dir.glob("*.jsonl"):
            if path not in live_manifests:
                path.unlink()
        if not any(repository_dir.iterdir()):
            repository_dir.rmdir()

    source_index.sort(key=lambda row: row["repository"])
    dump_jsonl(CATALOGUE_INDEX, source_index)
    build_batches()
    total_units = sum(row["work_units"] for row in source_index)
    total_files = sum(row["files"] for row in source_index)
    print(f"repository review catalogue: {len(source_index)} sources, {total_units} units, {total_files} imported files")
    return 0


def build_batches() -> None:
    units = sorted(load_units().values(), key=lambda unit: (unit["repository"], unit["scope"]["value"], unit["unit_id"]))
    batches: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    primary_count = 0

    def flush() -> None:
        nonlocal current, primary_count
        if not current:
            return
        number = len(batches) + 1
        batches.append(
            {
                "schema_version": SCHEMA_VERSION,
                "batch_id": f"RRB-{number:04d}",
                "units": [unit["unit_id"] for unit in current],
                "repositories": sorted({unit["repository"] for unit in current}),
                "unit_count": len(current),
                "files": sum(unit["stats"]["files"] for unit in current),
                "baseline_primary_retained": sum(unit["stats"]["baseline_primary_retained"] for unit in current),
            }
        )
        current = []
        primary_count = 0

    for unit in units:
        weight = int(unit["stats"]["baseline_primary_retained"])
        if current and (len(current) >= BATCH_UNIT_TARGET or primary_count + weight > BATCH_PRIMARY_FILE_TARGET):
            flush()
        current.append(unit)
        primary_count += weight
        if weight >= BATCH_PRIMARY_FILE_TARGET:
            flush()
    flush()
    dump_jsonl(BATCHES, batches)


def validate_review_record(record: dict[str, Any], unit: dict[str, Any], history_index: int, previous: dict[str, Any] | None) -> list[str]:
    errors: list[str] = []
    unit_id = unit["unit_id"]
    review_id = record.get("review_id")
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{unit_id}: review {history_index} has unsupported schema_version")
    if record.get("unit_id") != unit_id or record.get("repository") != unit["repository"]:
        errors.append(f"{unit_id}: review {history_index} targets the wrong unit/repository")
    if not isinstance(review_id, str) or not REVIEW_ID_RE.fullmatch(review_id) or review_id.split("-")[1] != unit_id.split("-")[1]:
        errors.append(f"{unit_id}: invalid review_id {review_id!r}")
    expected_revision = history_index + 1
    if review_id != f"RRV-{unit_id.split('-', 1)[1]}-r{expected_revision}":
        errors.append(f"{unit_id}: review IDs must be contiguous revisions starting at r1")
    if previous is None:
        if record.get("supersedes") not in {None, ""}:
            errors.append(f"{unit_id}: first review must not supersede another record")
    elif record.get("supersedes") != previous.get("review_id"):
        errors.append(f"{unit_id}: review {review_id} must supersede {previous.get('review_id')}")
    if record.get("status") not in {"reviewed", "deferred"}:
        errors.append(f"{unit_id}: status must be reviewed or deferred")
    expected_default = "retain" if record.get("status") == "reviewed" else "defer"
    if record.get("default_action") != expected_default:
        errors.append(f"{unit_id}: {record.get('status')} review must use default_action={expected_default}")
    if not isinstance(record.get("summary"), str) or len(record["summary"].strip()) < 20:
        errors.append(f"{unit_id}: review summary must explain the disposition")
    if not isinstance(record.get("recorded_at"), str) or "T" not in record["recorded_at"]:
        errors.append(f"{unit_id}: review requires recorded_at timestamp")
    if not isinstance(record.get("corpus_git_commit"), str) or len(record["corpus_git_commit"]) < 7:
        errors.append(f"{unit_id}: review requires corpus_git_commit")
    if not isinstance(record.get("unit_snapshot_sha256"), str) or len(record["unit_snapshot_sha256"]) != 64:
        errors.append(f"{unit_id}: review requires unit_snapshot_sha256")

    unit_records = load_unit_file_records(unit)
    paths = {str(item["path"]) for item in unit_records}
    matched: set[str] = set()
    rule_ids: set[str] = set()
    for rule_number, rule in enumerate(record.get("rules", []), start=1):
        rule_id = rule.get("rule_id")
        expected_rule = f"RRX-{unit_id.split('-', 1)[1]}-{rule_number}"
        if rule_id != expected_rule or not RULE_ID_RE.fullmatch(str(rule_id)):
            errors.append(f"{unit_id}: rule {rule_number} must have rule_id {expected_rule}")
        if rule_id in rule_ids:
            errors.append(f"{unit_id}: duplicate rule_id {rule_id}")
        rule_ids.add(str(rule_id))
        if rule.get("action") != "primary-exclude":
            errors.append(f"{unit_id}/{rule_id}: only primary-exclude rules are supported")
        selector = rule.get("selector") or {}
        kind = selector.get("kind")
        if kind not in {"exact-path", "path-set", "path-prefix"}:
            errors.append(f"{unit_id}/{rule_id}: selector must be exact-path, path-set, or path-prefix")
        if kind == "path-set" and (not isinstance(selector.get("paths"), list) or not selector.get("paths")):
            errors.append(f"{unit_id}/{rule_id}: path-set must contain paths")
        selected = selector_paths(selector, paths)
        specified: set[str] = set()
        if kind == "exact-path":
            specified = {str(selector.get("path", ""))}
        elif kind == "path-set":
            specified = {str(value) for value in selector.get("paths", [])}
        if specified - paths:
            errors.append(f"{unit_id}/{rule_id}: selector names paths outside the unit: {sorted(specified - paths)[:5]}")
        if not selected:
            errors.append(f"{unit_id}/{rule_id}: selector matches no unit files")
        overlap = matched & selected
        if overlap:
            errors.append(f"{unit_id}: rules overlap on {sorted(overlap)[:5]}")
        matched |= selected
        for field in ("rationale", "content_invariant"):
            if not isinstance(rule.get(field), str) or len(rule[field].strip()) < 30:
                errors.append(f"{unit_id}/{rule_id}: {field} must state explicit reasoning")
        evidence = rule.get("evidence")
        if not isinstance(evidence, list) or not evidence or any(not isinstance(item, str) or not item.strip() for item in evidence):
            errors.append(f"{unit_id}/{rule_id}: evidence must be a nonempty list of strings")
        policies = rule.get("policies")
        required = {"FILTER-002", "FILTER-004", "FILTER-005", "FILTER-018", "FILTER-020", "FILTER-022", "FILTER-023", "FILTER-024", "FILTER-025"}
        if not isinstance(policies, list) or not required.issubset(set(policies)):
            errors.append(f"{unit_id}/{rule_id}: policies must include repository-review safety rules")
    if record.get("status") == "deferred" and record.get("rules"):
        errors.append(f"{unit_id}: deferred review cannot activate exclusion rules")
    return errors


def validate() -> int:
    errors: list[str] = []
    source_rows = {source.repository: source for source in sources()}
    index = load_catalogue_index()
    if len(index) != len(source_rows):
        errors.append(f"catalogue has {len(index)} sources but sources.tsv has {len(source_rows)}")
    if len({row.get('repository') for row in index}) != len(index):
        errors.append("catalogue index has duplicate repositories")

    units = load_units()
    if len(units) != sum(int(row.get("work_units", 0)) for row in index):
        errors.append("catalogue unit IDs are not unique")

    for row in index:
        repository = row["repository"]
        source = source_rows.get(repository)
        if source is None:
            errors.append(f"catalogue contains unregistered repository {repository}")
            continue
        cat_path = ROOT / row["catalogue_file"]
        if not cat_path.is_file():
            errors.append(f"{repository}: missing catalogue file")
            continue
        catalogue = json.loads(cat_path.read_text())
        actual_revision = source_revision(source)
        if catalogue.get("source_revision") != actual_revision:
            errors.append(
                f"{repository}: source revision changed since review catalogue "
                f"({catalogue.get('source_revision')!r} -> {actual_revision!r}); run `just repository-review-catalogue`"
            )
        if source.transport == "web-dir":
            current_records = source_records(source, active_decisions_by_file())
            current_digest = material_snapshot_sha256(current_records)
            if current_digest != catalogue.get("source_snapshot_sha256"):
                errors.append(
                    f"{repository}: web-directory material changed since review catalogue; "
                    "run `just repository-review-catalogue`"
                )
        seen_paths: set[str] = set()
        source_records_for_digest = []
        for unit in catalogue.get("work_units", []):
            uid = unit.get("unit_id")
            if not isinstance(uid, str) or not UNIT_ID_RE.fullmatch(uid):
                errors.append(f"{repository}: invalid unit id {uid!r}")
                continue
            manifest = ROOT / unit["files_manifest"]
            if not manifest.is_file():
                errors.append(f"{uid}: missing files manifest")
                continue
            records = load_unit_file_records({"files_manifest": unit["files_manifest"]})
            unit_paths = [str(item["path"]) for item in records]
            overlap = seen_paths & set(unit_paths)
            if overlap:
                errors.append(f"{repository}: work units overlap on {sorted(overlap)[:5]}")
            seen_paths.update(unit_paths)
            # Reconstruct digest from committed rows without touching source bytes.
            from repository_review_lib import FileRecord, material_snapshot_sha256
            reconstructed = [
                FileRecord(
                    path=str(item["path"]), size_bytes=int(item["size_bytes"]), sha256=str(item["sha256"]),
                    formal_source=bool(item["formal_source"]), active_decisions=tuple(item.get("active_decisions", [])),
                    baseline_primary_status=str(item["baseline_primary_status"]), current_primary_status=str(item["current_primary_status"]),
                ) for item in records
            ]
            digest = material_snapshot_sha256(reconstructed)
            if digest != unit.get("snapshot_sha256"):
                errors.append(f"{uid}: manifest digest disagrees with catalogue")
            source_records_for_digest.extend(reconstructed)
            history = load_review_history(repository, uid)
            previous = None
            for review_number, review in enumerate(history):
                errors.extend(validate_review_record(review, {**unit, "repository": repository}, review_number, previous))
                previous = review
            if history and history[-1].get("status") == "reviewed" and history[-1].get("unit_snapshot_sha256") != unit.get("snapshot_sha256"):
                errors.append(f"{uid}: reviewed unit changed; append a new review revision before indexing")
        source_digest = material_snapshot_sha256(source_records_for_digest)
        if source_digest != catalogue.get("source_snapshot_sha256"):
            errors.append(f"{repository}: source snapshot digest disagrees with unit manifests")
        if len(seen_paths) != int(catalogue.get("totals", {}).get("files", -1)):
            errors.append(f"{repository}: unit coverage count disagrees with source totals")

    # Reviews for vanished units must not be silently abandoned.
    if REVIEWS_ROOT.exists():
        for path in REVIEWS_ROOT.glob("*/*.jsonl"):
            uid = path.stem
            if uid not in units:
                errors.append(f"orphan review history for vanished unit {uid}: {relative(path)}")

    exclusions, exclusion_errors = resolve_review_exclusions(require_fresh=True)
    errors.extend(exclusion_errors)

    batches = [json.loads(line) for line in BATCHES.read_text().splitlines() if line.strip()] if BATCHES.exists() else []
    batched_units = [uid for batch in batches for uid in batch.get("units", [])]
    if set(batched_units) != set(units) or len(batched_units) != len(set(batched_units)):
        errors.append("batches.jsonl must cover every work unit exactly once")

    if errors:
        for error in errors[:100]:
            print(f"ERROR: {error}", file=sys.stderr)
        if len(errors) > 100:
            print(f"ERROR: ... {len(errors) - 100} additional errors", file=sys.stderr)
        return 1

    reviews = latest_reviews(units)
    reviewed = sum(
        review.get("status") == "reviewed" and review.get("unit_snapshot_sha256") == units[uid].get("snapshot_sha256")
        for uid, review in reviews.items()
    )
    deferred = sum(review.get("status") == "deferred" for review in reviews.values())
    print(
        f"repository review catalogue ok: {len(index)} sources, {len(units)} units, "
        f"{reviewed} reviewed, {deferred} deferred, {len(exclusions)} explicitly excluded files"
    )
    return 0


def status(batch_id: str | None = None) -> int:
    units = load_units()
    reviews = latest_reviews(units)
    selected = set(units)
    if batch_id:
        batches = [json.loads(line) for line in BATCHES.read_text().splitlines() if line.strip()]
        batch = next((item for item in batches if item["batch_id"] == batch_id), None)
        if batch is None:
            raise SystemExit(f"unknown batch {batch_id}")
        selected = set(batch["units"])
    counts = collections.Counter()
    rows = []
    for uid in sorted(selected, key=lambda value: (units[value]["repository"], units[value]["scope"]["value"])):
        unit = units[uid]
        review = reviews.get(uid)
        state = "pending"
        if review:
            state = str(review.get("status"))
            if review.get("unit_snapshot_sha256") != unit.get("snapshot_sha256"):
                state = "stale"
        counts[state] += 1
        rows.append((state, uid, unit["repository"], unit["scope"]["value"] or ".", unit["stats"]["files"], unit["stats"]["baseline_primary_retained"]))
    print("state\tunit\trepository\tscope\tfiles\tprimary")
    for row in rows:
        print("\t".join(map(str, row)))
    print("summary", dict(sorted(counts.items())), file=sys.stderr)
    return 0


def template(uid: str) -> int:
    units = load_units()
    unit = units.get(uid)
    if unit is None:
        raise SystemExit(f"unknown unit {uid}")
    history = load_review_history(unit["repository"], uid)
    revision = len(history) + 1
    short = uid.split("-", 1)[1]
    record = {
        "schema_version": SCHEMA_VERSION,
        "review_id": f"RRV-{short}-r{revision}",
        "unit_id": uid,
        "repository": unit["repository"],
        "source_revision": unit.get("source_revision"),
        "unit_snapshot_sha256": unit["snapshot_sha256"],
        "supersedes": history[-1]["review_id"] if history else None,
        "status": "reviewed",
        "default_action": "retain",
        "summary": "REPLACE: explain what was inspected and why unselected material remains searchable.",
        "recorded_at": utc_now(),
        "corpus_git_commit": corpus_commit(),
        "rules": [
            {
                "rule_id": f"RRX-{short}-1",
                "action": "primary-exclude",
                "selector": {"kind": "exact-path", "path": "REPLACE"},
                "rationale": "REPLACE: repository-local reason this exact material should not occupy formalization search.",
                "content_invariant": "REPLACE: explain why this selector cannot hide unique definitions, statements, proofs, interfaces, or useful formal search evidence.",
                "evidence": ["REPLACE: concrete source-local evidence"],
                "policies": [
                    "FILTER-002", "FILTER-004", "FILTER-005", "FILTER-018", "FILTER-020",
                    "FILTER-022", "FILTER-023", "FILTER-024", "FILTER-025",
                ],
            }
        ],
    }
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def append_review(path: pathlib.Path) -> int:
    record = json.loads(path.read_text())
    units = load_units()
    uid = str(record.get("unit_id", ""))
    unit = units.get(uid)
    if unit is None:
        raise SystemExit(f"review targets unknown unit {uid!r}")
    history = load_review_history(unit["repository"], uid)
    previous = history[-1] if history else None
    errors = validate_review_record(record, unit, len(history), previous)
    if record.get("unit_snapshot_sha256") != unit.get("snapshot_sha256"):
        errors.append(f"{uid}: proposed review is not pinned to the current unit snapshot")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    destination = review_path(unit["repository"], uid)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    print(destination)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and audit repository-local filtering review work")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    sub.add_parser("validate")
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--batch")
    template_parser = sub.add_parser("template")
    template_parser.add_argument("unit")
    append_parser = sub.add_parser("append")
    append_parser.add_argument("review", type=pathlib.Path)
    args = parser.parse_args()
    if args.command == "build":
        return build()
    if args.command == "validate":
        return validate()
    if args.command == "status":
        return status(args.batch)
    if args.command == "template":
        return template(args.unit)
    return append_review(args.review)


if __name__ == "__main__":
    raise SystemExit(main())
