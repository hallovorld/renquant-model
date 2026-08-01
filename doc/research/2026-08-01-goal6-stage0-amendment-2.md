# GOAL-6 Stage 0 — Amendment 2 (visible, pre-run): the H2(c) clear-violation band

**Amends `doc/research/2026-07-28-goal6-stage0-prereg.md` §5 H2(c) only. Filed BEFORE
any Stage-0 run (the prereg's own progress doc records "no run yet"), per the visible-
correction precedent this prereg already carries (Amendment 1; long-term-agreements
entry 10 — no silent overwrites).**

## What §5 H2(c) actually uses SE_HAC for — narrower than model#163 framed it

`SE_HAC` (NW/Bartlett, `L = h_min − 1 = 19`) appears in the decision path exactly once:
H2 is **REFUTED** when the effect-size condition (c) *"fails by more than one `SE_HAC`
of the smaller sample (a clear violation, not a rounding tie)"*; anything nearer is
**INCONCLUSIVE**. It is a tie-discriminator band, **not** a rejection test at a normal
quantile — so the size-probe finding does not invalidate a test here; it mis-widths a
boundary. model#163's "amend / caveat / downgrade the veto" framing overstated the
exposure; this amendment corrects the record and the band together.

## The measured defect `[早前实测 + 独立审计 UPHELD]`

For the overlap dependence a 20-day label induces by construction, the Bartlett
estimator at L=19 captures **66.75%** of the true long-run variance (closed form;
audit's Route B), so `SE_HAC` **understates** the honest SE by a factor of
√0.6675 ≈ **0.817**. The (c) band is therefore ~**18% too narrow**: outcomes that are
honestly near-ties get classified as "clear violations" → REFUTED instead of
INCONCLUSIVE. Direction: biased toward REFUTED (against H2 support) — safe for
promotion, wrong for the record.

## The amendment (one sentence changes)

§5 H2 REFUTED clause, replace:

> (c) fails by more than one `SE_HAC` of the smaller sample

with:

> (c) fails by more than **1.25 × `SE_HAC`** of the smaller sample — the widening
> factor is frozen at 1.25 ≥ 1.224 = √(1/0.6675), the audited analytic de-bias for the
> pure-overlap dependence the label construction guarantees `[analytic, audit UPHELD]`,
> rounded UP so residual under-coverage (estimation noise; any AR-like persistence
> beyond pure overlap, which only widens the honest band further) errs toward
> INCONCLUSIVE — the refusing-to-overclaim direction for a boundary whose exact width
> is not identified.

No other constant, statistic, hypothesis, or gate changes. `SE_HAC`'s formula and
`L = 19` are untouched — the amendment corrects the BAND's width where the estimator is
consumed, not the estimator.

## Why not the other #163 options

* **Recalibrate per model#162**: correct in principle, but (c) is not a test — building
  a seeded generator calibration for a tie-discriminator imports machinery the decision
  does not need, and #162's own review bars it from authorizing verdicts without a
  frozen DGP argument. Disproportionate here.
* **Downgrade (c) to descriptive**: removes a frozen hard gate entirely — a larger
  change to the preregistration's substance than correcting a band width with an
  audited constant, and it would delete the protection (c) exists to give.

## Not claimed

That 1.25 is exact for the realized series — it is a lower-bounded conservative widening
whose stated failure mode is extra INCONCLUSIVEs, never extra REFUTEDs. That any other
SE_HAC use exists in the prereg (the frozen text says "used only for §5 H2's effect-size
veto (c)"; grep confirms). That this amendment licenses running Stage 0 — the runner
remains unbuilt and the #163 record should note this amendment as the executed decision.
