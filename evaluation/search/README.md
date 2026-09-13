# Search quality evaluation

This directory is the regression harness for mathematician-facing retrieval.
Search changes are evaluated here before they are adopted by the public search
page.

## Gold set

`gold.json` contains natural-language queries and hand-reviewed relevant files.
The intended user is a mathematician asking whether a definition, theorem, or
construction has already been formalized.  A judgment is attached to a concrete
Zoekt repository identifier and file path:

- relevance 3: direct owner of the theorem/construction or an equally direct
  independent formalization;
- relevance 2: closely relevant implementation, specialization, or alternate
  development;
- relevance 1: supporting material (not currently used in the initial set).

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

## Reproducibility

The default evaluator calls the local Zoekt binary and local `.zoekt` shards,
not the hosted API.  Every report records a fingerprint of shard names, sizes,
and mtimes.  Comparisons refuse to attribute score changes to retrieval code if
the index fingerprint differs.

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

## Baseline

`frontend_lexical_v1` mirrors the current public default: split the user's text
on whitespace/quotes, turn every token into a mandatory `content:` regex term,
restrict to proof-source files, and search case-insensitively.  The committed
baseline is the score of that behavior before any retrieval improvement.

Do not replace this baseline in the same commit as a candidate retrieval change.
A candidate should receive a new variant name and be compared against the frozen
baseline on the same index.

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

## Initial measured baseline

On the 22-case initial gold set and the local index fingerprint committed in
`baselines/frontend_lexical_v1.json`, the current frontend behavior scores:

| Metric | Baseline |
| --- | ---: |
| owner Hit@10 (primary) | 0.136 |
| Hit@1 | 0.091 |
| Hit@5 | 0.182 |
| Hit@10 | 0.182 |
| Hit@20 | 0.364 |
| source Hit@10 | 0.864 |
| MRR | 0.152 |
| nDCG@10 | 0.110 |
| zero-result rate | 0.136 |

Two diagnostic slices are especially informative.  The two conversational
queries have zero results under the strict compiler.  The two synonym-tagged
queries have source Hit@10 = 1.0 but owner Hit@10 = 0.0: the corpus/source is
being found, but the useful file is not being ranked into view.  These are
predeclared targets for future query and ranking experiments.

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
unjudged files.  The current depth-10 pool combines the frozen frontend baseline, normalized
path/content lexical retrieval, frozen multi-query RRF, and the measured Cohere
reranker.  It has 414 unique query/file candidates: 32 already judged and 382
explicitly marked unjudged.  Unjudged does not mean irrelevant.

This follows the TREC test-collection model: pool top documents from diverse
runs, judge the pool, and keep qrels distinct from run output.  It also avoids a
known failure mode in neural retrieval evaluation where a new method appears
worse simply because many of its top results were never judged.

## Research directions after the lexical baseline

The measured experiments narrow the next branches:

- **Fielded lexical retrieval first.** Module/file paths are unusually valuable
  in formal libraries.  Restoring path evidence plus conservative query
  normalization raises owner Hit@10 from 0.136 to 0.500 on the initial qrels.
- **Semantic first-stage retrieval, not reranking alone.** For normalized
  path/content retrieval, owner Hit is identical at depths 20, 50, 100, and
  150 (0.545).  The missing owner files are absent from the lexical candidate
  set, so no reranker can recover them.  Dense retrieval, learned sparse
  expansion (for example SPLADE), or another independent first-stage signal is
  required for that residue.
- **Hybrid fusion.** Exact formal identifiers and semantic paraphrases are
  complementary.  Combine independent lexical/dense runs by a rank-based method
  such as Reciprocal Rank Fusion before learning score calibration.
- **Hierarchical retrieval.** Normalized lexical retrieval already has source
  Hit@5 = 0.955 while owner Hit@10 = 0.500.  This supports testing a cheap
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
- **Reranking only after candidate recall is high.** Once a hybrid first stage
  puts owner files into (say) the top 100--200 reliably, compare a cross-encoder
  or LLM reranker on owner Hit@10/nDCG@10, with latency and API cost recorded.
- **User-intent data should grow the benchmark.** Lean Finder reports gains from
  training/evaluating against real mathematician intents rather than only
  informalized theorem statements.  Real search failures from this site should
  therefore become future gold queries, with a held-out partition once the set
  is large enough for repeated tuning to overfit it.

Additional references:

- Anthropic, *Contextual Retrieval*:
  https://www.anthropic.com/engineering/contextual-retrieval
- TREC 2025 overview of relevance judgments and pooling:
  https://trec.nist.gov/pubs/trec33/papers/overview_33.pdf
- Lu et al., *Lean Finder: Semantic Search for Mathlib That Understands User
  Intents*: https://arxiv.org/abs/2510.15940
- Formal et al., *SPLADE v2*: https://arxiv.org/abs/2109.10086
- Jina Embeddings retrieval/late-interaction documentation:
  https://jina.ai/en-US/embeddings/
- Google Gemini Embeddings documentation (including code-retrieval task
  formatting): https://ai.google.dev/gemini-api/docs/embeddings
