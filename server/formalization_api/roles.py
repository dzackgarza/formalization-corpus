from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any


NAVIGATION_DECISION_IDS = frozenset({"FD-016"})
NAVIGATION_ROLE = "navigation-import-only"


class FileRoleIndex:
    """Search-result roles derived from durable filtering decisions.

    FD-016 files remain ordinary indexed documents.  The role index changes only
    presentation order: non-navigation hits stay in Zoekt order and verified
    import-only navigation hits follow them, also in Zoekt order.
    """

    def __init__(self, navigation: set[tuple[str, str]]) -> None:
        self._navigation = frozenset(navigation)

    @classmethod
    def empty(cls) -> "FileRoleIndex":
        return cls(set())

    @classmethod
    def from_path(cls, path: pathlib.Path | None) -> "FileRoleIndex":
        if path is None or not path.is_file():
            return cls.empty()
        navigation: set[tuple[str, str]] = set()
        with path.open() as handle:
            for number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("decision_id") not in NAVIGATION_DECISION_IDS:
                    continue
                if row.get("primary") != "retain":
                    raise ValueError(
                        f"navigation role at {path}:{number} is not primary-retained"
                    )
                navigation.add((str(row["repository"]), str(row["file"])))
        return cls(navigation)

    @property
    def navigation_count(self) -> int:
        return len(self._navigation)

    def is_navigation(self, repository: str, file_name: str) -> bool:
        return (repository, file_name) in self._navigation

    def fingerprint(self) -> dict[str, Any]:
        digest = hashlib.sha256()
        for repository, file_name in sorted(self._navigation):
            digest.update(repository.encode())
            digest.update(b"\0")
            digest.update(file_name.encode())
            digest.update(b"\n")
        return {
            "navigation_count": len(self._navigation),
            "navigation_sha256": digest.hexdigest(),
        }

    def rerank_files(self, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self._navigation or not files:
            return files
        ordinary: list[dict[str, Any]] = []
        navigation: list[dict[str, Any]] = []
        for file_match in files:
            key = (
                str(file_match.get("Repository", "")),
                str(file_match.get("FileName", "")),
            )
            if key not in self._navigation:
                ordinary.append(file_match)
                continue
            enriched = dict(file_match)
            enriched["FileRole"] = NAVIGATION_ROLE
            navigation.append(enriched)
        return ordinary + navigation

    def rerank_response(self, body: bytes) -> bytes:
        if not self._navigation:
            return body
        payload: dict[str, Any] = json.loads(body)
        result = payload.get("Result")
        if not isinstance(result, dict):
            return body
        files = result.get("Files")
        if not isinstance(files, list):
            return body
        reranked = self.rerank_files(files)
        demoted = sum(
            1
            for item in reranked
            if isinstance(item, dict) and item.get("FileRole") == NAVIGATION_ROLE
        )
        if demoted == 0:
            return body
        result["Files"] = reranked
        result["NavigationFilesDemoted"] = demoted
        result["RoleRerankingApplied"] = True
        return (json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
