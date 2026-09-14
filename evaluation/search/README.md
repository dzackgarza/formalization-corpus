# Search quality evaluation

This directory is the regression harness for mathematician-facing retrieval.
Search changes are evaluated here before they are adopted by the public search
page.

The permanent experimental record is governed by
[`SCIENTIFIC_PROTOCOL.md`](./SCIENTIFIC_PROTOCOL.md).  Timestamped immutable run
artifacts live under `runs/`; `ledger.jsonl` is the append-only chronology of
measurements, observations, hypotheses, decisions and anomalies.  Frozen files
under `baselines/` are convenient regression inputs, not substitutes for that
historical record.

## Gold set

`gold.json` contains natural-language queries and hand-reviewed relevant files.
The intended user is a mathematician asking whether a definition, theorem, or
construction has already been formalized.  A judgment is attached to a concrete
Zoekt repository identifier and file path:

- relevance 3: direct owner of the theorem/construction or an equally direct
  independent formalization;
- relevance 2: closely relevant implementation, specialization, or alternate
  development;
- relevance 1: supporting material;
- relevance 0: reviewed and nonrelevant to the mathematical information need.

Absence from the judgment list means **unjudged**, not relevance 0.  This
distinction matters during pooling: a reviewed negative candidate must not remain
indistinguishable from a candidate nobody has inspected yet.  Every query still
requires at least one positive judgment.

The first set is deliberately small and high-confidence.  It includes exact
names, ordinary mathematical prose, conversational questions, synonym shifts,
and cross-proof-assistant queries.  Probable negative queries are not included
in aggregate retrieval scores until absence has been independently established.

Gold edits and retrieval changes should be separate commits.  Do not repair a
retrieval regression by weakening or replacing its gold judgment.

## Metrics

The primary metric is **owner Hit@10**: the fraction of queries for which a
relevance-3 file appears in the first ten results.  This reflects the main user
need: reach an actual formalization rather than merely a repository-wide import
file that mentions its module name.

The report also records:

- Hit@1/5/10/20: at least one judged relevant file in the first `k` results;
- owner Hit@1/5/10/20: at least one direct-owner file in the first `k`;
- source Hit@k: at least one result from a source containing a judged file;
- gold Recall@k: fraction of the explicitly judged files retrieved by `k`;
- MRR and owner MRR: reciprocal rank of the first relevant/direct-owner file;
- nDCG@k: graded ranking score using the 1--3 relevance judgments;
- zero-result rate;
- query latency and result-payload bytes.

Precision is intentionally not a primary metric.  The corpus is large enough
that an unjudged result may still be genuinely useful, so treating all unjudged
files as false positives would make the initial sparse judgment pool look more
complete than it is.  nDCG is therefore a lower-bound ranking diagnostic, not a
claim that every unjudged result is irrelevant.

All metrics are also sliced by the query tags in `gold.json`.

### Deterministic and stochastic systems

The current lexical baseline is deterministic, but the evaluation protocol is
not.  Query expansion, generated contextualization, sampling-based retrieval,
LLM reranking, or future learned components may make repeated executions differ.
Keep two axes distinct:

- **rank cutoff K** describes one ranked execution: Success/Hit@K,
  Owner-Success/owner-Hit@K, Recall@K, MRR and nDCG@K;
- **trial count R** describes repeated stochastic executions.  For a fixed
  predicate such as Owner-Success@10, report the expected single-run success
  probability and Pass@R[Owner-Success@10].

For `n` sampled runs of one query, with `c` runs satisfying the success
predicate, `evaluate_repeated.py` uses the standard finite-sample pass estimator
`1 - C(n-c, R) / C(n, R)`.  Reports also carry query-level bootstrap confidence
intervals.  Never report only best-of-R performance: single-run expected quality
must remain visible, because Pass@R can improve merely by spending R times the
inference budget.

Repeated runs must use the same qrels, index fingerprint, query configuration,
and named retrieval variant.  Record model/version, temperature, seed when the
provider exposes it, candidate depth, and other sampling controls in each run
report.  A deterministic system is simply the degenerate one-run/no-variance
case of this protocol.

To aggregate repeated reports:

```sh
python evaluation/search/evaluate_repeated.py run-*.json --rank-cutoff 10 --pass-r 1,2,5,10
```

## Reproducibility

