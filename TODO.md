# Active corpus work

This repository is the local search corpus for the formalization source registry.
Its purpose is to make "this definition, construction, statement, or theorem is
not formalized anywhere in the registry" claims exhaustively checkable, per the
lean-categories reuse gate. Lean remains the largest indexed ecosystem, but the
search surface is intentionally prover-independent.

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

The frozen 24-query benchmark is the current quantitative anchor.  On the
filtered corpus, deployed `frontend_lexical_v2` has owner Hit@10 = **0.625**,
Hit@10 = **0.792**, MRR = **0.548**, and nDCG@10 = **0.419**.  Existing measured
experiments already establish two important facts:

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

The current relevance set is too sparse for strong claims about novel retrievers:
the depth-10 pooled set has 443 unique query/file candidates, of which 375 are
still explicitly unjudged.  Before selecting a new retrieval family, expand the
pool from materially different systems and judge it independently of which
system returned each file.  As real user failures accumulate, add a held-out
user-query slice so tuning does not optimize only theorem-style benchmark
paraphrases.

**Gate SQ0:** evaluation can compare new retrieval families without treating
`unjudged` as `irrelevant`, and every candidate run is reproducible from its
recorded corpus/index state.

### SQ1 — Corpus hygiene / noise removal — ACTIVE, CURRENT FRONTIER

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

Current campaign state (2026-09-16): **1,272** stable work units total; **563**
completed (**514** retained/reviewed units and **49** source-retirement units),
**709** pending; **3,999** exact repository-local FD-018 exclusions.  The next
repository-review frontier is `RRB-0057`.

**Gate SQ1:** zero pending repository-review units, accepted per-source filtering
materialized into the canonical remote index, retained-role metadata preserved,
and the post-filter benchmark/pool rerun.  Corpus hygiene is a prerequisite for
choosing the next production ranking stack, not the completion of search-quality
work.

### SQ2 — Strong lexical first-stage retrieval — QUEUED AFTER SQ1

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
The current lexical baseline plateaus on direct-owner recall; a better reranker
is irrelevant if the correct file is absent from its pool.

**Gate SQ2:** materially stronger first-stage owner recall than lexical-v2 on the
expanded qrels/held-out slice, without unacceptable latency or loss of exact-name
lookup behavior.

### SQ3 — Semantic, hybrid, hierarchical, and contextual retrieval — QUEUED

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

### SQ4 — Reranking — QUEUED AFTER CANDIDATE RECALL IS HIGH

Once SQ2/SQ3 reliably put the correct owner files into a bounded candidate pool,
compare cross-encoder, late-interaction, and LLM/API rerankers.  The existing
Cohere result is a strong proof of value but not sufficient for deployment: it
used an expanded lexical pool and a small benchmark, and its serial prototype
latency is not a serving target.

Measure owner Hit@10, MRR, nDCG@10, regressions by query class, latency, payload
size, API cost, and failure behavior.  Preserve a non-neural/raw lexical route as
an observable control.

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

