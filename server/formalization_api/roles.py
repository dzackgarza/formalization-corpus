from __future__ import annotations

import collections
import hashlib
import json
import pathlib
from typing import Any


IMPORT_NAVIGATION_ROLE = "navigation-import-only"
ACL2_PROOF_METADATA_ROLE = "proof-metadata-useless-runes"
ROLE_BY_DECISION_ID = {
    "FD-016": IMPORT_NAVIGATION_ROLE,
    "FD-017": ACL2_PROOF_METADATA_ROLE,
}
ROLE_ORDER = (IMPORT_NAVIGATION_ROLE, ACL2_PROOF_METADATA_ROLE)


class FileRoleIndex:
    """Search-result roles derived from durable filtering decisions.

    Role-bearing files remain ordinary indexed documents.  The role index changes
    only presentation order: ordinary formal-source hits stay in Zoekt order,
    followed by lower-priority searchable metadata/navigation roles, each stable
    within its own role.
    """

    def __init__(self, roles: dict[tuple[str, str], str]) -> None:
        self._roles = dict(roles)

    @classmethod
    def empty(cls) -> "FileRoleIndex":
        return cls({})

    @classmethod
    def from_path(cls, path: pathlib.Path | None) -> "FileRoleIndex":
        if path is None or not path.is_file():
            return cls.empty()
        roles: dict[tuple[str, str], str] = {}
        with path.open() as handle:
            for number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                role = ROLE_BY_DECISION_ID.get(str(row.get("decision_id", "")))
                if role is None:
                    continue
                if row.get("primary") != "retain":
                    raise ValueError(
                        f"search role at {path}:{number} is not primary-retained"
                    )
                key = (str(row["repository"]), str(row["file"]))
                previous = roles.get(key)
                if previous is not None and previous != role:
                    raise ValueError(f"file has conflicting search roles at {path}:{number}: {key}")
                roles[key] = role
        return cls(roles)

    @property
    def navigation_count(self) -> int:
        return sum(role == IMPORT_NAVIGATION_ROLE for role in self._roles.values())

    def is_navigation(self, repository: str, file_name: str) -> bool:
        return self._roles.get((repository, file_name)) == IMPORT_NAVIGATION_ROLE

    def fingerprint(self) -> dict[str, Any]:
        digest = hashlib.sha256()
        navigation_digest = hashlib.sha256()
        counts = collections.Counter(self._roles.values())
        for (repository, file_name), role in sorted(self._roles.items()):
            encoded = repository.encode() + b"\0" + file_name.encode() + b"\n"
            digest.update(role.encode())
            digest.update(b"\0")
            digest.update(encoded)
            if role == IMPORT_NAVIGATION_ROLE:
                navigation_digest.update(encoded)
        return {
            "role_counts": dict(sorted(counts.items())),
            "roles_sha256": digest.hexdigest(),
            "navigation_count": counts.get(IMPORT_NAVIGATION_ROLE, 0),
            "navigation_sha256": navigation_digest.hexdigest(),
        }

    def rerank_files(self, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self._roles or not files:
            return files
        ordinary: list[dict[str, Any]] = []
        by_role: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLE_ORDER}
        for file_match in files:
            key = (
                str(file_match.get("Repository", "")),
                str(file_match.get("FileName", "")),
            )
            role = self._roles.get(key)
            if role is None:
                ordinary.append(file_match)
                continue
            enriched = dict(file_match)
            enriched["FileRole"] = role
            by_role[role].append(enriched)
        return ordinary + [item for role in ROLE_ORDER for item in by_role[role]]

    def rerank_response(self, body: bytes) -> bytes:
        if not self._roles:
            return body
        payload: dict[str, Any] = json.loads(body)
        result = payload.get("Result")
        if not isinstance(result, dict):
            return body
        files = result.get("Files")
        if not isinstance(files, list):
            return body
        reranked = self.rerank_files(files)
        role_counts = collections.Counter(
            str(item.get("FileRole"))
            for item in reranked
            if isinstance(item, dict) and item.get("FileRole")
        )
        demoted = sum(role_counts.values())
        if not demoted:
            return body
        result["Files"] = reranked
        result["RoleFilesDemoted"] = demoted
        result["RoleCounts"] = dict(sorted(role_counts.items()))
        result["NavigationFilesDemoted"] = role_counts.get(IMPORT_NAVIGATION_ROLE, 0)
        result["RoleRerankingApplied"] = True
        return (json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