The default evaluator calls the local Zoekt binary and local `.zoekt` shards,
not the hosted API.  Every report records a fingerprint of shard names, sizes,
and mtimes, the Git commit, and the exact clean/dirty worktree state.  Comparisons
refuse to attribute score changes to retrieval code if the index fingerprint
differs.  Canonical ledger archival rejects dirty-tree reports by default.

Run:

```sh
just eval-search
just test-search-quality
```

`eval-search` prints the current report.  `test-search-quality` compares the
current retrieval scores with the committed baseline on the same index.  The
ordinary commit test validates the gold data without requiring a multi-gigabyte
index to exist in CI.

The production API can be measured separately:

```sh
python evaluation/search/evaluate.py --provider api
```

Latency from the local provider measures retrieval execution and JSONL output;
production browser latency should additionally be measured whenever the API or
rendering payload changes.

## Baselines

`frontend_lexical_v1` is the historical public behavior: split the user's text
on whitespace/quotes, turn every token into a mandatory `content:` regex term,
restrict to proof-source files, and search case-insensitively.  It is retained as
the before-state for the first measured search improvement.

`frontend_lexical_v2` is the deployed lexical baseline.  It uses the same
`site/search-query.json` normalization policy as the browser: conversational
intent words and punctuation are removed conservatively, proof-assistant names
can narrow the proof-source extension, and mathematical terms may match file/module
paths as well as contents.  `just test-search-quality` guards this baseline.

Do not replace a baseline merely because a candidate scores better.  A candidate
receives its own variant/report first; a deployed behavior receives a new baseline
only in the separate production-change step after the comparison is reviewed.

## Experimental protocol

1. Freeze the gold set and index fingerprint.
2. Run the baseline and candidate on every gold query.
3. Compare the predeclared primary metric, all secondary metrics, per-tag slices,
   latency, and payload size.  Do not select a metric after seeing the outcome.
4. Inspect changed rankings for the individual queries, especially gains that
   coincide with losses elsewhere.
5. Only then decide whether the candidate is an improvement.
6. Add corrected real user failures to the gold set over time; keep a held-out
   portion once the set is large enough that repeated tuning risks overfitting.

## Candidate strategies to measure, not assumptions to adopt

The existing evidence suggests a staged retrieval architecture is worth testing:

1. **Query normalization/rewriting.** Remove conversational scaffolding and
   normalize punctuation without destroying mathematical proper names.  The
   current strict conjunction is known to turn several natural questions into
   zero-result queries.  This is the cheapest experiment and should be measured
   before adding models.
2. **Lexical ranking improvements.** Preserve filename/path/declaration-name
   signals, penalize repository-wide import aggregators, and test whether a
   stronger lexical scorer improves direct-owner rank.
3. **Hybrid lexical + dense retrieval.** Retrieve lexical and embedding
   candidates independently and combine ranks (for example with reciprocal-rank
   fusion).  Exact identifiers and semantic paraphrases have complementary
   failure modes.
4. **Chunk context.** If a dense index is built, embed chunks with source name,
   file path, nearby declaration/section names, and enough enclosing context to
   identify what a chunk is about.  LLM-generated contextual prefixes are an
   experiment, not a prerequisite; deterministic mathematical metadata should
   be tried first.
5. **Reranking.** Rerank a larger candidate pool into the displayed top-k with a
   cross-encoder, late-interaction retriever, or small LLM.  Measure the added
   owner-Hit/nDCG against latency and API cost.
6. **Structure-aware chunks.** Compare fixed line/token windows with
   declaration-aware chunks where parser support exists.  Cross-prover support
   means this must be evaluated per proof assistant rather than assumed to help
   uniformly.

Available API credentials make dense retrieval and reranking feasible, but no
provider is selected in advance.  Embedding model, chunking, candidate-pool size,
fusion rule, and reranker must each be named experimental variables in reports.

## References behind the evaluation design

- Anthropic, *Retrieval Augmented Generation* cookbook:
  https://github.com/anthropics/claude-cookbooks/blob/main/capabilities/retrieval_augmented_generation/guide.ipynb
- Anthropic, *Contextual Retrieval* (hybrid lexical+dense retrieval,
  recall@20 evaluation, contextualized chunks, reranking):
  https://www.anthropic.com/engineering/contextual-retrieval
- Thakur et al., *BEIR* (heterogeneous evaluation of lexical, dense,
  late-interaction, and reranking systems): https://arxiv.org/abs/2104.08663
- Cormack, Clarke, Büttcher, *Reciprocal Rank Fusion*:
  https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
