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

## Corpus filtering and retrieval-eligibility rules

These rules govern file-level filtering, deduplication, indexing, and ranking.
They are intentionally conservative.  A false positive in search is visible and
can later be downranked; a false exclusion removes evidence from discovery and
can persist unnoticed for a long time.

The detailed decision procedure, examples, current measurements, and known
footguns live in [`docs/CORPUS-FILTERING.md`](./docs/CORPUS-FILTERING.md).  The
`FILTER-###` rules below are the review contract and take precedence over an
ad-hoc cleanup heuristic.

### FILTER-001 — Preserve the project's actual information need

The primary purpose of the corpus is to find prior formal work: definitions,
structures, constructions, specifications, lemma/theorem statements, proofs,
and useful formal interfaces across proof assistants.  Filtering must be judged
against that purpose, not against whether a file looks polished, finished,
canonical, upstreamed, popular, or production-ready.

An incomplete proof can still be high-value prior art.  A checked theorem
statement ending in `sorry`, `admit`, an axiom, a hole, or an equivalent
proof-assistant mechanism may identify the right definitions, names, types,
interfaces, namespace, or intended statement.  Do not confuse proof completion
with search value.

### FILTER-002 — Hard exclusion has a much higher evidence bar than downranking

When a file's value is uncertain, retain it and attach role/provenance metadata;
then test downranking or a secondary result channel.  Hard exclusion from the
primary mathematical-content index is appropriate only when there is a
content-level reason to believe no unique searchable formal mathematics is
being lost.

Path names, repository conventions, model intuition, or a few inspected
examples are not sufficient evidence for a corpus-wide hard filter.

### FILTER-003 — Keep source membership, storage, index eligibility, and rank separate

Do not solve a file-ranking problem by removing an otherwise valid source from
`sources.tsv`.  Distinguish at least:

1. **source membership** — whether the upstream source belongs in the corpus;
2. **retention/hydration** — what is locally preserved from that source;
3. **primary mathematical index eligibility** — what may occupy mathematical
   result slots;
4. **auxiliary metadata/documentation eligibility** — what may help source or
   module discovery without competing with theorem-bearing files;
5. **ranking** — how eligible mathematical documents are ordered.

A document can be useful metadata while being a poor primary mathematical
result.  Filtering work must state which layer it changes.

### FILTER-004 — The unilateral hard-filter boundary is content based

A document may be removed from the **primary mathematical-content index**
without per-document relevance review only when at least one of these is true:

1. a prover-aware or format-aware check establishes that it contains no formal
   mathematical declarations/proofs relevant to this corpus, and any useful
   navigation/documentation is retained in an auxiliary channel; or
2. its searchable content is exactly represented by another indexed document,
   and all original source/path occurrences are retained as provenance aliases.

Anything weaker is a candidate for tagging/downranking or an experiment, not an
automatic exclusion policy.

### FILTER-005 — Filtering must be reversible and provenance preserving

Do not destructively delete upstream material merely to make search cleaner.
Every hard filter or deduplication mechanism must be reproducible from the
source checkout and must preserve enough metadata to answer why a document is
absent from the primary index.

For deduplicated content, retain every original `(source, path)` occurrence as
an alias.  Search-result canonicalization is an implementation detail; it must
not erase the fact that identical formal material occurs in several sources.

### FILTER-006 — Exact-content deduplication is safe; normalization is a new experiment

Byte-identical formal-source files contribute no new searchable mathematical
text.  They may be represented once in a content index if all occurrences are
retained as aliases/provenance.  Every original source/path/module name must
remain searchable metadata: two byte-identical files can live under different
mathematically informative paths, and path terms are themselves a useful
retrieval signal.

Do not silently broaden this rule to whitespace normalization, comment removal,
alpha-renaming, pretty-print normalization, AST equality, or semantic
equivalence.  Each broader equivalence relation can discard useful names,
documentation, syntax, or provenance and requires its own measured policy.

A whole-file no-content test is different from normalization.  `FD-015` applies
only to a **nonempty** formal-source byte stream for which `raw.strip()` is empty:
the file contains byte whitespace and nothing else.  It does not authorize
removing whitespace from a substantive file, excluding comment-only files, or
treating a regex-declaration-free file as empty.  Those classes retain searchable
text and remain governed by the higher evidence bar above.

### FILTER-007 — Pure import aggregators are navigation data, not owner results

A file that is **prover-aware verified** to contain only imports (plus
whitespace/comments) contains no declaration or proof of its own.  Such a file
should normally not compete with the imported theorem/definition-bearing file
for primary mathematical result slots **once its navigation signal is available
through the actual search surface**.

Preserve its module identity, import edges, source/path provenance, and useful
comments/documentation as searchable auxiliary metadata.  The module/path name
itself may be the phrase a user knows even when the imported declaration has a
less obvious name.  Do not infer
"pure import" from a filename or a regex alone.  `open`, notation, attributes,
options, aliases, namespace commands, declarations, or other executable/formal
commands take a file outside this unilateral class.

