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
| **T11 (new, this session's actual bug)** | **cross-lag statistics computed on a drifting sample** — `Y.shift(-lag)` nulls the NEWEST rows, so longer lags silently drop the most recent dates; measured impact: lag-0 IC +0.028→+0.043 (PatchTST), +0.069→+0.100 (prod XGB), the rise losing 60% and the second model REVERSING (z = −2.09) | every cross-lag and cross-arm comparison runs on `align_lags(...).dates` from `renquant_model_common.lag_alignment` (model#89). The run FAILS if any arm is computed off that common sample. `dropped_per_lag` is reported. |
| **T12 (new)** | **arms drawn from different score windows** — the closure test paired REAL `scores[L:N]` against PERSIST `scores[0:N−L)`, an era term worth 19–28% of the statistic | both arms of every paired comparison are restricted to the SAME score dates before any statistic is computed |

## 1. Subjects (all three, same treatment)

| subject | corpus | note |
|---|---|---|
| prod XGB (panel-LTR) | `data/exp/oos_pick_table_recipe_v2.parquet` | the model that actually trades — also the positive control |
| certified top-decile clf | `clf-wf/clf_wf_scores.parquet` | 43 folds, 178,191 rows; recipe fidelity proven bitwise against the served artifact (max abs prediction diff 0.0) |
| PatchTST | `wf-eval/scores.parquet` | UNRESOLVED; model#85 UNDERPOWERED, model#87 retracted |

Comparative tables run on the **142-name intersection**; each subject's own
universe figures are reported alongside as descriptive.

## 2. Measurements (frozen)

- **Statistics:** per-date rank IC; top-decile minus bottom-decile spread.
- **Horizon:** 60d (the traded horizon). 20d reported descriptively only —
  Stage 0 already found no power gain there and this prereg does not retest it.
- **Nulls:** within-date permutation (20 seeds) and the persistence-matched
  control, both computed on the common sample per T11/T12.
- **Lag profile:** lags 0/20/40/60/80/100/120/160, ALL on one common sample.
  Reported as a RESULT; never used to define a null.
- **Inference:** block-level, block length = the arm's own label horizon,
  `n_eff` stated in every row.

## 3. Questions and frozen rules

**Q1 — does each subject beat its own persistence?** `d = REAL − persistence`
on IC at 60d, block-level t over folds, both arms on the common sample.
- **FRESH-INFORMATIVE** if `t_d ≥ 1.0`; **PERSISTENCE-DRIVEN** if `t_d ≤ −1.0`;
  otherwise **UNRESOLVED**.
- The prod XGB acts as the design's positive control: if IT lands UNRESOLVED or
  PERSISTENCE-DRIVEN, the design lacks the sensitivity to say anything about
  the other two, and **all** verdicts become UNRESOLVED.

**Q2 — is the lag profile real once the sample is fixed?** Descriptive, with
one registered decision: **PROFILE-CONFIRMED** only if, on the common sample,
some lag > 0 beats lag 0 with block-level `t ≥ 2.0` for the prod XGB AND at
least one other subject agrees in direction. Anything else is
**PROFILE-WITHDRAWN**, and the parked horizon prereg (model#88) stays parked.

**Q3 — which statistic carries more power?** Same as Stage 0's H1, recomputed:
tail spread vs IC, on the common sample, decided by which arm's `REAL − permutation`
block-level t is higher by ≥ 1.0 with the winner's own t ≥ 2.0. Ties →
INCONCLUSIVE → production keeps IC.

Ties, ambiguity, or any broken arm resolve to the conservative branch
(UNRESOLVED / WITHDRAWN / INCONCLUSIVE). No verdict here authorises a live
change; a positive result authorises the next gate-chain step, nothing more.

## 4. Discipline

Read-only over the corpora and the panel; scratch-only writes; every number
provenance-tagged (LONG rule #10); negative and inconclusive outcomes reported
with equal prominence; frozen — any change is a timestamped amendment written
before the affected run.
