# PREREG (FROZEN) — GOAL-6 Stage 0: re-baseline the ruler

Frozen: 2026-07-28, before any Stage-0 run.
Design: orchestrator `doc/research/2026-07-28-goal6-model-capability-design.md` §5 Stage 0.
Author: claude · Adversarial reviewer: codex.
Cost: zero new data, zero cloud, CPU only (the 43-fold scoring precedent ran 11s/fold).

## 0. Known-trap checklist (mandatory section; each item names a real past failure)

| # | past failure | how THIS design avoids it |
|---|---|---|
| T1 | 2026-07-28: chose a `shift+120d` placebo that turned out to sit on the **peak** of the score's own predictive profile (IC lag-100d = +0.078, t=3.21), making `real − placebo` structurally negative and the decision statistic uninformative | no lag-shift null is used as a decision statistic. Nulls are §3: label permutation within date, and a **persistence-matched** control. The lag profile is measured as a RESULT, never used to define the null |
| T2 | 2026-07-28: reported naive per-date t (+5.39) on overlapping 60-day labels whose block-adjusted t was +0.70 | every t in this study is fold/block-level; naive t may be reported for comparability but is never a decision input, and each table states its `n_eff` |
| T3 | 2026-07-27→28: an invocation was frozen without an end-to-end smoke on the exact environment, and the batch was VOID | a 2-fold smoke on the exact command runs BEFORE the full sweep; the sweep is only launched if the smoke's outputs parse |
| T4 | 2026-07-28: machine slept 5h mid-run, freezing a batch at 12/43 | any run >15 min is launched under `caffeinate -i -w <pid>` |
| T5 | recurring: absolute IC quoted without its matched null | every reported effect is a REAL − NULL difference with its own dispersion; absolute values appear only in descriptive tables that say so |
| T6 | recurring: post-hoc subgroup search rescuing a dead result | the hypothesis set below is closed. Regime/sector/date splits are descriptive-only and may not change any verdict |
| T7 | 2026-06→07: production inputs mutated by an experiment | read-only: no write outside the scratch dir; no file under `RenQuant/data/` or any live artifact/state is opened for writing |
| T8 | recurring: model/panel internals implemented in the orchestrator | this study lives in **renquant-model**; the orchestrator holds only the design + registry |

## 1. Question

Given the same already-trained models and the same panel, **which
measurement choice — statistic and horizon — has the most power to detect
the edge that is actually there?** This is a measurement study. No model is
trained, promoted, or killed by it.

## 2. Subjects and data

- **Models (already trained, unchanged):** (a) production panel-LTR XGB
  ranker; (b) the certified top-decile classifier (the blend leg); (c) the
  PatchTST 43-fold corpus scores already computed under model#85
  (`scores.parquet`, 88,750 rows, 625 disjoint OOS dates) — reused, not
  recomputed.
- **Panel:** the existing `transformer_v4_wl200_clean.parquet`
  (142 tickers, 2016-01-04 → 2026-04-28), read-only.
- **Labels:** `fwd_20d_excess` and `fwd_60d_excess`, both already present.
  Note they are cross-sectionally standardised (σ ≈ 1.005), so spreads are
  in cross-sectional σ units, not percentage points — every table must say so.

## 3. Statistics and nulls (frozen)

**Statistics (3):** per-date rank IC · top-decile minus bottom-decile spread
· top-decile hit rate (fraction of top-decile names with positive excess).

**Horizons (2):** 20d, 60d. Additionally, the **IC-vs-horizon profile**
(lags 0…160d in 20d steps) is computed as a descriptive result for each
model — this is the T1 finding promoted to a first-class measurement.

**Nulls (2, both computed for every statistic × horizon):**
1. **Within-date permutation**, 20 seeds — destroys cross-sectional ordering,
   preserves everything else. Verified clean in prior work (−0.0008).
2. **Persistence-matched control** — for each date, replace the model score
   with the model's own score from 60 trading days earlier (rank-preserving
   in time, signal-destroying in freshness). This isolates "does today's
   score add information beyond the persistence of an old score", which the
   T1 finding showed is the actual confound (cross-sectional rank
   autocorrelation 0.59 at 1d, 0.30 at 60d).

**Inference:** all effects reported as REAL − NULL with fold/block-level
dispersion; block length = ceil(label_horizon / rebalance spacing). Every
table states `n_eff`.

## 4. Hypotheses (closed set)

- **H1 (statistic):** the tail statistics (decile spread, hit rate) have
  higher power than full-cross-section IC on the same data.
  *Decision use:* if supported, the Stage-2 primary statistic is the tail
  spread; if refuted, Stage 2 keeps IC and the GOAL-6 §3 option A is
  withdrawn.
- **H2 (horizon):** the 20d label yields a higher power ratio (effect / SE)
  than 60d, at equal or lower effect size.
  *Decision use:* if supported, 20d becomes the **measurement** horizon for
  Stage 1–2 diagnostics. A trading-horizon change is explicitly out of scope
  and would need its own economics prereg.
- **H3 (horizon mis-specification):** at least one model's IC-vs-horizon
  profile peaks materially beyond its training horizon.
  *Decision use:* descriptive only in Stage 0. If supported, it opens a
  separate prereg — it does not modify H1/H2 verdicts.

## 5. Decision rule (frozen)

For each hypothesis, the decision statistic is the block-level t of
(REAL − within-date-permutation null), compared between the two arms being
contrasted (statistic A vs B for H1; horizon A vs B for H2).

- **SUPPORTED** — the favoured arm's t exceeds the other by ≥ 1.0 AND the
  favoured arm's own t ≥ 2.0.
- **REFUTED** — the favoured arm's t is lower, or its own t < 1.0.
- **INCONCLUSIVE** — anything else. Ties, ambiguity, or a broken run resolve
  to INCONCLUSIVE, and Stage 2 then proceeds with the CURRENT production
  choices (IC, 60d) rather than an unvalidated switch.

The persistence-matched null is reported for every arm and is a **veto**: if
an arm's REAL − persistence difference is not positive at t ≥ 1.0, that arm
cannot be declared SUPPORTED regardless of its permutation null, because its
apparent edge is stale-score persistence rather than fresh information.

## 6. Deliverable

One results document containing: the 3 × 2 statistic × horizon table per
model with both nulls and block-level inference; the IC-vs-horizon profiles;
the H1/H2/H3 verdicts under §5; and an explicit recommendation for the
Stage-2 primary statistic and measurement horizon. Negative and inconclusive
outcomes are reported with the same prominence as positive ones.
