# F-7 round 4: verified workflow-classification, not a hardcoded `provenance.kind`

**Date:** 2026-07-14
**Branch:** `fix/f7-provenance-none` (same branch as PR #55 — round 4 continues it)
**Companion:** renquant-artifacts#24 (round 3, still unmerged as of this writing)
**Trigger:** Codex's round-3 follow-up review on PR #55, quoted verbatim (findings 1–2 only;
finding 3, commit-authorship, is out of scope here — see "Not touched" below):

> 1. `BuildArtifactManifestTask` and `BuildPatchTstArtifactManifestTask` now emit
> `{"kind":"none"}` unconditionally. These are generic training entry points; an exploratory
> or registered-experiment invocation can write to a fresh path with no prior
> EXPLORATORY_ONLY marker, so the proposed path lookup cannot distinguish it from canonical
> production. The producer is therefore self-classifying an experiment artifact as `none`,
> precisely the bypass the gate must prevent. Strict model-evidence/panel validation is
> necessary quality evidence, but it is not an immutable proof of workflow class or
> experiment lineage.
>
> 2. The correct contract is producer-written and non-forgeable at this boundary: the caller
> must supply a verified workflow classification derived from a canonical run bundle /
> registered experiment record; canonical publication records a canonical producer identity
> plus immutable WF-gate evidence, while experiment-originated artifacts carry the immutable
> experiment id and run-bundle digest. Reject missing or inconsistent classification. Do not
> default either path to `none`. The registry should validate that evidence, not infer
> absence from a mutable path.
>
> Please add adversarial integration coverage: execute the same model producer under a
> registered experiment context at a fresh artifact path and prove it cannot obtain
> canonical/none classification; prove normal canonical publication succeeds only with its
> immutable producer/WF evidence.

## Investigation: does a "canonical run" / "WF-gate evidence" / "run bundle" concept already exist?

Before designing anything new, searched this repo and renquant-orchestrator for an existing
convention to reuse, per this repo's own "check before inventing" discipline:

- **No environment variable / config flag / CLI switch** anywhere in `renquant_model_gbdt` or
  `renquant_model_patchtst` already distinguishes "canonical production training" from
  "research/experimental" invocation.
- **renquant-orchestrator DOES construct `TrainingContext` directly** for the real daily
  production retrain: `daily.py::TrainGbdtArtifactTask.run()` builds
  `TrainingContext(dataset_manifest=..., model_config=..., output_dir=...)` and runs it through
  `PanelGbdtTrainingPipeline`. `renquant_model_gbdt/__init__.py`'s own comment already
  documents this: "Consumed by renquant-orchestrator's DailyRunPipeline, which injects its own
  loader/trainer/validator." This IS the closest thing to "the canonical training entrypoint"
  in the whole multirepo — but it is not itself a non-forgeable proof of anything; it is just
  application code that happens to run once a day. `PatchTstTrainingContext` has NO known
  external caller today (PatchTST retrains go through a separate subprocess path,
  `renquant_model_patchtst.hf_trainer`, invoked from orchestrator's
  `build_patchtst_wf_manifest.py` / `retrain_patchtst.py`, which never constructs
  `PatchTstTrainingContext` directly).
- **renquant-orchestrator's `run_bundle.json`** (`PersistDailyRunBundleTask` in `daily.py`) is
  the closest existing "non-forgeable run identity" concept in this multirepo (this repo's own
  `CLAUDE.md` requires "persist a run bundle for every full run"). It bundles
  `strategy_config_hash`, `data_manifest`, `artifact_manifest`, and more under one JSON file.
  But it is built AFTER the artifact manifest already exists, using the manifest as one of its
  OWN input fields — it cannot be the identity bound INTO the manifest at manifest-build time
  without a circular dependency (the run bundle doesn't exist yet when
  `BuildArtifactManifestTask` runs).
- **`experiments/ensemble_phase0/admissibility_ledger.py` / `experiment_manifest.py`** build
  real per-run evidence ledgers (fingerprints, cutoffs, digests, an
  `EXPLORATORY_ONLY`-by-default `nested_wf_harness_status`), but these are scoped to that one
  ensemble feature, not a repo-wide canonical-vs-experiment contract this task could bind to.

