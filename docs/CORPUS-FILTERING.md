# Corpus filtering policy and decision guide

This document expands the `FILTER-###` rules in `CONTRIBUTING.md`.  It exists
because file-level cleanup is unusually dangerous in a search corpus: once a
class is excluded from indexing, ordinary search no longer exposes evidence
that the class was useful.  A bad filter can therefore look successful simply
because it has hidden the counterexamples.

The project goal is not to index only complete, canonical or production-quality
libraries.  It is to help a mathematician or agent answer questions such as:

- Has this definition or structure already been formalized?
- Has anyone stated this lemma or theorem in a proof assistant?
- Which names/types/interfaces were used?
- Is there a proof or partial proof that can be adapted?
- Is there an implementation in another proof assistant that clarifies the
  mathematical structure?

That objective makes recall of formal statements and interfaces more important
than conventional source-code cleanliness.

## 1. Vocabulary: five separate layers

Filtering discussions must say which layer they mean.

**Source membership.** `sources.tsv` answers whether an independently
addressable formalization source belongs in the corpus.  A few low-value files
inside a valid source are not a reason to remove the source.

**Retention/hydration.** A local checkout may keep files that are needed for
provenance, linking, rebuilding or auxiliary search even if they are not primary
mathematical results.

**Primary mathematical-content eligibility.** These documents may occupy the
ranked result slots used to answer definition/theorem/proof searches.

**Auxiliary metadata/documentation eligibility.** These documents or derived
records may help locate a source/module, explain terminology or traverse an
import graph without competing with theorem-bearing content.

**Ranking.** Among primary-eligible documents, some roles may deserve a penalty
or boost.  Ranking is reversible at query time; hard exclusion is not.

Do not use one layer as a substitute for another.  In particular, do not delete
a source from `sources.tsv` to solve a file-role problem.

## 2. The losslessness boundary

The unilateral hard-filter boundary is deliberately narrow.  A document may be
removed from the primary mathematical index without individual relevance review
only when one of the following can be established:

1. **No formal mathematical content:** a prover-aware/format-aware classifier
   establishes that the document contains no definitions, declarations,
   theorem/lemma statements, structures, constructions, specifications, proofs
   or equivalent formal content relevant to the corpus.  Useful navigation or
   documentation must remain accessible in an auxiliary representation.
2. **Exact content redundancy:** another indexed document has exactly the same
   searchable bytes, and every original `(source, path)` is retained as an alias
   of the canonical content record.

If neither condition is established, retain the document.  Add a role tag and
test downranking or a secondary search channel first.

This is intentionally asymmetric.  Search noise is observable and reversible.
An excluded theorem statement may remain undiscoverable for months and may also
disappear from future qrel pools, making the evaluation self-confirming.

**Agent stop rule:** if the content invariant is uncertain, do not improvise a
hard filter.  Produce a manifest/role tag, record the uncertainty, and leave the
material discoverable until the class has been studied.

## 3. Current class-by-class policy

| Class | Primary mathematical index | Required treatment / reason |
| --- | --- | --- |
| Byte-identical formal files | Canonicalize one content record | Preserve every source/path as an alias; do not discard provenance. |
| Zero-byte formal files | Exclude | No searchable mathematical content. The source/path and exclusion reason remain in the ledger. |
| Nonempty byte-whitespace-only formal files (`raw.strip() == b""`) | Exclude | No token, identifier, comment, declaration, statement or proof text exists. This is a whole-file no-content test, not whitespace normalization. |
| Strict build metadata (`lean-toolchain`, manifests, package/build files) | Exclude | Not formal mathematics; keep for hydration/build provenance if needed. |
| Non-formal README/project documentation | Exclude from formalization search; optional separate metadata index | Not a formal theorem/definition result. Retain upstream and, if useful for maintainer/source discovery, index only in the separate metadata index. A README-named file in a prover source language remains primary content. |
| Prover-aware verified import-only module | **Keep until auxiliary search is live** | It owns no declaration/proof, but its module/path/comments are useful navigation. Move it out of primary only after the deployed search path actually preserves those signals. |
| `sorry`/`admit`/holes/axioms | **Keep** | A checked statement/interface is useful prior art even when proof completion is missing. |
| `generated/`, `ChallengeDeps`, autogenerated path | **Keep by default** | Generation provenance does not imply redundancy; many generated files contain unique declarations. |
| Tests/fixtures/examples/benchmarks | **Keep by default** | Can contain unique declarations, examples and proof patterns. Tag/downrank experimentally if useful. |
| Audit files | **Keep by default** | Can contain declarations/formal checks; role name alone is insufficient. |
| Roadmap/`Suggested` files | **Keep by default** | Often contain elaborated statements/definitions with holes, directly relevant to prior-art search. |
| Vendored/copied/forked paths | **Keep unless exact duplicate** | Vendoring is provenance, not proof of content identity. |
| Regex finds no declaration keyword | **Keep** | Cross-prover/Lean regexes are not sound declaration classifiers. |
| Proof traces/caches/session artifacts | Prover-specific review | Some are regenerable noise; others encode authored proof steps. Never apply a cross-prover blanket rule. |

