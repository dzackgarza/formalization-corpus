#!/usr/bin/env python3
"""Validate stable contributor policy identifiers and filtering references."""

from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
FILTERING = ROOT / "docs" / "CORPUS-FILTERING.md"

DEFINITION_RE = re.compile(r"^###\s+(FILTER-\d{3})\b", re.MULTILINE)
REFERENCE_RE = re.compile(r"\bFILTER-\d{3}\b")


def main() -> int:
    contributing = CONTRIBUTING.read_text()
    definitions = DEFINITION_RE.findall(contributing)
    errors: list[str] = []

    if not definitions:
        errors.append("CONTRIBUTING.md defines no FILTER-### policies")

    seen: set[str] = set()
    for code in definitions:
        if code in seen:
            errors.append(f"duplicate filtering policy definition: {code}")
        seen.add(code)

    filtering = FILTERING.read_text()
    for code in sorted(set(REFERENCE_RE.findall(filtering))):
        if code not in seen:
            errors.append(f"docs/CORPUS-FILTERING.md references undefined policy: {code}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"filtering policies ok: {len(definitions)} stable FILTER-### definitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
