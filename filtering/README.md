# Filtering record

The source checkouts are authoritative.  Filtering builds reversible derived
search views; it never deletes upstream material.

`decision-catalog.json` records stable class decisions (`FD-###`) and their
justifications.  `ledger.jsonl` is the append-only per-file history.  Each
affected file records the exact class decision, source revision, content hash or
parser evidence where applicable, the corpus commit that made the observation,
and the complete class justification.  `current.jsonl` is only the latest
materialized snapshot and may be regenerated from the sources; it is not a
replacement for the history.

`duplicate-aliases.json` records exact SHA-256 content groups.  Duplicate files
remain physically indexable because their distinct paths and sources are useful
retrieval/provenance signals.  The API uses the alias map to collapse identical
hits while reporting every original occurrence.

The derived local views are gitignored:

- `.index-primary/` — formal mathematical documents eligible for the public
  search index;
- `.index-metadata/` — README/documentation and parser-verified import-only
  navigation modules.

See `CONTRIBUTING.md` `FILTER-###` and `docs/CORPUS-FILTERING.md` before changing
any decision.
