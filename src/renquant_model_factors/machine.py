"""Shared simple-sort factor machine: (readers, factor, frozen params) → artifact.

G-I MoE impl step 1 (design orch#984 §4–5): the three momentum-grade
candidates (`high52w`, `lowbeta`, `quality_gp`) are clones of the momentum
emitter PATTERN, so the machinery that pattern already proved is IMPORTED,
never copied — ``content_sha256_of`` / ``verify_artifact_content_sha`` come
from ``renquant_model_momentum.train`` and the chained ledger comes from
``renquant_model_momentum.ledger`` (re-exported by the package
``__init__``). What is NEW here is exactly what differs per factor: the
frozen params, the per-ticker scoring formula, and the artifact ``kind``.

One shared assembly (``build_factor_artifact``) mirrors the momentum
artifact contract field-for-field where the field's meaning carries over:
self-carried ``cutoff_date``, ``effective_train_cutoff_date`` (MEASURED from
the data actually read, not asserted), params + universe + per-input read
digests + ``content_sha256``; every drop is counted (``n_missing_series``),
and the names floor is MEASURED and recorded (``names_floor_ok``), never
silently enforced — refusal belongs to the consumers, exactly as in the
momentum train core.

Scores are RAW, never z-scored here: the serving-side blend
(``renquant_pipeline.kernel.panel_pipeline.blend_scorer.BlendPanelScorer``)
z-scores every component cross-sectionally at serve time (mu/sd ddof=0 over
the finite-scored universe) — that is how the momentum ledger's scores are
consumed today, and these emitters ride the same machinery.

Pure over ``readers``: no disk, no network, no clock beyond the trained_at
stamp. Nothing here schedules anything (operator-gated, a later step) and
nothing here screens IC (impl step 2, its own frozen spec).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

import numpy as np
import pandas as pd

from renquant_model_momentum.train import content_sha256_of  # imported, never copied

__all__ = ["ARTIFACT_SCHEMA_VERSION", "FactorDef", "FactorReaders",
           "TickerScore", "artifact_kind_for", "build_factor_artifact",
           "factor_config_fingerprint", "validate_factor_params"]

ARTIFACT_SCHEMA_VERSION = 1


def artifact_kind_for(factor_name: str, params_version: str) -> str:
    """Mirror of momentum's ``artifact_kind_for``: the kind is DERIVED from the
    factor name + params_version so a new params version can never ship
    mislabeled under the old kind (the version-mislabel class, model#200 CR)."""
    return f"factor_{factor_name}_{params_version}"


class FactorReaders(Protocol):
    """Injected input surface — the machine never touches disk itself.

    Every series is date-sorted with a DatetimeIndex. A factor's score
    function touches ONLY the surfaces its formula names (high52w: close;
    lowbeta: close + market_close; quality_gp: fundamental) — a stub reader
    in tests need only implement those. ``market_close`` is the SPY close
    series supplied as an INPUT, never fetched (design orch#984 §4).

    ``read_digests`` must return {input_name -> sha256 hex} for every input
    the reader actually served: recorded-at-read, not pinned — same policy
    as the momentum readers (the digest record is what makes any later
    dispute answerable).
    """

    def close(self, ticker: str) -> pd.Series | None: ...

    def market_close(self) -> pd.Series: ...

    def fundamental(self, ticker: str) -> pd.Series | None: ...

    def read_digests(self) -> Mapping[str, str]: ...


@dataclass(frozen=True)
class TickerScore:
    """One ticker's scoring outcome: a RAW score (NaN = fail-closed on this
    ticker, e.g. min_obs not met), the qualifying-observation count, and the
    MEASURED date of the newest input actually consumed (None when nothing
    qualified)."""

    score: float
    n_obs: int
    last_read: pd.Timestamp | None


#: A factor's per-ticker scorer. Returns None when the ticker's input series
#: is missing ENTIRELY (counted as n_missing_series, momentum's discipline);
#: returns a TickerScore with a NaN score when the series exists but fails
#: the frozen floors (min_obs / staleness) — the distinction is load-bearing
#: for coverage accounting.
FactorScoreFn = Callable[
    ["FactorReaders", str, pd.Timestamp, Mapping[str, Any]],
    "TickerScore | None"]


@dataclass(frozen=True)
class FactorDef:
    """One factor = a name (the kind is derived from it), a params validator
    (fail-closed on unknown params_version), and a per-ticker score function.
    The frozen params themselves live in the factor's ``_frozen_params_*``
    module — prereg content, never constructed ad hoc."""

    name: str
    validate_params: Callable[[Mapping[str, Any]], dict]
    score_fn: FactorScoreFn


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _jsonable(obj: Any) -> Any:
    """Strict-JSON projection: numpy scalars unwrapped, non-finite floats ->
    None (explicit null, never a bare NaN token), lists stay lists.

    Minimal equivalent of ``renquant_model_momentum.train._jsonable`` — that
    helper is underscore-private, so it is re-stated here rather than
    imported; there is NO semantic divergence, and the public sha helpers
    (``content_sha256_of`` etc.) ARE imported."""
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


def factor_config_fingerprint(factor_name: str, params: Mapping[str, Any]) -> str:
    """Scoring-config identity: ``factor_<name>-<params_version>-<digest16>``.

    The digest recipe is byte-for-byte the momentum producer's
    ``params_config_fingerprint`` (canonical JSON, sha256, first 16 hex) —
    the ONE divergence is the PREFIX: that helper stamps ``momentum-``, which
    would mislabel a factor artifact as a momentum recipe, so it is not
    imported for this. The fingerprint is recomputable from the artifact by
    any reader (the same property ``blend_scorer.config_fp_pin_matches``
    relies on for the momentum leg) and is stable across weekly publishes
    with unchanged frozen params.
    """
    if not factor_name:
        raise ValueError("factor_name must be non-empty")
    canon = json.dumps(dict(params), sort_keys=True, separators=(",", ":"),
                       allow_nan=False)
    digest = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]
    return f"factor_{factor_name}-{params.get('params_version')}-{digest}"


