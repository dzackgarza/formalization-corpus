#!/usr/bin/env python3
"""Recompute the per-file filtering decisions, one hydrated source at a time.

Content decisions (every decision in ``SCAN_DECISIONS``) need the source bytes.
They are recomputed only for the sources named with ``--source``, whose checkout
must match the committed review catalogue. The other registered sources keep
their current content decisions. Review exclusions (FD-018), exact duplicates
(FD-006) and the per-source primary counts are recomputed for the whole corpus
from the committed catalogue manifests, so no other checkout is read.
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
    Source,
    append_filter_ledger,
    dump_jsonl,
    is_acl2_useless_runes_report,
    is_formal_file,
    is_lean_build_metadata,
    is_nonformal_readme,
    is_whitespace_only_formal_source,
    iter_files,
    lean_import_only_candidate,
    load_catalog,
    load_jsonl,
    sha256_file,
    source_revision,
    sources,
    ungenerated_changes,
    verify_lean_import_only,
)
from repository_review_lib import (
    FileRecord,
    catalogue_path,
    catalogued_records,
    file_record,
    load_json,
    material_snapshot_sha256,
    resolve_review_exclusions,
)

SCAN_DECISIONS = frozenset({"FD-001", "FD-002", "FD-007", "FD-011", "FD-013", "FD-015", "FD-016", "FD-017"})
ZOEKT_DEFAULT_FILE_LIMIT = 2 * 1024 * 1024


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def corpus_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def decision_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["repository"], row["file"], row["decision_id"]


def stable_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"observed_at", "corpus_git_commit"}
    }


class Recorder:
    """Build decision rows that share one catalog, scan time and corpus commit."""

    def __init__(self, catalog: dict[str, dict[str, Any]], now: str, commit: str) -> None:
        self.catalog = catalog
        self.now = now
        self.commit = commit

    def row(
        self,
        decision_id: str,
        *,
        repository: str,
        file: str,
        proof_assistant: str,
        revision: str | None,
        content_sha256: str | None,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        decision = self.catalog[decision_id]
        return {
            "schema_version": 1,
            "repository": repository,
            "file": file,
            "proof_assistant": proof_assistant,
            "source_revision": revision,
            "decision_id": decision_id,
            "title": decision["title"],
            "primary": decision["primary"],
            "auxiliary": decision["auxiliary"],
            "result_action": decision.get("result_action"),
            "policies": decision["policies"],
            "justification": decision["justification"],
            "content_sha256": content_sha256,
            "evidence": evidence,
            "observed_at": self.now,
            "corpus_git_commit": self.commit,
        }


def scan_source(
    source: Source, revision: str | None, record: Recorder
) -> tuple[list[dict[str, Any]], list[FileRecord]]:
    """Return the content decisions and the file records of one checkout."""
    rows: list[dict[str, Any]] = []
    candidates: list[tuple[pathlib.Path, str, str]] = []
    files: list[FileRecord] = []

    def add(decision_id: str, rel: str, digest: str | None, evidence: dict[str, Any]) -> None:
        rows.append(
            record.row(
                decision_id, repository=source.repository, file=rel,
                proof_assistant=source.proof_assistant, revision=revision,
                content_sha256=digest, evidence=evidence,
            )
        )

    for path in iter_files(source):
        rel = path.relative_to(source.root).as_posix()
        size = path.stat().st_size
        digest = sha256_file(path)
        formal = is_formal_file(source.proof_assistant, path)
        files.append(file_record(source.repository, rel, size, digest, formal, {}))

        if is_nonformal_readme(source.proof_assistant, path):
            add("FD-002", rel, None, {"basename": path.name, "size_bytes": size})
            continue
        if source.proof_assistant == "lean" and is_lean_build_metadata(path):
            add("FD-013", rel, digest, {"basename": path.name, "size_bytes": size})
            continue
        if not formal:
            continue
        if size == 0:
            add("FD-001", rel, digest, {"size_bytes": 0})
            continue
        # Narrower than "comment-only": comments and prose are search evidence,
        # a nonempty file of whitespace alone is not.
        raw = path.read_bytes()
        if is_whitespace_only_formal_source(raw):
            add("FD-015", rel, digest, {"size_bytes": size, "content_class": "whitespace-only"})
            continue
        if source.proof_assistant == "acl2" and is_acl2_useless_runes_report(path):
            add("FD-017", rel, digest, {
                "path_component": ".sys",
                "artifact_suffix": "@useless-runes.lsp",
                "size_bytes": size,
                "content_class": "acl2-certification-proof-metadata",
            })
        if source.proof_assistant == "pvs" and path.suffix.casefold() == ".prf":
            add("FD-007", rel, digest, {"extension": ".prf", "size_bytes": size})
            if size > ZOEKT_DEFAULT_FILE_LIMIT:
                add("FD-011", rel, digest, {
                    "size_bytes": size, "zoekt_default_file_limit": ZOEKT_DEFAULT_FILE_LIMIT,
                })
        if source.proof_assistant == "lean" and path.suffix == ".lean" and lean_import_only_candidate(raw):
            candidates.append((path, rel, digest))

    accepted, parser_meta = verify_lean_import_only([path for path, _rel, _digest in candidates])
    for path, rel, digest in candidates:
        if path in accepted:
            add("FD-016", rel, digest, {
                "tree_sitter_verified": True,
                "allowed_top_level_nodes": ["import", "line_comment", "block_comment"],
                "parser_sha256": parser_meta["parser_sha256"],
            })
    return rows, files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", action="append", default=[], metavar="REPOSITORY",
        help="recompute the content decisions of this hydrated source (repeatable)",
    )
    parser.add_argument(
        "--allow-dirty", action="store_true",
        help="run although tracked files outside the generated filtering state have changes",
    )
    args = parser.parse_args()

    dirty = ungenerated_changes()
    if dirty and not args.allow_dirty:
        raise SystemExit(
            "filter-state generation requires committed classifier inputs; uncommitted changes:\n  "
            + "\n  ".join(dirty[:20])
        )

    registered = {source.repository: source for source in sources()}
    unknown = sorted(set(args.source) - set(registered))
    if unknown:
        raise SystemExit(f"unregistered sources: {', '.join(unknown)}")
    scanned = set(args.source)

    review_exclusions, review_errors = resolve_review_exclusions(require_fresh=True)
    if review_errors:
        raise SystemExit(
            "repository review state is invalid; run `just repository-review-validate`:\n  "
            + "\n  ".join(review_errors[:50])
        )

    record = Recorder(load_catalog(), utc_now(), corpus_commit())
    old_rows = load_jsonl(CURRENT)
    old_by_source: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in old_rows:
        if row["decision_id"] in SCAN_DECISIONS:
            old_by_source[row["repository"]].append(row)

    current: list[dict[str, Any]] = []
    source_revisions: dict[str, str | None] = {}
    manifest_records: dict[str, list[FileRecord]] = {}
    for repository, source in sorted(registered.items()):
        revision = load_json(catalogue_path(repository)).get("source_revision")
        source_revisions[repository] = revision
        manifest_records[repository] = catalogued_records(repository, {})
        by_path = {item.path: item for item in manifest_records[repository]}
        if repository in scanned:
            if not source.root.exists():
                raise SystemExit(f"{repository}: --source needs the hydrated checkout at {source.root}")
            if source_revision(source) != revision:
                raise SystemExit(
                    f"{repository}: checkout revision differs from the review catalogue; "
                    f"run `python scripts/repository-review.py build --source {repository}`"
                )
            rows, files = scan_source(source, revision, record)
            if material_snapshot_sha256(files) != material_snapshot_sha256(manifest_records[repository]):
                raise SystemExit(
                    f"{repository}: checkout content differs from the review catalogue; "
                    f"run `python scripts/repository-review.py build --source {repository}`"
                )
            current.extend(rows)
            continue
        for row in old_by_source[repository]:
            item = by_path.get(row["file"])
            content_matches = item is not None and row["content_sha256"] in {None, item.sha256}
            if row["source_revision"] != revision or not content_matches:
                raise SystemExit(
                    f"{repository}: content decisions predate the review catalogue; "
                    f"hydrate it and run `python scripts/build-filter-state.py --source {repository}`"
                )
            current.append(row)

    for (repository, rel), exclusion in sorted(review_exclusions.items()):
        current.append(
            record.row(
                "FD-018", repository=repository, file=rel,
                proof_assistant=registered[repository].proof_assistant,
                revision=source_revisions[repository], content_sha256=exclusion["file_sha256"],
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
            )
        )

    # A file is primary-eligible when it is nonempty formal source and no active
    # decision excludes it from the primary index.
    excluded = {(row["repository"], row["file"]) for row in current if row["primary"] == "exclude"}
    hashes: dict[str, list[tuple[str, FileRecord]]] = collections.defaultdict(list)
    primary_counts: collections.Counter[str] = collections.Counter()
    for repository, records in manifest_records.items():
        for item in records:
            if item.formal_source and item.size_bytes > 0 and (repository, item.path) not in excluded:
                hashes[item.sha256].append((repository, item))
                primary_counts[repository] += 1

    # Every occurrence stays in the physical index; FD-006 only canonicalizes results.
    duplicate_groups: list[dict[str, Any]] = []
    for digest, members in sorted(hashes.items()):
        if len(members) < 2:
            continue
        members.sort(key=lambda member: (member[0], member[1].path))
        canonical = {"repository": members[0][0], "file": members[0][1].path}
        duplicate_groups.append({
            "sha256": digest,
            "size_bytes": members[0][1].size_bytes,
            "canonical": canonical,
            "occurrences": [
                {"repository": repository, "file": item.path,
                 "proof_assistant": registered[repository].proof_assistant}
                for repository, item in members
            ],
        })
        for number, (repository, item) in enumerate(members):
            current.append(
                record.row(
                    "FD-006", repository=repository, file=item.path,
                    proof_assistant=registered[repository].proof_assistant,
                    revision=source_revisions[repository], content_sha256=digest,
                    evidence={
                        "sha256": digest,
                        "group_size": len(members),
                        "duplicate_role": "canonical" if number == 0 else "alias",
                        "canonical": canonical,
                    },
                )
            )

    current.sort(key=decision_key)
    old = {decision_key(row): row for row in old_rows}
    new = {decision_key(row): row for row in current}
    events: list[dict[str, Any]] = []
    for key in sorted(old.keys() - new.keys()):
        events.append({
            **old[key],
            "ledger_event": "reverted",
            "recorded_at": record.now,
            "reverted_by_corpus_git_commit": record.commit,
            "event_reason": "The file no longer matches this decision in the current source snapshot.",
        })
    for key in sorted(new):
        previous = old.get(key)
        if previous is not None and stable_payload(previous) == stable_payload(new[key]):
            continue
        events.append({
            **new[key],
            "ledger_event": "applied" if previous is None else "updated",
            "recorded_at": record.now,
        })

    # A decision whose substance is unchanged keeps the provenance of the scan
    # that made it; the snapshot records the latest scan.
    current = [
        old[decision_key(row)]
        if decision_key(row) in old and stable_payload(old[decision_key(row)]) == stable_payload(row)
        else row
        for row in current
    ]

    FILTER_ROOT.mkdir(parents=True, exist_ok=True)
    append_filter_ledger(events)
    dump_jsonl(CURRENT, current)
    DUPLICATES.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": record.now,
                "corpus_git_commit": record.commit,
                "hash_algorithm": "sha256",
                "groups": duplicate_groups,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    empty_primary = sorted(repository for repository in registered if primary_counts[repository] <= 0)
    snapshot = {
        "schema_version": 1,
        "generated_at": record.now,
        "corpus_git_commit": record.commit,
        "source_revisions": source_revisions,
        "decision_counts": dict(collections.Counter(row["decision_id"] for row in current)),
        "ledger_events_appended": len(events),
        "duplicate_groups": len(duplicate_groups),
        "duplicate_occurrences": sum(len(group["occurrences"]) for group in duplicate_groups),
        "primary_eligible_counts_by_source": dict(sorted(primary_counts.items())),
        "sources_with_no_primary_documents": empty_primary,
    }
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")

    print(json.dumps(snapshot["decision_counts"], sort_keys=True))
    print(
        f"filter state: {len(current)} current decisions, {len(events)} ledger events, "
        f"{len(duplicate_groups)} duplicate groups"
    )
    if empty_primary:
        print("ERROR: filtering would leave sources without primary documents:")
        for repository in empty_primary:
            print(f"  {repository}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
