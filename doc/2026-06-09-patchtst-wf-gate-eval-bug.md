# PatchTST WF-gate evaluation is broken — the model is good, the gate measures it wrong

**Date:** 2026-06-09 · **Author:** Claude · **Status:** open bug, fix plan below
**Severity:** HIGH — the gate emits a **false negative** on a good production model,
which (a) blocks the live daily from buying and (b) nearly led to a wrong
"retire the model" decision.

---

## 0 · TL;DR

The WF gate reports the live PatchTST primary (`pt07`) at cross-sectional
`real_ic = -0.017` → **FAIL**. That number is a **gate measurement artifact**, not
the model. The model's own held-out evaluation is **IC +0.07 / +0.117**, per-regime
**BEAR +0.19**. Two compounding bugs in the gate's PatchTST scoring path cause the
false negative. **Do not trust the gate's verdict on any PatchTST artifact until
both are fixed.**

## 1 · Ground truth — the model is good

| source (independent of the gate) | value |
|---|---|
| native held-out val_preds IC (full, 2025-02..2026-02) | **+0.0706** |
| native held-out IC on the gate's labelled window (≤2025-11-15) | **+0.117** |
| checkpoint `per_regime_ic` | **BEAR +0.192**, BULL_VOL +0.052, CHOPPY +0.031 |
| training calibrator `pool_ic` | +0.043 |

`score_with_history` is *fundamentally* sound: on a freshly-pipeline-trained cut it
reproduces native predictions at **+0.95 correlation**. The failure is specific to
how the **gate** drives it.

## 2 · Root cause #1 — the gate evaluates on the WRONG dataset

- The gate's sanity panel loader hardcodes the dataset:
  `renquant-backtesting/src/renquant_backtesting/wf_gate/runner.py::_load_sanity_panel`
  → `REPO/data/alpha158_291_fundamental_dataset(_rawlabel).parquet`.
- But `pt07` (and the weekly PatchTST cuts) were **trained on a different dataset**:
  `data/transformer_v4_wl200_clean.parquet` (recorded in the artifact's
  `training_contract.dataset`; the trainer's `--dataset` default).
- A model rank-normalized (CSRankNorm) and fit on dataset A, scored on dataset B
  with different feature values/universe, sees **out-of-distribution inputs** →
  near-noise predictions.

**Evidence (same model, same scorer, only the dataset changes):**
```
score_with_history IC on alpha158_291 (gate's panel)        = -0.017
score_with_history IC on transformer_v4_wl200 (own dataset) = +0.017   (sign flips)
```
The dataset alone accounts for a ~+0.034 swing.

## 3 · Root cause #2 — two divergent scorer implementations (§7.5 violation)

There are **two** PatchTST scorer classes for the same job:

| used by | class | file |
|---|---|---|
| **gate** | `PatchTstStatefulScorer` | `renquant-model/.../renquant_model_patchtst/scorer.py` (via `renquant_common.load_scorer`) |
| **production / training eval** | `HFPatchTSTPanelScorer` | `renquant-pipeline/.../kernel/panel_pipeline/hf_patchtst_scorer.py` |

Even **on the right dataset**, the gate's scorer recovers only `+0.017`, versus the
model's native `+0.117` on the same window — so the gate's scorer **diverges from the
path that actually scores the model correctly**. `HFPatchTSTPanelScorer`'s own
docstring warns: *"at inference time, panel_history MUST be CSRankNorm'd or the model
sees out-of-distribution feature scales and produces garbage scores."* The likely
divergence is in **how/over-what-universe CSRankNorm is applied** and in **sequence
construction**, between the two implementations.

## 4 · How to fix

**Fix A — dataset (renquant-backtesting `wf_gate`):**
`_load_sanity_panel` must load the **candidate's own training dataset** (resolve
`artifact.training_contract.dataset` / sidecar metadata), not a hardcoded path. Thread
the dataset down through `run_sanity_battery` → `_load_sanity_panel`. Default to the
current alpha158 path only when the artifact records no dataset (GBDT). Add a test:
a PatchTST artifact whose `training_contract.dataset` ≠ alpha158 loads that dataset.

**Fix B — unify the scorer (§7.5 single source) — the load-bearing one:**
Collapse the two PatchTST scorers to one. Preferred: the gate's manifest sanity
(`_score_manifest_sanity` `.pt` branch in `runner.py`) loads and scores via the SAME
implementation production uses (`HFPatchTSTPanelScorer`), OR the two classes are merged
in `renquant-model` and both consumers import it. First, **pin the exact divergence**
with a unit test that scores one checkpoint through both classes on identical
`(panel_history, tickers)` and asserts equal scores; the failing assertion localizes
the bug (suspects: CSRankNorm universe = history-window vs full-panel; `fillna`
ordering; `tail(seq_len)` window edges; NaN handling).

**Validation recipe (must hold after the fix):**
1. `score_with_history(checkpoint)` vs native `val_preds` on identical `(date,ticker)`
   → correlation ~1.0 (today: pt07 path degrades; fresh-cut path already ~0.95).
2. Gate `real_ic` on a PatchTST candidate ≈ its native held-out IC within noise
   (pt07 should read ≈ **+0.117** on the ≤2025-11-15 window, not −0.017).
3. Only *then* does the §7.2 placebo verdict mean anything — the placebo-gate
   calibration is a **separate** question (RFC #259 P1/P2), not part of this bug.

## 5 · What is NOT the cause (ruled out)

- Not the recipe fingerprint (fixed separately, renquant-backtesting #48).
- Not feature-column order (identical between pt07 and fresh cuts, matches checkpoint).
- Not `uses_film_regime` / `uses_cross_stock_attn` / `seq_len` / CSRankNorm flag
  (all identical between pt07 and the correctly-scored fresh cut).
- Not a sign flip in `score_with_history` (returns the same `score` head as the
  native path).

## 6 · Related

- `memory/patchtst-gate-eval-unreliable.md`, `memory/recipe-coverage-gap-blocks-gbdt-gate.md`
- RFC #259 (overlapping-label placebo gate) — the *calibration* question, downstream of this.
- renquant-backtesting #48 (recipe-fingerprint robustness) — merged, unrelated to this bug.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
