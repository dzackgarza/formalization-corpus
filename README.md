# formalization-corpus

One search across formalized mathematics, whichever assistant it was written
in: *has this definition, construction, statement, or theorem already been
formalized, and where?* A hit in Rocq shows that the mathematics has already
been formalized even though it cannot be imported into Lean; a hit in Mathlib
both locates the formalization and can be imported directly.

Lean is where most of this material currently lives, which is why most of the
corpus is Lean. It is not what the corpus is about.

[`sources.tsv`](./sources.tsv) is the canonical source inventory: one row per
formalization source, with its URL, local directory, proof assistant, transport,
sync group, and discovery provenance. [`SOURCES.md`](./SOURCES.md) is a
human-maintained topic guide and annotation layer over notable sources; it is
not a second inventory.

## What the corpus contains

The canonical table currently has 893 sources. A source is an independently
addressable formalization library, repository, or published source distribution:
Mathlib is one source, UniMath is one source, and the Mizar Mathematical Library
is one source. How a source was discovered does not change its identity.

`sources.tsv` records six fields:

- `url` — canonical upstream location;
- `directory` — local checkout/mirror location and search-index identifier;
- `proof_assistant` — Lean, Rocq, Agda, Isabelle, HOL, Mizar, Metamath, ACL2, PVS, or Twelf;
- `transport` — `git`, `gitlab`, or `web-dir`;
- `sync_group` — operational refresh cadence (`routine`, `bulk`, or `cross-prover`);
- `discovered_via` — provenance such as `registry` or `reservoir`.

The last two fields are ingestion/maintenance metadata only. In particular, a
Lean repository discovered through Reservoir is still simply a Lean source. The
separate `reservoir-index/` checkout is package metadata used to discover more
source repositories; it is not itself a source category.

Synchronization keeps only the proof-source extensions appropriate to each proof
assistant plus minimal build metadata where needed. Definitions, structures,
specifications, theorem statements, constructions, and proofs are all searchable.

## Workflow

```sh
just build-tools        # build zoekt-index, zoekt, and the Lean ast-grep parser
just sync               # refresh the routine sync group
just sync-bulk          # refresh the large secondary sync group
just sync-cross-prover  # refresh non-Lean proof-assistant sources
just index-cross-prover # incrementally rebuild only that group's Zoekt shards
just index              # (re)build the Zoekt index over all sources
just metrics            # validate corpus membership and regenerate public totals
just site               # regenerate committed static source metadata
just preview            # deploy site/ to formalization-corpus-preview.localhost
just check-sources      # verify static source-table identities and cross-prover documentation
just eval-search        # measure the frozen mathematician-facing retrieval benchmark
just test-search-quality # compare retrieval scores with the committed same-index baseline
just search "Nat.Prime"                  # Zoekt text search
just ast "def $NAME : $TYPE := $VALUE"   # Lean syntax-tree pattern search
just publish            # ship the index to the search host
just deploy-api         # deploy FastAPI adapter + stock Zoekt backend binary
```

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the source-inventory invariant,
public terminology, numbered copy/information-design rules, and the conservative
`FILTER-###` contract for corpus/index cleanup.  The detailed filtering decision
guide is [`docs/CORPUS-FILTERING.md`](./docs/CORPUS-FILTERING.md).

## The hosted search

