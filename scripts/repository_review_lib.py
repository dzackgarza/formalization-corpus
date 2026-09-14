#!/usr/bin/env python3
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Iterable

from filtering_lib import CURRENT, FILTER_ROOT, ROOT, is_formal_file, iter_files, load_jsonl, sha256_file, source_revision, sources

REVIEW_ROOT = FILTER_ROOT / "repository-review"
CATALOGUE_ROOT = REVIEW_ROOT / "catalogue"
FILES_ROOT = REVIEW_ROOT / "files"
REVIEWS_ROOT = REVIEW_ROOT / "reviews"
CATALOGUE_INDEX = REVIEW_ROOT / "catalogue.jsonl"
BATCHES = REVIEW_ROOT / "batches.jsonl"

SCHEMA_VERSION = 1
SOURCE_SPLIT_FILE_THRESHOLD = 2_000
SOURCE_SPLIT_BYTE_THRESHOLD = 256 * 1024 * 1024
LEAF_FILE_TARGET = 2_000
LEAF_BYTE_TARGET = 256 * 1024 * 1024
BATCH_UNIT_TARGET = 12
BATCH_PRIMARY_FILE_TARGET = 3_000

UNIT_ID_RE = re.compile(r"^RRU-[0-9a-f]{12}$")
REVIEW_ID_RE = re.compile(r"^RRV-[0-9a-f]{12}-r[1-9][0-9]*$")
RULE_ID_RE = re.compile(r"^RRX-[0-9a-f]{12}-[1-9][0-9]*$")


@dataclass(frozen=True)
class FileRecord:
    path: str
    size_bytes: int
    sha256: str
    formal_source: bool
    active_decisions: tuple[str, ...]
    baseline_primary_status: str
    current_primary_status: str

    def as_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "formal_source": self.formal_source,
            "active_decisions": list(self.active_decisions),
            "baseline_primary_status": self.baseline_primary_status,
            "current_primary_status": self.current_primary_status,
        }


@dataclass(frozen=True)
class Unit:
    repository: str
    unit_id: str
    scope_kind: str
    scope_value: str
    scope_roots: tuple[str, ...]
    records: tuple[FileRecord, ...]

    @property
    def snapshot_sha256(self) -> str:
        return material_snapshot_sha256(self.records)

    def stats(self) -> dict[str, int]:
        statuses = collections.Counter(record.current_primary_status for record in self.records)
        baseline = collections.Counter(record.baseline_primary_status for record in self.records)
        return {
            "files": len(self.records),
            "bytes": sum(record.size_bytes for record in self.records),
            "formal_source_files": sum(record.formal_source for record in self.records),
            "baseline_primary_retained": baseline["primary-retained"],
            "current_primary_retained": statuses["primary-retained"],
            "current_primary_excluded": statuses["primary-excluded"],
            "auxiliary_only": statuses["auxiliary-only"],
            "unindexed_nonformal": statuses["unindexed-nonformal"],
        }


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def corpus_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def stable_id(prefix: str, *parts: str) -> str:
    payload = "\0".join(parts).encode()
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:12]}"


def unit_id(repository: str, scope_kind: str, scope_identity: str) -> str:
    return stable_id("RRU", repository, scope_kind, scope_identity)


