# PREREG (FROZEN) — corrected signal evaluation, three subjects

Frozen: 2026-07-29, before the run. Author: claude · Reviewer: codex.

**Supersedes** the measurement portions of model#86 (Stage 0) and model#87
(closure). Both were computed with a harness whose cross-lag comparisons ran
on a drifting sample; their numbers may not be quoted. This prereg re-derives
them on the corrected primitive and is the only admissible source going
forward.

## 0. Known-trap checklist

| # | past failure | avoided how |
|---|---|---|
| T1 | a placebo sitting on the signal's own peak (shift-120 vs a profile peaking at 100d) | no lag-shift null is a decision statistic |
| T2 | naive per-date t on overlapping labels (+5.39 vs block-adjusted +0.70) | block-level inference only; `n_eff` printed per row |
| T6 | post-hoc subgroup rescue | closed hypothesis set; splits descriptive only |
| T9 | acting on a striking by-product of another study | every claim here is registered before computation |
| T10 | confusing "the score is stale" with "the signal is long-horizon" | turnover-matched control (a smoothed score manufactures persistence without changing signal) |
| **T11 (new, this session's actual bug)** | **cross-lag statistics computed on a drifting sample** — `Y.shift(-lag)` nulls the NEWEST rows, so longer lags silently drop the most recent dates. Measured directly in the bug-hunt scratch run (`bughunt/h9_fix.py` + `h9_results.json`, quarantined local scratch space, not committed to git by this project's design — same convention as `bughunt/h6_closure.py` + `h6_results.json`): holding the sample common moved lag-0 IC +0.028→+0.043 (PatchTST, `h9_results.json.PatchTST.fixed_set."0".ic_fixed`) and +0.069→+0.100 (prod XGB, `...prodXGB.fixed_set."0".ic_fixed`); the closure-test recomputation on the common sample separately dropped PatchTST's block-count from 4/4 to 0/4 and the prod-XGB positive control from 4/4 to 1/4 (`h6_results.json`: `p_as_closure=4, p_fixed=0, ctrl_as_closure=4, ctrl_fixed=1`) — a z ≈ −2.09 reversal on the prod-XGB rise-vs-lag0 statistic at lag 80–100. **CORRECTION:** an earlier revision of this row struck this table as "fabricated" after a search that covered only git branch history; the scratch directory is intentionally outside git (§4 "scratch-only writes"), and re-verified directly against the actual files on disk the numbers above are exactly what is recorded — restored, not fabricated. | every cross-lag and cross-arm comparison runs on `align_lags(...).dates` from `renquant_model_common.lag_alignment` (model#89). The run FAILS if any arm is computed off that common sample. `dropped_per_lag` is reported. |
| **T12 (new)** | **arms drawn from different score windows** — the closure test paired REAL `scores[L:N]` against PERSIST `scores[0:N−L)`, an era term worth 19–28% of the statistic | both arms of every paired comparison are restricted to the SAME score dates before any statistic is computed |

## 1. Subjects (all three, same treatment)

| subject | corpus | note |
|---|---|---|
| prod XGB (panel-LTR) | `data/exp/oos_pick_table_recipe_v2.parquet` | the model that actually trades — also the positive control |
| certified top-decile clf | `clf-wf/clf_wf_scores.parquet` | 43 folds, 178,191 rows; recipe fidelity proven bitwise against the served artifact (max abs prediction diff 0.0) |
| PatchTST | `wf-eval/scores.parquet` | UNRESOLVED; model#85 UNDERPOWERED (MERGED 2026-07-29T08:10:54Z), model#87 retracted (MERGED 2026-07-29T08:10:45Z) |

Comparative tables run on the **142-name intersection**; each subject's own
universe figures are reported alongside as descriptive.

## 2. Measurements (frozen)

