from __future__ import annotations

import json
import pathlib
import subprocess
import threading
import asyncio
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from formalization_api.app import create_app


class BackendHandler(BaseHTTPRequestHandler):
    search_calls = 0
    list_calls = 0

    def do_POST(self) -> None:  # noqa: N802
        size = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(size))
        if self.path == "/api/search":
            type(self).search_calls += 1
            payload = {
                "Result": {
                    "Files": [
                        {
                            "FileName": "Mathlib.lean",
                            "Repository": "leanprover-community__mathlib4",
                            "Language": "Lean 4",
                            "ChunkMatches": [],
                        }
                    ],
                    "FileCount": 1,
                    "MatchCount": 1,
                    "Duration": 123,
                    "Echo": body,
                }
            }
        elif self.path == "/api/list":
            type(self).list_calls += 1
            payload = {
                "List": {
                    "Repos": [
                        {
                            "Repository": {"Name": "leanprover-community__mathlib4"},
                            "Stats": {"Documents": 1},
                        }
                    ]
                }
            }
        else:
            self.send_response(404)
            self.end_headers()
            return
        encoded = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def backend_server() -> tuple[ThreadingHTTPServer, str]:
    BackendHandler.search_calls = 0
    BackendHandler.list_calls = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), BackendHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


async def with_client(
    url: str,
    callback,
    *,
    duplicate_aliases_path=None,
    file_roles_path=None,
) -> None:
    app = create_app(
        backend_url=url,
        duplicate_aliases_path=duplicate_aliases_path,
        file_roles_path=file_roles_path,
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            await callback(client)


def test_search_is_cached_and_preserves_request_shape() -> None:
    server, url = backend_server()
    try:
        async def run(client: httpx.AsyncClient) -> None:
            payload = {
                "Q": "content:Hasse file:\\.lean$",
                "Opts": {
                    "MaxDocDisplayCount": 5,
                    "ShardMaxMatchCount": 10000,
                    "ChunkMatches": True,
                    "Whole": True,
                },
            }
            first = await client.post("/api/search", json=payload)
            second = await client.post("/api/search", json=payload)
            assert first.status_code == second.status_code == 200
            assert first.headers["x-cache"] == "MISS"
            assert second.headers["x-cache"] == "HIT"
            assert BackendHandler.search_calls == 1
            assert first.json()["Result"]["Echo"] == payload
        asyncio.run(with_client(url, run))
    finally:
        server.shutdown()


def test_documentation_search_uses_shared_backend_and_exact_fd002_membership() -> None:
    class DocumentationBackendHandler(BackendHandler):
        last_query = None

        def do_POST(self) -> None:  # noqa: N802
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size))
            type(self).last_query = body.get("Q")
            payload = {
                "Result": {
                    "Files": [
                        {"FileName": "README.md", "Repository": "docs", "Score": 30},
                        {"FileName": "Index.lean", "Repository": "lean", "Score": 20},
                        {"FileName": "README.md", "Repository": "not-fd002", "Score": 10},
                    ],
                    "FileCount": 3,
                }
            }
            encoded = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    primary = ThreadingHTTPServer(("127.0.0.1", 0), DocumentationBackendHandler)
    threading.Thread(target=primary.serve_forever, daemon=True).start()
    host, port = primary.server_address
    primary_url = f"http://{host}:{port}"
    try:
        with tempfile.TemporaryDirectory() as directory:
            roles = pathlib.Path(directory) / "filter-state.jsonl"
            roles.write_text(
                "\n".join(
                    [
                        json.dumps({
                            "decision_id": "FD-002", "primary": "exclude", "auxiliary": "include",
                            "repository": "docs", "file": "README.md",
                        }),
                        json.dumps({
                            "decision_id": "FD-016", "primary": "retain", "auxiliary": "include",
                            "repository": "lean", "file": "Index.lean",
                        }),
                    ]
                ) + "\n"
            )

            async def run(client: httpx.AsyncClient) -> None:
                response = await client.post(
                    "/api/search/documentation", json={"Q": "topic"}
                )
                assert response.status_code == 200
                result = response.json()["Result"]
                assert [(f["Repository"], f["FileName"]) for f in result["Files"]] == [
                    ("docs", "README.md")
                ]
                assert result["Files"][0]["FileRole"] == "documentation-readme"
                assert result["DocumentationFilesReturned"] == 1
                assert result["AuxiliaryChannel"] == "documentation"
                assert result["FileCount"] == 1
                assert DocumentationBackendHandler.last_query == (
                    "(topic) file:(^|/)readme"
                )

            asyncio.run(
                with_client(
                    primary_url,
                    run,
                    file_roles_path=roles,
                )
            )
    finally:
        primary.shutdown()


