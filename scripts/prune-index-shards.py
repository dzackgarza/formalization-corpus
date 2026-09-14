#!/usr/bin/env python3
"""Remove Zoekt shards whose repository is no longer in sources.tsv."""

from __future__ import annotations

import argparse
import pathlib
import re

from filtering_lib import sources


SHARD = re.compile(r"(.+)_v\d+\.\d+\.zoekt$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=pathlib.Path)
    args = parser.parse_args()

    registered = {source.repository for source in sources()}
    removed: list[pathlib.Path] = []
    if args.index.exists():
        for path in args.index.glob("*.zoekt"):
            match = SHARD.fullmatch(path.name)
            if match and match.group(1) not in registered:
                path.unlink()
                removed.append(path)
    print(f"pruned {len(removed)} stale shard(s) from {args.index}")
    for path in removed:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
