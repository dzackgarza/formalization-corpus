from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import repository_review_lib as review_lib  # noqa: E402
from repository_review_lib import (  # noqa: E402
    FileRecord,
    partition_source,
    selector_paths,
)
import filtering_lib  # noqa: E402


def record(path: str, size: int = 10) -> FileRecord:
    return FileRecord(
        path=path,
        size_bytes=size,
        sha256=(path.encode().hex() + "0" * 64)[:64],
        formal_source=True,
        active_decisions=(),
        baseline_primary_status="primary-retained",
        current_primary_status="primary-retained",
    )


class RepositoryReviewTests(unittest.TestCase):
    def test_small_repository_is_one_stable_unit(self) -> None:
        records = [record("A.lean"), record("Dir/B.lean")]
        units = partition_source("owner__repo", records)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].scope_kind, "repository")
        self.assertEqual({r.path for r in units[0].records}, {"A.lean", "Dir/B.lean"})

    def test_extremely_large_repository_is_partitioned_without_loss_or_overlap(self) -> None:
        records = [record(f"A/F{i}.lean") for i in range(3000)] + [
            record(f"B/G{i}.lean") for i in range(3000)
        ]
        units = partition_source("owner__huge", records)
        self.assertGreater(len(units), 1)
        paths = [r.path for unit in units for r in unit.records]
        self.assertEqual(len(paths), len(records))
        self.assertEqual(len(set(paths)), len(records))
        self.assertEqual(set(paths), {r.path for r in records})

    def test_large_partition_ids_do_not_shift_when_one_file_is_added(self) -> None:
        before = [record(f"A/F{i}.lean") for i in range(3000)]
        after = before + [record("A/NewSibling.lean")]
        before_units = {unit.unit_id: unit.snapshot_sha256 for unit in partition_source("owner__stable", before)}
        after_units = {unit.unit_id: unit.snapshot_sha256 for unit in partition_source("owner__stable", after)}
        self.assertEqual(set(before_units), set(after_units))
        changed = [uid for uid in before_units if before_units[uid] != after_units[uid]]
        self.assertEqual(len(changed), 1)

    def test_selectors_are_literal_and_bounded_to_unit_paths(self) -> None:
        paths = {"Generated/A.lean", "Generated/Sub/B.lean", "Owner.lean"}
        self.assertEqual(
            selector_paths({"kind": "path-prefix", "prefix": "Generated"}, paths),
            {"Generated/A.lean", "Generated/Sub/B.lean"},
        )
        self.assertEqual(
            selector_paths({"kind": "path-set", "paths": ["Owner.lean", "Absent.lean"]}, paths),
            {"Owner.lean"},
        )
        self.assertEqual(selector_paths({"kind": "regex", "pattern": ".*"}, paths), set())


    def test_fresh_review_rule_resolves_to_exact_hashed_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            saved = (
                review_lib.ROOT, review_lib.REVIEW_ROOT, review_lib.CATALOGUE_ROOT,
                review_lib.FILES_ROOT, review_lib.REVIEWS_ROOT, review_lib.CATALOGUE_INDEX,
            )
            review_lib.ROOT = root
            review_lib.REVIEW_ROOT = root / "filtering/repository-review"
            review_lib.CATALOGUE_ROOT = review_lib.REVIEW_ROOT / "catalogue"
            review_lib.FILES_ROOT = review_lib.REVIEW_ROOT / "files"
            review_lib.REVIEWS_ROOT = review_lib.REVIEW_ROOT / "reviews"
            review_lib.CATALOGUE_INDEX = review_lib.REVIEW_ROOT / "catalogue.jsonl"
            try:
                repository = "owner__repo"
                uid = review_lib.unit_id(repository, "repository", ".")
                manifest = review_lib.FILES_ROOT / repository / f"{uid}.jsonl"
                review_lib.dump_jsonl(manifest, [{
                    "path": "Generated.lean", "size_bytes": 4, "sha256": "a" * 64,
                    "formal_source": True, "active_decisions": [],
                    "baseline_primary_status": "primary-retained",
                    "current_primary_status": "primary-retained",
                }])
                catalogue = review_lib.CATALOGUE_ROOT / f"{repository}.json"
                catalogue.parent.mkdir(parents=True, exist_ok=True)
                catalogue.write_text(json.dumps({
                    "repository": repository, "proof_assistant": "lean",
                    "source_revision": "abc", "source_snapshot_sha256": "b" * 64,
                    "work_units": [{
                        "unit_id": uid, "scope": {"kind": "repository", "value": "."},
                        "snapshot_sha256": "c" * 64,
                        "stats": {"files": 1, "baseline_primary_retained": 1},
                        "files_manifest": str(manifest.relative_to(root)),
                    }],
                }))
                review_lib.dump_jsonl(review_lib.CATALOGUE_INDEX, [{
                    "repository": repository, "catalogue_file": str(catalogue.relative_to(root)),
                }])
                review = review_lib.REVIEWS_ROOT / repository / f"{uid}.jsonl"
                short = uid.split("-", 1)[1]
                review_lib.dump_jsonl(review, [{
                    "review_id": f"RRV-{short}-r1", "unit_id": uid, "repository": repository,
                    "status": "reviewed", "unit_snapshot_sha256": "c" * 64,
                    "rules": [{
                        "rule_id": f"RRX-{short}-1", "action": "primary-exclude",
                        "selector": {"kind": "exact-path", "path": "Generated.lean"},
                        "rationale": "generated fixture", "content_invariant": "redundant fixture",
                        "evidence": ["source-local evidence"],
                    }],
                }])
                exclusions, errors = review_lib.resolve_review_exclusions()
                self.assertEqual(errors, [])
                item = exclusions[(repository, "Generated.lean")]
                self.assertEqual(item["file_sha256"], "a" * 64)
                self.assertEqual(item["rule_id"], f"RRX-{short}-1")
            finally:
                (
                    review_lib.ROOT, review_lib.REVIEW_ROOT, review_lib.CATALOGUE_ROOT,
                    review_lib.FILES_ROOT, review_lib.REVIEWS_ROOT, review_lib.CATALOGUE_INDEX,
                ) = saved

    def test_stale_review_never_resolves_an_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            saved = (
                review_lib.ROOT, review_lib.REVIEW_ROOT, review_lib.CATALOGUE_ROOT,
                review_lib.FILES_ROOT, review_lib.REVIEWS_ROOT, review_lib.CATALOGUE_INDEX,
            )
            review_lib.ROOT = root
            review_lib.REVIEW_ROOT = root / "filtering/repository-review"
            review_lib.CATALOGUE_ROOT = review_lib.REVIEW_ROOT / "catalogue"
            review_lib.FILES_ROOT = review_lib.REVIEW_ROOT / "files"
            review_lib.REVIEWS_ROOT = review_lib.REVIEW_ROOT / "reviews"
            review_lib.CATALOGUE_INDEX = review_lib.REVIEW_ROOT / "catalogue.jsonl"
            try:
                repository = "owner__repo"
                uid = review_lib.unit_id(repository, "repository", ".")
                manifest = review_lib.FILES_ROOT / repository / f"{uid}.jsonl"
                review_lib.dump_jsonl(manifest, [{
                    "path": "A.lean", "size_bytes": 1, "sha256": "a" * 64,
                    "formal_source": True, "active_decisions": [],
                    "baseline_primary_status": "primary-retained",
                    "current_primary_status": "primary-retained",
                }])
                catalogue = review_lib.CATALOGUE_ROOT / f"{repository}.json"
                catalogue.parent.mkdir(parents=True, exist_ok=True)
                catalogue.write_text(json.dumps({
                    "repository": repository, "proof_assistant": "lean",
                    "source_revision": "abc", "source_snapshot_sha256": "b" * 64,
                    "work_units": [{
                        "unit_id": uid, "scope": {"kind": "repository", "value": "."},
                        "snapshot_sha256": "current-snapshot".ljust(64, "0"),
                        "stats": {"files": 1, "baseline_primary_retained": 1},
                        "files_manifest": str(manifest.relative_to(root)),
                    }],
                }))
                review_lib.dump_jsonl(review_lib.CATALOGUE_INDEX, [{
                    "repository": repository, "catalogue_file": str(catalogue.relative_to(root)),
                }])
                short = uid.split("-", 1)[1]
                review_lib.dump_jsonl(review_lib.REVIEWS_ROOT / repository / f"{uid}.jsonl", [{
                    "review_id": f"RRV-{short}-r1", "unit_id": uid, "repository": repository,
                    "status": "reviewed", "unit_snapshot_sha256": "stale-snapshot".ljust(64, "0"),
                    "rules": [{
                        "rule_id": f"RRX-{short}-1", "action": "primary-exclude",
                        "selector": {"kind": "exact-path", "path": "A.lean"},
                        "rationale": "old rationale", "content_invariant": "old invariant",
                        "evidence": ["old evidence"],
                    }],
                }])
                exclusions, errors = review_lib.resolve_review_exclusions(require_fresh=True)
                self.assertEqual(exclusions, {})
                self.assertTrue(any("stale" in error for error in errors))
            finally:
                (
                    review_lib.ROOT, review_lib.REVIEW_ROOT, review_lib.CATALOGUE_ROOT,
                    review_lib.FILES_ROOT, review_lib.REVIEWS_ROOT, review_lib.CATALOGUE_INDEX,
                ) = saved

    def test_fd018_has_no_standalone_path_heuristic_authority(self) -> None:
        decision = filtering_lib.load_catalog()["FD-018"]
        self.assertEqual(decision["primary"], "exclude")
        self.assertIn("repository-review record", decision["justification"])
        self.assertIn("FILTER-024", decision["policies"])


if __name__ == "__main__":
    unittest.main()
