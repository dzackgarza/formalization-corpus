# Active corpus work

This repository is the local search corpus of every Lean formalization repository
recorded in the lean-categories formalization source registry, plus the pinned
Mathlib checkout and Lean Reservoir metadata. Its purpose is to make
"this mathematics is not formalized anywhere in the registry" claims exhaustively
checkable, per the lean-categories reuse gate.

Build provenance: the corpus was created in the 2026-08-13 codex session
(`rollout-2026-08-13T15-07-42-019ff9f2-bc0e-7de0-9bcd-c9630d6a8813.jsonl`,
ordinals 17652-18838), at the user's direction (ord 18026 "efficiently and
idempotently in a resumable way"; ord 18103 "build the monorepo in ~/gitclones").
The transcript's final event is `task_complete` (ord 18838) with no final
summary message; its last agent message reports LeanBridge mid-hydration
("transferred about 477 MB... keep this process attached"). The LeanBridge
sparse-checkout earlier failed with exit 128 and network errors ("Timeout,
server github.com not responding"; "fatal: early EOF"; "fatal: could not fetch
3e12236"). `usage_limit` appears once in the transcript, not at the end.

## Corpus state (verified 2026-08-15)

- 97 manifest repos in `repos.tsv`; 101 Zoekt shard files (LeanBridge spans 3).
- 36,541 `.lean` files in the tree; the Zoekt index matches the tree exactly
  (per-repo file counts identical, zero diff in both directions). LeanBridge:
  2,215 real `.lean` files, blob `3e12236` present, exact shard-vs-tree match.
- 96/97 repo dirs use the lean-only sparse-checkout pattern (`/*` `!/*/`
  `/**/*.lean` `/lakefile.*` `/lean-toolchain` `/lake-manifest.json` `/README*`);
  mathlib4 is a full checkout. Repos sit on default branch; no commit pinning
  (ord 18089).
- `reservoir-index/`: 453 metadata entries. `reservoir-sources/`: 4 hydrated
  repositories (FFaCiL, EllipticCurve, ec-tate-lean, YaelDillies__toric).
- 3 commits; no remote configured; corpus content itself is untracked
  (`.gitignore` excludes `/*__*`).
- 96 zero-byte `*.err` debris files trashed 2026-08-15.
- Search E2E verified: `residue` → 15 docs.
- Shard-build attribution: shards were built/verified in this conversation's
  earlier turns (22:17) and by the 08/15 `/tmp` sessions, which tracked the
  same 2,215 LeanBridge files in a separate corpus copy — attribution
  ambiguous, disk state complete either way.
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
   declaration semantics after builds). Usage facts to record: `zoekt -r` prints
   repo names (it is not a filter), `-l` lists filenames, `repo:`/`file:` filters
   take regexes; ast-grep runs per-repo via `sgconfig.yml`; `rg` covers
   corpus-wide text search.

5. **Cover the Reservoir dirs in `just index`.** The `index` recipe loops over
   `repos.tsv` only. The `reservoir-index/` and `reservoir-sources/` shards
   exist but are not produced by the recipe — their indexing is not
   reproducible from the justfile.

6. **Remove or reconcile `missing.now`.** It lists 9 repositories as MISSING
   (displayed_categories, teorth analysis/equational_theories/expdb/pfr,
   Sphere-Packing-Lean, PutnamBench, lean-smt, CvxLean) that now have indexed
   content. It is stale debris from the failed early hydration attempt.

7. **Decide whether a completion summary is still owed.** The owning session
   ended (`task_complete`, ord 18838) without declaring anything done; every
   "complete" claim is post-hoc disk verification (this turn and prior turns),
   not the task's own completion. If a summary is wanted, write it from the
   transcript and this TODO.
