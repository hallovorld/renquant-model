#!/usr/bin/env python3
"""Inference machinery for the frozen momentum prereg: generators, bars, gates. (GOAL-7)

Implements §4 of model#164 (+ Amendment 1 context) exactly; every frozen constant is
restated in ONE dict and cross-checked by tests against the prereg's numbers. No real
data enters this module — it consumes per-date series handed to it by the runner.

The two admissible H0 generators (the FROZEN family):
  * overlap-MA(19): rolling 20-day mean of iid innovations, variance-matched to the
    target series — the dependence a 20-day label induces by construction;
  * AR(p): p <= 20 chosen by AIC on the demeaned series, innovations resampled iid
    from the fitted residuals (heavy tails survive), with an ACF adequacy envelope —
    fail -> UNRESOLVED-METHOD (no collapse; the #166-reviewed rule).

Bar: t* = max over the family of the seeded 97.5th percentile of |T| (alpha = 0.025 per
test, two decision tests), 5,000 reps, seed 20260801, n = the realized series length.
"""
from __future__ import annotations

import numpy as np

FROZEN_INFERENCE = {
    "h": 20, "L": 59, "alpha_per_test": 0.025, "quantile": 0.975,
    "reps": 5000, "seed": 20260801, "ar_p_max": 20,
    "acf_envelope_lags": 40, "acf_envelope_se_mult": 2.0,
    "gate_band": (0.0184, 0.0316),      # 0.025 ± 3·sqrt(0.025·0.975/5000)
    "mde_ceiling": 0.06,
}


# ---------------------------------------------------------------- estimator T ----
def bartlett_hac_t(v: np.ndarray, L: int) -> float:
    """The pinned SE_HAC formula (1/n autocovariances, Bartlett weights) — mirrors
    renquant_common.metrics.hac_se to the digit; the runner cross-checks the two on
    every execution and refuses on disagreement, so a drift in either is loud."""
    v = np.asarray(v, float)
    n = len(v)
    mu = v.mean()
    d = v - mu
    g0 = float(d @ d) / n
    total = g0
    for k in range(1, L + 1):
        gk = float(d[:-k] @ d[k:]) / n
        total += 2.0 * (1.0 - k / (L + 1.0)) * gk
    if total <= 0:
        return float("nan")
    return float(mu / np.sqrt(total / n))


# ---------------------------------------------------------------- generators ----
def gen_overlap_ma(rng: np.random.Generator, n: int, h: int, target_var: float) -> np.ndarray:
    e = rng.standard_normal(n + h)
    x = np.convolve(e, np.ones(h) / h, mode="valid")[:n]
    sd = x.std()
    return x * (np.sqrt(target_var) / sd) if sd > 0 else x


def fit_ar(v: np.ndarray, p_max: int) -> dict:
    """AR(p) by OLS on lags, p chosen by AIC. Returns phi, residuals, p."""
    v = np.asarray(v, float)
    x = v - v.mean()
    best = None
    for p in range(1, p_max + 1):
        if len(x) - p < 10 * p:
            break
        Y = x[p:]
        X = np.column_stack([x[p - k:len(x) - k] for k in range(1, p + 1)])
        with np.errstate(all="ignore"):
            phi, *_ = np.linalg.lstsq(X, Y, rcond=None)
            if not np.all(np.isfinite(phi)):
                continue                   # ill-conditioned lag matrix at this p
            resid = Y - X @ phi
            sse = float(resid @ resid)
        if not np.isfinite(sse):
            continue
        nn = len(Y)
        aic = nn * np.log(max(sse / nn, 1e-300)) + 2 * p
        if best is None or aic < best["aic"]:
            best = {"p": p, "phi": phi, "resid": resid, "aic": aic}
    return best


def gen_ar_resample(rng: np.random.Generator, n: int, phi: np.ndarray,
                    resid_pool: np.ndarray) -> np.ndarray:
    p = len(phi)
    burn = 300
    x = np.zeros(n + burn)
    eps = rng.choice(resid_pool, size=n + burn, replace=True)
    for t in range(p, n + burn):
        x[t] = float(phi @ x[t - p:t][::-1]) + eps[t]
    return x[burn:]


# ---------------------------------------------------------------- adequacy ----
def sample_acf(v: np.ndarray, max_lag: int) -> np.ndarray:
    v = np.asarray(v, float)
    if not np.all(np.isfinite(v)):
        return np.full(max_lag, np.nan)
    d = v - v.mean()
    g0 = float(d @ d)
    if g0 <= 0:
        return np.full(max_lag, np.nan)
    return np.array([float(d[:-k] @ d[k:]) / g0 for k in range(1, max_lag + 1)])


def ar_implied_acf(phi: np.ndarray, resid_pool: np.ndarray, max_lag: int,
                   n: int, rng: np.random.Generator, reps: int = 400) -> np.ndarray:
    """Implied ACF by simulation (exact closed forms exist only for small p)."""
    acc = np.zeros(max_lag)
    for _ in range(reps):
        acc += sample_acf(gen_ar_resample(rng, n, phi, resid_pool), max_lag)
    return acc / reps


