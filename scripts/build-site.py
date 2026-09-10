#!/usr/bin/env python3
"""Generate the static data the Pages site needs from the manifests.

The site itself holds no index: it queries the search host. What it does need
locally is the repository table — every checkout's name, its origin URL, and
which manifest it came from — so a search hit can be linked back to its source
on GitHub and the corpus can be browsed without a query.
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "corpus.json"

MANIFESTS = {
    "lean": "repos.tsv",
    "reservoir": "reservoir.tsv",
    "port": "port-sources.tsv",
}


def rows(name: str) -> list[tuple[str, str]]:
    path = ROOT / name
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        url, directory = line.split("\t")[:2]
        out.append((url.rstrip("/"), directory))
    return out


def main() -> None:
    repos = {}
    for kind, manifest in MANIFESTS.items():
        for url, directory in rows(manifest):
            # Zoekt names a shard by the checkout's basename, which is how a
            # search result identifies its repository.
            repos[pathlib.PurePosixPath(directory).name] = {
                "url": url,
                "kind": kind,
            }

    counts = {kind: sum(1 for r in repos.values() if r["kind"] == kind) for kind in MANIFESTS}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"repos": repos, "counts": counts}, indent=0, sort_keys=True))
    print(f"{OUT}: {len(repos)} repositories {counts}")


if __name__ == "__main__":
    main()
