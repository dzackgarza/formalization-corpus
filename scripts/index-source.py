#!/usr/bin/env python3
"""Build and verify the Zoekt index one source at a time, in an index store.

The store is an rsync location: a local directory or ``host:path``.  It holds
the served primary shards in ``index/``, the metadata shards in
``index-metadata/`` and one provenance record per source in
``index-provenance/<repository>.json``.

``refresh`` finds the registered sources whose shards are stale and processes
them in small batches.  For each batch it hydrates the checkouts, rebuilds the
review catalogue and the filter state for the sources whose revision changed,
and validates both.  Then, for each source, it links the primary and metadata
views into a temporary build directory, builds and verifies the shards, uploads
them and their provenance to the store, removes the stale shards of that source
from the store, and releases the checkout.  A stopped run resumes from the
committed evidence and the stored provenance.

``verify`` checks the whole store against ``sources.tsv``, the committed
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
import time
from dataclasses import dataclass
from typing import Any

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


PRIMARY = "primary"
METADATA = "metadata"
STORE_DIRS = {PRIMARY: "index", METADATA: "index-metadata"}
PROVENANCE = "index-provenance"
INDEX_FLAGS = {PRIMARY: ["-large_file", "**/*.prf"], METADATA: []}
SHARD = re.compile(r"(.+)_v\d+\.\d+\.zoekt$")
BUILD_PREFIX = ".index-build-"
SCHEMA_VERSION = 2
Views = dict[str, dict[str, str]]
Shards = dict[str, dict[str, str]]
Provenance = dict[str, Any]  # a provenance record, as parsed JSON


def store_shell(location: str, command: str) -> str:
    """Run ``command`` in the store root, over ssh when ``location`` is ``host:path``."""
    host, separator, path = location.partition(":")
    if separator and "/" not in host:
        return subprocess.check_output(["ssh", host, f"mkdir -p {path} && cd {path} && {command}"], text=True)
    pathlib.Path(location).mkdir(parents=True, exist_ok=True)
    return subprocess.check_output(["sh", "-c", command], cwd=location, text=True)


def owner(name: str) -> str | None:
    """Return the repository that the store file ``name`` belongs to."""
    directory, _, file = name.partition("/")
    if directory == PROVENANCE:
        return file.removesuffix(".json") if file.endswith(".json") else None
    match = SHARD.fullmatch(file)
    return match.group(1) if match and directory in STORE_DIRS.values() else None


@dataclass
class Store:
    """The index store: each stored file with its SHA-256, and the provenance records."""

    location: str
    files: dict[str, str]
    records: dict[str, Provenance]

    @classmethod
    def open(cls, location: str) -> Store:
        dirs = " ".join([*STORE_DIRS.values(), PROVENANCE])
        listing = store_shell(location, f"mkdir -p {dirs} && find {dirs} -type f -print0 | xargs -0 -r sha256sum")
        files = {name: digest for digest, name in (line.split("  ", 1) for line in listing.splitlines())}
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(["rsync", "-a", f"{location}/{PROVENANCE}/", directory], check=True)
            records = {path.stem: json.loads(path.read_text()) for path in pathlib.Path(directory).glob("*.json")}
        return cls(location, files, records)

    def shards(self, repository: str) -> Shards:
        found: Shards = {view: {} for view in STORE_DIRS}
        for view, directory in STORE_DIRS.items():
            for name, digest in self.files.items():
                if name.startswith(f"{directory}/") and owner(name) == repository:
                    found[view][name.partition("/")[2]] = digest
        return found

    def put(self, source: pathlib.Path, directory: str, names: set[str]) -> None:
        """Make ``names`` in the store ``directory`` equal ``source``: upload those present, delete the rest.

        rsync writes each file under a temporary name and renames it, so Zoekt never loads a partial shard.
        """
        if not names:
            return
        with tempfile.NamedTemporaryFile("w", suffix=".rules") as rules:
            rules.write("".join(f"+ /{name}\n" for name in sorted(names)) + "- *\n")
            rules.flush()
            subprocess.run(
                [
                    "rsync", "-a", "--mkpath", "--delete-after", f"--filter=merge {rules.name}",
                    f"{source}/", f"{self.location}/{directory}/",
                ],
                check=True,
            )
        for name in names:
            path = source / name
            if path.is_file():
                self.files[f"{directory}/{name}"] = sha256_file(path)
            else:
                self.files.pop(f"{directory}/{name}", None)


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


def source_errors(source: Source, state: FilterState, zoekt: str, store: Store) -> list[str]:
    """Return why the stored shards of ``source`` do not represent its committed evidence."""
    repository = source.repository
    record = store.records.get(repository)
    if record is None:
        return [f"{repository}: no index provenance"]
    if record["schema_version"] != SCHEMA_VERSION:
        return [f"{repository}: provenance schema {record['schema_version']} is not {SCHEMA_VERSION}"]
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
    if store.shards(repository) != record["shards"]:
        errors.append(f"{repository}: stored shards differ from provenance")
    return errors


def prune(store: Store, registered: set[str]) -> None:
    """Remove stale build directories, and the stored files of sources absent from ``sources.tsv``."""
    for path in ROOT.glob(f"{BUILD_PREFIX}*"):
        shutil.rmtree(path)
    stale = sorted(name for name in store.files if owner(name) not in registered)
    with tempfile.TemporaryDirectory() as empty:
        for directory in (*STORE_DIRS.values(), PROVENANCE):
            names = {name.partition("/")[2] for name in stale if name.startswith(f"{directory}/")}
            store.put(pathlib.Path(empty), directory, names)
    for name in stale:
        store.records.pop(pathlib.PurePosixPath(name).stem, None)
        print(f"pruned {name}")


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


def needs_evidence(source: Source, state: FilterState, offline: bool, remote: dict[str, str], store: Store) -> bool:
    """Return true when the review catalogue and filter state must be rebuilt from a checkout."""
    if source.transport == "web-dir":
        return not offline or source.repository not in store.records
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


def link_view(source: Source, root: pathlib.Path, files: dict[str, str]) -> None:
    """Hard-link ``files`` from the checkout into ``root`` and require each to match its catalogued hash."""
    for relative, digest in files.items():
        origin = source.root / relative
        if sha256_file(origin) != digest:
            raise SystemExit(f"{source.repository}: {relative} differs from the review catalogue")
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.link(origin, destination)


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


def index_source(source: Source, state: FilterState, zoekt: str, store: Store) -> None:
    """Build and verify the shards of ``source``, then replace its shards and provenance in the store."""
    repository = source.repository
    catalogue = load_json(catalogue_path(repository))
    if source_revision(source) != catalogue["source_revision"]:
        raise SystemExit(f"{repository}: checkout revision differs from the review catalogue")
    views = expected_views(repository, state)
    if not views[PRIMARY]:
        raise SystemExit(f"{repository}: no primary documents")
    # The build directory is under ROOT, on the file system of the checkouts, so the views can be hard links.
    with tempfile.TemporaryDirectory(dir=ROOT, prefix=BUILD_PREFIX) as directory:
        build = pathlib.Path(directory)
        shards: Shards = {}
        for view, files in views.items():
            output = build / "shards" / view
            output.mkdir(parents=True)
            shards[view] = {}
            if not files:
                continue
            root = build / "views" / view / repository
            link_view(source, root, files)
            run(str(ROOT / "bin" / "zoekt-index"), *INDEX_FLAGS[view], "-index", str(output), str(root))
            built = sorted(output.glob("*.zoekt"))
            if indexed_files(repository, built) != set(files):
                raise SystemExit(f"{repository}: {view} shards do not hold exactly the {view} view")
            shards[view] = {path.name: sha256_file(path) for path in built}
        record: Provenance = {
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
        stored = store.shards(repository)
        for view, store_dir in STORE_DIRS.items():
            store.put(build / "shards" / view, store_dir, set(shards[view]) | set(stored[view]))
        provenance = build / PROVENANCE
        provenance.mkdir()
        (provenance / f"{repository}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        store.put(provenance, PROVENANCE, {f"{repository}.json"})
        store.records[repository] = record
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
    deadline = None if args.stop_after is None else time.monotonic() + 60 * args.stop_after
    registered = sources()
    store = Store.open(args.store)
    prune(store, {source.repository for source in registered})
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
    evidence = {s.repository for s in reachable if needs_evidence(s, state, args.offline, remote, store)}
    stale = [s for s in reachable if s.repository in evidence or source_errors(s, state, zoekt, store)]
    # A source whose catalogue is ahead of its filter state stopped mid-batch; finish it first,
    # because every later filter-state rebuild requires the two to agree.
    stale.sort(key=lambda s: state.snapshot_revisions.get(s.repository) == load_json(catalogue_path(s.repository))["source_revision"])
    print(f"{len(stale)} of {len(selected)} sources need indexing; {len(evidence)} need new evidence")
    for start in range(0, len(stale), args.batch_size):
        if deadline is not None and time.monotonic() > deadline:
            print(f"stopped after {args.stop_after} minutes: {len(stale) - start} sources remain")
            break
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
            index_source(source, state, zoekt, store)
            if not args.keep_checkouts:
                release_checkout(source)
    for failure in failures:
        print(f"ERROR: {failure}", file=sys.stderr)
    return 1 if failures else 0


def verify(location: str) -> int:
    registered = sources()
    store = Store.open(location)
    state = load_filter_state()
    zoekt = zoekt_revision()
    names = {source.repository for source in registered}
    errors = [error for source in registered for error in source_errors(source, state, zoekt, store)]
    errors.extend(f"{name}: file of no registered source" for name in sorted(store.files) if owner(name) not in names)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"index ok: {len(registered)} registered sources match their evidence and provenance")
    return 0


def release(location: str) -> int:
    if verify(location):
        raise SystemExit("index verification failed; checkouts kept")
    for source in sources():
        release_checkout(source)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", required=True, help="the index store: a directory or host:path")
    commands = parser.add_subparsers(dest="command", required=True)
    refresh_parser = commands.add_parser("refresh", help="index the stale sources")
    refresh_parser.add_argument("--source", action="append", default=[], help="limit to this repository")
    refresh_parser.add_argument("--group", help="limit to this sync group")
    refresh_parser.add_argument("--offline", action="store_true", help="compare with the checkouts on disk instead of the remotes")
    refresh_parser.add_argument("--keep-checkouts", action="store_true", help="keep each checkout after indexing")
    refresh_parser.add_argument("--batch-size", type=int, default=8, help="checkouts hydrated at one time")
    refresh_parser.add_argument("--stop-after", type=float, metavar="MINUTES", help="start no batch after this many minutes")
    commands.add_parser("verify", help="check the store against the inventory and provenance")
    commands.add_parser("release", help="verify, then remove the reproducible checkouts")
    args = parser.parse_args()
    if args.command == "refresh":
        return refresh(args)
    if args.command == "verify":
        return verify(args.store)
    return release(args.store)


if __name__ == "__main__":
    raise SystemExit(main())
