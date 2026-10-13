# Active corpus work

This repository is the local search corpus for the formalization source registry.
Its purpose is to make "this definition, construction, statement, or theorem is
not formalized anywhere in the registry" claims exhaustively checkable, per the
lean-categories reuse gate. Lean remains the largest indexed ecosystem, but the
search surface is intentionally prover-independent.

## Build the index with bounded local source storage

`just source-refresh-index` and the scheduled `index` GitHub workflow rebuild one
source at a time: each source whose catalogue entry or filter decisions differ from
its provenance record in `lean-corpus/index-provenance/` on the search host is
hydrated at its catalogued revision, indexed, installed, and released. A run that
stops resumes from the recorded provenance. The auxiliary metadata shards are not
yet built per source.

The current `just index` dependency on `filter-views` materializes views across
the hydrated corpus. `filter-state`, `filter-validate`, and repository-review
validation also use corpus-wide state. Make these stages work per source while
preserving cross-source duplicate aliases and the existing review freshness
rules. Update sync, metrics, and publish so routine operation does not require
all source checkouts at once. Verify a full index against the registered source
inventory and its retained provenance before releasing existing checkouts.

## Current expansion (2026-09-13)

- `sources.tsv` is now the single canonical source inventory: 909 independent
  sources, one row each. It replaces the former `repos.tsv`, `reservoir.tsv`,
  and `port-sources.tsv` split. Operational differences live in fields instead:
  `proof_assistant`, `transport`, `sync_group`, and `discovered_via`. The current
  sync groups are 126 routine sources, 738 bulk sources, and 45 cross-prover
  sources. Discovery through Reservoir is provenance, not a source category.
- Inclusion is based on reusable formal content, not headline-theorem status.
  Definitions, structures, interfaces, formal semantics, specifications,
  theorem statements, constructions, and proofs all count as prior art.
- The cross-prover baseline now includes the major library/archive surfaces:
  UniMath and agda-unimath, MathComp and MathComp Analysis, Rocq stdlib,
  Agda stdlib and agda-categories, Isabelle/HOL and AFP, HOL Light and HOL4,
  the current Mizar Mathematical Library, `set.mm`, ACL2 Community Books,
  NASALib/PVS, and Twelf, plus substantial theorem- and semantics-scale
  developments recorded in `SOURCES.md`.
- `sync-manifest.zsh` reads `sources.tsv`, filters by `sync_group`, selects
  proof-source extensions by `proof_assistant`, and supports GitHub, GitLab, and
  the current Mizar HTTP distribution. Existing checkout directories are
  preserved; table unification does not require recloning.
- Cross-prover hydration and indexing completed on 2026-09-13: all 45 manifest
  sources have Zoekt shards and the sparse source trees contain 76,700 formal
  source files — Rocq 11,349; Agda 7,914; Isabelle 14,355; HOL Light 2,003;
  HOL4 5,133; Mizar 1,500; Metamath 96; ACL2 28,666; PVS 4,680; Twelf 1,004.
  Representative lexical searches were verified against UniMath, agda-unimath,
  AFP, HOL Light, HOL4, MML, `set.mm`, ACL2, NASALib, and Twelf. `just
  sync-cross-prover` refreshes that sync group and `just index-cross-prover`
  refreshes only its shards. The old spellings remain compatibility aliases.
  The August completion record below is retained as historical
  provenance, not a description of the current corpus boundary.

## Search-quality convergence programme — primary workstream

The end goal of this repository is **high-recall, low-noise prior-art search for
formal mathematics**.  The repository-review catalogue and filtering ledger are
not the product and are not an administrative end state: they are the first
stage of a retrieval-quality programme.  Search results are currently useful but
still substantially too noisy, and the deployed lexical retriever still misses
known direct-owner files.  Work must therefore flow through the following state
machine rather than stopping after corpus hygiene.

The frozen 24-query benchmark is the current quantitative anchor.  After the
complete repository-review campaign, deployed `frontend_lexical_v2` on the
canonical remote index has owner Hit@10 = **0.583**, Hit@10 = **0.750**, MRR =
**0.539**, and nDCG@10 = **0.406**.  Existing measured experiments establish two
important facts:

