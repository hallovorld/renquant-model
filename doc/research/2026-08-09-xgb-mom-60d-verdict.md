# xgb_mom_60d — the one execution: KILL, with an honest reading

The single execution of the merged prereg (model#211), run 2026-08-09,
zero deviations. **Verdict under the frozen §3 gate: KILL** — leg 2 fails
(4/8 folds with positive real signal; the bar was ≥6). Legs 1/3/4 pass.

Reproducibility: `data/2026-08-09-xgbmom-run.py` (the harness; real mode
was gated on the merge) · `data/2026-08-09-xgbmom-result.json` (per-fold
real / shuffle / real-signal, seed-mean) · pre-run controls committed
(`…-control-positive.json` PASS with planted signal +0.3715;
`…-control-null.json` KILL at −0.0027 — the harness detects what it
should and only that) · `data/2026-08-09-xgbmom-verify.py` recomputes the
legs and verdict from the committed JSON `[VERIFIED — exit 0]`.

## The per-fold picture `[VERIFIED — committed result JSON]`

| fold (test year) | real IC | shuffle IC | real signal |
|---|---|---|---|
| 2019 | −0.005 | +0.022 | **−0.026** |
| 2020 | +0.197 | +0.080 | **+0.117** |
| 2021 | −0.051 | −0.019 | −0.032 |
| 2022 | +0.018 | −0.008 | +0.026 |
| 2023 | +0.059 | +0.072 | −0.013 |
| 2024 | −0.010 | −0.002 | −0.009 |
| 2025 | +0.114 | +0.041 | **+0.073** |
| 2026 (to 05-07) | +0.131 | +0.090 | **+0.041** |

Mean real signal **+0.0221** (leg 1 pass); A/A seed std 0.0017 (leg 3);
recency guard pass (2025 and 2026 both positive). The kill is entirely
leg 2: the signal exists ON AVERAGE but only in 4 of 8 years.

## Honest reading

Learned momentum on this corpus is **episodic, not persistent**: strong
exactly in the high-dispersion years (2020, 2025, 2026), absent-to-negative
in the quiet ones. This matches the system's standing evidence from the
other direction — the formula arms' book value concentrated in the same
regimes, and the panel's own skill is documented as tail-driven and
episodic. The frozen gate demanded year-in-year-out consistency for a
STANDING expert arm, and that bar was not met — a completed outcome, not a
tuning invitation.

## What would be a legitimate next question (a NEW dated prereg, if ever)

A conditional-activation form — the momentum learner as an expert that an
allocation layer weights only in dispersion/volatility regimes — is the
hypothesis this table generates. It is NOT tested here, and nothing below
shadow-candidacy exists for it. Feature variants, window changes, or gate
softening on THIS prereg are prohibited by its own terms.

## Standing consequences

* No new arm enters the system from this line today.
* The shuffle floors (+0.02..+0.09 per fold) re-measure the corpus's known
  leakage floor and are consistent with prior records — differences, not
  levels, remain the only trustworthy statistic on this corpus.
