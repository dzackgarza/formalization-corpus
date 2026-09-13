#!/usr/bin/env python3
"""Measure the searchable formal corpus without guessing declaration counts.

The metrics here are deliberately syntax-agnostic.  A "proof file" is a file
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
    ("lean", "reservoir.tsv"),
    (None, "port-sources.tsv"),
)

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


def is_proof_file(kind: str, root: pathlib.Path, path: pathlib.Path) -> bool:
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
            "sources": 0,
            "searchable_sources": 0,
            "sources_with_proof_files": 0,
            "proof_files": 0,
            "proof_source_lines": 0,
            "proof_source_bytes": 0,
        }
    )

    for kind, relative in rows:
        source = ROOT / relative
        name = relative.name
        bucket = stats[kind]
        bucket["sources"] += 1
        bucket["searchable_sources"] += int(name in indexed)

        files = 0
        lines = 0
        byte_count = 0
        if source.exists():
            for path in source.rglob("*"):
                if not path.is_file() or not is_proof_file(kind, source, path):
                    continue
                files += 1
                lines += line_count(path)
                byte_count += path.stat().st_size
        bucket["sources_with_proof_files"] += int(files > 0)
        bucket["proof_files"] += files
        bucket["proof_source_lines"] += lines
        bucket["proof_source_bytes"] += byte_count

    ecosystems = []
    for kind in ORDER:
        bucket = stats[kind]
        ecosystems.append({"kind": kind, "label": LABELS[kind], **bucket})

    totals = {
        key: sum(bucket[key] for bucket in stats.values())
        for key in (
            "sources",
            "searchable_sources",
            "sources_with_proof_files",
            "proof_files",
            "proof_source_lines",
            "proof_source_bytes",
        )
    }
    totals["proof_assistants"] = len(stats)

    registered_names = {directory.name for _, directory in rows}
    payload = {
        "summary": totals,
        "ecosystems": ecosystems,
        "unsearchable_sources": sorted(registered_names - indexed),
        "definitions": {
            "proof_file": (
                "A source file written in the language of its proof assistant; ACL2 .sys generated rune reports "
                "and PVS .prf proof traces are excluded."
            ),
            "proof_source_lines": "Physical newline-delimited lines in those proof source files.",
            "declaration_counts": (
                "Not reported until comparable declaration counts can be obtained from each proof assistant using its own parser or elaborator."
            ),
        },
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        f"{OUT}: {totals['searchable_sources']}/{totals['sources']} searchable sources, "
        f"{totals['proof_files']} proof files, {totals['proof_source_lines']} lines of proof source"
    )


if __name__ == "__main__":
    main()
