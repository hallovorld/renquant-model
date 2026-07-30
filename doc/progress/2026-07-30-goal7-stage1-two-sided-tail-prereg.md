# GOAL-7 Stage 1 — the payoff is two-sided, so a ranker is the wrong object   (PR pending)

STATUS:    planned  (frozen registration; NO run has been executed)
WHAT:      Registers one question for GOAL-7: does `|z(mom_12_1_tr)|` — a two-sided
           transform with no free parameters — clear a finite-sample bar on a
           once-used date holdout, AFTER being orthogonalised to volatility?
WHY/DIR:   GOAL-7 is a standalone momentum model for shadow, at most ten factors, and
           the operator specified it must consider momentum AND mean reversion.
           model#110 measured why that is right and why a ranker is wrong: the decile
           profile of forward excess return against 12−1 momentum is U-SHAPED
           (d0 +0.135, middle −0.03…−0.09, d9 +0.375), rank correlation with decile
           only +0.27, full-cross-section IC t = +0.589 ≈ 0. Both extremes pay and the
           middle does not, so a linear ranker cancels the two ends against each other.
EVIDENCE:  n/a — this PR makes NO model or data claim. Every number is tagged as prior
           work with a reference; nothing was measured for it.
NEXT:      Split by date with a 60-trading-day embargo, run the §6 self-checks, then
           the screen. Verdict withheld pending adversarial review.

## The one clause that decides whether the result will mean anything

§4, and it is registered as a **kill condition rather than a caveat**: `|z|` of momentum
is large exactly where the cross-section is dispersed, and this programme has already
been burned by that. The prod XGB's traded estimand (+0.2534 SD) was reproduced by a
single sort on STD20 (+0.2836) and collapsed to −0.0554 when orthogonalised to STD60
`[VERIFIED — prior work, memory panel-signal-identity-capacity]`. So if the residual
after orthogonalising `u` to `|z(STD60)|` fails the bar, the verdict is
**VOLATILITY-TILT** and the hypothesis is not supported no matter what the raw arm says.
That is the outcome I expect to have to report if the raw arm looks good.

## The HARKing problem, stated rather than managed away

The U-shape was found post hoc, in a study whose own verdict was UNRESOLVED. §2 fixes
the transform, estimand, estimator and critical value before either partition is
touched, splits by date with an embargo, and uses the holdout once. But the U-shape was
observed on the full sample, so a holdout carved from it is **not independent of the
observation that motivated the design**. §2 records that, and §7 limits a pass to
SCREEN-INTERESTING accordingly. Independent confirmation would need dates outside this
corpus and this stage does not claim it.

## Why the primary statistic is the tail and not IC

The tail statistic has led IC on **4 of 4** independent subjects on this programme and
cleared no preregistered bar on any of them `[VERIFIED — prior work, memory
panel-signal-identity-capacity]`, and on identical data whole-cross-section IC read
`t = 1.15` against a top-10 spread of `t = 2.92`. Every house gate adjudicates on the
lower-powered statistic. Using the tail here is the registered choice, not a
convenience — and it is the same statistic the motivating study used as its primary.

## What a pass does and does not buy

TWO-SIDED-SUPPORTED licenses **writing** the Stage-2 design for a ≤10-factor standalone
scorer for SHADOW. It does not authorise building it, no config/artifact/state/launchd
change, no capital. The ten-factor budget is deliberately NOT spent here: Stage 1 tests
one transform precisely so the budget is not committed before the formulation is known
to have anything — the cheap-screen-before-cathedral rule.

## Live-surface impact

None. Two documents. No run has been executed.
