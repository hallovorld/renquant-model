"""The residual-momentum feature family: mechanisms as pure functions. (GOAL-7)

Library only. EVERY constant is a parameter: the frozen values (252/21/200, ≥3-of-5, …)
live in the preregistration (model#164) and are passed in by the runner, so this module
can be reviewed as mechanism and the prereg as policy — and so no constant can hide here
outside the freeze.

Inputs are aligned numpy arrays for ONE name's formation window (daily total returns,
market total returns, volumes). Each function returns ``nan`` when its own input floor
is unmet — never a silently-degraded number. Cross-sectional assembly (per-date z,
≥k-of-5) is `composite_scores`.

References: Blitz–Huij–Martens 2011 (F1); Da–Gurun–Warachka 2014 (F2);
Moskowitz–Grinblatt 1999 (F3); Lee–Swaminathan 2000 lineage (F4);
Ang–Chen–Xing 2006 / Daniel–Moskowitz 2016 (F5).
"""
from __future__ import annotations

import numpy as np

__all__ = ["f1_residual_momentum", "f2_information_discreteness",
           "f3_industry_momentum", "f4_signed_volume_agreement",
           "f5_downside_beta_penalty", "composite_scores"]

_EPS = 1e-12


def _valid_pair(r_i: np.ndarray, r_m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    m = np.isfinite(r_i) & np.isfinite(r_m)
    return r_i[m], r_m[m]


def f1_residual_momentum(r_i: np.ndarray, r_m: np.ndarray, *, min_obs: int) -> float:
    """EXACT intercept-OLS market-model alpha t-statistic.

    `y = α + β·x + ε` fit by OLS; returns `t = α̂ / SE(α̂)` with
    `SE(α̂) = s·√(1/n + x̄²/Sxx)`, `s² = SSE/(n−2)` — the full alpha standard error
    including the nonzero-market-mean term and residual degrees of freedom
    `[codex on model#167: mean(ε)/sd(ε)·√N omitted both and was not the stated
    statistic]`. A same-window Σε with an intercept is identically zero (the degeneracy
    the first version caught); the alpha t is the non-degenerate estimand of the
    underreaction mechanism: standardized idiosyncratic drift."""
    x, y = _valid_pair(np.asarray(r_m, float), np.asarray(r_i, float))
    # (x = market, y = name; _valid_pair mirrors its args)
    n = len(x)
    if n < min_obs or n < 3:
        return float("nan")
    xbar, ybar = float(x.mean()), float(y.mean())
    vx = x - xbar
    sxx = float(vx @ vx)
    if sxx < _EPS:
        return float("nan")
    beta = float(vx @ (y - ybar)) / sxx
    alpha = ybar - beta * xbar
    resid = y - alpha - beta * x
    sse = float(resid @ resid)
    s2 = sse / (n - 2)
    if s2 < _EPS:
        return float("nan")
    se_alpha = float(np.sqrt(s2 * (1.0 / n + xbar * xbar / sxx)))
    if se_alpha < _EPS:
        return float("nan")
    return float(alpha / se_alpha)

def f2_information_discreteness(r_i: np.ndarray, *, min_obs: int) -> float:
    """sign(cumulative return) · (frac_pos_days − frac_neg_days): smooth trends score
    high in their own direction, jumpy ones near zero or negative."""
    r = np.asarray(r_i, float)
    r = r[np.isfinite(r)]
    if len(r) < min_obs:
        return float("nan")
    cum = float(np.prod(1.0 + r) - 1.0)
    if abs(cum) < _EPS:
        return 0.0
    frac_pos = float(np.mean(r > 0))
    frac_neg = float(np.mean(r < 0))
    return float(np.sign(cum) * (frac_pos - frac_neg))


def f3_industry_momentum(formation_returns: dict[str, float],
                         sector_of: dict[str, str]) -> dict[str, float]:
    """Equal-weight sector formation return assigned to each member.

    Names without a sector (ETFs) or whose formation return is nan get nan — counted
    by the caller, never silently dropped into a sector mean."""
    by_sector: dict[str, list[float]] = {}
    for t, r in formation_returns.items():
        s = sector_of.get(t)
        if s is not None and np.isfinite(r):
            by_sector.setdefault(s, []).append(float(r))
    means = {s: float(np.mean(v)) for s, v in by_sector.items()}
    return {t: (means[sector_of[t]]
                if sector_of.get(t) in means and np.isfinite(formation_returns[t])
                else float("nan"))
            for t in formation_returns}


def f4_signed_volume_agreement(r_i: np.ndarray, vol: np.ndarray, *, min_obs: int) -> float:
    """(Σ vol·1[r>0] − Σ vol·1[r<0]) / Σ vol — direction-confirming volume share."""
    r = np.asarray(r_i, float); v = np.asarray(vol, float)
    m = np.isfinite(r) & np.isfinite(v) & (v >= 0)
    r, v = r[m], v[m]
    if len(r) < min_obs:
        return float("nan")
    tot = float(v.sum())
    if tot < _EPS:
        return float("nan")
    return float((v[r > 0].sum() - v[r < 0].sum()) / tot)


def f5_downside_beta_penalty(r_i: np.ndarray, r_m: np.ndarray, *, min_obs: int,
                             min_side_obs: int) -> float:
    """−(β⁻ − β⁺): betas conditional on market down/up days. `min_side_obs` is the
    per-side floor the RUNNER must declare and justify — this library refuses to pick
    one (a hidden constant here would sit outside the freeze)."""
    y, x = _valid_pair(np.asarray(r_i, float), np.asarray(r_m, float))
    if len(x) < min_obs:
        return float("nan")

    def _beta(mask: np.ndarray) -> float:
        xs, ys = x[mask], y[mask]
        if len(xs) < min_side_obs:
            return float("nan")
        vx = xs - xs.mean()
        d = float(vx @ vx)
        if d < _EPS:
            return float("nan")
        return float(vx @ (ys - ys.mean())) / d

    b_down, b_up = _beta(x < 0), _beta(x > 0)
    if not (np.isfinite(b_down) and np.isfinite(b_up)):
        return float("nan")
    return float(-(b_down - b_up))


def composite_scores(features: dict[str, dict[str, float]], *, min_features: int
                     ) -> tuple[dict[str, float], dict[str, int]]:
    """Per-date equal-weight mean of per-feature cross-sectional z-scores.

    `features` maps feature name -> {ticker -> value}. Returns (scores, n_used) where
    `n_used[t]` counts the features that contributed; names below `min_features` get
    nan AND stay in the output so the caller counts them."""
    tickers = sorted({t for col in features.values() for t in col})
    zcols: dict[str, dict[str, float]] = {}
    for fname, col in features.items():
        vals = np.array([col.get(t, float("nan")) for t in tickers], float)
        finite = np.isfinite(vals)
        if finite.sum() < 2:
            continue
        mu = float(vals[finite].mean())
        sd = float(vals[finite].std(ddof=0))
        if sd < _EPS:
            continue
        zcols[fname] = {t: (float((v - mu) / sd) if np.isfinite(v) else float("nan"))
                        for t, v in zip(tickers, vals)}
    scores: dict[str, float] = {}
    n_used: dict[str, int] = {}
    for t in tickers:
        zs = [z[t] for z in zcols.values() if np.isfinite(z[t])]
        n_used[t] = len(zs)
        scores[t] = float(np.mean(zs)) if len(zs) >= min_features else float("nan")
    return scores, n_used
