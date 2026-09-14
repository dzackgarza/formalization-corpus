from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import unittest

import lablog


class LabLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.saved = (lablog.ROOT, lablog.SEARCH, lablog.LEDGER, lablog.RUNS)
        lablog.ROOT = root
        lablog.SEARCH = root / "evaluation" / "search"
        lablog.LEDGER = lablog.SEARCH / "ledger.jsonl"
        lablog.RUNS = lablog.SEARCH / "runs"
        lablog.RUNS.mkdir(parents=True)

    def tearDown(self) -> None:
        lablog.ROOT, lablog.SEARCH, lablog.LEDGER, lablog.RUNS = self.saved
        self.tmp.cleanup()

    def test_validate_checks_immutable_artifact_hash(self) -> None:
        artifact = lablog.RUNS / "run.json"
        artifact.write_text('{"ok":true}\n')
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        lablog.append_record(
            {
                "schema_version": 1,
                "record_type": "measurement",
                "record_id": "M-test",
                "observed_at": "2026-01-01T00:00:00+00:00",
                "artifact": str(artifact.relative_to(lablog.ROOT)),
                "artifact_sha256": digest,
            }
        )
        self.assertEqual(lablog.validate(), [])
        artifact.write_text('{"ok":false}\n')
        self.assertTrue(any("artifact hash mismatch" in error for error in lablog.validate()))

    def test_evidence_must_point_backward(self) -> None:
        lablog.append_record(
            {
                "schema_version": 1,
                "record_type": "observation",
                "record_id": "O-test",
                "observed_at": "2026-01-01T00:00:00+00:00",
                "evidence": ["M-future"],
                "text": "premature conclusion",
            }
        )
        self.assertTrue(any("must refer to an earlier" in error for error in lablog.validate()))

    def test_repeated_run_summary_can_be_archived(self) -> None:
        report = lablog.ROOT / "report.json"
        report.write_text(
            json.dumps(
                {
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "corpus_git_commit": "abc123",
                    "variant": "stochastic",
                    "gold_sha256": "gold",
                    "rank_cutoff": 10,
                    "runs": 5,
                    "summary": {
                        "single_run_success": {"mean": 0.6},
                        "single_run_owner_success": {"mean": 0.4},
                        "pass_at_r": {
                            "5": {
                                "success": {"mean": 0.9},
                                "owner_success": {"mean": 0.8},
                            }
                        },
                    },
                }
            )
            + "\n"
        )
        original = lablog.repository_state
        lablog.repository_state = lambda _root: {"commit": "current", "worktree_clean": True}
        try:
            record = lablog.measurement_record(
                report,
                stage="candidate",
                note=None,
                allow_dirty=False,
                historical=True,
            )
        finally:
            lablog.repository_state = original
        self.assertEqual(record["metrics"]["success@10"], 0.6)
        self.assertEqual(record["metrics"]["pass@5[owner_success@10]"], 0.8)


if __name__ == "__main__":
    unittest.main()
