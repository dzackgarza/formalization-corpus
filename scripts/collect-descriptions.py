#!/usr/bin/env python3
"""Collect one line of description per registered source.

Run locally and commit the result; the Pages build merges it rather than
hitting GitHub on every deploy. Sources, in order of preference:

1. SOURCES.md — human-maintained annotations of what notable sources hold, and the only
   source that says anything about mathematical content rather than repeating a
   project's own tagline.
2. The Reservoir index checkout, which carries each package's description.
3. The GitHub API, for repositories in neither.

A source none of them describe gets no line. Inventing a description for a
source nobody has read is the one thing this must not do.

SOURCES.md is parsed, not pattern-matched: rendered to HTML with the same
markdown library the site build uses, then walked as a document. A table cell
is a cell, a link is a link, and an asterisk inside a description stays inside
the description.
"""

import html.parser
import json
import pathlib
import re
import subprocess
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "descriptions.tsv"
REPO_URL = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")


def source_key(url: str) -> str:
    """Canonical key for a registry link or manifest source URL."""
    parsed = urllib.parse.urlsplit(url.rstrip("/"))
    return f"{parsed.netloc.lower()}{parsed.path.rstrip('/').lower()}"


class Registry(html.parser.HTMLParser):
    """Rows of the domain tables: the source a row is about, and its line.

    A row's subject is the first repository link in its first cell; everything
    after that cell is what the row says about it.
    """

    def __init__(self) -> None:
        super().__init__()
        self.rows: dict[str, str] = {}
        self.cells: list[str] = []
        self.subject: str | None = None
        self.in_cell = False
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.in_cell, self.text = True, []
        elif tag == "a" and self.in_cell and not self.cells and not self.subject:
            href = dict(attrs).get("href", "")
            if href.startswith(("https://", "http://")):
                self.subject = source_key(href)

    def handle_endtag(self, tag):
        if tag == "td":
            self.cells.append("".join(self.text).strip())
            self.in_cell = False
        elif tag == "tr":
            if self.subject and len(self.cells) > 1:
                self.rows[self.subject] = sentence(self.cells[1])
            self.cells, self.subject = [], None

    def handle_data(self, data):
        if self.in_cell:
            self.text.append(data)


def sentence(text: str) -> str:
    """The first sentence: the subject, before provenance, licensing and status."""
    text = " ".join(text.split())
    parts = re.split(r"(?<=\.)\s+(?=[A-Z(])", text)
    out = (parts[0] if parts else text).strip()
    if len(out) > 220:
        out = out[:217].rsplit(" ", 1)[0] + "…"
    return out.rstrip(" ;,.")


def from_sources() -> dict[str, str]:
    import markdown

    parser = Registry()
    parser.feed(markdown.markdown((ROOT / "SOURCES.md").read_text(), extensions=["tables"]))
    return parser.rows


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


def previous() -> dict[str, str]:
    """What the last run found, so re-running costs nothing for repositories
    whose line came from the GitHub API and has not changed."""
    if not OUT.exists():
        return {}
    cached = dict(
        line.split("\t", 1) for line in OUT.read_text().splitlines() if "\t" in line
    )
    return {key: value for key, value in cached.items() if valid_description(value)}


def valid_description(text: str) -> bool:
    """Reject API error payloads and other failed lookups masquerading as prose."""
    text = text.strip()
    if not text:
        return False
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(payload, dict) and "message" in payload:
                return False
    return True


def source_rows() -> list[tuple[str, str]]:
    import csv

    rows = []
    with (ROOT / "sources.tsv").open(newline="") as handle:
        for record in csv.DictReader(handle, delimiter="\t"):
            rows.append((record["url"].rstrip("/"), pathlib.PurePosixPath(record["directory"]).name))
    return rows


def main() -> None:
    annotated, reservoir, cached = from_sources(), from_reservoir(), previous()
    print(f"{len(annotated)} annotated, {len(reservoir)} described by the Reservoir index, {len(cached)} cached")

    out, missing = {}, []
    for url, directory in source_rows():
        key = source_key(url)
        if key in annotated:
            out[directory] = annotated[key]
        elif key in reservoir:
            out[directory] = reservoir[key]
        elif directory in cached:
            out[directory] = cached[directory]
        else:
            missing.append((directory, url))

    print(f"{len(missing)} need the GitHub API")
    for directory, url in missing:
        found = REPO_URL.match(url)
        if not found:
            continue
        got = subprocess.run(
            ["gh", "api", f"repos/{found.group(1)}/{found.group(2)}",
             "--jq", ".description // \"\""],
            capture_output=True, text=True,
        )
        if got.returncode == 0 and valid_description(got.stdout):
            out[directory] = got.stdout.strip()

    with OUT.open("w") as fh:
        for directory in sorted(out, key=str.lower):
            fh.write(f"{directory}\t{out[directory]}\n")
    print(f"{OUT}: {len(out)} described, {len(source_rows()) - len(out)} without")


if __name__ == "__main__":
    main()
