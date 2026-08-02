# GOAL-6 Job B: gbdt WF depth-extension tool — built; golden parity FAILED (input vintage), batch gated off

**Bottom line:** the Job B driver (`tools/wf_gbdt_depth_extension.py`) is built and
verified on its pure surface, the backward ladder is computed (**82 new windows,
2019-01-14 .. 2023-09-11**, 21-calendar-day grid), but the mandated golden
reproduction of the earliest existing window **FAILED prediction parity:
max|Δ| = 0.6489841341972351** (target < 1e-6) over 4380 OOS rows / 15 dates
`[VERIFIED: doc/research/data/2026-08-02-jobb-gbdt-depth-extension/golden_report.json]`.
Per the Job B spec this is reported without rationalization and the batch was NOT
launched; the tool now hard-refuses batch mode until a passed golden exists.
**Decision needed upstream:** the existing 43-window ladder cannot be
byte-reproduced from current inputs (the June-vintage input bytes are gone), so
depth extension requires either (a) regenerating the WHOLE ladder on the current
input vintage first, or (b) an explicitly documented vintage seam. This tool
refuses to make that call silently.

## Golden verdict — localization (measured, not assumed)

Reproduction path is byte-faithful in everything the current inputs still permit:

| check | result |
| --- | --- |
| training slice (rows/tickers/dates) | 526515 / 292 / 1890 — EXACT match |
| sentiment-gate zeroed rows | 366713 — EXACT match (regime replay reproduced) |
| effective_train_cutoff_date | match (2023-07-10) |
| config_fingerprint | match (sha256:f8fb2259b2bf1537, from the strategy-104 subrepo config) |
| 158 global_z norm constants vs today's stats file | max drift 1.8e-9 (float noise) |
| in-sample train IC | +0.1365 vs reference +0.1389 |
| booster bytes | DIFFER → prediction max\|Δ\| = 0.649 |

The divergence localizes to the 5 fundamental columns' robust-z refit:
`data/sec_fundamentals_daily.parquet` was rebuilt **2026-08-01** (panel + stats
files same day) with revised historical values. Measured drift on the golden
train slice: `gross_profitability` median Δ = 7.13e-3 — exactly the
`feature_means_max_abs_delta` in the report; `book_to_price` robust scale
Δ = 9.45e-3 — exactly the `feature_stds_max_abs_delta`. One alpha raw-clip
bound also changed. Different training matrix ⇒ different booster. This is an
input-vintage fact, not a recipe/path divergence.

## What was built

* `tools/wf_gbdt_depth_extension.py` — Job B driver, mirroring the Job A shape
  (`wf_clf_corpus_rebuild_persist.py`): read-only over RenQuant
  (`sys.dont_write_bytecode` set before any umbrella import), recipe imported
  live from `renquant_model_gbdt` (LoadPanelTask → sentiment training gate →
  BuildNormalizationTask → TrainBoosterTask → BuildArtifactTask → fingerprint →
  smoke — the exact `renquant_orchestrator.train_gbdt` sequence the manifest
  names as trainer, with `skip_cv` per the manifest options), params
  ARTIFACT-CARRIED (earliest window's `params` + `best_iter`) and
  cross-asserted equal to `PANEL_LTR_PARAMS` / `DEFAULT_N_ROUNDS`.
* Ladder convention DERIVED from the manifest, not invented: all 42 gaps are
  exactly 21 calendar days, all cutoffs Mondays, and 2023-12-25 (NYSE holiday)
  is a cutoff ⇒ pure arithmetic grid, no holiday adjustment; OOS windows are
  panel trading dates in `(cut, next_cut]`.
* Per-window artifacts mirror the existing windows KEY-FOR-KEY with exact-type
  parity (`check_artifact_field_parity`, incl. the stringified-norm_kind
  incident guard) and must share the existing ladder's recipe fingerprint
  (recipe_match.py mirror) or the window refuses.
* Extension lineage manifest under the #94 append-only rule: new ordered sha
  list (new windows chronologically BEFORE the existing 43), new
  `lineage_root_sha`, old root recorded and recomputable from the suffix;
  `recipe_id` = the lineage lane's recipe fingerprint rule.
* Structural refusals mirrored from backtesting `lineage_lane`: duplicate /
  unordered ladders, artifact-vs-manifest cutoff mismatch, missing artifacts.
* `--out-dir` refuses to resolve inside the umbrella; every input is
  digest-recorded at read time (panel, stats, fundamentals, WF manifest,
  strategy config, SPY OHLCV, GMM artifact).
* Batch gate: `require_golden_pass` — the full batch refuses to train without
  a PASSED `golden_report.json` (added after the measured failure above).

## Config source (measured 2026-08-02)

The strategy-104 SUBREPO config reproduces the June artifacts'
`config_fingerprint` (sha256:f8fb2259b2bf1537) and `config_fingerprint_fields`
byte-exactly; the umbrella copy has drifted (sha256:14586756d4f67691 today).
Every regime key the replay tasks consume was measured equal in both; the
effective sentiment policy matches the artifact-carried policy, and the tool
hard-asserts the produced gate contract against the reference window.

## Numbers

* Ladder: 82 new windows, earliest 2019-01-14, latest 2023-09-11 (panel min
  2016-01-04 — reaches past 2019, no truncation; min-train-dates floor 250
  never binds) `[VERIFIED: extension_plan.json]`.
* Golden fit wall time: **6.7 s** fit, 14.0 s total per window (panel load
  0.4 s cached, regime replay 6.5 s). Implied batch: ≤ 82 × 14 s ≈ **19 min**
  upper bound (backward windows train on strictly less data); ~21–30 min for
  the spec's 90–130-fit range.
* Tests: new file **23 passed**; full suite **1328 passed** (was 1305 before
  this branch).

## Not done / blocked

* The 82-fit batch: NOT launched (golden parity failed; batch mode now refuses
  by construction). Unblocking is an upstream vintage decision, not a tool fix.
