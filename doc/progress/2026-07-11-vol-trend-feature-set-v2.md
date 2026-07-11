# Vol/trend feature-set v2 — returns-based vol (F1) + trend interactions (F2)

**What:** the `vol_trend_v2` feature recipe — F1/F2 from the STD60 provenance
verdict — as a versioned, config-gated addition to the GBDT panel feature
recipe. Recipe spec + reference implementation + version-key mechanics + tests.
**No production behavior changes:** the columns are not in the production
panel, no artifact is retrained or re-scored, and the production readiness
config is untouched.

**Provenance (cited, required reading):**

- orchestrator **#476** — `doc/research/2026-07-11-std60-rule-provenance.md`:
  qlib `STD60 = std(close LEVELS, 60d)/close_today` is 92-101% trend-confounded
  on trending names; candidate fixes C1 (returns-based vol) and C2
  (trend-interaction features) assigned to renquant-model as feature-spec owner.
- orchestrator **#475** — `doc/research/2026-07-11-meta-score-attribution.md`:
  during META's 2026-07-06..07-10 +11.5% rally, STD60 fell 10.2% purely via the
  denominator (numerator +0.1%) while 60d returns-vol ROSE 4.8% — the model-side
  replay shows score sensitivity to STD60 on this path.

## The recipe (6 new columns, self-documenting names)

`src/renquant_model_gbdt/vol_trend_features.py` — canonical spec + reference
implementation (exact conventions in the module docstring: simple daily
returns, strict full-window `min_periods`, ddof/denominator per statistic).

F1 — returns-based volatility (the honest risk measure):

| column | definition |
|---|---|
| `ret_vol_20d` | std of daily simple returns, trailing 20 returns, ddof=1 |
| `ret_vol_60d` | std of daily simple returns, trailing 60 returns, ddof=1 |
| `ret_semivol_down_60d` | downside semi-deviation: sqrt(sum(min(r,0)^2)/(n-1)), 60 returns |

F2 — trend interactions ("quiet steady riser" vs "quiet dead money"):

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
  gains three checks (`config_requires_vol_trend_features`,
  `artifact_contains_vol_trend_features`, `artifact_stamps_vol_trend_addendum`).
  Undeclared configs produce a byte-identical readiness report.
- The production readiness config
  (`configs/gbdt_track_b_full_wf_retrain_readiness.json`) is **not** modified:
  production keeps the old feature set until a gated retrain adopts the new one.

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

`tests/gbdt/test_vol_trend_features.py` — **20 new tests** (suite: 332 → 352
passed, 3 skipped, local run via the RenQuant venv):

- recipe correctness against brute-force goldens (rolling std / semivol /
  `np.polyfit` residual std; strict warmup-NaN policy);
- the honesty properties on synthetic fixtures: a 55-flat + 5-day +11.5% smooth
  rally deflates qlib STD60 >5% while `ret_vol_60d` does not fall (the #475
  META week); trending-quiet vs flat-quiet names with identical return noise
  get the same `ret_vol_60d` but separate by >5x on `std60_x_ret_120d`;
  `resid_vol_60d` is exactly linear-trend-invariant while STD60's numerator
  inflates >3x on the same noise; the 52wk-high interaction pins to 0 at highs;
- version-key mechanics: stamp present iff columns present; Track-B-only and
  baseline panels byte-identical to pre-v2; fingerprint binding; readiness
  behind the declared key with an unchanged default report.

## Adoption path (explicitly NOT this PR)

Adoption = the **standard gated retrain + promotion path — the #467 weekly-rail
protocol. No override.** Concretely: (1) renquant-base-data rebuilds the panel
with the 6 columns per this reference spec (separate PR in that repo, validated
against this module's golden vectors); (2) a retrain config declares
`feature_set_version: "vol_trend_v2"`; (3) the candidate runs the full WF gate
(placebo-clean, per the preregistered comparison design required by #476 §7 —
baseline recipe vs C1+C2 redesign) and is promoted only on a pass. Nothing in
this PR — and no freshness/manual override — puts these features in production.
