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

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "corpus.json"
SUBJECTS = ROOT / "site" / "subjects.html"

MANIFESTS = (
    ("lean", "repos.tsv"),
    ("reservoir", "reservoir.tsv"),
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
			<p class="lede">Registered sources organized by mathematical area.</p>
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

    text = (ROOT / "SOURCES.md").read_text()

    # The page is for readers looking for formal content. How the corpus is kept
    # in step with the manifests belongs to the repository, not to them.
    text = re.sub(r"^## Refreshing this registry.*?(?=^## )", "", text, flags=re.S | re.M)
    body = text.split("\n## ", 1)
    text = "## " + body[1] if len(body) > 1 else text

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


def main() -> None:
    subjects_page()
    what = descriptions()
    repos = {}
    for default_kind, manifest in MANIFESTS:
        for url, directory, declared_kind, transport in rows(manifest):
            # Zoekt names a shard by the checkout's basename, which is how a
            # search result identifies its source.
            name = pathlib.PurePosixPath(directory).name
            kind = declared_kind or default_kind
            repos[name] = {"url": url, "kind": kind, "transport": transport}
            if name in what:
                repos[name]["what"] = what[name]

    counts: dict[str, int] = {}
    for repo in repos.values():
        counts[repo["kind"]] = counts.get(repo["kind"], 0) + 1
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"repos": repos, "counts": counts}, indent=0, sort_keys=True))
    print(f"{OUT}: {len(repos)} sources {counts}")


if __name__ == "__main__":
    main()
