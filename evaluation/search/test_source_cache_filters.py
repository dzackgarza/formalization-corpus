from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("source_cache_filters", ROOT / "scripts/source-cache.py")
assert spec and spec.loader
source_cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_cache)


class SourceCacheFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="source-cache-filter-test-")
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.global_config = self.root / "global.gitconfig"
        self.global_config.touch()
        env = mock.patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": str(self.global_config),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Source Cache Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Source Cache Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_LFS_SKIP_SMUDGE": "0",
        })
        env.start()
        self.addCleanup(env.stop)

    def git(self, *args: str, cwd: pathlib.Path | None = None) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd or self.root, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout

    def configure_filter(self) -> None:
        # Include the driver from a separate file, as user Git configs may do.
        included = self.root / "filters.gitconfig"
        self.git("config", "--global", "include.path", str(included))
        for key, value in (
            ("filter.marker.clean", "sed 's/^WORKTREE://'"),
            ("filter.marker.smudge", "sed 's/^/WORKTREE:/'"),
            ("filter.marker.required", "true"),
        ):
            self.git("config", "--file", str(included), key, value)

    def upstream(self, filename: str, data: bytes, driver: str) -> pathlib.Path:
        upstream = self.root / "upstream"
        self.git("init", "-b", "main", str(upstream))
        self.git("config", "uploadpack.allowFilter", "true", cwd=upstream)
        self.git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=upstream)
        (upstream / ".gitattributes").write_text(f"{filename} filter={driver} -text\n")
        (upstream / filename).write_bytes(data)
        self.git("add", ".", cwd=upstream)
        self.git("commit", "-m", "fixture", cwd=upstream)
        return upstream

    def source(self, upstream: pathlib.Path, checkout: pathlib.Path) -> source_cache.Source:
        return source_cache.Source(
            url=upstream.as_uri(), directory=checkout, proof_assistant="lean",
            transport="git", sync_group="test", discovered_via="test",
        )

    def invalidate_stat(self, path: pathlib.Path) -> None:
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))

    def legacy_checkout(self, upstream: pathlib.Path) -> pathlib.Path:
        checkout = self.root / "legacy"
        self.git("clone", upstream.as_uri(), str(checkout))
        return checkout

    def test_smudged_checkout_is_clean_and_real_changes_are_rejected(self) -> None:
        self.configure_filter()
        upstream = self.upstream("payload.data", b"WORKTREE:original\n", "marker")
        checkout = self.legacy_checkout(upstream)
        source = self.source(upstream, checkout)
        payload = checkout / "payload.data"
        self.assertEqual(payload.read_bytes(), b"WORKTREE:original\n")
        self.invalidate_stat(payload)
        source_cache.ensure_clean(source)

        payload.write_bytes(b"WORKTREE:changed\n")
        with self.assertRaisesRegex(SystemExit, "dirty source cache"):
            source_cache.ensure_clean(source)
        self.git("add", "payload.data", cwd=checkout)
        with self.assertRaisesRegex(SystemExit, "dirty source cache"):
            source_cache.ensure_clean(source)
        self.git("reset", "--hard", "HEAD", cwd=checkout)
        (checkout / "untracked").write_text("do not delete")
        with self.assertRaisesRegex(SystemExit, "untracked material"):
            source_cache.ensure_clean(source)

    def test_both_global_config_files_keep_their_precedence(self) -> None:
        home = self.root / "home"
        xdg = self.root / "xdg"
        (xdg / "git").mkdir(parents=True)
        home.mkdir()
        with mock.patch.dict(os.environ, {"HOME": str(home), "XDG_CONFIG_HOME": str(xdg)}):
            os.environ.pop("GIT_CONFIG_GLOBAL")
            config = xdg / "git/config"
            self.git("config", "--file", str(config), "filter.marker.clean", "sed 's/^WORKTREE://'")
            self.git("config", "--file", str(config), "filter.marker.smudge", "sed 's/^/WRONG:/'")
            self.git("config", "--file", str(home / ".gitconfig"), "filter.marker.smudge", "sed 's/^/WORKTREE:/'")
            upstream = self.upstream("payload.data", b"WORKTREE:original\n", "marker")
            source = self.hydrate(upstream)
            payload = source.root / "payload.data"
            self.assertEqual(payload.read_bytes(), b"WORKTREE:original\n")
            self.invalidate_stat(payload)
            source_cache.ensure_clean(source)

    def test_local_filter_overrides_global(self) -> None:
        self.configure_filter()
        upstream = self.upstream("payload.data", b"WORKTREE:original\n", "marker")
        checkout = self.legacy_checkout(upstream)
        self.git("config", "filter.marker.clean", "sed 's/^LOCAL://'", cwd=checkout)
        self.git("config", "filter.marker.smudge", "sed 's/^/LOCAL:/'", cwd=checkout)
        payload = checkout / "payload.data"
        payload.unlink()
        self.git("checkout", "--", "payload.data", cwd=checkout)
        self.assertEqual(payload.read_bytes(), b"LOCAL:original\n")
        self.invalidate_stat(payload)
        source_cache.ensure_clean(self.source(upstream, checkout))

    def hydrate(self, upstream: pathlib.Path) -> source_cache.Source:
        fixture = self.root / "corpus"
        (fixture / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "sync-manifest.zsh", fixture)
        shutil.copy2(ROOT / "scripts/source_git.py", fixture / "scripts")
        checkout = fixture / "nested"
        source = self.source(upstream, checkout)
        with (
            mock.patch.object(source_cache, "ROOT", fixture),
            mock.patch.object(source_cache, "source_map", return_value={source.repository: source}),
            mock.patch.object(source_cache, "catalogue_map", return_value={}),
        ):
            source_cache.hydrate(source.repository, latest=True)
        return source

    def test_hydration_and_clean_check_share_filters_without_url_rewrites(self) -> None:
        self.configure_filter()
        upstream = self.upstream("payload.data", b"WORKTREE:original\n", "marker")
        # Ambient Git would redirect the canonical URL to a nonexistent repository.
        self.git("config", "--global", f"url.{(self.root / 'missing').as_uri()}.insteadOf", upstream.as_uri())
        with self.assertRaises(subprocess.CalledProcessError):
            self.git("ls-remote", upstream.as_uri(), "HEAD")
        source = self.hydrate(upstream)
        payload = source.root / "payload.data"
        self.assertEqual(payload.read_bytes(), b"WORKTREE:original\n")
        self.invalidate_stat(payload)
        source_cache.ensure_clean(source)

        # Existing hydration must likewise fetch and check out with the filter.
        (upstream / "payload.data").write_bytes(b"WORKTREE:next revision\n")
        self.git("commit", "-am", "next", cwd=upstream)
        source_cache.checkout_revision(source, None, latest=True)
        self.assertEqual(payload.read_bytes(), b"WORKTREE:next revision\n")
        self.invalidate_stat(payload)
        source_cache.ensure_clean(source)

    @unittest.skipUnless(shutil.which("git-lfs"), "Git LFS executable not installed")
    def test_real_lfs_smudged_checkout_is_clean(self) -> None:
        self.git("lfs", "install", "--skip-repo")
        data = b"\x00source cache LFS payload\xff"
        upstream = self.upstream("solution_tree_v6.zip", data, "lfs")
        checkout = self.legacy_checkout(upstream)
        payload = checkout / "solution_tree_v6.zip"
        self.assertEqual(payload.read_bytes(), data)
        self.assertTrue(self.git("show", "HEAD:solution_tree_v6.zip", cwd=checkout).startswith(
            "version https://git-lfs.github.com/spec/v1\n"
        ))
        self.invalidate_stat(payload)
        source = self.source(upstream, checkout)
        source_cache.ensure_clean(source)
        payload.write_bytes(data + b"changed")
        with self.assertRaisesRegex(SystemExit, "dirty source cache"):
            source_cache.ensure_clean(source)

    @unittest.skipUnless(shutil.which("git-lfs"), "Git LFS executable not installed")
    def test_gc_keeps_dirty_lfs_checkout_and_releases_clean_checkout(self) -> None:
        self.git("lfs", "install", "--skip-repo")
        data = b"\x00source cache LFS payload\xff"
        upstream = self.upstream("solution_tree_v6.zip", data, "lfs")
        checkout = self.legacy_checkout(upstream)
        payload = checkout / "solution_tree_v6.zip"
        source = self.source(upstream, checkout)
        revision = self.git("rev-parse", "HEAD", cwd=checkout).strip()
        catalogue = {source.repository: {"source_revision": revision}}
        sources = {source.repository: source}
        # Supply the persisted catalogue and published shard inventory without
        # touching the actual remote index. The Git checks and deletion are real.
        with (
            mock.patch.object(source_cache, "source_map", return_value=sources),
            mock.patch.object(source_cache, "campaign_source_map", return_value=sources),
            mock.patch.object(source_cache, "campaign_catalogue_map", return_value=catalogue),
            mock.patch.object(source_cache, "retired_repository_names", return_value=set()),
            mock.patch.object(source_cache, "remote_shard_names", return_value=["test.zoekt"]),
            mock.patch.object(source_cache, "PRIMARY_VIEW", self.root / "primary"),
            mock.patch.object(source_cache, "METADATA_VIEW", self.root / "metadata"),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            payload.write_bytes(data + b"changed")
            source_cache.gc_source_cache()
            self.assertTrue(checkout.is_dir())
            self.assertIn("dirty source cache", output.getvalue())
            payload.write_bytes(data)
            self.invalidate_stat(payload)
            source_cache.gc_source_cache()
            self.assertFalse(checkout.exists())
            self.assertIn("dehydrated=1 kept=0", output.getvalue())

    @unittest.skipUnless(shutil.which("git-lfs"), "Git LFS executable not installed")
    def test_real_lfs_hydration_preserves_filter_configuration(self) -> None:
        self.git("lfs", "install", "--skip-repo")
        data = b"\x00source cache LFS payload\xff"
        upstream = self.upstream("solution_tree_v6.zip", data, "lfs")
        source = self.hydrate(upstream)
        payload = source.root / "solution_tree_v6.zip"
        self.assertEqual(payload.read_bytes(), data)
        self.invalidate_stat(payload)
        source_cache.ensure_clean(source)


if __name__ == "__main__":
    unittest.main()
