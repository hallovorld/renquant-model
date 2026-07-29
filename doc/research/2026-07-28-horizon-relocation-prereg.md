# PREREG (FROZEN) — is the panel's signal at a LONGER horizon than we trade?

Frozen: 2026-07-28, before the run. Author: claude · Reviewer: codex.
Origin: operator question — "用旧 patchtst 替代新 patchtst 来预测？这很诡异！
是不是哪里不对？如果真有 alpha 的话有可能 streamline 吗？"

## 0. Known-trap checklist

| # | past failure | avoided how |
|---|---|---|
| T1 | a placebo sitting on the signal's own peak | nulls here are within-date permutation and a **horizon-matched** shuffle; no lag-shift null anywhere |
| T2 | naive t on overlapping labels | block-level inference with the block length set to EACH arm's own label horizon (a 120d arm blocks at 120d, not 60d) — the longer arm is penalised correctly, never flattered |
| T6 | post-hoc horizon picking | the horizon grid is enumerated here before the run: 20, 60, 100, 120, 160 trading days |
| T9 | acting on a striking by-product | this registers the test; the descriptive lag profiles from Stage 0 / model#87 do NOT constitute its result |
| **T10 (new)** | **confusing "the score is stale" with "the signal is long-horizon"** — a stale score can look long-horizon because the score barely changes | an explicit **turnover-matched control**: the same test on a deliberately smoothed version of the prod XGB score (60-day rolling mean), which manufactures persistence WITHOUT changing the underlying signal. If smoothing alone reproduces the long-horizon profile, the effect is persistence, not horizon. |

## 1. The observation to be tested

Both evaluated subjects show per-date IC that RISES with label lag
`[VERIFIED — goal6-stage0/results.json, wf-eval/diagnostics.log]`:

| lag | PatchTST | prod XGB |
|---|---|---|
| 0d | +0.028 (t=1.22) | +0.069 (t=1.92) |
| 40d | +0.053 | **+0.088** |
| 80d | +0.072 | +0.076 |
| 100d | **+0.078 (t=3.21)** | — |
| 160d | +0.045 | **+0.089** |

This is a PANEL-level pattern, not a PatchTST quirk. If real, the recipes
are trained and traded at a horizon where their own signal is weakest.

Two competing explanations, and the design must separate them:
- **H-A (horizon relocation):** the information genuinely concerns returns
  3–6 months out. Actionable — retrain and trade at that horizon.
- **H-B (persistence artefact):** slow-moving scores plus overlapping labels
  manufacture the profile. Not actionable; the "signal" is an autocorrelation
  shadow. This is what closed PatchTST at 60d (model#87).

## 2. Design (frozen)

- **Subjects:** prod XGB corpus (primary — it is the model that trades) and
  the certified clf corpus, both on the 142-name intersection. PatchTST is
  included as a descriptive third subject only; it is CLOSED at 60d and this
  prereg cannot un-close it.
- **Horizon grid (frozen):** 20, 60, 100, 120, 160 trading days. For each,
  the label is the realised excess return over exactly that window,
  constructed from the same OHLCV source as the existing labels.
- **Statistics:** per-date rank IC and top-decile spread, block-level, with
  the block length set to the arm's OWN horizon.
- **Nulls, per arm:** within-date permutation (20 seeds) and the
  **turnover-matched control** of T10.
- **Cost realism (required, not optional):** each arm reports the implied
  holding period and the number of independent bets per year. A 120-day
  horizon quarters the rebalance count relative to 20 days; an effect that
  only appears at long horizons must still clear costs at the turnover it
  implies, and the report states that arithmetic explicitly.

## 3. Decision rule (frozen)

Let `h*` be the horizon maximising (REAL − permutation) block-level t for
the PROD XGB, with `t*` its value.

- **RELOCATE (open a shadow at h\*)** — `t* ≥ 2.0` AND `h* ≠ 60` AND the
  turnover-matched control at `h*` is materially weaker than REAL (its t
  below half of `t*`) AND the clf subject agrees in direction.
  Consequence: a shadow lane trained and scored at `h*`, entering through the
  standard gate chain. NOT a production switch.
- **STAY (60d is correct)** — `h* = 60`, or `t* < 2.0`, or the turnover
  control reproduces the effect.
- **INCONCLUSIVE** — anything else, including a broken arm.

Ties and ambiguity resolve to STAY: the burden of proof is on moving, not on
keeping. No post-hoc horizon outside the frozen grid may be adopted.

## 4. Why this matters beyond one model

If RELOCATE holds, every gate, label, and turnover assumption in the stack is
mis-specified in the same direction, and the fix is a recipe change rather
than a new architecture. If STAY holds, the long-lag profile is an
autocorrelation shadow and the programme keeps its current horizon with one
fewer open question. Both outcomes are useful; neither is a promotion.