- frozen Gemini multi-query expansion + reciprocal-rank fusion raises owner
  Hit@10 to **0.750** and removes zero-result queries by increasing candidate
  recall;
- reranking a 30-document expanded pool with Cohere `rerank-v4.0-fast` reaches
  owner Hit@10/Hit@20 = **0.958/0.958**, Hit@10 = **1.000**, and nDCG@10 =
  **0.718** on the current judged set, but reranking cannot recover a relevant
  file that the first stage never retrieves.

Those experiments are evidence about architecture, not a deployment decision.
The long-horizon programme is:

### SQ0 — Evaluation and provenance foundation — ACTIVE/ESTABLISHED

Keep the existing scientific protocol intact while the corpus changes.  Every
retrieval experiment must name the corpus/index fingerprint, query/gold version,
retriever, model/version where applicable, latency, and cost.  Gold/qrel edits
remain separate from retrieval-code changes.

The current relevance set is still too small for strong claims about novel
retrievers, but independent pooling is now materially broader: the 24-query gold
set contains **2,608** explicit query/file judgments.  The accepted lexical
reference and its otherwise identical control have completed the predeclared
pooling campaign through displayed depth 100: their current union contains
**2,485/2,485** judged candidates (1,314 relevant and 1,171 nonrelevant).  The
earlier SPLADE++ query-expansion differential pool added 147 judgments in one
source-blind review pass: 34 relevant alternatives (17 relevance-1 and 17
relevance-2) and 113 nonrelevant files, with no new direct-owner judgments.
Do not deepen the same lexical pool merely to create more qrels; new pooling
should come from a materially different retrieval family and remain independent
of which system returned each file.  As real user failures accumulate, add a
held-out user-query slice so tuning does not optimize only theorem-style benchmark
paraphrases.

**Gate SQ0:** evaluation can compare new retrieval families without treating
`unjudged` as `irrelevant`, and every candidate run is reproducible from its
recorded corpus/index state.

### SQ1 — Corpus hygiene / noise removal — COMPLETE

Complete the repository-by-repository review below.  This stage removes only
source-local material that can be excluded with a high-confidence
content-level argument, and records ambiguous-but-valid roles for later ranking
rather than deleting them.  Typical targets are build/CLI wrappers, generated
reports, documentation-only scaffolding, dead commented code, linter/project
maintenance machinery, and other files shown by inspection to contain no useful
definition, statement, proof, interface, or prior-art signal.

This is the urgent current work because garbage in the candidate corpus degrades
every later lexical, dense, and reranking experiment.  It must not become a
blanket path-name cleanup: test/tutorial/generated/deprecated/benchmark/import
files remain when they contain useful formal content.  Role tagging and
reversible downranking are preferred when hard exclusion is not lossless.

Final campaign state (2026-09-17): **1,272** stable work units total; **1,272**
completed (**1,145** retained/reviewed units and **127** source-retirement units),
**0** pending; **6,908** exact repository-local FD-018 exclusions.  All accepted
source-local decisions were materialized into the canonical remote index, the
source caches were dehydrated after their review batches, and the required
post-filter production benchmark/pool rerun is recorded in the search ledger.

**Gate SQ1 — PASSED:** zero pending repository-review units, accepted per-source
filtering materialized into the canonical remote index, retained-role metadata
preserved, and the post-filter benchmark/pool rerun completed.  Corpus hygiene is
a prerequisite for choosing the next production ranking stack, not the
completion of search-quality work.

### SQ2 — Strong lexical first-stage retrieval — ACTIVE, RESOURCE-BOUND FRONTIER

Replace the assumption that raw Zoekt ranking is the best lexical scorer with a
measured fielded information-retrieval stage.  Evaluate mature implementations
rather than hand-rolling a scoring engine.  At minimum compare:

- BM25 and TF-IDF/BM25-family scoring over source content;
- separately weighted fields for repository/source, file/module path,
  declaration name, namespace/section, signature/type, docstring/commentary, and
  body text where parser support exists;