**Honest finding:** there is currently no non-forgeable "this is a genuine canonical
production run" evidence mechanism anywhere in this codebase for the manifest-build step to
bind to. Building one (e.g. a signed attestation bound at training time from a specific,
restricted canonical entrypoint) is a real, separate, larger design effort — not invented here
to paper over the gap. Per this task's own instruction, the narrower, defensible interim fix
below is what actually ships.

## The fix

1. **`workflow_class` is now a REQUIRED constructor argument with no default** on
   `TrainingContext` (`renquant_model_gbdt.pipelines`) and `PatchTstTrainingContext`
   (`renquant_model_patchtst.pipelines`). There is no code path left where a manifest is built
   without an explicit, auditable, per-invocation declaration — this directly closes the
   literal bug ("hardcoded regardless of context").
2. **New shared module** `renquant_model_common.workflow_provenance` (`build_verified_provenance`)
   — the ONE implementation both `BuildArtifactManifestTask` and
   `BuildPatchTstArtifactManifestTask` call, per this repo's "families share only through
   `renquant_model_common`" rule and its own triple-impl-avoidance lesson:
   - `workflow_class="canonical"` → `provenance = {"kind": "none"}` (residual limitation — see
     below).
   - `workflow_class="experiment"` → NOT trusted at face value. Independently verified by
     reusing the real `renquant_artifacts.experiment_registry` machinery round 3 already built:
     `model_config["experiment_registry_index_path"]` must be supplied; a real
     `_experiment_classification.json` marker must actually exist at `output_dir` (written by
     the registered-experiment harness via `write_experiment_classification()` BEFORE this task
     runs — a bare declaration with nothing on disk is rejected, not trusted); the marker's own
     `manifest_digest`/`experiment_id` are cross-checked against the immutable registry index
     via `verify_manifest_registered`. Only then is
     `provenance = {"kind": "experiment", "dir": ..., "registry_index_path": ...}` built via
     `build_experiment_provenance_reference` — never a caller-supplied dict taken on faith.
3. **`renquant_artifacts.experiment_registry` is imported LAZILY** (inside the function, not at
   module top level) because it only exists on the still-unmerged renquant-artifacts#24
   branch — a top-level import would break bare `import renquant_model_gbdt` /
   `import renquant_model_patchtst` for anyone still on renquant-artifacts main, which would be
   a far worse regression than the bug being fixed. Verified both ways (see Tests below).
4. **`ctx.artifact_manifest` is now set BEFORE `validate_artifact_manifest()` is called**, not
   after, in both `BuildArtifactManifestTask.run()` and `BuildPatchTstArtifactManifestTask.run()`.
   This means a genuinely-registered experiment's manifest — correctly built with
   `provenance.kind="experiment"` — is still visible on `ctx` for inspection even though the
   registry-side promotion gate (`reject_exploratory_promotion`) then correctly and
   unconditionally rejects it. This is what makes the adversarial test below possible without
   weakening the existing gate for any other failure mode.

## Honestly-disclosed residual limitation

`workflow_class="canonical"` still results in the bare, self-declared
`provenance = {"kind": "none"}` — the SAME residual-trust status this codebase's other
self-declared manifest fields already carry (`code_commit`, `config_fingerprint`), and the same
honesty standard round 3's own opaque `store://`/`object://` URI limit set. This PR does **not**
achieve full cryptographic non-forgeability for the canonical side — see the investigation
above for why (no such mechanism exists anywhere in this codebase yet to bind to). What it DOES
fix: the literal "hardcoded regardless of context" bug, by making the declaration explicit,
required, and auditable per call site, and by making the "experiment" side genuinely
independently verified rather than caller-asserted.

## Known, disclosed, NOT-fixed-here consequence: renquant-orchestrator's `daily.py`

`TrainGbdtArtifactTask` in renquant-orchestrator's `daily.py` constructs `TrainingContext(...)`
directly for the real daily production retrain — the one real external call site for this
class. Adding a required `workflow_class` field means that call site will raise `TypeError`
(missing required argument) until renquant-orchestrator is updated in a **coordinated follow-up
PR** to pass `workflow_class=renquant_model_gbdt.WORKFLOW_CLASS_CANONICAL`. This is the same
kind of sequenced, breaking cross-repo change this F-7 chain has already used (see PR #55's own
migration-order proof). Not touched here — out of scope for this repo's PR, flagged for the
operator/next session. `PatchTstTrainingContext` has no equivalent live external caller today,
so no parallel orchestrator-side break exists for the PatchTST twin.

