from __future__ import annotations

import asyncio
import hashlib
import json
import os
import pathlib
import subprocess
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.openapi.utils import get_openapi

from .cache import ByteLRUTTLCache, SingleFlight
from .duplicates import DuplicateAliasIndex
from .roles import FileRoleIndex
from .models import (
    BatchSearchItemResponse,
    BatchSearchRequest,
    BatchSearchResponse,
    ErrorResponse,
    ListRequest,
    ListResponse,
    SearchRequest,
    SearchResponse,
    SourceLeadRequest,
    SourceLeadResponse,
)

DEFAULT_BACKEND_URL = "http://127.0.0.1:6071"
DEFAULT_DUPLICATE_ALIASES_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "data" / "duplicate-aliases.json"
)
DEFAULT_FILE_ROLES_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "data" / "filter-state.jsonl"
)
CACHE_TTL_SECONDS = 300.0
CACHE_MAX_BYTES = 64 * 1024 * 1024
CACHE_MAX_ENTRY_BYTES = 8 * 1024 * 1024
CACHE_MAX_ENTRIES = 256
BATCH_GLOBAL_CONCURRENCY = 32
DEFAULT_SOURCE_LEAD_REMOTE = "git@github.com:dzackgarza/formalization-corpus.git"
DEFAULT_SOURCE_LEAD_BASE_BRANCH = "main"
SOURCE_LEAD_QUEUE_URL = (
    "https://github.com/dzackgarza/formalization-corpus/issues"
    '?q=is%3Aissue+label%3A%22source+lead%22'
)
GIT_LOCAL_ENV_VARS = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
}


def _isolated_git_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in GIT_LOCAL_ENV_VARS:
        env.pop(name, None)
    return env


class BackendError(RuntimeError):
    def __init__(self, status_code: int, body: bytes) -> None:
        super().__init__(f"search backend returned HTTP {status_code}")
        self.status_code = status_code
        self.body = body


class SourceLeadError(RuntimeError):
    pass


class SourceLeadDispatcher:
    def __init__(
        self, remote: str, *, base_branch: str = DEFAULT_SOURCE_LEAD_BASE_BRANCH
    ) -> None:
        self.remote = remote
        self.base_branch = base_branch

    async def submit(self, lead: SourceLeadRequest) -> None:
        await asyncio.to_thread(self._submit_sync, lead)

    def _git(
        self,
        cwd: str,
        *args: str,
        input_text: str | None = None,
    ) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=_isolated_git_env(),
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=30,
        )
        return result.stdout.strip()

    def _submit_sync(self, lead: SourceLeadRequest) -> None:
        payload = json.dumps(
            {"url": str(lead.url), "notes": lead.notes.strip()},
            ensure_ascii=False,
            separators=(",", ":"),
        ) + "\n"
        with tempfile.TemporaryDirectory(prefix="formalization-source-lead-") as directory:
            self._git(directory, "init", "-q")
            self._git(directory, "remote", "add", "origin", self.remote)
            self._git(
                directory,
                "fetch",
                "-q",
                "--depth=1",
                "--filter=blob:none",
                "origin",
                self.base_branch,
            )
            base = self._git(directory, "rev-parse", "FETCH_HEAD")
            self._git(directory, "read-tree", base)
            blob = self._git(directory, "hash-object", "-w", "--stdin", input_text=payload)
            self._git(
                directory,
                "update-index",
                "--add",
                "--cacheinfo",
                f"100644,{blob},.source-lead.json",
            )
            tree = self._git(directory, "write-tree")
            commit = self._git(
                directory,
                "-c",
                "user.name=Formalization Corpus",
                "-c",
                "user.email=source-leads@users.noreply.github.com",
                "commit-tree",
                tree,
                "-p",
                base,
                input_text="Queue anonymous source lead\n",
            )
            branch = f"source-lead/{uuid4().hex}"
            self._git(directory, "push", "-q", "origin", f"{commit}:refs/heads/{branch}")


