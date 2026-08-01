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

## The amendment

Replace the envelope with the max-test form:

> per-lag envelope `z₁₋α/(2K) · SE_k` with α = 0.05, K = 40, and Bartlett's-formula
> `SE_k = √((1 + 2·Σ_{j<k} r_j²)/n)`; the gate fails iff any lag's |empirical −
> implied| exceeds its own envelope.

Measured on the identical perfect-specification fixtures `[本次实测]`: rejects
**4/20, 0/20, 0/20** where the frozen rule rejects 18/20, 15/20, 19/20.

## Honesty about the residual miscalibration

The 4/20 cell (n=2150, φ=0.6) is above the nominal ~1/20 and did not move when the
implied-ACF simulation precision was raised 8× — the rule is approximately sized, not
exact, and this amendment does NOT claim otherwise. The direction prices it: an
adequacy false-reject can only ever produce **UNRESOLVED-METHOD** — it costs
completed-run probability, never verdict validity. A rule erring toward refusing to run
is acceptable; the frozen rule erring toward *always* refusing is not a gate at all.

## Not claimed

That the max-test envelope is optimal — it is the principled correction of the two
identified defects (max-of-K and dependence-blind SE), measured against the same
fixtures, with its residual imperfection stated. That any other §4 machinery changes:
generators, bars, reps, seed, α, and the no-collapse rule (#166's) are untouched.
