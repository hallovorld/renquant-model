"""TRAIN core: `train_momentum_artifact` — pure over injected readers. (GOAL-7 slice 2)

"Training" for this construction is the rolling estimation itself (per-name
residual state over the formation window) plus the per-date cross-sectional
stats the serving/scoring step needs — no fitted hyper-parameters in v0
(design §1). The mechanism functions are IMPORTED from
``renquant_model_common.momentum_features`` (F1–F5 + composite), never copied.

**Frozen v0 params from a PACKAGED MIRROR** (model#164 §2): window=252 /
skip=21 / min_obs=200, min_features=3, names_per_date_floor=50, and the
runner-declared min_side_obs=30 — carried by ``_frozen_params_v0``, which ships
in the wheel. They were previously read at call time from the sealed v1 runner
outside ``src/``; that made the installed package raise ``FileNotFoundError`` at
first use while every in-repo test passed (review round 1). The sealed runner
remains the AUTHORITY: ``test_params_v0_mirrors_the_sealed_v1_runner`` holds the
mirror equal to it wherever the repo is present, so a drifted copy fails loudly
instead of silently. ``params_v0()`` stamps ``params_version: "v0"``; a future weighted
composite or factor-residualization (design v-next) is a NEW params version,
never a silent change.

The assembly mirrors the v1 runner's ``assemble_day`` construction exactly
(same window bounds, same inner-join/dropna pairing, same feature calls in the
same order); the golden test proves score identity to <1e-9 against
``assemble_day`` itself on a fixed synthetic panel.

Artifact contract (gate-compatible from day one, design §1): self-carried
``cutoff_date``, ``effective_train_cutoff_date`` (MEASURED from the data
actually read, not asserted), ``cutoff_embargo_days``, params + universe +
per-input read digests + ``content_sha256``. TYPE discipline per the
stringified-norm_kind lesson: every list stays a list; the artifact serializes
with ``allow_nan=False`` (non-finite floats become null explicitly).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Protocol

import numpy as np
import pandas as pd

from renquant_model_common.momentum_features import (  # imported, never copied
    _EPS, composite_scores, f1_residual_momentum, f2_information_discreteness,
    f3_industry_momentum, f4_signed_volume_agreement, f5_downside_beta_penalty)

__all__ = ["ARTIFACT_KIND", "ARTIFACT_SCHEMA_VERSION", "MomentumReaders",
           "content_sha256_of", "params_v0", "train_momentum_artifact",
           "verify_artifact_content_sha"]

from . import _frozen_params_v0 as _F
from . import _frozen_params_v1_fast as _FF

ARTIFACT_KIND = "momentum_residual_v0"
ARTIFACT_SCHEMA_VERSION = 1


#: The params keys train_momentum_artifact requires (beyond params_version).
_REQUIRED_PARAM_KEYS = ("window", "skip", "min_obs", "min_features",
                        "names_per_date_floor", "min_side_obs")

#: Number of composite features (f1..f5) — the hard ceiling on min_features.
_N_FEATURES = 5


class MomentumReaders(Protocol):
    """Injected input surface — the core never touches disk itself.

    ``read_digests`` must return {input_name -> sha256 hex} for every input the
    reader actually served: recorded-at-read, not pinned (design §1 — this is
    production training, not a frozen study; the digest record is what makes
    any later dispute answerable).
    """

    def tr_returns(self, ticker: str) -> pd.Series | None: ...

    def volume(self, ticker: str) -> pd.Series | None: ...

    def market_tr_returns(self) -> pd.Series: ...

    def sector_of(self) -> Mapping[str, str | None]: ...

    def read_digests(self) -> Mapping[str, str]: ...


def params_v0() -> dict:
    """The v0 params block, from the PACKAGED mirror (review round 1).

    Previously sourced by importing `tools/goal7_momentum_run.py`, which never enters
    the wheel — an installed consumer failed at first use while every in-repo test
    passed. The six numbers now live in `_frozen_params_v0`, which ships, and
    `test_params_v0_mirrors_the_sealed_v1_runner` holds that module equal to the sealed
    runner's `FROZEN` dict wherever the repo is present. See that module's docstring for
    why a mirror rather than an inversion.
    """
    return {
        "params_version": "v0",
        "window": int(_F.WINDOW),
        "skip": int(_F.SKIP),
        "min_obs": int(_F.MIN_OBS),
        "min_features": int(_F.MIN_FEATURES),
        "names_per_date_floor": int(_F.NAMES_PER_DATE_FLOOR),
        "min_side_obs": int(_F.MIN_SIDE_OBS),
        "params_source": _F.PARAMS_SOURCE,
    }


def params_v1_fast() -> dict:
    """The v1_fast params block — the FAST momentum clock (model#199).

    Same construction as v0, different clock: 63-day formation, 5-day
    short-reversal skip, min_obs scaled to the same coverage ratio. The
    authority for the numbers is the #199 issue (frozen before any run);
    `test_params_v1_fast_matches_the_frozen_issue` holds the packaged module
    to those literals. SHADOW-ONLY lane by the operator's architecture
    decision — the slow v0 lane is the one bound for the prod MoE.
    """
    return {
        "params_version": "v1_fast",
        "window": int(_FF.WINDOW),
        "skip": int(_FF.SKIP),
        "min_obs": int(_FF.MIN_OBS),
        "min_features": int(_FF.MIN_FEATURES),
        "names_per_date_floor": int(_FF.NAMES_PER_DATE_FLOOR),
        "min_side_obs": int(_FF.MIN_SIDE_OBS),
        "params_source": _FF.PARAMS_SOURCE,
    }


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _jsonable(obj: Any) -> Any:
    """Strict-JSON projection: numpy scalars unwrapped, non-finite floats ->
    None (explicit null, never a bare NaN token), lists stay lists."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if np.isfinite(f) else None
    if obj is None or isinstance(obj, str):
        return obj
    raise TypeError(f"non-jsonable artifact value of type {type(obj).__name__}")


def content_sha256_of(artifact: Mapping[str, Any]) -> str:
    """sha256 over the canonical JSON of the artifact WITHOUT content_sha256."""
    body = {k: v for k, v in artifact.items() if k != "content_sha256"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"),
                       allow_nan=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def verify_artifact_content_sha(artifact: Mapping[str, Any]) -> None:
    """Raise ValueError unless the self-carried content_sha256 recomputes."""
    claimed = artifact.get("content_sha256")
    actual = content_sha256_of(artifact)
    if claimed != actual:
        raise ValueError(
            f"artifact content_sha256 mismatch: carried {claimed!r}, "
            f"recomputed {actual}")


def _validate_v0_domains(p: dict) -> None:
    """Domain checks for params_version 'v0' — no silent inheritance by future
    versions (each new version must declare its own explicit validator)."""
    if p["window"] <= 0:
        raise ValueError(f"params['window'] must be > 0, got {p['window']}")
    if p["skip"] < 0:
        raise ValueError(f"params['skip'] must be >= 0, got {p['skip']}")
    if p["min_obs"] <= 0:
        raise ValueError(f"params['min_obs'] must be > 0, got {p['min_obs']}")
    if p["min_obs"] > p["window"]:
        raise ValueError(
            f"params['min_obs']={p['min_obs']} must be <= "
            f"params['window']={p['window']} — a minimum observation count "
            "larger than the formation window can never be satisfied")
    if not (1 <= p["min_features"] <= _N_FEATURES):
        raise ValueError(
            f"params['min_features']={p['min_features']} must be in "
            f"[1, {_N_FEATURES}] — the composite has exactly {_N_FEATURES} "
            "features (f1..f5), so a higher floor can never be satisfied")
    if p["names_per_date_floor"] <= 0:
        raise ValueError(
            f"params['names_per_date_floor']={p['names_per_date_floor']} "
            "must be > 0")
    if p["min_side_obs"] <= 0:
        raise ValueError(
            f"params['min_side_obs']={p['min_side_obs']} must be > 0")


def _validate_params(params: Mapping[str, Any]) -> dict:
    if not isinstance(params, Mapping):
        raise ValueError("params must be a mapping")
    pv = params.get("params_version")
    if not isinstance(pv, str) or not pv:
        raise ValueError(
            "params must carry a non-empty string params_version — a params "
            "block without a version is a silent-change vector (design §1)")
    missing = [k for k in _REQUIRED_PARAM_KEYS if k not in params]
    if missing:
        raise ValueError(f"params missing required keys: {missing}")
    p = dict(params)
    for k in _REQUIRED_PARAM_KEYS:
        if not isinstance(p[k], (int, np.integer)) or isinstance(p[k], bool):
            raise ValueError(f"params[{k!r}] must be an int, got "
                             f"{type(p[k]).__name__}")
        p[k] = int(p[k])
    if pv != "v0":
        raise ValueError(
            f"unsupported params_version {pv!r} — no domain validator is "
            "registered for it; a new params version must define its own "
            "explicit domain validator rather than inheriting v0's, and "
            "must be added here as a fail-closed dispatch")
    _validate_v0_domains(p)
    return p


def train_momentum_artifact(asof: Any, universe: list[str],
                            params: Mapping[str, Any], *,
                            readers: MomentumReaders) -> dict:
    """One training run = one artifact for ``asof`` (the cutoff date).

    Mirrors the v1 runner's ``assemble_day`` construction exactly (window
    bounds, pairing, feature calls, composite) — the golden test pins the
    identity. Every drop is counted (``n_missing_series``), the names floor is
    MEASURED and recorded (``names_floor_ok``), never silently enforced here:
    consumers (scoring/evaluation) own the refusal, exactly as the v1 runner
    skips thin dates at IC time, not at assembly.

    Pure over ``readers``: no disk, no clock beyond the trained_at stamp."""
    p = _validate_params(params)
    ts = pd.Timestamp(asof)
    tickers = sorted(dict.fromkeys(str(t) for t in universe))
    if not tickers:
        raise ValueError("universe is empty")

    lo = ts - pd.tseries.offsets.BDay(p["window"] + p["skip"])
    hi = ts - pd.tseries.offsets.BDay(p["skip"])

    spy_tr = readers.market_tr_returns()
    m = spy_tr.loc[(spy_tr.index > lo) & (spy_tr.index <= hi)]
    sector_of = dict(readers.sector_of())

    feats: dict[str, dict[str, float]] = {k: {} for k in
                                          ("f1", "f2", "f3", "f4", "f5")}
    formation: dict[str, float] = {}
    n_missing_series = 0
    last_read: pd.Timestamp | None = None
    for t in tickers:
        r = readers.tr_returns(t)
        if r is None:
            n_missing_series += 1
            continue
        w = r.loc[(r.index > lo) & (r.index <= hi)]
        pair = pd.concat([w, m], axis=1, join="inner").dropna()
        if len(pair):
            pmax = pair.index.max()
            last_read = pmax if last_read is None else max(last_read, pmax)
        ri, rm = pair.iloc[:, 0].to_numpy(), pair.iloc[:, 1].to_numpy()
        feats["f1"][t] = f1_residual_momentum(ri, rm, min_obs=p["min_obs"])
        feats["f2"][t] = f2_information_discreteness(ri, min_obs=p["min_obs"])
        v = readers.volume(t)
        vw = (v.reindex(pair.index).to_numpy() if v is not None
              else np.full(len(pair), np.nan))
        feats["f4"][t] = f4_signed_volume_agreement(ri, vw, min_obs=p["min_obs"])
        feats["f5"][t] = f5_downside_beta_penalty(
            ri, rm, min_obs=p["min_obs"], min_side_obs=p["min_side_obs"])
        formation[t] = float(np.prod(1.0 + ri) - 1.0) if len(ri) else float("nan")
    feats["f3"] = f3_industry_momentum(formation, sector_of)
    scores, n_used = composite_scores(feats, min_features=p["min_features"])

    # Per-date cross-sectional stats for the serving/scoring step — the SAME
    # moments composite_scores standardizes with (mean, sd ddof=0 over finite
    # values; a feature with <2 finite values or sd<eps contributes nothing).
    tickers_x = sorted({t for col in feats.values() for t in col})
    xstats: dict[str, dict[str, Any]] = {}
    for fname, col in feats.items():
        vals = np.array([col.get(t, float("nan")) for t in tickers_x], float)
        finite = np.isfinite(vals)
        n_finite = int(finite.sum())
        mean = float(vals[finite].mean()) if n_finite else float("nan")
        sd = float(vals[finite].std(ddof=0)) if n_finite else float("nan")
        used = bool(n_finite >= 2 and np.isfinite(sd) and sd >= _EPS)
        xstats[fname] = {"n_finite": n_finite, "mean": mean, "sd": sd,
                         "used_in_composite": used}

    n_scored = int(sum(1 for s in scores.values() if np.isfinite(s)))
    artifact: dict[str, Any] = {
        "kind": ARTIFACT_KIND,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "trained_at_utc": _utc_now(),
        "cutoff_date": ts.date().isoformat(),
        "cutoff_embargo_days": p["skip"],
        "cutoff_embargo_days_rule": (
            "business days; the formation window is "
            "(cutoff - (window+skip) bd, cutoff - skip bd] — no label enters "
            "training, so the skip IS the gap between the last readable input "
            "and the cutoff (model#164 §2)"),
        "effective_train_cutoff_date": (last_read.date().isoformat()
                                        if last_read is not None else None),
        "effective_train_cutoff_rule": (
            "MEASURED max index date over every (name, market) pair actually "
            "consumed — never asserted from the window arithmetic"),
        "formation_window": {"lo_exclusive": lo.date().isoformat(),
                             "hi_inclusive": hi.date().isoformat()},
        "params": dict(p),
        "universe": tickers,
        "n_names": len(tickers),
        "n_missing_series": n_missing_series,
        "n_scored": n_scored,
        "names_floor_ok": bool(n_scored >= p["names_per_date_floor"]),
        "features": {t: {f: feats[f].get(t, float("nan"))
                         for f in ("f1", "f2", "f3", "f4", "f5")}
                     for t in tickers_x},
        "formation_return": dict(formation),
        "cross_sectional_stats": xstats,
        "scores": dict(scores),
        "n_used": {t: int(n) for t, n in n_used.items()},
        "inputs": {
            "read_digests": dict(readers.read_digests()),
            "digest_policy": ("recorded-at-read, not pinned — production "
                              "training over live surfaces (design §1)"),
        },
    }
    artifact = _jsonable(artifact)
    artifact["content_sha256"] = content_sha256_of(artifact)
    return artifact
