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


def load_review_refresh():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(
            "formalization_review_refresh", SCRIPTS / "refresh-review-filter-state.py"
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


    def test_retired_batch_member_is_selectable_for_cleanup_but_not_hydration(self) -> None:
        source_cache = load_source_cache()
        active = {"active": object()}
        campaign = {"active": object(), "retired": object()}
        with (
            mock.patch.object(source_cache, "source_map", return_value=active),
            mock.patch.object(source_cache, "campaign_source_map", return_value=campaign),
            mock.patch.object(source_cache, "batch_repositories", return_value=["active", "retired"]),
        ):
            self.assertEqual(
                source_cache.select_repositories([], "RRB-X", allow_retired=True),
                ["active", "retired"],
            )
            with self.assertRaisesRegex(SystemExit, "unknown active repositories"):
                source_cache.select_repositories([], "RRB-X", allow_retired=False)

    def test_retired_reindex_removes_remote_shard_without_building_local_index(self) -> None:
        source_cache = load_source_cache()
        with (
            mock.patch.object(source_cache, "source_map", return_value={}),
            mock.patch.object(source_cache, "retired_repository_names", return_value={"retired"}),
            mock.patch.object(source_cache, "remove_repository_shards") as remove,
            mock.patch.object(source_cache, "ensure_zoekt_index") as build_index,
            mock.patch.object(source_cache, "materialize") as materialize,
        ):
            source_cache.reindex(["retired"], keep_views=False, validate_published=False)
        remove.assert_called_once_with("retired")
        build_index.assert_not_called()
        materialize.assert_not_called()

    def test_retired_remote_shard_deletion_is_exact_and_verified(self) -> None:
        source_cache = load_source_cache()
        with (
            mock.patch.object(
                source_cache, "remote_shard_names", side_effect=[["retired_v16.00000.zoekt"], []]
            ),
            mock.patch.object(source_cache, "remote_command") as remote,
            mock.patch.object(source_cache.remote_shard_inventory, "cache_clear"),
        ):
            source_cache.remove_repository_shards("retired")
        args = remote.call_args.args[0]
        self.assertEqual(args[:2], ["rm", "-f"])
        self.assertEqual(args[2], f"{source_cache.REMOTE_INDEX}/retired_v16.00000.zoekt")

    def test_review_refresh_accepts_retired_campaign_identity(self) -> None:
        refresh = load_review_refresh()
        active = type("Source", (), {"repository": "active"})()
        with (
            mock.patch.object(refresh, "sources", return_value=[active]),
            mock.patch.object(
                refresh,
                "load_catalogue_index",
                return_value=[{"repository": "active"}, {"repository": "retired", "inventory_status": "retired"}],
            ),
            mock.patch.object(refresh, "batch_repositories", return_value={"active", "retired"}),
        ):
            self.assertEqual(refresh.selected_repositories([], "RRB-X"), {"active", "retired"})


if __name__ == "__main__":
    unittest.main()
