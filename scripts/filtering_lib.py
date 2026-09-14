#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import pathlib
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Iterable

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_TABLE = ROOT / "sources.tsv"
FILTER_ROOT = ROOT / "filtering"
CATALOG = FILTER_ROOT / "decision-catalog.json"
CURRENT = FILTER_ROOT / "current.jsonl"
LEDGER = FILTER_ROOT / "ledger.jsonl"
DUPLICATES = FILTER_ROOT / "duplicate-aliases.json"
SNAPSHOT = FILTER_ROOT / "snapshot.json"

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
    "pvs": (".pvs", ".prf"),
    "twelf": (".elf",),
}

SKIP_DIRS = {".git", ".lake", ".venv", "node_modules"}
DECL_RE = re.compile(
    rb"(?m)^\s*(?:private\s+|protected\s+|noncomputable\s+|unsafe\s+|partial\s+)*"
    rb"(?:theorem|lemma|def|abbrev|structure|class|instance|inductive|coinductive|axiom|example)\b"
)
IMPORT_LINE_RE = re.compile(rb"(?m)^\s*(?:public\s+)?import\s+")


@dataclass(frozen=True)
class Source:
    url: str
    directory: pathlib.Path
    proof_assistant: str
    transport: str
    sync_group: str
    discovered_via: str

    @property
    def repository(self) -> str:
        return self.directory.name

    @property
    def root(self) -> pathlib.Path:
        return ROOT / self.directory


def sources() -> list[Source]:
    out: list[Source] = []
    with SOURCE_TABLE.open(newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            out.append(
                Source(
                    url=row["url"],
                    directory=pathlib.Path(row["directory"]),
                    proof_assistant=row["proof_assistant"],
                    transport=row["transport"],
                    sync_group=row["sync_group"],
                    discovered_via=row["discovered_via"],
                )
            )
    return out


def source_revision(source: Source) -> str | None:
    if source.transport == "web-dir":
        return None
    try:
        return subprocess.check_output(
            ["git", "-C", str(source.root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def is_formal_file(kind: str, path: pathlib.Path) -> bool:
    return any(path.name.endswith(suffix) for suffix in FORMAL_SUFFIXES[kind])


def is_readme(path: pathlib.Path) -> bool:
    return path.name.casefold().startswith("readme")


def is_nonformal_readme(kind: str, path: pathlib.Path) -> bool:
    """Return true only for README-like files outside the prover source language.

    A formal-source file such as ``README.lean``, ``README.thy``, or
    ``README.agda`` can contain declarations, theorem statements, examples, or
    proofs.  Its basename is therefore not an exclusion signal.
    """
    return is_readme(path) and not is_formal_file(kind, path)


def is_lean_build_metadata(path: pathlib.Path) -> bool:
    low = path.name.casefold()
    # Keep formal Lean source such as lakefile.lean in the primary corpus.  Lake
    # files are ordinary Lean programs and may contain definitions, structures,
    # examples, axioms, or other reusable formal content.  Only the non-formal
    # package metadata formats are safe filename-level exclusions.
    return low in {"lean-toolchain", "lake-manifest.json", "lakefile.toml"}


def iter_files(source: Source) -> Iterable[pathlib.Path]:
    if not source.root.exists():
        return
    for directory, dirs, files in os.walk(source.root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        base = pathlib.Path(directory)
        for name in files:
            path = base / name
            if path.is_file():
                yield path


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_catalog() -> dict[str, dict[str, Any]]:
    data = json.loads(CATALOG.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("unsupported filtering decision catalog")
    decisions = data.get("decisions") or []
    by_id = {item["decision_id"]: item for item in decisions}
    if len(by_id) != len(decisions):
        raise ValueError("duplicate filtering decision id")
    return by_id


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def dump_jsonl(path: pathlib.Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def strip_lean_comments(raw: bytes) -> bytes:
    """Remove nested Lean comments for import-only candidate discovery.

    This is only a cheap prefilter.  The final decision is made by tree-sitter.
    """
    out = bytearray()
    i = 0
    block_depth = 0
    line_comment = False
    n = len(raw)
    while i < n:
        if line_comment:
            if raw[i] == 10:
                out.append(10)
                line_comment = False
            i += 1
            continue
        if block_depth:
            if i + 1 < n and raw[i : i + 2] == b"/-":
                block_depth += 1
                i += 2
                continue
            if i + 1 < n and raw[i : i + 2] == b"-/":
                block_depth -= 1
                i += 2
                continue
            if raw[i] == 10:
                out.append(10)
            i += 1
            continue
        if i + 1 < n and raw[i : i + 2] == b"--":
            line_comment = True
            i += 2
            continue
        if i + 1 < n and raw[i : i + 2] == b"/-":
            block_depth = 1
            i += 2
            continue
        out.append(raw[i])
        i += 1
    return bytes(out)


def lean_import_only_candidate(raw: bytes) -> bool:
    if not IMPORT_LINE_RE.search(raw) or DECL_RE.search(raw):
        return False
    stripped = strip_lean_comments(raw)
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    return bool(lines) and all(
        re.match(rb"^(?:public\s+)?import\b", line) is not None for line in lines
    )


def verify_lean_import_only(paths: list[pathlib.Path]) -> tuple[set[pathlib.Path], dict[str, Any]]:
    """Tree-sitter verify candidate files contain only imports/comments."""
    if not paths:
        return set(), {"parser": "tree-sitter-lean", "candidates": 0, "rejected": 0}
    parser = ROOT / ".ast-grep" / "lean.so"
    if not parser.is_file():
        raise FileNotFoundError(f"Lean parser is unavailable: {parser}")
    with tempfile.TemporaryDirectory() as directory:
        tmp = pathlib.Path(directory)
        paths_file = tmp / "paths.txt"
        paths_file.write_text("".join(str(path) + "\n" for path in paths))
        query_file = tmp / "nonimport.scm"
        query_file.write_text(
            '((module (_) @top)\n'
            ' (#not-match? @top "^(public[[:space:]]+)?import\\\\b|^--|^/-"))\n'
            '(ERROR) @error\n'
        )
        proc = subprocess.run(
            [
                "tree-sitter", "query", "-l", str(parser), "--lang-name", "lean",
                "--paths", str(paths_file), str(query_file),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "tree-sitter import-only verification failed")
        rejected: set[pathlib.Path] = set()
        current: pathlib.Path | None = None
        for line in proc.stdout.splitlines():
            if line and not line.startswith(" "):
                current = pathlib.Path(line)
            elif current is not None and line.lstrip().startswith("pattern:"):
                rejected.add(current)
        accepted = set(paths) - rejected
        return accepted, {
            "parser": "tree-sitter-lean",
            "parser_sha256": sha256_file(parser),
            "candidates": len(paths),
            "rejected": len(rejected),
            "accepted": len(accepted),
        }
