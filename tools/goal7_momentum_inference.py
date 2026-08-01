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
    # The committed §4.4 positive-control fixture: iid N(0,1), n=756, generated once
    # with np.random.default_rng(20260801 + 7), written with Python-float repr and read
    # back with float_precision="round_trip" (pandas' default C parser is LOSSY — 230 of
    # 756 values differed in the last bits without it). Pinned by content.
    "positive_control_sha256":
        "ff859a68dd7f0bd73c428458575def9839d5670a860aa5ac323942107e48f8c5",
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
    cfg = dict(cfg); cfg["_fit"] = fit
    dev = np.abs(emp - imp)
    if rule == "frozen_2se":
        env = np.full(lags, cfg["acf_envelope_se_mult"] / np.sqrt(n))
    elif rule == "bootstrap_max":
        # [codex on model#170] Calibrate the max-deviation statistic's threshold by a
        # precommitted parametric bootstrap UNDER THE FITTED NULL: simulate B series
        # from the fit, compute each one's own D_b = max_k |acf_b − implied| against
        # the SAME implied curve, take the (1−α) quantile as the gate threshold. This
        # assesses the GATE's threshold, not whether AR is the right real-series null —
        # the separate UNRESOLVED-METHOD safeguard is untouched.
        B = int(cfg.get("adequacy_boot_reps", 500))
        alpha = float(cfg.get("adequacy_alpha", 0.05))
        fit = cfg["_fit"]                       # injected by adequacy_check wrapper
        d_boot = np.empty(B)
        for b in range(B):
            sim = gen_ar_resample(rng, n, fit["phi"], fit["resid"])
            d_boot[b] = float(np.nanmax(np.abs(sample_acf(sim, lags) - imp)))
        thresh = float(np.quantile(d_boot, 1.0 - alpha))
        d_real = float(np.nanmax(dev))
        return {"ok": bool(d_real <= thresh), "rule": rule,
                "max_abs_dev": d_real, "bootstrap_threshold": thresh,
                "boot_reps": B, "alpha": alpha}
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
        # Rule-aware serialization: the bootstrap_max rule reports a scalar threshold,
        # not a per-lag envelope, so it has no worst_lag/envelope_at_worst — the earlier
        # unconditional interpolation CRASHED on the very path it had to report.
        if adq["rule"] == "bootstrap_max":
            detail = (f"max dev {adq['max_abs_dev']:.4f} > bootstrap threshold "
                      f"{adq['bootstrap_threshold']:.4f} "
                      f"(B={adq['boot_reps']}, alpha={adq['alpha']})")
        else:
            detail = (f"max dev {adq['max_abs_dev']:.4f}, worst lag {adq['worst_lag']} "
                      f"(envelope there {adq['envelope_at_worst']:.4f})")
        return {**out, "status": "UNRESOLVED-METHOD",
                "why": f"AR adequacy failed under rule {adq['rule']!r}: {detail} — per "
                       f"the reviewed rule there is NO collapse to the MA member"}
    out["bars"]["ar_resample"] = bar_under(
        lambda r: gen_ar_resample(r, n, fit["phi"], fit["resid"]))
    out["t_star"] = max(out["bars"].values())
    out["status"] = "calibrated"
    return out


# ---------------------------------------------------------------- gates ----
def _rejection_rate(gen, bar: float, L: int, rng: np.random.Generator,
                    reps: int, band) -> dict:
    """Fraction of fresh draws from ``gen`` with |T_HAC| >= ``bar``, vs the band."""
    hits = 0
    for _ in range(reps):
        t = bartlett_hac_t(gen(rng), L)
        if np.isfinite(t) and abs(t) >= bar:
            hits += 1
    rate = hits / reps
    lo, hi = band
    return {"rate": rate, "hits": hits, "reps": reps, "bar": float(bar),
            "ok": bool(lo <= rate <= hi)}


def machinery_self_check(series: np.ndarray, cal: dict, cfg: dict,
                         reps: int | None = None) -> dict:
    """§4.4 gate 2: series simulated from EACH admissible generator, pushed through the
    identical pipeline, must reject within the frozen band — both members, not just MA.

    Each generator is tested against ITS OWN calibrated bar (``cal["bars"][g]``) on
    FRESH seeded draws (deterministic sub-streams seed+1 / seed+2, disjoint from the
    calibration stream at seed): a correct calibration puts each rate at ~alpha.
    Testing the non-binding member against the max bar is conservative by construction
    and would fail a two-sided band spuriously; the max enters only the decision test.
    The AR fit is recomputed here — ``fit_ar`` is deterministic, so this is the same
    member calibration used.
    """
    n = len(series)
    var = float(np.asarray(series, float).var())
    reps = reps or cfg["reps"]
    band = cfg["gate_band"]
    out: dict = {"band": list(band)}
    out["overlap_ma"] = _rejection_rate(
        lambda r: gen_overlap_ma(r, n, cfg["h"], var), cal["bars"]["overlap_ma"],
        cfg["L"], np.random.default_rng(cfg["seed"] + 1), reps, band)
    fit = fit_ar(np.asarray(series, float), cfg["ar_p_max"])
    out["ar_resample"] = _rejection_rate(
        lambda r: gen_ar_resample(r, n, fit["phi"], fit["resid"]),
        cal["bars"]["ar_resample"],
        cfg["L"], np.random.default_rng(cfg["seed"] + 2), reps, band)
    out["ok"] = bool(out["overlap_ma"]["ok"] and out["ar_resample"]["ok"])
    return out


def positive_control(noise: np.ndarray, cfg: dict, reps: int | None = None) -> dict:
    """§4.4 gate 1: the committed pure-noise series' rejection rate under the FULL
    protocol must lie within the frozen band.

    The control takes the candidate's seat once: the frozen family is fitted to it and
    its bar calibrated exactly as for real data, adequacy rule included. The rate is
    then measured per family member — fresh seeded draws from each member fitted to the
    control, against that member's own bar (sub-streams seed+1/+2 via the self-check) —
    and the gate requires BOTH in-band. The headline ``rate`` is the binding (max-bar)
    member's, i.e. the protocol's realized size at its own decision bar.

    NOT the implementation: testing iid draws against the worst-case ``t_star``. That
    reading is DEGENERATE — measured 0.0150 at probe scale (2026-08-01, n=756,
    reps=1200), below the 0.0184 floor mechanically, because the overlap-MA member's
    bar is inflated by the by-construction dependence the iid control does not have.
    A two-sided size band is only
    satisfiable against a matched null; the iid-vs-t_star rate is still PUBLISHED below
    as ``iid_vs_t_star`` (a one-sided conservatism diagnostic, no alpha budget).
    """
    noise = np.asarray(noise, float)
    reps = reps or cfg["reps"]
    band = cfg["gate_band"]
    cal = calibrate_bar(noise, cfg)
    if cal.get("status") != "calibrated":
        return {"ok": False, "band": list(band), "calibration": cal,
                "why": f"control bar not calibrated: {cal.get('why', cal['status'])}"}
    mach = machinery_self_check(noise, cal, cfg, reps=reps)
    binding = max(cal["bars"], key=cal["bars"].get)
    n = len(noise)
    iid = _rejection_rate(lambda r: r.standard_normal(n), cal["t_star"], cfg["L"],
                          np.random.default_rng(cfg["seed"] + 3), reps, band)
    return {"ok": mach["ok"], "band": list(band), "binding_member": binding,
            "rate": mach[binding]["rate"], "per_member": mach,
            "t_star_control": cal["t_star"], "calibration": cal,
            "iid_vs_t_star": {**iid, "note": "diagnostic only, no alpha budget"}}