## Adversarial integration test (the exact one Codex asked for)

`tests/gbdt/test_workflow_class_provenance.py::test_registered_experiment_at_fresh_path_is_never_none`
and its PatchTST twin in `tests/patchtst/test_workflow_class_provenance.py`:

- Run the REAL `BuildArtifactManifestTask` / `BuildPatchTstArtifactManifestTask` (via the real
  `PanelGbdtTrainingPipeline` / `PatchTstTrainingPipeline`, not mocks) under a genuinely
  registered experiment context.
- `output_dir` is a brand-new path (asserted `not output_dir.exists()` before the test's own
  `write_experiment_classification()` call) — no pre-existing marker, exactly the gap Codex
  described.
- Proves TWO things together: (1) the manifest's `provenance` correctly reports
  `{"kind": "experiment", ...}`, never `{"kind": "none"}`, verified via the real
  (non-mocked) `renquant_artifacts.experiment_registry` on-disk-marker + immutable-registry-index
  cross-check; (2) that correctly-classified manifest is THEN unconditionally rejected by the
  real registry-side promotion gate (`validate_artifact_manifest` →
  `verify_artifact_provenance` → `reject_exploratory_promotion`), proving a registered-experiment
  invocation cannot obtain canonical/none classification through this producer end-to-end.

Additional guard-rail tests (both families): missing `workflow_class` raises `TypeError`;
unrecognized `workflow_class` raises `ValueError`; `workflow_class="experiment"` with no
`experiment_registry_index_path` raises; with an index path but no on-disk marker raises; with a
real marker whose digest is NOT in the registry index raises. Positive control: genuine
canonical publication (`workflow_class=WORKFLOW_CLASS_CANONICAL`) still succeeds and still gets
`kind="none"` (asserted in the existing `test_training_pipeline.py` files, updated to declare
`workflow_class` explicitly, plus a dedicated PatchTST positive-control test).

These new test modules use `pytest.importorskip("renquant_artifacts.experiment_registry")` (same
idiom this repo already uses for optional torch/transformers) since that module only exists on
the unmerged renquant-artifacts#24 branch — they SKIP, rather than hard-erroring collection,
when the local sibling `renquant-artifacts` checkout is still on main.

## Tests

Ran the full suite twice, against both realistic sibling states:

- **Against `renquant-artifacts` main** (no `experiment_registry` module): **796 passed, 4
  skipped** (2 pre-existing unrelated + 2 new module-level skips for the workflow-class-
  provenance test files), 0 failures. Confirms bare `import renquant_model_gbdt` /
  `import renquant_model_patchtst` and all canonical-path tests work with zero regard for
  whether the sibling artifacts checkout has the F-7 round-3/4 machinery yet.
- **Against renquant-artifacts#24 round-3's fixed contract** (worktree PYTHONPATH override, same
  method PR #55 used): **807 passed, 2 skipped** (pre-existing, unrelated), 0 failures — the 11
  new tests (6 gbdt + 5 patchtst) all exercise the real experiment-registry machinery and pass,
  including the adversarial fresh-path test.
- `ruff check` clean on all touched/new files.

## Not touched (explicit scope boundary)

- Codex's finding 3 (commit-authorship rebuild) — being handled separately per the task's
  instruction; the underlying rule couldn't be independently verified to exist. Branch history
  left as-is; no force-push.
- renquant-orchestrator's `daily.py` — see "Known, disclosed, NOT-fixed-here consequence" above.
- `experiments/gbdt_scratch_from_archived_20260528/promote_candidate.py` (unmerged
  `feat/g4-score-backfill` branch) — same follow-up already flagged in the round-3 progress doc,
  unchanged here.
- No merge performed. Branch protection requires Codex's separate approval on this repo; the
  known credential-sharing merge-approval deadlock is being handled by the operator via a
  documented owner-only override, not by any workaround here.
