# GOAL-7 residual momentum v1 — the single execution's verdict: UNRESOLVED-METHOD

**The one licensed §7 invocation ran 2026-08-02 (claim 11:19Z, sealed result
sha256 `46118a12…`) and terminated at the CALIBRATION gate with
`UNRESOLVED-METHOD`. No H1/H2 statistic was ever compared to a bar; nothing is
licensed and nothing is killed. The shot is consumed: claim and result are
sealed read-only, and the runner refuses any re-invocation (exit 4).**

Committed verbatim in `doc/research/data/2026-08-02-goal7-momentum-v1-result/`
(top-level `data/` is gitignored — the umbrella's production data symlink —
so these are nested under `doc/research/` and force-added past the ignore rule):
`result.json` (byte-identical to the sealed store copy) + `EXECUTION_CLAIM.json`.

## What the machinery refused, exactly `[VERIFIED — result.json]`

- Series: 2,378 per-date cross-sectional Spearman ICs of the composite S vs
  `fwd_20d_excess` (221 thin dates skipped, 0 infeasible).
- Realized ACF: **ρ₁ = 0.9269**, decaying to ~0 around lag 15 and OVERSHOOTING
  to ρ ≈ −0.20 by lags 17–20 before a slow rise — the published 40-lag vector
  is in the result.
- The frozen calibration family fit AR(1) (p=1); the Amendment-2 adequacy rule
  (`bootstrap_max`, B=500, α=0.05) measured **max ACF deviation 0.4047 against
  a bootstrap threshold 0.1645** → ADEQUACY FAILED, and the reviewed rule says
  plainly: no collapse to the MA member. The only calibrated bar it could
  publish (overlap-MA 2.463) is published as required, unused.

## Reading it honestly

1. **This is the designed outcome for exactly this situation, not a crash.**
   The h=20 overlapping-label structure plus real score persistence produce an
   IC series whose dependence an AR(1) null cannot honestly represent; the
   prereg (post-A2/A4) requires the machine to refuse rather than fabricate a
   t\* from an inadequate null. The two negative-control validations in the A4
   bundle showed this refusal machinery has teeth; tonight it used them on us.
2. **Momentum is neither retained nor killed by this.** UNRESOLVED-METHOD is a
   statement about the CALIBRATION FAMILY, not about the candidate: no effect
   estimate was bar-tested. The prereg's single-shot rule consumes the run
   regardless (rerunning after seeing the refusal would be method-shopping).
3. **The ACF vector is the deliverable.** Publishing bars + realized ACF
   regardless of outcome was frozen into §4.4 precisely so a v2 could be
   designed against MEASURED dependence instead of assumed dependence.

## What a v2 must do differently (direction, NOT a prereg)

- A null adequate for ρ₁≈0.93 with oscillatory decay: the candidates already
  proven elsewhere in this program are (a) gap-block resampling with gap ≥ h
  (the Stage-0 geometry — n_eff ≈ floor((T−h)/2h)+1 ≈ 58 at T=2378, h=20),
  or (b) a bootstrap null on the REAL series (the block-length ledger rule:
  where the real series exists, bootstrap it; never L=h).
- Any v2 is a NEW preregistration through the same freeze-then-run door, with
  its own single shot. The v1 chain's inputs (durable store, manifest) are
  reusable by digest; the v1 result stands as published evidence.

## Chain provenance

Prereg #164 + Amendments 1–4 (all merged) · runner #177 + import fix #188 ·
manifest base-data#60 · durable store 294/294 · Grant A executed 2026-08-02
(sibling → f851406). First --execute attempt crashed pre-inference at import
(zero estimand; fix #188, claim removal recorded there); this second and FINAL
invocation ran to the calibration gate and sealed.