## 4. Exact duplicate handling

Exact duplicate content is the safest large-scale cleanup class, but even here
the output model matters.

The search index may canonicalize a byte-identical content blob once, but the
result must retain all source/path aliases.  A duplicate in two repositories can
carry useful provenance: one may be upstream, another a course copy, a vendored
dependency, or the version a downstream source actually imports.  Canonical
selection must not imply an unsupported claim about which occurrence is the
"real" source.

Path/module aliases must remain **searchable**, not merely stored in a hidden
provenance table.  Formal libraries encode mathematical names heavily in module
paths; two byte-identical files can therefore contribute different retrieval
terms even though their file contents are identical.

Do not silently change "byte-identical" into a stronger equivalence relation.
Removing comments, normalizing whitespace, parsing/reprinting an AST,
alpha-renaming, or comparing declarations semantically can erase documentation,
names or syntax that is useful to a searcher.  Treat each broader equivalence as
a separate research hypothesis.

The separate whitespace-only exclusion does not weaken this rule.  `FD-015`
matches only nonempty formal-source files whose entire byte stream is removed by
`bytes.strip()`.  Such a file has no searchable textual content to normalize in
the first place.  A file containing even only a comment, TODO, import, hole,
declaration, or other non-whitespace byte is outside this class and remains
eligible unless some independent policy applies.

The 2026-09-14 audit found roughly 5,200 Lean files participating in exact-byte
duplicate groups, including about 2,623 files in groups spanning more than one
source.  One conspicuous generated example is the repeated `WorkspaceTest.lean`
harness in `leanprover__lean-eval`: hundreds of copies are byte-identical.  The
reason this class is safe to collapse is the hash identity, not the `generated/`
path.

## 5. Import aggregators

An umbrella module can be useful navigation but is normally not the owner of a
definition or theorem.  The correct primary result is usually the imported file
that contains the declaration.

Only call a file **pure import-only** after a prover-aware parse establishes that
its formal commands are imports and no declarations/notation/attributes/options
or other content-bearing commands are present.  Comments may still be useful
documentation; preserve them in the auxiliary representation and keep the
module/path name searchable.  If an import-only result is useful because its
name identifies the mathematical topic, the desired behavior is usually to use
that navigation signal to surface the imported owner file, not simply discard
the signal.

The 2026-09-14 deployment audit found that the first implementation violated
the second half of this rule.  `FD-005` correctly classified 2,711 Lean modules
and materialized them into a local `.zoekt-metadata` view, but production
publishing transferred only the primary `.zoekt` index and the live search
process was configured with only that primary index directory.  Thus the module
names, paths, comments, and imports were not searchable at all.  `FD-005` is
therefore superseded by `FD-016`: verified import-only modules remain in primary
search (and may also remain in the auxiliary view) until auxiliary retrieval is
deployed and tested end to end.  Parser correctness by itself is not sufficient
evidence for exclusion when the preservation channel is absent.

On the restored primary index, raw Zoekt ranking reproduces the original
import-aggregator crowding: for example, `SphereEversion.lean` enters ahead of
the judged theorem owner and moves that owner from rank 10 to rank 11.  The
deployed result policy therefore treats `FD-016` as a navigation role rather
than an exclusion rule.  It preserves every returned candidate and its Zoekt
score, stably orders ordinary formal-content hits before verified import-only
navigation hits, and labels the latter `navigation-import-only`.  This recovers
the measured owner-ranking benefit of the old hard filter without hiding the
module/path signal.  The raw `normalized_path_content_v1` control intentionally
does not apply this role ordering.

