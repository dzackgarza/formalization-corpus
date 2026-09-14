#!/usr/bin/env python3
"""Measure corpus/file-role quality before retrieval tuning.

This is deliberately a diagnostic, not an exclusion policy.  Path/content
heuristics identify classes worth reviewing (aggregators, generated files,
roadmaps, tests, etc.); they do not declare those files irrelevant.  The report
also measures how often those roles occur in the deployed baseline's top ten and
performs a bounded post-hoc filtering simulation over the report's top-20 window.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

import evaluate
from provenance import repository_state

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_REPORT = ROOT / "evaluation/search/baselines/frontend_lexical_v2.json"
DEFAULT_GOLD = ROOT / "evaluation/search/gold.json"

FORMAL_SUFFIXES = {
    ".lean", ".v", ".agda", ".thy", ".ml", ".hl", ".sml", ".sig",
    ".miz", ".mm", ".mm0", ".mm1", ".lisp", ".lsp", ".acl2", ".pvs", ".elf",
}

DECL_RE = re.compile(
    r"(?m)^\s*(?:private\s+|protected\s+|noncomputable\s+|unsafe\s+|partial\s+)*"
    r"(?:theorem|lemma|def|abbrev|structure|class|instance|inductive|coinductive|axiom|example)\b"
)
IMPORT_RE = re.compile(r"(?m)^\s*(?:public\s+)?import\s+")
SORRY_RE = re.compile(r"\b(?:sorry|admit)\b")

TEST_SEGMENTS = {
    "test", "tests", "testdata", "fixture", "fixtures", "bench", "benchmark", "benchmarks",
}


def source_rows() -> dict[str, dict[str, str]]:
    with (ROOT / "sources.tsv").open(newline="") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        return {pathlib.PurePosixPath(row["directory"]).name: row for row in rows}


def is_formal_file(path: pathlib.Path) -> bool:
    name = path.name.lower()
    return path.suffix.lower() in FORMAL_SUFFIXES or name.endswith(
        (".lagda.md", ".lagda.rst", ".lagda.tex")
    )


def path_roles(file_name: str) -> set[str]:
    low = file_name.casefold()
    parts = [part.casefold() for part in pathlib.PurePosixPath(file_name).parts]
    base = parts[-1] if parts else low
    roles: set[str] = set()
    if "generated" in parts or "challengedeps" in base or "workspacetest" in base:
        roles.add("generated-path")
    if any("roadmap" in part for part in parts) or base in {"suggested.lean", "roadmap.lean"}:
        roles.add("roadmap-suggested")
    if any("audit" in part for part in parts):
        roles.add("audit-path")
    if any(part in {"vendor", "vendored"} for part in parts):
        roles.add("vendored-path")
    if any(
        part in TEST_SEGMENTS
        or part.startswith("test")
        or part.endswith("tests")
        or part == ".sofi-test-folders"
        for part in parts[:-1]
    ):
        roles.add("test-fixture-path")
    if base == "lakefile.lean":
        roles.add("build-config")
    return roles


def lean_content_roles(path: pathlib.Path) -> tuple[set[str], dict[str, int]]:
    text = path.read_text(errors="replace")
    declarations = len(DECL_RE.findall(text))
    imports = len(IMPORT_RE.findall(text))
    sorry_admit = len(SORRY_RE.findall(text))
    roles: set[str] = set()
    nonblank = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("--")
    ]
    importish = sum(
        1 for line in nonblank if line.startswith("import ") or line.startswith("public import ")
    )
    if imports and declarations == 0 and nonblank and importish / len(nonblank) >= 0.9:
        roles.add("import-aggregator")
    if declarations == 0:
        roles.add("no-declaration-regex")
    if sorry_admit:
        # Diagnostic only: theorem statements and useful owner files can contain sorry.
        roles.add("contains-sorry-admit")
    return roles, {
        "declarations_regex": declarations,
        "imports": imports,
        "sorry_admit_tokens": sorry_admit,
    }


def zoekt_file_count(pattern: str) -> int | None:
    zoekt = ROOT / "bin" / "zoekt"
    index = ROOT / ".zoekt"
    if not zoekt.is_file() or not index.is_dir():
        return None
    proc = subprocess.run(
        [str(zoekt), "-index_dir", str(index), "-l", f"file:{pattern}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return len([line for line in proc.stdout.splitlines() if line.strip()])


def qrel_map(gold: dict[str, Any]) -> dict[str, dict[tuple[str, str], int]]:
    return {
        case["id"]: {
            (judgment["repository"], judgment["file"]): judgment["relevance"]
            for judgment in case["judgments"]
        }
        for case in gold["cases"]
    }


def role_for_result(
    repository: str,
    file_name: str,
    rows: dict[str, dict[str, str]],
    lean_cache: dict[tuple[str, str], set[str]],
) -> set[str]:
    roles = path_roles(file_name)
    row = rows.get(repository)
    if not row or row["proof_assistant"] != "lean" or not file_name.endswith(".lean"):
        return roles
    key = (repository, file_name)
    if key not in lean_cache:
        path = ROOT / row["directory"] / file_name
        if path.is_file():
            lean_cache[key] = lean_content_roles(path)[0]
        else:
            lean_cache[key] = set()
    return roles | lean_cache[key]


def posthoc_filter_metrics(
    report: dict[str, Any],
    qrels: dict[str, dict[tuple[str, str], int]],
    rows: dict[str, dict[str, str]],
    banned: set[str],
) -> dict[str, Any]:
    lean_cache: dict[tuple[str, str], set[str]] = {}
    hit: list[int] = []
    owner_hit: list[int] = []
    reciprocal: list[float] = []
    owner_reciprocal: list[float] = []
    incomplete = 0
    changed: list[dict[str, Any]] = []
    for case in report["cases"]:
        original = case["top_results"][:10]
        filtered = [
            item
            for item in case["top_results"][:20]
            if not (
                role_for_result(item["repository"], item["file"], rows, lean_cache) & banned
            )
        ][:10]
        if len(filtered) < 10 and case.get("result_count", 0) >= 10:
            # We only have the frozen report's first 20 results, so this simulation
            # may be unable to refill all ten slots after aggressive filtering.
            incomplete += 1
        rels = [
            qrels[case["id"]].get((item["repository"], item["file"]), 0)
            for item in filtered
        ]
        first = next((rank for rank, rel in enumerate(rels, 1) if rel > 0), None)
        first_owner = next((rank for rank, rel in enumerate(rels, 1) if rel == 3), None)
        hit.append(int(first is not None))
        owner_hit.append(int(first_owner is not None))
        reciprocal.append(1 / first if first else 0.0)
        owner_reciprocal.append(1 / first_owner if first_owner else 0.0)

        original_rels = [
            qrels[case["id"]].get((item["repository"], item["file"]), 0)
            for item in original
        ]
        original_state = {
            "hit": int(any(rel > 0 for rel in original_rels)),
            "owner_hit": int(any(rel == 3 for rel in original_rels)),
            "first_relevant": next(
                (rank for rank, rel in enumerate(original_rels, 1) if rel > 0), None
            ),
            "first_owner": next(
                (rank for rank, rel in enumerate(original_rels, 1) if rel == 3), None
            ),
        }
        filtered_state = {
            "hit": hit[-1],
            "owner_hit": owner_hit[-1],
            "first_relevant": first,
            "first_owner": first_owner,
        }
        if filtered_state != original_state:
            changed.append(
                {
                    "id": case["id"],
                    "before": original_state,
                    "after": filtered_state,
                }
            )
    return {
        "banned_roles": sorted(banned),
        "window": 20,
        "hit@10": statistics.fmean(hit),
        "owner_hit@10": statistics.fmean(owner_hit),
        "mrr": statistics.fmean(reciprocal),
        "owner_mrr": statistics.fmean(owner_reciprocal),
        "queries_with_incomplete_refill": incomplete,
        "changed_queries": changed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=pathlib.Path, default=DEFAULT_REPORT)
    parser.add_argument("--gold", type=pathlib.Path, default=DEFAULT_GOLD)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()

    rows = source_rows()
    gold = json.loads(args.gold.read_text())
    baseline = json.loads(args.baseline.read_text())
    qrels = qrel_map(gold)

    formal_total = 0
    formal_bytes = 0
    nonformal_total = 0
    nonformal_bytes = 0
    by_assistant: Counter[str] = Counter()
    nonformal_kinds: Counter[str] = Counter()
    path_role_counts: Counter[str] = Counter()
    lean_role_counts: Counter[str] = Counter()
    lean_files = 0
    lean_bytes = 0
    hashes: dict[bytes, list[tuple[str, str]]] = defaultdict(list)

    for repository, row in rows.items():
        base = ROOT / row["directory"]
        if not base.exists():
            continue
        for directory, dirs, files in os.walk(base):
            dirs[:] = [
                name for name in dirs if name not in {".git", ".lake", ".venv", "node_modules"}
            ]
            for name in files:
                path = pathlib.Path(directory) / name
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                rel = path.relative_to(base).as_posix()
                if not is_formal_file(path):
                    nonformal_total += 1
                    nonformal_bytes += size
                    low = name.casefold()
                    if low.startswith("readme"):
                        nonformal_kinds["README*"] += 1
                    elif low == "lake-manifest.json":
                        nonformal_kinds["lake-manifest.json"] += 1
                    elif low.startswith("lakefile"):
                        nonformal_kinds["lakefile.*"] += 1
                    elif low == "lean-toolchain":
                        nonformal_kinds["lean-toolchain"] += 1
                    elif path.suffix.casefold() == ".prf":
                        nonformal_kinds["PVS .prf"] += 1
                    else:
                        nonformal_kinds["other"] += 1
                    continue

                formal_total += 1
                formal_bytes += size
                by_assistant[row["proof_assistant"]] += 1
                for role in path_roles(rel):
                    path_role_counts[role] += 1

                if row["proof_assistant"] == "lean" and path.suffix == ".lean":
                    lean_files += 1
                    lean_bytes += size
                    try:
                        raw = path.read_bytes()
                    except OSError:
                        continue
                    content_roles, _ = lean_content_roles(path)
                    for role in content_roles:
                        lean_role_counts[role] += 1
                    hashes[hashlib.sha256(raw).digest()].append((repository, rel))

    duplicate_groups = [members for members in hashes.values() if len(members) > 1]
    cross_source_groups = [
        members for members in duplicate_groups if len({repo for repo, _ in members}) > 1
    ]

    top10_role_state: dict[str, Counter[str]] = defaultdict(Counter)
    top10_role_queries: dict[str, set[str]] = defaultdict(set)
    lean_cache: dict[tuple[str, str], set[str]] = {}
    for case in baseline["cases"]:
        judgments = qrels[case["id"]]
        for item in case["top_results"][:10]:
            key = (item["repository"], item["file"])
            state = "unjudged" if key not in judgments else f"relevance-{judgments[key]}"
            for role in role_for_result(*key, rows, lean_cache):
                top10_role_state[role][state] += 1
                top10_role_queries[role].add(case["id"])

    filters = {
        "no-import-aggregators": {"import-aggregator"},
        "no-aggregators-or-roadmaps": {"import-aggregator", "roadmap-suggested"},
        "no-obvious-nontarget-roles": {
            "import-aggregator", "roadmap-suggested", "generated-path", "audit-path", "test-fixture-path"
        },
    }

    metrics = {
        "formal_source_files": formal_total,
        "formal_source_bytes": formal_bytes,
        "nonformal_materialized_files": nonformal_total,
        "nonformal_materialized_bytes": nonformal_bytes,
        "lean_files": lean_files,
        "lean_bytes": lean_bytes,
        "lean_import_aggregators": lean_role_counts["import-aggregator"],
        "lean_import_aggregator_rate": lean_role_counts["import-aggregator"] / lean_files,
        "lean_contains_sorry_admit": lean_role_counts["contains-sorry-admit"],
        "lean_contains_sorry_admit_rate": lean_role_counts["contains-sorry-admit"] / lean_files,
        "lean_exact_duplicate_files": sum(len(group) for group in duplicate_groups),
        "lean_exact_duplicate_file_rate": sum(len(group) for group in duplicate_groups) / lean_files,
        "lean_cross_source_duplicate_files": sum(len(group) for group in cross_source_groups),
        "lean_cross_source_duplicate_file_rate": sum(len(group) for group in cross_source_groups) / lean_files,
        "top10_import_aggregator_slots": sum(top10_role_state["import-aggregator"].values()),
        "top10_roadmap_suggested_slots": sum(top10_role_state["roadmap-suggested"].values()),
        "top10_vendored_slots": sum(top10_role_state["vendored-path"].values()),
    }

    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "repository_state": repository_state(ROOT),
        "variant": "corpus_file_quality_v1",
        "provider": "filesystem+frozen-ranking",
        "gold_sha256": hashlib.sha256(args.gold.read_bytes()).hexdigest(),
        "query_config_sha256": baseline.get("query_config_sha256"),
        "index": baseline.get("index"),
        "retrieval_engine": baseline.get("retrieval_engine"),
        "baseline_report": str(args.baseline.relative_to(ROOT)),
        "baseline_artifact_sha256": hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        "metrics": metrics,
        "formal_files_by_proof_assistant": dict(sorted(by_assistant.items())),
        "nonformal_materialized_kinds": dict(nonformal_kinds.most_common()),
        "path_role_counts": dict(path_role_counts.most_common()),
        "lean_content_role_counts": dict(lean_role_counts.most_common()),
        "duplicates": {
            "exact_groups": len(duplicate_groups),
            "cross_source_groups": len(cross_source_groups),
            "largest_cross_source_groups": [
                {"size": len(group), "examples": group[:12]}
                for group in sorted(cross_source_groups, key=len, reverse=True)[:20]
            ],
        },
        "zoekt_indexed_metadata_file_counts": {
            "README*": zoekt_file_count(r"(^|/)README"),
            "lakefile*": zoekt_file_count(r"(^|/)lakefile"),
            "lean-toolchain": zoekt_file_count(r"lean-toolchain$"),
            "PVS .prf": zoekt_file_count(r"\.prf$"),
        },
        "top10_role_judgment_state": {
            role: {
                "slots": sum(states.values()),
                "queries": len(top10_role_queries[role]),
                "states": dict(states),
            }
            for role, states in sorted(top10_role_state.items())
        },
        "posthoc_filter_simulations": {
            name: posthoc_filter_metrics(baseline, qrels, rows, banned)
            for name, banned in filters.items()
        },
        "heuristic_policy": {
            "warning": "Role labels are diagnostics, not relevance judgments or automatic exclusion rules.",
            "contains_sorry_admit": "Diagnostic only; never used by the post-hoc exclusion simulations.",
            "import_aggregator": "Lean file with >=1 import, zero declaration-regex matches, and >=90% of non-comment nonblank lines import/public import lines.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(metrics, indent=2, sort_keys=True))
    for name, result in report["posthoc_filter_simulations"].items():
        print(
            f"{name}: owner_hit@10={result['owner_hit@10']:.3f} "
            f"hit@10={result['hit@10']:.3f} mrr={result['mrr']:.3f} "
            f"incomplete_refill={result['queries_with_incomplete_refill']}"
        )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
