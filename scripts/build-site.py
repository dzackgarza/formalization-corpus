#!/usr/bin/env python3
"""Generate the static data the Pages site needs from the manifests.

The site itself holds no index: it queries the search host. What it does need
locally is the repository table — every checkout's name, its origin URL, and
which manifest it came from — so a search hit can be linked back to its source
on GitHub and the corpus can be browsed without a query.
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "corpus.json"
SUBJECTS = ROOT / "site" / "subjects.html"

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


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>By subject — Lean Reference Corpus</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
<style>
	html {{ font-size: 87.5%; }}
	header.container > hgroup > h1 {{ font-size: 1.4rem; margin-bottom: 0.2rem; }}
	header.container {{ padding-block: 1.2rem 0; }}
	header.container nav {{ margin-bottom: 0; }}
	main {{ padding-block: 1rem; }}
	main table {{ font-size: 0.85rem; }}
	main td:first-child {{ width: 22em; }}
	main h2 {{ font-size: 1.15rem; margin-top: 2.2rem; }}
</style>
</head>
<body>
<header class="container">
	<hgroup>
		<h1><a href="./">Lean Reference Corpus</a></h1>
		<p>What has been formalized, by subject.</p>
	</hgroup>
	<nav>
		<ul>
			<li><a href="./">Search</a></li>
			<li><a href="./corpus.html">Every repository</a></li>
			<li><a href="./subjects.html" aria-current="page">By subject</a></li>
			<li><a href="./api.html">API</a></li>
		</ul>
	</nav>
</header>
<main class="container">
{body}
</main>
</body>
</html>
"""


def subjects_page() -> None:
    """Render the registry as a page: what has been formalized, by subject."""
    import markdown

    text = (ROOT / "SOURCES.md").read_text()

    # The page is for readers looking for theorems. How the corpus is kept in
    # step with the manifests belongs to the repository, not to them.
    text = re.sub(r"^## Refreshing this registry.*?(?=^## )", "", text, flags=re.S | re.M)
    body = text.split("\n## ", 1)
    text = "## " + body[1] if len(body) > 1 else text

    html = markdown.markdown(text, extensions=["tables", "attr_list"])
    SUBJECTS.write_text(PAGE.format(body=html))
    print(f"{SUBJECTS}: {len(html)} bytes")


def declarations() -> dict[str, tuple[int, int]]:
    """Theorems and definitions per repository, from scripts/count-declarations.py.

    Counted where the checkouts are and committed, like the descriptions: the
    Pages build has the manifests but not the sources.
    """
    path = ROOT / "declarations.tsv"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            out[parts[0]] = (int(parts[1]), int(parts[2]))
    return out


def main() -> None:
    subjects_page()
    what = descriptions()
    counted = declarations()
    repos = {}
    for kind, manifest in MANIFESTS.items():
        for url, directory in rows(manifest):
            # Zoekt names a shard by the checkout's basename, which is how a
            # search result identifies its repository.
            name = pathlib.PurePosixPath(directory).name
            repos[name] = {"url": url, "kind": kind}
            if name in what:
                repos[name]["what"] = what[name]
            if name in counted:
                repos[name]["theorems"], repos[name]["definitions"] = counted[name]

    counts = {kind: sum(1 for r in repos.values() if r["kind"] == kind) for kind in MANIFESTS}
    counts["theorems"] = sum(r.get("theorems", 0) for r in repos.values())
    counts["definitions"] = sum(r.get("definitions", 0) for r in repos.values())
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"repos": repos, "counts": counts}, indent=0, sort_keys=True))
    print(f"{OUT}: {len(repos)} repositories, "
          f"{counts['theorems']:,} theorems, {counts['definitions']:,} definitions")


if __name__ == "__main__":
    main()