Do not use a regex such as "90% of lines begin with import" as the production
classifier.  The current audit uses such a heuristic only as a diagnostic.

There is a known qrel footgun: the current Bruhat--Tits query historically gave
owner-level credit to `chrisflav__bruhat-tits/BruhatTits.lean`, an import-only
root, although `BruhatTits/Graph/Tree.lean` contains the tree proof.  This was
recorded as ledger anomaly `A-20260914T062024Z-fb018b47`.  Correct owner semantics
before using aggregator suppression to claim an Owner-Hit improvement.

## 6. Incomplete formalization is still formal prior work

Do not filter `sorry`, `admit`, holes, axioms or equivalent constructs merely
because the proof is unfinished.  For this corpus, a useful hit can consist of:

- the exact theorem statement;
- a structure or class interface;
- definitions and notation surrounding the statement;
- a partially completed proof exposing the intended lemmas;
- a namespace/module path that reveals where related formal work lives.

The clean 2026-09-14 audit found many Lean files containing `sorry`/`admit`, and
one already-judged direct-owner Serre-duality result is among them.  Treat proof
completion as provenance, not a relevance filter.

## 7. Why `generated/` is not a safe filter

The clean audit found approximately 3.6k Lean files in generated-like paths.
Most were **not** exact duplicates, and thousands contained declarations.
`leanprover__lean-eval/generated/*/ChallengeDeps.lean`, for example, contains
substantial unique definitions and structures such as the Jordan-normal-form
formal interface and Tarski-geometry structures.  Those are exactly the kind of
formal prior work this corpus is intended to expose.

Generated boilerplate can still be removed when another invariant proves it is
redundant.  `WorkspaceTest.lean` is a good example: use its exact hash identity,
not its generated path, as the reason to canonicalize it.

## 8. README and documentation policy

README content is ambiguous in value, and the basename does not determine its
role. A non-formal `README.md`/`README.rst`-style document is not itself formal
mathematical content, so it should not normally occupy primary theorem-search
slots. A file such as `README.lean`, `README.thy`, `README.agda`, or
`Readme.lsp` is different: it is formal source and can contain definitions,
statements, examples, proofs, or reusable syntax. It must remain in the primary
formal-content channel unless a stronger independent invariant applies.

Non-formal README material can still help maintainers identify a source or
understand project layout.  That is a different information need from the site's
formalization search.  The repository may therefore retain such files in the
separate `.index-metadata` / `.zoekt-metadata` view for explicit maintainer-side
source-discovery queries.  That index is not published by `just publish`, is not
queried by the public API, and is never fused or appended into ordinary search
results.

An earlier 2026-09-14 implementation got this boundary wrong.  It first tried a
second deployed documentation backend and then replaced it with `docs__*` shards
inside the same Zoekt directory as formal source, plus an API endpoint whose
results the browser appended after formal hits.  The latter was not an auxiliary
index: it was one deployed search corpus with a segregated result class.  That
architecture is rejected.  FD-002 is now physically absent from the public
formalization index, and primary-index validation treats any residual `docs__*`
shard as an unregistered-source defect.

The associated lexical audit remains reproducible with
`scripts/audit-readme-searchability.py`; its 2026-09-14 result is committed as
`filtering/audits/readme-searchability-20260914.json`.  It found 831 of 3,000
sampled rare README terms absent from primary text.  This establishes only that
the documents contain different words.  It is **not** evidence of improved recall
for the site's intended task of finding formalized definitions, statements,
constructions, interfaces, or proofs, and must not be reported as a search-quality
gain.

The 2026-09-14 audit initially found over a thousand README-named files
physically present in the Zoekt index. That observation led to an overly broad
basename classifier; a subsequent audit found formal `README.*` modules in Lean,
Agda, Isabelle and ACL2. Only the non-formal documentation subset is safe to
move out of the primary index by this rule.

Likewise, declaration docstrings and source comments can be valuable query
signals and must not be stripped merely to reduce bytes or make deduplication
easier.  A statement's prose description may match a mathematician's query much
better than its internal declaration name.

### Formal-language build scripts are still formal source

