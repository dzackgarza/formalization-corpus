# Active corpus work

This repository is the local search corpus of every Lean formalization repository
recorded in the lean-categories formalization source registry, plus the pinned
Mathlib checkout and Lean Reservoir metadata. Its purpose is to make
"this mathematics is not formalized anywhere in the registry" claims exhaustively
checkable, per the lean-categories reuse gate.

Build provenance: the corpus was created in the 2026-08-13 codex session
(`rollout-2026-08-13T15-07-42-019ff9f2-bc0e-7de0-9bcd-c9630d6a8813.jsonl`,
ordinals 17652-18840), at the user's direction (ord 18026 "efficiently and
idempotently in a resumable way"; ord 18103 "build the monorepo in ~/gitclones").
That session died mid-hydration (`usage_limit_exceeded`, ord 18840, exit 128 on
the LeanBridge sparse-checkout) and produced no completion summary.

## Corpus state (verified 2026-08-15)

- 97 manifest repos in `repos.tsv`; every repo dir has a Zoekt shard.
- 36,541 `.lean` files in the tree; the Zoekt index matches the tree exactly
  (per-repo file counts identical, zero diff in both directions).
- `reservoir-index/`: 453 metadata entries. `reservoir-sources/`: 4 hydrated
  repositories (FFaCiL, EllipticCurve, ec-tate-lean, YaelDillies__toric).
- 3 commits; no remote configured; corpus content itself is untracked
  (`.gitignore` excludes `/*__*`).
- `just test-commit` passes. `missing.now` lists 9 repositories as MISSING that
  now have indexed content — stale.

## Outstanding work

1. **Hydrate the Lean Reservoir sources.** The user directed searching the Lean
   Reservoir (transcript ord 2878: "One should also consider searching the Lean
   Reservoir (800+ packages)"). Only 4 of 453 indexed packages have sources. The
   scope decision (which packages, how many) was never recorded. Read the
   continuation session `rollout-2026-08-13T22-15-24-*.jsonl` first — it may
   record the decision. Then hydrate the selected set, add it to `repos.tsv`,
   and index.

2. **Run the exhaustive residue audit — the corpus's reason for existing.**
   The corpus was built to replace per-repo partial checks with an exhaustive
   check of every catalogue term against all recorded sources (ord 17652). The
   audit never ran against the completed corpus. The lean-categories catalogues
   still carry 574 unchecked entries:
   sage-preamble 285, weibel 61, whitehead 58, hartshorne 43, ahlfors 42,
   shafarevich 38, hatcher 28, folland 14, apostol 5. Verify each against the
   corpus with `just search` / `just ast`; annotate exact matches; leave only
   sourced residues.

3. **Add a remote and push.** The workspace exists only locally: 3 commits, no
   remote, corpus content untracked. Data loss on this machine destroys the
   corpus. Either push to GitHub or record an explicit local-only decision.

4. **Write the design doc / README.** Nothing in the repository documents its
   purpose, query workflow (`just search`, `just ast`), update procedure
   (`just sync`), or indexing (`just index`). The design decision is recorded
   only in the dead transcript (ord 18083: independent repos in one workspace,
   Zoekt for broad search, ast-grep with tree-sitter-lean for structural
   search, Lean LSP to confirm candidates in their own projects, Lean Scout for
   declaration semantics after builds).

5. **Cover the Reservoir dirs in `just index`.** The `index` recipe loops over
   `repos.tsv` only. The `reservoir-index/` and `reservoir-sources/` shards
   exist but are not produced by the recipe — their indexing is not
   reproducible from the justfile.

6. **Remove or reconcile `missing.now`.** It lists 9 repositories as MISSING
   (displayed_categories, teorth analysis/equational_theories/expdb/pfr,
   Sphere-Packing-Lean, PutnamBench, lean-smt, CvxLean) that now have indexed
   content. It is stale debris from the failed early hydration attempt.

7. **Decide whether a completion summary is still owed.** The owning session
   died before declaring anything done; every "complete" claim is post-hoc disk
   verification (this turn and prior turns), not the task's own completion.
   If a summary is wanted, write it from the transcript and this TODO.
