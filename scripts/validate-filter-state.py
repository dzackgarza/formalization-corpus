#!/usr/bin/env python3
"""Validate the reversible filtering record and its derived snapshots."""

from __future__ import annotations

import collections
import json
import sys
from typing import Any

from filtering_lib import (
    CURRENT,
    DUPLICATES,
    SNAPSHOT,
    load_filter_ledger,
    load_catalog,
    load_jsonl,
    source_revision,
    sources,
)
from repository_review_lib import resolve_review_exclusions


EVENT_ONLY = {
    "ledger_event",
    "recorded_at",
    "event_reason",
    "reverted_by_corpus_git_commit",
}

SCAN_EPHEMERAL = {"observed_at", "corpus_git_commit"}


def file_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["repository"], row["file"], row["decision_id"]


def file_payload(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if key not in EVENT_ONLY}


def stable_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Fields that define the decision, excluding latest-scan provenance.

    ``build-filter-state.py`` intentionally does not append an ``updated`` event
    merely because the same decision was re-observed at a later corpus commit.
    The current snapshot therefore carries the latest scan timestamp/commit,
    while the ledger retains the event that actually changed the decision.
    """
    return {key: value for key, value in row.items() if key not in SCAN_EPHEMERAL}


def validate_state(
    *,
    catalog: dict[str, dict[str, Any]],
    ledger: list[dict[str, Any]],
    current: list[dict[str, Any]],
    duplicates: dict[str, Any],
    snapshot: dict[str, Any],
    registered_repositories: set[str],
) -> list[str]:
    errors: list[str] = []

    active: dict[tuple[str, str, str], dict[str, Any]] = {}
    source_state: dict[str, str] = {}
    for number, event in enumerate(ledger, start=1):
        decision_id = event.get("decision_id")
        if decision_id not in catalog:
            errors.append(f"ledger line {number}: unknown decision {decision_id!r}")
            continue

        if event.get("scope") == "source":
            action = event.get("ledger_event")
            if action not in {"removed-from-corpus", "restored-to-corpus"}:
                errors.append(f"ledger line {number}: unsupported source event {action!r}")
            else:
                source_state[event["repository"]] = action
            continue

        if "file" not in event:
            errors.append(f"ledger line {number}: file decision has no file path")
            continue
        key = file_key(event)
        action = event.get("ledger_event")
        if action in {"applied", "updated"}:
            active[key] = file_payload(event)
        elif action == "reverted":
            if key not in active:
                errors.append(f"ledger line {number}: reverts inactive decision {key}")
            active.pop(key, None)
        else:
            errors.append(f"ledger line {number}: unsupported file event {action!r}")

    current_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for number, row in enumerate(current, start=1):
        decision_id = row.get("decision_id")
        if decision_id not in catalog:
            errors.append(f"current line {number}: unknown decision {decision_id!r}")
            continue
        try:
            key = file_key(row)
        except KeyError as exc:
            errors.append(f"current line {number}: missing {exc.args[0]}")
            continue
        if key in current_by_key:
            errors.append(f"current line {number}: duplicate decision key {key}")
            continue
        current_by_key[key] = row

        definition = catalog[decision_id]
        for field in ("title", "primary", "auxiliary", "policies", "justification"):
            if row.get(field) != definition.get(field):
                errors.append(f"current line {number}: {key} has stale catalog field {field}")
        if row.get("result_action") != definition.get("result_action"):
            errors.append(f"current line {number}: {key} has stale result_action")

    if set(active) != set(current_by_key):
        missing = sorted(set(active) - set(current_by_key))[:10]
        extra = sorted(set(current_by_key) - set(active))[:10]
        if missing:
            errors.append(f"current snapshot omits active ledger decisions: {missing}")
        if extra:
            errors.append(f"current snapshot contains decisions absent from ledger replay: {extra}")
    for key in sorted(set(active) & set(current_by_key)):
        if stable_payload(active[key]) != stable_payload(current_by_key[key]):
            errors.append(f"current snapshot disagrees with ledger replay for {key}")
            if len(errors) >= 50:
                break

    for repository, state in sorted(source_state.items()):
        if state == "removed-from-corpus" and repository in registered_repositories:
            errors.append(
                f"{repository}: latest source ledger event removes it, but sources.tsv still registers it"
            )
        if state == "restored-to-corpus" and repository not in registered_repositories:
            errors.append(
                f"{repository}: latest source ledger event restores it, but sources.tsv omits it"
            )

    counts = dict(collections.Counter(row["decision_id"] for row in current))
    if snapshot.get("decision_counts") != counts:
        errors.append("snapshot decision_counts does not match current.jsonl")
    if snapshot.get("sources_with_no_primary_documents"):
        errors.append(
            "snapshot records registered sources with no primary documents: "
            + ", ".join(snapshot["sources_with_no_primary_documents"])
        )
    eligible_counts = snapshot.get("primary_eligible_counts_by_source") or {}
    if set(eligible_counts) != registered_repositories:
        missing = sorted(registered_repositories - set(eligible_counts))[:10]
        extra = sorted(set(eligible_counts) - registered_repositories)[:10]
        if missing:
            errors.append(f"snapshot lacks registered sources: {missing}")
        if extra:
            errors.append(f"snapshot contains unregistered sources: {extra}")
    empty_counts = sorted(repo for repo, count in eligible_counts.items() if count <= 0)
    if empty_counts:
        errors.append(f"snapshot has nonpositive primary counts: {empty_counts[:10]}")

    if duplicates.get("schema_version") != 1:
        errors.append("duplicate-aliases.json has unsupported schema_version")
    groups = duplicates.get("groups") or []
    group_by_hash: dict[str, dict[str, Any]] = {}
    occurrence_keys: set[tuple[str, str, str]] = set()
    for number, group in enumerate(groups, start=1):
        digest = group.get("sha256")
        occurrences = group.get("occurrences") or []
        if not isinstance(digest, str) or len(digest) != 64:
            errors.append(f"duplicate group {number}: invalid sha256")
            continue
        if digest in group_by_hash:
            errors.append(f"duplicate group {number}: repeated digest {digest}")
        group_by_hash[digest] = group
        if len(occurrences) < 2:
            errors.append(f"duplicate group {number}: fewer than two occurrences")
        canonical = group.get("canonical") or {}
        canonical_pair = (canonical.get("repository"), canonical.get("file"))
        occurrence_pairs = [(item.get("repository"), item.get("file")) for item in occurrences]
        if canonical_pair not in occurrence_pairs:
            errors.append(f"duplicate group {number}: canonical occurrence is absent")
        if len(set(occurrence_pairs)) != len(occurrence_pairs):
            errors.append(f"duplicate group {number}: repeated source/path occurrence")
        for repository, file in occurrence_pairs:
            occurrence_keys.add((repository, file, "FD-006"))

    fd006_keys = {key for key in current_by_key if key[2] == "FD-006"}
    if occurrence_keys != fd006_keys:
        missing = sorted(occurrence_keys - fd006_keys)[:10]
        extra = sorted(fd006_keys - occurrence_keys)[:10]
        if missing:
            errors.append(f"duplicate alias map has occurrences without FD-006 decisions: {missing}")
        if extra:
            errors.append(f"FD-006 decisions absent from duplicate alias map: {extra}")
    for key in sorted(fd006_keys):
        row = current_by_key[key]
        digest = row.get("content_sha256")
        evidence = row.get("evidence") or {}
        group = group_by_hash.get(digest)
        if group is None:
            errors.append(f"{key}: duplicate decision references unknown hash {digest}")
            continue
        if evidence.get("sha256") != digest:
            errors.append(f"{key}: FD-006 evidence hash disagrees with content hash")
        if evidence.get("group_size") != len(group["occurrences"]):
            errors.append(f"{key}: FD-006 group_size disagrees with alias map")
        if evidence.get("canonical") != group["canonical"]:
            errors.append(f"{key}: FD-006 canonical target disagrees with alias map")

    duplicate_occurrences = sum(len(group.get("occurrences") or []) for group in groups)
    if snapshot.get("duplicate_groups") != len(groups):
        errors.append("snapshot duplicate_groups does not match duplicate-aliases.json")
    if snapshot.get("duplicate_occurrences") != duplicate_occurrences:
        errors.append("snapshot duplicate_occurrences does not match duplicate-aliases.json")
    if counts.get("FD-006", 0) != duplicate_occurrences:
        errors.append("FD-006 count does not equal duplicate occurrence count")

    return errors


def main() -> int:
    catalog = load_catalog()
    ledger = load_filter_ledger()
    current = load_jsonl(CURRENT)
    duplicates = json.loads(DUPLICATES.read_text())
    snapshot = json.loads(SNAPSHOT.read_text())
    source_rows = sources()
    registered = {source.repository for source in source_rows}
    errors = validate_state(
        catalog=catalog,
        ledger=ledger,
        current=current,
        duplicates=duplicates,
        snapshot=snapshot,
        registered_repositories=registered,
    )

    review_exclusions, review_errors = resolve_review_exclusions(require_fresh=True)
    errors.extend(review_errors)
    fd018_rows = {
        (str(row["repository"]), str(row["file"])): row
        for row in current
        if row.get("decision_id") == "FD-018"
    }
    if set(fd018_rows) != set(review_exclusions):
        missing = sorted(set(review_exclusions) - set(fd018_rows))[:10]
        extra = sorted(set(fd018_rows) - set(review_exclusions))[:10]
        if missing:
            errors.append(f"accepted repository-review exclusions lack FD-018 materialization: {missing}")
        if extra:
            errors.append(f"FD-018 decisions have no fresh repository-review rule: {extra}")
    for key in sorted(set(fd018_rows) & set(review_exclusions)):
        row = fd018_rows[key]
        expected = review_exclusions[key]
        evidence = row.get("evidence") or {}
        for field in ("review_id", "unit_id", "rule_id", "selector", "unit_snapshot_sha256", "rationale", "content_invariant"):
            if evidence.get(field) != expected.get(field):
                errors.append(f"{key}: FD-018 evidence field {field} disagrees with repository review")
        if evidence.get("review_evidence") != expected.get("evidence"):
            errors.append(f"{key}: FD-018 review_evidence disagrees with repository review")
        if row.get("content_sha256") != expected.get("file_sha256"):
            errors.append(f"{key}: FD-018 content hash disagrees with repository-review manifest")
        if evidence.get("size_bytes") != expected.get("file_size_bytes"):
            errors.append(f"{key}: FD-018 size disagrees with repository-review manifest")

    recorded_revisions = snapshot.get("source_revisions") or {}
    for source in source_rows:
        if not source.root.exists():
            continue
        actual = source_revision(source)
        expected = recorded_revisions.get(source.repository)
        if actual != expected:
            errors.append(
                f"{source.repository}: source revision changed since filtering snapshot "
                f"({expected!r} -> {actual!r}); run `just filter-state` before indexing"
            )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"filter state ok: {len(current)} active decisions, "
        f"{len(duplicates.get('groups') or [])} duplicate groups, "
        f"{len(registered)} registered sources"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
