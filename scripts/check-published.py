#!/usr/bin/env python3
"""Require the published search index to match the canonical source inventory.

A lapsed source, whose Git upstream has no HEAD, has no shard; it is not expected.
"""

from __future__ import annotations

import http.client
import json
import time
import urllib.error
from functools import lru_cache

from filtering_lib import sources, upstream_head
from published_index import published_sources

SOURCES = {source.repository: source for source in sources()}


@lru_cache(maxsize=None)
def lapsed(repository: str) -> bool:
    source = SOURCES[repository]
    return source.transport != "web-dir" and upstream_head(source) is None


def main() -> None:
    expected = set(SOURCES)
    actual: set[str] = set()
    missing: list[str] = []
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
        missing = sorted(repository for repository in expected - actual if not lapsed(repository))
        if not missing and actual <= expected:
            print(f"published index matches sources.tsv: {len(actual)} sources, {len(expected - actual)} lapsed")
            return
        if attempt < 29:
            time.sleep(1)

    if last_error is not None and not actual:
        raise SystemExit(f"could not read published source inventory after retries: {last_error}")

    extra = sorted(actual - expected)
    lines = ["published index differs from sources.tsv"]
    if missing:
        lines.append("missing:\n  " + "\n  ".join(missing))
    if extra:
        lines.append("extra:\n  " + "\n  ".join(extra))
    raise SystemExit("\n".join(lines))


if __name__ == "__main__":
    main()