Do not equate “an auxiliary view can be materialized” with “the information is
searchable.”  Before removing an import-only module from primary search, verify
end to end that the deployed query path publishes and queries the auxiliary
representation.  If that delivery path is absent or disabled, keep the module
primary-eligible.  This is the reason historical `FD-005` is superseded by
`FD-016` in the current corpus state.

Primary eligibility does not require giving navigation modules raw Zoekt rank.
The current result layer uses `FD-016` as an explicit role: verified import-only
hits remain indexed and returned, but are stably placed after ordinary formal
content within the retrieved candidate set and labelled
`navigation-import-only`.  This is ranking, not filtering: it must not remove a
candidate, reduce the retrieval budget, or make a direct module/path hit
unqueryable.  Keep the raw lexical control separately measurable so a ranking
gain cannot be misreported as evidence that the files were safe to exclude.

### FILTER-008 — Documentation/build metadata belongs in a separate retrieval role

Non-formal README files, toolchain pins, manifests, package/build files, and
similar metadata do not themselves constitute formal theorem/definition/proof
content. They should not consume primary mathematical result slots merely
because they are present in a hydrated source. The filename is not enough when
the file itself is in a proof assistant's source language: `README.lean`,
`README.thy`, `README.agda`, `Readme.lsp`, and analogous formal-source files
remain primary mathematical content unless some stronger independent invariant
applies.

The same rule applies to formal-language build scripts. In particular,
`lakefile.lean` is an ordinary Lean program, not equivalent to
`lakefile.toml`/`lake-manifest.json`/`lean-toolchain`. A 2026-09-14 exhaustive
audit of the then-498 excluded `lakefile.lean` files found declaration syntax in
125 of them, including hundreds of `def`s plus structures, inductives, an
example, and an axiom. Those declarations are often build helpers, but that is
not a content-level proof of irrelevance. `lakefile.lean` therefore remains in
the primary formal-source channel unless a stronger per-file invariant applies.

Generated/system directories must be narrowed the same way. ACL2's
`*@useless-runes.lsp` reports are the concrete counterexample to treating
certification output as disposable: an exhaustive 2026-09-14 audit found
589,709 distinct generated event identifiers in those reports that were absent
from every retained non-`.sys` ACL2 source file under a conservative textual
check. `FD-014` is therefore superseded by retained role `FD-017`. The reports
remain searchable as proof metadata and may be downranked behind authored
formal-source hits; neither physical filtering nor a blanket query-time `.sys`
exclusion is permitted.

Non-formal README and project documentation can still be useful to maintainers for
source discovery, provenance, or understanding project layout.  If they are made
searchable, keep them in a genuinely separate documentation/source-discovery index.
They are not mathematical prior-art results and must not be merged into the public
formalization search merely because they contain terminology absent from formal
source.

"Separate" is an index boundary, not a result-ordering convention.  FD-002 files
must not occupy shards in the public `.zoekt` index, be queried through
`/api/search`, or be appended to ordinary formalization results.  The repository's
optional `.zoekt-metadata` index is a maintainer-side auxiliary index built with
`just index-metadata` and queried explicitly with `just search-metadata`; it is not
published or queried by the public site.  A future reader-facing documentation
search, if one is justified independently, must remain a distinct search surface.

### FILTER-009 — Never filter on `sorry`, `admit`, holes, or proof incompleteness alone

Proof incompleteness is not a corpus-quality failure for the project's prior-art
use case.  A declaration with an unfinished proof can be exactly the result a
mathematician or agent needs.  `sorry`/`admit` status may be recorded as
provenance, but it is not a primary-index exclusion signal.

### FILTER-010 — `generated/` is provenance, not a relevance class

Do not exclude a file because its path contains `generated`, `autogen`,
`ChallengeDeps`, or an analogous label.  Generated files may contain unique and
useful formal definitions, structures, theorem statements, or proofs.

Generated boilerplate may still be removable by a stronger invariant such as
exact-content deduplication.  Apply the stronger invariant, not the path label.

### FILTER-011 — Tests, fixtures, examples, and benchmarks are not automatically disposable

Test/fixture/example/benchmark files can contain unique declarations, minimal
reproductions, API examples, theorem statements, or proof patterns.  Their role
may justify downranking for ordinary mathematical lookup, but path membership
alone is not a safe hard-exclusion criterion.

### FILTER-012 — Audit, roadmap, and suggested files are not automatically disposable

Audit files may encode declarations or precise formal checks.  Roadmap and
`Suggested` files may contain elaborated definitions and theorem statements,
including statements whose proofs remain holes.  These can be valuable prior
art.  Tag such roles and evaluate ranking behavior; do not hard-filter the class
without a stronger content invariant.

