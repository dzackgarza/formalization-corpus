# Lean Reference Corpus

A searchable corpus of Lean 4 formalization repositories, built to make the
claim "this mathematics is not formalized anywhere in the Lean ecosystem"
exhaustively checkable.

The corpus is a working premise of the `lean-categories` reuse gate: before
authoring any mathematical construct, search this corpus. A term found here is
a reusable formalization; a term not found here, after corpus-wide search, is
a candidate for new authorship.

## What the corpus contains

- **The pinned Mathlib checkout** (`leanprover-community__mathlib4/`), matching
  the exact version the corpus is indexed against. This is the primary search
  surface.
- **97 registered formalization repositories** (see `repos.tsv`), each a
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

Current corpus size: 36,541 `.lean` files across the registered
repositories, indexed into 101 Zoekt shards.

## Workflow

```sh
just build-tools   # build zoekt-index, zoekt, and the Lean ast-grep parser
just sync          # clone or update the 97 registered repositories
just sync-reservoir# clone or update the 739 Lean Reservoir packages
just index         # (re)build the Zoekt index over repos.tsv + reservoir.tsv
just search "Nat.Prime"     # Zoekt text search
just ast "def $NAME : $TYPE := $VALUE"   # Lean syntax-tree pattern search
```

Add a repository by appending `url<TAB>path` to `repos.tsv` (Reservoir
packages go in `reservoir.tsv`), then `just sync` (or `just sync-reservoir`)
and `just index`.

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
