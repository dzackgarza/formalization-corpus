from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    sha256: str
    occurrences: tuple[tuple[str, str], ...]


class DuplicateAliasIndex:
    """Exact-content duplicate aliases keyed by (repository, file path)."""

    def __init__(self, groups: list[DuplicateGroup]) -> None:
        self._by_occurrence: dict[tuple[str, str], DuplicateGroup] = {}
        for group in groups:
            for occurrence in group.occurrences:
                if occurrence in self._by_occurrence:
                    raise ValueError(f"duplicate occurrence belongs to multiple groups: {occurrence}")
                self._by_occurrence[occurrence] = group

    @classmethod
    def empty(cls) -> "DuplicateAliasIndex":
        return cls([])

    @classmethod
    def from_path(cls, path: pathlib.Path | None) -> "DuplicateAliasIndex":
        if path is None or not path.is_file():
            return cls.empty()
        data = json.loads(path.read_text())
        if data.get("schema_version") != 1:
            raise ValueError(f"unsupported duplicate alias map: {path}")
        groups: list[DuplicateGroup] = []
        for raw in data.get("groups") or []:
            occurrences = tuple(
                (str(item["repository"]), str(item["file"]))
                for item in raw.get("occurrences") or []
            )
            if len(occurrences) < 2:
                continue
            groups.append(DuplicateGroup(sha256=str(raw["sha256"]), occurrences=occurrences))
        return cls(groups)

    @property
    def occurrence_count(self) -> int:
        return len(self._by_occurrence)

    def collapse_response(self, body: bytes) -> bytes:
        if not self._by_occurrence:
            return body
        payload: dict[str, Any] = json.loads(body)
        result = payload.get("Result")
        if not isinstance(result, dict):
            return body
        files = result.get("Files")
        if not isinstance(files, list):
            return body

        seen_groups: set[str] = set()
        collapsed = 0
        output: list[dict[str, Any]] = []
        for file_match in files:
            if not isinstance(file_match, dict):
                output.append(file_match)
                continue
            key = (str(file_match.get("Repository", "")), str(file_match.get("FileName", "")))
            group = self._by_occurrence.get(key)
            if group is None:
                output.append(file_match)
                continue
            if group.sha256 in seen_groups:
                collapsed += 1
                continue
            seen_groups.add(group.sha256)
            enriched = dict(file_match)
            enriched["ExactDuplicateAliases"] = [
                {"Repository": repository, "FileName": file_name}
                for repository, file_name in group.occurrences
                if (repository, file_name) != key
            ]
            output.append(enriched)

        if collapsed == 0 and output == files:
            # Aliases still need to be exposed even if only one group member was
            # returned, so fall through to serialization when a row was enriched.
            if not any("ExactDuplicateAliases" in item for item in output if isinstance(item, dict)):
                return body
        result["Files"] = output
        result["DuplicateFilesCollapsed"] = collapsed
        result["DistinctFilesReturned"] = len(output)
        return (json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
