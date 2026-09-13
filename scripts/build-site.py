#!/usr/bin/env python3
"""Generate the static data the Pages site needs from the manifests.

The site itself holds no index: it queries the search host. What it does need
locally is the source table — every checkout's name, its origin URL, and
which manifest it came from — so a search hit can be linked back to its source
on GitHub and the corpus can be browsed without a query.
"""

import json
import html
import pathlib
import re
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "corpus.json"
SUBJECTS = ROOT / "site" / "subjects.html"

MANIFESTS = (
    ("lean", "repos.tsv"),
    ("lean", "reservoir.tsv"),
    (None, "port-sources.tsv"),
)


def rows(name: str) -> list[tuple[str, str, str | None, str]]:
    path = ROOT / name
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        url, directory = fields[:2]
        kind = fields[2] if len(fields) > 2 and fields[2] else None
        transport = fields[3] if len(fields) > 3 and fields[3] else "git"
        out.append((url.rstrip("/"), directory, kind, transport))
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
<title>Subjects — Formalization Corpus</title>
<link rel="stylesheet" href="./styles.css">
</head>
<body>
<header class="site-header">
	<div class="shell masthead">
			<a class="brand" href="./">
				<span class="brand-mark" aria-hidden="true">FC</span>
				<span class="brand-name">Formalization Corpus</span>
		</a>
		<nav class="site-nav" aria-label="Primary">
			<a href="./">Search</a>
			<a href="./corpus.html">Sources</a>
			<a href="./subjects.html" aria-current="page">Subjects</a>
			<a href="./api.html">API</a>
		</nav>
	</div>
</header>
<main class="shell page-main">
	<header class="page-heading">
			<h1>Subjects</h1>
			<p class="lede">Formalization sources organized by mathematical area.</p>
	</header>
	<div class="content-layout">
		<aside class="toc" aria-label="Subject areas">
			<div class="toc-title">On this page</div>
			<nav>{toc}</nav>
		</aside>
		<article class="prose">{body}</article>
	</div>
</main>
<footer class="site-footer">
	<div class="shell footer-inner">
			<p>Subject descriptions are maintained in <code>SOURCES.md</code>.</p>
		<div class="footer-links"><a href="https://github.com/dzackgarza/formalization-corpus">GitHub</a><a href="./corpus.html">Sources</a></div>
	</div>
</footer>
</body>
</html>
"""


def subjects_page() -> None:
    """Render the registry as a page: what has been formalized, by subject."""
    import markdown

    source_text = (ROOT / "SOURCES.md").read_text()

    # This page is a mathematical subject index, not a projection of the
    # repository's maintenance taxonomy.  Keep only sections whose headings
    # are mathematical subject areas.  Discovery indexes, package registries,
    # proof-assistant groupings, and maintainer workflow remain in SOURCES.md.
    public_subjects = {
        "Category theory, higher structures, type-theory semantics",
        "Algebra, number theory, algebraic geometry",
        "Quadratic forms, lattices, sphere packing",
        "Analysis, probability, geometry, dynamics",
        "Combinatorics, discrete mathematics, logic, foundations",
        "Computational and applied mathematics",
    }
    sections = re.split(r"(?m)^## ", source_text)
    selected = []
    for section in sections[1:]:
        heading, _, body = section.partition("\n")
        if heading.strip() in public_subjects:
            selected.append(f"## {heading}\n{body}")
    text = "\n".join(selected)

    md = markdown.Markdown(extensions=["tables", "attr_list", "toc"])
    rendered = md.convert(text)
    toc_items = []
    for token in getattr(md, "toc_tokens", []):
        if token.get("level") != 2:
            continue
        label = html.escape(re.sub(r"<[^>]+>", "", token.get("name", "")))
        toc_items.append(f'<a href="#{token["id"]}">{label}</a>')
    SUBJECTS.write_text(PAGE.format(body=rendered, toc="".join(toc_items)))
    print(f"{SUBJECTS}: {len(rendered)} bytes")


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
    subjects_page()
    what = descriptions()
    sources = []
    for default_kind, manifest in MANIFESTS:
        for url, directory, declared_kind, transport in rows(manifest):
            # The index identifier follows the checkout name because Zoekt uses
            # it in raw search responses.  It is search metadata, not the
            # source's public identity.
            index_id = pathlib.PurePosixPath(directory).name
            proof_assistant = declared_kind or default_kind
            source = {
                "index_id": index_id,
                "name": public_name(url, directory, transport),
                "url": url,
                "proof_assistant": proof_assistant,
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
            {"sources": sources, "sources_by_proof_assistant": counts},
            indent=0,
            sort_keys=True,
        )
    )
    print(f"{OUT}: {len(sources)} sources {counts}")



if __name__ == "__main__":
    main()
