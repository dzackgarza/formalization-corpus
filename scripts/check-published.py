#!/usr/bin/env python3
"""Require the published search index to match the canonical source inventory."""

from __future__ import annotations

import csv
import http.client
import json
import pathlib
import time
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
from published_index import published_sources


def expected_sources() -> set[str]:
    with (ROOT / "sources.tsv").open(newline="") as handle:
        return {
            pathlib.PurePosixPath(row["directory"]).name
            for row in csv.DictReader(handle, delimiter="\t")
        }



def main() -> None:
    expected = expected_sources()
    actual: set[str] = set()
    last_error: Exception | None = None
    for attempt in range(30):
        try:
            actual = published_sources()
            last_error = None
        except (
            ConnectionResetError,
            TimeoutError,
            http.client.HTTPException,
            json.JSONDecodeError,
            urllib.error.URLError,
        ) as exc:
            last_error = exc
            if attempt < 29:
                time.sleep(1)
                continue
            break
        if actual == expected:
            print(f"published index matches sources.tsv: {len(expected)} sources")
            return
        if attempt < 29:
            time.sleep(1)

    if last_error is not None and not actual:
        raise SystemExit(f"could not read published source inventory after retries: {last_error}")

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