def test_list_is_proxied_without_search_cache() -> None:
    server, url = backend_server()
    try:
        async def run(client: httpx.AsyncClient) -> None:
            first = await client.post("/api/list", json={"Q": "repo:mathlib4"})
            second = await client.post("/api/list", json={"Q": "repo:mathlib4"})
            assert first.status_code == second.status_code == 200
            assert BackendHandler.list_calls == 2
        asyncio.run(with_client(url, run))
    finally:
        server.shutdown()


def test_openapi_is_generated_from_pydantic_models() -> None:
    server, url = backend_server()
    try:
        async def run(client: httpx.AsyncClient) -> None:
            response = await client.get("/api/openapi.json")
            assert response.status_code == 200
            document = response.json()
            assert document["openapi"].startswith("3.1.")
            assert document["security"] == []
            assert document["paths"]["/api/search"]["post"]["operationId"] == "searchCorpus"
            assert (
                document["paths"]["/api/search/batch"]["post"]["operationId"]
                == "searchCorpusBatch"
            )
            assert document["paths"]["/api/list"]["post"]["operationId"] == "listSources"
            assert "SearchRequest" in document["components"]["schemas"]
            assert "SearchResponse" in document["components"]["schemas"]
            assert "BatchSearchRequest" in document["components"]["schemas"]
            assert "BatchSearchResponse" in document["components"]["schemas"]
        asyncio.run(with_client(url, run))
    finally:
        server.shutdown()


def test_validation_errors_keep_public_error_shape() -> None:
    server, url = backend_server()
    try:
        async def run(client: httpx.AsyncClient) -> None:
            response = await client.post("/api/search", json={"Q": ""})
            assert response.status_code == 400
            assert set(response.json()) == {"Error"}
        asyncio.run(with_client(url, run))
    finally:
        server.shutdown()


def test_batch_search_preserves_order_and_reuses_cache() -> None:
    server, url = backend_server()
    try:
        async def run(client: httpx.AsyncClient) -> None:
            payload = {
                "Searches": [
                    {"ID": "first", "Request": {"Q": "quasicategory"}},
                    {"ID": "second", "Request": {"Q": "inner fibration"}},
                    {"ID": "repeat", "Request": {"Q": "quasicategory"}},
                ],
                "MaxConcurrency": 3,
            }
            first = await client.post("/api/search/batch", json=payload)
            assert first.status_code == 200
            results = first.json()["Results"]
            assert [item["ID"] for item in results] == ["first", "second", "repeat"]
            assert [item["StatusCode"] for item in results] == [200, 200, 200]
            assert results[0]["Result"]["Echo"]["Q"] == "quasicategory"
            assert results[1]["Result"]["Echo"]["Q"] == "inner fibration"
            assert results[2]["Result"]["Echo"]["Q"] == "quasicategory"
            assert BackendHandler.search_calls == 2
            assert results[0]["Cache"] == "MISS"
            assert results[1]["Cache"] == "MISS"
            assert results[2]["Cache"] in {"COALESCED", "HIT"}

            second = await client.post("/api/search/batch", json=payload)
            assert second.status_code == 200
            second_results = second.json()["Results"]
            assert all(item["Cache"] == "HIT" for item in second_results)
            assert BackendHandler.search_calls == 2

        asyncio.run(with_client(url, run))
    finally:
        server.shutdown()


