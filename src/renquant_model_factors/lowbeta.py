"""lowbeta — betting-against-beta (Frazzini–Pedersen), simple-sort emitter.

Artifact kind ``factor_lowbeta_v0``. Formula and freeze rationale live in
``_frozen_params_lowbeta_v0``; this module contributes only the params
block, its v0 domain validator, and the per-ticker score function.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from typing import Any, Mapping

from . import _frozen_params_lowbeta_v0 as _F
from .machine import (FactorDef, FactorReaders, TickerScore,
                      build_factor_artifact, validate_factor_params)

__all__ = ["FACTOR", "build_lowbeta_artifact", "params_v0", "score_lowbeta"]

#: The params keys the score function requires (beyond params_version).
_REQUIRED_INT_KEYS = ("beta_window", "min_obs", "names_per_date_floor")

#: Degenerate-regressor floor on Σ(x-x̄)² — mirrors the momentum features'
#: _EPS guard (underscore-private there, so re-stated, not imported): a
#: flat market window cannot identify a slope, so the score fails closed.
_SSX_EPS = 1e-12


def params_v0() -> dict:
    """The v0 params block, from the frozen module (prereg content)."""
    return {
        "params_version": "v0",
        "beta_window": int(_F.BETA_WINDOW),
        "min_obs": int(_F.MIN_OBS),
        "names_per_date_floor": int(_F.NAMES_PER_DATE_FLOOR),
        "params_source": _F.PARAMS_SOURCE,
    }


def _validate_v0_domains(p: dict) -> None:
    """Domain checks for params_version 'v0' — no silent inheritance by
    future versions (each new version must declare its own validator)."""
    if p["beta_window"] <= 0:
        raise ValueError(
            f"params['beta_window'] must be > 0, got {p['beta_window']}")
    if p["min_obs"] <= 1:
        raise ValueError(
            f"params['min_obs'] must be > 1 (a slope needs at least two "
            f"pairs), got {p['min_obs']}")
    if p["min_obs"] > p["beta_window"]:
        raise ValueError(
            f"params['min_obs']={p['min_obs']} must be <= "
            f"params['beta_window']={p['beta_window']} — a minimum pair "
            "count larger than the window can never be satisfied")
    if p["names_per_date_floor"] <= 0:
        raise ValueError(
            f"params['names_per_date_floor']={p['names_per_date_floor']} "
            "must be > 0")


def _validate_params(params: Mapping[str, Any]) -> dict:
    return validate_factor_params(
        params, int_keys=_REQUIRED_INT_KEYS,
        domain_validators={"v0": _validate_v0_domains})


def score_lowbeta(readers: FactorReaders, ticker: str, ts: pd.Timestamp,
                  p: Mapping[str, Any]) -> TickerScore | None:
    """score = -beta_hat, OLS slope of ticker daily returns on SPY's.

    The two close series are inner-joined by date FIRST, simple
    close-to-close returns are computed on the aligned price frame, and a
    pair is kept only when its two dates are ADJACENT in the market
    calendar (the market series' index) — so an interior gap on either
    leg (missing row or NaN) DROPS the pairs touching it, never
    forward-fills, and can never pair a multi-session ticker return with
    a one-session market return. Non-finite pairs removed, then the
    trailing ``beta_window`` pairs at/before the cutoff. Fewer than
    ``min_obs`` pairs, or a degenerate market window (Σ(x-x̄)² ≈ 0),
    -> NaN (fail-closed). The newest paired date is MEASURED into
    last_read.
    """
    c = readers.close(ticker)
    if c is None:
        return None
    m = readers.market_close()
    mm = m.loc[m.index <= ts]
    px = pd.concat([c.loc[c.index <= ts], mm], axis=1, join="inner").dropna()
    r = px.pct_change(fill_method=None)
    # Paired-DAILY contract: consecutive aligned rows must be adjacent in
    # the market calendar, else the return spans multiple sessions.
    daily = np.diff(mm.index.get_indexer(px.index)) == 1
    pair = r.iloc[1:][daily]
    pair = pair[np.isfinite(pair).all(axis=1)]
    pair = pair.tail(int(p["beta_window"]))
    n = int(len(pair))
    if n == 0:
        return TickerScore(float("nan"), 0, None)
    last_read = pair.index.max()
    if n < p["min_obs"]:
        return TickerScore(float("nan"), n, last_read)
    y = pair.iloc[:, 0].to_numpy(dtype=float)  # ticker returns
    x = pair.iloc[:, 1].to_numpy(dtype=float)  # SPY returns
    xc = x - x.mean()
    ssx = float(xc @ xc)
    if ssx <= _SSX_EPS:
        return TickerScore(float("nan"), n, last_read)
    beta = float(xc @ (y - y.mean()) / ssx)
    return TickerScore(-beta, n, last_read)


FACTOR = FactorDef(name="lowbeta", validate_params=_validate_params,
                   score_fn=score_lowbeta)


def build_lowbeta_artifact(asof: Any, universe: list[str],
                           params: Mapping[str, Any], *,
                           readers: FactorReaders) -> dict:
    """One scoring run = one ``factor_lowbeta_v0`` artifact for ``asof``."""
    return build_factor_artifact(asof, universe, params, factor=FACTOR,
                                 readers=readers)
