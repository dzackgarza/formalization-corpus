#!/usr/bin/env python3
"""Read the canonical published Zoekt source inventory."""

from __future__ import annotations

import json
import urllib.request

API = "https://formalization-corpus.dzackgarza.com/api/list"


def published_sources(*, timeout: float = 30) -> set[str]:
    request = urllib.request.Request(
        API,
        data=b'{"Q":""}',
        headers={
            "Content-Type": "application/json",
            "User-Agent": "formalization-corpus-publish-check/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return {
        row["Repository"]["Name"]
        for row in payload.get("List", {}).get("Repos", [])
    }
