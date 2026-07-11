# Vol/trend feature-set v2 — candidate returns-based vol (C1/F1) + trend interactions (C2/F2)

**What:** the `vol_trend_v2` feature recipe — C1/F1 (returns-based vol) and
C2/F2 (trend interactions), the two candidate feature changes orchestrator
#476 §5 lists for its §7 preregistered experiment — as a versioned,
config-gated, **experiment-contract-gated** addition to the GBDT panel feature
recipe. Recipe spec + reference implementation + version-key mechanics +
experiment-contract promotion gate + tests. **No production behavior
changes:** the columns are not in the production panel, no artifact is
retrained or re-scored, and the production readiness config is untouched.

**2026-07-11 revision note (Codex CHANGES_REQUESTED, model#44).** The original
version of this PR described F1/F2 as arising from a "STD60 provenance
verdict" and cited "92-101% trend-confounded on trending names" as an
established, general-adoption fact. Codex's review correctly identified this
as overstated: #476 (after its own Codex-driven correction) establishes only a
mechanically-reproduced decomposition on one path (the META 07-06..07-10
rally) plus explicit hypotheses (H1-H4), not a general verdict, and its own §7
states the required next artifact is a **preregistered** baseline-vs-C1+C2
comparison that has not run. This revision (a) reframes every claim below from
"fix for a proven defect" to "candidate implementation for that not-yet-run
preregistered experiment", and (b) adds an experiment-contract gate so a
`vol_trend_v2` artifact cannot become promotion-eligible without a declared,
matching experiment id and an associated run bundle — see "Experiment-contract
promotion gate" below.

**Provenance (cited, required reading — hypotheses, not a verdict):**

- orchestrator **#476** — `doc/research/2026-07-11-std60-rule-provenance.md`:
  H3 ("qlib `STD60 = std(close LEVELS, 60d)/close_today` mistakes trend for
  calm on trending names") is, per the doc's own post-Codex-review status, "a
  live hypothesis — mechanical decomposition independently reproduced [on the
  META path]; causal-mechanism claim not established" (§3). §5 lists C1
  (returns-based vol) and C2 (trend-interaction features) as *candidates to
  evaluate under the preregistered plan in §7*, explicitly NOT a fix menu or a
  recommendation. §7 requires a preregistered, purged/embargoed walk-forward
  comparison of the baseline STD-family recipe vs. a C1+C2 redesign before
  either is adopted; that experiment has not run.
- orchestrator **#475** — `doc/research/2026-07-11-meta-score-attribution.md`:
  during META's 2026-07-06..07-10 +11.5% rally, STD60 fell 10.2% purely via the
  denominator (numerator +0.1%) while 60d returns-vol ROSE 4.8% — a
  re-verified measurement of that one path, not a general-adoption claim.

This PR's existence does not itself validate or invalidate anything about the
current STD60 feature. That determination is exactly what the #476 §7
preregistered experiment — not yet run — would produce.

## The recipe (6 new columns, self-documenting names)

`src/renquant_model_gbdt/vol_trend_features.py` — canonical spec + reference
implementation (exact conventions in the module docstring: simple daily
returns, strict full-window `min_periods`, ddof/denominator per statistic).

C1/F1 — candidate returns-based volatility measure:

| column | definition |
|---|---|
| `ret_vol_20d` | std of daily simple returns, trailing 20 returns, ddof=1 |
| `ret_vol_60d` | std of daily simple returns, trailing 60 returns, ddof=1 |
| `ret_semivol_down_60d` | downside semi-deviation: sqrt(sum(min(r,0)^2)/(n-1)), 60 returns |

C2/F2 — candidate trend-interaction features (testing the H3 hypothesis, not
yet established as the fitted model's actual mechanism):

| column | definition |
|---|---|
| `resid_vol_60d` | regression std error of a 60d linear fit of close (sqrt(SSR/(n-2))) / close_today — detrended STD60 |
| `std60_x_ret_120d` | qlib STD60 × signed 120d simple return |
| `high_52wk_dist_x_ret_vol_60d` | (1 − close/rolling_max(close, 252)) × `ret_vol_60d` |

## Version-key mechanics

- Precedent: Track B stamps `feature_addendum_v1` (recipe-variant identity) when
  its columns appear in the panel; the WF gate's recipe-match check reads it.
- Minted version: **`feature_set_version = "vol_trend_v2"`**, stamped by
  `LoadPanelTask` as a `vol_trend_v2` sub-object **nested inside
  `feature_addendum_v1`** whenever any of the 6 columns is present in the
  loaded panel.
- Why nested rather than a new top-level `feature_addendum_v2` key:
  renquant-common's fail-closed fingerprint contract
  (`model_fingerprint.PREDICTIVE_KEYS`) classifies `feature_addendum_v1` as one
  atomic PREDICTIVE unit and **hard-errors on any unclassified top-level key**
  (`UnclassifiedKeyError`); adding a top-level key is a cross-repo
  classification-table change that module reserves for reviewed contract
  migrations (`FINGERPRINT_SCHEMA_VERSION`). Nesting binds the v2 recipe into
  `model_content_sha256` today with zero shared-contract changes — proven by
  `test_vol_trend_stamp_binds_into_model_content_fingerprint`.
- Readiness gate: `wf_retrain_readiness` accepts the new set **only behind the
  declared version key** — a retrain config that sets
  `feature_set_version: "vol_trend_v2"` (top level or under `full_wf_retrain`)
  gains checks (`config_requires_vol_trend_features`,
  `artifact_contains_vol_trend_features`, `artifact_stamps_vol_trend_addendum`,
  plus the experiment-contract checks below). Undeclared configs produce a
  byte-identical readiness report.
- The production readiness config
  (`configs/gbdt_track_b_full_wf_retrain_readiness.json`) is **not** modified:
  production keeps the old feature set until a gated retrain adopts the new
  one — pinned directly against the committed file by
  `test_vol_trend_v2_disabled_by_default_in_production_config`.

## Experiment-contract promotion gate (new this revision)

Training/experimentation under `vol_trend_v2` remains unrestricted — no
declaration is required to compute the columns or train a candidate artifact
with them. **Promotion eligibility is a separate, stricter gate:**

- A retrain config that declares `feature_set_version: "vol_trend_v2"` must
  also declare a non-empty **`experiment_id`** (top level or under
  `full_wf_retrain`) — the identifier of the preregistered #476 §7 comparison
  the run stands in for. This mirrors the `experiment_id` convention already
  used in this codebase's own experiment tooling (orchestrator's
  `expkit.prereg.FrozenSpec.experiment_id` and `config_experiment_store`'s
  `config_experiments.experiment_id`).
- `LoadPanelTask` carries two new (optional, default-`None`)
  `GbdtTrainingContext` fields — `experiment_id` and `experiment_run_bundle_ref`
  — verbatim into the `vol_trend_v2` stamp whenever the recipe is active.
  Leaving them `None` does not block training; it only means the resulting
  artifact's stamp will have `experiment_id: null, run_bundle_ref: null`.
- `wf_retrain_readiness.validate_full_wf_retrain_readiness` adds a new check
  `config_requires_vol_trend_experiment_id` (config must declare a non-empty
  id) and `artifact_stamps_vol_trend_experiment_contract` (the artifact's
  `vol_trend_v2` stamp must carry an `experiment_id` that **matches** the
  config's declared id, plus a non-empty `run_bundle_ref`). Both are part of
  `report["ok"]` whenever `vol_trend_v2` is declared — an artifact tagged
  `vol_trend_v2` without a valid, matching experiment id and run bundle
  reference is **never** promotion-eligible through this readiness check,
  regardless of the feature/addendum checks passing.
- **No freshness/manual-override bypass:** renquant-model itself has no
  freshness-override or manual-promotion code path (verified: no
  `manual_override`/`freshness_override`/`force_promote` hits anywhere in this
  repo). The actual freshness-override mechanism referenced in the model
  freshness governance policy lives in `renquant-orchestrator`
  (`model_freshness_enforcer.py`) — a different repo, out of this PR's scope
  per the subrepo ownership model. That module is explicitly **observe-only**
  ("this module reads + classifies + recommends. It NEVER retrains, promotes,
  swaps pins, or changes any artifact" — its own docstring) and selects a
  `promote_passing` recommendation strictly by reading a
  `wf_gate_metadata.passed` bit. Because this PR makes the experiment-contract
  check a mandatory component of `wf_retrain_readiness`'s `ok` output whenever
  `vol_trend_v2` is declared, no code path in any repo can cause that `passed`
  bit to be true for a `vol_trend_v2` artifact without the experiment contract
  — the gate is enforced at its single source of truth, not just documented.
  (Additionally: a missing-experiment-contract failure reason does not match
  any of that module's `INFRA_FAILURE_KEYWORDS`, so it is classified as a
  substance failure, not infra — meaning even the deferred/unimplemented
  "promote freshest infra-only-failure" fallback would not surface it.)

## Zero default behavior change (the contract this PR must satisfy)

- Existing artifacts and their scoring are byte-unaffected: no scorer/transform
  code touched; old artifacts carry no new columns; `feature_cols` still derives
  from the panel file, which does not contain the new columns in production.
- A Track-B-only panel stamps the exact pre-v2 addendum dict (same keys, same
  order) — pinned by `test_track_b_only_panel_stamps_byte_identical_pre_v2_addendum`.
- A baseline panel produces an artifact with no `vol_trend` trace — pinned by
  `test_baseline_full_pipeline_artifact_has_no_v2_trace`.
- Trainer byte-identity is independently pinned by the pre-existing
  `test_panel_trainer_parity` golden (still green).

## Tests

`tests/gbdt/test_vol_trend_features.py` — **26 tests** (20 original + 6 new
this revision; full suite: 332 → 358 passed, 3 skipped, local run via the
RenQuant venv):

- recipe correctness against brute-force goldens (rolling std / semivol /
  `np.polyfit` residual std; strict warmup-NaN policy);
- the reproduced #476 §3 decomposition on controlled synthetic fixtures: a
  55-flat + 5-day +11.5% smooth rally deflates qlib STD60 >5% while
  `ret_vol_60d` does not fall; trending-quiet vs flat-quiet names with
  identical return noise get the same `ret_vol_60d` but separate by >5x on
  `std60_x_ret_120d`; `resid_vol_60d` is exactly linear-trend-invariant while
  STD60's numerator inflates >3x on the same noise; the 52wk-high interaction
  pins to 0 at highs — pinned as fixture properties, explicitly not claims
  about the live model/corpus;
- version-key mechanics: stamp present iff columns present (with
  `experiment_id`/`run_bundle_ref` defaulting to `None` and propagating
  verbatim from `ctx` when the caller sets them); Track-B-only and baseline
  panels byte-identical to pre-v2; fingerprint binding; readiness behind the
  declared key with an unchanged default report;
- **new — the experiment-contract gate:** `test_readiness_fails_when_config_omits_experiment_id`,
  `test_readiness_fails_when_artifact_missing_experiment_contract`,
  `test_readiness_fails_on_experiment_id_mismatch`,
  `test_readiness_fails_when_run_bundle_ref_missing`,
  `test_readiness_accepts_declared_vol_trend_config_and_artifact` (updated to
  require the full contract), and `test_vol_trend_v2_disabled_by_default_in_production_config`
  (reads the actual committed production config file).

## Adoption path (explicitly NOT this PR)

Adoption = the **standard gated retrain + promotion path — the #467 weekly-rail
protocol, with the experiment-contract gate above satisfied. No override.**
Concretely: (1) renquant-base-data rebuilds the panel with the 6 columns per
this reference spec (separate PR in that repo, validated against this module's
golden vectors); (2) the #476 §7 preregistered experiment is declared
(`experiment_id` + design) before any run; (3) a retrain config declares both
`feature_set_version: "vol_trend_v2"` and the matching `experiment_id`; (4) the
candidate runs the full WF gate (placebo-clean, per the preregistered
comparison design in §7 — baseline recipe vs C1+C2 redesign) and is promoted
only on a pass AND with the experiment-contract check green. Nothing in this
PR — and no freshness/manual override — puts these features in production
ahead of that.
