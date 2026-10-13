#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
from typing import Any

from filtering_lib import (
    CURRENT,
    FILTER_ROOT,
    ROOT,
    SNAPSHOT,
    append_filter_ledger,
    is_formal_file,
    is_acl2_useless_runes_report,
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
    verify_lean_import_only,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def corpus_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


# Decisions that refresh-review-filter-state.py derives from the committed review
# manifests: FD-018 from review rules, FD-006 from content hashes across all sources.
REVIEW_DERIVED = {"FD-006", "FD-018"}


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
    parser = argparse.ArgumentParser(
        description=(
            "Recompute the content-derived file decisions of hydrated sources. "
            "FD-006 and FD-018 belong to refresh-review-filter-state.py, which must run "
            "after `repository-review.py build` for the same sources."
        )
    )
    parser.add_argument("--repository", action="append", default=[], help="default: every active source")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()

    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True
    )
    if status.strip() and not args.allow_dirty:
        raise SystemExit("filter-state generation requires a clean worktree; commit the classifier first")

    active = {source.repository: source for source in sources()}
    selected = set(args.repository) or set(active)
    unknown = sorted(selected - set(active))
    if unknown:
        raise SystemExit(f"unknown active repositories: {unknown}")
    missing = sorted(repository for repository in selected if not active[repository].root.exists())
    if missing:
        raise SystemExit(f"hydrate these sources first: {missing}")

    catalog = load_catalog()
    now = utc_now()
    commit = corpus_commit()
    old_rows = load_jsonl(CURRENT)
    current: list[dict[str, Any]] = [
        row
        for row in old_rows
        if row["repository"] not in selected or row["decision_id"] in REVIEW_DERIVED
    ]
    import_candidates: list[tuple[Any, pathlib.Path, str, bytes, str]] = []
    source_revisions: dict[str, str | None] = {}

    for repository in sorted(selected):
        source = active[repository]
        revision = source_revision(source)
        source_revisions[source.repository] = revision
        for path in iter_files(source):
            rel = path.relative_to(source.root).as_posix()
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

            # This is intentionally narrower than "contains no declaration" or
            # "comment-only".  Comments and prose are useful search evidence;
            # a nonempty file consisting solely of whitespace has none.
            raw_for_whitespace = path.read_bytes()
            if is_whitespace_only_formal_source(raw_for_whitespace):
                current.append(
                    decision_record(
                        catalog=catalog, decision_id="FD-015", repository=source.repository,
                        file=rel, proof_assistant=source.proof_assistant,
                        source_revision_value=revision, content_sha256=digest,
                        evidence={"size_bytes": size, "content_class": "whitespace-only"},
                        observed_at=now, commit=commit,
                    )
                )
                continue

            if source.proof_assistant == "acl2" and is_acl2_useless_runes_report(path):
                current.append(
                    decision_record(
                        catalog=catalog, decision_id="FD-017", repository=source.repository,
                        file=rel, proof_assistant=source.proof_assistant,
                        source_revision_value=revision, content_sha256=digest,
                        evidence={
                            "path_component": ".sys",
                            "artifact_suffix": "@useless-runes.lsp",
                            "size_bytes": size,
                            "content_class": "acl2-certification-proof-metadata",
                        }, observed_at=now, commit=commit,
                    )
                )

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
                raw = raw_for_whitespace
                if lean_import_only_candidate(raw):
                    import_candidates.append((source, path, rel, raw, digest))

    accepted_imports, parser_meta = verify_lean_import_only(
        [path for _source, path, _rel, _raw, _digest in import_candidates]
    )
    for source, path, rel, _raw, digest in import_candidates:
        if path not in accepted_imports:
            continue
        current.append(
            decision_record(
                catalog=catalog, decision_id="FD-016", repository=source.repository,
                file=rel, proof_assistant=source.proof_assistant,
                source_revision_value=source_revisions[source.repository], content_sha256=digest,
                evidence={
                    "tree_sitter_verified": True,
                    "allowed_top_level_nodes": ["import", "line_comment", "block_comment"],
                    "parser_sha256": parser_meta.get("parser_sha256"),
                }, observed_at=now, commit=commit,
            )
        )

    current.sort(key=decision_key)
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

    # Do not rewrite provenance fields on decisions whose substantive payload is
    # unchanged.  The top-level snapshot records the latest scan commit/time; an
    # unchanged per-file row should keep the provenance of the decision actually
    # represented by that row.  This also keeps repository-review batches
    # auditable instead of producing whole-corpus timestamp churn for a handful
    # of changed decisions.
    current = [
        old.get(decision_key(row), row)
        if old.get(decision_key(row)) is not None
        and stable_payload(old[decision_key(row)]) == stable_payload(row)
        else row
        for row in current
    ]

    FILTER_ROOT.mkdir(parents=True, exist_ok=True)
    append_filter_ledger(events)
    from filtering_lib import dump_jsonl
    dump_jsonl(CURRENT, current)
    snapshot = json.loads(SNAPSHOT.read_text())
    snapshot["source_revisions"] = {**snapshot["source_revisions"], **source_revisions}
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(
        f"content filter state for {len(selected)} sources: {len(current)} current decisions, "
        f"{len(events)} ledger events, parser verification {json.dumps(parser_meta, sort_keys=True)}; run repository-review.py build and "
        "refresh-review-filter-state.py for the same sources next"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
