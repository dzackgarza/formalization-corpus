from __future__ import annotations

import json
import pathlib
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


async def with_client(url: str, callback, *, duplicate_aliases_path=None) -> None:
    app = create_app(backend_url=url, duplicate_aliases_path=duplicate_aliases_path)
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
                "Opts": {"MaxDocDisplayCount": 5, "ChunkMatches": True},
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
            assert document["paths"]["/api/list"]["post"]["operationId"] == "listSources"
            assert "SearchRequest" in document["components"]["schemas"]
            assert "SearchResponse" in document["components"]["schemas"]
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
