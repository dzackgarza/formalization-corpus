# Search-quality scientific protocol

Search ranking is an empirical system.  Changes to query normalization,
contextualization, embedding models, chunking, fusion, reranking or learned
components are therefore experiments, not ordinary UI tuning.  Every claim
about search quality must be recoverable from timestamped data tied to an exact
corpus state.

The same rule applies before retrieval tuning: audit the indexed material itself.
Do not attribute poor rankings to a search algorithm until file-role pollution,
generated material, aggregators, duplication and other corpus-quality effects
have been measured.  Data-quality role heuristics are diagnostics, not relevance
judgments; test proposed filters against qrels before changing ingestion.

## The permanent record

`ledger.jsonl` is the append-only chronological record.  It contains four kinds
of entries:

- **measurement** — an immutable evaluator report plus its principal metrics;
- **observation** — a factual pattern seen in one or more measurements;
- **hypothesis** — a proposed explanation or prediction to test next;
- **decision** — a production or experimental choice justified by earlier
  records;
- **anomaly** — a suspected measurement/data/tool failure that must not silently
  become a search conclusion.

Measurement records point to complete immutable JSON artifacts in `runs/` and
store the artifact SHA-256.  Notes cite earlier ledger record IDs in `evidence`.
Do not edit old ledger lines or old run artifacts to make later conclusions look
cleaner; append a correcting observation instead.

All times are UTC ISO-8601.  Each measurement carries at least:

- report timestamp and Git commit;
- clean/dirty worktree state and state fingerprint for new-format reports;
- qrel (`gold.json`) SHA-256;
- query-normalization SHA-256;
- Zoekt index fingerprint;
- Zoekt binary SHA-256 and source-checkout commit for local retrieval runs;
- named retrieval variant/provider;
- model/version and retrieval/reranking parameters where applicable;
- ranking, latency and payload metrics;
- the full per-query result report in the immutable run artifact.

The recorder rejects dirty-tree canonical measurements by default.  A dirty
exploratory report may be retained explicitly, but it must not be promoted to a
baseline or production claim without rerunning from a committed state.

## Experimental cycle

1. **Record the problem.** Append an observation tied to concrete run IDs.  Do
   not start from an impression such as “semantic search should be better.”
2. **State a hypothesis.** Say what mechanism is expected to improve which
   predeclared metric and what failure mode it addresses.
3. **Freeze the comparison state.** Baseline and candidate use the same qrels,
   index fingerprint and query set.  Stochastic systems also record model,
   temperature/seed when available, candidate depth and sampling controls.
4. **Run the candidate without changing judgments.** Archive the raw report
   before interpreting it.
5. **Pool and judge new retrieval families.** Retrieval output never assigns its
   own relevance.  Add qrels in a separate gold-only commit, including explicit
   relevance 0 for reviewed negatives, then rerun every compared system.
6. **Compare paired queries, not only aggregate numbers.** Inspect gains,
   regressions, tag slices, latency/cost and changed rankings.  Once the query
   set is large enough, use held-out queries and query-level bootstrap intervals.
7. **Record the conclusion.** Append an observation and, if warranted, a
   production decision citing the exact run IDs.  A failed experiment remains in
   the ledger.
8. **Deploy separately.** Production behavior changes only after the experimental
   comparison is recorded.  The production measurement after deployment becomes
   a new ledger entry rather than overwriting the candidate run.

## Rank cutoff versus stochastic trials

Do not overload `k`.  A ranked run uses cutoff **K** (`Success@K`,
`Owner-Success@K`, Recall@K, nDCG@K).  A stochastic system uses trial count **R**
(`Pass@R[Owner-Success@10]`, for example).  Always report expected single-run
quality alongside Pass@R so additional inference budget is visible.

## Relevance judgments and changing data

Qrels are scientific data.  A new relevant file discovered by a candidate is not
a “false positive” merely because it was absent from the old gold set.  Pool it,
review it independently of the producing system, and commit that judgment
separately.  After a qrel change, regenerate all reports used in a comparison.

Similarly, an index change invalidates same-index comparisons.  Keep the old run
as history; run both baseline and candidate again on the new index rather than
normalizing away the change.

## Commands

Archive a completed clean report:

```sh
python evaluation/search/lablog.py run report.json --stage candidate \
  --note 'fielded lexical candidate before deployment'
```

Record a dated observation or hypothesis:

```sh
python evaluation/search/lablog.py note observation \
  'Owner Hit@10 is much lower than source Hit@10.' \
  --evidence M-... --tag ranking
```

Inspect or validate the permanent record:

```sh
python evaluation/search/lablog.py show
python evaluation/search/lablog.py validate
```

The frozen baseline files under `baselines/` remain convenient regression inputs;
they are not the historical record.  The immutable `runs/` artifacts plus
`ledger.jsonl` are.
