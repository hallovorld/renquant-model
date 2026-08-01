# Progress: the momentum feature engine — and the degeneracy it caught pre-freeze (GOAL-7)

WHAT: `src/renquant_model_common/momentum_features.py` — F1–F5 and the composite as pure
functions, every constant a parameter (frozen values live in the prereg and are passed by
the runner; a constant hiding here would sit outside the freeze). Nine analytic tests, no
market data anywhere.

THE CATCH: implementing F1 exactly as the freeze candidate wrote it — same-window OLS,
score = Σε/(σ_ε·√N) — is **identically zero**: with an intercept (explicit or via
demeaning), the residual mean is absorbed by construction. The analytic fixtures returned
0/nan where the mechanism demands signal. Resolution implemented and documented in the
module: β̂ by demeaned OLS, then ε_t = r_i,t − β̂·r_m,t with the intercept deliberately
NOT removed — F1 is the market-model **alpha t-statistic** over the formation window, the
standardized idiosyncratic drift the underreaction mechanism is about. The freeze
candidate (model#164, still under review) is being corrected to this precise form in the
same push; a degenerate formula frozen would have produced an all-zero F1 arm and a
silently meaningless H2.

ALSO: `min_side_obs` for F5 is a required parameter this library refuses to default —
the runner must declare and justify it under review, so no constant escapes the freeze.

Tests: 9 analytic (beta-only ≈ 0 alpha-t; idio drift > 5; smooth-vs-jump discreteness;
sector means with ETF nan; volume agreement = 1 on constructed flow; exact −1.5 downside
penalty on per-side-linear fixtures; ≥k-of-5 with names kept visible; zero-variance
feature dropped, not divided by). Suite: full run below.
