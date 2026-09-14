from __future__ import annotations

import pathlib
import sys
import unittest
import importlib.util

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import filtering_lib  # noqa: E402


def load_validator():
    path = ROOT / "scripts" / "validate-filter-state.py"
    spec = importlib.util.spec_from_file_location("validate_filter_state", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FilteringTests(unittest.TestCase):
    def test_filter_catalog_has_unique_decisions_and_known_policy_shape(self) -> None:
        catalog = filtering_lib.load_catalog()
        self.assertGreaterEqual(len(catalog), 10)
        for decision_id, decision in catalog.items():
            self.assertRegex(decision_id, r"^FD-\d{3}$")
            self.assertTrue(decision["justification"])
            self.assertTrue(decision["policies"])
            self.assertIn(decision["primary"], {"exclude", "retain", "no-change"})
            self.assertIn(decision["auxiliary"], {"exclude", "include", "no-change"})

    def test_nested_lean_comments_do_not_hide_import_only_candidate(self) -> None:
        raw = b"/- outer /- nested -/ comment -/\n-- line\npublic import Foo.Bar\nimport Baz\n"
        self.assertTrue(filtering_lib.lean_import_only_candidate(raw))

    def test_nonimport_command_is_not_import_only_candidate(self) -> None:
        self.assertFalse(
            filtering_lib.lean_import_only_candidate(b"import Mathlib\nopen scoped BigOperators\n")
        )

    def test_import_only_modules_remain_primary_until_auxiliary_search_is_served(self) -> None:
        catalog = filtering_lib.load_catalog()
        self.assertEqual(catalog["FD-005"].get("status"), "superseded")
        self.assertEqual(catalog["FD-005"].get("superseded_by"), "FD-016")
        self.assertEqual(catalog["FD-016"]["primary"], "retain")
        self.assertEqual(catalog["FD-016"]["auxiliary"], "include")

    def test_declaration_is_not_import_only_candidate(self) -> None:
        self.assertFalse(
            filtering_lib.lean_import_only_candidate(b"import Mathlib\ntheorem owner : True := by trivial\n")
        )

    def test_pvs_prf_is_formal_content(self) -> None:
        self.assertTrue(filtering_lib.is_formal_file("pvs", pathlib.Path("proof.prf")))

    def test_formal_lakefile_is_not_build_metadata_filter_candidate(self) -> None:
        self.assertFalse(filtering_lib.is_lean_build_metadata(pathlib.Path("lakefile.lean")))
        self.assertTrue(filtering_lib.is_lean_build_metadata(pathlib.Path("lakefile.toml")))
        self.assertTrue(filtering_lib.is_lean_build_metadata(pathlib.Path("lake-manifest.json")))
        self.assertTrue(filtering_lib.is_lean_build_metadata(pathlib.Path("lean-toolchain")))

    def test_acl2_sys_filter_is_exactly_useless_runes_reports(self) -> None:
        self.assertTrue(
            filtering_lib.is_acl2_useless_runes_report(
                pathlib.Path("books/foo/.sys/bar@useless-runes.lsp")
            )
        )
        self.assertFalse(
            filtering_lib.is_acl2_useless_runes_report(pathlib.Path("books/foo/.sys/bar.lsp"))
        )
        self.assertFalse(
            filtering_lib.is_acl2_useless_runes_report(
                pathlib.Path("books/foo/bar@useless-runes.lsp")
            )
        )

    def test_acl2_useless_runes_reports_are_retained_proof_metadata(self) -> None:
        catalog = filtering_lib.load_catalog()
        self.assertEqual(catalog["FD-014"].get("status"), "superseded")
        self.assertEqual(catalog["FD-014"].get("superseded_by"), "FD-017")
        self.assertEqual(catalog["FD-017"]["primary"], "retain")

    def test_formal_readme_is_not_documentation_filter_candidate(self) -> None:
        self.assertFalse(filtering_lib.is_nonformal_readme("lean", pathlib.Path("README.lean")))
        self.assertFalse(filtering_lib.is_nonformal_readme("agda", pathlib.Path("README.agda")))
        self.assertFalse(filtering_lib.is_nonformal_readme("isabelle", pathlib.Path("README.thy")))
        self.assertFalse(filtering_lib.is_nonformal_readme("acl2", pathlib.Path("Readme.lsp")))

    def test_whitespace_only_is_lossless_but_comments_are_not_empty(self) -> None:
        self.assertTrue(filtering_lib.is_whitespace_only_formal_source(b" \n\t\r\n"))
        self.assertFalse(filtering_lib.is_whitespace_only_formal_source(b""))
        self.assertFalse(filtering_lib.is_whitespace_only_formal_source(b"-- useful name\n"))
        self.assertFalse(filtering_lib.is_whitespace_only_formal_source(b"/- useful docs -/\n"))
        self.assertFalse(filtering_lib.is_whitespace_only_formal_source(b"theorem t : True := by trivial\n"))
        self.assertTrue(filtering_lib.is_nonformal_readme("lean", pathlib.Path("README.md")))

    def test_ledger_replay_detects_snapshot_drift(self) -> None:
        validator = load_validator()
        catalog = {
            "FD-001": {
                "title": "empty",
                "primary": "exclude",
                "auxiliary": "exclude",
                "policies": ["FILTER-001"],
                "justification": "empty",
            }
        }
        base = {
            "schema_version": 1,
            "repository": "repo",
            "file": "A.lean",
            "proof_assistant": "lean",
            "source_revision": "abc",
            "decision_id": "FD-001",
            "title": "empty",
            "primary": "exclude",
            "auxiliary": "exclude",
            "result_action": None,
            "policies": ["FILTER-001"],
            "justification": "empty",
            "content_sha256": "0" * 64,
            "evidence": {"size_bytes": 0},
            "observed_at": "2026-01-01T00:00:00+00:00",
            "corpus_git_commit": "deadbeef",
        }
        ledger = [{**base, "ledger_event": "applied", "recorded_at": "x"}]
        snapshot = {
            "decision_counts": {"FD-001": 1},
            "sources_with_no_primary_documents": [],
            "primary_eligible_counts_by_source": {"repo": 1},
            "duplicate_groups": 0,
            "duplicate_occurrences": 0,
        }
        self.assertEqual(
            validator.validate_state(
                catalog=catalog,
                ledger=ledger,
                current=[base],
                duplicates={"schema_version": 1, "groups": []},
                snapshot=snapshot,
                registered_repositories={"repo"},
            ),
            [],
        )
        bad = [dict(base, title="edited")]
        errors = validator.validate_state(
            catalog=catalog,
            ledger=ledger,
            current=bad,
            duplicates={"schema_version": 1, "groups": []},
            snapshot=snapshot,
            registered_repositories={"repo"},
        )
        self.assertTrue(any("stale catalog field title" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