class SearchProxy:
    def __init__(
        self,
        client: httpx.AsyncClient,
        duplicate_aliases: DuplicateAliasIndex,
        file_roles: FileRoleIndex,
    ) -> None:
        self.client = client
        self.duplicate_aliases = duplicate_aliases
        self.file_roles = file_roles
        self.cache = ByteLRUTTLCache(
            ttl_seconds=CACHE_TTL_SECONDS,
            max_bytes=CACHE_MAX_BYTES,
            max_entry_bytes=CACHE_MAX_ENTRY_BYTES,
            max_entries=CACHE_MAX_ENTRIES,
        )
        self.singleflight = SingleFlight()
        self.batch_slots = asyncio.Semaphore(BATCH_GLOBAL_CONCURRENCY)

    async def search(self, payload: dict[str, Any]) -> tuple[bytes, str]:
        normalized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        key = hashlib.sha256(normalized).hexdigest()

        cached = await self.cache.get(key)
        if cached is not None:
            return cached, "HIT"

        async def produce() -> bytes:
            # A previous leader may have filled the cache while this coroutine was
            # waiting to become the single-flight producer.
            cached_again = await self.cache.get(key)
            if cached_again is not None:
                return cached_again
            body = await self._post("/api/search", payload)
            body = self.duplicate_aliases.collapse_response(body)
            body = self.file_roles.rerank_response(body)
            body = self._normalize_search_response(body)
            await self.cache.put(key, body)
            return body

        body, leader = await self.singleflight.run(key, produce)
        return body, "MISS" if leader else "COALESCED"

    @staticmethod
    def _normalize_search_response(body: bytes) -> bytes:
        """Normalize backend no-hit responses to the public response schema."""

        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return body
        if not isinstance(payload, dict):
            return body
        result = payload.get("Result")
        if isinstance(result, dict) and result.get("Files") is None:
            result["Files"] = []
            return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        return body

    async def list_sources(self, payload: dict[str, Any]) -> bytes:
        return await self._post("/api/list", payload)

    async def batch_search(
        self,
        items: list[tuple[str, dict[str, Any]]],
        *,
        max_concurrency: int,
    ) -> list[BatchSearchItemResponse]:
        local_slots = asyncio.Semaphore(max_concurrency)

        async def run(item_id: str, payload: dict[str, Any]) -> BatchSearchItemResponse:
            async with local_slots, self.batch_slots:
                try:
                    body, cache_status = await self.search(payload)
                except BackendError as exc:
                    try:
                        error_body = json.loads(exc.body)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        message = exc.body.decode("utf-8", "replace")
                    else:
                        message = (
                            error_body.get("Error", "search backend rejected the query")
                            if isinstance(error_body, dict)
                            else "search backend rejected the query"
                        )
                    return BatchSearchItemResponse(
                        ID=item_id,
                        StatusCode=exc.status_code,
                        Error=message,
                    )

                response = SearchResponse.model_validate_json(body)
                return BatchSearchItemResponse(
                    ID=item_id,
                    StatusCode=200,
                    Cache=cache_status,
                    Result=response.Result,
                )

        return list(
            await asyncio.gather(
                *(run(item_id, payload) for item_id, payload in items)
            )
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> bytes:
        try:
            response = await self.client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise BackendError(502, b'{"Error":"search backend unavailable"}') from exc
        if response.status_code >= 400:
            raise BackendError(response.status_code, response.content)
        return response.content


API_DESCRIPTION = (
    "Public, read-only search API for the Formalization Corpus. "
    "No authentication is required."
)


def create_app(
    *,
    backend_url: str | None = None,
    duplicate_aliases_path: str | pathlib.Path | None = None,
    file_roles_path: str | pathlib.Path | None = None,
    source_lead_remote: str | None = None,
    source_lead_base_branch: str = DEFAULT_SOURCE_LEAD_BASE_BRANCH,
) -> FastAPI:
    backend = backend_url or os.environ.get("ZOEKT_BACKEND_URL", DEFAULT_BACKEND_URL)
    aliases_value = duplicate_aliases_path or os.environ.get("DUPLICATE_ALIASES_PATH")
    aliases_path = pathlib.Path(aliases_value) if aliases_value else DEFAULT_DUPLICATE_ALIASES_PATH
    roles_value = file_roles_path or os.environ.get("FILE_ROLES_PATH")
    roles_path = pathlib.Path(roles_value) if roles_value else DEFAULT_FILE_ROLES_PATH

    lead_remote = source_lead_remote or os.environ.get(
        "SOURCE_LEAD_GIT_REMOTE", DEFAULT_SOURCE_LEAD_REMOTE
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = httpx.AsyncClient(base_url=backend, timeout=60.0)
        duplicate_aliases = DuplicateAliasIndex.from_path(aliases_path)
        file_roles = FileRoleIndex.from_path(roles_path)
        app.state.proxy = SearchProxy(client, duplicate_aliases, file_roles)
        app.state.source_leads = SourceLeadDispatcher(
            lead_remote, base_branch=source_lead_base_branch
        )
        try:
            yield
        finally:
            await client.aclose()

    app = FastAPI(
        title="Formalization Corpus API",
        version="1.1.0",
        description=API_DESCRIPTION,
        openapi_url="/api/openapi.json",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
        servers=[
            {
                "url": "https://formalization-corpus.dzackgarza.com",
                "description": "Production",
            }
        ],
        openapi_tags=[
            {
                "name": "Search",
                "description": "Search source text in the corpus.",
            },
            {
                "name": "Sources",
                "description": "List source metadata from the live index.",
            },
        ],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "HEAD", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Cache"],
        max_age=86400,
    )

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
                servers=app.servers,
            )
            # The API is intentionally public and has no authentication scheme.
            schema["security"] = []
            schema["externalDocs"] = {
                "description": "Formalization Corpus",
                "url": "https://dzackgarza.github.io/formalization-corpus/",
            }
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        message = "; ".join(error["msg"] for error in exc.errors())
        return JSONResponse(status_code=400, content={"Error": message})

    @app.post(
        "/api/search",
        operation_id="searchCorpus",
        summary="Search the corpus",
        response_model=None,
        responses={
            200: {
                "model": SearchResponse,
                "description": "Search results grouped by file.",
                "headers": {
                    "X-Cache": {
                        "description": "Search-cache result: HIT, MISS, or COALESCED.",
                        "schema": {
                            "type": "string",
                            "enum": ["HIT", "MISS", "COALESCED"],
                        },
                    }
                },
            },
            400: {"model": ErrorResponse, "description": "Invalid search request."},
            502: {"model": ErrorResponse, "description": "Search backend unavailable."},
        },
        tags=["Search"],
    )
    async def search(request: SearchRequest, raw_request: Request) -> Response:
        proxy: SearchProxy = raw_request.app.state.proxy
        payload = request.model_dump(by_alias=True, exclude_none=True)
        try:
            body, cache_status = await proxy.search(payload)
        except BackendError as exc:
            return Response(
                content=exc.body,
                status_code=exc.status_code,
                media_type="application/json",
            )
        return Response(
            content=body,
            media_type="application/json",
            headers={"X-Cache": cache_status},
        )

    @app.post(
        "/api/search/batch",
        operation_id="searchCorpusBatch",
        summary="Search the corpus in bulk",
        response_model=BatchSearchResponse,
        responses={
            200: {
                "model": BatchSearchResponse,
                "description": (
                    "Per-query search results in input order. Backend errors are "
                    "reported on the affected item without failing the whole batch."
                ),
            },
            400: {"model": ErrorResponse, "description": "Invalid batch request."},
        },
        tags=["Search"],
    )
    async def batch_search(
        request: BatchSearchRequest,
        raw_request: Request,
    ) -> BatchSearchResponse:
        proxy: SearchProxy = raw_request.app.state.proxy
        items = [
            (
                item.ID,
                item.Request.model_dump(by_alias=True, exclude_none=True),
            )
            for item in request.Searches
        ]
        results = await proxy.batch_search(
            items,
            max_concurrency=request.MaxConcurrency,
        )
        return BatchSearchResponse(Results=results)

    @app.post(
        "/api/submit/source",
        response_model=SourceLeadResponse,
        status_code=202,
        include_in_schema=False,
    )
    async def submit_source_lead(
        lead: SourceLeadRequest, raw_request: Request
    ) -> SourceLeadResponse | JSONResponse:
        dispatcher: SourceLeadDispatcher = raw_request.app.state.source_leads
        try:
            await dispatcher.submit(lead)
        except (subprocess.SubprocessError, OSError, SourceLeadError):
            return JSONResponse(
                status_code=502,
                content={"Error": "could not submit the source lead"},
            )
        return SourceLeadResponse(queue_url=SOURCE_LEAD_QUEUE_URL)

    @app.post(
        "/api/list",
        operation_id="listSources",
        summary="List sources",
        response_model=None,
        responses={
            200: {
                "model": ListResponse,
                "description": "Matching source metadata and index statistics.",
            },
            400: {"model": ErrorResponse, "description": "Invalid source query."},
            502: {"model": ErrorResponse, "description": "Search backend unavailable."},
        },
        tags=["Sources"],
    )
    async def list_sources(request: ListRequest, raw_request: Request) -> Response:
        proxy: SearchProxy = raw_request.app.state.proxy
        payload = request.model_dump(by_alias=True, exclude_none=True)
        try:
            body = await proxy.list_sources(payload)
        except BackendError as exc:
            return Response(
                content=exc.body,
                status_code=exc.status_code,
                media_type="application/json",
            )
        return Response(content=body, media_type="application/json")

    return app


app = create_app()