def test_batch_search_reports_backend_errors_per_query() -> None:
    class SelectiveErrorHandler(BackendHandler):
        def do_POST(self) -> None:  # noqa: N802
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size))
            if self.path != "/api/search":
                self.send_response(404)
                self.end_headers()
                return
            if body.get("Q") == "bad query":
                encoded = json.dumps({"Error": "invalid query syntax"}).encode()
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
                return
            encoded = json.dumps(
                {
                    "Result": {
                        "Files": [],
                        "FileCount": 0,
                        "MatchCount": 0,
                        "Echo": body,
                    }
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), SelectiveErrorHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    url = f"http://{host}:{port}"
    try:
        async def run(client: httpx.AsyncClient) -> None:
            response = await client.post(
                "/api/search/batch",
                json={
                    "Searches": [
                        {"ID": "good", "Request": {"Q": "theorem"}},
                        {"ID": "bad", "Request": {"Q": "bad query"}},
                    ]
                },
            )
            assert response.status_code == 200
            good, bad = response.json()["Results"]
            assert good["ID"] == "good"
            assert good["StatusCode"] == 200
            assert good["Result"]["Echo"]["Q"] == "theorem"
            assert good["Error"] is None
            assert bad == {
                "ID": "bad",
                "StatusCode": 400,
                "Cache": None,
                "Result": None,
                "Error": "invalid query syntax",
            }

        asyncio.run(with_client(url, run))
    finally:
        server.shutdown()


def test_no_hit_backend_null_files_is_normalized_for_search_and_batch() -> None:
    class NoHitBackendHandler(BackendHandler):
        def do_POST(self) -> None:  # noqa: N802
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size))
            if self.path != "/api/search":
                self.send_response(404)
                self.end_headers()
                return
            encoded = json.dumps(
                {
                    "Result": {
                        "Files": None,
                        "FileCount": 0,
                        "MatchCount": 0,
                        "Echo": body,
                    }
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), NoHitBackendHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    url = f"http://{host}:{port}"
    try:
        async def run(client: httpx.AsyncClient) -> None:
            single = await client.post("/api/search", json={"Q": "no such mathematics"})
            assert single.status_code == 200
            assert single.json()["Result"]["Files"] == []

            batch = await client.post(
                "/api/search/batch",
                json={
                    "Searches": [
                        {"ID": "none", "Request": {"Q": "still no such mathematics"}}
                    ]
                },
            )
            assert batch.status_code == 200
            item = batch.json()["Results"][0]
            assert item["StatusCode"] == 200
            assert item["Result"]["Files"] == []
            assert item["Error"] is None

        asyncio.run(with_client(url, run))
    finally:
        server.shutdown()


def test_exact_duplicate_hits_are_collapsed_with_alias_provenance() -> None:
    class DuplicateBackendHandler(BackendHandler):
        def do_POST(self) -> None:  # noqa: N802
            size = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(size)
            payload = {
                "Result": {
                    "Files": [
                        {"FileName": "A.lean", "Repository": "repo-a", "ChunkMatches": []},
                        {"FileName": "B.lean", "Repository": "repo-b", "ChunkMatches": []},
                        {"FileName": "C.lean", "Repository": "repo-c", "ChunkMatches": []},
                    ],
                    "FileCount": 3,
                    "MatchCount": 3,
                }
            }
            encoded = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), DuplicateBackendHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    url = f"http://{host}:{port}"
    try:
        with tempfile.TemporaryDirectory() as directory:
            aliases = pathlib.Path(directory) / "aliases.json"
            aliases.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "groups": [
                            {
                                "sha256": "a" * 64,
                                "occurrences": [
                                    {"repository": "repo-a", "file": "A.lean"},
                                    {"repository": "repo-b", "file": "B.lean"},
                                ],
                            }
                        ],
                    }
                )
            )

            async def run(client: httpx.AsyncClient) -> None:
                response = await client.post("/api/search", json={"Q": "theorem"})
                assert response.status_code == 200
                result = response.json()["Result"]
                assert [(f["Repository"], f["FileName"]) for f in result["Files"]] == [
                    ("repo-a", "A.lean"),
                    ("repo-c", "C.lean"),
                ]
                assert result["DuplicateFilesCollapsed"] == 1
                assert result["DistinctFilesReturned"] == 2
                assert result["Files"][0]["ExactDuplicateAliases"] == [
                    {"Repository": "repo-b", "FileName": "B.lean"}
                ]

            asyncio.run(with_client(url, run, duplicate_aliases_path=aliases))
    finally:
        server.shutdown()


def test_import_only_navigation_hits_are_retained_but_demoted() -> None:
    class RoleBackendHandler(BackendHandler):
        def do_POST(self) -> None:  # noqa: N802
            size = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(size)
            payload = {
                "Result": {
                    "Files": [
                        {"FileName": "Index.lean", "Repository": "repo", "Score": 30},
                        {"FileName": "Owner.lean", "Repository": "repo", "Score": 20},
                        {"FileName": "Other.lean", "Repository": "other", "Score": 10},
                    ],
                    "FileCount": 3,
                }
            }
            encoded = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), RoleBackendHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    url = f"http://{host}:{port}"
    try:
        with tempfile.TemporaryDirectory() as directory:
            roles = pathlib.Path(directory) / "filter-state.jsonl"
            roles.write_text(
                json.dumps(
                    {
                        "decision_id": "FD-016",
                        "primary": "retain",
                        "repository": "repo",
                        "file": "Index.lean",
                    }
                )
                + "\n"
            )

            async def run(client: httpx.AsyncClient) -> None:
                response = await client.post("/api/search", json={"Q": "topic"})
                assert response.status_code == 200
                result = response.json()["Result"]
                assert [(f["Repository"], f["FileName"]) for f in result["Files"]] == [
                    ("repo", "Owner.lean"),
                    ("other", "Other.lean"),
                    ("repo", "Index.lean"),
                ]
                assert result["Files"][-1]["FileRole"] == "navigation-import-only"
                assert result["NavigationFilesDemoted"] == 1
                assert result["RoleFilesDemoted"] == 1
                assert result["RoleCounts"] == {"navigation-import-only": 1}
                assert result["RoleRerankingApplied"] is True
                assert result["FileCount"] == 3

            asyncio.run(with_client(url, run, file_roles_path=roles))
    finally:
        server.shutdown()


