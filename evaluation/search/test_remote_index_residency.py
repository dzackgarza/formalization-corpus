from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def load_source_cache():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(
            "formalization_source_cache", SCRIPTS / "source-cache.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


class RemoteIndexResidencyTests(unittest.TestCase):
    def test_publish_index_is_verification_only(self) -> None:
        lines = (ROOT / "justfile").read_text().splitlines()
        start = lines.index("publish-index:") + 1
        body_lines: list[str] = []
        for line in lines[start:]:
            if line and not line.startswith((" ", "\t")) and not line.startswith("#"):
                break
            body_lines.append(line)
        body = "\n".join(body_lines)
        self.assertNotIn("rsync", body)
        self.assertNotIn(".zoekt/", body)
        self.assertIn("check-published.py", body)

    def test_source_cache_has_no_persistent_local_index(self) -> None:
        text = (SCRIPTS / "source-cache.py").read_text()
        self.assertNotIn('INDEX = ROOT / ".zoekt"', text)
        self.assertIn("REMOTE_HOST", text)
        self.assertIn("publish_repository_shards", text)

    def test_remote_shard_lookup_uses_search_host(self) -> None:
        source_cache = load_source_cache()
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Example__Repo_v16.00000.zoekt\n", stderr=""
        )
        with mock.patch.object(source_cache, "remote_command", return_value=completed) as remote:
            names = source_cache.remote_shard_names("Example__Repo")
        self.assertEqual(names, ["Example__Repo_v16.00000.zoekt"])
        args = remote.call_args.args[0]
        self.assertEqual(args[0], "find")
        self.assertEqual(args[1], source_cache.REMOTE_INDEX)
        self.assertIn("*.zoekt", args)
        self.assertNotIn("Example__Repo_v*.zoekt", args)


if __name__ == "__main__":
    unittest.main()