- explicit boosts for exact formal identifiers and canonical module/path hits;
- reversible penalties for known noisy roles such as import/navigation modules
  and proof metadata, without removing them from candidate recall;
- learned sparse retrieval (for example SPLADE-family methods) as a separate
  experiment if ordinary BM25/fielding plateaus.

Compare candidate recall at depths 10/20/50/100/200, not only displayed top-10.
The current post-review lexical-v2 baseline has a measured direct-owner plateau:
Owner Hit@10/20/50/100/200 is **0.583 at every cutoff**.  Zoekt's built-in BM25
scorer is rejected under identical normalized query semantics, and an independent
corpus-wide SQLite FTS5 BM25 channel established that a genuinely different
lexical scorer adds useful candidates.  After field-channel ablations and
independent differential-pool judgment, the provisional lexical reference is the
two-channel **baseline+path Zoekt** retriever fused with corpus-wide FTS5 by
qrel-independent pair-RRF.  On the current expanded qrels its direct first stage
reaches Owner Hit@10/20/50/100/200 =
**0.875/0.958/1.000/1.000/1.000**, Source Hit@10 = **1.000**, and the exact-name
slice reaches Owner Hit@10/20 = **0.833/1.000**.  Retrieval-component latency is
still high at about **6.63 s p50 / 19.89 s p95**, so this is not yet a production
serving decision.

