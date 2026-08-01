# Momentum prereg — Amendment 2 (visible, PRE-RUN): the adequacy envelope is degenerate as frozen

**Amends §4.3's AR-adequacy envelope only. Filed BEFORE any execution — the runner's
inference stage exists but has computed nothing on real data — per the same
implementation-before-freeze route that produced Amendment 1.**

## The defect `[本次实测 2026-08-01, model#169's inference tests]`

§4.3 froze: *"AR adequacy envelope: max abs ACF deviation over lags 1…40 ≤ 2 plug-in
SEs."* Implemented faithfully and probed on PERFECT-SPECIFICATION data — true AR(1)
series, correct family, correct fit, where the gate should pass essentially always — it
**rejects 15–19 of 20** (n=2150 φ=0.6: 18/20; φ=0.9: 15/20; n=600 φ=0.5: 19/20).

Two structural reasons: the **maximum** of K=40 noisy deviations almost surely exceeds a
per-lag 2·SE band (expected max ≈ 2.7σ under perfect spec), and `1/√n` understates ACF
sampling variance for dependent series (Bartlett's formula). Frozen as written, nearly
every execution would end **UNRESOLVED-METHOD regardless of truth** — the same defect
class as Amendment 1's F1: a rule that cannot behave as intended, in the opposite
direction (always-reject instead of always-zero).

## The amendment (v2, per review — bootstrap-calibrated, not approximated)

Replace the envelope with a **parametric-bootstrap-calibrated max test**:

> Fit the AR(p) null as §4.2 specifies. Simulate **B = 500** series from the fitted
> null (seeded, residual-resampled). Score each against the same implied-ACF curve as
> the real series: `D_b = max_{k≤40} |acf_b(k) − implied(k)|`. The gate threshold is the
> **95th percentile of {D_b}**; adequacy fails iff `D_real` exceeds it.

This calibrates the max statistic's threshold under the null itself — no per-lag SE
approximation, no max-of-K miscalibration — and, per the review, it assesses only the
GATE's threshold: whether AR is the right real-series null remains guarded by the
separate UNRESOLVED-METHOD outcome.

**Validation, frozen and partially executed:** independent perfect-specification sets
(fresh seed ranges, fit + full gate per trial). Measured at B=300, M=50 per case
`[本次实测 2026-08-01]`: false-failures **2/50, 2/50, 4/50** for (n=2150, φ=0.6),
(n=2150, φ=0.9), (n=600, φ=0.5) — all consistent with the nominal 5% (MC SE ≈ 3.1%).
**The full validation has EXECUTED and PASSED** `[本次实测 2026-08-01]` — M = 200
independent perfect-specification trials per case, B = 500 bootstrap draws per trial,
fresh seed ranges (50000+/90000+), against the frozen acceptance bar ≤ **0.10**
(= 0.05 + 3·√(0.05·0.95/200)):

| case | false failures | rate | verdict |
|---|---|---|---|
| n=2150, φ=0.6 | 6/200 | **0.030** | PASS |
| n=2150, φ=0.9 | 10/200 | **0.050** | PASS |
| n=600, φ=0.5 | 8/200 | **0.040** | PASS |

All three sit at or below the nominal 5% itself. Raw record committed at
`doc/research/data/2026-08-01-goal7-adequacy-validation/full_validation.json`,
sha256 `d61e980360eb3bbc5395b78fc206e869f1bdb6a867f09bbb2f2d331150c978a1`. Had any case exceeded 0.10, this amendment's replacement would have been
void by its own frozen criterion.

## What the first draft of this amendment got wrong, on the record

Draft 1 proposed a per-lag `z₁₋α/(2K) · Bartlett-SE` envelope whose own perfect-spec
false-failure rate measured 4/20 in the worst case — and argued the direction
("errors only cause UNRESOLVED") made that acceptable. The review rejected both: 20
trials is not evidence for a 5% familywise gate, and direction does not make an
uncalibrated refusal probability a calibrated criterion. Draft 2 replaces approximation
with calibration and argument with measurement.

## Not claimed

That the max-test envelope is optimal — it is the principled correction of the two
identified defects (max-of-K and dependence-blind SE), measured against the same
fixtures, with its residual imperfection stated. That any other §4 machinery changes:
generators, bars, reps, seed, α, and the no-collapse rule (#166's) are untouched.