[dzackgarza.github.io/formalization-corpus](https://dzackgarza.github.io/formalization-corpus/)
searches the corpus from a browser. It is the real index behind it, not a
derived summary: the web interface queries the same index, compiling its
proof-assistant/source/topic controls to backend filters.

The work is split by what each side can host:

| Where | What it serves | Why there |
| --- | --- | --- |
| GitHub Pages (`site/`) | The page, the query UI, the source table | Static, versioned with the source metadata, free to serve |
| `formalization-corpus.dzackgarza.com` | Search API and OpenAPI contract | The multi-gigabyte Zoekt index cannot live in a Pages site |

The page holds no index. It posts a zoekt query to the search host and renders
what comes back, so nothing but the answer crosses the wire. `site/corpus.json`
is generated from the manifests by `scripts/build-site.py`, which is how a hit
in `leanprover__hex-lll` links back to its file on GitHub.

The search host carries the index alone — no source checkouts and no indexing
work. `just index` builds locally and `just publish` rsyncs `.zoekt/`; Zoekt
watches its shard directory, so replaced shards load without a restart. The
public HTTP boundary is a small FastAPI/Pydantic adapter on `127.0.0.1:6070`.
An unmodified `zoekt-webserver` listens privately on `127.0.0.1:6071` and is not
exposed by nginx.

For local visual review, `just preview` deploys the same `site/` tree that GitHub
Pages serves to `/var/www/static-sites/formalization-corpus-preview/`. The
machine's existing nginx `*.localhost` static-site vhost exposes that copy at
`http://formalization-corpus-preview.localhost/`; no preview daemon, alternate
build, or additional TCP port is involved. The local and GitHub Pages frontends
are therefore the same files; access to the separate search API is a CORS concern
of that API, not a reason to fork the frontend.
The Zoekt binary is built unmodified from `tools/sourcegraph__zoekt`:

```sh
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o zoekt-webserver ./cmd/zoekt-webserver
```

It runs with `-html=false -rpc` on the private backend port. FastAPI proxies
`/api/search` and `/api/list`, validates the public request models, generates
`/api/openapi.json` from those models, and supplies permissive CORS for the
public read-only API. Search responses use a bounded in-process LRU/TTL cache:
5 minute TTL, 64 MiB total, 8 MiB per entry, 256 entries maximum. Concurrent
identical cache misses are coalesced so only one request reaches Zoekt.

## Querying it

The JSON API is open — no key, no account. FastAPI publishes its
OpenAPI 3.1 contract at
[`/api/openapi.json`](https://formalization-corpus.dzackgarza.com/api/openapi.json).
The [API page](https://dzackgarza.github.io/formalization-corpus/api.html) renders
that live contract with Scalar; request/response schemas and client snippets
therefore come from the API rather than a second hand-maintained copy. See the
[For agents](https://dzackgarza.github.io/formalization-corpus/agents.html) page
for a compact agent prompt and optional OpenAPI-to-MCP setup.
The short version:

```sh
curl -s https://formalization-corpus.dzackgarza.com/api/search \
  -H 'Content-Type: application/json' \
  -d '{"Q": "Hasse invariant file:\\.lean$", "Opts": {"MaxDocDisplayCount": 20}}' \
  | jq -r '.Result.Files[] | "\(.Repository)  \(.FileName)"'
```

`Opts` worth knowing: `MaxDocDisplayCount` caps files returned, `ChunkMatches`
returns the matching lines rather than bare filenames, `NumContextLines` adds
context, and `Whole` returns each file in full. `/api/list` enumerates indexed
sources.

Add a source by adding one row to `sources.tsv`. Add or update a `SOURCES.md`
entry only when a human topic annotation or reference note is useful.
`proof_assistant` determines
which source extensions are materialized; `sync_group` controls refresh cadence
without splitting the inventory into multiple files.

## Usage facts

- `just search` uses `zoekt -r`, which **prints the repository names**
  containing a match. It is not a filter.
- `zoekt -l` lists file names. `repo:` and `file:` are regular-expression
  filters usable inside queries.
- `just ast` runs a Lean syntax-tree pattern across the corpus via
  `ast-grep` with the custom `tree-sitter-lean` parser (see `sgconfig.yml`).
  Metavariable queries use `$NAME` syntax.
- For raw text across the whole corpus, `rg` works directly on the checkout
  directories.

## Design decisions

- **Zoekt for broad lexical search.** Shards are cheap to build and update
  incrementally, and the index is queryable at source granularity.
  Recorded at ord 18083 of the corpus-building session.
- **`ast-grep` + `tree-sitter-lean` for structural search.** Pattern queries
  over the Lean syntax tree, run per-repository via `sgconfig.yml`.
- **Lean LSP-based verification** (typechecking candidate declarations) was
  considered but not built; candidate hits from Zoekt/ast-grep are verified
  against the pinned Mathlib checkout instead.
- **Sparse proof-source checkouts.** Lean repositories keep Lean source and
  build metadata; cross-prover repositories keep only the formal source
  extensions appropriate to their prover plus their README. This keeps the
  corpus disk-light without discarding searchable definitions or proofs.
- **No commit pinning.** Git sources are shallow-checked-out at their current
  HEAD; direct distributions such as MML mirror their current published source.
  The corpus is a snapshot as of the last relevant sync.
- **`path` is never used as a variable name in recipes**: in zsh it is the
  array tied to `PATH`, so assignment silently destroys the environment.
  Recipes use `dir`.

## Failure accounting

`sync-manifest.zsh` writes group-specific failure logs such as
`sources-routine-missing.now`, `sources-bulk-missing.now`, or
`sources-cross-prover-missing.now` (gitignored), one `url<TAB>path<TAB>REASON`
line per failed source. Git-backed reasons include
`CLONE-FAIL`, `SPARSE-FAIL`, `UPDATE-FAIL`, and `FETCH-FAIL`; direct directory
sources can report `WEB-SYNC-FAIL`. Re-run the sync recipe to retry; existing
working checkouts are updated in place.
