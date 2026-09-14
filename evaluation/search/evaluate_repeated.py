#!/usr/bin/env python3
"""Aggregate repeated stochastic retrieval runs.

Each input is a normal evaluation report over the same query set, qrels, index,
and retrieval configuration.  Rank cutoff K and stochastic trial count R are
kept separate throughout:

* Success@K / Owner-Success@K describe one ranked run.
* Pass@R[Success@K] estimates whether at least one of R independent runs
  succeeds for the same information need.

The pass estimator is the standard unbiased finite-sample estimator used for
pass@k evaluation: 1 - C(n-c, R) / C(n, R), where n is the number of sampled
runs and c is the number that satisfy the success predicate.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import random
import statistics
from typing import Any

import evaluate


def pass_at_r(n: int, c: int, r: int) -> float:
    if n < 1:
        raise ValueError("n must be positive")
    if not 0 <= c <= n:
        raise ValueError("c must satisfy 0 <= c <= n")
    if not 1 <= r <= n:
        raise ValueError("r must satisfy 1 <= r <= n")
    if n - c < r:
        return 1.0
    return 1.0 - math.comb(n - c, r) / math.comb(n, r)


def bootstrap_mean(
    values: list[float], *, samples: int = 10_000, seed: int = 0
) -> dict[str, Any]:
    if not values:
        raise ValueError("cannot bootstrap an empty sample")
    mean = statistics.fmean(values)
    if len(values) == 1 or samples == 0:
        return {"mean": mean, "ci95": [mean, mean]}
    rng = random.Random(seed)
    n = len(values)
    boot = [
        statistics.fmean(values[rng.randrange(n)] for _ in range(n))
        for _ in range(samples)
    ]
    return {
        "mean": mean,
        "ci95": [evaluate.percentile(boot, 0.025), evaluate.percentile(boot, 0.975)],
    }


def validate_reports(reports: list[dict[str, Any]]) -> None:
    if not reports:
        raise ValueError("at least one report is required")
    first = reports[0]
    keys = ("gold_sha256", "query_config_sha256", "index", "variant")
    first_cases = [(case["id"], case["query"]) for case in first["cases"]]
    for number, report in enumerate(reports[1:], start=2):
        for key in keys:
            if report.get(key) != first.get(key):
                raise ValueError(f"run {number}: {key} differs from run 1")
        cases = [(case["id"], case["query"]) for case in report["cases"]]
        if cases != first_cases:
            raise ValueError(f"run {number}: query/case order differs from run 1")


def aggregate_repeated(
    reports: list[dict[str, Any]],
    *,
    rank_cutoff: int = 10,
    pass_r: tuple[int, ...] = (1, 2, 5, 10),
    bootstrap_samples: int = 10_000,
    bootstrap_seed: int = 0,
) -> dict[str, Any]:
    validate_reports(reports)
    n_runs = len(reports)
    if str(rank_cutoff) not in reports[0]["cases"][0]["per_k"]:
        raise ValueError(f"rank cutoff {rank_cutoff} is not present in the input reports")
    rs = tuple(sorted(set(r for r in pass_r if 1 <= r <= n_runs)))

    query_rows: list[dict[str, Any]] = []
    for case_index, base_case in enumerate(reports[0]["cases"]):
        cases = [report["cases"][case_index] for report in reports]
        relevant_successes = sum(case["per_k"][str(rank_cutoff)]["hit"] for case in cases)
        owner_successes = sum(case["per_k"][str(rank_cutoff)]["owner_hit"] for case in cases)
        row = {
            "id": base_case["id"],
            "query": base_case["query"],
            "runs": n_runs,
            "relevant_successes": relevant_successes,
            "owner_successes": owner_successes,
            "single_run_success_probability": relevant_successes / n_runs,
            "single_run_owner_success_probability": owner_successes / n_runs,
            "mean_mrr": statistics.fmean(case["reciprocal_rank"] for case in cases),
            "mean_owner_mrr": statistics.fmean(case["owner_reciprocal_rank"] for case in cases),
            "mean_ndcg": statistics.fmean(case["per_k"][str(rank_cutoff)]["ndcg"] for case in cases),
            "pass_at_r": {},
        }
        for r in rs:
            row["pass_at_r"][str(r)] = {
                "success": pass_at_r(n_runs, relevant_successes, r),
                "owner_success": pass_at_r(n_runs, owner_successes, r),
            }
        query_rows.append(row)

    summary: dict[str, Any] = {
        "single_run_success": bootstrap_mean(
            [row["single_run_success_probability"] for row in query_rows],
            samples=bootstrap_samples,
            seed=bootstrap_seed,
        ),
        "single_run_owner_success": bootstrap_mean(
            [row["single_run_owner_success_probability"] for row in query_rows],
            samples=bootstrap_samples,
            seed=bootstrap_seed + 1,
        ),
        "mrr": bootstrap_mean(
            [row["mean_mrr"] for row in query_rows],
            samples=bootstrap_samples,
            seed=bootstrap_seed + 2,
        ),
        "owner_mrr": bootstrap_mean(
            [row["mean_owner_mrr"] for row in query_rows],
            samples=bootstrap_samples,
            seed=bootstrap_seed + 3,
        ),
        "ndcg": bootstrap_mean(
            [row["mean_ndcg"] for row in query_rows],
            samples=bootstrap_samples,
            seed=bootstrap_seed + 4,
        ),
        "pass_at_r": {},
    }
    for offset, r in enumerate(rs, start=10):
        summary["pass_at_r"][str(r)] = {
            "success": bootstrap_mean(
                [row["pass_at_r"][str(r)]["success"] for row in query_rows],
                samples=bootstrap_samples,
                seed=bootstrap_seed + offset,
            ),
            "owner_success": bootstrap_mean(
                [row["pass_at_r"][str(r)]["owner_success"] for row in query_rows],
                samples=bootstrap_samples,
                seed=bootstrap_seed + offset + 100,
            ),
        }

    first = reports[0]
    return {
        "schema_version": 1,
        "variant": first["variant"],
        "provider": first.get("provider"),
        "runs": n_runs,
        "rank_cutoff": rank_cutoff,
        "pass_trial_counts": list(rs),
        "gold_sha256": first["gold_sha256"],
        "query_config_sha256": first.get("query_config_sha256"),
        "index": first.get("index"),
        "bootstrap": {"unit": "query", "samples": bootstrap_samples, "seed": bootstrap_seed},
        "summary": summary,
        "queries": query_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=pathlib.Path)
    parser.add_argument("--rank-cutoff", type=int, default=10)
    parser.add_argument("--pass-r", default="1,2,5,10")
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    reports = [json.loads(path.read_text()) for path in args.reports]
    requested_r = tuple(int(value) for value in args.pass_r.split(",") if value.strip())
    try:
        output = aggregate_repeated(
            reports,
            rank_cutoff=args.rank_cutoff,
            pass_r=requested_r,
            bootstrap_samples=args.bootstrap_samples,
            bootstrap_seed=args.bootstrap_seed,
        )
    except ValueError as exc:
        parser.error(str(exc))

    s = output["summary"]
    k = output["rank_cutoff"]
    print(
        f"variant={output['variant']} runs={output['runs']} rank_cutoff={k} "
        f"Success@{k}={s['single_run_success']['mean']:.3f} "
        f"Owner-Success@{k}={s['single_run_owner_success']['mean']:.3f}"
    )
    for r in output["pass_trial_counts"]:
        p = s["pass_at_r"][str(r)]
        print(
            f"Pass@{r}[Success@{k}]={p['success']['mean']:.3f} "
            f"Pass@{r}[Owner-Success@{k}]={p['owner_success']['mean']:.3f}"
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
