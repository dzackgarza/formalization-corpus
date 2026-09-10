#!/usr/bin/env python3
"""Collect one line of description per registered repository.

Run locally and commit the result; the Pages build merges it rather than
hitting GitHub on every deploy. Sources, in order of preference:

1. SOURCES.md — the curated judgment of what a repository holds. Written here,
   and the only source that says anything about mathematical content rather
   than repeating a project's own tagline.
2. The Reservoir index checkout, which carries each package's description.
3. The GitHub API, for repositories in neither.

A repository none of them describe gets no line. Inventing a description for a
repository nobody has read is the one thing this must not do.
"""

import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "descriptions.tsv"

LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
CODE = re.compile(r"`([^`]*)`")
REPO_URL = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")


def plain(md: str) -> str:
    """Markdown cell to one sentence of prose."""
    text = LINK.sub(r"\1", md)
    text = CODE.sub(r"\1", text)
    # Emphasis marks book and paper titles in the curated rows; the page is
    # plain text, so they go rather than surfacing as stray asterisks.
    text = text.replace("*", "").strip()
    # Keep semicolon clauses: they carry the second half of the subject
    # ("Mathematical Components; the Odd Order Theorem"). Cut at a sentence
    # end, where the curated rows turn to provenance, licensing and status.
    parts = re.split(r"(?<=\.)\s+(?=[A-Z(])", text)
    out = (parts[0] if parts else text).strip()
    if len(out) > 220:
        out = out[:217].rsplit(" ", 1)[0] + "…"
    return out.rstrip(" ;,.")


def from_sources() -> dict[str, str]:
    """Map owner/repo to the curated line in SOURCES.md."""
    found = {}
    for line in (ROOT / "SOURCES.md").read_text().splitlines():
        if not line.startswith("| ["):
            continue
        cells = [c.strip() for c in line.strip("|").split(" | ")]
        if len(cells) < 2:
            continue
        m = REPO_URL.search(cells[0])
        if not m:
            continue
        found[f"{m.group(1)}/{m.group(2)}".lower()] = plain(cells[1])
    return found


def from_reservoir() -> dict[str, str]:
    found = {}
    for meta in (ROOT / "reservoir-index").rglob("metadata.json"):
        try:
            data = json.loads(meta.read_text())
        except json.JSONDecodeError:
            continue
        name, desc = data.get("fullName"), (data.get("description") or "").strip()
        if name and desc:
            found[name.lower()] = desc
    return found


def manifest_rows() -> list[tuple[str, str]]:
    rows = []
    for name in ("repos.tsv", "reservoir.tsv", "port-sources.tsv"):
        for line in (ROOT / name).read_text().splitlines():
            if line.strip():
                url, directory = line.split("\t")[:2]
                rows.append((url.rstrip("/"), pathlib.PurePosixPath(directory).name))
    return rows


def previous() -> dict[str, str]:
    """What the last run found, so re-running costs nothing for repositories
    whose line came from the GitHub API and has not changed."""
    if not OUT.exists():
        return {}
    return dict(
        line.split("\t", 1) for line in OUT.read_text().splitlines() if "\t" in line
    )


def main() -> None:
    curated, reservoir, cached = from_sources(), from_reservoir(), previous()
    print(f"{len(curated)} curated, {len(reservoir)} from the Reservoir index, {len(cached)} cached")

    out, missing = {}, []
    for url, directory in manifest_rows():
        m = REPO_URL.match(url)
        key = f"{m.group(1)}/{m.group(2)}".lower() if m else ""
        if key in curated:
            out[directory] = curated[key]
        elif key in reservoir:
            out[directory] = reservoir[key]
        elif directory in cached:
            out[directory] = cached[directory]
        else:
            missing.append((directory, url))

    print(f"{len(missing)} need the GitHub API")
    for directory, url in missing:
        m = REPO_URL.match(url)
        if not m:
            continue
        got = subprocess.run(
            ["gh", "api", f"repos/{m.group(1)}/{m.group(2)}", "--jq", ".description // \"\""],
            capture_output=True, text=True,
        )
        desc = got.stdout.strip()
        if desc:
            out[directory] = desc

    with OUT.open("w") as fh:
        for directory in sorted(out, key=str.lower):
            fh.write(f"{directory}\t{out[directory]}\n")
    print(f"{OUT}: {len(out)} described, {len(manifest_rows()) - len(out)} without")


if __name__ == "__main__":
    main()
