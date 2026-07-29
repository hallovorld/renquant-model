# GOAL-6 Stage 0 — RESULTS (frozen prereg model#86, executed 2026-07-28)

Executed exactly as frozen; no design deviations. Wall time 10m03s
(compute 12.3s), zero cloud spend, read-only.

## Verdicts under the frozen §5 rule

| hypothesis | verdict | consequence |
|---|---|---|
| **H1** tail statistic vs IC | **INCONCLUSIVE** | Stage 2 keeps the CURRENT production choices: primary statistic = IC |
| **H2** 20d vs 60d horizon | **NOT SUPPORTED** | measurement horizon stays 60d |
| **H3** horizon mis-specification | **SUPPORTED for PatchTST**, not for XGB | descriptive only; opens a separate prereg, changes nothing here |

## The decision grid — REAL minus NULL, block-level t

Spread in cross-sectional σ units; hit is a fraction.
`[VERIFIED — goal6-stage0/results.json, results_xgb.json]`

| subject | statistic | 20d perm t (n_eff) | 20d persist t | 60d perm t (n_eff) | 60d persist t |
|---|---|---|---|---|---|
| PatchTST | IC | +0.88 (32) | **−2.00** | +0.93 (11) | **−2.31** |
| PatchTST | spread | **+2.11** (32) | −0.92 | **+2.03** (11) | −1.28 |
| PatchTST | hit | +0.39 (32) | −1.13 | +0.82 (11) | −0.79 |
| XGB | IC | +1.18 (26) | +1.39 | +1.28 (9) | +1.23 |
| XGB | spread | **+2.10** (26) | +1.13 | +1.99 (9) | +0.97 |
| XGB | hit | +1.59 (26) | +1.59 | +0.98 (9) | +0.34 |

Permutation nulls measured clean (IC level +0.0008 to +0.0013). Fold-level
cross-check reproduces the 43-fold run to 2dp (+2.94 spread / +1.17 IC vs
+2.90 / +1.16).

## The finding that matters most (negative, given top billing)

**The persistence-matched null splits the two models by sign, in all six
cells each.**

- **XGB:** REAL − persistence is **positive everywhere** (+0.34 … +1.59) —
  today's score adds information over a 60-trading-day-old one.
- **PatchTST:** **negative everywhere** (−0.79 … −2.31) — a 60-trading-day-old
  PatchTST score predicts today's forward return **better than today's score
  does**.

Internally consistent with the lag profile: fresh-vs-60d-label IC = +0.0278,
stale-vs-same-label = +0.0705, predicting a −0.043 effect against −0.056
measured `[DERIVED — verdict.log consistency block]`. **PatchTST's apparent
walk-forward edge is stale-score persistence, not fresh information.** This
is precisely the confound the persistence null was written to catch, and it
fired.

## IC-vs-horizon profiles (descriptive)

- **PatchTST** (trained on `fwd_60d_excess`): 0d +0.028 (t=1.22) → 40d +0.053
  → 60d +0.071 → **100d +0.078 (t=3.21)** → 120d +0.072 → 160d +0.045. Peak
  is **2.8–3.1× the lag-0 IC**, well beyond the training horizon.
- **XGB:** 0d +0.069 (t=1.92) → 40d +0.088 → 80d +0.076 → 160d +0.089 —
  essentially flat; the peak sits at the last measured lag, so the true peak
  may lie beyond 160d.

## Coverage and disclosures

- **Top-decile clf NOT covered.** Only a single 2026-07-28 fit exists; no
  fold dirs and no `(date, ticker, score)` corpus. Building one needs a WF
  training loop, which this prereg forbids. The `h2_xgb_score_*` files were
  **rejected as in-sample** (3 model loads for 827 scored dates).
- §5 does not name which horizon H1 is tested at (or which statistic for
  H2), so the rule was applied to **every cell** and all cells reported. No
  cell was selected post-hoc.
- XGB corpus: `data/exp/oos_pick_table_recipe_v2.parquet`, 508 dates
  2024-02-02…2026-02-11, 43-fold `walkforward_manifest_gbdt_prod_recipe_v2`,
  generator asserts `effective_train_cutoff + lookahead BDay < score date`
  `[VERIFIED — manifest recipe block]`.

## What this changes

1. **Stage 2 proceeds with IC at 60d** — the frozen rule's default, because
   neither alternative cleared its bar. The spread was directionally the
   strongest statistic in **4 of 4** cells (the only statistic to reach
   t ≥ 2.0 anywhere, while IC never exceeded +1.28), but a consistent
   direction that does not clear a preregistered bar is not a licence to
   switch.
2. **The GOAL-6 design's "20d buys power" claim is falsified.** 20d yields
   ~3× the independent blocks but loses proportionate effect size, so the
   power ratio is flat. The design document's MDE ladder assumed constant
   effect across horizons; that assumption is now measured and wrong.
3. **PatchTST's fate is no longer a power question.** The 43-fold rule
   returned UNDERPOWERED; Stage 0 adds an orthogonal, decisive-looking
   result — its edge is stale persistence. Closing it as an alpha source now
   needs its own frozen prereg with a kill rule; this document does not
   pronounce one, by design.
