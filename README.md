# Lean Reference Corpus

A searchable corpus of Lean 4 formalization repositories, built to make the
claim "this mathematics is not formalized anywhere in the Lean ecosystem"
exhaustively checkable.

The corpus is a working premise of the `lean-categories` reuse gate: before
authoring any mathematical construct, search this corpus. A term found here is
a reusable formalization; a term not found here, after corpus-wide search, is
a candidate for new authorship.

[`SOURCES.md`](./SOURCES.md) is the registry: every repository the corpus knows
about, grouped by mathematical domain, with what each one holds and how far it
is to be trusted. It is the single source of truth for what the ecosystem
offers, and consuming repositories link to it instead of keeping their own
copies. The `.tsv` manifests beside it say what to check out; `SOURCES.md` says
what the checkouts are worth.

## What the corpus contains

- **The pinned Mathlib checkout** (`leanprover-community__mathlib4/`), matching
  the exact version the corpus is indexed against. This is the primary search
  surface.
- **119 registered formalization repositories** (see `repos.tsv`), each a
  shallow (`--depth 1 --filter=blob:none`) sparse checkout containing only
  `.lean` files, `lakefile.*`, `lean-toolchain`, `lake-manifest.json`, and
  `README*`.
- **The Lean Reservoir index** (`reservoir-index/`), the package metadata
  registry cloned from
  <https://github.com/leanprover/reservoir-index>.
- **739 Lean Reservoir packages** (see `reservoir.tsv`), hydrated into
  `reservoir-sources/` with the same sparse convention. Packages already
  present in `repos.tsv` (exact URL match) and Mathlib-family repositories are
  excluded from the reservoir list; the reservoir is a separate manifest so a
  routine `just sync` does not pull 800 repositories.
- **10 Rocq and Agda libraries** (see `port-sources.tsv`), hydrated into
  `port-sources/` keeping `.v`, `.agda`, and `.lagda*` files. The reuse gate
  forbids re-proving something that exists "in another proof assistant as a
  port source", so those sources are indexed with the Lean ones; Zoekt searches
  text and does not care which assistant wrote it.

## Workflow

```sh
just build-tools        # build zoekt-index, zoekt, and the Lean ast-grep parser
just sync               # clone or update the registered Lean repositories
just sync-reservoir     # clone or update the 739 Lean Reservoir packages
just sync-port-sources  # clone or update the Rocq and Agda port sources
just index              # (re)build the Zoekt index over all three manifests
just check-sources      # report repositories in SOURCES.md that no manifest checks out
just search "Nat.Prime"                  # Zoekt text search
just ast "def $NAME : $TYPE := $VALUE"   # Lean syntax-tree pattern search
just publish            # ship the index to the search host and restart it
```

## The hosted search

[dzackgarza.github.io/lean-reference-corpus](https://dzackgarza.github.io/lean-reference-corpus/)
searches the corpus from a browser. It is the real index behind it, not a
derived summary: the same queries and the same results as `just search`.

The work is split by what each side can host:

| Where | What it serves | Why there |
| --- | --- | --- |
| GitHub Pages (`site/`) | The page, the query UI, the repository table | Static, versioned with the manifests, free to serve |
| `lean-corpus.dzackgarza.com` | `POST /api/search` only | 4.6 GB of shards cannot live in a Pages site |

The page holds no index. It posts a zoekt query to the search host and renders
what comes back, so nothing but the answer crosses the wire. `site/corpus.json`
is generated from the manifests by `scripts/build-site.py`, which is how a hit
in `leanprover__hex-lll` links back to its file on GitHub.

The search host carries the index alone — no checkouts, no Go toolchain, no
indexing work. `just index` builds locally and `just publish` rsyncs `.zoekt/`;
the server watches its shard directory, so replaced shards load without a
restart. The site is therefore exactly as current as the last local `just sync`.
The binary is cross-compiled from `tools/sourcegraph__zoekt`:

```sh
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o zoekt-webserver ./cmd/zoekt-webserver
```

It runs with `-html=false`, so the host answers queries and serves no pages,
and with `-cors_origin` naming the Pages site.

Add a repository by describing it in `SOURCES.md` under the domain it belongs
to, appending `url<TAB>path` to the matching manifest — `repos.tsv` for Lean 4,
`reservoir.tsv` for Reservoir packages, `port-sources.tsv` for another proof
assistant — then running its `sync` recipe and `just index`.

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
  incrementally, and the index is queryable at repository granularity.
  Recorded at ord 18083 of the corpus-building session.
- **`ast-grep` + `tree-sitter-lean` for structural search.** Pattern queries
  over the Lean syntax tree, run per-repository via `sgconfig.yml`.
- **Lean LSP-based verification** (typechecking candidate declarations) was
  considered but not built; candidate hits from Zoekt/ast-grep are verified
  against the pinned Mathlib checkout instead.
- **Sparse checkouts.** Only Lean sources and build metadata are checked out,
  keeping the corpus disk-light while remaining fully searchable.
- **No commit pinning.** Repositories are shallow-checked-out at their
  current HEAD; the corpus is a snapshot as of the last `sync`.
- **`path` is never used as a variable name in recipes**: in zsh it is the
  array tied to `PATH`, so assignment silently destroys the environment.
  Recipes use `dir`.

## Failure accounting

`just sync-reservoir` writes failures to `reservoir-missing.now` (gitignored),
one `url<TAB>path<TAB>REASON` line per failed clone. Reasons: `CLONE-FAIL`
(network or dead repository), `SPARSE-FAIL`, `UPDATE-FAIL`, `FETCH-FAIL`.
Re-run the recipe to retry; it skips directories that already contain a
working clone.