def material_snapshot_sha256(records: Iterable[FileRecord]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item.path):
        digest.update(record.path.encode())
        digest.update(b"\0")
        digest.update(str(record.size_bytes).encode())
        digest.update(b"\0")
        digest.update(record.sha256.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def active_decisions_by_file() -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in load_jsonl(CURRENT):
        out[(str(row["repository"]), str(row["file"]))].append(row)
    for rows in out.values():
        rows.sort(key=lambda row: str(row["decision_id"]))
    return out


def classify_status(formal: bool, decisions: list[dict[str, Any]], *, ignore_review: bool) -> str:
    rows = [row for row in decisions if not (ignore_review and row.get("decision_id") == "FD-018")]
    primary_excluded = any(row.get("primary") == "exclude" for row in rows)
    auxiliary_included = any(row.get("auxiliary") == "include" for row in rows)
    if formal and not primary_excluded:
        return "primary-retained"
    if primary_excluded and auxiliary_included:
        return "auxiliary-only"
    if primary_excluded:
        return "primary-excluded"
    return "unindexed-nonformal"


def source_records(source: Any, decisions: dict[tuple[str, str], list[dict[str, Any]]]) -> list[FileRecord]:
    records: list[FileRecord] = []
    for path in iter_files(source):
        rel = path.relative_to(source.root).as_posix()
        size = path.stat().st_size
        digest = sha256_file(path)
        formal = is_formal_file(source.proof_assistant, path)
        rows = decisions.get((source.repository, rel), [])
        records.append(
            FileRecord(
                path=rel,
                size_bytes=size,
                sha256=digest,
                formal_source=formal,
                active_decisions=tuple(str(row["decision_id"]) for row in rows),
                baseline_primary_status=classify_status(formal, rows, ignore_review=True),
                current_primary_status=classify_status(formal, rows, ignore_review=False),
            )
        )
    records.sort(key=lambda record: record.path)
    return records


def _fits(records: Iterable[FileRecord]) -> bool:
    rows = list(records)
    return len(rows) <= LEAF_FILE_TARGET and sum(record.size_bytes for record in rows) <= LEAF_BYTE_TARGET


def _make_unit(
    repository: str,
    kind: str,
    identity: str,
    roots: tuple[str, ...],
    records: list[FileRecord],
) -> Unit:
    records = sorted(records, key=lambda record: record.path)
    if kind == "repository":
        display = "."
    elif kind in {"subtree", "direct-files"} and len(roots) == 1:
        display = roots[0]
    elif kind in {"subtree-bucket", "file-bucket"}:
        display = identity
    elif len(roots) == 1:
        display = roots[0]
    else:
        display = f"{roots[0]} .. {roots[-1]} ({len(roots)} roots)"
    return Unit(
        repository=repository,
        unit_id=unit_id(repository, kind, identity),
        scope_kind=kind,
        scope_value=display,
        scope_roots=roots,
        records=tuple(records),
    )


def _stable_bucket_units(
    repository: str,
    *,
    parent_identity: str,
    kind: str,
    items: list[tuple[str, list[FileRecord]]],
    hash_prefix: str = "",
) -> list[Unit]:
    """Partition review items without order-sensitive packing.

    Existing items stay in the same hash bucket when a sibling is added.  Only
    the affected bucket may need to split further, so unrelated completed reviews
    do not become stale merely because lexical ordering changed elsewhere.
    """
    if not items:
        return []
    records = [record for _, rows in items for record in rows]
    roots = tuple(sorted(key for key, _ in items))
    if _fits(records):
        identity = f"{parent_identity}/@{kind}/{hash_prefix or 'all'}"
        unit_kind = "file-bucket" if kind == "files" else "subtree-bucket"
        return [_make_unit(repository, unit_kind, identity, roots, records)]

    buckets: dict[str, list[tuple[str, list[FileRecord]]]] = collections.defaultdict(list)
    depth = len(hash_prefix)
    for key, rows in items:
        digest = hashlib.sha256(key.encode()).hexdigest()
        buckets[digest[depth]].append((key, rows))

    # Hash collisions cannot recurse forever in practice, but fail closed if all
    # keys have the same full digest prefix instead of manufacturing an unstable
    # order-based split.
    if depth >= 63 and len(buckets) == 1:
        raise ValueError(f"cannot stably partition oversized review bucket {parent_identity}/{hash_prefix}")

    units: list[Unit] = []
    for nibble in sorted(buckets):
        units.extend(
            _stable_bucket_units(
                repository,
                parent_identity=parent_identity,
                kind=kind,
                items=buckets[nibble],
                hash_prefix=hash_prefix + nibble,
            )
        )
    return units


def _partition_direct_files(repository: str, prefix: tuple[str, ...], records: list[FileRecord]) -> list[Unit]:
    if not records:
        return []
    parent = "/".join(prefix) or "."
    if _fits(records):
        roots = tuple(record.path for record in sorted(records, key=lambda record: record.path))
        kind = "direct-files" if len(records) == 1 else "file-bucket"
        return [_make_unit(repository, kind, f"{parent}/@files/all", roots, records)]
    return _stable_bucket_units(
        repository,
        parent_identity=parent,
        kind="files",
        items=[(record.path, [record]) for record in records],
    )


def _split_records(repository: str, records: list[FileRecord], prefix: tuple[str, ...] = ()) -> list[Unit]:
    if _fits(records):
        value = "/".join(prefix)
        kind = "repository" if not prefix else "subtree"
        roots = () if not prefix else (value,)
        identity = "." if not prefix else value
        return [_make_unit(repository, kind, identity, roots, records)]

    direct: list[FileRecord] = []
    children: dict[str, list[FileRecord]] = collections.defaultdict(list)
    depth = len(prefix)
    for record in records:
        parts = pathlib.PurePosixPath(record.path).parts
        if len(parts) <= depth + 1:
            direct.append(record)
        else:
            children[parts[depth]].append(record)

    units = _partition_direct_files(repository, prefix, direct)
    if not children:
        return units

    small_groups: list[tuple[str, list[FileRecord]]] = []
    for child in sorted(children):
        child_records = children[child]
        child_prefix = (*prefix, child)
        root = "/".join(child_prefix)
        if _fits(child_records):
            small_groups.append((root, child_records))
        else:
            units.extend(_split_records(repository, child_records, child_prefix))

    if small_groups:
        parent = "/".join(prefix) or "."
        units.extend(
            _stable_bucket_units(
                repository,
                parent_identity=parent,
                kind="subtrees",
                items=small_groups,
            )
        )
    return units


def partition_source(repository: str, records: list[FileRecord]) -> list[Unit]:
    total_bytes = sum(record.size_bytes for record in records)
    if len(records) <= SOURCE_SPLIT_FILE_THRESHOLD and total_bytes <= SOURCE_SPLIT_BYTE_THRESHOLD:
        return [_make_unit(repository, "repository", ".", (), records)]
    units = _split_records(repository, records)
    units.sort(key=lambda unit: (unit.scope_value, unit.unit_id))
    return units


def catalogue_path(repository: str) -> pathlib.Path:
    return CATALOGUE_ROOT / f"{repository}.json"


def unit_files_path(repository: str, unit_id_value: str) -> pathlib.Path:
    return FILES_ROOT / repository / f"{unit_id_value}.jsonl"


def review_path(repository: str, unit_id_value: str) -> pathlib.Path:
    return REVIEWS_ROOT / repository / f"{unit_id_value}.jsonl"


def dump_jsonl(path: pathlib.Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def load_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_catalogue_index() -> list[dict[str, Any]]:
    return load_jsonl(CATALOGUE_INDEX)


def load_units() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for source_row in load_catalogue_index():
        source_catalogue = load_json(ROOT / source_row["catalogue_file"])
        for unit in source_catalogue.get("work_units", []):
            item = dict(unit)
            item["repository"] = source_catalogue["repository"]
            item["proof_assistant"] = source_catalogue["proof_assistant"]
            item["source_revision"] = source_catalogue.get("source_revision")
            item["source_snapshot_sha256"] = source_catalogue["source_snapshot_sha256"]
            item["catalogue_file"] = source_row["catalogue_file"]
            out[item["unit_id"]] = item
    return out


def load_unit_file_records(unit: dict[str, Any]) -> list[dict[str, Any]]:
    return load_jsonl(ROOT / unit["files_manifest"])


def load_review_history(repository: str, unit_id_value: str) -> list[dict[str, Any]]:
    return load_jsonl(review_path(repository, unit_id_value))


def latest_reviews(units: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    units = units or load_units()
    out: dict[str, dict[str, Any]] = {}
    for unit_id_value, unit in units.items():
        history = load_review_history(unit["repository"], unit_id_value)
        if history:
            out[unit_id_value] = history[-1]
    return out


def selector_paths(selector: dict[str, Any], paths: set[str]) -> set[str]:
    kind = selector.get("kind")
    if kind == "exact-path":
        value = str(selector.get("path", ""))
        return {value} if value in paths else set()
    if kind == "path-set":
        values = {str(value) for value in selector.get("paths", [])}
        return values & paths
    if kind == "path-prefix":
        prefix = str(selector.get("prefix", "")).rstrip("/")
        if not prefix:
            return set()
        return {path for path in paths if path == prefix or path.startswith(prefix + "/")}
    return set()


def resolve_review_exclusions(*, require_fresh: bool = True) -> tuple[dict[tuple[str, str], dict[str, Any]], list[str]]:
    units = load_units()
    reviews = latest_reviews(units)
    exclusions: dict[tuple[str, str], dict[str, Any]] = {}
    errors: list[str] = []
    for unit_id_value, review in reviews.items():
        unit = units[unit_id_value]
        if review.get("status") != "reviewed":
            continue
        if review.get("unit_snapshot_sha256") != unit.get("snapshot_sha256"):
            if require_fresh:
                errors.append(f"{unit_id_value}: latest review is stale for current unit snapshot")
            continue
        records = load_unit_file_records(unit)
        by_path = {str(record["path"]): record for record in records}
        paths = set(by_path)
        matched_in_unit: set[str] = set()
        for rule in review.get("rules", []):
            if rule.get("action") != "primary-exclude":
                continue
            matched = selector_paths(rule.get("selector") or {}, paths)
            if not matched:
                errors.append(f"{unit_id_value}/{rule.get('rule_id')}: selector matches no files")
                continue
            for path in sorted(matched):
                record = by_path[path]
                if record.get("baseline_primary_status") != "primary-retained":
                    errors.append(
                        f"{unit_id_value}/{rule.get('rule_id')}: {path} is not baseline primary-retained"
                    )
                    continue
                if path in matched_in_unit:
                    errors.append(f"{unit_id_value}: overlapping exclusion rules match {path}")
                    continue
                matched_in_unit.add(path)
                key = (unit["repository"], path)
                exclusions[key] = {
                    "review_id": review["review_id"],
                    "unit_id": unit_id_value,
                    "rule_id": rule["rule_id"],
                    "selector": rule["selector"],
                    "rationale": rule["rationale"],
                    "content_invariant": rule["content_invariant"],
                    "evidence": rule["evidence"],
                    "unit_snapshot_sha256": unit["snapshot_sha256"],
                    "file_sha256": record["sha256"],
                    "file_size_bytes": record["size_bytes"],
                }
    return exclusions, errors
