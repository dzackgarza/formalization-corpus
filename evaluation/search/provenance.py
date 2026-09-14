#!/usr/bin/env python3
"""Repository-state provenance shared by search-quality reports."""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
from typing import Any


def _git(root: pathlib.Path, *args: str, text: bool = False) -> bytes | str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=text, stderr=subprocess.DEVNULL
    )


def repository_state(root: pathlib.Path) -> dict[str, Any]:
    """Describe the exact Git/worktree state used by a measurement.

    A commit hash alone is sufficient only for a clean checkout.  For exploratory
    dirty-tree runs, retain both the porcelain status and a hash over the tracked
    diff plus the contents of untracked files.  Official lab-log archival rejects
    dirty measurements by default, but keeping this fingerprint makes exploratory
    reports honest about what was actually executed.
    """

    commit = str(_git(root, "rev-parse", "HEAD", text=True)).strip()
    status = str(
        _git(root, "status", "--porcelain=v1", "--untracked-files=all", text=True)
    )
    tracked_diff = bytes(_git(root, "diff", "HEAD", "--binary"))

    h = hashlib.sha256()
    h.update(tracked_diff)
    untracked: list[str] = []
    for raw in status.splitlines():
        if not raw.startswith("?? "):
            continue
        rel = raw[3:]
        path = root / rel
        untracked.append(rel)
        h.update(b"\0UNTRACKED\0")
        h.update(rel.encode())
        h.update(b"\0")
        try:
            h.update(path.read_bytes())
        except OSError:
            h.update(b"<unreadable>")

    return {
        "commit": commit,
        "worktree_clean": not bool(status.strip()),
        "status": status.splitlines(),
        "state_sha256": h.hexdigest(),
        "untracked_files": untracked,
    }
