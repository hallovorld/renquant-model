"""Fit the alpha158+fund panel-rank calibrator from model-repo code.

The caller supplies a pre-trained panel-LTR XGBoost artifact and a data
directory containing ``alpha158_291_fundamental_dataset.parquet`` plus, for
production, the raw-label panel
``alpha158_291_fundamental_dataset_rawlabel.parquet``. This is the multirepo
replacement for RenQuant's umbrella ``scripts/fit_calibrator_alpha158_fund.py``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import re

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from renquant_model_common.calibrator_quality import flat_region_stats
from renquant_model_common.global_calibrator import fit_global_calibrator
from renquant_model_gbdt.feature_transform import transform_feature_frame


log = logging.getLogger("renquant_model_gbdt.fit_calibrator_alpha158_fund")

DEFAULT_PANEL_FILENAME = "alpha158_291_fundamental_dataset.parquet"
DEFAULT_RAW_LABEL_PANEL_FILENAME = "alpha158_291_fundamental_dataset_rawlabel.parquet"
DEFAULT_LABEL = "fwd_60d_excess"
MAX_FLAT_FRACTION = 0.30


def model_content_sha256(payload: dict) -> str:
    """Stable scorer identity over fields that change predictions."""
    content = {
        "params": payload.get("params"),
        "feature_cols": payload.get("feature_cols"),
        "feature_columns": payload.get("feature_columns"),
        "feature_means": payload.get("feature_means"),
        "feature_stds": payload.get("feature_stds"),
        "feature_norm_kind": payload.get("feature_norm_kind"),
        "feature_norm_kinds": payload.get("feature_norm_kinds"),
        "feature_raw_clip_low": payload.get("feature_raw_clip_low"),
        "feature_raw_clip_high": payload.get("feature_raw_clip_high"),
        "label_col": payload.get("label_col"),
        "booster_raw_json": payload.get("booster_raw_json"),
    }
    if not any(value is not None for value in content.values()):
        raise ValueError("payload has no recognizable scorer prediction content")
    blob = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _artifact_fingerprint(path: Path, payload: dict) -> str:
    try:
        content_fingerprint = model_content_sha256(payload)
    except ValueError:
        content_fingerprint = None
    return (
        payload.get("model_content_fingerprint")
        or content_fingerprint
        or payload.get("artifact_fingerprint")
        or payload.get("artifact_sha256")
        or payload.get("model_fingerprint")
        or payload.get("fingerprint")
        or "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    )


def _infer_raw_er_label(label_col: str) -> str:
    if label_col.endswith("_raw"):
        return label_col
    match = re.fullmatch(r"(fwd_\d+d_excess)", label_col)
    if match:
        return f"{match.group(1)}_raw"
    return f"{label_col}_raw"


def _infer_label_lookahead_days(label_col: str) -> int:
    match = re.search(r"fwd_(\d+)d", str(label_col or ""))
    return int(match.group(1)) if match else 60


def _label_scale_diagnostics(frame: pd.DataFrame, label_col: str) -> dict[str, float | int | bool]:
    if label_col not in frame.columns:
        raise KeyError(f"label column not present: {label_col}")
    labels = pd.to_numeric(frame[label_col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if labels.empty:
        raise ValueError(f"{label_col}: no finite labels")
    if "date" in frame.columns:
        by_date = frame.assign(date=pd.to_datetime(frame["date"]))
        per_date_std = (
            by_date.dropna(subset=[label_col])
            .groupby("date")[label_col]
            .std()
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
    else:
        per_date_std = pd.Series(dtype=float)
    per_date_std_median = float(per_date_std.median()) if not per_date_std.empty else float("nan")
    global_std = float(labels.std())
    abs_gt_20 = float((labels.abs() > 0.20).mean())
    looks_standardized = global_std > 0.50 and 0.75 <= per_date_std_median <= 1.25 and abs_gt_20 > 0.50
    return {
        "n": int(len(labels)),
        "mean": float(labels.mean()),
        "std": global_std,
        "min": float(labels.min()),
        "max": float(labels.max()),
        "abs_gt_20pct_fraction": abs_gt_20,
        "per_date_std_mean": float(per_date_std.mean()) if not per_date_std.empty else float("nan"),
        "per_date_std_median": per_date_std_median,
        "looks_cross_sectional_standardized": bool(looks_standardized),
    }


def _load_expected_return_labels(
    *,
    scoring_panel: pd.DataFrame,
    panel_path: Path,
    raw_label_panel_path: Path,
    model_label_col: str,
    er_label_col: str | None,
    allow_normalized_er_label: bool,
) -> tuple[pd.DataFrame, str, dict[str, float | int | bool], str]:
    chosen = er_label_col or _infer_raw_er_label(model_label_col)
    source = str(panel_path)

    if chosen not in scoring_panel.columns:
        if not raw_label_panel_path.exists():
            if allow_normalized_er_label and model_label_col in scoring_panel.columns:
                chosen = model_label_col
            else:
                raise FileNotFoundError(
                    f"Expected-return label {chosen!r} is not in {panel_path} and raw-label panel "
                    f"is missing: {raw_label_panel_path}"
                )
        else:
            raw_labels = pd.read_parquet(raw_label_panel_path, columns=["ticker", "date", chosen])
            raw_labels["date"] = pd.to_datetime(raw_labels["date"])
            scoring_panel = scoring_panel.merge(raw_labels, on=["ticker", "date"], how="left", validate="many_to_one")
            source = str(raw_label_panel_path)

    if chosen not in scoring_panel.columns:
        raise KeyError(f"Expected-return label {chosen!r} is unavailable after raw-label merge")

    diag = _label_scale_diagnostics(scoring_panel, chosen)
    if diag["looks_cross_sectional_standardized"] and not allow_normalized_er_label:
        raise ValueError(
            f"EXPECTED-RETURN-LABEL CONTRACT FAIL: {chosen!r} looks cross-sectionally standardized; "
            "Kelly/QP mu must use raw return units"
        )
    return scoring_panel, chosen, diag, source


def _mean_or_none(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _score_metric_metadata(
    *,
    label_ics: list[float],
    er_ics: list[float],
    data_start: str | None,
    data_end: str | None,
) -> dict[str, float | int | str | None]:
    window = "cli_bounded_panel" if (data_start or data_end) else "full_available_panel"
    return {
        "scorer_ic_scope": "calibrator_fit_window",
        "scorer_ic_window": window,
        "scorer_fit_window_mean_ic": _mean_or_none(label_ics),
        "scorer_fit_window_median_ic": float(np.median(label_ics)) if label_ics else None,
        "scorer_fit_window_n_dates": int(len(label_ics)),
        "scorer_fit_window_mean_ic_vs_er_label": _mean_or_none(er_ics),
        "scorer_fit_window_median_ic_vs_er_label": float(np.median(er_ics)) if er_ics else None,
        "scorer_fit_window_n_dates_vs_er_label": int(len(er_ics)),
        "scorer_oos_mean_ic": None,
        "scorer_oos_mean_ic_vs_er_label": None,
        "scorer_oos_metric_status": "not_measured_by_calibrator_fit",
    }


def _per_date_ic(frame: pd.DataFrame, score_col: str, label_col: str) -> list[float]:
    valid = frame.dropna(subset=[score_col, label_col])
    out: list[float] = []
    for _, group in valid.groupby("date"):
        if len(group) < 5:
            continue
        ic, _ = spearmanr(group[score_col], group[label_col])
        if not np.isnan(ic):
            out.append(float(ic))
    return out


def fit_alpha158_fund_calibrator(
    *,
    data_dir: str | Path,
    scorer_artifact: str | Path,
    out_path: str | Path,
    panel_path: str | Path | None = None,
    raw_label_panel_path: str | Path | None = None,
    er_label_col: str | None = None,
    allow_normalized_er_label: bool = False,
    data_start: str | None = None,
    data_end: str | None = None,
    method: str = "platt",
    min_rows: int = 1000,
) -> Path:
    data_dir = Path(data_dir).expanduser().resolve()
    panel_path = Path(panel_path).expanduser().resolve() if panel_path else data_dir / DEFAULT_PANEL_FILENAME
    raw_label_panel_path = (
        Path(raw_label_panel_path).expanduser().resolve()
        if raw_label_panel_path
        else data_dir / DEFAULT_RAW_LABEL_PANEL_FILENAME
    )
    scorer_artifact = Path(scorer_artifact).expanduser().resolve()
    out_path = Path(out_path).expanduser().resolve()

    art = json.loads(scorer_artifact.read_text())
    feat_cols = list(art["feature_cols"])
    fingerprint = _artifact_fingerprint(scorer_artifact, art)
    label_col = art.get("label_col", DEFAULT_LABEL)
    lookahead_days = _infer_label_lookahead_days(label_col)

    import xgboost as xgb  # noqa: PLC0415

    booster = xgb.Booster()
    booster.load_model(bytearray(art["booster_raw_json"].encode("utf-8")))

    panel = pd.read_parquet(panel_path)
    panel["date"] = pd.to_datetime(panel["date"])
    if data_start:
        panel = panel[panel["date"] >= pd.Timestamp(data_start)].copy()
    if data_end:
        panel = panel[panel["date"] < pd.Timestamp(data_end)].copy()

    panel, chosen_er_label, er_label_diag, er_label_source = _load_expected_return_labels(
        scoring_panel=panel,
        panel_path=panel_path,
        raw_label_panel_path=raw_label_panel_path,
        model_label_col=label_col,
        er_label_col=er_label_col,
        allow_normalized_er_label=allow_normalized_er_label,
    )

    X = transform_feature_frame(panel, feat_cols, art, source_space="panel")
    panel["panel_score"] = booster.predict(xgb.DMatrix(X.values.astype(np.float64)))

    label_ics = _per_date_ic(panel, "panel_score", label_col)
    er_ics = _per_date_ic(panel, "panel_score", chosen_er_label)

    panel_scores: dict[str, pd.Series] = {}
    future_returns: dict[str, pd.Series] = {}
    for ticker, group in panel.groupby("ticker"):
        sorted_group = group.sort_values("date").set_index("date")
        panel_scores[str(ticker)] = sorted_group["panel_score"]
        future_returns[str(ticker)] = sorted_group[chosen_er_label].dropna()

    calib = fit_global_calibrator(
        panel_scores,
        future_returns,
        lookahead_days=lookahead_days,
        threshold=0.0,
        threshold_mode="crosssectional",
        method=method,
        min_rows=min_rows,
    )

    prob_flat = flat_region_stats(calib.prob_x, calib.prob_y)
    er_flat = flat_region_stats(calib.er_x, calib.er_y)
    if prob_flat["fraction"] > MAX_FLAT_FRACTION:
        raise ValueError(f"probability curve flat region {prob_flat['fraction'] * 100:.1f}% exceeds gate")
    if er_flat["fraction"] > MAX_FLAT_FRACTION:
        raise ValueError(f"expected_return curve flat region {er_flat['fraction'] * 100:.1f}% exceeds gate")

    metadata = dict(calib.metadata)
    metadata["scorer_artifact"] = str(scorer_artifact)
    metadata["scorer_artifact_fingerprint"] = fingerprint
    metadata["scorer_model_content_fingerprint"] = fingerprint
    metadata.update(_score_metric_metadata(label_ics=label_ics, er_ics=er_ics, data_start=data_start, data_end=data_end))
    metadata["model_label_col"] = label_col
    metadata["expected_return_label_col"] = chosen_er_label
    metadata["expected_return_label_source"] = er_label_source
    metadata["expected_return_label_contract"] = "raw_return_units_required"
    metadata["expected_return_label_diagnostics"] = er_label_diag
    metadata["method"] = method
    if data_start:
        metadata["data_window_start"] = data_start
    if data_end:
        metadata["data_window_end"] = data_end
    metadata["lookahead_days_used"] = lookahead_days

    calib.save(out_path, metadata=metadata)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--scorer-artifact", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--panel", type=Path, default=None)
    parser.add_argument("--raw-label-panel", type=Path, default=None)
    parser.add_argument("--er-label-col", default=None)
    parser.add_argument("--allow-normalized-er-label", action="store_true")
    parser.add_argument("--data-start", default=None)
    parser.add_argument("--data-end", default=None)
    parser.add_argument("--method", default="platt", choices=["platt", "isotonic"])
    parser.add_argument("--min-rows", type=int, default=1000)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    fit_alpha158_fund_calibrator(
        data_dir=args.data_dir,
        scorer_artifact=args.scorer_artifact,
        out_path=args.out,
        panel_path=args.panel,
        raw_label_panel_path=args.raw_label_panel,
        er_label_col=args.er_label_col,
        allow_normalized_er_label=args.allow_normalized_er_label,
        data_start=args.data_start,
        data_end=args.data_end,
        method=args.method,
        min_rows=args.min_rows,
    )
    return 0


__all__ = ["fit_alpha158_fund_calibrator", "model_content_sha256"]


if __name__ == "__main__":
    raise SystemExit(main())
