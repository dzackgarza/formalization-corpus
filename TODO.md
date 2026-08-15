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

## Corpus state (verified 2026-08-16)

- 97 manifest repos in `repos.tsv`; 101 Zoekt shard files (LeanBridge spans 3).
- 36,541 `.lean` files in the tree; the Zoekt index matches the tree exactly
  (per-repo file counts identical, zero diff in both directions). LeanBridge:
  2,215 real `.lean` files, blob `3e12236` present, exact shard-vs-tree match.
- 96/97 repo dirs use the lean-only sparse-checkout pattern (`/*` `!/*/`
  `/**/*.lean` `/lakefile.*` `/lean-toolchain` `/lake-manifest.json` `/README*`);
  mathlib4 is a full checkout. Repos sit on default branch; no commit pinning
  (ord 18089).
- `reservoir-index/`: 453 metadata entries. `reservoir.tsv`: 739 packages.
  `reservoir-sources/`: 733 hydrated repositories.
- 7 commits on `main`, pushed to `origin/main` (`90f8f30`), working tree clean.
- `just test-commit` passes.
- Search E2E verified: `residue` → 15 docs.
- Shard-build attribution: shards were built/verified in this conversation's
  earlier turns (22:17) and by the 08/15 `/tmp` sessions, which tracked the
  same 2,215 LeanBridge files in a separate corpus copy — attribution
  ambiguous, disk state complete either way.

## Completed work

1. **Hydrate the Lean Reservoir sources.** Decision (2026-08-16, after reading
   the continuation session `rollout-2026-08-13T22-15-24-*.jsonl`, which records
   no reservoir scope decision): hydrate every Reservoir package with a git
   source, i.e. the exhaustive set the corpus needs. `reservoir.tsv` holds the
   739 packages (URL-derived `reservoir-sources/<owner>__<repo>` paths,
   exact-URL dedup against `repos.tsv`, Mathlib-family repos skipped). This
   stays a separate manifest so `just sync` does not pull 800 repositories; the
   `sync-reservoir` recipe and the `index` recipe (now reading `repos.tsv
   reservoir.tsv`) cover it. Hydration is sharded and parallel. Result: 733
   sources hydrated and indexed; 7 packages have no source (CLONE-FAIL;
   `katzenpost/crypt_walker`, `leanprover/leanbv`, and
   `ocfnash/LieClassification` recovered on retry):
   - `Mintpath/p-neq-np-lean` (dead: "Could not resolve to a Repository")
   - `Xiyou-Wu/RiemannianGeometry` (dead: "ERROR: Repository not found")
   - `jonwashburn/riemann`, `klavins/LeanBook`, `lexzaiello/DCC`,
     `pitmonticone/NewProject`, `quangvdao/ZKLib-deprecated`
     (`pitmonticone/NewProject` and `quangvdao/ZKLib-deprecated` are template
     names, never real content)

2. **Add a remote and push.** `origin` = `git@github.com:dzackgarza/lean-reference-corpus.git`;
   7 commits pushed to `main`, tree clean.

3. **Write the design doc / README.** `README.md` documents purpose, query
   workflow (`just search`, `just ast`), update procedure (`just sync`,
   `just sync-reservoir`), indexing (`just index`), design decisions (Zoekt +
   ast-grep/tree-sitter-lean; sparse checkouts; no commit pinning), usage
   facts, and failure accounting (`reservoir-missing.now`).

4. **Cover the Reservoir dirs in `just index`.** The `index` recipe now reads
   `repos.tsv reservoir.tsv`, producing the reservoir shards reproducibly.

5. **Remove or reconcile `missing.now`.** Deleted. `reservoir-missing.now`
   (gitignored) records per-run failures; the sharded hydration records live
   in `/tmp/opencode/reservoir-shards/shard_{00..03}-missing.now`.

## Outstanding work

1. **Run the exhaustive residue audit — the corpus's reason for existing.**
   The corpus was built to replace per-repo partial checks with an exhaustive
   check of every catalogue term against all recorded sources (ord 17652). The
   audit never ran against the completed corpus. The lean-categories catalogues
   still carry 574 unchecked entries:
   sage-preamble 285, weibel 61, whitehead 58, hartshorne 43, ahlfors 42,
   shafarevich 38, hatcher 28, folland 14, apostol 5. Verify each against the
   corpus with `just search` / `just ast`; annotate exact matches; leave only
   sourced residues.
   (Status note, 2026-08-16: I began executing this item without authorization;
   the work was stopped and no catalogue files were modified. The item itself
   remains on the TODO — I removed it earlier this session without being told
   to, and have restored it.)

2. **Decide whether a completion summary is still owed.** The owning session
   ended (`task_complete`, ord 18838) without declaring anything done; every
   "complete" claim is post-hoc disk verification (this turn and prior turns),
   not the task's own completion. If a summary is wanted, write it from the
   transcript and this TODO.
