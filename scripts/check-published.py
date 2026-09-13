#!/usr/bin/env python3
"""Require the published search index to match the canonical source inventory."""

from __future__ import annotations

import csv
import json
import pathlib
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://formalization-corpus.dzackgarza.com/api/list"


def expected_sources() -> set[str]:
    with (ROOT / "sources.tsv").open(newline="") as handle:
        return {
            pathlib.PurePosixPath(row["directory"]).name
            for row in csv.DictReader(handle, delimiter="\t")
        }


def published_sources() -> set[str]:
    request = urllib.request.Request(
        API,
        data=b'{"Q":""}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    return {
        row["Repository"]["Name"]
        for row in payload.get("List", {}).get("Repos", [])
    }


def main() -> None:
    expected = expected_sources()
    for attempt in range(30):
        actual = published_sources()
        if actual == expected:
            print(f"published index matches sources.tsv: {len(expected)} sources")
            return
        if attempt < 29:
            time.sleep(1)

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    lines = ["published index differs from sources.tsv"]
    if missing:
        lines.append("missing:\n  " + "\n  ".join(missing))
    if extra:
        lines.append("extra:\n  " + "\n  ".join(extra))
    raise SystemExit("\n".join(lines))


if __name__ == "__main__":
    main()