The first learned-sparse probe used SPLADE++ only as a qrel-independent query
expansion bridge into corpus FTS5; it is explicitly **not** a document-side
SPLADE dot-product index.  After judging its 147-candidate differential pool, it
remains materially weaker at Owner Hit@10/20/50/100/200 =
**0.625/0.667/0.750/0.833/0.917**, so that bridge is rejected as the SQ2
replacement.  Do not infer that a full SPLADE index has been tested.  The first
response-depth probe capped both retrieval backends at 100 while retaining 100
candidates per retriever.  It reduced first-stage response payload but changed
the fielded-Zoekt ranking (including Owner Hit@20 changing from 0.958 to 1.000),
so it is rejected as a transparent transport optimization under the predeclared
ranking-identity criterion.  A two-worker client-side run of the unchanged
depth-200 baseline/path requests is ranking-preserving on the recorded top 20
and all measured owner cutoffs, but does not improve direct Zoekt latency
(p50 6.51 s versus 6.49 s; empirical 23rd-of-24 latency 13.67 s versus 13.02 s),
so request scheduling is also rejected as the SQ2 latency lever.  A subsequent
deterministic corpus-FTS5 path-prefix channel is also rejected: relative to plain
corpus BM25, Owner Hit@10/20 falls from **0.792/0.875** to **0.750/0.833**, the
exact-name Owner Hit@20 falls from **1.000** to **0.833**, and FTS5 p95 latency
rises from about **391 ms** to **543 ms**.  The immediate frontier is therefore
the materially richer deterministic structure-local representation already
available from source text.  The first syntax-agnostic matched-line probe was
negative: adding a fourth line-local FTS5 evidence channel to the accepted
ranker lowers Owner Hit@10 from **0.958** to **0.917**, Owner Hit@1 from
**0.458** to **0.375**, owner MRR from **0.612** to **0.571**, and nDCG@10
from **0.675** to **0.647**, while exact-name Owner Hit@10 remains 1.000.
Do not tune that channel's line limit or fusion weight against the current
qrels.  The source-hierarchy follow-up is positive at the first stage.  Adding
one equal-weight repository-rank channel derived only from each repository's
best fielded and corpus-BM25 file ranks raises first-stage Owner Hit@10/20 from
**0.875/0.958** to **0.917/1.000** and owner MRR from **0.6204** to **0.6243**,
while Source Hit@10 and depth-200 owner coverage remain **1.000**.  The exact-name
first-stage slice preserves Owner Hit@10/20 = **0.833/1.000**.  After the fixed
content reranker, Owner Hit@5 rises from **0.792** to **0.833**, Owner Hit@10/20
remains **0.958/1.000**, and nDCG@10 rises slightly from **0.675** to **0.677**;
final owner MRR is essentially flat/slightly lower (**0.6119 -> 0.6113**), so
this does not settle the second-stage ordering problem.  Accept the source-rank
channel as the qrel-independent first-stage reference and do not tune its weight.
The accepted run and its otherwise identical lexical control have now completed
the predeclared independent pooling campaign through displayed depth 100.  Their
current depth-100 union contains **2,485/2,485** judged query/file candidates:
**1,314** relevant (802 relevance-1, 415 relevance-2, 97 relevance-3) and
**1,171** nonrelevant, within **2,608 total qrels**.  On a fresh same-index rerun,
the source-hierarchy first stage still improves Owner Hit@10/20 to
**0.917/1.000** from **0.875/0.958** and owner MRR to **0.6243** from **0.6204**.
Its judged gold Recall@10/20/50/100 is
**0.1819/0.3146/0.5996/0.8285** versus
**0.1675/0.2971/0.5697/0.8166** for the two-channel lexical control, while the
exact-name first-stage slice remains Owner Hit@10/20 = **0.833/1.000** for both.
After the fixed content reranker, Owner Hit@5 remains improved (**0.833 versus
0.792**), Owner Hit@10/20 is **0.958/1.000** for both, and nDCG@10 is
**0.6056 versus 0.6029**.  Retain the fixed source-hierarchy channel and stop
deepening this same pool or tuning its weights on these qrels; advance from pool
expansion to the next documented search-quality gate.
The first parser-backed declaration/signature probe is negative as a global
equal-weight second-stage channel.  Lean declaration/type/member captures from
the repository's existing tree-sitter parser lower final Owner Hit@10/20 from
**0.958/1.000** to **0.917/0.917**, lower nDCG@10 from **0.677** to **0.621**,
and increase p50/p95 component latency from about **9.71/24.99 s** to
**11.75/32.79 s**.  Exact-name Owner Hit@10/20 remains **1.000/1.000**, but the
cross-prover slice falls from **1.000/1.000** to **0.750/0.750** because a
Lean-only global channel changes competition against unsupported provers; in
particular the Mizar Jordan-curve owner moves from rank 9 to 21.  Reject that
construction without weight tuning.  The source-local follow-up also fails its
predeclared gate.  Projecting the Lean declaration/signature preference only
within fixed repository slots preserves the cross-prover Owner Hit@10/20 cutoffs
at **1.000/1.000** and raises final Owner Hit@5 from **0.833** to **0.875**, but
Owner Hit@20 falls from **1.000** to **0.958** because the mapping-cone owner moves
from rank 13 to 54; nDCG@10 falls from **0.677** to **0.664**, and p50/p95
component latency rises to about **11.81/28.08 s**.  Reject parser-backed
declaration ordering in both global and source-local forms without weight/context
tuning.  The independent semantic first-stage branch is now **resource-deferred**:
an inventory of the canonical remote search host found the existing Zoekt/API and
complete corpus-FTS5 runtime, but no already-present semantic/vector service,
index, neural retrieval runtime, or provider-backed semantic surface.  Do not
substitute connector-local model downloads, model caches, throwaway environments,
or dense/learned-sparse indexes for that missing remote capability.  Resume this
branch only when an existing remote semantic service/index is connected or an
explicit remote-runtime deployment is available.  Meanwhile keep the accepted
source-hierarchy lexical reference fixed, continue independent pooling/evaluation
work that does not require local neural state, and do not tune fusion weights
against the qrels; a better reranker remains irrelevant when the correct file is
absent from its pool.  A low-latency structural fallback also fails its
predeclared gate.  Applying the same fixed source-hierarchy mechanism to the
single corpus-FTS5 stream keeps retrieval near the plain FTS5 control
(p50/p95 **0.134/0.385 s** versus **0.136/0.375 s**) and leaves exact-name Owner
Hit@10 at **0.667**, but lowers overall Owner Hit@10 from **0.792** to **0.708**
and owner MRR from **0.5128** to **0.5117**, despite improving Owner Hit@20 from
**0.875** to **0.958**.  Reject that standalone hierarchy without weight/cutoff
tuning.  The fast control remains plain corpus FTS5; the stronger lexical
reference remains the accepted multi-channel baseline+path Zoekt plus corpus-FTS5
source-hierarchy construction.

