# xgb_mom_60d — preregistration, frozen before any training run

STATUS: frozen before results. The operator's momentum model (terminology
reconciled 2026-08-09): an xgboost cross-sectional learner whose feature
set is EXCLUSIVELY the price-momentum family — not the frozen-formula arms
(mom_resid_252/63), not the full-feature panel. One execution after this
merges; PASS/KILL the day it completes; a retry is a new dated prereg.
Naming per orch#915: `xgb_mom_60d` (<family>_<method>_<clock>).

## 1 · Hypothesis

A learner restricted to price-momentum features carries REAL walk-forward
signal (above its own shuffle floor) on this corpus — i.e., the momentum
thesis survives being learned rather than hand-coded. `[knowledge anchor —
the L2 line measured the FORMULA arms' book value; this tests the LEARNED
form at IC level on identical folds to the production-family baseline]`

## 2 · Frozen experiment (every runner constant lives HERE)

| element | frozen choice |
|---|---|
| corpus | `data/alpha158_291_fundamental_dataset.parquet`, sha256 `870f68ebad5d2d87e2601f62310f34615d2d8d25df9d9cbf563629b13129bf7e` [VERIFIED — hashed this session]; 726,128 rows, 2016-01-04..2026-05-07 |
| features (explicit, 70) | BETA/CNTN/CNTP/IMAX/IMIN/MAX/MIN/QTLD/QTLU/RANK/ROC/RSV/SUMN/SUMP × windows {5,10,20,30,60} — the exact list is §5. VSUMP*/VSUMN* (10 cols) EXCLUDED: volume confirmation is a different thesis; this arm stays interpretable as price momentum |
| label | fwd_60d_excess (the corpus label; unchanged from the production family) |
| folds | the 7 reviewed CUTS of `wf_sanity_paired.py` verbatim PLUS an 8th: train 2016-01-01..2025-12-31, test 2026-02-01..2026-05-07 (the same convention as the emitted 2026 replay fold, sidecar-verified fold_train_end 2025-12-31) |
| model params | `run_wf` verbatim: rank:pairwise, eta 0.05, max_depth 5, min_child_weight 50, subsample 0.7, colsample 0.7, 100 rounds |
| seeds | A/A triple {42, 43, 44}; reported numbers are seed-means |
| guards | min_train_rows 1000, min_test_rows 100 (run_wf's, now FROZEN here — the L3 lesson: a pre-run script does not preregister) |
| placebo | within-date label shuffle, same 3 seeds, per fold — per-fold real signal = fold IC − fold shuffle IC |
| baseline (recorded, not gated) | the FULL-feature run on identical folds/seeds — the paired Δ is descriptive context, not a bar: this arm is an allocation EXPERT candidate, not a panel replacement |

## 3 · PASS / KILL (deterministic, all required)

1. seed-mean real signal (mean over folds of [IC − shuffle IC]) > 0;
2. ≥ 6 of 8 folds have positive seed-mean real signal;
3. A/A stability: the std of the 3 seeds' mean-IC ≤ 0.01 (a learner that
   flips sign across seeds is noise);
4. the 2026 fold's real signal is not the ONLY positive one among
   {2024, 2025, 2026} folds (recency guard: at least one other recent
   fold positive).

PASS earns a shadow-candidacy memo (deployment is a separate grant chain
and is additionally gated on closing orch#937/#939 — a new arm must not
inherit the validated-vs-traded gap). KILL is a completed outcome: "the
learned momentum form carries no real WF signal on this corpus."

## 4 · What this does not show

* No book/return-space claim (IC-level only; the L2 cost lessons stand).
* No serving claim (the #937 gap governs anything live).
* No feature search: the 70-column list is frozen; variants = new prereg.

## 5 · The frozen feature list (70)

BETA10 BETA20 BETA30 BETA5 BETA60 CNTN10 CNTN20 CNTN30 CNTN5 CNTN60
CNTP10 CNTP20 CNTP30 CNTP5 CNTP60 IMAX10 IMAX20 IMAX30 IMAX5 IMAX60
IMIN10 IMIN20 IMIN30 IMIN5 IMIN60 MAX10 MAX20 MAX30 MAX5 MAX60
MIN10 MIN20 MIN30 MIN5 MIN60 QTLD10 QTLD20 QTLD30 QTLD5 QTLD60
QTLU10 QTLU20 QTLU30 QTLU5 QTLU60 RANK10 RANK20 RANK30 RANK5 RANK60
ROC10 ROC20 ROC30 ROC5 ROC60 RSV10 RSV20 RSV30 RSV5 RSV60
SUMN10 SUMN20 SUMN30 SUMN5 SUMN60 SUMP10 SUMP20 SUMP30 SUMP5 SUMP60
