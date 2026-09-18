#!/usr/bin/env python3
"""Build and query a corpus-wide contentless SQLite FTS5 lexical index.

The canonical source caches are intentionally ghosted after repository review.
This experiment therefore streams exact, already-filtered file contents back
from the canonical Zoekt shard set and builds a distinct mature lexical index
without rehydrating the full corpus on the connector host.  The FTS5 table is
contentless: it keeps the inverted index but does not duplicate source text.

The script has three roles:

* ``manifest`` derives the exact current-primary file inventory from the
  committed repository-review catalogue;
* ``build`` runs on the search host and populates/resumes the contentless FTS5
  database from the local Zoekt HTTP endpoint while verifying every available
  source byte hash against that manifest.  Zoekt's explicit non-content
  sentinels for files it refuses to index are retained as such and recorded in
  metadata rather than being mistaken for source bytes;
* ``query-batch`` executes deterministic BM25-family first-stage experiments
  over a JSON batch supplied on stdin.

No relevance judgments are read by this module.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import itertools
import json
import pathlib
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable, Iterator


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CATALOGUE = ROOT / "filtering" / "repository-review" / "catalogue.jsonl"
DEFAULT_FILTER_STATE = ROOT / "filtering" / "current.jsonl"
SCHEMA_VERSION = 2
TOKENIZER = "unicode61"
ZOEKT_NONCONTENT_SENTINELS = frozenset(
    {
        b"NOT-INDEXED: exceeds the maximum size limit",
        b"NOT-INDEXED: contains too many trigrams",
    }
)


def _zoekt_alternate_representation(raw: bytes) -> str | None:
    """Classify deliberate Zoekt representations that are not source bytes.

    Zoekt indexes a Git symlink as its link-target blob, whereas the review
    catalogue was produced from hydrated working trees and therefore hashes the
    dereferenced file contents.  Relative symlink targets are unambiguous here:
    they are single short path strings beginning with ``./`` or ``../``.  Keep
    this classifier deliberately narrow so an unexplained source mismatch still
    stops the build instead of being laundered as an indexing representation.
    """

    if raw in ZOEKT_NONCONTENT_SENTINELS:
        return "zoekt-sentinel:" + raw.decode("ascii")
    if len(raw) <= 4096 and (raw.startswith(b"../") or raw.startswith(b"./")):
        try:
            target = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if "\n" not in target and "\r" not in target and "\x00" not in target:
            return "git-symlink-target"
    return None


@dataclass(frozen=True)
class ManifestFile:
    repository: str
    path: str
    sha256: str
    size_bytes: int
    proof_assistant: str
    source_revision: str


@dataclass(frozen=True)
class FetchedContent:
    raw: bytes
    representation: str


def _jsonl(path: pathlib.Path) -> Iterator[dict[str, Any]]:
    with path.open() as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL {path}:{number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"expected object in {path}:{number}")
            yield row


def iter_manifest_files(
    *,
    root: pathlib.Path = ROOT,
    catalogue: pathlib.Path = DEFAULT_CATALOGUE,
    filter_state: pathlib.Path = DEFAULT_FILTER_STATE,
) -> Iterator[ManifestFile]:
    """Yield every document in the current materialized primary view.

    Repository-review file manifests are immutable intake snapshots.  Their
    ``current_primary_status`` fields therefore reflect filtering state when the
    catalogue was created, not later accepted review decisions.  Reconstruct the
    live view exactly as ``materialize-index-views.py`` does: start from formal
    source files in the pinned catalogue and apply the current filter state.
    """

    primary_excluded = {
        (str(row["repository"]), str(row["file"]))
        for row in _jsonl(filter_state)
        if row.get("primary") == "exclude"
    }
    seen: set[tuple[str, str]] = set()
    for source in _jsonl(catalogue):
        if source.get("inventory_status") == "retired":
            continue
        repository = str(source["repository"])
        proof_assistant = str(source["proof_assistant"])
        source_revision = str(source["source_revision"])
        source_catalogue = json.loads((root / str(source["catalogue_file"])).read_text())
        for unit in source_catalogue["work_units"]:
            files_manifest = root / str(unit["files_manifest"])
            for item in _jsonl(files_manifest):
                if not item.get("formal_source"):
                    continue
                key = (repository, str(item["path"]))
                if key in primary_excluded:
                    continue
                if key in seen:
                    raise ValueError(f"duplicate current-primary file {repository}:{item['path']}")
                seen.add(key)
                yield ManifestFile(
                    repository=repository,
                    path=str(item["path"]),
                    sha256=str(item["sha256"]),
                    size_bytes=int(item["size_bytes"]),
                    proof_assistant=proof_assistant,
                    source_revision=source_revision,
                )


def write_manifest(output: pathlib.Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    size_bytes = 0
    repositories: set[str] = set()
    digest = hashlib.sha256()
    with output.open("wb") as handle:
        # Large repository-review catalogues may be hash-partitioned into work
        # units, so catalogue traversal order is not necessarily path order.
        # Persist one canonical ordering because the remote builder groups a
        # streaming manifest by repository and validates monotone paths.
        for item in sorted(
            iter_manifest_files(), key=lambda row: (row.repository, row.path)
        ):
            row = {
                "path": item.path,
                "proof_assistant": item.proof_assistant,
                "repository": item.repository,
                "sha256": item.sha256,
                "size_bytes": item.size_bytes,
                "source_revision": item.source_revision,
            }
            encoded = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
            handle.write(encoded)
            digest.update(encoded)
            count += 1
            size_bytes += item.size_bytes
            repositories.add(item.repository)
    return {
        "document_count": count,
        "content_bytes": size_bytes,
        "repository_count": len(repositories),
        "manifest_sha256": digest.hexdigest(),
    }


def read_manifest(path: pathlib.Path) -> Iterator[ManifestFile]:
    previous: tuple[str, str] | None = None
    for row in _jsonl(path):
        item = ManifestFile(
            repository=str(row["repository"]),
            path=str(row["path"]),
            sha256=str(row["sha256"]),
            size_bytes=int(row["size_bytes"]),
            proof_assistant=str(row["proof_assistant"]),
            source_revision=str(row["source_revision"]),
        )
        key = (item.repository, item.path)
        if previous is not None and key <= previous:
            raise ValueError(
                "manifest must be strictly sorted by repository/path; "
                f"saw {key!r} after {previous!r}"
            )
        previous = key
        yield item


def manifest_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regex_escape(text: str) -> str:
    return re.sub(r"([.*+?^${}()|\[\]\\])", r"\\\1", text)


def _quoted_pattern(pattern: str) -> str:
    return '"' + pattern.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _search(
    api_url: str,
    query: str,
    *,
    top: int,
    timeout: float,
) -> tuple[list[dict[str, Any]], int]:
    payload = json.dumps(
        {
            "Q": query,
            "Opts": {
                "MaxDocDisplayCount": max(1, top),
                "ShardMaxMatchCount": max(10000, top * 2),
                "TotalMaxMatchCount": 0,
                "ChunkMatches": True,
                "Whole": True,
            },
        }
    ).encode()
    request = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"search request failed for {query!r}: {exc}") from exc
    decoded = json.loads(body)
    result = decoded.get("Result") or {}
    return list(result.get("Files") or []), int(result.get("FileCount") or 0)


def _decode_file(
    item: dict[str, Any],
    *,
    expected_repository: str,
    expected_path: str,
    expected_sha256: str,
) -> FetchedContent:
    if item.get("Repository") != expected_repository or item.get("FileName") != expected_path:
        raise ValueError(
            "search result identity mismatch: expected "
            f"{expected_repository}:{expected_path}, got "
            f"{item.get('Repository')}:{item.get('FileName')}"
        )
    raw = base64.b64decode(item.get("Content") or "")
    actual = hashlib.sha256(raw).hexdigest()
    if actual == expected_sha256:
        return FetchedContent(raw=raw, representation="source-content")
    alternate = _zoekt_alternate_representation(raw)
    if alternate is not None:
        return FetchedContent(raw=raw, representation=alternate)
    if actual != expected_sha256:
        raise ValueError(
            f"content hash mismatch for {expected_repository}:{expected_path}: "
            f"manifest {expected_sha256}, remote {actual}"
        )
    raise AssertionError("unreachable content verification state")


def fetch_file(
    item: ManifestFile,
    *,
    api_url: str,
    timeout: float,
) -> FetchedContent:
    repository = _quoted_pattern(_regex_escape(item.repository))
    path = _quoted_pattern(_regex_escape(item.path))
    rows, _ = _search(
        api_url,
        f"repo:{repository} file:{path}",
        top=2,
        timeout=timeout,
    )
    exact = [
        row
        for row in rows
        if row.get("Repository") == item.repository and row.get("FileName") == item.path
    ]
    if len(exact) != 1:
        raise ValueError(
            f"expected one canonical result for {item.repository}:{item.path}, got {len(exact)}"
        )
    return _decode_file(
        exact[0],
        expected_repository=item.repository,
        expected_path=item.path,
        expected_sha256=item.sha256,
    )


def fetch_repository(
    repository: str,
    items: list[ManifestFile],
    *,
    api_url: str,
    timeout: float,
) -> dict[str, FetchedContent]:
    repo_pattern = _quoted_pattern(_regex_escape(repository))
    rows, reported = _search(
        api_url,
        f"repo:{repo_pattern}",
        top=len(items) + 8,
        timeout=timeout,
    )
    expected = {item.path: item for item in items}
    actual: dict[str, FetchedContent] = {}
    for row in rows:
        if row.get("Repository") != repository:
            continue
        path = str(row.get("FileName") or "")
        item = expected.get(path)
        if item is None:
            raise ValueError(f"remote index has unexpected file {repository}:{path}")
        actual[path] = _decode_file(
            row,
            expected_repository=repository,
            expected_path=path,
            expected_sha256=item.sha256,
        )
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))[:10]
        extra = sorted(set(actual) - set(expected))[:10]
        raise ValueError(
            f"repository inventory mismatch for {repository}: "
            f"expected={len(expected)} returned={len(actual)} reported={reported} "
            f"missing={missing} extra={extra}"
        )
    return actual


def create_schema(db: sqlite3.Connection) -> None:
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA temp_store=MEMORY")
    db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.execute(
        "CREATE TABLE IF NOT EXISTS docs_meta ("
        "rowid INTEGER PRIMARY KEY, repository TEXT NOT NULL, path TEXT NOT NULL, "
        "sha256 TEXT NOT NULL, proof_assistant TEXT NOT NULL, source_revision TEXT NOT NULL, "
        "indexed_sha256 TEXT, representation TEXT, "
        "UNIQUE(repository, path))"
    )
    columns = {
        str(row[1]) for row in db.execute("PRAGMA table_info(docs_meta)")
    }
    if "indexed_sha256" not in columns:
        db.execute("ALTER TABLE docs_meta ADD COLUMN indexed_sha256 TEXT")
    if "representation" not in columns:
        db.execute("ALTER TABLE docs_meta ADD COLUMN representation TEXT")
    # Schema-v1 databases could only have reached this point after exact source
    # hash verification, because they stopped at the first Zoekt sentinel.  It
    # is therefore safe to mark their already-inserted rows as source content.
    db.execute(
        "UPDATE docs_meta SET indexed_sha256=sha256, representation='source-content' "
        "WHERE indexed_sha256 IS NULL OR representation IS NULL"
    )
    db.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5("
        "source, path, content, content='', tokenize='unicode61')"
    )
    db.execute("CREATE INDEX IF NOT EXISTS docs_meta_repository ON docs_meta(repository)")


def _meta(db: sqlite3.Connection) -> dict[str, str]:
    return {str(key): str(value) for key, value in db.execute("SELECT key, value FROM meta")}


def _put_meta(db: sqlite3.Connection, key: str, value: Any) -> None:
    db.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def _insert_document(
    db: sqlite3.Connection,
    item: ManifestFile,
    fetched: FetchedContent,
) -> bool:
    existing = db.execute(
        "SELECT rowid, sha256 FROM docs_meta WHERE repository=? AND path=?",
        (item.repository, item.path),
    ).fetchone()
    if existing is not None:
        if str(existing[1]) != item.sha256:
            raise ValueError(
                f"resume hash mismatch for {item.repository}:{item.path}: "
                f"database {existing[1]}, manifest {item.sha256}"
            )
        return False
    cursor = db.execute(
        "INSERT INTO docs_meta(repository, path, sha256, proof_assistant, source_revision, "
        "indexed_sha256, representation) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            item.repository,
            item.path,
            item.sha256,
            item.proof_assistant,
            item.source_revision,
            hashlib.sha256(fetched.raw).hexdigest(),
            fetched.representation,
        ),
    )
    rowid = int(cursor.lastrowid)
    db.execute(
        "INSERT INTO docs(rowid, source, path, content) VALUES (?, ?, ?, ?)",
        (
            rowid,
            item.repository,
            item.path,
            fetched.raw.decode("utf-8", "replace"),
        ),
    )
    return True


def _group_manifest(path: pathlib.Path) -> Iterator[tuple[str, list[ManifestFile]]]:
    for repository, group in itertools.groupby(read_manifest(path), key=lambda item: item.repository):
        items = list(group)
        paths = [item.path for item in items]
        if paths != sorted(paths):
            raise ValueError(f"manifest paths are not sorted within {repository}")
        yield repository, items


def build_index(
    *,
    manifest: pathlib.Path,
    db_path: pathlib.Path,
    api_url: str,
    timeout: float,
    workers: int,
    repository_batch_files: int,
    repository_batch_bytes: int,
    optimize: bool,
) -> dict[str, Any]:
    if workers <= 0:
        raise ValueError("workers must be positive")
    manifest_digest = manifest_sha256(manifest)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    try:
        create_schema(db)
        state = _meta(db)
        prior_manifest = state.get("manifest_sha256")
        if prior_manifest is not None and prior_manifest != manifest_digest:
            raise ValueError(
                "existing database was built from a different manifest: "
                f"{prior_manifest} != {manifest_digest}"
            )
        _put_meta(db, "schema_version", SCHEMA_VERSION)
        _put_meta(db, "manifest_sha256", manifest_digest)
        _put_meta(db, "tokenizer", TOKENIZER)
        _put_meta(db, "sqlite_version", sqlite3.sqlite_version)
        _put_meta(db, "complete", 0)
        db.commit()

        started = time.perf_counter()
        repository_count = 0
        inserted = 0
        expected_total = 0
        expected_bytes = 0
        for repository, items in _group_manifest(manifest):
            repository_count += 1
            expected_total += len(items)
            expected_bytes += sum(item.size_bytes for item in items)
            before = int(
                db.execute(
                    "SELECT COUNT(*) FROM docs_meta WHERE repository=?", (repository,)
                ).fetchone()[0]
            )
            if before == len(items):
                print(
                    f"{repository_count:04d} {repository} files={len(items)} already-indexed",
                    flush=True,
                )
                continue
            if before:
                expected_paths = {item.path for item in items}
                existing_paths = {
                    str(row[0])
                    for row in db.execute(
                        "SELECT path FROM docs_meta WHERE repository=?", (repository,)
                    )
                }
                if not existing_paths <= expected_paths:
                    raise ValueError(f"database has stale paths for {repository}")

            repo_bytes = sum(item.size_bytes for item in items)
            fetch_whole_repo = (
                len(items) <= repository_batch_files and repo_bytes <= repository_batch_bytes
            )
            if fetch_whole_repo:
                contents = fetch_repository(
                    repository,
                    items,
                    api_url=api_url,
                    timeout=timeout,
                )
                for item in items:
                    inserted += int(_insert_document(db, item, contents[item.path]))
            else:
                missing = [
                    item
                    for item in items
                    if db.execute(
                        "SELECT 1 FROM docs_meta WHERE repository=? AND path=?",
                        (item.repository, item.path),
                    ).fetchone()
                    is None
                ]

                def fetch(item: ManifestFile) -> tuple[ManifestFile, FetchedContent]:
                    return item, fetch_file(item, api_url=api_url, timeout=timeout)

                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                    for item, fetched in pool.map(fetch, missing):
                        inserted += int(_insert_document(db, item, fetched))
            db.commit()
            after = int(
                db.execute(
                    "SELECT COUNT(*) FROM docs_meta WHERE repository=?", (repository,)
                ).fetchone()[0]
            )
            if after != len(items):
                raise ValueError(
                    f"repository insertion incomplete for {repository}: {after}/{len(items)}"
                )
            elapsed = time.perf_counter() - started
            print(
                f"{repository_count:04d} {repository} files={len(items)} "
                f"mode={'repository' if fetch_whole_repo else 'file'} total={expected_total} "
                f"elapsed_s={elapsed:.1f}",
                flush=True,
            )

        actual_total = int(db.execute("SELECT COUNT(*) FROM docs_meta").fetchone()[0])
        if actual_total != expected_total:
            raise ValueError(f"database document count mismatch: {actual_total} != {expected_total}")
        if optimize:
            print("optimizing FTS5 index", flush=True)
            db.execute("INSERT INTO docs(docs) VALUES ('optimize')")
            db.commit()
        _put_meta(db, "repository_count", repository_count)
        _put_meta(db, "document_count", actual_total)
        _put_meta(db, "content_bytes", expected_bytes)
        _put_meta(db, "complete", 1)
        _put_meta(db, "build_elapsed_seconds", f"{time.perf_counter() - started:.6f}")
        db.commit()
        return index_fingerprint(db, db_path=db_path)
    finally:
        db.close()


def _fts_quote(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def fts_match(terms: Iterable[str], *, field: str | None = None) -> str:
    values = [term for term in terms if term]
    if not values:
        return '"__formalization_corpus_no_terms__"'
    if field is None:
        return " OR ".join(_fts_quote(term) for term in values)
    if field not in {"source", "path", "content"}:
        raise ValueError(f"unsupported FTS field {field!r}")
    return " OR ".join(f"{field} : {_fts_quote(term)}" for term in values)


def _rank_channel(
    db: sqlite3.Connection,
    *,
    terms: list[str],
    field: str | None,
    top: int,
) -> list[tuple[int, float]]:
    query = fts_match(terms, field=field)
    rows = db.execute(
        "SELECT rowid, bm25(docs, 1.0, 1.0, 1.0) AS score "
        "FROM docs WHERE docs MATCH ? ORDER BY score ASC, rowid ASC LIMIT ?",
        (query, top),
    ).fetchall()
    return [(int(rowid), -float(score)) for rowid, score in rows]


def _result_rows(
    db: sqlite3.Connection,
    ranked: list[tuple[int, float, dict[str, int]]],
) -> list[dict[str, Any]]:
    if not ranked:
        return []
    ids = [rowid for rowid, _, _ in ranked]
    placeholders = ",".join("?" for _ in ids)
    metadata = {
        int(rowid): (str(repository), str(path))
        for rowid, repository, path in db.execute(
            f"SELECT rowid, repository, path FROM docs_meta WHERE rowid IN ({placeholders})",
            ids,
        )
    }
    result: list[dict[str, Any]] = []
    for rowid, score, ranks in ranked:
        repository, path = metadata[rowid]
        result.append(
            {
                "Repository": repository,
                "FileName": path,
                "Score": score,
                "FieldRanks": ranks,
            }
        )
    return result


def query_index(
    db: sqlite3.Connection,
    *,
    terms: list[str],
    top: int,
    mode: str,
    rrf_constant: int = 60,
) -> list[dict[str, Any]]:
    if top <= 0:
        raise ValueError("top must be positive")
    if rrf_constant <= 0:
        raise ValueError("RRF constant must be positive")
    if mode == "bm25-all":
        rows = _rank_channel(db, terms=terms, field=None, top=top)
        return _result_rows(
            db,
            [(rowid, score, {"all": rank}) for rank, (rowid, score) in enumerate(rows, 1)],
        )
    if mode != "fielded-rrf":
        raise ValueError(f"unsupported query mode {mode!r}")

    scores: dict[int, float] = {}
    ranks: dict[int, dict[str, int]] = {}
    # Retrieve deeper in each independent field so the fused top-k is not
    # artificially clipped by a field-local top-k boundary.
    channel_depth = max(top, min(1000, top * 3))
    for field in ("source", "path", "content"):
        rows = _rank_channel(db, terms=terms, field=field, top=channel_depth)
        for rank, (rowid, _) in enumerate(rows, start=1):
            scores[rowid] = scores.get(rowid, 0.0) + 1.0 / (rrf_constant + rank)
            ranks.setdefault(rowid, {})[field] = rank
    fused = sorted(
        scores,
        key=lambda rowid: (-scores[rowid], min(ranks[rowid].values()), rowid),
    )[:top]
    return _result_rows(db, [(rowid, scores[rowid], ranks[rowid]) for rowid in fused])


def index_fingerprint(db: sqlite3.Connection, *, db_path: pathlib.Path) -> dict[str, Any]:
    meta = _meta(db)
    page_count = int(db.execute("PRAGMA page_count").fetchone()[0])
    page_size = int(db.execute("PRAGMA page_size").fetchone()[0])
    payload = {
        "kind": "sqlite-fts5-contentless-v1",
        "schema_version": int(meta.get("schema_version", 0)),
        "manifest_sha256": meta.get("manifest_sha256"),
        "tokenizer": meta.get("tokenizer"),
        "sqlite_version": meta.get("sqlite_version"),
        "repository_count": int(meta.get("repository_count", 0)),
        "document_count": int(meta.get("document_count", 0)),
        "content_bytes": int(meta.get("content_bytes", 0)),
        "complete": meta.get("complete") == "1",
        "index_bytes": page_count * page_size,
        "db_file_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "representation_counts": {
            str(representation): int(count)
            for representation, count in db.execute(
                "SELECT representation, COUNT(*) FROM docs_meta "
                "GROUP BY representation ORDER BY representation"
            )
        },
    }
    payload["metadata_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


def query_batch(
    *,
    db_path: pathlib.Path,
    requests: list[dict[str, Any]],
    mode: str,
    rrf_constant: int,
) -> dict[str, Any]:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        fingerprint = index_fingerprint(db, db_path=db_path)
        if not fingerprint["complete"]:
            raise ValueError("FTS5 index is incomplete")
        responses: list[dict[str, Any]] = []
        for request in requests:
            started = time.perf_counter()
            results = query_index(
                db,
                terms=[str(term) for term in request.get("terms", [])],
                top=int(request.get("top", 200)),
                mode=mode,
                rrf_constant=rrf_constant,
            )
            responses.append(
                {
                    "id": str(request["id"]),
                    "elapsed_ms": (time.perf_counter() - started) * 1000,
                    "results": results,
                }
            )
        return {"index": fingerprint, "mode": mode, "responses": responses}
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("output", type=pathlib.Path)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--manifest", type=pathlib.Path, required=True)
    build_parser.add_argument("--db", type=pathlib.Path, required=True)
    build_parser.add_argument("--api-url", default="http://127.0.0.1:6071/api/search")
    build_parser.add_argument("--timeout", type=float, default=120.0)
    build_parser.add_argument("--workers", type=int, default=4)
    build_parser.add_argument("--repository-batch-files", type=int, default=512)
    build_parser.add_argument("--repository-batch-bytes", type=int, default=32 * 1024 * 1024)
    build_parser.add_argument("--optimize", action="store_true")

    query_parser = subparsers.add_parser("query-batch")
    query_parser.add_argument("--db", type=pathlib.Path, required=True)
    query_parser.add_argument("--mode", choices=("bm25-all", "fielded-rrf"), required=True)
    query_parser.add_argument("--rrf-constant", type=int, default=60)

    args = parser.parse_args()
    if args.command == "manifest":
        print(json.dumps(write_manifest(args.output), sort_keys=True))
        return 0
    if args.command == "build":
        try:
            fingerprint = build_index(
                manifest=args.manifest,
                db_path=args.db,
                api_url=args.api_url,
                timeout=args.timeout,
                workers=args.workers,
                repository_batch_files=args.repository_batch_files,
                repository_batch_bytes=args.repository_batch_bytes,
                optimize=args.optimize,
            )
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(fingerprint, sort_keys=True))
        return 0
    if args.command == "query-batch":
        try:
            requests = json.load(sys.stdin)
            if not isinstance(requests, list):
                raise ValueError("query batch must be a JSON list")
            report = query_batch(
                db_path=args.db,
                requests=requests,
                mode=args.mode,
                rrf_constant=args.rrf_constant,
            )
        except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(report, sort_keys=True))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
