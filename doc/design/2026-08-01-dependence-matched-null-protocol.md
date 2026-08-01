# Dependence-matched null construction — a protocol FOR DISCUSSION

**Status: FOR DISCUSSION, not frozen. No real decision series is touched by this
document, and nothing here licenses running any test.**

## One protocol, two waiting consumers

1. **model#161 (approved discussion draft):** its §3a′ leaves the momentum H1 at
   **UNRESOLVED-METHOD** *"until a null calibrated against the real series — its
   construction and acceptance criteria separately frozen — supports it."* This is that
   construction, proposed.
2. **model#154 (v1-vs-v2 Stage-A):** its amendment-2d ask — replace the gate's
   `dependence_aware_mean` (gap = 0 blocks; its own docstring forbids inferential use)
   with *"a dependence-preserving bootstrap of the caller's own per-date series"* — is
   the same instrument. Each contrast series would receive its own calibration under
   this protocol.

Shared evidence base, all previously measured: real per-date IC series carry
ρ₁ ≈ 0.82–0.975 while within-date permutation destroys it (model#153); the Bartlett/L=h−1
HAC is oversized even under the pure-overlap shape (size 0.117 at nominal 0.05, n=2150 —
independently audited UPHELD, two routes, with the analytic mechanism: L=19 captures only
66.75% of the overlap shape's long-run variance); gap-separated blocks are too few on
short series (4–5 at h=60/n≈565, model#157).

## The protocol, stepwise (all constants HERE are proposals for the freeze)

Given a per-date decision series `x_1..x_n` with label horizon `h`, level α, and the
frozen statistic pipeline `T` (e.g. HAC-t at a frozen L):

1. **Measure the dependence, don't assume it.** Sample ACF of the demeaned series to lag
   `3h`, with plug-in standard errors. Committed with the run.
2. **Fit a CANDIDATE SENSITIVITY MODEL by frozen rule.** AR(p) with `p` chosen by AIC,
   `p ≤ h`, on the demeaned series; innovations resampled i.i.d. from the fitted
   residuals (so heavy tails survive). **Adequacy gate:** the fitted model's implied ACF
   must match the sample ACF within a frozen envelope (max abs deviation over lags
   1..2h ≤ 2 plug-in SEs). Fail → **UNRESOLVED-METHOD**, stated, no fallback improvised
   at run time. **Per review, passing this gate does NOT make the fit a validated
   null**: an AR(p) matched on second moments can miss nonlinear or regime-switching
   dependence entirely, and its own adequacy gate cannot see what its family cannot
   express. A real-series VERDICT additionally requires a separately justified DGP
   argument — frozen by the consuming preregistration — for why this family covers the
   dependence that matters; absent that argument, the protocol's output is sensitivity
   evidence, not authorization.
3. **Calibrate.** Simulate ≥ 5,000 seeded series of length n from the fitted generator
   with mean forced to 0; push each through the IDENTICAL pipeline `T`; the empirical
   (1−α) quantile of |T| is the decision bar `t*`. Committed record: series digest,
   fitted parameters, residual pool digest, seed, reps, `t*`.
4. **Validation gates, run before any verdict is read:**
   * **positive control** — the committed pure-noise series through the identical
     protocol must not reject at ≈ α (within MC error);
   * **machinery self-check** — series simulated from the fitted generator, pushed
     through the full protocol, must reject at α within a frozen tolerance (this checks
     the plumbing, not the model);
   * **mis-specification stress** — size under the ALTERNATIVE family (overlap-MA(h−1)
     matched to the same variance). **Per review, reporting cannot substitute for error
     control**: if the alternative-family size exceeds 1.5α, the outcome is
     **UNRESOLVED-METHOD** — unless the consuming preregistration has PRECOMMITTED the
     conservative rule `t* = max(t*_fitted, t*_alternative)` (the worst-case bar over
     the admissible generator family), in which case the decision proceeds at that bar
     and at that bar only. Publishing both bars remains mandatory either way, as
     disclosure — never as the decision mechanism.
5. **Output discipline.** `t*` is series-specific and α-specific; nothing generalizes
   across series, and reusing a bar across series is a protocol violation by definition.
   And per the two review points above: what steps 1–4 yield is a calibrated
   SENSITIVITY instrument plus disclosure obligations; verdict authority comes only
   from the consumer's frozen DGP argument and (on stress failure) its precommitted
   worst-case rule.

## The honest weak point, named up front

Steps 1–3 estimate the null's WIDTH from the same series whose MEAN is being tested.
That is what every HAC does implicitly; making it explicit adds one real risk — if the
true mean is far from 0, the demeaned ACF is contaminated and the fitted null is slightly
too wide, pushing the test **conservative** (the safe direction, but a power cost, and it
must be said rather than discovered). A run report must state the sample mean alongside
the fitted parameters so a reader can judge the contamination risk.

## What this protocol does NOT do

It does not choose α, h, L, the AIC cap, the envelope width, or the stress threshold —
those freeze with each consumer's preregistration. It does not rescue underpowered
designs: a valid bar on 4–5 blocks of material is still a bar nobody can clear
(model#157). It does not validate `T` for series whose dependence the AR family cannot
express — that is exactly what the adequacy gate and UNRESOLVED-METHOD are for.
