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
<style>
:root {{ --bg:#fbfbf9; --fg:#1a1a19; --dim:#6b6b66; --rule:#dedcd5; --accent:#7a3b12; --panel:#fff; }}
@media (prefers-color-scheme: dark) {{
	:root {{ --bg:#16161a; --fg:#e6e4de; --dim:#99968d; --rule:#2e2e35; --accent:#e0a56a; --panel:#1d1d22; }}
}}
* {{ box-sizing: border-box; }}
a {{ color: var(--accent); }}
body {{ margin:0; background:var(--bg); color:var(--fg);
	font:15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
header {{ border-bottom:1px solid var(--rule); padding:18px 20px 14px; }}
header h1 {{ font-size:17px; margin:0 0 3px; font-weight:600; letter-spacing:-0.01em; }}
header h1 a {{ color:inherit; text-decoration:none; }}
nav {{ font-size:13px; }}
nav a {{ margin-right:14px; }}
.sub {{ color:var(--dim); font-size:13px; margin:0; }}
main {{ padding:18px 20px 60px; max-width:1000px; }}
main > h1 {{ display:none; }}
h2 {{ font-size:15px; margin:34px 0 10px; padding-top:16px; border-top:1px solid var(--rule); }}
p {{ margin: 10px 0; }}
table {{ border-collapse:collapse; width:100%; margin:10px 0 22px; font-size:13.5px; }}
th {{ text-align:left; font-size:12px; text-transform:uppercase; letter-spacing:0.04em;
	color:var(--dim); font-weight:600; border-bottom:1px solid var(--rule); padding:6px 10px 6px 0; }}
td {{ vertical-align:top; border-bottom:1px solid var(--rule); padding:8px 10px 8px 0; }}
td:first-child {{ width:22em; }}
td:first-child code {{ font-size:12.5px; }}
code {{ font-family:ui-monospace, SFMono-Regular, Menlo, monospace; background:var(--panel);
	border:1px solid var(--rule); border-radius:3px; padding:0 4px; }}
a code {{ color:var(--accent); }}
@media (max-width:640px) {{ td:first-child {{ width:auto; }} table, td, th {{ display:block; width:auto; }} }}
</style>
</head>
<body>
<header>
	<h1><a href="./">Lean Reference Corpus</a></h1>
	<nav><a href="./">Search</a><a href="./corpus.html">Every repository</a><a href="./subjects.html">By subject</a></nav>
</header>
<main>
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


def main() -> None:
    subjects_page()
    what = descriptions()
    repos = {}
    for kind, manifest in MANIFESTS.items():
        for url, directory in rows(manifest):
            # Zoekt names a shard by the checkout's basename, which is how a
            # search result identifies its repository.
            name = pathlib.PurePosixPath(directory).name
            repos[name] = {"url": url, "kind": kind}
            if name in what:
                repos[name]["what"] = what[name]

    counts = {kind: sum(1 for r in repos.values() if r["kind"] == kind) for kind in MANIFESTS}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"repos": repos, "counts": counts}, indent=0, sort_keys=True))
    described = sum(1 for r in repos.values() if r.get("what"))
    print(f"{OUT}: {len(repos)} repositories {counts}, {described} described")


if __name__ == "__main__":
    main()
