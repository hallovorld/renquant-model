# Momentum prereg — Amendment 1 (visible, PRE-RUN): the F1 formula is degenerate as frozen

**Amends `doc/research/2026-08-01-goal7-residual-momentum-prereg.md` §1's F1 formula
only. Filed BEFORE any execution — no runner exists, nothing has been computed under the
frozen document — per the visible-amendment precedent (Stage-0 Amendments 1–2;
long-term-agreements entry 10: corrections are visible, never silent).**

## The defect `[本次实测 2026-08-01, model#167]`

§1 froze F1 as *"rolling OLS … score = `Σε/(σ_ε·√N)`"*. Implemented exactly as written,
that statistic is **identically zero**: a same-window regression with an intercept —
explicit, or implicit via demeaning — absorbs the residual mean by construction, so
`Σε ≡ 0` for every name on every date. The feature engine's analytic fixtures (model#167)
returned 0/nan on inputs where the underreaction mechanism demands signal; a beta-only
series and a strong-idiosyncratic-drift series were indistinguishable.

Frozen as written, the study would have executed with an all-zero F1 arm: the composite
would silently become a 4-feature model, and H2's parsimony contrast would compare `S`
against an arm of pure noise-free zeros — a meaningless comparison produced without any
error message.

## The amendment (formula made precise; nothing else moves)

F1 is the **EXACT intercept-OLS market-model alpha t-statistic** over the formation
window (`t−273…t−21`; window 252, skip 21, min obs 200 — unchanged):

* fit `r_i,t = α + β·r_m,t + ε_t` by OLS;
* `s² = SSE/(n−2)`; `SE(α̂) = s·√(1/n + x̄²/Sxx)` where `x̄` is the market-return mean
  and `Sxx = Σ(r_m,t − x̄)²`;
* `F1 = α̂ / SE(α̂)`.

Per the review of this amendment's first draft: `mean(ε)/sd(ε)·√N` omitted the
`x̄²/Sxx` term and the `n−2` degrees of freedom and therefore was NOT the stated
t-statistic for nonzero-mean market returns. The engine (model#167) implements the exact
form above and carries the demanded hand-derived nonzero-`x̄` control (β = 2.3,
α = −0.5, SSE = 0.30, t = −0.5/√0.225, asserted to 1e-12) plus a seeded
nonzero-market-mean cross-check against an independent implementation to 1e-9 — the
amendment and the engine freeze IDENTICAL mathematics.

This is the standardized idiosyncratic drift — the quantity the mechanism (underreaction
to firm-specific news) is about, and the engine's fixtures confirm it separates the
beta-only case (|t| < 3, seeded) from the idio-drift case (t > 5) `[本次实测, model#167]`.

## Why this is amendable at all

The freeze's purpose is to prevent outcome-driven changes. No outcome exists: no runner,
no scores, no IC, no label statistic has been computed under the frozen document (its own
§7 execution gate is unsatisfied). A formula that is identically zero cannot be
"tuned toward" any result by being made non-degenerate; the amendment direction is from
undefined to defined, not from one answer to another.

## Process disclosure, on the record

The first attempt at this correction was pushed to the merged PR's auto-deleted branch
(recreating it) and the merged PR's body was edited — both wrong; a merged prereg's
review record must not move. The body was restored to the merged content, the recreated
branch deleted, and this amendment PR is the legitimate path. The mistake and its
reversal are disclosed in model#164's comments.

## Not claimed

That any other frozen constant changes — window, skip, min-obs, the family, the bar
machinery, the population, and every digest are untouched. That the alpha-t form is the
uniquely correct residual momentum; it is the minimal non-degenerate reading of the
frozen intent, and BHM's split-window variant remains a possible future design, not this
study.
