"""Global panel-wide score calibrator.

This is the model-repo lift of RenQuant's umbrella
``training_panel.global_calibrator``. It keeps the JSON artifact contract while
removing ``kernel.*`` imports so training and scheduled retrain can run from
the multirepo model package.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
import logging
from pathlib import Path
from typing import Any
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from renquant_model_common.calibrator_quality import flat_region_stats


log = logging.getLogger("renquant_model_common.global_calibrator")

ER_CLIP = 0.20
MAX_ER_FLAT_FRACTION = 0.30


@dataclass
class GlobalPanelCalibration:
    """Two monotone maps: raw score -> probability and raw score -> expected return."""

    prob_x: np.ndarray
    prob_y: np.ndarray
    er_x: np.ndarray
    er_y: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.prob_x = np.asarray(self.prob_x, dtype=float)
        self.prob_y = np.asarray(self.prob_y, dtype=float)
        self.er_x = np.asarray(self.er_x, dtype=float)
        self.er_y = np.asarray(self.er_y, dtype=float)
        for name, arr in (("prob_x", self.prob_x), ("er_x", self.er_x)):
            if len(arr) >= 2 and not np.all(np.diff(arr) >= 0):
                first = int(np.argmax(np.diff(arr) < 0))
                raise ValueError(f"{name} must be monotonically non-decreasing; first violation={first}")

    def calibrate_probability(self, raw_score: float) -> float:
        if len(self.prob_x) == 0 or len(self.prob_y) == 0:
            return 0.5
        return float(np.interp(raw_score, self.prob_x, self.prob_y, left=self.prob_y[0], right=self.prob_y[-1]))

    def calibrate_probability_vec(self, raw_scores: np.ndarray) -> np.ndarray:
        if len(self.prob_x) == 0 or len(self.prob_y) == 0:
            return np.full(np.shape(raw_scores), 0.5, dtype=float)
        return np.interp(raw_scores, self.prob_x, self.prob_y, left=self.prob_y[0], right=self.prob_y[-1])

    def _native_lookahead_days(self) -> int | None:
        for key in ("lookahead_days_used", "lookahead_days", "er_lookahead"):
            try:
                value = int(self.metadata.get(key))
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
        return None

    def _scale_expected_return_to_horizon(self, value: float, horizon_days: int | None) -> float:
        if horizon_days is None:
            return float(value)
        native = self._native_lookahead_days()
        if native is None or native <= 0 or int(horizon_days) == native:
            return float(value)
        return float(value) * (float(horizon_days) / float(native))

    def expected_return(self, raw_score: float, *, horizon_days: int | None = None) -> float:
        if len(self.er_x) == 0 or len(self.er_y) == 0:
            return 0.0
        native_value = float(np.interp(raw_score, self.er_x, self.er_y, left=self.er_y[0], right=self.er_y[-1]))
        return self._scale_expected_return_to_horizon(native_value, horizon_days)

    def expected_return_vec(self, raw_scores: np.ndarray, *, horizon_days: int | None = None) -> np.ndarray:
        if len(self.er_x) == 0 or len(self.er_y) == 0:
            return np.zeros(np.shape(raw_scores), dtype=float)
        values = np.interp(raw_scores, self.er_x, self.er_y, left=self.er_y[0], right=self.er_y[-1])
        if horizon_days is None:
            return values
        native = self._native_lookahead_days()
        if native is None or native <= 0 or int(horizon_days) == native:
            return values
        return values * (float(horizon_days) / float(native))

    def save(self, path: str | Path, metadata: dict | None = None) -> None:
        merged_meta = {**self.metadata, **(metadata or {})}
        er_max_abs = float(np.max(np.abs(self.er_y), initial=0.0))
        if er_max_abs > ER_CLIP + 1e-9:
            raise ValueError(f"expected_return.y max|y|={er_max_abs:.4f} > {ER_CLIP}")
        prob_min = float(self.prob_y.min(initial=0.0))
        prob_max = float(self.prob_y.max(initial=0.0))
        if prob_min < -1e-9 or prob_max > 1.0 + 1e-9:
            raise ValueError(f"probability.y out of [0,1]: [{prob_min:.4f}, {prob_max:.4f}]")
        er_flat = flat_region_stats(self.er_x, self.er_y)
        max_er_flat = float(merged_meta.get("max_expected_return_flat_fraction", MAX_ER_FLAT_FRACTION))
        if er_flat["fraction"] > max_er_flat:
            raise ValueError(
                "expected_return.y flat region spans "
                f"{er_flat['fraction'] * 100:.1f}% of x-domain; max={max_er_flat * 100:.0f}%"
            )

        payload = {
            "version": 1,
            "kind": "global_panel_calibration",
            "trained_date": str(date.today()),
            "probability": {"x": self.prob_x.tolist(), "y": self.prob_y.tolist()},
            "expected_return": {"x": self.er_x.tolist(), "y": self.er_y.tolist()},
            "metadata": {
                **merged_meta,
                "expected_return_flat_fraction": er_flat["fraction"],
                "expected_return_longest_flat_span": er_flat["longest_span"],
            },
        }
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, default=str))

    @classmethod
    def load(cls, path: str | Path) -> "GlobalPanelCalibration":
        payload = json.loads(Path(path).read_text())
        if payload.get("kind") != "global_panel_calibration":
            raise ValueError(f"Not a global_panel_calibration artifact: {path}")
        prob_y = np.asarray(payload["probability"]["y"], dtype=float)
        er_y = np.asarray(payload["expected_return"]["y"], dtype=float)
        prob_y = np.clip(prob_y, 0.0, 1.0)
        er_y = np.clip(er_y, -ER_CLIP, ER_CLIP)
        return cls(
            prob_x=np.asarray(payload["probability"]["x"], dtype=float),
            prob_y=prob_y,
            er_x=np.asarray(payload["expected_return"]["x"], dtype=float),
            er_y=er_y,
            metadata=payload.get("metadata", {}),
        )


def fit_global_calibrator(
    panel_scores: dict[str, pd.Series],
    future_returns: dict[str, pd.Series],
    *,
    lookahead_days: int = 10,
    threshold: float = 0.03,
    threshold_mode: str = "absolute",
    min_rows: int = 1000,
    rolling_window_years: float | None = None,
    method: str = "isotonic",
) -> GlobalPanelCalibration:
    """Pool all ticker score/return pairs and fit probability + ER heads."""
    cutoff_ts: pd.Timestamp | None = None
    if rolling_window_years is not None and rolling_window_years > 0:
        latest = pd.Timestamp.min
        for raw in panel_scores.values():
            if not raw.empty:
                latest = max(latest, pd.Timestamp(raw.index.max()))
        if latest is not pd.Timestamp.min:
            cutoff_ts = latest - pd.Timedelta(days=int(rolling_window_years * 365.25))

    rows_raw: list[np.ndarray] = []
    rows_fwd: list[np.ndarray] = []
    rows_keys: list[tuple[pd.Timestamp, str]] = []
    contributed_tickers = 0
    for ticker, raw in panel_scores.items():
        fwd = future_returns.get(ticker)
        if fwd is None or raw.empty or fwd.empty:
            continue
        idx = raw.index.intersection(fwd.index)
        if cutoff_ts is not None:
            idx = idx[idx >= cutoff_ts]
        if len(idx) == 0:
            continue
        r = raw.loc[idx].astype(float).values
        f = fwd.loc[idx].astype(float).values
        ok = np.isfinite(r) & np.isfinite(f)
        if not ok.any():
            continue
        contributed_tickers += 1
        rows_raw.append(r[ok])
        rows_fwd.append(f[ok])
        rows_keys.extend((pd.Timestamp(d), ticker) for d in idx[ok])

    if not rows_raw:
        raise ValueError("fit_global_calibrator: no overlapping rows across tickers")
    raw_all = np.concatenate(rows_raw)
    fwd_all = np.concatenate(rows_fwd)
    if len(raw_all) < min_rows:
        raise ValueError(f"fit_global_calibrator: pooled n={len(raw_all)} < min_rows={min_rows}")

    raw_all, fwd_all, rows_keys = _drop_nan_leaf_collapse(raw_all, fwd_all, rows_keys, min_rows=min_rows)
    rho, _ = spearmanr(raw_all, fwd_all)
    per_date_ic_mean, n_dates_eval = _per_date_ic(raw_all, fwd_all, rows_keys)

    threshold_mode = threshold_mode.lower()
    if threshold_mode == "crosssectional" and len(rows_keys) == len(raw_all):
        df_prob = pd.DataFrame({"date": [key[0] for key in rows_keys], "fwd": fwd_all})
        per_date_median = df_prob.groupby("date")["fwd"].transform("median")
        prob_labels = (fwd_all >= per_date_median.values).astype(float)
    else:
        prob_labels = (fwd_all >= threshold).astype(float)

    fwd_clipped_count = int(np.sum(np.abs(fwd_all) > ER_CLIP))
    fwd_for_er = np.clip(fwd_all, -ER_CLIP, ER_CLIP)

    method_lc = (method or "isotonic").lower()
    if method_lc == "platt":
        prob_x, prob_y, er_x, er_y, er_head_method = _fit_platt_and_smooth_er(raw_all, prob_labels, fwd_all)
    elif method_lc == "isotonic":
        prob_x, prob_y, er_x, er_y, er_head_method = _fit_isotonic(raw_all, prob_labels, fwd_for_er)
    else:
        raise ValueError(f"unknown calibration method: {method!r}")

    n_unique_prob_y = int(len(set(np.round(prob_y, 8))))
    if n_unique_prob_y < 5:
        raise ValueError(
            f"fit_global_calibrator: probability head collapsed to {n_unique_prob_y} unique y values"
        )
    er_flat = flat_region_stats(er_x, er_y)
    if er_flat["fraction"] > MAX_ER_FLAT_FRACTION and method_lc == "platt":
        raise ValueError(
            f"fit_global_calibrator: expected_return flat region {er_flat['fraction'] * 100:.1f}% "
            f"> {MAX_ER_FLAT_FRACTION * 100:.0f}%"
        )
    if er_flat["fraction"] > MAX_ER_FLAT_FRACTION:
        log.warning(
            "fit_global_calibrator: expected_return flat region %.1f%% > %.0f%% for method=%s",
            er_flat["fraction"] * 100,
            MAX_ER_FLAT_FRACTION * 100,
            method_lc,
        )

    metadata = {
        "n_rows": int(len(raw_all)),
        "n_tickers": int(contributed_tickers),
        "pool_ic": float(rho) if rho == rho else None,
        "per_date_ic_mean": per_date_ic_mean,
        "n_dates_eval": int(n_dates_eval),
        "n_unique_prob_y": n_unique_prob_y,
        "threshold": float(threshold),
        "threshold_mode": threshold_mode,
        "lookahead_days": int(lookahead_days),
        "prob_base_rate": float(prob_labels.mean()),
        "er_mean": float(fwd_all.mean()),
        "er_std": float(fwd_all.std()),
        "calibration_method": method_lc,
        "er_clip_bound": ER_CLIP,
        "er_target_clip_count": fwd_clipped_count,
        "er_head_method": er_head_method,
        "n_unique_er_y": int(len(set(np.round(er_y, 8)))),
        "expected_return_flat_fraction": er_flat["fraction"],
    }
    log.info(
        "fit_global_calibrator: n=%d tickers=%d pool_ic=%s per_date_ic=%s base_rate=%.3f",
        metadata["n_rows"],
        metadata["n_tickers"],
        f"{metadata['pool_ic']:+.4f}" if metadata["pool_ic"] is not None else "n/a",
        f"{per_date_ic_mean:+.4f}" if per_date_ic_mean is not None else "n/a",
        metadata["prob_base_rate"],
    )
    return GlobalPanelCalibration(prob_x=prob_x, prob_y=prob_y, er_x=er_x, er_y=er_y, metadata=metadata)


def _drop_nan_leaf_collapse(
    raw_all: np.ndarray,
    fwd_all: np.ndarray,
    rows_keys: list[tuple[pd.Timestamp, str]],
    *,
    min_rows: int,
) -> tuple[np.ndarray, np.ndarray, list[tuple[pd.Timestamp, str]]]:
    from collections import Counter

    bucket = np.round(raw_all, 8)
    mode_val, mode_count = Counter(bucket.tolist()).most_common(1)[0]
    mode_pct = mode_count / len(raw_all)
    if mode_pct <= 0.01:
        return raw_all, fwd_all, rows_keys
    keep = ~np.isclose(raw_all, mode_val, atol=1e-9)
    raw_all = raw_all[keep]
    fwd_all = fwd_all[keep]
    if len(rows_keys) == len(keep):
        rows_keys = [key for key, ok in zip(rows_keys, keep) if ok]
    if len(raw_all) < min_rows:
        raise ValueError(f"fit_global_calibrator: after NaN-leaf filter n={len(raw_all)} < min_rows={min_rows}")
    return raw_all, fwd_all, rows_keys


def _per_date_ic(
    raw_all: np.ndarray,
    fwd_all: np.ndarray,
    rows_keys: list[tuple[pd.Timestamp, str]],
) -> tuple[float | None, int]:
    if len(rows_keys) != len(raw_all):
        return None, 0
    rhos: list[float] = []
    df_pool = pd.DataFrame({"date": [key[0] for key in rows_keys], "raw": raw_all, "fwd": fwd_all})
    for _, group in df_pool.groupby("date", sort=False):
        if len(group) < 5:
            continue
        rho, _ = spearmanr(group["raw"].values, group["fwd"].values)
        if rho == rho:
            rhos.append(float(rho))
    return (float(np.mean(rhos)), len(rhos)) if rhos else (None, 0)


def _fit_platt_and_smooth_er(
    raw_all: np.ndarray,
    prob_labels: np.ndarray,
    fwd_all: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
    from sklearn.linear_model import HuberRegressor, LinearRegression, LogisticRegression

    x_mean = float(np.mean(raw_all))
    x_std = float(np.std(raw_all))
    if x_std < 1e-12:
        x_std = 1.0
    prob_model = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        prob_model.fit(((raw_all - x_mean) / x_std).reshape(-1, 1), prob_labels)
    x_min = float(np.min(raw_all))
    x_max = float(np.max(raw_all))
    if x_max - x_min < 1e-12:
        x_min -= 1.0
        x_max += 1.0
    prob_x = np.linspace(x_min, x_max, 100)
    prob_y = prob_model.predict_proba(((prob_x - x_mean) / x_std).reshape(-1, 1))[:, 1]

    x_fit = ((raw_all - x_mean) / x_std).reshape(-1, 1)
    try:
        er_model = HuberRegressor(epsilon=1.35, alpha=1e-4, max_iter=1000)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            er_model.fit(x_fit, fwd_all)
        er_head_method = "huber_tanh_bound"
    except Exception as exc:  # noqa: BLE001
        log.warning("Huber ER head failed (%s); falling back to linear on clipped targets", exc)
        er_model = LinearRegression().fit(x_fit, np.clip(fwd_all, -ER_CLIP, ER_CLIP))
        er_head_method = "linear_tanh_bound_fallback"
    er_x = prob_x.copy()
    er_pred = er_model.predict(((er_x - x_mean) / x_std).reshape(-1, 1))
    er_y = ER_CLIP * np.tanh(er_pred / ER_CLIP)
    return prob_x, prob_y, er_x, er_y, er_head_method


def _fit_isotonic(
    raw_all: np.ndarray,
    prob_labels: np.ndarray,
    fwd_for_er: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
    from sklearn.isotonic import IsotonicRegression

    iso_prob = IsotonicRegression(out_of_bounds="clip").fit(raw_all, prob_labels)
    iso_er = IsotonicRegression(out_of_bounds="clip").fit(raw_all, fwd_for_er)
    return (
        np.asarray(iso_prob.X_thresholds_, dtype=float),
        np.asarray(iso_prob.y_thresholds_, dtype=float),
        np.asarray(iso_er.X_thresholds_, dtype=float),
        np.clip(np.asarray(iso_er.y_thresholds_, dtype=float), -ER_CLIP, ER_CLIP),
        "isotonic_clipped",
    )


__all__ = ["ER_CLIP", "GlobalPanelCalibration", "fit_global_calibrator"]