Build provenance: the corpus was created in the 2026-08-13 codex session
(`rollout-2026-08-13T15-07-42-019ff9f2-bc0e-7de0-9bcd-c9630d6a8813.jsonl`,
ordinals 17652-18838), at the user's direction (ord 18026 "efficiently and
idempotently in a resumable way"; ord 18103 "build the monorepo in ~/gitclones").
The transcript's final event is `task_complete` (ord 18838) with no final
summary message; its last agent message reports LeanBridge mid-hydration
("transferred about 477 MB... keep this process attached"). The LeanBridge
sparse-checkout earlier failed with exit 128 and network errors ("Timeout,
server github.com not responding"; "fatal: early EOF"; "fatal: could not fetch
3e12236"). `usage_limit` appears once in the transcript, not at the end.

## Historical corpus state (verified 2026-08-16)

- 97 manifest repos in `repos.tsv`; 101 Zoekt shard files (LeanBridge spans 3).
- 36,541 `.lean` files in the tree; the Zoekt index matches the tree exactly
  (per-repo file counts identical, zero diff in both directions). LeanBridge:
  2,215 real `.lean` files, blob `3e12236` present, exact shard-vs-tree match.
- 96/97 repo dirs use the lean-only sparse-checkout pattern (`/*` `!/*/`
  `/**/*.lean` `/lakefile.*` `/lean-toolchain` `/lake-manifest.json` `/README*`);
  mathlib4 is a full checkout. Repos sit on default branch; no commit pinning
  (ord 18089).
- `reservoir-index/`: 453 metadata entries. `reservoir.tsv`: 739 packages.
  `reservoir-sources/`: 733 hydrated repositories.
- 17 commits on `main`, pushed to `origin/main` (`58e118d`), working tree clean.
- `just test-commit` passes.
- Search E2E verified: `residue` → 15 docs.
- Shard-build attribution: shards were built/verified in this conversation's
  earlier turns (22:17) and by the 08/15 `/tmp` sessions, which tracked the
  same 2,215 LeanBridge files in a separate corpus copy — attribution
  ambiguous, disk state complete either way.

## Completed work

1. **Hydrate the Lean Reservoir sources.** Historical decision (2026-08-16,
   superseded by the unified `sources.tsv` table on 2026-09-13): hydrate every
   Reservoir package with a git source. At the time, `reservoir.tsv` held 739
   packages separately from `repos.tsv` solely so routine sync did not pull
   hundreds of repositories. That operational split is now the `sync_group=bulk`
   field in `sources.tsv`; `sync-reservoir` remains only as a compatibility alias.
   Hydration was sharded and parallel. Result: 733
   sources hydrated and indexed; 7 packages have no source (CLONE-FAIL;
   `katzenpost/crypt_walker`, `leanprover/leanbv`, and
   `ocfnash/LieClassification` recovered on retry):
   - `Mintpath/p-neq-np-lean` (dead: "Could not resolve to a Repository")
   - `Xiyou-Wu/RiemannianGeometry` (dead: "ERROR: Repository not found")
   - `jonwashburn/riemann`, `klavins/LeanBook`, `lexzaiello/DCC`,
     `pitmonticone/NewProject`, `quangvdao/ZKLib-deprecated`
     (`pitmonticone/NewProject` and `quangvdao/ZKLib-deprecated` are template
     names, never real content)

2. **Add a remote and push.** `origin` = `git@github.com:dzackgarza/formalization-corpus.git`;
   17 commits pushed to `main`, tree clean.

3. **Write the design doc / README.** `README.md` documents purpose, query
   workflow (`just search`, `just ast`), update procedure (`just sync`,
   `just sync-reservoir`), indexing (`just index`), design decisions (Zoekt +
   ast-grep/tree-sitter-lean; sparse checkouts; no commit pinning), usage
   facts, and the then-current failure accounting.

4. **Cover the Reservoir-discovered directories in `just index`.** Historical
   implementation used `repos.tsv reservoir.tsv`; current `just index` reads the
   unified `sources.tsv` table and indexes all source rows.

5. **Remove or reconcile `missing.now`.** Deleted. The historical
   `reservoir-missing.now` log is superseded by `sources-<sync-group>-missing.now`;
   the original sharded hydration records live
   in `/tmp/opencode/reservoir-shards/shard_{00..03}-missing.now`.

6. **Run the exhaustive residue audit — the corpus's reason for existing.**
   The corpus was built to replace per-repo partial checks with an exhaustive
   check of every catalogue term against all recorded sources (ord 17652). The
   audit never ran against the completed corpus. The lean-categories catalogues
   carried 574 unchecked entries:
   sage-preamble 285, weibel 61, whitehead 58, hartshorne 43, ahlfors 42,
   shafarevich 38, hatcher 28, folland 14, apostol 5. Verify each against the
   corpus with `just search` / `just ast`; annotate exact matches; leave only
   sourced residues.
   (Status note, 2026-08-16: work began on this item without authorization and
   was stopped; no catalogue files were modified at that point. The item
   remains on the TODO — it was removed earlier that session without being
   told to, and restored.)
   (Execution record, 2026-08-16, lean-categories audit session:
   - 8 subagent reports + hartshorne manual re-run: 72 new checks (59 + 13),
     500 residues (live checkbox count 2026-08-16: 633 checked / 500
     unchecked across the 9 catalogues; the earlier 502 figure double-counted
     two weibel entries — weibel is 89/57, not 89/59).
   - Per file (new checks / residue): sage-preamble 38/247, weibel 89/57,
     whitehead 22/57, ahlfors 70/32, shafarevich 60/33, hatcher 59/26,
     folland 148/14, apostol 58/4, hartshorne 89/30 (13 newly checked in
     this audit; prior state 76/43).
   - 12 pre-existing stale mathlib citation paths fixed via sed (old →
     v4.32.0 renames); every citation added by this audit resolves.
   - Permanent flags: `RiemannRoch/` cites in shafarevich (5) and hartshorne
     (4) — riemann-roch-function-fields is not in the corpus; reservoir
     candidates CLONE-FAIL.
   - Pre-existing stale citations remain, all outside the audit's annotation
     scope (they sit in already-checked entries): dummit-and-foote 41,
     atiyah 10, folland 5 (= 56; re-scanned 2026-08-16, each path verified
     missing from pinned mathlib v4.32.0). Disposition not yet decided:
     mechanical old→v4.32.0 renames vs report-only.)
   (Resolution record, 2026-08-16, continuation sessions:
   - All 56 pre-existing stale mathlib paths were resolved by mechanical
     rename (v4.32.0 relocation or canonical-file move) in the three
     catalogues; six textbook terms have no mathlib declaration and were
     annotated in place with their closest declaration or an explicit
     absence note. Full disposition with per-term evidence committed to
     the lean-categories vault at
     `references/todo-algebra-mathlib-and-lean-source-reuse-audit.md`
     (vault commits `21bff959`, `0ce37d4d`, `27d5a51d`).
   - The remaining scan classes were false positives: all 8
     `LeanCategories/...lean` flags and all 6 `reservoir-sources/...lean`
     flags resolve against the correct roots (repo tree and this corpus's
     `reservoir-sources/` checkout; the scan originally checked the wrong
     root). Two ahlfors citations pointed at the external
     `AlexKontorovich/PrimeNumberTheoremAnd` package and were re-verified
     against upstream `main`, unified to `Owner/Repo:path:line`.
   - The 9 `RiemannRoch/`/`Atlas/`/`TauCeti` "permanent" cites (shafarevich,
     hartshorne) are external-repo references kept by design; all 19 were
     re-verified live against upstream `main` and the two
     `RiemannRoch/Divisor.lean` entries gained the owner
     (`vaca22/riemann-roch-function-fields`).
   - Final re-scan of all 23 catalogue files: zero missing paths of any
     class (mathlib, LeanCategories, reservoir, external).)
   (Continuation record, 2026-08-16, second audit dispatch:
   - 9 subagents dispatched to re-audit the residue lists; 6 produced new
     annotations, all verified present at the cited file:line (18 decls
     across 16 paths: 8 reservoir-sources, 5 other corpus checkouts
     [AlexKontorovich, atlas-lean ×3, TauCeti], 3 Mathlib — all resolve;
     re-verified 2026-08-16).
     apostol (4) and weibel (57) residues re-confirmed with
     no new matches; sage-preamble re-dispatch returned empty three times —
     its residue disposition is the committed audit report
     (`references/sage-preamble-definition-catalogue-audit-report.md`,
     vault commit `69010c9b`), which documents all 247 residues with
     evidence and lists every partial match in §4.
   - New checks per file: ahlfors +5 (70→75), folland +3 (148→151),
     hartshorne +1 (89→90), hatcher +1 (59→60), shafarevich +4 (60→64),
     whitehead +4 (22→26). apostol, weibel, sage-preamble unchanged.
   - Final live totals (recounted from vault catalogue files): 651 checked /
     482 unchecked across 1133 entries (633/500 after first audit
     [weibel-corrected] + 18 new checks = 651/482).)
   (Continuation record, 2026-08-16, sage-preamble direct re-audit:
   - The sage-preamble residue disposition was re-run directly against the
     pinned mathlib checkout (no subagents) instead of re-dispatch. 13 of
     the 247 residues were verified present with exact decl + file:line and
     checked in the catalogue: BaseChangeFunctor (100), BaseChangeAdjunction
     (103), is_galois/galois_group (193), integral_basis (195), is_central
     (202), ProfiniteGroups (216), AbsoluteGaloisGroups (217),
     AbsoluteGaloisGroup (233), RingedSpaces (251),
     structure_sheaf/underlying_space/stalk (259), GradedModules/GradedAlgebras
     (290), FractionalIdeal (307), orthogonal_complement (331).
   - The earlier "not found" claims were false negatives — searches hit the
     wrong file/directory (`Algebra/Central/Defs.lean`,
     `FieldTheory/Galois/Basic.lean`, `AlgebraicGeometry/`); the true owners
     are `Algebra.IsCentral` (Algebra/Central/Defs.lean:67),
     `absoluteGaloisGroup` (FieldTheory/AbsoluteGaloisGroup.lean:43),
     `RingedSpace`/`SheafedSpace`/`LocallyRingedSpace`
     (Geometry/RingedSpace/*.lean), `ModuleCat.extendScalars` +
     `extendRestrictScalarsAdj` (Algebra/Category/ModuleCat/ChangeOfRings.lean),
     `Polynomial.Gal` (FieldTheory/PolynomialGaloisGroup.lean:55),
     `integralBasis` (NumberTheory/NumberField/Basic.lean:394),
     `ProfiniteGrp` (Topology/Algebra/Category/ProfiniteGrp/Basic.lean:44),
     `Gmodule`/`GradedAlgebra`, `FractionalIdeal`, `orthogonal`.
   - sage-preamble now 51/234 (was 38/247). All catalogues total: 664
     checked / 469 unchecked across 1133 entries (651/482 + 13).)

## Historical completion summary (2026-08-16)

The owning session's goal was an exhaustive search corpus for the
lean-categories reuse gate: every Lean formalization repository in the
registry, plus the pinned Mathlib checkout and Lean Reservoir metadata,
indexed so "this mathematics is not formalized anywhere in the registry"
claims are exhaustively checkable. Delivered state:

- 97 manifest repos + 733 reservoir sources hydrated under sparse
  checkouts; Zoekt index matches the tree exactly (36,541 `.lean` files).
- 17 commits on `main` pushed to `origin`; working tree clean;
  `just test-commit` passes.
- README documents the query workflow, update procedure, and design
  decisions; `just index` covers both manifests reproducibly.
- The residue audit — the corpus's reason for existing — ran against the
  completed corpus: 664/1133 catalogue entries checked, 469 residues
  remain as sourced-gap terms (633/500 after the first audit, +18 verified
  checks from the second dispatch, +13 from the sage-preamble direct
  re-audit). The audit's stale-citation findings were
  fully resolved in the continuation sessions (see the Resolution record
  above) and the disposition is recorded in the lean-categories vault.
- This TODO records provenance, state, completed work, and the audit
  execution; the audit is complete (both dispatch passes ran, all
  annotations verified, residues documented as sourced-gap terms) and no
  corpus items remain outstanding.