### FILTER-013 — Vendored/copied material is removable only when redundancy is established

`vendor`, `vendored`, copied, mirrored, or forked paths are not evidence of
content identity.  A vendored copy may have local fixes, additional declarations,
different names, or a historically useful version.  Apply exact-content
deduplication when it is actually identical; otherwise retain it unless a
separate equivalence study establishes a safe policy.

### FILTER-014 — Regex absence of declarations is diagnostic only

Do not hard-filter a formal-language file because a generic regular expression
did not find `theorem`, `lemma`, `def`, or similar tokens.  Proof assistants have
macros, commands, generated declarations, notation, section machinery, examples,
attributes, and system-specific syntax that a cross-prover regex cannot classify
soundly.  Hard content classification must be prover/format aware.

### FILTER-015 — Cross-prover filtering requires prover-specific semantics

Do not project Lean assumptions onto Rocq, Isabelle, HOL, Mizar, Metamath, ACL2,
PVS, Twelf, or Agda.  Generated proof traces, session files, proof scripts,
theory roots, and caches have different meanings in different systems.

A supposedly generated or auxiliary extension may contain authored proof steps
or the only useful representation of a proof.  Establish its role for that
proof assistant before excluding it.

### FILTER-016 — Unjudged is not irrelevant

Sparse qrels cannot certify a filter as safe.  A pooled candidate absent from
`gold.json` is **unjudged**, not relevance 0.  Do not cite lack of a relevance
judgment as evidence that a file class is garbage.

When a filtering experiment changes top results, pool and review the affected
candidates independently of the system that produced them.

### FILTER-017 — Owner relevance means owner content, not merely a convenient module root

An import-only umbrella module can be an excellent navigation result while not
being the file that owns the requested definition/theorem.  Relevance judgments
and ranking metrics must distinguish these cases.  Do not give an aggregator
owner-level credit merely because following its imports eventually reaches the
formalization.

If an old qrel conflicts with this semantics, record the anomaly and correct the
qrel in a gold-only change before using it to justify a filtering policy.

### FILTER-018 — Every filtering proposal is a measured data experiment before deployment

Before changing ingestion/index eligibility, record a hypothesis and produce a
candidate/shadow index or post-hoc simulation against the frozen baseline.  Keep
qrels, query set, and comparison index state controlled; inspect per-query gains
and losses, not only aggregate scores.

Archive the measurement in `evaluation/search/ledger.jsonl`/`runs/`, including
the exact filter policy/version and affected-document counts.  Data filtering is
part of search-quality research and follows the same scientific protocol as
ranking changes.

### FILTER-019 — Prefer role metadata and downranking while evidence is incomplete

The default intermediate state for a suspicious class is an explicit file-role
tag: import aggregator, generated, test/fixture, audit, roadmap, vendored,
documentation, build metadata, duplicate alias, and so on.  Role tags make
ranking experiments possible without losing recall.

Only promote a role from "tag/downrank" to "hard exclude" when the stronger
`FILTER-004` criterion is satisfied.

### FILTER-020 — Record exclusion reasons as durable data

Any production hard filter must have a stable policy identifier, implementation
version, date/commit, counts by source/proof assistant, and a reversible mapping
to excluded documents.  A future contributor must be able to audit which policy
hid a file without reconstructing old shell commands or Git history.

Filtered material must not become an invisible denominator that evaluation can
never rediscover.  The unfiltered source remains authoritative input; the
primary index is a derived view.

### FILTER-021 — Do not optimize disk/index size at the expense of recall

Index bloat is worth reducing, but byte savings are not evidence of mathematical
irrelevance.  Report storage/runtime improvements separately from retrieval
quality.  A smaller index is a valid win only when the relevant-content and
provenance invariants remain satisfied.

When an agent or contributor cannot establish the invariant needed for a hard
filter, the required action is to stop at classification/tagging and record the
uncertainty.  "Looks like junk" is never a reason to make content undiscoverable.

## Source-lead intake

Source suggestions are unreviewed leads, not proposed `sources.tsv` rows.  The
submitter is not responsible for identifying the canonical source boundary,
proof assistant, transport, sync group, topics, or other corpus metadata.  A URL
is sufficient; free-text notes are optional.

Each suggestion should enter the public GitHub issue queue with the `source lead`
label.  Review then establishes what the actual source is, whether it is already
represented, and what metadata belongs in the corpus.  Anonymous web submissions
must create the same kind of public issue and must not write to `sources.tsv` or
any parallel intake database directly.

The anonymous transport uses a transient `source-lead/*` Git ref only to invoke
the issue-creation workflow.  The workflow creates the issue as
`github-actions[bot]` and deletes the ref.  These refs are transport, not an
alternate intake queue; if issue creation fails, the undeleted ref is recovery
state for that failed submission.

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
