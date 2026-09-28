#!/usr/bin/env python3
"""Build and verify the Zoekt index one source at a time.

``refresh`` finds the registered sources whose shards are stale and processes
them in small batches.  For each batch it hydrates the checkouts, rebuilds the
review catalogue and the filter state for the sources whose revision changed,
and validates both.  Then, for each source, it links the primary and metadata
views, builds and verifies the shards, records the provenance in
``.index-provenance/<repository>.json``, and releases the views and the
checkout.  A stopped run resumes from the committed evidence and the recorded
provenance.

``verify`` checks the whole index against ``sources.tsv``, the committed
evidence and the provenance, with no checkout.  ``release`` runs ``verify`` and
then removes the checkouts that ``sources.tsv`` can hydrate again.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from filtering_lib import (
    CURRENT,
    ROOT,
    SNAPSHOT,
    SOURCE_TABLE,
    Source,
    load_jsonl,
    sha256_file,
    source_revision,
    sources,
)
from repository_review_lib import catalogue_path, catalogued_records, corpus_commit, load_json, utc_now


PROVENANCE_ROOT = ROOT / ".index-provenance"
PRIMARY = "primary"
METADATA = "metadata"
INDEX_DIRS = {PRIMARY: ROOT / ".zoekt", METADATA: ROOT / ".zoekt-metadata"}
VIEW_DIRS = {PRIMARY: ROOT / ".index-primary", METADATA: ROOT / ".index-metadata"}
INDEX_FLAGS = {PRIMARY: ["-large_file", "**/*.prf"], METADATA: []}
SHARD = re.compile(r"(.+)_v\d+\.\d+\.zoekt$")
SCHEMA_VERSION = 1
Views = dict[str, dict[str, str]]


@dataclass(frozen=True)
class FilterState:
    excluded_primary: set[tuple[str, str]]
    included_metadata: set[tuple[str, str]]
    snapshot_revisions: dict[str, str | None]


def load_filter_state() -> FilterState:
    rows = load_jsonl(CURRENT)
    return FilterState(
        excluded_primary={(row["repository"], row["file"]) for row in rows if row["primary"] == "exclude"},
        included_metadata={(row["repository"], row["file"]) for row in rows if row["auxiliary"] == "include"},
        snapshot_revisions=json.loads(SNAPSHOT.read_text())["source_revisions"],
    )


def zoekt_revision() -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT / "tools" / "sourcegraph__zoekt"), "rev-parse", "HEAD"], text=True
    ).strip()


def expected_views(repository: str, state: FilterState) -> Views:
    """Map each view to its files and their catalogued SHA-256, from committed evidence only."""
    views: Views = {PRIMARY: {}, METADATA: {}}
    for record in catalogued_records(repository, {}):
        key = (repository, record.path)
        if record.formal_source and key not in state.excluded_primary:
            views[PRIMARY][record.path] = record.sha256
        if key in state.included_metadata:
            views[METADATA][record.path] = record.sha256
    return views


def view_digest(files: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(sorted(files.items())).encode()).hexdigest()


def shard_paths(repository: str) -> dict[str, list[pathlib.Path]]:
    found: dict[str, list[pathlib.Path]] = {}
    for view, index in INDEX_DIRS.items():
        found[view] = sorted(
            path
            for path in index.glob("*.zoekt")
            if (match := SHARD.fullmatch(path.name)) and match.group(1) == repository
        )
    return found


def provenance_path(repository: str) -> pathlib.Path:
    return PROVENANCE_ROOT / f"{repository}.json"


def source_errors(source: Source, state: FilterState, zoekt: str) -> list[str]:
    """Return why the recorded shards of ``source`` do not represent its committed evidence."""
    repository = source.repository
    path = provenance_path(repository)
    if not path.is_file():
        return [f"{repository}: no index provenance"]
    record = json.loads(path.read_text())
    catalogue = load_json(catalogue_path(repository))
    errors: list[str] = []
    if record["source_revision"] != catalogue["source_revision"]:
        errors.append(f"{repository}: indexed revision differs from the review catalogue")
    if record["source_snapshot_sha256"] != catalogue["source_snapshot_sha256"]:
        errors.append(f"{repository}: indexed snapshot differs from the review catalogue")
    if state.snapshot_revisions.get(repository) != catalogue["source_revision"]:
        errors.append(f"{repository}: filter state revision differs from the review catalogue")
    if record["zoekt_revision"] != zoekt:
        errors.append(f"{repository}: shards were built by another Zoekt revision")
    views = expected_views(repository, state)
    if not views[PRIMARY]:
        errors.append(f"{repository}: no primary documents")
    for view, files in views.items():
        if record["views"][view]["sha256"] != view_digest(files):
            errors.append(f"{repository}: {view} view changed since indexing")
    on_disk = {
        path.relative_to(ROOT).as_posix(): path for paths in shard_paths(repository).values() for path in paths
    }
    if set(on_disk) != set(record["shards"]):
        errors.append(f"{repository}: shard files differ from provenance")
        return errors
    for name, path in on_disk.items():
        if sha256_file(path) != record["shards"][name]:
            errors.append(f"{repository}: {name} differs from provenance")
    return errors


def prune(registered: set[str]) -> None:
    """Remove shards, provenance and views of sources absent from ``sources.tsv``."""
    removed: list[pathlib.Path] = []
    for index in INDEX_DIRS.values():
        for path in index.glob("*.zoekt"):
            match = SHARD.fullmatch(path.name)
            if match and match.group(1) not in registered:
                path.unlink()
                removed.append(path)
    for path in PROVENANCE_ROOT.glob("*.json"):
        if path.stem not in registered:
            path.unlink()
            removed.append(path)
    for root in VIEW_DIRS.values():
        if root.exists():
            shutil.rmtree(root)
    for path in removed:
        print(f"pruned {path.relative_to(ROOT)}")


def remote_revision(source: Source) -> str:
    """Return the revision that sync would check out, without cloning."""
    if source.root.exists() and not subprocess.run(
        ["git", "-C", str(source.root), "symbolic-ref", "-q", "HEAD"], stdout=subprocess.DEVNULL
    ).returncode == 0:
        return str(source_revision(source))
    output = subprocess.check_output(
        ["git", "ls-remote", source.url, "HEAD"],
        text=True,
        timeout=120,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0"},
    )
    return output.split()[0]


def needs_evidence(source: Source, state: FilterState, offline: bool, remote: dict[str, str]) -> bool:
    """Return true when the review catalogue and filter state must be rebuilt from a checkout."""
    if source.transport == "web-dir":
        return not offline or not provenance_path(source.repository).is_file()
    recorded = load_json(catalogue_path(source.repository))["source_revision"]
    if state.snapshot_revisions.get(source.repository) != recorded:
        return True
    if offline:
        return source.root.exists() and source_revision(source) != recorded
    return remote[source.repository] != recorded


def run(*command: str, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, env=None if env is None else {**os.environ, **env})
    if result.returncode:
        raise SystemExit(f"stopped: {command[1] if command[0] == 'python' else command[0]} exited {result.returncode}")


def hydrate(batch: list[Source]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        manifest = pathlib.Path(directory) / "sources.tsv"
        lines = SOURCE_TABLE.read_text().splitlines(keepends=True)
        wanted = {source.directory.as_posix() for source in batch}
        manifest.write_text(lines[0] + "".join(line for line in lines[1:] if line.split("\t")[1] in wanted))
        run("./sync-manifest.zsh", str(manifest), env={"SYNC_GROUP": "all"})


def link_view(source: Source, view: str, files: dict[str, str]) -> pathlib.Path:
    """Hard-link ``files`` from the checkout and require each to match its catalogued hash."""
    root = VIEW_DIRS[view] / source.repository
    if root.exists():
        shutil.rmtree(root)
    for relative, digest in files.items():
        origin = source.root / relative
        if sha256_file(origin) != digest:
            raise SystemExit(f"{source.repository}: {relative} differs from the review catalogue")
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.link(origin, destination)
    return root


def indexed_files(repository: str, shards: list[pathlib.Path]) -> set[str]:
    prefix = f"{repository}/"
    files: set[str] = set()
    for shard in shards:
        output = subprocess.check_output([str(ROOT / "bin" / "zoekt"), "-shard", str(shard), "-l", "-r", "f:."], text=True)
        for line in output.splitlines():
            if not line.startswith(prefix):
                raise SystemExit(f"{shard.name}: document {line!r} belongs to another repository")
            files.add(line.removeprefix(prefix))
    return files


def index_source(source: Source, state: FilterState, zoekt: str) -> None:
    repository = source.repository
    catalogue = load_json(catalogue_path(repository))
    if source_revision(source) != catalogue["source_revision"]:
        raise SystemExit(f"{repository}: checkout revision differs from the review catalogue")
    views = expected_views(repository, state)
    if not views[PRIMARY]:
        raise SystemExit(f"{repository}: no primary documents")
    for paths in shard_paths(repository).values():
        for path in paths:
            path.unlink()
    shards: dict[str, str] = {}
    for view, files in views.items():
        if not files:
            continue
        root = link_view(source, view, files)
        INDEX_DIRS[view].mkdir(exist_ok=True)
        run(str(ROOT / "bin" / "zoekt-index"), *INDEX_FLAGS[view], "-index", str(INDEX_DIRS[view]), str(root))
        shutil.rmtree(root)
        built = shard_paths(repository)[view]
        if indexed_files(repository, built) != set(files):
            raise SystemExit(f"{repository}: {view} shards do not hold exactly the {view} view")
        shards.update({path.relative_to(ROOT).as_posix(): sha256_file(path) for path in built})
    record = {
        "schema_version": SCHEMA_VERSION,
        "repository": repository,
        "source_revision": catalogue["source_revision"],
        "source_snapshot_sha256": catalogue["source_snapshot_sha256"],
        "views": {view: {"files": len(files), "sha256": view_digest(files)} for view, files in views.items()},
        "zoekt_revision": zoekt,
        "shards": shards,
        "corpus_git_commit": corpus_commit(),
        "indexed_at": utc_now(),
    }
    PROVENANCE_ROOT.mkdir(exist_ok=True)
    provenance_path(repository).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"indexed {repository}: {record['views'][PRIMARY]['files']} primary, {record['views'][METADATA]['files']} metadata documents")


def reproducible(source: Source) -> bool:
    """Return true when sync can hydrate the checkout again from ``sources.tsv`` alone."""
    if source.transport == "web-dir":
        return True
    attached = subprocess.run(["git", "-C", str(source.root), "symbolic-ref", "-q", "HEAD"], stdout=subprocess.DEVNULL)
    clean = subprocess.check_output(["git", "-C", str(source.root), "status", "--porcelain"], text=True) == ""
    return attached.returncode == 0 and clean


def release_checkout(source: Source) -> None:
    if not source.root.exists():
        return
    if not reproducible(source):
        print(f"kept {source.directory}: detached or modified checkout")
        return
    shutil.rmtree(source.root)
    print(f"released {source.directory}")


def refresh(args: argparse.Namespace) -> int:
    registered = sources()
    prune({source.repository for source in registered})
    selected = [
        source
        for source in registered
        if (not args.source or source.repository in args.source) and (not args.group or source.sync_group == args.group)
    ]
    unknown = sorted(set(args.source) - {source.repository for source in registered})
    if unknown:
        raise SystemExit(f"not registered in sources.tsv: {unknown}")
    remote: dict[str, str] = {}
    failures: list[str] = []
    if not args.offline:
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            jobs = {
                source.repository: pool.submit(remote_revision, source)
                for source in selected
                if source.transport != "web-dir"
            }
            for repository, job in jobs.items():
                try:
                    remote[repository] = job.result()
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, IndexError) as error:
                    failures.append(f"{repository}: cannot read the remote revision ({error})")
    reachable = [s for s in selected if s.transport == "web-dir" or args.offline or s.repository in remote]
    state = load_filter_state()
    zoekt = zoekt_revision()
    evidence = {s.repository for s in reachable if needs_evidence(s, state, args.offline, remote)}
    stale = [s for s in reachable if s.repository in evidence or source_errors(s, state, zoekt)]
    # A source whose catalogue is ahead of its filter state stopped mid-batch; finish it first,
    # because every later filter-state rebuild requires the two to agree.
    stale.sort(key=lambda s: state.snapshot_revisions.get(s.repository) == load_json(catalogue_path(s.repository))["source_revision"])
    print(f"{len(stale)} of {len(selected)} sources need indexing; {len(evidence)} need new evidence")
    for start in range(0, len(stale), args.batch_size):
        batch = stale[start : start + args.batch_size]
        absent = [s for s in batch if not s.root.exists()]
        if args.offline and absent:
            raise SystemExit(f"offline refresh needs these checkouts: {[s.repository for s in absent]}")
        evidence.update(s.repository for s in absent)
        rebuild = [s for s in batch if s.repository in evidence]
        if rebuild and not args.offline:
            hydrate(rebuild)
        rebuild_names = [f"--source={s.repository}" for s in rebuild]
        if rebuild:
            run("python", "scripts/repository-review.py", "build", *rebuild_names)
            run("python", "scripts/repository-review.py", "validate")
            run("python", "scripts/build-filter-state.py", *rebuild_names)
            run("python", "scripts/validate-filter-state.py")
            state = load_filter_state()
        for source in batch:
            index_source(source, state, zoekt)
            if not args.keep_checkouts:
                release_checkout(source)
    for failure in failures:
        print(f"ERROR: {failure}", file=sys.stderr)
    return 1 if failures else 0


def verify() -> int:
    registered = sources()
    state = load_filter_state()
    zoekt = zoekt_revision()
    names = {source.repository for source in registered}
    errors = [error for source in registered for error in source_errors(source, state, zoekt)]
    for index in INDEX_DIRS.values():
        for path in index.glob("*.zoekt"):
            match = SHARD.fullmatch(path.name)
            if not match or match.group(1) not in names:
                errors.append(f"{path.relative_to(ROOT)}: shard of no registered source")
    errors.extend(f"{path.name}: provenance of no registered source" for path in PROVENANCE_ROOT.glob("*.json") if path.stem not in names)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"index ok: {len(registered)} registered sources match their evidence and provenance")
    return 0


def release() -> int:
    if verify():
        raise SystemExit("index verification failed; checkouts kept")
    for source in sources():
        release_checkout(source)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    refresh_parser = commands.add_parser("refresh", help="index the stale sources")
    refresh_parser.add_argument("--source", action="append", default=[], help="limit to this repository")
    refresh_parser.add_argument("--group", help="limit to this sync group")
    refresh_parser.add_argument("--offline", action="store_true", help="compare with the checkouts on disk instead of the remotes")
    refresh_parser.add_argument("--keep-checkouts", action="store_true", help="keep each checkout after indexing")
    refresh_parser.add_argument("--batch-size", type=int, default=8, help="checkouts hydrated at one time")
    commands.add_parser("verify", help="check the index against the inventory and provenance")
    commands.add_parser("release", help="verify, then remove the reproducible checkouts")
    args = parser.parse_args()
    if args.command == "refresh":
        return refresh(args)
    if args.command == "verify":
        return verify()
    return release()


if __name__ == "__main__":
    raise SystemExit(main())
