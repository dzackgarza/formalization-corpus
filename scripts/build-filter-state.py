#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
from typing import Any

from filtering_lib import (
    CURRENT,
    DUPLICATES,
    FILTER_ROOT,
    LEDGER,
    ROOT,
    SNAPSHOT,
    is_formal_file,
    is_lean_build_metadata,
    is_nonformal_readme,
    iter_files,
    lean_import_only_candidate,
    load_catalog,
    load_jsonl,
    sha256_file,
    source_revision,
    sources,
    verify_lean_import_only,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def corpus_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def decision_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["repository"], row["file"], row["decision_id"]


def decision_record(
    *,
    catalog: dict[str, dict[str, Any]],
    decision_id: str,
    repository: str,
    file: str,
    proof_assistant: str,
    source_revision_value: str | None,
    content_sha256: str | None,
    evidence: dict[str, Any],
    observed_at: str,
    commit: str,
) -> dict[str, Any]:
    decision = catalog[decision_id]
    return {
        "schema_version": 1,
        "repository": repository,
        "file": file,
        "proof_assistant": proof_assistant,
        "source_revision": source_revision_value,
        "decision_id": decision_id,
        "title": decision["title"],
        "primary": decision["primary"],
        "auxiliary": decision["auxiliary"],
        "result_action": decision.get("result_action"),
        "policies": decision["policies"],
        "justification": decision["justification"],
        "content_sha256": content_sha256,
        "evidence": evidence,
        "observed_at": observed_at,
        "corpus_git_commit": commit,
    }


def stable_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"observed_at", "corpus_git_commit"}
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()

    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True
    )
    if status.strip() and not args.allow_dirty:
        raise SystemExit("filter-state generation requires a clean worktree; commit the classifier first")

    catalog = load_catalog()
    now = utc_now()
    commit = corpus_commit()
    current: list[dict[str, Any]] = []
    hashes: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    import_candidates: list[tuple[Any, pathlib.Path, str, bytes, str]] = []
    source_revisions: dict[str, str | None] = {}
    primary_counts: collections.Counter[str] = collections.Counter()
    scanned_counts: collections.Counter[str] = collections.Counter()

    # First pass: content-independent decisions plus content hashes.
    for source in sources():
        revision = source_revision(source)
        source_revisions[source.repository] = revision
        if not source.root.exists():
            continue
        for path in iter_files(source):
            rel = path.relative_to(source.root).as_posix()
            scanned_counts[source.repository] += 1
            try:
                size = path.stat().st_size
            except OSError:
                continue
            formal = is_formal_file(source.proof_assistant, path)

            if is_nonformal_readme(source.proof_assistant, path):
                current.append(
                    decision_record(
                        catalog=catalog, decision_id="FD-002", repository=source.repository,
                        file=rel, proof_assistant=source.proof_assistant,
                        source_revision_value=revision, content_sha256=None,
                        evidence={"basename": path.name, "size_bytes": size}, observed_at=now, commit=commit,
                    )
                )
                continue

            if source.proof_assistant == "lean" and is_lean_build_metadata(path):
                digest = sha256_file(path) if size else hashlib.sha256(b"").hexdigest()
                current.append(
                    decision_record(
                        catalog=catalog, decision_id="FD-013", repository=source.repository,
                        file=rel, proof_assistant=source.proof_assistant,
                        source_revision_value=revision, content_sha256=digest,
                        evidence={"basename": path.name, "size_bytes": size}, observed_at=now, commit=commit,
                    )
                )
                continue

            if not formal:
                continue

            digest = sha256_file(path) if size else hashlib.sha256(b"").hexdigest()

            if size == 0:
                current.append(
                    decision_record(
                        catalog=catalog, decision_id="FD-001", repository=source.repository,
                        file=rel, proof_assistant=source.proof_assistant,
                        source_revision_value=revision, content_sha256=digest,
                        evidence={"size_bytes": 0}, observed_at=now, commit=commit,
                    )
                )
                continue

            if source.proof_assistant == "acl2" and ".sys" in pathlib.PurePosixPath(rel).parts:
                current.append(
                    decision_record(
                        catalog=catalog, decision_id="FD-004", repository=source.repository,
                        file=rel, proof_assistant=source.proof_assistant,
                        source_revision_value=revision, content_sha256=digest,
                        evidence={
                            "path_component": ".sys",
                            "size_bytes": size,
                            "prior_query_semantics": "production/evaluator queries already exclude (^|/)\\.sys/",
                        }, observed_at=now, commit=commit,
                    )
                )
                continue

            if source.proof_assistant == "pvs" and path.suffix.casefold() == ".prf":
                current.append(
                    decision_record(
                        catalog=catalog, decision_id="FD-007", repository=source.repository,
                        file=rel, proof_assistant=source.proof_assistant,
                        source_revision_value=revision, content_sha256=digest,
                        evidence={"extension": ".prf", "size_bytes": size}, observed_at=now, commit=commit,
                    )
                )
                if size > 2 * 1024 * 1024:
                    current.append(
                        decision_record(
                            catalog=catalog, decision_id="FD-011", repository=source.repository,
                            file=rel, proof_assistant=source.proof_assistant,
                            source_revision_value=revision, content_sha256=digest,
                            evidence={"size_bytes": size, "zoekt_default_file_limit": 2 * 1024 * 1024},
                            observed_at=now, commit=commit,
                        )
                    )

            raw: bytes | None = None
            if source.proof_assistant == "lean" and path.suffix == ".lean":
                raw = path.read_bytes()
                if lean_import_only_candidate(raw):
                    import_candidates.append((source, path, rel, raw, digest))

            # Candidate for exact-content result dedup.  Import-only files are
            # removed after parser verification below; harmless inclusion here
            # is corrected before duplicate groups are finalized.
            hashes[digest].append(
                {
                    "repository": source.repository,
                    "file": rel,
                    "proof_assistant": source.proof_assistant,
                    "source_revision": revision,
                    "size_bytes": size,
                }
            )
            primary_counts[source.repository] += 1

    accepted_imports, parser_meta = verify_lean_import_only(
        [path for _source, path, _rel, _raw, _digest in import_candidates]
    )
    import_keys: set[tuple[str, str]] = set()
    for source, path, rel, _raw, digest in import_candidates:
        if path not in accepted_imports:
            continue
        import_keys.add((source.repository, rel))
        current.append(
            decision_record(
                catalog=catalog, decision_id="FD-005", repository=source.repository,
                file=rel, proof_assistant=source.proof_assistant,
                source_revision_value=source_revisions[source.repository], content_sha256=digest,
                evidence={
                    "tree_sitter_verified": True,
                    "allowed_top_level_nodes": ["import", "line_comment", "block_comment"],
                    "parser_sha256": parser_meta.get("parser_sha256"),
                }, observed_at=now, commit=commit,
            )
        )
        primary_counts[source.repository] -= 1

    # Exact duplicates among documents that remain primary-eligible.  All paths
    # stay in the physical index; FD-006 controls result-layer canonicalization.
    duplicate_groups: list[dict[str, Any]] = []
    for digest, members in sorted(hashes.items()):
        eligible = [m for m in members if (m["repository"], m["file"]) not in import_keys]
        if len(eligible) < 2:
            continue
        eligible.sort(key=lambda m: (m["repository"], m["file"]))
        group = {
            "sha256": digest,
            "size_bytes": eligible[0]["size_bytes"],
            "canonical": {"repository": eligible[0]["repository"], "file": eligible[0]["file"]},
            "occurrences": [
                {"repository": m["repository"], "file": m["file"], "proof_assistant": m["proof_assistant"]}
                for m in eligible
            ],
        }
        duplicate_groups.append(group)
        for number, member in enumerate(eligible):
            current.append(
                decision_record(
                    catalog=catalog, decision_id="FD-006", repository=member["repository"],
                    file=member["file"], proof_assistant=member["proof_assistant"],
                    source_revision_value=member["source_revision"], content_sha256=digest,
                    evidence={
                        "sha256": digest,
                        "group_size": len(eligible),
                        "duplicate_role": "canonical" if number == 0 else "alias",
                        "canonical": group["canonical"],
                    }, observed_at=now, commit=commit,
                )
            )

    current.sort(key=decision_key)
    old_rows = load_jsonl(CURRENT)
    old = {decision_key(row): row for row in old_rows}
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
                "event_reason": "The file no longer matches this decision in the current source snapshot.",
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

    FILTER_ROOT.mkdir(parents=True, exist_ok=True)
    if events:
        with LEDGER.open("a") as handle:
            for event in events:
                handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    from filtering_lib import dump_jsonl
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
        )
        + "\n"
    )

    repositories = [source.repository for source in sources() if source.root.exists()]
    empty_primary = sorted(repo for repo in repositories if primary_counts[repo] <= 0)
    snapshot = {
        "schema_version": 1,
        "generated_at": now,
        "corpus_git_commit": commit,
        "source_revisions": source_revisions,
        "parser_verification": parser_meta,
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
