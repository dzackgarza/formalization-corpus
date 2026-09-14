#!/usr/bin/env python3
"""Measure FD-002 terminology that is absent from the primary document view.

This is a lexical discoverability audit, not a semantic non-existence claim.
It selects a deterministic sample of rare readable terms from non-formal
README/source-documentation files, then performs one fixed-string ripgrep scan
over the primary hard-link view to determine which sampled terms occur there.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import re
import subprocess
import tempfile

from filtering_lib import CURRENT, ROOT, load_jsonl, sha256_file, sources


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{9,}")
SKIP_PREFIXES = (
    "http",
    "github",
    "copyright",
    "installation",
    "documentation",
    "description",
    "repository",
    "formalization",
    "formalisation",
)


def corpus_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def readable_candidate(token: str) -> bool:
    if len(token) > 40 or token.isupper():
        return False
    if token.casefold().startswith(SKIP_PREFIXES):
        return False
    if sum(char.isdigit() for char in token) > len(token) // 3:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=3000)
    parser.add_argument(
        "--primary", type=pathlib.Path, default=ROOT / ".index-primary"
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=ROOT / "filtering" / "audits" / "readme-searchability-20260914.json",
    )
    args = parser.parse_args()

    if args.sample_size <= 0:
        raise SystemExit("--sample-size must be positive")
    if not args.primary.is_dir():
        raise SystemExit(f"missing primary view: {args.primary}")

    source_roots = {source.repository: source.root for source in sources()}
    rows = [row for row in load_jsonl(CURRENT) if row.get("decision_id") == "FD-002"]
    document_frequency: collections.Counter[str] = collections.Counter()
    first_occurrence: dict[str, tuple[str, str]] = {}

    for row in rows:
        path = source_roots[row["repository"]] / row["file"]
        text = path.read_text(errors="ignore")
        for token in set(TOKEN_RE.findall(text)):
            if not readable_candidate(token):
                continue
            document_frequency[token] += 1
            first_occurrence.setdefault(token, (row["repository"], row["file"]))

    singleton_terms = sorted(
        (token for token, count in document_frequency.items() if count == 1),
        key=lambda token: (-len(token), token.casefold()),
    )
    sampled = singleton_terms[: args.sample_size]

    with tempfile.TemporaryDirectory(prefix="readme-searchability-") as directory:
        patterns = pathlib.Path(directory) / "patterns.txt"
        patterns.write_text("\n".join(sampled) + "\n")
        result = subprocess.run(
            [
                "rg",
                "-I",
                "-o",
                "--no-filename",
                "-F",
                "-f",
                str(patterns),
                str(args.primary),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise SystemExit(result.stderr.strip() or f"ripgrep exited {result.returncode}")
        primary_matches = set(result.stdout.splitlines())

    absent = [token for token in sampled if token not in primary_matches]
    examples = [
        {
            "term": token,
            "repository": first_occurrence[token][0],
            "file": first_occurrence[token][1],
        }
        for token in absent[:100]
    ]
    payload = {
        "schema_version": 1,
        "audit": "fd002-readme-primary-searchability-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "corpus_git_commit": corpus_commit(),
        "filter_state_sha256": sha256_file(CURRENT),
        "counts": {
            "fd002_documents": len(rows),
            "rare_readable_singleton_terms": len(singleton_terms),
            "sampled_terms": len(sampled),
            "sampled_terms_present_in_primary_text": len(sampled) - len(absent),
            "sampled_terms_absent_from_primary_text": len(absent),
        },
        "method": {
            "claim_scope": (
                "lexical searchability only; absence from primary text does not assert "
                "semantic nonexistence"
            ),
            "token_regex": TOKEN_RE.pattern,
            "candidate_rule": (
                "terms appearing in exactly one FD-002 document; skip selected generic "
                "web/documentation prefixes, tokens longer than 40 characters, all-uppercase "
                "tokens, and tokens with more than one third digits"
            ),
            "sample_order": "(-length, casefolded token, token), first N",
            "primary_scan": "ripgrep -I -o --no-filename -F -f over .index-primary",
        },
        "examples_absent_from_primary_text": examples,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(args.output)
    print(json.dumps(payload["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
