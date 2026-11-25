"""Exercise the actual just CLI on a checkout without local index shards."""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class SearchCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix=".tmp-search-cli-", dir=ROOT)
        self.addCleanup(temporary.cleanup)
        self.checkout = pathlib.Path(temporary.name)
        shutil.copyfile(ROOT / "justfile", self.checkout / "justfile")

    def assert_missing_index(self, query: str = "IsometryEquiv") -> None:
        result = subprocess.run(
            ["just", "search", query], cwd=self.checkout, text=True,
            capture_output=True, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Missing local Zoekt index: .zoekt", result.stderr)
        self.assertIn("just index", result.stderr)
        self.assertIn("just search-remote", result.stderr)
        if query == "IsometryEquiv":
            self.assertIn("just search-remote IsometryEquiv", result.stderr)
        self.assertNotIn("no such file or directory: ./bin/zoekt", result.stderr)

    def test_absent_index(self) -> None:
        self.assert_missing_index()

    def test_empty_index(self) -> None:
        (self.checkout / ".zoekt").mkdir()
        self.assert_missing_index()

    def test_non_shards_are_not_an_index(self) -> None:
        index = self.checkout / ".zoekt"
        index.mkdir()
        (index / "README").write_text("no shards")
        (index / "not-a-shard.zoekt").mkdir()
        self.assert_missing_index()

    def test_query_is_not_executed_as_shell_source(self) -> None:
        self.assert_missing_index("$(touch sentinel)")
        self.assertFalse((self.checkout / "sentinel").exists())


if __name__ == "__main__":
    unittest.main()
