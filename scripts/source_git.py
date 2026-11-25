"""Run Git for disposable source checkouts with isolated global configuration.

Public-source URLs must not be rewritten by the user's global Git config, even
during lazy blob fetches. Content filters, however, must be identical during
checkout and cleanliness checks. Keep only the global filter definitions, at
global precedence (repository-local definitions must still win).
"""
from __future__ import annotations

import os
import pathlib
import signal
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def source_git_environment(
    args: list[str], *, cwd: pathlib.Path | None = None
) -> Iterator[dict[str, str]]:
    # Source commands use an optional leading -C checkout. Resolve conditional
    # global includes in the same repository context as the actual command.
    prefix = args[:2] if args[:1] == ["-C"] else []
    # Unlike --global, a scoped query reads both the XDG and home global
    # files, in Git's normal precedence order, including conditional includes.
    query_env = dict(os.environ)
    query_env.pop("GIT_CONFIG", None)  # Only affects the git config subcommand.
    query = subprocess.run(
        ["git", *prefix, "config", "--includes", "--null", "--show-scope",
         "--get-regexp", r"^filter\."],
        cwd=cwd, env=query_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    # --get-regexp returns 1 with no diagnostics when no keys match.
    if query.returncode != 0 and (query.returncode != 1 or query.stderr):
        query.check_returncode()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull}
    fields = query.stdout.split(b"\0")[:-1]
    entries = [
        entry for scope, entry in zip(fields[::2], fields[1::2], strict=True)
        if scope == b"global"
    ]
    if not entries:
        yield env
        return

    # A separate global file preserves the original config precedence and
    # excludes unrelated settings (especially url.*.insteadOf). Git itself
    # serializes the values, including whitespace and quoting in filter commands.
    with tempfile.TemporaryDirectory(prefix="source-git-config-") as directory:
        config = pathlib.Path(directory) / "config"
        for entry in entries:
            key, separator, value = entry.partition(b"\n")
            subprocess.run(
                ["git", "config", "--file", str(config), "--add",
                 os.fsdecode(key), os.fsdecode(value) if separator else "true"],
                check=True,
            )
        env["GIT_CONFIG_GLOBAL"] = str(config)
        yield env


def main() -> int:
    # A shell timeout should also unwind the temporary config context.
    def terminate(signum: int, _frame: object) -> None:
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    args = sys.argv[1:]
    with source_git_environment(args) as env:
        return subprocess.run(["git", *args], env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
