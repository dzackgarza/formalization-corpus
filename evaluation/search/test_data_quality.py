#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit_corpus_data  # noqa: E402


class CorpusDataQualityTests(unittest.TestCase):
    def test_path_roles_are_diagnostics_for_obvious_file_roles(self) -> None:
        self.assertIn(
            "roadmap-suggested",
            audit_corpus_data.path_roles("TauCetiRoadmap/Foo/Suggested.lean"),
        )
        self.assertIn(
            "generated-path",
            audit_corpus_data.path_roles("generated/foo/ChallengeDeps.lean"),
        )
        self.assertIn(
            "test-fixture-path",
            audit_corpus_data.path_roles("Tests/Fixtures/Example.lean"),
        )
        self.assertIn(
            "vendored-path",
            audit_corpus_data.path_roles("Project/Vendored/Library/Foo.lean"),
        )

    def test_strict_import_aggregator_requires_no_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "Umbrella.lean"
            path.write_text("public import Foo\nimport Bar\n")
            roles, counts = audit_corpus_data.lean_content_roles(path)
            self.assertIn("import-aggregator", roles)
            self.assertEqual(counts["imports"], 2)

            path.write_text("import Foo\n\ntheorem owner : True := by trivial\n")
            roles, _ = audit_corpus_data.lean_content_roles(path)
            self.assertNotIn("import-aggregator", roles)

    def test_sorry_is_diagnostic_not_an_exclusion_role(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "Partial.lean"
            path.write_text("theorem useful_statement : True := by sorry\n")
            roles, _ = audit_corpus_data.lean_content_roles(path)
            self.assertIn("contains-sorry-admit", roles)
            self.assertNotIn("import-aggregator", roles)


if __name__ == "__main__":
    unittest.main()