def test_distinct_retained_metadata_roles_are_stably_demoted() -> None:
    class RoleBackendHandler(BackendHandler):
        def do_POST(self) -> None:  # noqa: N802
            size = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(size)
            payload = {
                "Result": {
                    "Files": [
                        {"FileName": "report@useless-runes.lsp", "Repository": "acl2", "Score": 40},
                        {"FileName": "Index.lean", "Repository": "lean", "Score": 30},
                        {"FileName": "Owner.lisp", "Repository": "acl2", "Score": 20},
                        {"FileName": "Other.lean", "Repository": "lean", "Score": 10},
                    ],
                    "FileCount": 4,
                }
            }
            encoded = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), RoleBackendHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    url = f"http://{host}:{port}"
    try:
        with tempfile.TemporaryDirectory() as directory:
            roles = pathlib.Path(directory) / "filter-state.jsonl"
            roles.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in (
                        {"decision_id": "FD-016", "primary": "retain", "repository": "lean", "file": "Index.lean"},
                        {"decision_id": "FD-017", "primary": "retain", "repository": "acl2", "file": "report@useless-runes.lsp"},
                    )
                )
                + "\n"
            )

            async def run(client: httpx.AsyncClient) -> None:
                response = await client.post("/api/search", json={"Q": "topic"})
                assert response.status_code == 200
                result = response.json()["Result"]
                assert [(f["Repository"], f["FileName"]) for f in result["Files"]] == [
                    ("acl2", "Owner.lisp"),
                    ("lean", "Other.lean"),
                    ("lean", "Index.lean"),
                    ("acl2", "report@useless-runes.lsp"),
                ]
                assert result["Files"][-2]["FileRole"] == "navigation-import-only"
                assert result["Files"][-1]["FileRole"] == "proof-metadata-useless-runes"
                assert result["RoleFilesDemoted"] == 2
                assert result["RoleCounts"] == {
                    "navigation-import-only": 1,
                    "proof-metadata-useless-runes": 1,
                }

            asyncio.run(with_client(url, run, file_roles_path=roles))
    finally:
        server.shutdown()


def git(*args: str, cwd: pathlib.Path | None = None) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def source_lead_remote(root: pathlib.Path) -> pathlib.Path:
    remote = root / "remote.git"
    seed = root / "seed"
    git("init", "-q", "--bare", str(remote))
    git("init", "-q", str(seed))
    (seed / "README.md").write_text("test repository\n")
    git("add", "README.md", cwd=seed)
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "-q",
        "-m",
        "initial",
        cwd=seed,
    )
    git("branch", "-M", "main", cwd=seed)
    git("remote", "add", "origin", str(remote), cwd=seed)
    git("push", "-q", "origin", "main", cwd=seed)
    return remote


def test_source_lead_is_transported_without_changing_main() -> None:
    backend, backend_url = backend_server()
    try:
        with tempfile.TemporaryDirectory() as directory:
            remote = source_lead_remote(pathlib.Path(directory))
            main_before = git("--git-dir", str(remote), "rev-parse", "refs/heads/main")

            app = create_app(
                backend_url=backend_url,
                source_lead_remote=str(remote),
            )

            async def run() -> None:
                async with app.router.lifespan_context(app):
                    transport = httpx.ASGITransport(app=app)
                    async with httpx.AsyncClient(
                        transport=transport, base_url="http://testserver"
                    ) as client:
                        response = await client.post(
                            "/api/submit/source",
                            json={
                                "url": "https://github.com/example/formal-proof",
                                "notes": "May contain a formalization of the main theorem.",
                            },
                        )
                        assert response.status_code == 202
                        assert "source+lead" in response.json()["queue_url"]

            asyncio.run(run())

            main_after = git("--git-dir", str(remote), "rev-parse", "refs/heads/main")
            assert main_after == main_before
            refs = git(
                "--git-dir",
                str(remote),
                "for-each-ref",
                "--format=%(refname)",
                "refs/heads/source-lead/",
            ).splitlines()
            assert len(refs) == 1
            payload = json.loads(
                git("--git-dir", str(remote), "show", f"{refs[0]}:.source-lead.json")
            )
            assert payload == {
                "url": "https://github.com/example/formal-proof",
                "notes": "May contain a formalization of the main theorem.",
            }
    finally:
        backend.shutdown()


def test_source_lead_validation_and_openapi_boundary() -> None:
    server, url = backend_server()
    try:
        async def run(client: httpx.AsyncClient) -> None:
            invalid = await client.post(
                "/api/submit/source", json={"url": "not a URL"}
            )
            assert invalid.status_code == 400
            assert set(invalid.json()) == {"Error"}

            openapi = await client.get("/api/openapi.json")
            assert "/api/submit/source" not in openapi.json()["paths"]

        asyncio.run(with_client(url, run))
    finally:
        server.shutdown()