- Santhanam et al., *ColBERTv2* (late-interaction retrieval):
  https://arxiv.org/abs/2112.01488
- Lu et al., *Lean Finder: Semantic Search for Mathlib That Understands User
  Intents* (retrieval aligned to real mathematician query intent):
  https://arxiv.org/abs/2510.15940
- Gao et al., *LeanSearch v2: Global Premise Retrieval for Lean 4 Theorem
  Proving* (hierarchy-informalized corpus plus embedding/reranker retrieval):
  https://arxiv.org/abs/2605.13137
- Kurgan et al., *TheoremGraph: Bridging Formal and Informal Mathematics*
  (declaration name/signature representations plus dependency-graph expansion):
  https://arxiv.org/abs/2606.25363
- Lu et al., *Automated Formalization via Conceptual Retrieval-Augmented LLMs*
  (concept-definition knowledge base, query augmentation, hybrid retrieval and
  reranking): https://proceedings.iclr.cc/paper_files/paper/2026/hash/fd83f4e0dcaf1c64ea15bbb1695bb40f-Abstract-Conference.html

## Measured lexical baselines

On the 24-case gold set, including adversarial cases for mathematical uses of
words such as “formal” and “existence,” the original v1 behavior and the promoted
v2 lexical behavior score as follows on the same current index:

| Metric | v1 historical | v2 deployed |
| --- | ---: | ---: |
| owner Hit@10 (primary) | 0.167 | **0.625** |
| Hit@1 | 0.083 | **0.417** |
| Hit@5 | 0.292 | **0.708** |
| Hit@10 | 0.333 | **0.792** |
| Hit@20 | 0.500 | **0.792** |
| source Hit@10 | 0.792 | **0.958** |
| MRR | 0.179 | **0.548** |
| nDCG@10 | 0.125 | **0.419** |
| zero-result rate | 0.125 | **0.042** |

The historical conversational slice had zero results for both queries.  The v2
normalization fixes those lexical false negatives while preserving the exact-name
queries; synonym-shift queries still motivate the semantic/multi-query experiments
below.

The absolute scores rose after the first pooled-review pass added 13 source-backed
relevance judgments.  This is expected: previously unjudged direct formalizations
were not false positives.  The v2-over-v1 ordering remained large after that qrel
expansion.

The current baseline is measured on the filtered primary-content index introduced
by the corpus-hygiene experiment.  Against the immediately preceding raw-index
control on the same 24 queries and qrels, filtering raises deployed lexical-v2
owner Hit@10 from 0.583 to 0.625 while Hit@10 remains 0.792; nDCG@10 rises from
0.410 to 0.419.  Two subsequent safety audits narrowed overbroad filename/path
rules: formal prover sources such as `README.lean`, `README.thy`, `README.agda`,
and `Readme.lsp` remain primary content, as do all 498 `lakefile.lean` files.
ACL2 `.sys` filtering is now limited to the exact
`*@useless-runes.lsp` certification-report class.  The final conservative index
is 9,225,984,895 bytes, still about 11.7% smaller than the
10,451,699,803-byte raw control.  Restoring the formal README modules changed
none of the six measured metric sets; restoring `lakefile.lean` likewise leaves
the deployed lexical metrics unchanged, though the raw multi-query nDCG changes
slightly.  This is an important reminder that benchmark stability does not prove
a hard filter is recall-safe.  The immutable before/after/corrected reports and
superseding deployment decisions are recorded in `ledger.jsonl`; the individual
file-level decisions and reversions are in `filtering/ledger.jsonl`.

The public webserver also has a measured serving-quality parameter. Zoekt's JSON
handler derives internal per-shard match limits from `MaxDocDisplayCount` when no
explicit `ShardMaxMatchCount` is supplied; the display count is therefore **not**
a passive output-truncation knob. On this corpus, the previous display count of
60 implicitly produced a roughly 300-match shard budget and reduced deployed
lexical-v2 Hit@10 from 0.792 to 0.542 and Owner Hit@10 from 0.625 to 0.292. A
controlled sweep at fixed display count 60 found that an explicit shard budget
of 10,000 is the first tested value that exactly reproduces the unrestricted
local lexical metrics, both against a local stock webserver and the production
endpoint. The browser and evaluator therefore read the serving budget from the
same `site/search-query.json`; query-normalization and serving-budget provenance
are hashed separately in evaluation reports.

## Relevance-judgment pooling

