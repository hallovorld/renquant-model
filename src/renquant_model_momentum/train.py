"""TRAIN core: `train_momentum_artifact` — pure over injected readers. (GOAL-7 slice 2)

"Training" for this construction is the rolling estimation itself (per-name
residual state over the formation window) plus the per-date cross-sectional
stats the serving/scoring step needs — no fitted hyper-parameters in v0
(design §1). The mechanism functions are IMPORTED from
``renquant_model_common.momentum_features`` (F1–F5 + composite), never copied.

**Frozen v0 params BY IMPORT, never restated** (model#164 §2): window=252 /
skip=21 / min_obs=200, min_features=3, names_per_date_floor=50, and the
runner-declared min_side_obs=30 — all sourced at call time from the sealed v1
runner's ``FROZEN`` dict / ``MIN_SIDE_OBS`` constant
(``tools/goal7_momentum_run.py``), so no constant can drift here outside the
freeze. ``params_v0()`` stamps ``params_version: "v0"``; a future weighted
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
import importlib.util
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

ARTIFACT_KIND = "momentum_residual_v0"
ARTIFACT_SCHEMA_VERSION = 1

_REPO = Path(__file__).resolve().parents[2]
_V1_RUNNER_PATH = _REPO / "tools" / "goal7_momentum_run.py"
_V1_CACHE: Any = None

#: The params keys train_momentum_artifact requires (beyond params_version).
_REQUIRED_PARAM_KEYS = ("window", "skip", "min_obs", "min_features",
                        "names_per_date_floor", "min_side_obs")


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


def _load_v1_runner():
    """The sealed v1 runner module — the by-import home of the frozen constants.

    Loaded the way the v2 runner loads it (spec_from_file_location; the module
    has no import-time side effects beyond a sys.path insert). Cached."""
    global _V1_CACHE
    if _V1_CACHE is None:
        if not _V1_RUNNER_PATH.is_file():
            raise FileNotFoundError(
                f"frozen-constant source missing: {_V1_RUNNER_PATH} — params v0 "
                "is BY IMPORT from the sealed v1 runner and has no restated "
                "fallback by design")
        spec = importlib.util.spec_from_file_location(
            "goal7_momentum_run", _V1_RUNNER_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _V1_CACHE = mod
    return _V1_CACHE


def params_v0() -> dict:
    """The v0 params block: frozen constants BY IMPORT (model#164 §2).

    252/21/200 (window/skip/min_obs), min_features 3, names_per_date_floor 50
    come from the v1 runner's ``FROZEN`` dict; min_side_obs 30 is the
    runner-declared F5 per-side floor (reviewed in model#177). None of the six
    numbers is restated here — they are read from the sealed module, and the
    pinning test publishes the expected literals so any drift fails loudly."""
    v1 = _load_v1_runner()
    return {
        "params_version": "v0",
        "window": int(v1.FROZEN["window"]),
        "skip": int(v1.FROZEN["skip"]),
        "min_obs": int(v1.FROZEN["min_obs"]),
        "min_features": int(v1.FROZEN["min_features"]),
        "names_per_date_floor": int(v1.FROZEN["names_per_date_floor"]),
        "min_side_obs": int(v1.MIN_SIDE_OBS),
        "params_source": ("tools/goal7_momentum_run.py::FROZEN + MIN_SIDE_OBS "
                          "(by import; frozen in model#164 §2, F5 floor in "
                          "model#177)"),
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