**Gate SQ2:** materially stronger first-stage owner recall than lexical-v2 on the
expanded qrels/held-out slice, without unacceptable latency or loss of exact-name
lookup behavior.

### SQ3 — Semantic, hybrid, hierarchical, and contextual retrieval — RESOURCE-DEFERRED

Build an independent semantic first-stage signal and fuse it with lexical search.
The experiments must separately measure the choices below rather than bundle
them into one opaque system:

- dense embeddings over file/chunk records;
- deterministic contextualization first: source name, proof assistant, canonical
  module path, namespace/section, declaration name and type/signature, nearby
  declaration names, and dependency neighborhood where available;
- LLM-generated contextual prefixes only as a measured follow-up to deterministic
  context, not as a prerequisite;
- declaration-aware chunks for Lean and other provers with reliable parsers,
  compared against fixed token/line windows;
- source-first/hierarchical retrieval, motivated by the existing high source
  Hit@5 versus lower direct-owner file recall;
- hybrid lexical+dense fusion, initially with rank-based fusion such as RRF rather
  than uncalibrated score addition;
- late-interaction/multi-vector retrieval (ColBERT/Jina-style) as its own
  candidate family rather than silently substituting it for ordinary dense
  embeddings.

**Gate SQ3:** hybrid/semantic retrieval raises first-stage direct-owner recall
beyond the best lexical system and keeps exact identifiers competitive; candidate
pool size, storage, latency, API/GPU cost, and cross-prover coverage are recorded.

### SQ4 — Reranking — RESOURCE-DEFERRED AFTER CANDIDATE RECALL

Once SQ2/SQ3 reliably put the correct owner files into a bounded candidate pool,
compare cross-encoder, late-interaction, and LLM/API rerankers.  The existing
Cohere result is a strong proof of value but not sufficient for deployment: it
used an expanded lexical pool and a small benchmark, and its serial prototype
latency is not a serving target.

Measure owner Hit@10, MRR, nDCG@10, regressions by query class, latency, payload
size, API cost, and failure behavior.  Preserve a non-neural/raw lexical route as
an observable control.

Current execution is resource-deferred here as well.  The canonical search host
has no reranker/vector service or provider-backed model client, and neither the
search-host service environment nor the connector workflow currently exposes a
Cohere or alternative reranker credential.  The historical Cohere evaluator
therefore cannot be rerun against the current corpus without adding a new remote
provider/runtime.  There is also no recorded real-user query stream from which to
form the required held-out user slice.  Do not substitute connector-local model
downloads, throwaway model environments, stale-index Cohere scores, or invented
"user" queries for either missing input.  Resume this gate when a permitted
remote reranker/provider and an authentic held-out query source are available.

**Gate SQ4:** a reranker gives a robust top-k gain on expanded judgments and held-
out user queries at an operationally acceptable cost/latency envelope.

### SQ5 — Production serving and continuous quality loop — QUEUED

Only after the retrieval stack is selected should serving be optimized around it:
parallel candidate generation, caching, bounded payloads, remote index placement,
and graceful degradation when model/API components are unavailable.  Deploy as a
named new retrieval variant, retain the previous baseline, and continue pooling
real failures back into the evaluation set.

The detailed experimental protocol and existing measurements live in
`evaluation/search/README.md` and `evaluation/search/experiments/README.md`.
Those files are evidence and experiment logs; **this section is the authoritative
execution order and convergence DAG for the search-quality workstream.**

## Repository-by-repository filtering review (started 2026-09-15)

The next corpus-hygiene phase is an exhaustive source-local review of imported
material. The durable work surface is `filtering/repository-review/`; it is
derived from authoritative hydrated checkouts rather than the already-filtered
search index. The current catalogue covers 889 campaign sources and
221,247 imported files (5,889,982,886 bytes) in 1,272 stable work units. Very
large repositories are split into bounded, stable hash-partitioned subtree/file
buckets so one new sibling does not renumber later work; ordinary units
are capped at 2,000 files and 256 MiB. The current plan groups the frontier into
122 deterministic batches, each with at most 12 units and at most 2,997
baseline-primary files.

