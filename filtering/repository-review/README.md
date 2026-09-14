# Repository review catalogue

This directory is the durable work surface for source-by-source filtering review.
It is deliberately separate from the already-filtered index: catalogue generation
walks the authoritative hydrated source trees so earlier exclusions remain visible
for future audit.

Generated state:

- `catalogue.jsonl` — one source row with source snapshot and work-unit count;
- `catalogue/<repository>.json` — source metadata, totals, source snapshot, and
  stable work units;
- `files/<repository>/<RRU-...>.jsonl` — every imported file assigned to that
  unit, with path, size, SHA-256, formal-source status, and current decisions;
- `batches.jsonl` — deterministic review scheduling over all work units.

Large-source partitioning is intentionally stable under sibling insertions.
Literal subtrees are used while they remain bounded; collections of small sibling
subtrees and large sets of direct files are assigned to SHA-256 buckets.  This
costs some extra work units but avoids order-sensitive chunk boundaries where one
new path would invalidate unrelated later reviews.

Human review history lives under `reviews/<repository>/<RRU-...>.jsonl`.  These
files are append-only.  The latest line is the active disposition for that unit;
a later line must explicitly supersede the previous review ID.

A completed review normally uses `status=reviewed` and
`default_action=retain`.  That makes retention of everything not selected by a
rule explicit rather than implicit.  Every review also carries `review_evidence`
with concrete unit-wide observations, so a no-blacklist result is auditable rather
than a bare checkbox.  `status=deferred` means the unit is still open and cannot
activate exclusions.

Exclusion rules are repository-local and may select only an exact path, an
explicit path set, or a literal subtree prefix.  Every rule records a rationale,
a content-level losslessness invariant, source-local evidence, and the required
`FILTER-###` policies.  Rules are pinned to the unit snapshot; changed units are
stale and block indexing until a new review revision is appended.

`FD-018` is the per-file materialization of accepted repository-local blacklist
rules.  Do not write `FD-018` records manually.  `scripts/build-filter-state.py`
resolves fresh accepted review rules against these manifests and records the exact
matched paths/hashes in the ordinary append-only filtering ledger.

## Review workflow

For a work unit, generate a non-mutating template, edit it outside the review
history, then append it through the validator:

```sh
python scripts/repository-review.py template RRU-... > /tmp/review.json
$EDITOR /tmp/review.json
python scripts/repository-review.py append /tmp/review.json
python scripts/repository-review.py validate
```

Do not hand-append review JSONL.  `append` rejects stale snapshots, broken
supersession chains, unbounded selectors, selectors outside the unit, missing
reasoning/evidence, and incomplete policy references before history is mutated.
For a reviewed unit with no blacklist, delete the placeholder rule and leave
`rules: []`; the explicit default `retain` is then the substantive disposition.

## Source retirement

If a whole-repository unit establishes that the imported repository is tooling,
review machinery, metadata, or otherwise outside the corpus source invariant, do
not blacklist all of its files.  Set `source_action.action` to `retire-source`,
cite `FD-012`/`COPY-005`, and record the source-level rationale, content invariant,
and evidence.  After the review is committed, apply it explicitly with:

```sh
python scripts/repository-review.py retire-source RRU-...
```

Retirement removes the row from the live source/topic/description inventory but
leaves the hydrated checkout untouched.  Its catalogue, exact file hashes, and
review history remain frozen in this campaign catalogue with
`inventory_status=retired`; retirement therefore cannot erase the evidence used
to justify the source-level decision.
