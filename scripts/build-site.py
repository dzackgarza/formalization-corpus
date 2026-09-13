#!/usr/bin/env python3
"""Generate the static data the Pages site needs from the manifests.

The site itself holds no index: it queries the search host. What it does need
locally is the source table — every source's canonical URL, proof assistant,
and index identifier — so a search hit can be linked back to its source and the
corpus can be browsed without a query.
"""

import json
import pathlib
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "corpus.json"

SOURCE_TABLE = ROOT / "sources.tsv"

PROOF_ASSISTANTS = {
    "lean": {"label": "Lean", "url": "https://lean-lang.org/"},
    "rocq": {"label": "Rocq", "url": "https://rocq-prover.org/"},
    "agda": {"label": "Agda", "url": "https://agda.readthedocs.io/"},
    "isabelle": {"label": "Isabelle", "url": "https://isabelle.in.tum.de/"},
    "hol-light": {"label": "HOL Light", "url": "https://github.com/jrh13/hol-light"},
    "hol4": {"label": "HOL4", "url": "https://hol-theorem-prover.org/"},
    "mizar": {"label": "Mizar", "url": "https://mizar.uwb.edu.pl/"},
    "metamath": {"label": "Metamath", "url": "https://us.metamath.org/"},
    "acl2": {"label": "ACL2", "url": "https://acl2.org/"},
    "pvs": {"label": "PVS", "url": "https://pvs.csl.sri.com/"},
    "twelf": {"label": "Twelf", "url": "https://twelf.org/"},
}


def source_rows() -> list[dict[str, str]]:
    import csv

    with SOURCE_TABLE.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def descriptions() -> dict[str, str]:
    """One line per repository, collected by scripts/collect-descriptions.py.

    Committed rather than fetched, so a Pages build never depends on the GitHub
    API being reachable or on 800 requests going out per deploy.
    """
    path = ROOT / "descriptions.tsv"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        if "\t" in line:
            name, what = line.split("\t", 1)
            out[name] = what
    return out


def public_name(url: str, directory: str, transport: str) -> str:
    """Reader-facing source identity; never expose checkout/index naming."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").removesuffix(".git")
    if parsed.netloc in {"github.com", "www.github.com"} and path:
        return path
    if "gitlab" in parsed.netloc and path:
        return path
    if transport == "web-dir" and "mizar" in parsed.netloc.lower():
        return "Mizar Mathematical Library"
    name = pathlib.PurePosixPath(directory).name
    return name.replace("__", "/")


def main() -> None:
    what = descriptions()
    sources = []
    for row in source_rows():
        url = row["url"].rstrip("/")
        directory = row["directory"]
        transport = row["transport"]
        # The index identifier follows the checkout name because Zoekt uses it
        # in raw search responses. It is search metadata, not public identity.
        index_id = pathlib.PurePosixPath(directory).name
        source = {
            "index_id": index_id,
            "name": public_name(url, directory, transport),
            "url": url,
            "proof_assistant": row["proof_assistant"],
        }
        if index_id in what:
            source["what"] = what[index_id]
        sources.append(source)

    sources.sort(key=lambda source: source["name"].lower())
    counts: dict[str, int] = {}
    for source in sources:
        key = source["proof_assistant"]
        counts[key] = counts.get(key, 0) + 1
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "sources": sources,
                "sources_by_proof_assistant": counts,
                "proof_assistants": PROOF_ASSISTANTS,
            },
            indent=0,
            sort_keys=True,
        )
    )
    print(f"{OUT}: {len(sources)} sources {counts}")



if __name__ == "__main__":
    main()
