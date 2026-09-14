from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import filtering_lib  # noqa: E402


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

    def test_declaration_is_not_import_only_candidate(self) -> None:
        self.assertFalse(
            filtering_lib.lean_import_only_candidate(b"import Mathlib\ntheorem owner : True := by trivial\n")
        )

    def test_pvs_prf_is_formal_content(self) -> None:
        self.assertTrue(filtering_lib.is_formal_file("pvs", pathlib.Path("proof.prf")))

    def test_lakefile_lean_is_build_metadata(self) -> None:
        self.assertTrue(filtering_lib.is_lean_build_metadata(pathlib.Path("lakefile.lean")))


if __name__ == "__main__":
    unittest.main()
