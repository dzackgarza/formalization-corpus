# Contributing

This repository is a mathematical reference/search corpus.  Public copy should
read like a mathematics reference work, not like an implementation dashboard,
product page, ingestion log, or repository-maintenance report.

The rules below are numbered so review comments can cite them directly.

## Copy and information-design rules

### COPY-001 — Labels must make independent sense

A heading, column label, statistic, or control must be understandable without
knowing the implementation or reading explanatory prose elsewhere on the page.

Rejected examples seen during the site redesign include **What it holds**,
**Corpus reach**, **Searchable sources**, and **With formalization files**.
Prefer ordinary nouns such as **Sources**, **Topics**, **Proof assistant**, and
**Description**.

### COPY-002 — Do not restate the defining premise of the site

The whole corpus exists to search formalizations.  Therefore adjectives such as
"searchable" and "formalization" must not be added merely to distinguish the
objects already defined by the page.  A source in this corpus is searchable by
definition; a file indexed as mathematical content is part of a formalization by
definition.

Do not write copy such as **searchable sources**, **formalization files**, or
**lines of formalization code** merely to restate those premises.

### COPY-003 — Public metrics must measure a mathematical/reference concept

Do not publish a count merely because the implementation can count it.  File
counts, byte counts, physical line counts, index shard counts, hydration counts,
and similar operational quantities are maintenance diagnostics unless a concrete
reader-facing use has been established.

Useful public counts currently include source count, proof-assistant count, topic
count, and the number of sources assigned to a topic.  Definition/theorem counts
may be added only when their cross-system meaning and extraction method are
sound.

### COPY-004 — A discrepancy is a defect, not a statistic

Do not expose ingestion/indexing failures as a public denominator such as
**902 / 909 sources**.  Determine why the entries differ and repair the source
inventory, hydration, or index.  If an entry cannot contribute formalized
material, it is not a corpus source.

### COPY-005 — Corpus membership has a content invariant

Every row of `sources.tsv` must identify an independently addressable source of
formal material and must contain at least one source-language file for its proof
assistant when hydrated.  Metadata repositories, search engines, project boards,
review machinery, documentation-only sites, package indexes, and dead upstream
repositories may be useful references, but they are not corpus sources merely
because they are adjacent to formalization work.

Reference-only resources belong in documentation such as `SOURCES.md`, not in
`sources.tsv` and not in the search index.

### COPY-006 — Do not explain internal exclusions on reader-facing pages

Details such as generated ACL2 `.sys` files, PVS proof traces, sparse-checkout
rules, ignored build artifacts, or index-file extensions belong in maintainer
documentation.  The public site should describe what it contains, not enumerate
implementation artifacts that were intentionally omitted.

### COPY-007 — Do not hedge obvious live-state statements

Avoid phrases such as **currently available to search**, **counts are computed
from the files available to search**, or **what is actually hydrated and
indexed**.  On a live search site these are either tautologies or evidence that a
known failure has been normalized into copy.  Fix the state instead.

### COPY-008 — Keep backend vocabulary behind the API boundary

Zoekt, repository regexes, paths, shard names, sparse checkout, raw index IDs,
and similar implementation concepts are not part of the primary mathematical
interface.  The main search UI should use corpus concepts: query text, proof
assistant, source, and topic.  Backend syntax belongs on the API page.

### COPY-009 — Avoid product/marketing register

This is a reference project, not a product landing page.  Avoid value-proposition
copy and invented branded concepts such as **formal prior art**, **corpus
snapshot**, **browse the index**, **move by mathematical area**, or **inspect
coverage**.  State what the page is and what it lists.

### COPY-010 — Avoid vague metaphors and container language

Repositories do not "hold" mathematics, and a UI should not rely on metaphors
whose referent is unclear.  Prefer **Description**, **Mathematical content**, or
the name of the actual object being described.

### COPY-011 — Use standard mathematical names for classification

Public classification is by **Topics**, with many-to-many membership.  Topic
names should be recognizable mathematical areas (for example **Commutative
algebra**, **Functional analysis**, **Graph theory**, **Program verification**),
not repository directory names, project-specific taxonomies, or vague buckets.

A source may belong to any number of topics.  Do not force one-source/one-topic
classification.

### COPY-012 — Separate mathematical description from maintenance status

The first public description of a mathematical source should say what mathematics
it formalizes.  Terms such as **upstreamed**, **stale**, **bridge**, **sorry-free**,
toolchain status, license status, CI details, popularity, and development process
are maintenance/provenance notes and should not replace the mathematical
description.

When status is worth recording, keep it in maintainer documentation or a
separate provenance field rather than mixing it into **Mathematical content**.

### COPY-013 — Avoid proof-assistant insider jargon when ordinary wording exists

Reader-facing descriptions should not assume familiarity with terms such as
SSReflect, MoSeL, THIR, typeclass hierarchy, FFI, or internal Mathlib paths unless
the term itself is the subject of the source.  Prefer the underlying mathematical
or formal-methods description.

### COPY-014 — Use one term for one concept

Do not cycle between **source**, **repository**, **library**, **project**,
**formalization**, and **corpus entry** when they refer to the same counted
entity.  The canonical counted entity is a **source**.  A source may technically
be a repository, library, project, or published source distribution, but public
totals should simply say **Sources**.

### COPY-015 — Do not duplicate totals as a separate conceptual section

If a number is only the total row of a table, do not create a second card grid
with a new heading such as **Corpus statistics**.  Put the total in the table or
state it once in ordinary prose.

### COPY-016 — Technical caveats belong where they are actionable

Low-level details are appropriate on the API page or in maintainer documentation
when a caller/contributor can act on them.  They should not leak onto Search,
Sources, or Topics merely because the implementation needs them.

## Source-inventory invariant

`sources.tsv` is the canonical corpus inventory.  For a fully hydrated local
corpus, every row must satisfy all of the following:

1. the upstream source exists;
2. the local source exists;
3. it contains at least one source-language file for its proof assistant;
4. it has an index shard;
5. searching that source can return formal content.

If any condition fails, repair the source or remove the row.  Do not preserve a
bad row so that historical registry counts remain stable.

`SOURCES.md` may also document useful external indexes, search tools, project
boards, review systems, and other references.  Their presence there does not
make them corpus sources.

## Public terminology

Use these terms consistently:

| Concept | Public term |
| --- | --- |
| one counted corpus entry | Source |
| proof system | Proof assistant |
| mathematical classification | Topic |
| free-text source summary | Description |
| source summary inside a topic table | Mathematical content |

Implementation field names may differ internally, but generated public copy
should use the terms above.
