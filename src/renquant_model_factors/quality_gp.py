"""quality_gp — gross profitability (Novy-Marx), simple-sort emitter.

Artifact kind ``factor_quality_gp_v0``. The field-availability finding, the
exact upstream formula (gross_profit / total_assets, computed by
``renquant_base_data.sec_fundamentals``), and the freeze rationale live in
``_frozen_params_quality_gp_v0``; this module contributes only the params
block, its v0 domain validator, and the per-ticker score function.

The reader contract: ``FactorReaders.fundamental(ticker)`` serves the
ticker's ``gross_profitability`` series (which column that is, is part of
the FROZEN params — ``source_column`` — so a reader wired to a different
column is a fingerprint-visible recipe change, not a silent swap).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from typing import Any, Mapping

from . import _frozen_params_quality_gp_v0 as _F
from .machine import (FactorDef, FactorReaders, TickerScore,
                      build_factor_artifact, validate_factor_params)

__all__ = ["FACTOR", "build_quality_gp_artifact", "params_v0",
           "score_quality_gp"]

#: The params keys the score function requires (beyond params_version).
_REQUIRED_INT_KEYS = ("min_obs", "max_age_days", "names_per_date_floor")
_REQUIRED_STR_KEYS = ("source_column",)


def params_v0() -> dict:
    """The v0 params block, from the frozen module (prereg content)."""
    return {
        "params_version": "v0",
        "source_column": str(_F.SOURCE_COLUMN),
        "min_obs": int(_F.MIN_OBS),
        "max_age_days": int(_F.MAX_AGE_DAYS),
        "names_per_date_floor": int(_F.NAMES_PER_DATE_FLOOR),
        "params_source": _F.PARAMS_SOURCE,
    }


def _validate_v0_domains(p: dict) -> None:
    """Domain checks for params_version 'v0' — no silent inheritance by
    future versions (each new version must declare its own validator)."""
    if p["min_obs"] <= 0:
        raise ValueError(f"params['min_obs'] must be > 0, got {p['min_obs']}")
    if p["max_age_days"] <= 0:
        raise ValueError(
            f"params['max_age_days'] must be > 0, got {p['max_age_days']}")
    if p["names_per_date_floor"] <= 0:
        raise ValueError(
            f"params['names_per_date_floor']={p['names_per_date_floor']} "
            "must be > 0")


def _validate_params(params: Mapping[str, Any]) -> dict:
    return validate_factor_params(
        params, int_keys=_REQUIRED_INT_KEYS, str_keys=_REQUIRED_STR_KEYS,
        domain_validators={"v0": _validate_v0_domains})


def score_quality_gp(readers: FactorReaders, ticker: str, ts: pd.Timestamp,
                     p: Mapping[str, Any]) -> TickerScore | None:
    """score = the most recent finite gross_profitability at/before cutoff.

    The value is the UPSTREAM Novy-Marx ratio — this function never
    recomputes it. Fail-closed on two floors: fewer than ``min_obs`` finite
    snapshots, or a newest snapshot older than ``max_age_days`` CALENDAR
    days (the staleness ceiling that keeps a filing-dark name from serving
    a fossil value forever). The snapshot's own date is MEASURED into
    last_read — for annual filers it legitimately trails the cutoff.
    """
    f = readers.fundamental(ticker)
    if f is None:
        return None
    w = f.loc[f.index <= ts]
    valid = w[np.isfinite(w)]
    n = int(len(valid))
    if n == 0:
        return TickerScore(float("nan"), 0, None)
    last_read = valid.index.max()
    if n < p["min_obs"]:
        return TickerScore(float("nan"), n, last_read)
    age_days = int((ts.normalize() - pd.Timestamp(last_read).normalize()).days)
    if age_days > p["max_age_days"]:
        return TickerScore(float("nan"), n, last_read)
    return TickerScore(float(valid.iloc[-1]), n, last_read)


FACTOR = FactorDef(name="quality_gp", validate_params=_validate_params,
                   score_fn=score_quality_gp)


def build_quality_gp_artifact(asof: Any, universe: list[str],
                              params: Mapping[str, Any], *,
                              readers: FactorReaders) -> dict:
    """One scoring run = one ``factor_quality_gp_v0`` artifact for ``asof``."""
    return build_factor_artifact(asof, universe, params, factor=FACTOR,
                                 readers=readers)