Do not infer that a source-language file is safe to exclude merely because its
conventional role is build configuration. `lakefile.lean` is the concrete
counterexample: Lake configuration is written in ordinary Lean, and projects
frequently define helper functions, structures, inductives, instances, examples,
or other declarations in it. An exhaustive 2026-09-14 audit of the 498
`lakefile.lean` files then classified as build metadata found declaration syntax
in 125 files (including 577 `def`s, 13 inductives, 14 structures, 34 abbrevs,
8 instances, one example, and one axiom).

Most such declarations are likely operational build helpers, but the project
does not use likelihood as a hard-filter criterion. `lakefile.lean` therefore
stays in the primary formal-content index. Non-formal Lake metadata such as
`lakefile.toml`, `lake-manifest.json`, and `lean-toolchain` may still be excluded
by their format because they cannot contain Lean declarations or proofs.

## 9. Tests, audits, roadmaps and vendored material

These are role labels, not deletion proofs.

Tests and examples can encode minimal API use, unique theorem statements and
proof patterns.  Audit files can contain formal declarations or checks.  Roadmap
and `Suggested` files can contain elaborated statements with holes and are often
valuable evidence that somebody already designed the formal interface.  Vendored
copies can differ from upstream.

Tag these roles.  If they pollute ranking, measure role-based penalties.  Hard
filter only a narrower subset established by `FILTER-004`, such as an exact
duplicate or a prover-aware verified non-content file.

## 10. Proof-assistant-specific artifacts

Do not create a universal "generated proof artifact" blacklist.  `.prf`, session
files, compiled traces, generated theories and caches have different semantics
across systems.  Before excluding an extension or path family, determine:

1. whether it is authored or mechanically regenerated;
2. whether it contains theorem/definition statements or proof steps absent from
   the retained source representation;
3. whether users may search for syntax/names appearing only there;
4. whether an auxiliary proof/provenance index should retain it.

Only then write a prover-specific policy.

For ACL2, narrowing the initial broad `.sys` rule to
`*@useless-runes.lsp` was still not enough.  Those reports contain certification
proof metadata whose event names need not occur textually in the authored book.
An exhaustive 2026-09-14 audit found 589,709 distinct event identifiers in the
9,359 nonempty reports that were absent from every retained non-`.sys` ACL2
source file under a conservative token check.  The examples include generated
contracts, induction schemes, signatures, accessors and lemmas.  `FD-014` is
therefore superseded by `FD-017`: the reports remain primary-searchable as a
proof-metadata role.  Ranking may place them behind authored formal source, but
the query compiler must not blanket-exclude `.sys` paths.  `FD-004` and
`FD-014` remain only as historical ledger vocabulary.  The exact extraction and
comparison procedure is reproducible with `scripts/audit-acl2-useless-runes.py`;
the recorded corpus/source-revision result is
`filtering/audits/acl2-useless-runes-20260914.json`.

## 11. Repository-by-repository review catalogue

The large source-local filtering campaign uses
`filtering/repository-review/` rather than ad hoc shell exclusions.  The
catalogue is generated from the authoritative hydrated source trees, not from
`.index-primary`, so previously filtered material remains visible to later
audits.  Each imported file is recorded with path, size, SHA-256, formal-source
status, and the active filtering decisions that currently affect it.

Most repositories are one work unit.  Extremely large sources are partitioned
recursively by literal subtrees.  When a directory has many small sibling
subtrees, or too many direct files, those items enter deterministic SHA-256
buckets rather than order-sensitive sequential chunks.  A new sibling therefore
changes only its bucket unless that bucket itself must split; it does not shift
every later work-unit boundary.  Unit IDs are hashes of repository identity plus
that stable scope/bucket identity.  `batches.jsonl` groups work units for
execution, but batch identity is scheduling metadata, not filtering authority.

A completed unit review is append-only under `reviews/<repo>/<unit>.jsonl` and
has an explicit default disposition.  `default_action=retain` means every file
not named by an exclusion rule stays searchable.  `status=deferred` means the
unit remains open and activates nothing.  Exclusion rules may use only an exact
path, an explicit path set, or a literal subtree prefix.  Every rule must record
both the source-local rationale and the content invariant that establishes why
no useful definition, statement, proof, interface, or retrieval evidence is
being hidden.

