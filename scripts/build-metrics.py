#!/usr/bin/env python3
"""Measure the searchable formal corpus without guessing declaration counts.

The metrics here are deliberately syntax-agnostic.  A "formal unit" is a file
whose extension is native proof/theory source for its prover.  Generated ACL2
`.sys` rune reports and PVS `.prf` proof traces are excluded: they are useful to
Zoekt, but they would badly distort a measure of mathematical source coverage.

Definitions/theorems are *not* counted globally.  Their concrete syntax and
elaboration model differ substantially across provers, and most of the Lean
projects in this corpus are sparse source checkouts rather than built
environments.  A cross-prover declaration total belongs here only after it can
be obtained from prover-native parsers/environments rather than keyword grep.
"""

from __future__ import annotations

import json
import pathlib
import re
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "metrics.json"

MANIFESTS: tuple[tuple[str | None, str], ...] = (
    ("lean", "repos.tsv"),
    ("reservoir", "reservoir.tsv"),
    (None, "port-sources.tsv"),
)

FORMAL_SUFFIXES: dict[str, tuple[str, ...]] = {
    "lean": (".lean",),
    "reservoir": (".lean",),
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
    "lean": "Lean (curated)",
    "reservoir": "Lean Reservoir",
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


def manifest_rows() -> list[tuple[str, pathlib.Path]]:
    rows: list[tuple[str, pathlib.Path]] = []
    names: set[str] = set()
    for default_kind, manifest in MANIFESTS:
        for line in (ROOT / manifest).read_text().splitlines():
            if not line.strip():
                continue
            fields = line.split("\t")
            directory = pathlib.Path(fields[1])
            kind = fields[2] if len(fields) > 2 and fields[2] else default_kind
            if kind is None:
                raise ValueError(f"{manifest}: no kind for {line!r}")
            name = directory.name
            if name in names:
                raise ValueError(f"duplicate corpus source name: {name}")
            names.add(name)
            rows.append((kind, directory))
    return rows


def indexed_source_names() -> set[str]:
    out: set[str] = set()
    for path in (ROOT / ".zoekt").glob("*.zoekt"):
        found = SHARD.fullmatch(path.name)
        if found:
            out.add(found.group(1))
    return out


def is_formal_unit(kind: str, root: pathlib.Path, path: pathlib.Path) -> bool:
    rel = path.relative_to(root)
    if any(part in SKIP_PARTS for part in rel.parts):
        return False
    if kind == "acl2" and ".sys" in rel.parts:
        return False
    return any(path.name.endswith(suffix) for suffix in FORMAL_SUFFIXES[kind])


def line_count(path: pathlib.Path) -> int:
    lines = 0
    last = b""
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            lines += chunk.count(b"\n")
            last = chunk[-1:]
    return lines + int(bool(last) and last != b"\n")


def main() -> None:
    rows = manifest_rows()
    indexed = indexed_source_names()
    stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "registered_sources": 0,
            "indexed_sources": 0,
            "formal_content_sources": 0,
            "formal_units": 0,
            "formal_lines": 0,
            "formal_bytes": 0,
        }
    )

    for kind, relative in rows:
        source = ROOT / relative
        name = relative.name
        bucket = stats[kind]
        bucket["registered_sources"] += 1
        bucket["indexed_sources"] += int(name in indexed)

        files = 0
        lines = 0
        byte_count = 0
        if source.exists():
            for path in source.rglob("*"):
                if not path.is_file() or not is_formal_unit(kind, source, path):
                    continue
                files += 1
                lines += line_count(path)
                byte_count += path.stat().st_size
        bucket["formal_content_sources"] += int(files > 0)
        bucket["formal_units"] += files
        bucket["formal_lines"] += lines
        bucket["formal_bytes"] += byte_count

    ecosystems = []
    for kind in ORDER:
        bucket = stats[kind]
        ecosystems.append({"kind": kind, "label": LABELS[kind], **bucket})

    totals = {
        key: sum(bucket[key] for bucket in stats.values())
        for key in (
            "registered_sources",
            "indexed_sources",
            "formal_content_sources",
            "formal_units",
            "formal_lines",
            "formal_bytes",
        )
    }
    totals["curated_sources"] = sum(
        bucket["registered_sources"] for kind, bucket in stats.items() if kind != "reservoir"
    )
    totals["curated_formal_content_sources"] = sum(
        bucket["formal_content_sources"] for kind, bucket in stats.items() if kind != "reservoir"
    )
    # Reservoir is Lean, not a twelfth proof assistant family.
    totals["prover_families"] = len(stats) - int("reservoir" in stats)

    registered_names = {directory.name for _, directory in rows}
    payload = {
        "summary": totals,
        "ecosystems": ecosystems,
        "unindexed_sources": sorted(registered_names - indexed),
        "definitions": {
            "formal_unit": (
                "A prover-native theory/source file; ACL2 .sys generated rune reports "
                "and PVS .prf proof traces are excluded."
            ),
            "formal_lines": "Physical newline-delimited lines in those formal units.",
            "declaration_counts": (
                "Not reported until prover-native parsing/elaboration is available across the corpus."
            ),
        },
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        f"{OUT}: {totals['indexed_sources']}/{totals['registered_sources']} indexed sources, "
        f"{totals['formal_units']} formal units, {totals['formal_lines']} formal lines"
    )


if __name__ == "__main__":
    main()
