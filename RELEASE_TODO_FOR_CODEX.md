# RELEASE TODO — final Codex updates (staged by Fable, 2026-08-25)

The tree here is release-staged: import closure pulled from Box C (104 modules via
`wander-train/collect_release_closure.py`), constitution + sealed panels + admission
digest copied, README/ARCHITECTURE written. Remaining before `git push` + release tag:

## Blocking
1. **LICENSE — Ben's signature required.** Proposal: Apache-2.0 (patent grant suits
   an architecture release). Do not choose without Ben.
2. **Fresh-clone import check**: `python3 -c "import oracle_release_runtime_w24"`
   from `runtime/admitted/` with `runtime/` on sys.path, NO corpora present — the
   runtimes must fail *gracefully* (declines / clear errors), not crash on import.
   Fix any hard corpus-path imports by env-var guards (`ORACLE_WIKIPEDIA_BUILD`,
   `ORACLE_BENCH_BUILD`, `SOUL_STATE_ROOT`).
3. **Path scrub**: replace absolute `/opt/oracle-clm/...` defaults with
   repo-relative/env-var resolution in the organs (worker/daemon/server/harness).
   Grep-verify no box IPs (`BOX-A-IP`, `BOX-C-IP`) or tokens anywhere in the tree.
4. **corpora/README.md** — write the build instructions (simple-Wikipedia dump ->
   build script, OpenStax download + `textbook_build_v1.py`, WordNet/ConceptNet
   compile, bench build) with source URLs and licenses of each corpus.
5. **requirements.txt** — stdlib-only for the runtime (verify); harness/server
   extras if any.

## Strongly wanted
6. `docs/depth-ladder.md` — D1 methodology writeup (withheld combos, co-occurrence
   check, premise scoring) + the 0.0 -> 14/58 story with panel-v2 caveats (exact
   citation checking + matched negatives are being repaired — note it honestly).
7. Quickstart in README: minimal REPL against the chain with a tiny bundled demo
   corpus (or corpus-less demo showing typed declines + reflection).
8. CI: GitHub Action running the import check + a 10-question smoke (corpus-less).
9. Version/tag proposal: `v0.1.0-architecture` release, title
   "ORACLE7 — the compiler learning model (architecture release)".
   Release notes: draft from README "It builds itself" + the 2026-08-25 record.
10. Decide public repo name with Ben (`oracle7`, `compiler-learning-model`, ...).

## Notes
- `docs/admission_ledger_digest.jsonl` = gate verdicts + reasons only (no world
  content). The full ledgers stay private.
- The w-chain here is the manifest ancestry (w2/w3/w11 orphans excluded by design).
- Corpora are NOT in the repo; sealed panels reference them by build name.
- Coordinate with the oracle7 site tab (`ORACLE7_EXECUTION_SPEC_2026_08_25.md`) so
  the site links the GitHub release and vice versa.