The initial qrels are intentionally high-confidence but incomplete.  Absolute
ranking metrics can therefore underestimate a retriever that discovers a useful
file which has not yet been judged.  Follow the standard IR pooling workflow
before drawing strong conclusions from a new family of retrievers:

1. run several materially different retrieval systems on the same queries and
   index;
2. take the union of their top results at a fixed depth;
3. review those candidates independently of which system returned them;
4. add new relevance judgments in a **gold-only commit**;
5. regenerate the frozen baseline against the expanded qrels before the next
   retrieval-code comparison.

`build_pool.py` produces that review set without assigning relevance to
unjudged files.  Reviewed nonrelevant files are recorded explicitly as relevance
0 and reported separately from candidates still awaiting review.  The current
depth-10 pool combines the frozen frontend baseline, normalized
path/content lexical retrieval, frozen multi-query RRF, and the measured Cohere
reranker.  It has 443 unique query/file candidates: 63 judged relevant, 5 judged
nonrelevant, and 375 explicitly unjudged.  The gold set currently contains 84
judgments total; some judged files lie outside this depth-10 pool.  Unjudged does
not mean irrelevant.

This follows the TREC test-collection model: pool top documents from diverse
runs, judge the pool, and keep qrels distinct from run output.  It also avoids a
known failure mode in neural retrieval evaluation where a new method appears
worse simply because many of its top results were never judged.

## Research directions after the lexical baseline

The measured experiments narrow the next branches:

- **Fielded lexical retrieval first.** Module/file paths are unusually valuable
  in formal libraries.  The current combination of conservative query
  normalization, path evidence, and the safe primary-content filter raises
  owner Hit@10 from the historical v1 value 0.167 to 0.625 on the current qrels.
- **Semantic first-stage retrieval, not reranking alone.** For normalized
  path/content retrieval, owner Hit@20 is currently 0.625.  A pre-filter
  candidate-depth audit also plateaued at 0.625 through depths 50, 100, and 150;
  that deeper audit should be rerun against the filtered index before treating
  the exact plateau as current.  The general candidate-recall limitation remains
  directly testable: no reranker can recover an owner file absent from its
  candidate pool.
- **Hybrid fusion.** Exact formal identifiers and semantic paraphrases are
  complementary.  Combine independent lexical/dense runs by a rank-based method
  such as Reciprocal Rank Fusion before learning score calibration.
- **Hierarchical retrieval.** Normalized lexical retrieval already has source
  Hit@5 = 0.958 while owner Hit@10 = 0.625.  This supports testing a cheap
  source-first stage followed by stronger file/chunk retrieval within a handful
  of sources, rather than assuming every request needs a global dense scan.
- **Deterministic chunk context before generated context.** For file/chunk
  embeddings, include canonical source name, proof assistant, module path,
  namespace/section and declaration names.  Then measure whether LLM-generated
  chunk context adds anything beyond that deterministic mathematical context.
- **Late interaction is a separate experiment.** ColBERT-style/Jina
  multi-vector retrieval retains token-level evidence that a single dense
  vector may blur.  It should be compared as its own first-stage run, not
  silently substituted for dense embeddings.
- **Declaration-aware retrieval where parsers permit it.** For Lean and other
  systems with reliable declaration extraction, compare file/chunk retrieval
  against records containing declaration name, signature/type, docstring,
  namespace and dependency neighborhood.  TheoremGraph's results make this a
  stronger hypothesis than embedding arbitrary fixed source windows.
- **Train/evaluate on user intent, not only theorem paraphrases.** Lean Finder's
  gains come from modeling how mathematicians actually ask for library material.
  As this corpus accumulates real queries, keep a held-out user-query slice and
  use it before considering any domain-specific embedding fine-tuning.
- **Reranking only after candidate recall is high.** Once a hybrid first stage
  puts owner files into (say) the top 100--200 reliably, compare a cross-encoder
  or LLM reranker on owner Hit@10/nDCG@10, with latency and API cost recorded.

Additional references:

- TREC 2025 overview of relevance judgments and pooling:
  https://trec.nist.gov/pubs/trec33/papers/overview_33.pdf
- Formal et al., *SPLADE v2*: https://arxiv.org/abs/2109.10086
- Jina Embeddings retrieval/late-interaction documentation:
  https://jina.ai/en-US/embeddings/
- Google Gemini Embeddings documentation (including code-retrieval task
  formatting): https://ai.google.dev/gemini-api/docs/embeddings
