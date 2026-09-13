# formalization-corpus

One search across formalized mathematics, whichever assistant it was written
in: *has this definition, construction, statement, or theorem already been
formalized, and where?* A hit in Rocq answers the prior-art question even though
it cannot be imported into Lean; a hit in Mathlib answers it and can be imported.

Lean is where most of this material currently lives, which is why most of the
corpus is Lean. It is not what the corpus is about.

[`SOURCES.md`](./SOURCES.md) is the registry: every source the corpus knows
about, grouped by mathematical domain, with what each one holds and how far it
is to be trusted. It is the single source of truth for what the ecosystem
offers, and consuming repositories link to it instead of keeping their own
copies. The `.tsv` manifests beside it say what to check out; `SOURCES.md` says
what the checkouts are worth.

## What the corpus contains

- **The pinned Mathlib checkout** (`leanprover-community__mathlib4/`), matching
  the exact version the corpus is indexed against. This is the primary search
  surface.
- **The registered Lean 4 formalization repositories** (see `repos.tsv`), each a
  shallow (`--depth 1 --filter=blob:none`) sparse checkout containing only
  `.lean` files, `lakefile.*`, `lean-toolchain`, `lake-manifest.json`, and
  `README*`.
- **The Lean Reservoir index** (`reservoir-index/`), the package metadata
  registry cloned from
  <https://github.com/leanprover/reservoir-index>.
- **The Lean Reservoir packages** (see `reservoir.tsv`), hydrated into
  `reservoir-sources/` with the same sparse convention. Packages already
  present in `repos.tsv` (exact URL match) and Mathlib-family repositories are
  excluded from the reservoir list; the reservoir is a separate manifest so a
  routine `just sync` does not pull 800 repositories.
- **The non-Lean formalization libraries** (see `port-sources.tsv`), hydrated
  into `port-sources/`.  The manifest records the prover for each source, and
  synchronization keeps only its formal source: Rocq `.v`; Agda `.agda` and
  literate Agda; Isabelle `.thy`; HOL Light `.ml`/`.hl`; HOL4/CakeML `.sml`/`.sig`;
  Mizar `.miz`; Metamath `.mm`/`.mm0`/`.mm1`; ACL2 `.lisp`/`.lsp`/`.acl2`;
  PVS `.pvs`/`.prf`; and Twelf `.elf`. Definitions, structures, specifications,
  theorem statements, constructions, and proofs are all search material: a
  source does not need to prove a headline theorem to be useful here.

## Workflow

```sh
just build-tools        # build zoekt-index, zoekt, and the Lean ast-grep parser
just sync               # clone or update the registered Lean repositories
just sync-reservoir     # clone or update the 738 Lean Reservoir packages
just sync-ports         # clone or update the non-Lean formalization libraries
just index-ports        # incrementally rebuild only the non-Lean Zoekt shards
just index              # (re)build the Zoekt index over all manifests
just metrics            # recompute exact source/unit/line reach statistics
just site               # regenerate committed static source metadata
just preview            # deploy site/ to formalization-corpus-preview.localhost
just check-sources      # report repositories in SOURCES.md that no manifest checks out
just search "Nat.Prime"                  # Zoekt text search
just ast "def $NAME : $TYPE := $VALUE"   # Lean syntax-tree pattern search
just publish            # ship the index to the search host
```

## The hosted search

[dzackgarza.github.io/formalization-corpus](https://dzackgarza.github.io/formalization-corpus/)
searches the corpus from a browser. It is the real index behind it, not a
derived summary: the same queries and the same results as `just search`.

The work is split by what each side can host:

| Where | What it serves | Why there |
| --- | --- | --- |
| GitHub Pages (`site/`) | The page, the query UI, the source table | Static, versioned with the manifests, free to serve |
| `formalization-corpus.dzackgarza.com` | `POST /api/search` only | The multi-gigabyte Zoekt index cannot live in a Pages site |

The page holds no index. It posts a zoekt query to the search host and renders
what comes back, so nothing but the answer crosses the wire. `site/corpus.json`
is generated from the manifests by `scripts/build-site.py`, which is how a hit
in `leanprover__hex-lll` links back to its file on GitHub.

The search host carries the index alone — no checkouts, no Go toolchain, no
indexing work. `just index` builds locally and `just publish` rsyncs `.zoekt/`;
the server watches its shard directory, so replaced shards load without a
restart. The site is therefore exactly as current as the last local source sync,
index build, and publish.

For local visual review, `just preview` performs a **static deploy** to
`/var/www/static-sites/formalization-corpus-preview/`. The machine's existing
nginx `*.localhost` static-site vhost serves it at
`http://formalization-corpus-preview.localhost/`; no preview daemon or additional
TCP port is started. The production search API deliberately accepts browser CORS
only from the production Pages origin, so the local static preview disables the
search box rather than proxying or starting a local search backend.
The binary is cross-compiled from `tools/sourcegraph__zoekt`:

```sh
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o zoekt-webserver ./cmd/zoekt-webserver
```

It runs with `-html=false -rpc`, so the host answers queries and serves no
pages, and with `-cors_origin` naming the Pages site. `-rpc` is what registers
`/api/`: without it the process is healthy and every query is a 404.

## Querying it

The JSON API is open — no key, no account. The
[API page](https://dzackgarza.github.io/formalization-corpus/api.html) has the
query language, the options and the response shape; the short version:

```sh
curl -s https://formalization-corpus.dzackgarza.com/api/search \
  -H 'Content-Type: application/json' \
  -d '{"Q": "Hasse invariant file:\\.lean$", "Opts": {"MaxDocDisplayCount": 20}}' \
  | jq -r '.Result.Files[] | "\(.Repository)  \(.FileName)"'
```

`Opts` worth knowing: `MaxDocDisplayCount` caps files returned, `ChunkMatches`
returns the matching lines rather than bare filenames, `NumContextLines` adds
context, and `Whole` returns each file in full. `/api/list` enumerates indexed
sources. CORS restricts browsers to the Pages origin; scripts are
unaffected.

Add a repository by describing it in `SOURCES.md` under the domain it belongs
to, appending `url<TAB>path` to `repos.tsv` for Lean 4 or
`url<TAB>path<TAB>kind<TAB>transport` to `port-sources.tsv` for another prover,
then running its sync recipe and `just index`.  Reservoir packages stay in
`reservoir.tsv`, which is generated and synchronized separately.

For `port-sources.tsv`, `kind` is the proof-source family (`rocq`, `agda`,
`isabelle`, `hol-light`, `hol4`, `mizar`, `metamath`, `acl2`, `pvs`, or
`twelf`). `transport` is normally `git`; `gitlab` records a GitLab-hosted git
source and `web-dir` is reserved for an authoritative directory distribution
such as the current Mizar MML. The kind determines which proof-source extensions
are materialized by the sparse checkout.

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

`sync-manifest.zsh` writes failures beside the manifest, e.g.
`reservoir-missing.now` or `port-sources-missing.now` (gitignored), one
`url<TAB>path<TAB>REASON` line per failed source. Git-backed reasons include
`CLONE-FAIL`, `SPARSE-FAIL`, `UPDATE-FAIL`, and `FETCH-FAIL`; direct directory
sources can report `WEB-SYNC-FAIL`. Re-run the sync recipe to retry; existing
working checkouts are updated in place.
