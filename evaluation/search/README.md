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
