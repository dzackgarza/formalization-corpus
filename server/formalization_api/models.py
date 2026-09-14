from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class APIModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class SearchOptions(APIModel):
    EstimateDocCount: bool | None = Field(
        default=None,
        description="Return an upper-bound estimate of eligible files.",
    )
    Whole: bool | None = Field(
        default=None,
        description="Include the complete matching file as base64 in Files[].Content.",
    )
    ShardMaxMatchCount: int | None = None
    TotalMaxMatchCount: int | None = None
    ShardRepoMaxMatchCount: int | None = None
    MaxWallTime: int | None = Field(
        default=None,
        description="Maximum search time in nanoseconds.",
    )
    FlushWallTime: int | None = None
    SchedulingClass: int | None = None
    MaxDocDisplayCount: int | None = Field(
        default=None,
        ge=0,
        description="Maximum number of matching files returned.",
    )
    MaxMatchDisplayCount: int | None = Field(
        default=None,
        ge=0,
        description="Maximum number of displayed matches.",
    )
    NumContextLines: int | None = Field(
        default=None,
        ge=0,
        description="Context lines before and after each match.",
    )
    ChunkMatches: bool | None = Field(
        default=None,
        description="Return contiguous matching chunks instead of legacy line matches.",
    )
    UseBM25Scoring: bool | None = None
    DebugScore: bool | None = None


class SearchRequest(APIModel):
    Q: str = Field(
        min_length=1,
        description=(
            "Zoekt query. Bare terms match substrings; whitespace combines terms, "
            "`or` forms alternatives, and `-` negates. Filters include `repo:`, "
            "`file:`, `content:`, `regex:`, and `case:`."
        ),
        examples=["content:Hasse file:\\.lean$"],
    )
    RepoIDs: list[int] | None = Field(
        default=None,
        description="Optional Sourcegraph repository IDs to intersect with the query.",
    )
    Opts: SearchOptions | None = Field(
        default=None,
        description="Search result and resource-limit options.",
    )


class Location(APIModel):
    ByteOffset: int
    LineNumber: int
    Column: int


class MatchRange(APIModel):
    Start: Location
    End: Location


class ChunkMatch(APIModel):
    DebugScore: str | None = None
    Content: str | None = Field(
        default=None,
        description="Base64-encoded matching lines.",
    )
    Ranges: list[MatchRange] | None = None
    SymbolInfo: list[dict[str, Any] | None] | None = None
    FileName: bool | None = None
    ContentStart: Location | None = None
    Score: float | None = None
    BestLineMatch: int | None = None


class FileMatch(APIModel):
    FileName: str
    Repository: str
    Language: str | None = None
    ChunkMatches: list[ChunkMatch] | None = None
    LineMatches: list[dict[str, Any]] | None = None
    Content: str | None = Field(
        default=None,
        description="Base64-encoded complete file when Opts.Whole is true.",
    )
    Checksum: str | None = None
    Score: float | None = None
    FileRole: str | None = Field(
        default=None,
        description="Result-layer role for retained lower-priority navigation or proof metadata.",
    )
    ExactDuplicateAliases: list["FileAlias"] | None = Field(
        default=None,
        description=(
            "Other corpus source/path occurrences with byte-identical formal source. "
            "They are aliases/provenance for this returned hit, not additional ranked results."
        ),
    )


class FileAlias(APIModel):
    Repository: str
    FileName: str


class SearchResult(APIModel):
    Files: list[FileMatch] = Field(default_factory=list)
    FileCount: int | None = None
    MatchCount: int | None = None
    Duration: int | None = Field(
        default=None,
        description="Search wall time in nanoseconds.",
    )
    FilesConsidered: int | None = None
    FilesLoaded: int | None = None
    FilesSkipped: int | None = None
    ShardsScanned: int | None = None
    DuplicateFilesCollapsed: int | None = Field(
        default=None,
        description="Number of byte-identical returned file hits collapsed into earlier ranked hits.",
    )
    DistinctFilesReturned: int | None = Field(
        default=None,
        description="Number of file hits remaining after exact-duplicate collapse.",
    )
    NavigationFilesDemoted: int | None = Field(
        default=None,
        description="Number of retained import-only navigation hits placed after ordinary hits.",
    )
    RoleFilesDemoted: int | None = Field(
        default=None,
        description="Number of retained role-bearing hits placed after ordinary formal-content hits.",
    )
    RoleCounts: dict[str, int] | None = Field(
        default=None,
        description="Counts of returned lower-priority file roles when role ranking is applied.",
    )
    RoleRerankingApplied: bool | None = None
    DocumentationFilesReturned: int | None = Field(
        default=None,
        description="Number of FD-002 README/source-documentation files returned by the auxiliary channel.",
    )
    AuxiliaryChannel: str | None = None


class SearchResponse(APIModel):
    Result: SearchResult


class BatchSearchItem(APIModel):
    ID: str = Field(
        min_length=1,
        max_length=200,
        description="Caller-supplied identifier returned unchanged with this query's result.",
    )
    Request: SearchRequest


class BatchSearchRequest(APIModel):
    Searches: list[BatchSearchItem] = Field(
        min_length=1,
        max_length=512,
        description="Independent corpus searches evaluated concurrently and returned in input order.",
    )
    MaxConcurrency: int = Field(
        default=16,
        ge=1,
        le=32,
        description="Maximum searches from this batch allowed to execute concurrently.",
    )


class BatchSearchItemResponse(APIModel):
    ID: str
    StatusCode: int
    Cache: str | None = Field(
        default=None,
        description="Per-query cache result when the search succeeded.",
    )
    Result: SearchResult | None = None
    Error: str | None = None


class BatchSearchResponse(APIModel):
    Results: list[BatchSearchItemResponse]


class ListOptions(APIModel):
    Field: int | None = None


class ListRequest(APIModel):
    Q: str = Field(
        default="",
        description="Repository query. Empty lists every source in the live index.",
        examples=["repo:mathlib4"],
    )
    Opts: ListOptions | None = None


class RepositoryInfo(APIModel):
    Name: str
    URL: str | None = None
    Source: str | None = None


class RepoStats(APIModel):
    Repos: int | None = None
    Shards: int | None = None
    Documents: int | None = None
    IndexBytes: int | None = None
    ContentBytes: int | None = None
    NewLinesCount: int | None = None


class RepoListEntry(APIModel):
    Repository: RepositoryInfo
    IndexMetadata: dict[str, Any] | None = None
    Stats: RepoStats | None = None


class RepoList(APIModel):
    Repos: list[RepoListEntry] | None = None
    ReposMap: dict[str, Any] | None = None
    Crashes: int | None = None
    Stats: RepoStats | None = None


class ListResponse(APIModel):
    List: RepoList


class ErrorResponse(APIModel):
    Error: str


class SourceLeadRequest(BaseModel):
    url: HttpUrl = Field(description="URL supplied as an unreviewed source lead.")
    notes: str = Field(default="", max_length=4000)


class SourceLeadResponse(BaseModel):
    queue_url: str
