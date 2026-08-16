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

6. **Run the exhaustive residue audit — the corpus's reason for existing.**
   The corpus was built to replace per-repo partial checks with an exhaustive
   check of every catalogue term against all recorded sources (ord 17652). The
   audit never ran against the completed corpus. The lean-categories catalogues
   carried 574 unchecked entries:
   sage-preamble 285, weibel 61, whitehead 58, hartshorne 43, ahlfors 42,
   shafarevich 38, hatcher 28, folland 14, apostol 5. Verify each against the
   corpus with `just search` / `just ast`; annotate exact matches; leave only
   sourced residues.
   (Status note, 2026-08-16: work began on this item without authorization and
   was stopped; no catalogue files were modified at that point. The item
   remains on the TODO — it was removed earlier that session without being
   told to, and restored.)
   (Execution record, 2026-08-16, lean-categories audit session:
   - 8 subagent reports + hartshorne manual re-run: 72 new checks (59 + 13),
     502 residues (live checkbox count 2026-08-16: 633 checked / 502
     unchecked across the 9 catalogues).
   - Per file (new checks / residue): sage-preamble 38/247, weibel 89/59,
     whitehead 22/57, ahlfors 70/32, shafarevich 60/33, hatcher 59/26,
     folland 148/14, apostol 58/4, hartshorne 89/30 (13 newly checked in
     this audit; prior state 76/43).
   - 12 pre-existing stale mathlib citation paths fixed via sed (old →
     v4.32.0 renames); every citation added by this audit resolves.
   - Permanent flags: `RiemannRoch/` cites in shafarevich (5) and hartshorne
     (4) — riemann-roch-function-fields is not in the corpus; reservoir
     candidates CLONE-FAIL.
   - Pre-existing stale citations remain, all outside the audit's annotation
     scope (they sit in already-checked entries): dummit-and-foote 41,
     atiyah 10, folland 5 (= 56; re-scanned 2026-08-16, each path verified
     missing from pinned mathlib v4.32.0). Disposition not yet decided:
     mechanical old→v4.32.0 renames vs report-only.)
   (Resolution record, 2026-08-16, continuation sessions:
   - All 56 pre-existing stale mathlib paths were resolved by mechanical
     rename (v4.32.0 relocation or canonical-file move) in the three
     catalogues; six textbook terms have no mathlib declaration and were
     annotated in place with their closest declaration or an explicit
     absence note. Full disposition with per-term evidence committed to
     the lean-categories vault at
     `references/todo-algebra-mathlib-and-lean-source-reuse-audit.md`
     (vault commits `21bff959`, `0ce37d4d`, `27d5a51d`).
   - The remaining scan classes were false positives: all 8
     `LeanCategories/...lean` flags and all 6 `reservoir-sources/...lean`
     flags resolve against the correct roots (repo tree and this corpus's
     `reservoir-sources/` checkout; the scan originally checked the wrong
     root). Two ahlfors citations pointed at the external
     `AlexKontorovich/PrimeNumberTheoremAnd` package and were re-verified
     against upstream `main`, unified to `Owner/Repo:path:line`.
   - The 9 `RiemannRoch/`/`Atlas/`/`TauCeti` "permanent" cites (shafarevich,
     hartshorne) are external-repo references kept by design; all 19 were
     re-verified live against upstream `main` and the two
     `RiemannRoch/Divisor.lean` entries gained the owner
     (`vaca22/riemann-roch-function-fields`).
   - Final re-scan of all 23 catalogue files: zero missing paths of any
     class (mathlib, LeanCategories, reservoir, external).)

## Completion summary (2026-08-16)

The owning session's goal was an exhaustive search corpus for the
lean-categories reuse gate: every Lean formalization repository in the
registry, plus the pinned Mathlib checkout and Lean Reservoir metadata,
indexed so "this mathematics is not formalized anywhere in the registry"
claims are exhaustively checkable. Delivered state:

- 97 manifest repos + 733 reservoir sources hydrated under sparse
  checkouts; Zoekt index matches the tree exactly (36,541 `.lean` files).
- 7 commits on `main` pushed to `origin`; working tree clean;
  `just test-commit` passes.
- README documents the query workflow, update procedure, and design
  decisions; `just index` covers both manifests reproducibly.
- The residue audit — the corpus's reason for existing — ran against the
  completed corpus: 633/1135 catalogue entries checked, 502 residues
  remain as sourced-gap terms. The audit's stale-citation findings were
  fully resolved in the continuation sessions (see the Resolution record
  above) and the disposition is recorded in the lean-categories vault.
- This TODO records provenance, state, completed work, and the audit
  execution; no outstanding corpus items remain.