- **Statistics:** per-date rank IC; top-decile minus bottom-decile spread.
- **Horizon:** 60d (the traded horizon). 20d reported descriptively only —
  Stage 0 (model#86, MERGED 2026-07-29T08:10:49Z) already found no power gain
  there and this prereg does not retest it.
- **Nulls:** within-date permutation (20 seeds) and the persistence-matched
  control, both computed on the common sample per T11/T12.
- **Lag profile:** lags 0/20/40/60/80/100/120/160, ALL on one common sample.
  Reported as a RESULT; never used to define a null.
- **Inference (frozen estimator):** every decision statistic in §3 is computed
  by `renquant_model_common.lag_alignment.dependence_aware_mean` (model#89) on
  the per-date series in date order, `block_length` = the arm's own label
  horizon. `dependence_aware_mean` returns a block-t, a moving-block bootstrap
  CI, and leave-one-block-out bounds, and its `.resolves` property is True
  only when all three agree on sign — no verdict in §3 uses a bare single-
  statistic threshold. `n_blocks` stated in every row.

## 3. Questions and frozen rules

**Q1 — does each subject beat its own persistence?** `d[t] = REAL[t] −
persistence[t]`, the per-date IC difference at 60d on the common sample.
`dependence_aware_mean(d, block_length=60)`, `ci_level=0.90`.
- **FRESH-INFORMATIVE** if `.resolves` and `.mean > 0`; **PERSISTENCE-DRIVEN**
  if `.resolves` and `.mean < 0`; otherwise **UNRESOLVED** (this replaces a
  bare `t_d` threshold with three-way agreement, per `dependence_aware_mean`'s
  own strict-by-design `.resolves` contract).
- The prod XGB acts as the design's positive control: if IT lands UNRESOLVED or
  PERSISTENCE-DRIVEN, the design lacks the sensitivity to say anything about
  the other two, and **all** verdicts become UNRESOLVED.

**Q2 — is the lag profile real once the sample is fixed?** For the prod XGB,
compute `rise[L][t] = IC_lag_L[t] − IC_lag_0[t]` for each of the 7 non-zero
lags `L ∈ {20,40,60,80,100,120,160}` on the common sample, then
`dependence_aware_mean(rise[L], block_length=L)` per lag — **7 tests, one
family**, so the per-lag `ci_level` is Bonferroni-corrected:
`ci_level = 1 − 0.10/7 ≈ 0.9857` (holds the family-wise rate at the same 0.10
Q1 uses for one test). Let `L*` be the lag with the largest `.mean` among the
7. **PROFILE-CONFIRMED** only if `rise[L*]` `.resolves` at the corrected
`ci_level` for the prod XGB AND at least one other subject's `rise[L*]`
(same `L*`, same corrected level) also `.resolves` with the same sign.
Anything else is **PROFILE-WITHDRAWN**, and the parked horizon prereg
(model#88) stays parked. No lag outside the frozen grid may be substituted
after seeing which one wins.

**Q3 — which statistic carries more power?** NOT a comparison of two
independently-computed t-statistics (that discards their shared block-level
noise and is not a valid contrast). Instead, a **paired per-block series**,
fully specified so it needs no run-time judgment call:
1. Partition the common sample into 60d blocks (T2's rule).
2. For each of the 20 within-date permutation seeds, average that seed's
   per-date `IC_perm` over the dates in block `b` — one block-level null draw
   per seed. `mean(IC_perm[b])`/`sd(IC_perm[b])` are the mean/sd of those 20
   draws. Identical construction for `spread_perm[b]`.
3. `z_IC[b] = (mean_date(IC_real[b]) − mean(IC_perm[b])) / sd(IC_perm[b])`;
   `z_spread[b]` likewise, both from the SAME 20 seeds and the SAME blocks
   (paired, not independent).
4. `diff[b] = z_spread[b] − z_IC[b]`; `dependence_aware_mean(diff,
   block_length=1)` (the series is already one value per block, so no further
   aggregation window — `block_length=1` makes each block its own unit for
   the bootstrap/LOBO views).

**SPREAD-MORE-POWERFUL** if `.resolves` and `.mean > 0`; **IC-MORE-POWERFUL**
if `.resolves` and `.mean < 0`; otherwise **INCONCLUSIVE → production keeps
IC** (ties/non-resolution favour the status quo, not the challenger).

Ties, ambiguity, or any broken arm resolve to the conservative branch
(UNRESOLVED / WITHDRAWN / INCONCLUSIVE). No verdict here authorises a live
change; a positive result authorises the next gate-chain step, nothing more.

## 4. Discipline

Read-only over the corpora and the panel; scratch-only writes; every number
provenance-tagged (LONG rule #10); negative and inconclusive outcomes reported
with equal prominence; frozen — any change is a timestamped amendment written
before the affected run.