For each unit, review must record an explicit default disposition (`retain` for
a completed review or `defer` for an open one) and any targeted blacklist rules
with source-local reasoning, a content-level losslessness invariant, evidence,
and literal selectors. Accepted rules are snapshot-pinned, may not silently carry
across changed material, and materialize as per-file `FD-018` decisions in the
ordinary filtering ledger. The batch is complete only when every unit has a fresh
explicit review record; number of exclusions is not a progress metric.  Current
progress and the reason this campaign exists are tracked in SQ1 above.

Commands: `just repository-review-status`, `just repository-review-batch
RRB-0001`, `python scripts/repository-review.py template RRU-...`, and
`python scripts/repository-review.py append /tmp/review.json`.

### Sparse source residency and connector-box storage (2026-09-15)

The source directories named by `sources.tsv` are **not Git submodules** of this
repository. They are disposable shallow/sparse nested checkouts used as intake
material. Their source text is not the persistent search representation: once a
repository has been reviewed and indexed, its **remote search-host Zoekt shard** plus the
committed repository-review catalogue/manifests/ledger are sufficient to keep it searchable
and auditable while the connector checkout is absent. Treat an absent source checkout
as a normal **ghost/dehydrated source**, not as corpus loss.

The intended long-horizon lifecycle is source-local and streaming:

1. hydrate exactly the source/review unit currently being inspected;
2. inspect it and record snapshot-pinned retain/exclude decisions;
3. materialize that source's filtered view;
4. build or replace only that repository's Zoekt shard(s);
5. remove the temporary filtered view and dehydrate the source checkout again.

The same principle applies to initial seeding: there is no requirement for all 885
source trees to coexist. A seed pass may hydrate, catalogue, filter, and index one
source (or a bounded batch) at a time and immediately dehydrate it before proceeding.
A from-scratch all-source hydration is therefore an optional convenience, not part
of the storage model.

The connector host must **not** carry a persistent full `.zoekt` mirror. The roughly
10 GB primary index lives on the droplet/search host; connector disk usage should return
to Git/audit/tooling state after each batch. Hydrated source checkouts, `.index-primary`,
`.index-metadata`, and newly built shard files are all bounded transient state. This keeps
the long-horizon worker viable even on a disk-constrained connector.

**Implemented source-cache workflow:** the long-horizon path is now first-class.
`just review-batch-hydrate RRB-NNNN` hydrates only the repositories in that review
batch at their catalogue-pinned revisions; `just review-filter-state RRB-NNNN`
materializes accepted FD-018 changes from committed manifests without scanning ghost
sources; `just review-batch-reindex RRB-NNNN` builds only those repositories' Zoekt shards in a
transient local staging directory and atomically replaces their shard set on the search
host; and `just review-batch-dehydrate RRB-NNNN` removes the source caches and temporary
hard-link views again. `just publish-index` only verifies the already-published remote shard
set; it must never `rsync --delete` from a connector-local `.zoekt` directory.

The legacy `just index`, `filter-views`, and full `repository-review.py build` remain
explicit whole-corpus maintenance/reproducibility commands. They are not the normal
review path. Repository-local upstream refreshes use
`python scripts/repository-review.py build --repository REPO`; from-scratch index
bootstrap uses `just source-seed-index fresh`, which streams one pinned source at a
time and dehydrates it immediately after its shard is accepted.

## Historical provenance

The August 2026 initial corpus build and the LeanCategories reuse-audit are
closed historical work. Their detailed hydration failures, transcript ordinals,
per-catalogue counts, stale-path repairs, and acceptance receipts remain in Git
history and in the canonical LeanCategories audit references; they are not live
selection or progress state for this repository.

Do not use the former `repos.tsv`/`reservoir.tsv` split, August source counts, or
the old "no corpus items remain outstanding" conclusion as present completion
evidence. `sources.tsv` is the current corpus inventory, and the active work is
the SQ0–SQ5 search-quality programme and repository-review state above.
