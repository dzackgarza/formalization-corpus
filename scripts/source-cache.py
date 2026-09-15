#!/usr/bin/env python3
"""Manage disposable source hydration around persistent Zoekt shards.

`sources.tsv` is the source identity manifest.  Source checkouts are a cache: they may
be removed after their content has been audited/indexed.  The persistent artifacts are
the committed review catalogue/ledger and the `.zoekt` shard(s).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
from typing import Any, Iterable
from functools import lru_cache

from filtering_lib import ROOT, Source, iter_files, sha256_file, sources
from repository_review_lib import BATCHES, load_catalogue_index, load_unit_file_records, load_units

PRIMARY_VIEW = ROOT / ".index-primary"
METADATA_VIEW = ROOT / ".index-metadata"
INDEX = ROOT / ".zoekt"


@lru_cache(maxsize=1)
def source_map() -> dict[str, Source]:
    return {source.repository: source for source in sources()}


@lru_cache(maxsize=1)
def catalogue_map() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in load_catalogue_index():
        if row.get("inventory_status", "active") != "active":
            continue
        data = json.loads((ROOT / row["catalogue_file"]).read_text())
        out[str(data["repository"])] = data
    return out


def batch_repositories(batch_id: str) -> list[str]:
    rows = [json.loads(line) for line in BATCHES.read_text().splitlines() if line.strip()]
    batch = next((row for row in rows if row.get("batch_id") == batch_id), None)
    if batch is None:
        raise SystemExit(f"unknown review batch {batch_id}")
    return sorted(set(map(str, batch.get("repositories", []))))


def select_repositories(repositories: list[str], batch: str | None) -> list[str]:
    selected = set(repositories)
    if batch:
        selected.update(batch_repositories(batch))
    registered = source_map()
    unknown = sorted(selected - set(registered))
    if unknown:
        raise SystemExit(f"unknown active repositories: {unknown}")
    if not selected:
        raise SystemExit("select at least one --repository or --batch")
    return sorted(selected)


def proof_globs(kind: str) -> list[str]:
    table = {
        "lean": ["/**/*.lean", "/lakefile.*", "/lean-toolchain", "/lake-manifest.json"],
        "rocq": ["/**/*.v"],
        "agda": ["/**/*.agda", "/**/*.lagda*"],
        "isabelle": ["/**/*.thy"],
        "hol-light": ["/**/*.ml", "/**/*.hl"],
        "hol4": ["/**/*.sml", "/**/*.sig"],
        "mizar": ["/**/*.miz"],
        "metamath": ["/**/*.mm", "/**/*.mm0", "/**/*.mm1"],
        "acl2": ["/**/*.lisp", "/**/*.lsp", "/**/*.acl2"],
        "pvs": ["/**/*.pvs", "/**/*.prf"],
        "twelf": ["/**/*.elf"],
    }
    try:
        return table[kind]
    except KeyError as exc:
        raise SystemExit(f"unsupported proof assistant for hydration: {kind}") from exc


def run_git(args: list[str], *, cwd: pathlib.Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    return subprocess.run(["git", *args], cwd=cwd, env=env, text=True, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def ensure_clean(source: Source) -> None:
    # `git status --untracked-files=all` is pathologically slow in very large
    # sparse imports such as ACL2. Check tracked/index state without expanding
    # untracked paths, then probe untracked material separately and stop at the
    # first entry. Both checks are fail-closed, but scale with sparse caches.
    tracked = run_git(
        ["-C", str(source.root), "status", "--porcelain=v1", "--untracked-files=no"]
    ).stdout
    if tracked.strip():
        raise SystemExit(f"refusing to alter dirty source cache {source.repository}:\n{tracked}")
    untracked = run_git(
        ["-C", str(source.root), "ls-files", "--others", "--exclude-standard", "--directory"]
    ).stdout.splitlines()
    if untracked:
        raise SystemExit(
            f"refusing to alter source cache {source.repository} with untracked material: "
            f"{untracked[0]}"
        )


def write_one_source_manifest(source: Source) -> pathlib.Path:
    handle = tempfile.NamedTemporaryFile("w", delete=False, prefix="formalization-source-", suffix=".tsv")
    path = pathlib.Path(handle.name)
    with handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["url", "directory", "proof_assistant", "transport", "sync_group", "discovered_via"])
        writer.writerow([
            source.url,
            source.directory.as_posix(),
            source.proof_assistant,
            source.transport,
            source.sync_group,
            source.discovered_via,
        ])
    return path


def configure_sparse(source: Source) -> None:
    if source.transport == "web-dir":
        return
    patterns = ["/*", "!/*/", *proof_globs(source.proof_assistant), "/README*"]
    run_git(["-C", str(source.root), "sparse-checkout", "set", "--no-cone", *patterns])


def checkout_revision(source: Source, revision: str | None, *, latest: bool) -> None:
    if source.transport == "web-dir":
        return
    ensure_clean(source)
    run_git(["-C", str(source.root), "remote", "set-url", "origin", source.url], check=False)
    configure_sparse(source)
    if latest:
        run_git(["-C", str(source.root), "fetch", "--prune", "--depth", "1", "origin", "HEAD"])
        run_git(["-C", str(source.root), "checkout", "--detach", "-q", "FETCH_HEAD"])
        return
    if not revision:
        raise SystemExit(f"{source.repository}: catalogue has no pin-able Git revision; use --latest only when intentionally refreshing intake")
    current = run_git(["-C", str(source.root), "rev-parse", "HEAD"]).stdout.strip()
    if current != revision:
        run_git(["-C", str(source.root), "fetch", "--depth", "1", "origin", revision])
        run_git(["-C", str(source.root), "checkout", "--detach", "-q", revision])
    # Reapply the sparse spec after checkout so only formal-source intake material is resident.
    configure_sparse(source)


def hydrate(repository: str, *, latest: bool) -> None:
    source = source_map()[repository]
    catalogue = catalogue_map().get(repository, {})
    revision = catalogue.get("source_revision")
    if source.root.exists() and source.transport != "web-dir" and not (source.root / ".git").exists():
        raise SystemExit(f"{repository}: source path exists but is not the expected nested Git checkout: {source.root}")
    if not source.root.exists():
        source.root.parent.mkdir(parents=True, exist_ok=True)
        manifest = write_one_source_manifest(source)
        try:
            env = dict(os.environ)
            env["SYNC_GROUP"] = "all"
            subprocess.run([str(ROOT / "sync-manifest.zsh"), str(manifest)], cwd=ROOT, env=env, check=True)
        finally:
            manifest.unlink(missing_ok=True)
    if source.transport != "web-dir":
        checkout_revision(source, str(revision) if revision else None, latest=latest)
    print(f"hydrated {repository}: {source.root.relative_to(ROOT)}")


def manifest_material(repository: str) -> dict[str, tuple[int, str]]:
    units = [unit for unit in load_units(active_only=True).values() if unit["repository"] == repository]
    out: dict[str, tuple[int, str]] = {}
    for unit in units:
        for row in load_unit_file_records(unit):
            path = str(row["path"])
            if path in out:
                raise SystemExit(f"{repository}: duplicate catalogue path {path}")
            out[path] = (int(row["size_bytes"]), str(row["sha256"]))
    return out


def verify_web_material(source: Source) -> None:
    expected = manifest_material(source.repository)
    actual: dict[str, tuple[int, str]] = {}
    for path in iter_files(source):
        rel = path.relative_to(source.root).as_posix()
        actual[rel] = (path.stat().st_size, sha256_file(path))
    if actual != expected:
        missing = sorted(set(expected) - set(actual))[:5]
        extra = sorted(set(actual) - set(expected))[:5]
        changed = sorted(path for path in set(actual) & set(expected) if actual[path] != expected[path])[:5]
        raise SystemExit(
            f"refusing to dehydrate changed web-dir source {source.repository}; "
            f"missing={missing} extra={extra} changed={changed}"
        )


def dehydrate(repository: str) -> None:
    source = source_map()[repository]
    if not source.root.exists():
        for root in (PRIMARY_VIEW, METADATA_VIEW):
            shutil.rmtree(root / repository, ignore_errors=True)
        print(f"already dehydrated {repository}")
        return
    catalogue = catalogue_map().get(repository)
    if catalogue is None:
        raise SystemExit(f"{repository}: no committed campaign catalogue; refusing to discard uncatalogued intake")
    if not shard_paths(repository):
        raise SystemExit(f"{repository}: no persistent Zoekt shard exists; refusing to dehydrate unindexed source")
    if source.transport == "web-dir":
        verify_web_material(source)
    else:
        if not (source.root / ".git").is_dir():
            raise SystemExit(f"{repository}: expected nested Git checkout at {source.root}")
        ensure_clean(source)
        expected_revision = catalogue.get("source_revision")
        actual_revision = run_git(["-C", str(source.root), "rev-parse", "HEAD"]).stdout.strip()
        if expected_revision and actual_revision != expected_revision:
            raise SystemExit(
                f"refusing to dehydrate {repository}: checkout revision {actual_revision} != "
                f"catalogued revision {expected_revision}; refresh/audit the catalogue first"
            )
    for root in (PRIMARY_VIEW, METADATA_VIEW):
        shutil.rmtree(root / repository, ignore_errors=True)
    shutil.rmtree(source.root)
    print(f"dehydrated {repository}; persistent review records and Zoekt shards retained")



def preflight_dehydrate(repository: str) -> None:
    source = source_map()[repository]
    if not source.root.exists():
        return
    catalogue = catalogue_map().get(repository)
    if catalogue is None:
        raise SystemExit(f"{repository}: no committed campaign catalogue")
    if not shard_paths(repository):
        raise SystemExit(f"{repository}: no persistent Zoekt shard exists")
    if source.transport == "web-dir":
        verify_web_material(source)
        return
    if not (source.root / ".git").is_dir():
        raise SystemExit(f"{repository}: expected nested Git checkout at {source.root}")
    ensure_clean(source)
    expected_revision = catalogue.get("source_revision")
    actual_revision = run_git(["-C", str(source.root), "rev-parse", "HEAD"]).stdout.strip()
    if expected_revision and actual_revision != expected_revision:
        raise SystemExit(
            f"{repository}: checkout revision {actual_revision} != catalogued revision {expected_revision}"
        )


def dehydrate_all() -> None:
    names = sorted(source_map())
    # Complete preflight before deleting anything.
    for repository in names:
        preflight_dehydrate(repository)
    for repository in names:
        dehydrate(repository)
    print(f"dehydrated all {len(names)} active source caches")


def gc_source_cache() -> None:
    """Dehydrate every currently safe/indexed cache; keep active intake resident."""
    safe: list[str] = []
    kept: list[tuple[str, str]] = []
    for repository in sorted(source_map()):
        try:
            preflight_dehydrate(repository)
        except SystemExit as exc:
            kept.append((repository, str(exc)))
        else:
            if source_map()[repository].root.exists():
                safe.append(repository)
    # Only delete after the full classification pass, so the operator sees a
    # stable preflight boundary even though unsafe in-flight sources are allowed.
    for repository in safe:
        dehydrate(repository)
    for repository, reason in kept:
        print(f"kept {repository}: {reason}")
    print(f"source cache gc: dehydrated={len(safe)} kept={len(kept)}")

def shard_paths(repository: str) -> list[pathlib.Path]:
    return sorted(INDEX.glob(f"{repository}_v*.zoekt"))


def status(repositories: Iterable[str] | None = None) -> None:
    src = source_map()
    names = list(repositories) if repositories is not None else sorted(src)
    hydrated = 0
    for repository in names:
        source = src[repository]
        resident = source.root.exists()
        hydrated += int(resident)
        shards = shard_paths(repository)
        print(f"{repository}\t{'hydrated' if resident else 'ghost'}\tshards={len(shards)}\tpath={source.directory}")
    print(f"summary hydrated={hydrated} ghost={len(names)-hydrated} selected={len(names)}")


def ensure_zoekt_index() -> pathlib.Path:
    binary = ROOT / "bin" / "zoekt-index"
    if binary.is_file():
        return binary
    source = ROOT / "tools" / "sourcegraph__zoekt"
    if not source.is_dir():
        raise SystemExit("Zoekt source is absent; run `just build-zoekt` after hydrating tools")
    binary.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["go", "build", "-o", str(binary), "./cmd/zoekt-index"], cwd=source, check=True)
    return binary


def materialize(repositories: list[str]) -> None:
    cmd = ["python", str(ROOT / "scripts" / "materialize-index-views.py")]
    for repository in repositories:
        cmd.extend(["--repository", repository])
    subprocess.run(cmd, cwd=ROOT, check=True)


def reindex(repositories: list[str], *, keep_views: bool) -> None:
    binary = ensure_zoekt_index()
    INDEX.mkdir(parents=True, exist_ok=True)
    materialize(repositories)
    try:
        for repository in repositories:
            view = PRIMARY_VIEW / repository
            if not view.is_dir():
                raise SystemExit(f"missing materialized primary view for {repository}")
            staging = pathlib.Path(tempfile.mkdtemp(prefix=f".zoekt-stage-{repository}-", dir=ROOT))
            backup = pathlib.Path(tempfile.mkdtemp(prefix=f".zoekt-backup-{repository}-", dir=ROOT))
            old = shard_paths(repository)
            try:
                subprocess.run(
                    [str(binary), "-large_file", "**/*.prf", "-index", str(staging), str(view)],
                    cwd=ROOT,
                    check=True,
                )
                staged = sorted(staging.glob(f"{repository}_v*.zoekt"))
                if not staged:
                    raise SystemExit(f"staged reindex produced no shard for {repository}")
                for path in old:
                    os.replace(path, backup / path.name)
                try:
                    for path in staged:
                        os.replace(path, INDEX / path.name)
                except BaseException:
                    for path in INDEX.glob(f"{repository}_v*.zoekt"):
                        path.unlink()
                    for path in backup.glob(f"{repository}_v*.zoekt"):
                        os.replace(path, INDEX / path.name)
                    raise
                print(f"reindexed {repository}: {len(shard_paths(repository))} shard(s)")
            finally:
                shutil.rmtree(staging, ignore_errors=True)
                shutil.rmtree(backup, ignore_errors=True)
    finally:
        if not keep_views:
            for repository in repositories:
                shutil.rmtree(PRIMARY_VIEW / repository, ignore_errors=True)
                shutil.rmtree(METADATA_VIEW / repository, ignore_errors=True)


def seed_all(*, fresh: bool) -> None:
    if INDEX.exists() and any(INDEX.glob("*.zoekt")):
        if not fresh:
            raise SystemExit(".zoekt is not empty; pass --fresh only for an intentional from-scratch seed")
        shutil.rmtree(INDEX)
    INDEX.mkdir(parents=True, exist_ok=True)
    names = sorted(source_map())
    for number, repository in enumerate(names, start=1):
        print(f"seed {number}/{len(names)} {repository}")
        hydrate(repository, latest=False)
        try:
            reindex([repository], keep_views=False)
        except BaseException:
            print(f"seed failed at {repository}; leaving that source hydrated for inspection")
            raise
        dehydrate(repository)
    print(f"seed complete: {len(names)} repositories; all source caches dehydrated")


def main() -> int:
    parser = argparse.ArgumentParser(description="Hydrate/dehydrate disposable corpus source mirrors")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("hydrate", "dehydrate", "status", "materialize", "reindex"):
        p = sub.add_parser(command)
        p.add_argument("--repository", action="append", default=[])
        p.add_argument("--batch")
        if command == "hydrate":
            p.add_argument("--latest", action="store_true", help="refresh current upstream instead of the committed campaign revision")
        if command == "reindex":
            p.add_argument("--keep-views", action="store_true")
    status_all = sub.add_parser("status-all")
    sub.add_parser("dehydrate-all")
    sub.add_parser("gc")
    seed = sub.add_parser("seed")
    seed.add_argument("--all", action="store_true", required=True)
    seed.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    if args.command == "status-all":
        status()
        return 0
    if args.command == "dehydrate-all":
        dehydrate_all()
        return 0
    if args.command == "gc":
        gc_source_cache()
        return 0
    if args.command == "seed":
        seed_all(fresh=args.fresh)
        return 0
    selected = select_repositories(args.repository, args.batch)
    if args.command == "status":
        status(selected)
    elif args.command == "hydrate":
        for repository in selected:
            hydrate(repository, latest=args.latest)
    elif args.command == "dehydrate":
        for repository in selected:
            dehydrate(repository)
    elif args.command == "materialize":
        materialize(selected)
    else:
        reindex(selected, keep_views=args.keep_views)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
