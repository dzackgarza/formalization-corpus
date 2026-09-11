#!/usr/bin/env python3
"""Count theorems and definitions per repository.

Run wherever the checkouts are — the same place `just index` runs — and commit
the result; the Pages build merges it. Lines of code measure typing. A count of
theorems and definitions measures how much mathematics a library states, which
is the number a reader is actually asking about.

Counting is syntactic: a declaration keyword at the start of a line, modulo the
modifiers Lean and Rocq allow in front of one. It will not match a declaration
written inside a term or produced by a macro, so treat every figure as a floor.
"""

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "declarations.tsv"

MODIFIERS = r"(?:@\[[^\]]*\]\s*)?(?:private |protected |noncomputable |public |nonrec |partial |unsafe |scoped |local )*"

# Agda has no declaration keyword — a definition is a name, a colon and a type —
# so there is nothing to count syntactically, and its rows stay empty rather
# than carrying a number that would mean something else.
LANGS = {
    ".lean": {
        "theorems": rf"^{MODIFIERS}(?:theorem|lemma)\s",
        "definitions": rf"^{MODIFIERS}(?:def|abbrev|instance|structure|class|inductive)\s",
    },
    ".v": {
        "theorems": r"^\s*(?:Theorem|Lemma|Corollary|Proposition|Remark|Fact)\s",
        "definitions": r"^\s*(?:Definition|Fixpoint|CoFixpoint|Inductive|CoInductive|Record|Structure|Class|Instance)\s",
    },
}


def manifest(name: str) -> list[tuple[str, str]]:
    return [
        (line.split("\t")[0].rstrip("/"), line.split("\t")[1])
        for line in (ROOT / name).read_text().splitlines()
        if line.strip()
    ]


def count(directory: pathlib.Path, suffix: str, pattern: str) -> int:
    """Total matching lines under a checkout, via ripgrep."""
    got = subprocess.run(
        ["rg", "--no-messages", "--count-matches", "--glob", f"*{suffix}", pattern, str(directory)],
        capture_output=True, text=True,
    )
    return sum(int(line.rsplit(":", 1)[1]) for line in got.stdout.splitlines() if ":" in line)


def main() -> None:
    rows = []
    for name in ("repos.tsv", "reservoir.tsv", "port-sources.tsv"):
        for _, directory in manifest(name):
            path = ROOT / directory
            if not path.is_dir():
                continue
            theorems = definitions = 0
            for suffix, patterns in LANGS.items():
                theorems += count(path, suffix, patterns["theorems"])
                definitions += count(path, suffix, patterns["definitions"])
            if theorems or definitions:
                rows.append((pathlib.PurePosixPath(directory).name, theorems, definitions))

    rows.sort(key=lambda r: r[0].lower())
    with OUT.open("w") as fh:
        for name, theorems, definitions in rows:
            fh.write(f"{name}\t{theorems}\t{definitions}\n")

    print(f"{OUT}: {len(rows)} repositories, "
          f"{sum(r[1] for r in rows):,} theorems, {sum(r[2] for r in rows):,} definitions")


if __name__ == "__main__":
    main()
