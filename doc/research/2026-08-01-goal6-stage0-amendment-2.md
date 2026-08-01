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

> a failure of (c) is graded **INCONCLUSIVE, never REFUTED**, until a clear-violation
> band calibrated under a separately justified and frozen dependence family exists for
> this series. The `SE_HAC`-width discriminator is SUSPENDED: its width is not
> identified — the audited 1.224 de-bias covers only the pure-overlap MA(19) component,
> and the AR-like persistence this document itself names has **no measured upper
> bound**, so no hand-chosen widening can be called conservative `[per review]`.

(c) itself is untouched: it remains a hard SUPPORTED gate on the point comparison
`d_20d ≤ d_60d`. What is suspended is only the band that promoted a (c) failure from
INCONCLUSIVE to REFUTED.

No other constant, statistic, hypothesis, or gate changes. `SE_HAC`'s formula and
`L = 19` are untouched — the amendment corrects the BAND's width where the estimator is
consumed, not the estimator.

## Why suspension rather than the alternatives

* **A widened band (this amendment's own first draft, 1.25×)**: rejected on review —
  the 1.224 factor is exact only for pure overlap; with no upper bound on the AR-like
  component, any hand-chosen constant can still be anti-conservative on a hard outcome.
* **Recalibrate per model#162 now**: the valid path, and the suspension names it as the
  condition for reinstatement; building it is real work with its own frozen DGP
  argument, and grading (c) failures INCONCLUSIVE meanwhile loses nothing decidable.
* **Downgrade (c) entirely**: removes the hard SUPPORTED gate too — more change than
  the defect requires; the point comparison stays.

## Not claimed

That the suspension is costless — H2 loses its ability to hard-REFUTE via (c) until the
calibrated band exists; outcomes that would have been REFUTED are held at INCONCLUSIVE,
which is the refusing-to-overclaim direction and is stated as the price. That any other
SE_HAC use exists in the prereg (the frozen text says "used only for §5 H2's effect-size
veto (c)"; grep confirms). That this amendment licenses running Stage 0 — the runner
remains unbuilt and the #163 record should note this amendment as the executed decision.
