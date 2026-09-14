#!/usr/bin/env python3
"""Validate the hydrated corpus and build reader-facing corpus totals.

Operational file/line counts are deliberately not published as corpus metrics.
This script does inspect source-language files and index shards because corpus
membership requires both; discrepancies are errors rather than public stats.
"""

from __future__ import annotations

import json
import pathlib
import re
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "metrics.json"

SOURCE_TABLE = ROOT / "sources.tsv"

FORMAL_SUFFIXES: dict[str, tuple[str, ...]] = {
    "lean": (".lean",),
    "rocq": (".v",),
    "agda": (".agda", ".lagda", ".lagda.md", ".lagda.rst", ".lagda.tex"),
    "isabelle": (".thy",),
    "hol-light": (".ml", ".hl"),
    "hol4": (".sml", ".sig"),
    "mizar": (".miz",),
    "metamath": (".mm", ".mm0", ".mm1"),
    "acl2": (".lisp", ".lsp", ".acl2"),
    "pvs": (".pvs",),
    "twelf": (".elf",),
}

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
SHARD = re.compile(r"(.+)_v\d+\.\d+\.zoekt$")
DOCUMENTATION_PREFIX = "docs__"
SKIP_PARTS = {".git", ".lake", "node_modules"}


def source_rows() -> list[tuple[str, pathlib.Path]]:
    import csv

    rows: list[tuple[str, pathlib.Path]] = []
    names: set[str] = set()
    with SOURCE_TABLE.open(newline="") as handle:
        for record in csv.DictReader(handle, delimiter="\t"):
            directory = pathlib.Path(record["directory"])
            name = directory.name
            if name in names:
                raise ValueError(f"duplicate corpus source name: {name}")
            names.add(name)
            rows.append((record["proof_assistant"], directory))
    return rows


def canonical_index_source_name(shard_name: str, registered: set[str]) -> str:
    if shard_name in registered:
        return shard_name
    if shard_name.startswith(DOCUMENTATION_PREFIX):
        source = shard_name[len(DOCUMENTATION_PREFIX):]
        if source in registered:
            return source
    return shard_name


def indexed_source_names(registered: set[str]) -> set[str]:
    out: set[str] = set()
    for path in (ROOT / ".zoekt").glob("*.zoekt"):
        found = SHARD.fullmatch(path.name)
        if found:
            out.add(canonical_index_source_name(found.group(1), registered))
    return out


def is_proof_file(kind: str, root: pathlib.Path, path: pathlib.Path) -> bool:
    rel = path.relative_to(root)
    if any(part in SKIP_PARTS for part in rel.parts):
        return False
    if kind == "acl2" and ".sys" in rel.parts:
        return False
    return any(path.name.endswith(suffix) for suffix in FORMAL_SUFFIXES[kind])


def main() -> None:
    rows = source_rows()
    counts = Counter(kind for kind, _ in rows)
    source_names = {relative.name for _, relative in rows}
    indexed = indexed_source_names(source_names)
    problems: list[str] = []
    for name in sorted(indexed - source_names):
        problems.append(f"{name}: index shard exists for a source absent from sources.tsv")
    registered_names = source_names

    for kind, relative in rows:
        source = ROOT / relative
        name = relative.name
        if not source.exists():
            problems.append(f"{name}: local source is absent")
            continue
        if not any(
            path.is_file() and is_proof_file(kind, source, path)
            for path in source.rglob("*")
        ):
            problems.append(f"{name}: no {kind} source-language files")
        if name not in indexed:
            problems.append(f"{name}: no index shard")

    if problems:
        raise SystemExit(
            "corpus invariant failed:\n  " + "\n  ".join(problems)
        )

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
