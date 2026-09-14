#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
from collections import Counter

from filtering_lib import CURRENT, ROOT, is_formal_file, iter_files, load_jsonl, source_revision, sources


TOP_LEVEL_SYMBOL = re.compile(rb"(?m)^\(([^()\s]+)")
LISP_TOKEN = re.compile(rb"[^()\s]+")
SOURCE_SUFFIXES = (".lisp", ".lsp", ".acl2")


def corresponding_book(source_root: pathlib.Path, report: pathlib.Path) -> pathlib.Path | None:
    rel = report.relative_to(source_root)
    parts = list(rel.parts)
    try:
        sys_index = parts.index(".sys")
    except ValueError:
        return None
    suffix = "@useless-runes.lsp"
    if not rel.name.casefold().endswith(suffix):
        return None
    base = rel.name[: -len(suffix)]
    parent = pathlib.Path(*parts[:sys_index])
    for extension in SOURCE_SUFFIXES:
        candidate = source_root / parent / f"{base}{extension}"
        if candidate.is_file():
            return candidate
    return None


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--examples", type=int, default=100)
    args = parser.parse_args()

    acl2_sources = [source for source in sources() if source.proof_assistant == "acl2"]
    if len(acl2_sources) != 1:
        raise SystemExit(f"expected one ACL2 source, found {len(acl2_sources)}")
    source = acl2_sources[0]

    decisions = load_jsonl(CURRENT)
    report_rows = [
        row
        for row in decisions
        if row["repository"] == source.repository and row["decision_id"] == "FD-017"
    ]
    if not report_rows:
        raise SystemExit("no active FD-017 ACL2 proof-metadata decisions")

    report_symbols: Counter[bytes] = Counter()
    initially_missing: Counter[bytes] = Counter()
    report_files: list[pathlib.Path] = []
    reports_with_corresponding_book = 0
    reports_without_corresponding_book = 0
    for row in report_rows:
        path = source.root / row["file"]
        report_files.append(path)
        symbols = [symbol.upper() for symbol in TOP_LEVEL_SYMBOL.findall(path.read_bytes())]
        for symbol in symbols:
            report_symbols[symbol] += 1

        book = corresponding_book(source.root, path)
        if book is None:
            reports_without_corresponding_book += 1
            continue
        reports_with_corresponding_book += 1
        book_bytes = book.read_bytes().upper()
        for symbol in symbols:
            if symbol not in book_bytes:
                initially_missing[symbol] += 1

    ordinary_files: list[pathlib.Path] = []
    remaining = set(initially_missing)
    for path in iter_files(source):
        if not is_formal_file("acl2", path) or ".sys" in path.parts:
            continue
        ordinary_files.append(path)
        raw = path.read_bytes().upper()
        present: set[bytes] = set()
        for token in LISP_TOKEN.findall(raw):
            # Match the original audit: remove common Lisp reader prefixes but
            # otherwise retain punctuation as part of the symbol token.
            token = token.lstrip(b"'`,")
            if token in remaining:
                present.add(token)
        remaining.difference_update(present)

    report_symbol_set = set(report_symbols)
    absent = sorted(remaining)
    present_elsewhere = set(initially_missing) - remaining

    corpus_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    result = {
        "schema_version": 1,
        "audit": "acl2-useless-runes-searchability-v1",
        "corpus_git_commit": corpus_commit,
        "repository": source.repository,
        "source_revision": source_revision(source),
        "filter_state_sha256": sha256_file(CURRENT),
        "method": {
            "report_symbol_extraction": "uppercased first non-parenthesis/non-whitespace token of each top-level list beginning in column 1",
            "corresponding_book_test": "retain only report symbols absent as raw byte substrings from the corresponding .lisp/.lsp/.acl2 source book",
            "ordinary_source_scope": "all ACL2 formal-source files outside .sys",
            "ordinary_token_extraction": "uppercased non-parenthesis/non-whitespace Lisp tokens with leading quote/backquote/comma reader prefixes stripped",
            "claim_scope": "lexical searchability only; absence does not assert semantic nonexistence or absence after macro expansion",
        },
        "counts": {
            "fd017_report_files": len(report_files),
            "reports_with_corresponding_book": reports_with_corresponding_book,
            "reports_without_corresponding_book": reports_without_corresponding_book,
            "ordinary_acl2_formal_files": len(ordinary_files),
            "report_top_level_symbol_occurrences": sum(report_symbols.values()),
            "distinct_report_top_level_symbols": len(report_symbol_set),
            "report_symbol_occurrences_absent_from_corresponding_book": sum(initially_missing.values()),
            "distinct_report_symbols_absent_from_corresponding_book": len(initially_missing),
            "distinct_initially_missing_symbols_found_in_other_ordinary_source": len(present_elsewhere),
            "distinct_report_symbols_absent_from_all_ordinary_source_tokens": len(absent),
        },
        "examples_absent_from_ordinary_source_tokens": [
            symbol.decode("utf-8", errors="backslashreplace") for symbol in absent[: args.examples]
        ],
    }

    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
        print(args.output)
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
