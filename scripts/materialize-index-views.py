#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil

from filtering_lib import (
    CURRENT,
    ROOT,
    is_formal_file,
    is_lean_build_metadata,
    is_readme,
    iter_files,
    load_jsonl,
    sources,
)


def link(source: pathlib.Path, destination: pathlib.Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=pathlib.Path, default=ROOT / ".index-primary")
    parser.add_argument("--metadata", type=pathlib.Path, default=ROOT / ".index-metadata")
    parser.add_argument("--repository", action="append", default=[], help="materialize only this repository; may be repeated")
    args = parser.parse_args()

    decisions = load_jsonl(CURRENT)
    excluded_primary = {
        (row["repository"], row["file"])
        for row in decisions
        if row["primary"] == "exclude"
    }
    included_auxiliary = {
        (row["repository"], row["file"])
        for row in decisions
        if row["auxiliary"] == "include"
    }
    source_rows = sources()
    registered = {source.repository for source in source_rows}
    selected = set(args.repository)
    unknown = sorted(selected - registered)
    if unknown:
        raise SystemExit(f"unknown repositories: {unknown}")
    partial = bool(selected)
    if not partial:
        selected = registered

    for root in (args.primary, args.metadata):
        if partial:
            root.mkdir(parents=True, exist_ok=True)
            for repository in selected:
                target = root / repository
                if target.exists():
                    shutil.rmtree(target)
        else:
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(parents=True)

    primary_counts: dict[str, int] = {}
    metadata_counts: dict[str, int] = {}
    for source in source_rows:
        if source.repository not in selected:
            continue
        primary_count = 0
        metadata_count = 0
        if not source.root.exists():
            raise SystemExit(f"source is not hydrated: {source.repository}; run `just source-hydrate {source.repository}`")
        for path in iter_files(source):
            rel = path.relative_to(source.root).as_posix()
            key = (source.repository, rel)
            if (
                is_formal_file(source.proof_assistant, path)
                and not is_lean_build_metadata(path)
                and key not in excluded_primary
            ):
                link(path, args.primary / source.repository / rel)
                primary_count += 1
            if key in included_auxiliary:
                link(path, args.metadata / source.repository / rel)
                metadata_count += 1
        primary_counts[source.repository] = primary_count
        metadata_counts[source.repository] = metadata_count

    empty = sorted(repo for repo, count in primary_counts.items() if count == 0)
    if empty:
        raise SystemExit(
            "derived primary view would erase registered sources:\n  " + "\n  ".join(empty)
        )
    mode = "partial" if partial else "full"
    print(
        f"{mode} primary view: {sum(primary_counts.values())} documents across {len(primary_counts)} sources; "
        f"separate metadata view: {sum(metadata_counts.values())} documents"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
