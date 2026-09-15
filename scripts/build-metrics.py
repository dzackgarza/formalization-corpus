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
import time
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


def indexed_source_names() -> set[str]:
    """Return the canonical index source identities.

    A fully indexed workstation validates its local ``.zoekt`` shards.  A
    source-review checkout may intentionally keep the 10+ GiB production index
    only on the deployment host; in that case validate the published inventory
    through the same API used by ``check-published.py`` rather than requiring a
    redundant local copy.
    """
    out: set[str] = set()
    for path in (ROOT / ".zoekt").glob("*.zoekt"):
        found = SHARD.fullmatch(path.name)
        if found:
            out.add(found.group(1))
    if out:
        return out

    from published_index import published_sources

    last_error: Exception | None = None
    for attempt in range(5):
        try:
            out = published_sources()
            if out:
                print("no local .zoekt shards; validating the published index inventory")
                return out
        except Exception as exc:
            last_error = exc
        if attempt < 4:
            time.sleep(1)
    detail = f": {last_error}" if last_error is not None else ""
    raise SystemExit(f"no local index shards and published index inventory is unavailable{detail}")


def is_proof_file(kind: str, root: pathlib.Path, path: pathlib.Path) -> bool:
    rel = path.relative_to(root)
    if any(part in SKIP_PARTS for part in rel.parts):
        return False
    if kind == "acl2" and ".sys" in rel.parts:
        return False
    return any(path.name.endswith(suffix) for suffix in FORMAL_SUFFIXES[kind])


def catalogue_formal_file_counts() -> dict[str, int]:
    """Formal-file counts from the committed audit snapshot for ghost sources."""
    index_path = ROOT / "filtering/repository-review/catalogue.jsonl"
    if not index_path.is_file():
        return {}
    out: dict[str, int] = {}
    for line in index_path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("inventory_status", "active") != "active":
            continue
        catalogue = json.loads((ROOT / row["catalogue_file"]).read_text())
        out[str(row["repository"])] = int(catalogue.get("totals", {}).get("formal_source_files", 0))
    return out


def main() -> None:
    rows = source_rows()
    counts = Counter(kind for kind, _ in rows)
    source_names = {relative.name for _, relative in rows}
    indexed = indexed_source_names()
    problems: list[str] = []
    for name in sorted(indexed - source_names):
        problems.append(f"{name}: index shard exists for a source absent from sources.tsv")
    registered_names = source_names
    audited_formal_counts = catalogue_formal_file_counts()

    for kind, relative in rows:
        source = ROOT / relative
        name = relative.name
        if source.exists():
            if not any(
                path.is_file() and is_proof_file(kind, source, path)
                for path in source.rglob("*")
            ):
                problems.append(f"{name}: no {kind} source-language files")
        elif audited_formal_counts.get(name, 0) <= 0:
            problems.append(f"{name}: source is ghosted and committed audit manifest has no formal source files")
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
