#!/usr/bin/env python3
"""Refresh repository-review filtering without hydrating unrelated sources.

This is the normal long-horizon filtering path.  Repository-review manifests already
pin every imported file by path/size/SHA-256, so new FD-018 decisions can be derived
from those committed manifests.  Exact-duplicate result groups are recomputed from the
same manifests.  No unrelated source checkout is needed.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import subprocess
from typing import Any

from filtering_lib import (
    CURRENT,
    DUPLICATES,
    FILTER_ROOT,
    ROOT,
    SNAPSHOT,
    append_filter_ledger,
    dump_jsonl,
    load_catalog,
    load_jsonl,
    sources,
)
from repository_review_lib import (
    BATCHES,
    load_catalogue_index,
    load_unit_file_records,
    load_units,
    resolve_review_exclusions,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def corpus_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def decision_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return str(row["repository"]), str(row["file"]), str(row["decision_id"])


def stable_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"observed_at", "corpus_git_commit"}
    }


def decision_record(
    *,
    definition: dict[str, Any],
    decision_id: str,
    repository: str,
    file: str,
    proof_assistant: str,
    source_revision: str | None,
    content_sha256: str,
    evidence: dict[str, Any],
    observed_at: str,
    commit: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "repository": repository,
        "file": file,
        "proof_assistant": proof_assistant,
        "source_revision": source_revision,
        "decision_id": decision_id,
        "title": definition["title"],
        "primary": definition["primary"],
        "auxiliary": definition["auxiliary"],
        "result_action": definition.get("result_action"),
        "policies": definition["policies"],
        "justification": definition["justification"],
        "content_sha256": content_sha256,
        "evidence": evidence,
        "observed_at": observed_at,
        "corpus_git_commit": commit,
    }


def batch_repositories(batch_id: str) -> set[str]:
    rows = [json.loads(line) for line in BATCHES.read_text().splitlines() if line.strip()]
    batch = next((row for row in rows if row.get("batch_id") == batch_id), None)
    if batch is None:
        raise SystemExit(f"unknown review batch {batch_id}")
    return set(map(str, batch.get("repositories", [])))


def selected_repositories(values: list[str], batch: str | None = None) -> set[str]:
    active = {source.repository for source in sources()}
    campaign = {str(row["repository"]) for row in load_catalogue_index()}
    requested = set(values)
    if batch:
        requested.update(batch_repositories(batch))
    unknown = sorted(requested - campaign)
    if unknown:
        raise SystemExit(f"unknown campaign repositories: {unknown}")
    if not requested:
        raise SystemExit("at least one --repository is required")
    # Batch history is immutable, so a reviewed batch may contain a source that was
    # retired after its source-level review.  Keep accepting that frozen identity;
    # the caller will remove its old file decisions instead of trying to rematerialize it.
    return requested


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh FD-018 and exact-duplicate state from committed review manifests"
    )
    parser.add_argument("--repository", action="append", default=[])
    parser.add_argument("--batch")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    selected = selected_repositories(args.repository, args.batch)

    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True
    )
    if status.strip() and not args.allow_dirty:
        raise SystemExit("review-filter refresh requires a clean worktree; pass --allow-dirty only for an intentional in-flight batch")

    catalogue = load_catalog()
    units = load_units(active_only=True)
    by_repository: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for unit in units.values():
        by_repository[str(unit["repository"])].append(unit)

    exclusions, review_errors = resolve_review_exclusions(require_fresh=True)
    if review_errors:
        raise SystemExit("repository review state is invalid:\n  " + "\n  ".join(review_errors[:50]))

    old_rows = load_jsonl(CURRENT)
    old = {decision_key(row): row for row in old_rows}
    now = utc_now()
    commit = corpus_commit()
    active_repositories = {source.repository for source in sources()}
    active_selected = selected & active_repositories
    retired_selected = selected - active_repositories

    # Preserve every unrelated decision verbatim. FD-006 is global result-role
    # metadata and is recomputed below from committed file hashes. FD-018 for active
    # selected repositories is replaced from latest accepted review records. A source
    # retired during this batch loses *all* file-level decisions: the source-level
    # FD-012 ledger event is now its durable disposition and the old file rows must not
    # survive as apparently active state for an unregistered repository.
    current: list[dict[str, Any]] = [
        row
        for row in old_rows
        if row.get("decision_id") != "FD-006"
        and row.get("repository") not in retired_selected
        and not (
            row.get("decision_id") == "FD-018"
            and row.get("repository") in active_selected
        )
    ]

    repo_meta: dict[str, dict[str, Any]] = {}
    for row in load_catalogue_index():
        if row.get("inventory_status", "active") != "active":
            continue
        data = json.loads((ROOT / row["catalogue_file"]).read_text())
        repo_meta[str(data["repository"])] = data

    for (repository, path), exclusion in sorted(exclusions.items()):
        if repository not in active_selected:
            continue
        meta = repo_meta[repository]
        definition = catalogue["FD-018"]
        current.append(
            decision_record(
                definition=definition,
                decision_id="FD-018",
                repository=repository,
                file=path,
                proof_assistant=str(meta["proof_assistant"]),
                source_revision=meta.get("source_revision"),
                content_sha256=str(exclusion["file_sha256"]),
                evidence={
                    "review_id": exclusion["review_id"],
                    "unit_id": exclusion["unit_id"],
                    "rule_id": exclusion["rule_id"],
                    "selector": exclusion["selector"],
                    "unit_snapshot_sha256": exclusion["unit_snapshot_sha256"],
                    "size_bytes": exclusion["file_size_bytes"],
                    "rationale": exclusion["rationale"],
                    "content_invariant": exclusion["content_invariant"],
                    "review_evidence": exclusion["evidence"],
                },
                observed_at=now,
                commit=commit,
            )
        )

    rows_by_file: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in current:
        rows_by_file[(str(row["repository"]), str(row["file"]))].append(row)

    hashes: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    primary_counts: collections.Counter[str] = collections.Counter()
    seen_paths: set[tuple[str, str]] = set()
    for repository, repository_units in sorted(by_repository.items()):
        meta = repo_meta[repository]
        for unit in repository_units:
            for record in load_unit_file_records(unit):
                key = (repository, str(record["path"]))
                if key in seen_paths:
                    raise SystemExit(f"catalogue work units overlap on {repository}/{record['path']}")
                seen_paths.add(key)
                if not record.get("formal_source"):
                    continue
                decisions = rows_by_file.get(key, [])
                if any(row.get("primary") == "exclude" for row in decisions):
                    continue
                primary_counts[repository] += 1
                hashes[str(record["sha256"])].append(
                    {
                        "repository": repository,
                        "file": str(record["path"]),
                        "proof_assistant": str(meta["proof_assistant"]),
                        "source_revision": meta.get("source_revision"),
                        "size_bytes": int(record["size_bytes"]),
                    }
                )

    duplicate_groups: list[dict[str, Any]] = []
    fd006 = catalogue["FD-006"]
    for digest, members in sorted(hashes.items()):
        if len(members) < 2:
            continue
        members.sort(key=lambda item: (item["repository"], item["file"]))
        canonical = {"repository": members[0]["repository"], "file": members[0]["file"]}
        group = {
            "sha256": digest,
            "size_bytes": members[0]["size_bytes"],
            "canonical": canonical,
            "occurrences": [
                {
                    "repository": member["repository"],
                    "file": member["file"],
                    "proof_assistant": member["proof_assistant"],
                }
                for member in members
            ],
        }
        duplicate_groups.append(group)
        for number, member in enumerate(members):
            current.append(
                decision_record(
                    definition=fd006,
                    decision_id="FD-006",
                    repository=member["repository"],
                    file=member["file"],
                    proof_assistant=member["proof_assistant"],
                    source_revision=member["source_revision"],
                    content_sha256=digest,
                    evidence={
                        "sha256": digest,
                        "group_size": len(members),
                        "duplicate_role": "canonical" if number == 0 else "alias",
                        "canonical": canonical,
                    },
                    observed_at=now,
                    commit=commit,
                )
            )

    current.sort(key=decision_key)
    new = {decision_key(row): row for row in current}
    events: list[dict[str, Any]] = []
    for key in sorted(old.keys() - new.keys()):
        row = old[key]
        events.append(
            {
                **row,
                "ledger_event": "reverted",
                "recorded_at": now,
                "reverted_by_corpus_git_commit": commit,
                "event_reason": "The file no longer matches this decision in the current reviewed snapshot.",
            }
        )
    for key in sorted(new):
        row = new[key]
        previous = old.get(key)
        if previous is not None and stable_payload(previous) == stable_payload(row):
            continue
        events.append(
            {
                **row,
                "ledger_event": "applied" if previous is None else "updated",
                "recorded_at": now,
            }
        )

    current = [
        old[decision_key(row)]
        if decision_key(row) in old and stable_payload(old[decision_key(row)]) == stable_payload(row)
        else row
        for row in current
    ]

    if args.dry_run:
        print(
            f"dry-run review filter state: {len(current)} current decisions, "
            f"{len(events)} ledger events, {len(duplicate_groups)} duplicate groups; "
            f"would refresh {len(active_selected)} active and retire-clean {len(retired_selected)} repositories"
        )
        return 0

    FILTER_ROOT.mkdir(parents=True, exist_ok=True)
    append_filter_ledger(events)
    dump_jsonl(CURRENT, current)
    DUPLICATES.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": now,
                "corpus_git_commit": commit,
                "hash_algorithm": "sha256",
                "groups": duplicate_groups,
            },
            indent=2,
            sort_keys=True,
        ) + "\n"
    )

    prior_snapshot = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}
    snapshot = {
        **prior_snapshot,
        "schema_version": 1,
        "generated_at": now,
        "corpus_git_commit": commit,
        "source_revisions": {
            repository: meta.get("source_revision")
            for repository, meta in sorted(repo_meta.items())
        },
        "decision_counts": dict(collections.Counter(row["decision_id"] for row in current)),
        "ledger_events_appended": len(events),
        "duplicate_groups": len(duplicate_groups),
        "duplicate_occurrences": sum(len(group["occurrences"]) for group in duplicate_groups),
        "primary_eligible_counts_by_source": dict(sorted(primary_counts.items())),
        "sources_with_no_primary_documents": sorted(
            repository for repository in repo_meta if primary_counts[repository] <= 0
        ),
    }
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")

    print(json.dumps(snapshot["decision_counts"], sort_keys=True))
    print(
        f"review filter state: {len(current)} current decisions, {len(events)} ledger events, "
        f"{len(duplicate_groups)} duplicate groups; refreshed {len(active_selected)} active and "
        f"retire-cleaned {len(retired_selected)} repositories"
    )
    if snapshot["sources_with_no_primary_documents"]:
        print("ERROR: filtering would leave sources without primary documents:")
        for repository in snapshot["sources_with_no_primary_documents"]:
            print(f"  {repository}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