def validate_factor_params(params: Mapping[str, Any], *,
                           int_keys: tuple[str, ...],
                           domain_validators: Mapping[str, Callable[[dict], None]],
                           str_keys: tuple[str, ...] = ()) -> dict:
    """The ONE structural params validator, shared by every factor.

    Mirrors momentum's ``_validate_params`` discipline: a params block
    without a non-empty string ``params_version`` is a silent-change vector
    and is refused; required keys are presence- AND type-checked (bool is
    not an int); the domain validator is dispatched BY version with a
    fail-closed else — a new params version must register its own explicit
    validator rather than inheriting v0's.
    """
    if not isinstance(params, Mapping):
        raise ValueError("params must be a mapping")
    pv = params.get("params_version")
    if not isinstance(pv, str) or not pv:
        raise ValueError(
            "params must carry a non-empty string params_version — a params "
            "block without a version is a silent-change vector (the momentum "
            "train rule, inherited verbatim)")
    missing = [k for k in (*int_keys, *str_keys) if k not in params]
    if missing:
        raise ValueError(f"params missing required keys: {missing}")
    p = dict(params)
    for k in int_keys:
        if not isinstance(p[k], (int, np.integer)) or isinstance(p[k], bool):
            raise ValueError(
                f"params[{k!r}] must be an int, got {type(p[k]).__name__}")
        p[k] = int(p[k])
    for k in str_keys:
        if not isinstance(p[k], str) or not p[k]:
            raise ValueError(
                f"params[{k!r}] must be a non-empty str, got {p[k]!r}")
    validator = domain_validators.get(pv)
    if validator is None:
        raise ValueError(
            f"unsupported params_version {pv!r} — no domain validator is "
            "registered for it; a new params version must define its own "
            "explicit domain validator rather than inheriting v0's, and "
            "must be added as a fail-closed dispatch")
    validator(p)
    return p


def build_factor_artifact(asof: Any, universe: list[str],
                          params: Mapping[str, Any], *,
                          factor: FactorDef,
                          readers: FactorReaders) -> dict:
    """One scoring run = one artifact for ``asof`` (the cutoff date).

    The momentum artifact contract, field-for-field where the meaning
    carries over. ``cutoff_embargo_days`` is 0 BY CONSTRUCTION for these
    simple sorts: the formula reads inputs through the cutoff itself and no
    label enters scoring, so there is no gap to declare (momentum's 21 is
    its short-reversal skip, which these formulas do not have).
    ``effective_train_cutoff_date`` is MEASURED from what was actually read
    — for quality_gp that is the newest QUALIFYING fundamental snapshot,
    which can trail the cutoff by up to the frozen staleness ceiling.

    Ledger discipline (caller-side): each factor appends to its OWN ledger
    file via the imported ``append_to_artifact_ledger`` — the chain's
    (cutoff_date, params_version) uniqueness key assumes a single-kind lane
    per file, exactly like the momentum / momentum_fast lanes.
    """
    p = factor.validate_params(params)
    ts = pd.Timestamp(asof)
    tickers = sorted(dict.fromkeys(str(t) for t in universe))
    if not tickers:
        raise ValueError("universe is empty")

    scores: dict[str, float] = {}
    n_obs: dict[str, int] = {}
    n_missing_series = 0
    last_read: pd.Timestamp | None = None
    for t in tickers:
        r = factor.score_fn(readers, t, ts, p)
        if r is None:
            n_missing_series += 1
            continue
        scores[t] = float(r.score)
        n_obs[t] = int(r.n_obs)
        if r.last_read is not None:
            last_read = (r.last_read if last_read is None
                         else max(last_read, r.last_read))

    n_scored = int(sum(1 for s in scores.values() if np.isfinite(s)))
    artifact: dict[str, Any] = {
        "kind": artifact_kind_for(factor.name, p["params_version"]),
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "trained_at_utc": _utc_now(),
        "cutoff_date": ts.date().isoformat(),
        "cutoff_embargo_days": 0,
        "cutoff_embargo_days_rule": (
            "zero by construction: the simple-sort formula reads inputs "
            "through the cutoff itself and no label enters scoring, so "
            "there is no formation gap to declare (design orch#984 §5 "
            "step 1; contrast momentum's short-reversal skip)"),
        "effective_train_cutoff_date": (last_read.date().isoformat()
                                        if last_read is not None else None),
        "effective_train_cutoff_rule": (
            "MEASURED max index date over every input series actually "
            "consumed — never asserted from the window arithmetic"),
        "params": dict(p),
        "config_fingerprint": factor_config_fingerprint(factor.name, p),
        "universe": tickers,
        "n_names": len(tickers),
        "n_missing_series": n_missing_series,
        "n_scored": n_scored,
        "names_floor_ok": bool(n_scored >= p["names_per_date_floor"]),
        "scores": dict(scores),
        "n_obs": dict(n_obs),
        "inputs": {
            "read_digests": dict(readers.read_digests()),
            "digest_policy": ("recorded-at-read, not pinned — production "
                              "scoring over live surfaces (the momentum "
                              "design §1 policy, inherited)"),
        },
    }
    artifact = _jsonable(artifact)
    artifact["content_sha256"] = content_sha256_of(artifact)
    return artifact
