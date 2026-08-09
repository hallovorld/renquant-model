# L3 meta-label classifier — the one execution of the frozen prereg: KILL

The single execution of `doc/design/2026-08-09-l3-classifier-prereg.md` (v1,
model#207) as amended by `…-prereg-v2.md` (v2, model#208). Executed
2026-08-09, exactly as frozen: no threshold moved, no feature changed, no
second attempt. **Verdict: KILL** — in v1's own completed-outcome words,
*"the panel's entry quality is not predictable from these entry-time
features at this history."*

Reproducibility: `data/2026-08-09-l3-experiment-run.py` (the run script;
re-checks the frozen CSV hash `eecfd050…` at start) · committed outputs
`…-l3-exp-folds-all.csv`, `…-l3-exp-placebo.csv`,
`…-l3-exp-external.csv`, `…-l3-exp-pooled-predictions.csv`,
`…-l3-exp-summary.json` · `data/2026-08-09-l3-exp-verify.py` recomputes all
four legs from the committed artifacts alone and exits 1 on drift
`[VERIFIED — run this session: "VERIFIED — … verdict KILL"]`.

## 1 · The four legs `[VERIFIED — summary JSON + verifier recomputation]`

| leg | frozen bar | measured | result |
|---|---|---|---|
| 1 · fold consistency | median uplift@τ=0.5 > 0 AND ≥⅔ folds > 0 | median **+0.0017** (+17bp/20d), share **0.667** (6/9, exactly ⅔) | PASS — marginal |
| 2 · placebo | median > within-date-shuffle p95 (200 seeds) | +0.0017 > **0.0000** | PASS — near-vacuous (§3) |
| 3 · external (once-only, frozen 34 rows) | uplift ≥ 0 | **−0.0454** on the 4/34 rows clearing τ=0.5 | **FAIL** |
| 4 · calibration | pooled slope ∈ [0.5, 2.0] | **−0.0008** | **FAIL** |

KILL requires nothing further: legs 3 and 4 fail outright, and PASS demanded
all four.

## 2 · What the classifier actually learned: nothing out-of-sample

The decisive number is the calibration slope ≈ **0**: across 5,492 pooled
out-of-fold predictions, the fitted P carries no relationship to realized
wins. Per-fold AUC agrees — 9 folds range 0.41–0.62 around 0.5, and the
descriptive depth-2 GBDT does no better (0.48–0.60) `[VERIFIED — folds
CSV]`, so this is not "logistic too small"; the nonlinearity probe found
nothing either.

Mechanically, the model collapses toward the base rate: with base win rate
0.63, most predictions sit just above 0.5, so τ=0.5 selects 80–100% of each
fold's rows (e.g. 559/614, 777/792, 471/471). The "uplift" then measures the
exclusion of a small low-P tail — a +17bp/20d effect with no calibration
behind it. The one large fold (+2.8%, 2026-04, 253/1,730 selected) is the
only fold where the model discriminated at all, and it is a single fold in a
live-heavy quarter.

## 3 · Honest annotations on the two passing legs

* **Leg 2's bar was degenerate at this configuration.** 165 of the 200
  placebo runs produced a median uplift of EXACTLY 0.0 — a shuffled-label
  model predicts ≈ the base rate for every row, τ=0.5 selects everything,
  and the uplift is identically zero. The placebo p95 is therefore 0, and
  "beat the placebo" reduces to "excluded anything at all". The leg is
  reported as it was frozen, and it passed — but it screened out nothing,
  and a future prereg should place τ relative to the base rate (the v1
  design took τ=0.5 as neutral; with base 0.63 it is not).
* **Leg 1 sits exactly on its own edge**: share-positive is 6/9 = 0.667, the
  frozen minimum, and the median is +17bp against a 20-day horizon whose
  cross-sectional σ is ~12% — indistinguishable from noise without leg 4's
  support, which failed.

## 4 · The declared live-only variant: NOT EVALUABLE

The v1-declared live-only training variant produced **zero folds**: the live
slice spans 40 dates, and the frozen guards (≥60 pre-boundary dates, ≥300
training rows) are unreachable inside it. The variant is reported as
unevaluable rather than silently skipped — `…-folds-liveonly.csv` is empty
by measurement, not omission. Any live-only re-attempt needs a redesigned
fold scheme and is a NEW dated prereg.

## 5 · External detail (the once-only read)

The frozen 34-row list resolved exactly (34/34, no drift — the feasibility
verifier's funnel re-confirmed pre-run). Walk-forward fold models scored all
34; 4 cleared τ=0.5; those 4 underperformed the 34-row mean by −4.5pp
`[VERIFIED — external CSV]`. With 3 run dates and correlated horizons this
is a sign check, as both prereg versions scoped it — and the sign is
negative.

## 6 · What this record does NOT show

* Not that meta-labeling is dead here — only that THESE 4 entry-time
  features (panel_score, mu, rank_score, n_candidates_that_date) carry no
  OOS signal for fwd_20d>0 on this history. The features the serving drift
  removed (sigma, expected_return — orch#931) were never tested.
* Not that the panel is broken — the panel's own edge is not at issue; its
  entry-quality PREDICTABILITY from its own emitted scalars is.
* Not a license to iterate: v1's clause binds — no feature additions, no
  threshold moves inside this prereg. A new attempt (e.g. τ set relative to
  base rate, features from a repaired producer stamp, a live-only-feasible
  fold scheme) is a NEW dated prereg.

## 7 · Consequence for the three-layer machine

L3 as designed does not earn a shadow lane. The allocation machine's value
now rests on L1 (exposure control, shadow-deployed, first row 2026-08-10)
and L2 (allocation engine, backtested + cost-passed, merged). The L3 slot
stays empty until a new prereg passes — an empty slot is a valid state of
the design (orch#918 §3 scoped L3 as an independent, severable layer).
