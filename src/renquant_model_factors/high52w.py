"""high52w — 52-week-high proximity (George–Hwang), simple-sort emitter.

Artifact kind ``factor_high52w_v0``. Formula and freeze rationale live in
``_frozen_params_high52w_v0``; this module contributes only the params
block, its v0 domain validator (its OWN, per the no-silent-inheritance
rule), and the per-ticker score function the shared machine drives.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from typing import Any, Mapping

from . import _frozen_params_high52w_v0 as _F
from .machine import (FactorDef, FactorReaders, TickerScore,
                      build_factor_artifact, validate_factor_params)

__all__ = ["FACTOR", "build_high52w_artifact", "params_v0", "score_high52w"]

#: The params keys the score function requires (beyond params_version).
_REQUIRED_INT_KEYS = ("window", "min_obs", "names_per_date_floor")


def params_v0() -> dict:
    """The v0 params block, from the frozen module (prereg content)."""
    return {
        "params_version": "v0",
        "window": int(_F.WINDOW),
        "min_obs": int(_F.MIN_OBS),
        "names_per_date_floor": int(_F.NAMES_PER_DATE_FLOOR),
        "params_source": _F.PARAMS_SOURCE,
    }


def _validate_v0_domains(p: dict) -> None:
    """Domain checks for params_version 'v0' — no silent inheritance by
    future versions (each new version must declare its own validator)."""
    if p["window"] <= 0:
        raise ValueError(f"params['window'] must be > 0, got {p['window']}")
    if p["min_obs"] <= 0:
        raise ValueError(f"params['min_obs'] must be > 0, got {p['min_obs']}")
    if p["min_obs"] > p["window"]:
        raise ValueError(
            f"params['min_obs']={p['min_obs']} must be <= "
            f"params['window']={p['window']} — a minimum observation count "
            "larger than the window can never be satisfied")
    if p["names_per_date_floor"] <= 0:
        raise ValueError(
            f"params['names_per_date_floor']={p['names_per_date_floor']} "
            "must be > 0")


def _validate_params(params: Mapping[str, Any]) -> dict:
    return validate_factor_params(
        params, int_keys=_REQUIRED_INT_KEYS,
        domain_validators={"v0": _validate_v0_domains})


def score_high52w(readers: FactorReaders, ticker: str, ts: pd.Timestamp,
                  p: Mapping[str, Any]) -> TickerScore | None:
    """score = close_t / max(close over the trailing window), on VALID closes.

    The window is the last ``window`` OBSERVATIONS of the series at/before
    the cutoff (trading-day semantics on the series' own calendar — the
    momentum core's convention). An observation qualifies iff it is finite
    and strictly positive; fewer than ``min_obs`` qualifying observations
    -> NaN (fail-closed). close_t is the most recent qualifying close; its
    date is MEASURED into last_read.
    """
    c = readers.close(ticker)
    if c is None:
        return None
    w = c.loc[c.index <= ts].tail(int(p["window"]))
    valid = w[np.isfinite(w) & (w > 0)]
    n = int(len(valid))
    if n == 0:
        return TickerScore(float("nan"), 0, None)
    last_read = valid.index.max()
    if n < p["min_obs"]:
        return TickerScore(float("nan"), n, last_read)
    return TickerScore(float(valid.iloc[-1] / valid.max()), n, last_read)


FACTOR = FactorDef(name="high52w", validate_params=_validate_params,
                   score_fn=score_high52w)


def build_high52w_artifact(asof: Any, universe: list[str],
                           params: Mapping[str, Any], *,
                           readers: FactorReaders) -> dict:
    """One scoring run = one ``factor_high52w_v0`` artifact for ``asof``."""
    return build_factor_artifact(asof, universe, params, factor=FACTOR,
                                 readers=readers)
