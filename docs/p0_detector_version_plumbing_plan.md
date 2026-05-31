# P0.2 Implementation Plan — `detector_version` Plumbing

Scope of THIS PR: thread `detector_version` through the research harness
end-to-end, with tests pinning the contract. Specifically the W0 sub-task
"Detector version plumbing" from
`docs/patchtst_capability_research_proposal.md` §"Implementation And
Delivery Plan".

This PR does NOT include the rest of W0 (placebo smoke fixture, structured
ledger writes, evidence-status enum, label-lineage audits). Those follow as
sibling PRs per §"Recommended PR sequence".

## Why this is the right first cut

- Phase A.0 (the first kill-gate experiment) explicitly calls
  `--detector-version v2026-05-31` in its sample command. Without the flag
  wired, A.0 cannot run.
- The plan's "Decision runs must not use `--no-regime-contract`" rule means
  the contract gate must actually work. Today it defaults to "legacy" and
  hard-fails on `calm_2017`, forcing every research run to bypass via my
  earlier PR #8 (which is meant to be temporary scaffolding).
- This is the smallest scope that unblocks A.0 → cheapest validation that
  the merged plan's gate machinery actually executes.

## Pre-condition audit (from my implementer-lens review, item I1 + I4)

- **I1 — `ComputeRegimeLabelsTask` doesn't exist**: superseded.
  `ComputeRegimeLabelsTask` DOES exist at
  `src/renquant_model_patchtst/sequence_training.py:82-94`. My initial grep
  only checked `research_pipeline.py` and missed it. The merged plan was
  correct; this PR threads `detector_version` through that Task as well as
  the research_pipeline call sites.
- **I4 — `RENQUANT_STRATEGY_DIR` kernel.* dependency audit**:
  `grep -rn "from kernel\." src/renquant_model_patchtst/` returns no
  matches. The fallback path is safe to keep for now; removing it is a
  separate concern (P0.4 in the plan).

## Affected sites — concrete list (closes I1 + I2 ambiguity)

The merged plan's P0.2 says "wire to `ExperimentSpec`,
`RegimeDetectorContractTask`, `ComputeRegimeLabelsTask`, and
`PerRegimeICCallback`". Real-source enumeration:

| # | Site | File | Change |
|---|---|---|---|
| 1 | `ExperimentSpec` | research_pipeline.py | new field `detector_version: str = "v2026-05-31"` (post-fix default — research runs use the fix; `"legacy"` opt-out preserved) |
| 2 | `RegimeDetectorContractTask` | research_pipeline.py | pass `spec.detector_version` to `compute_hmm_regime_labels(...)`; stamp into `regime_contract` for audit |
| 3 | `_load_regime_labels` helper | research_pipeline.py | pass `ctx.spec.detector_version` to `compute_hmm_regime_labels(...)` |
| 4 | `_trial_argv` | research_pipeline.py | append `--detector-version <spec.detector_version>` to subprocess argv so the trainer process sees it |
| 5 | `research.py` CLI | research.py | new `--detector-version` flag, default `"v2026-05-31"`, plumb to `ExperimentSpec` |
| 6 | `hf_trainer.py` CLI | hf_trainer.py | new `--detector-version` flag, default `"v2026-05-31"` |
| 7 | `ComputeRegimeLabelsTask` | sequence_training.py | thread `args.detector_version` into `compute_hmm_regime_labels(...)` |
| 8 | `StampEnvironmentTask` | research_pipeline.py | add `detector_version` to `ctx.environment` for audit |

That's 5 source files touched, 7 sites. I2's "5th plumbing site"
(`_trial_argv`) is now explicit.

## Default-value decision (closes I-review item)

Three options:
- (a) Library default of `compute_hmm_regime_labels` stays `"legacy"`;
  research CLI defaults to `"v2026-05-31"`; production cron unaffected.
- (b) Library default flips to `"v2026-05-31"`; everything switches at once.
- (c) Both default to `"legacy"`, force explicit opt-in everywhere.

This PR picks **(a)**. Rationale:

- `renquant-common`'s `DETECTOR_VERSION_DEFAULT` is `"legacy"` per its own
  PR #3 design (production-safety: no behavior change for daily cron).
- Research runs need the corrected detector by default — otherwise every
  user has to remember `--detector-version v2026-05-31` or get gated by
  `calm_2017` mislabel.
- The harness CLI default `"v2026-05-31"` is the operator opt-in pathway
  per the merged plan.

The full library default flip (option b) is downstream task #28 and
requires sim parity, not in scope here.

## Test surface

| Test | Pins |
|---|---|
| `test_research_cli_default_uses_corrected_detector` | research.py CLI default → `ExperimentSpec.detector_version == "v2026-05-31"` |
| `test_research_cli_can_override_to_legacy` | `--detector-version legacy` → `ExperimentSpec.detector_version == "legacy"` |
| `test_research_cli_rejects_unknown_detector_version` | `--detector-version garbage` → ValueError (delegated to renquant-common) |
| `test_contract_task_threads_detector_version` | `RegimeDetectorContractTask.run(ctx)` invokes `compute_hmm_regime_labels(..., detector_version=spec.detector_version)` |
| `test_load_regime_labels_threads_detector_version` | `_load_regime_labels(ctx)` likewise |
| `test_trial_argv_appends_detector_version` | `_trial_argv(spec, ...)` includes `--detector-version <value>` |
| `test_hf_trainer_cli_default_uses_corrected_detector` | hf_trainer.py CLI default `"v2026-05-31"` |
| `test_per_regime_callback_uses_correct_detector_version` | `PerRegimeICCallback` constructed with labels from the correct detector version |
| `test_environment_stamps_detector_version` | `StampEnvironmentTask` writes `detector_version` to `ctx.environment` |

All tests use synthetic data (no MPS, no SPY file required) so this PR
remains compute-light and CI-friendly.

## What this PR does NOT do

Explicit deferred-scope list per the merged plan's §"Recommended PR sequence":

- Placebo smoke fixture and Phase A.0 invocation script — sibling PR
  `model-p0-placebo-smoke`.
- Structured ledger writes (cut/seed/config/cross-stock/FiLM/detector-version
  as structured fields, not `notes`) — sibling PR.
- Evidence-status enum + legacy importer (`suspect_pre_pr9_placebo_bug`) —
  the bigger I5 work, broken into 5a/5b/5c sub-PRs per my implementer-lens
  review.
- Label-lineage audit fields — sibling PR.
- DLinear/NLinear adapter — W1.
- Selection-metric ablation — W2.
- Architecture changes (market/factor token, multi-horizon heads, FiLM
  retest) — W2 + decision experiments behind A.1/A.2 gates.

## Implementation discipline (from §1c + §7.10)

- Every code change keeps the existing T/J/P shape — `Task.run(ctx)` mutates
  `ctx`, returns `True`/`False`/`None`. No new orchestration primitives.
- `compute_hmm_regime_labels` is the single source of truth; this PR only
  threads a parameter through callers. No re-implementation.
- Tests pin contract, not internals — they instantiate the existing
  classes and assert on observable side-effects.
- All new arguments document their default + the rationale ("v2026-05-31
  corrects the calm_2017 mislabel; `legacy` preserved for production
  parity").