def adequacy_check(series: np.ndarray, fit: dict, cfg: dict,
                   rng: np.random.Generator) -> dict:
    """Two envelope rules, selected by ``cfg["envelope_rule"]``:

    * ``"frozen_2se"`` — the prereg text as frozen: max |emp − implied| over K lags
      ≤ 2·(1/√n). MEASURED DEGENERATE `[本次实测 2026-08-01]`: on perfect-specification
      true-AR(1) data it REJECTS 15–19 of 20 series (n=2150 φ∈{0.6,0.9}; n=600 φ=0.5) —
      the maximum of K noisy deviations exceeds a per-lag 2·SE band almost surely, and
      1/√n additionally understates ACF variance for dependent series.
    * ``"max_test_bartlett"`` — the principled max-test: per-lag envelope
      z₁₋α/(2K) · SE_k with Bartlett's-formula SE_k = √((1 + 2Σ_{j<k} r_j²)/n), α=0.05.
      Proposed as prereg Amendment 2; not the default until that amendment merges.
    """
    lags = cfg["acf_envelope_lags"]
    emp = sample_acf(series, lags)
    imp = ar_implied_acf(fit["phi"], fit["resid"], lags, len(series), rng)
    n = len(series)
    rule = cfg.get("envelope_rule", "frozen_2se")
    dev = np.abs(emp - imp)
    if rule == "frozen_2se":
        env = np.full(lags, cfg["acf_envelope_se_mult"] / np.sqrt(n))
    elif rule == "max_test_bartlett":
        from scipy import stats as _st
        z = float(_st.norm.ppf(1 - 0.05 / (2 * lags)))
        cum = np.cumsum(np.concatenate([[0.0], emp[:-1] ** 2]))
        env = z * np.sqrt((1.0 + 2.0 * cum) / n)
    else:
        raise ValueError(f"unknown envelope_rule {rule!r}")
    exceed = dev > env
    ok = bool(not np.any(exceed & np.isfinite(dev)))
    worst = int(np.nanargmax(dev - env)) + 1 if np.any(np.isfinite(dev)) else None
    return {"ok": ok, "rule": rule, "max_abs_dev": float(np.nanmax(dev)),
            "worst_lag": worst,
            "envelope_at_worst": float(env[worst - 1]) if worst else None}


# ---------------------------------------------------------------- calibration ----
def calibrate_bar(series: np.ndarray, cfg: dict) -> dict:
    """t* = max over the frozen family; UNRESOLVED-METHOD on adequacy failure."""
    rng = np.random.default_rng(cfg["seed"])
    n = len(series)
    var = float(np.asarray(series, float).var())
    out: dict = {"n": n, "bars": {}}

    def bar_under(gen) -> float:
        ts = np.empty(cfg["reps"])
        for i in range(cfg["reps"]):
            ts[i] = bartlett_hac_t(gen(rng), cfg["L"])
        return float(np.quantile(np.abs(ts[np.isfinite(ts)]), cfg["quantile"]))

    out["bars"]["overlap_ma"] = bar_under(
        lambda r: gen_overlap_ma(r, n, cfg["h"], var))

    fit = fit_ar(series, cfg["ar_p_max"])
    if fit is None:
        return {**out, "status": "UNRESOLVED-METHOD",
                "why": "AR fit impossible on this length"}
    adq = adequacy_check(series, fit, cfg, rng)
    out["ar_fit"] = {"p": fit["p"], "adequacy": adq}
    if not adq["ok"]:
        return {**out, "status": "UNRESOLVED-METHOD",
                "why": f"AR adequacy failed: max dev {adq['max_abs_dev']:.4f} > "
                       f"envelope {adq['envelope']:.4f} — per the reviewed rule there "
                       f"is NO collapse to the MA member"}
    out["bars"]["ar_resample"] = bar_under(
        lambda r: gen_ar_resample(r, n, fit["phi"], fit["resid"]))
    out["t_star"] = max(out["bars"].values())
    out["status"] = "calibrated"
    return out


# ---------------------------------------------------------------- gates ----
def machinery_self_check(series: np.ndarray, t_star: float, cfg: dict,
                         reps: int | None = None) -> dict:
    """Series simulated from the MA member, pushed through T, must reject at ~alpha."""
    rng = np.random.default_rng(cfg["seed"] + 1)
    n = len(series)
    var = float(np.asarray(series, float).var())
    reps = reps or cfg["reps"]
    hits = 0
    for _ in range(reps):
        t = bartlett_hac_t(gen_overlap_ma(rng, n, cfg["h"], var), cfg["L"])
        if np.isfinite(t) and abs(t) >= t_star:
            hits += 1
    rate = hits / reps
    lo, hi = cfg["gate_band"]
    return {"rate": rate, "ok": bool(lo <= rate <= hi), "band": [lo, hi]}