The review is pinned to the unit's material snapshot.  If any file inside that
unit changes, appears, disappears, or moves, validation marks the review stale
and indexing stops until a new review revision supersedes it.  For a partitioned
large repository, unchanged sibling units remain valid.  This is the mechanism
that prevents an old blacklist from becoming a lazy permanent omission after an
upstream update.

Accepted exclusions materialize as `FD-018` per-file decisions in the ordinary
filter ledger.  `FD-018` is intentionally powerless by itself: it can only be
created from a fresh accepted review rule, and its evidence carries the review,
unit, rule, selector, unit snapshot, file hash, rationale, invariant, and
source-local evidence.  Thus the public index remains reproducible through the
same per-file filtering machinery while the reasoning stays attached to the
repository review that justified it.

A distinct whole-source disposition exists for repositories that fail the
`COPY-005` corpus-membership invariant.  A whole-repository unit may request
`source_action=retire-source` under `FD-012`; it may not combine that action with
file-level blacklist rules.  Applying the action removes the source from the live
inventory but deliberately preserves its hydrated checkout and freezes its
catalogue/manifests/review history as a retired campaign source.  Do not emulate
source retirement by blacklisting every file: that would hide a source-membership
decision inside file-level filtering and destroy the audit boundary.

The operational commands are:

```sh
just repository-review-catalogue
just repository-review-validate
just repository-review-status
just repository-review-batch RRB-0001
python scripts/repository-review.py template RRU-... > /tmp/review.json
python scripts/repository-review.py append /tmp/review.json
```

Only after the review catalogue validates should `just filter-state` be run to
materialize accepted blacklist rules into `FD-018` decisions and the append-only
filtering ledger.

## 12. Required workflow for a new hard filter

1. **Name the role precisely.** Avoid vague classes such as "generated junk".
2. **State the content invariant.** Explain why the rule cannot remove unique
   definitions/theorem statements/proofs.
3. **Implement classification separately from exclusion.** Produce counts and a
   manifest first.
4. **Record provenance.** For every candidate document retain source, path,
   classifier/policy ID and reason.
5. **Inspect counterexamples.** Sample across sources and proof assistants; for a
   semantic hard filter, prefer exhaustive verification of the affected class.
6. **Run a shadow/candidate index.** Do not mutate the only usable index first.
7. **Compare against frozen qrels and queries.** Use the scientific protocol in
   `evaluation/search/SCIENTIFIC_PROTOCOL.md`.
8. **Pool changed rankings.** `unjudged != irrelevant`; review new/removed top
   results rather than assuming the old qrels are complete.
9. **Record storage/performance separately.** Smaller/faster is not evidence of
   preserved mathematical recall.
10. **Archive the measurement and decision.** Use `evaluation/search/lablog.py`;
    the filter policy/version and affected counts belong in the permanent record.
11. **Deploy reversibly.** Keep the unfiltered source authoritative and preserve
    the exclusion manifest so the primary index can be rebuilt without the rule.

## 13. Review questions

Before approving any filtering PR, reviewers should be able to answer:

- Which `FILTER-###` policy authorizes this hard exclusion?
- Is the rule content-based or merely path/repository based?
- Could a theorem statement with an unfinished proof be removed?
- Could a generated file contain a unique declaration?
- Could a test/roadmap/audit file contain useful prior art?
- If content is deduplicated, where are all original aliases preserved?
- If navigation/documentation leaves the primary index, where can search still
  use it as metadata?
- Is the classifier prover-aware where required?
- Were unjudged changed results reviewed rather than treated as irrelevant?
- Is there a clean, timestamped measurement tied to the exact commit/index/qrels?
- Can the filtering decision be reversed and audited later?

If any answer is unclear, prefer retention plus role metadata/downranking over
hard exclusion.

## 14. Dated measurements are evidence, not permanent classification rules

Counts in this document and in the search ledger describe a particular corpus
state.  They justify what to investigate; they do not by themselves authorize a
future filter.  Sources evolve, generated pipelines change, and a role that was
boilerplate in one repository can carry mathematical content in another.

Re-run the data-quality audit on the current corpus before a filtering campaign,
tie the result to the exact commit/index state, and preserve old measurements as
history rather than rewriting the policy around the latest count.
