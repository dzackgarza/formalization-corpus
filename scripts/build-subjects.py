#!/usr/bin/env python3
"""Build the many-to-many mathematical topic index used by the static site."""

from __future__ import annotations

import json
import html
import re
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAXONOMY = ROOT / "subject-taxonomy.tsv"
MEMBERSHIPS = ROOT / "source-subjects.tsv"
CORPUS = ROOT / "site" / "corpus.json"
OUT = ROOT / "site" / "subjects.json"
PAGE = ROOT / "site" / "topics.html"
LEGACY_PAGE = ROOT / "site" / "subjects.html"


def taxonomy_rows() -> list[tuple[str, str, str]]:
    rows = []
    seen = set()
    for lineno, line in enumerate(TAXONOMY.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 3:
            raise ValueError(f"{TAXONOMY.name}:{lineno}: expected group, slug, label")
        group, slug, label = fields
        if slug in seen:
            raise ValueError(f"{TAXONOMY.name}:{lineno}: duplicate topic {slug}")
        seen.add(slug)
        rows.append((group, slug, label))
    return rows


def membership_rows() -> list[tuple[str, str]]:
    rows = []
    seen = set()
    for lineno, line in enumerate(MEMBERSHIPS.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 2:
            raise ValueError(f"{MEMBERSHIPS.name}:{lineno}: expected source_id and subject_slug")
        pair = (fields[0], fields[1])
        if pair not in seen:
            rows.append(pair)
            seen.add(pair)
    return rows


def main() -> None:
    taxonomy = taxonomy_rows()
    known_subjects = {slug for _, slug, _ in taxonomy}
    corpus = json.loads(CORPUS.read_text())
    known_sources = {source["index_id"] for source in corpus["sources"]}

    by_subject: dict[str, set[str]] = defaultdict(set)
    for source_id, slug in membership_rows():
        if source_id not in known_sources:
            raise ValueError(f"unknown source id in {MEMBERSHIPS.name}: {source_id}")
        if slug not in known_subjects:
            raise ValueError(f"unknown topic in {MEMBERSHIPS.name}: {slug}")
        by_subject[slug].add(source_id)

    groups: OrderedDict[str, list[dict[str, object]]] = OrderedDict()
    subjects = {}
    for group, slug, label in taxonomy:
        sources = sorted(by_subject[slug])
        if not sources:
            continue
        item = {"slug": slug, "label": label, "source_count": len(sources)}
        groups.setdefault(group, []).append(item)
        subjects[slug] = {"label": label, "group": group, "sources": sources}

    payload = {
        "groups": [
            {"label": group, "subjects": items}
            for group, items in groups.items()
        ],
        "subjects": subjects,
        "classified_sources": len({source for sources in by_subject.values() for source in sources}),
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    sources_by_id = {source["index_id"]: source for source in corpus["sources"]}
    toc = []
    sections = []
    for group in payload["groups"]:
        group_slug = re.sub(r"[^a-z0-9]+", "-", group["label"].lower()).strip("-")
        toc.append(f'<div class="toc-title subject-group-title">{html.escape(group["label"])}</div>')
        section = [f'<h2 id="{group_slug}">{html.escape(group["label"])}</h2>']
        for subject in group["subjects"]:
            slug = subject["slug"]
            detail = payload["subjects"][slug]
            source_count = len(detail["sources"])
            source_word = "source" if source_count == 1 else "sources"
            toc.append(f'<a href="#subject-{slug}">{html.escape(subject["label"])}</a>')
            section.append(
                f'<h3 id="subject-{slug}">{html.escape(subject["label"])} '
                f'<span class="subject-count">{source_count} {source_word}</span></h3>'
            )
            rows = []
            for source_id in detail["sources"]:
                source = sources_by_id[source_id]
                name = html.escape(source["name"])
                url = html.escape(source["url"], quote=True)
                what = html.escape(source.get("what", ""))
                rows.append(f'<tr><td><a href="{url}">{name}</a></td><td>{what}</td></tr>')
            section.append(
                '<div class="table-wrap"><table><thead><tr><th>Source</th><th>Mathematical content</th></tr></thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div>'
            )
        sections.append("".join(section))

    PAGE.write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Topics — Formalization Corpus</title>
<link rel="stylesheet" href="./styles.css">
</head>
<body>
<header class="site-header">
  <div class="shell masthead">
    <a class="brand" href="./"><span class="brand-mark" aria-hidden="true">FC</span><span class="brand-name">Formalization Corpus</span></a>
    <nav class="site-nav" aria-label="Primary">
      <a href="./">Search</a><a href="./corpus.html">Sources</a><a href="./topics.html" aria-current="page">Topics</a><a href="./api.html">API</a>
    </nav>
  </div>
</header>
<main class="shell page-main">
  <header class="page-heading">
    <h1>Topics</h1>
    <p class="lede">Sources by mathematical topic. A source may appear under more than one topic.</p>
  </header>
  <div class="content-layout subject-layout">
    <aside class="toc subject-toc" aria-label="Topics">{"".join(toc)}</aside>
    <article class="prose subject-prose">{"".join(sections)}</article>
  </div>
</main>
<footer class="site-footer">
  <div class="shell footer-inner"><div></div><div class="footer-links"><a href="https://github.com/dzackgarza/formalization-corpus">GitHub</a><a href="./corpus.html">Sources</a></div></div>
</footer>
</body>
</html>
""")
    LEGACY_PAGE.write_text(
        '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=./topics.html">'
        '<link rel="canonical" href="./topics.html"><title>Topics — Formalization Corpus</title>'
    )
    print(
        f"{OUT}: {len(subjects)} topics, "
        f"{payload['classified_sources']} classified sources"
    )


if __name__ == "__main__":
    main()
