# F-7 follow-up: bake `provenance` into every artifact manifest this repo builds

**Date:** 2026-07-14
**Branch:** `fix/f7-provenance-none`
**Companion PRs:** renquant-artifacts#24 (round 3), RenQuant#471 (r9)
**Trigger:** Codex round-3 follow-up review on renquant-artifacts#24, quoted verbatim:

> **[P1] `provenance.kind="none"` remains a direct bypass of the experiment
> gate.**
>
> The required field closes omission, but it does not establish
> producer-written lineage: an artifact built from a registered experiment
> can set `{"kind": "none"}` and `verify_artifact_provenance()` returns
> immediately... A legitimate non-experiment artifact needs a verified
> producer class and its own evidence contract, not an unverified `none`
> assertion...
>
> This remains a breaking cross-repo migration: update the model
> artifact-manifest producer first, then merge artifacts, bump the umbrella
> pin, and materialize a clean integration checkout. Do not merge or pin
> #471 until that chain proves both experiment rejection and normal model
> publication.

## What this repo turned out to be, for this review

Investigated where artifact manifests are actually WRITTEN (not just
validated) across the multirepo. `renquant-artifacts` only reads/validates
(`registry.py`); `RenQuant/scripts/run_sim_104.py` only produces sim
performance metrics, never a manifest (before its own r9 fix). The real,
first-class producer is **this repo**:
`BuildArtifactManifestTask.run()` (`src/renquant_model_gbdt/pipelines.py`)
and its PatchTST twin `BuildPatchTstArtifactManifestTask.run()`
(`src/renquant_model_patchtst/pipelines.py`). Both already call
`validate_panel_artifact_contract()` / `validate_model_evidence_contract()`
(strict) against the trained artifact BEFORE building the manifest dict —
this is exactly the "verified producer class... its own evidence contract"
the review asks for, already real and already enforced here; it just
wasn't threaded into the manifest's `provenance` field at all.

A secondary, ad hoc producer
(`experiments/gbdt_scratch_from_archived_20260528/promote_candidate.py`)
hand-builds an equivalent manifest and writes directly into
`renquant-artifacts/registry/`. It lives on the unmerged
`feat/g4-score-backfill` branch — flagged as a known follow-up rather than
touched here (out-of-scope surgery on another in-flight branch).

## Fix

Both `BuildArtifactManifestTask.run()` and
`BuildPatchTstArtifactManifestTask.run()` now set
`manifest["provenance"] = {"kind": "none"}` as part of the manifest dict,
before `validate_artifact_manifest(manifest)` is called. This is the
honest, git-reviewable declaration renquant-artifacts#24 (round 2) already
requires as a REQUIRED field, and round 3's `_verify_none_provenance`
independently re-checks it against this manifest's own
`local_artifact_path`/`artifact_path` for a nearby EXPLORATORY_ONLY
classification marker — an ordinary training artifact (built here) never
has one, so the honest declaration validates as intended.

`experiments/gbdt_scratch_from_archived_20260528/promote_candidate.py`
(unmerged branch) was NOT touched — see above.

## Cross-repo migration proof (why this had to go first)

Ran this repo's FULL test suite (796 tests) against renquant-artifacts#24
round 3's fixed contract (via `ARTIFACTS_SRC=<that-worktree>/src make
test`): **796 passed, 0 failures** — proves ordinary model publication
(GBDT + PatchTST training pipelines) still works end-to-end under the new,
stricter provenance contract.

Then reverted JUST this branch's `provenance` addition (`git stash` on
`pipelines.py` + the two test files) and re-ran against the SAME fixed
renquant-artifacts contract: **4 tests fail**
(`test_training_pipeline_uses_common_task_job_pattern`,
`test_full_wf_pipeline_writes_readiness_report_to_manifest_metrics`,
`test_patchtst_training_pipeline_runs_sanity_stage`,
`test_pipeline_runs_with_adapter_checkpoint`), all with
`ValueError: artifact manifest is missing a required 'provenance' record`.
This is the live proof of the breaking-migration risk Codex flagged:
merging renquant-artifacts#24 and bumping this repo's pin BEFORE this fix
lands would break every real training run in production. Restored the fix
afterward; re-confirmed 796/796 passing.

## Tests

- `tests/gbdt/test_training_pipeline.py`: added an explicit assertion
  (`ctx.artifact_manifest["provenance"] == {"kind": "none"}`) to the
  existing end-to-end pipeline test rather than adding a parallel test, to
  keep the manifest's full shape asserted in one place.
- `tests/patchtst/test_training_pipeline.py`: same.
- Full suite: 796 passed, 2 skipped (pre-existing, unrelated), 0
  regressions, run against renquant-artifacts#24 round 3's fixed contract.

## Not yet done (explicit follow-ups)

- No PR opened yet for this branch (this doc ships with the branch so the
  eventual PR has it ready).
- `promote_candidate.py` (unmerged `feat/g4-score-backfill` branch) still
  needs the same one-line `provenance` addition before that branch merges
  — flagged, not fixed here.
- Umbrella `subrepos.lock.json` pin bump for `renquant-artifacts` (and, once
  this branch merges, `renquant-model`) is a follow-up once all of
  renquant-artifacts#24, this branch, and RenQuant#471 (r9) have Codex's
  approval — see renquant-artifacts#24's progress doc for the full
  sequencing note.
