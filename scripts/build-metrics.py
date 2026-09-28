#!/usr/bin/env python3
"""Build reader-facing corpus totals from sources.tsv and source-topics.tsv.

Operational file/line counts are not corpus metrics.  Corpus membership, which
requires primary documents and verified shards for each source, is checked by
``scripts/index-source.py verify``.
"""

from __future__ import annotations

import json
from collections import Counter

from filtering_lib import ROOT, sources

OUT = ROOT / "site" / "metrics.json"

LABELS = {
    "lean": "Lean 4",
    "rocq": "Rocq",
    "agda": "Agda",
    "isabelle": "Isabelle",
    "hol-light": "HOL Light",
    "hol4": "HOL4",
    "mizar": "Mizar",
    "metamath": "Metamath",
    "acl2": "ACL2",
    "pvs": "PVS",
    "twelf": "Twelf / LF",
}

ORDER = tuple(LABELS)


def main() -> None:
    rows = sources()
    counts = Counter(source.proof_assistant for source in rows)
    registered_names = {source.repository for source in rows}

    ecosystems = []
    for kind in ORDER:
        ecosystems.append({"kind": kind, "label": LABELS[kind], "sources": counts[kind]})

    topic_count = len(
        {
            fields[1]
            for line in (ROOT / "source-topics.tsv").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
            for fields in [line.split("\t")]
            if len(fields) == 2 and fields[0] in registered_names
        }
    )
    payload = {
        "summary": {
            "sources": len(rows),
            "proof_assistants": len([kind for kind in ORDER if counts[kind]]),
            "topics": topic_count,
        },
        "ecosystems": ecosystems,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        f"{OUT}: {len(rows)} sources, {payload['summary']['proof_assistants']} proof assistants, "
        f"{topic_count} topics"
    )


if __name__ == "__main__":
    main()
