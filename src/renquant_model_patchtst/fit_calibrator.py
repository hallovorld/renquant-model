"""Fit a global calibrator for a PatchTST-family sequence scorer.

This is the model-repo replacement for the old umbrella PatchTST calibrator.
It replays the same per-ticker sequence windows used at inference, scores
eligible ``(ticker, date)`` rows, and fits the shared
``GlobalPanelCalibration`` on raw forward-return labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd

from renquant_model_common.calibrator_quality import flat_region_stats
from renquant_model_common.global_calibrator import fit_global_calibrator


log = logging.getLogger("renquant_model_patchtst.fit_calibrator")

DEFAULT_PANEL = Path("data/transformer_v4_wl200_clean.parquet")
DEFAULT_RAW_LABEL_PANEL = Path("data/alpha158_291_fundamental_dataset_rawlabel.parquet")
DEFAULT_LABEL = "fwd_60d_excess"
MAX_FLAT_FRACTION = 0.30


def _resolve_path(path: str | Path | None, default: Path) -> Path:
    raw = Path(path) if path is not None else default
    return raw.expanduser().resolve()


def _sidecar_path_for(model_path: Path) -> Path:
    return model_path.with_name(model_path.name + ".metadata.json")


def _load_sidecar(model_path: Path) -> dict[str, Any]:
    sidecar = _sidecar_path_for(model_path)
    if not sidecar.exists():
        return {}
    return json.loads(sidecar.read_text())


def _load_checkpoint(model_path: Path) -> dict[str, Any]:
    import torch  # noqa: PLC0415

    payload = torch.load(model_path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict):
        raise ValueError(f"PatchTST checkpoint must be a dict: {model_path}")
    return payload


def _load_patchtst_scorer(model_path: Path):
    from renquant_model_patchtst.scorer import load  # noqa: PLC0415

    return load({"local_artifact_path": str(model_path)})


def _artifact_fingerprint(path: Path, checkpoint: dict[str, Any], sidecar: dict[str, Any]) -> str:
    return (
        sidecar.get("model_content_fingerprint")
        or sidecar.get("artifact_fingerprint")
        or sidecar.get("artifact_sha256")
        or sidecar.get("model_fingerprint")
        or sidecar.get("fingerprint")
        or checkpoint.get("model_content_fingerprint")
        or checkpoint.get("artifact_fingerprint")
        or checkpoint.get("artifact_sha256")
        or checkpoint.get("model_fingerprint")
        or checkpoint.get("fingerprint")
        or "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    )


def _infer_raw_er_label(label_col: str) -> str:
    if label_col.endswith("_raw"):
        return label_col
    match = re.fullmatch(r"(fwd_\d+d_excess)", label_col)
    if match:
        return f"{match.group(1)}_raw"
    return f"{label_col}_raw"


def _infer_label_lookahead_days(label_col: str | None) -> int:
    match = re.search(r"fwd_(\d+)d", str(label_col or ""))
    return int(match.group(1)) if match else 60


def _unique_columns(columns: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for col in columns:
        if col not in seen:
            out.append(col)
            seen.add(col)
    return out


def _label_scale_diagnostics(frame: pd.DataFrame, label_col: str) -> dict[str, float | int | bool]:
    if label_col not in frame.columns:
        raise KeyError(f"label column not present: {label_col}")
    labels = pd.to_numeric(frame[label_col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if labels.empty:
        raise ValueError(f"{label_col}: no finite labels")
    per_date_std = (
        frame.assign(date=pd.to_datetime(frame["date"]))
        .dropna(subset=[label_col])
        .groupby("date")[label_col]
        .std()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
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


def _load_panel_with_raw_label(
    *,
    panel_path: Path,
    raw_label_panel_path: Path,
    feature_cols: list[str],
    label_col: str,
    er_label_col: str,
    allow_normalized_er_label: bool,
) -> tuple[pd.DataFrame, dict[str, float | int | bool], str]:
    panel_columns = _unique_columns(["ticker", "date", label_col, er_label_col, *feature_cols])
    try:
        panel = pd.read_parquet(panel_path, columns=panel_columns)
        er_source = str(panel_path)
    except Exception:
        panel_columns = _unique_columns(["ticker", "date", label_col, *feature_cols])
        panel = pd.read_parquet(panel_path, columns=panel_columns)
        er_source = str(raw_label_panel_path)
    panel["date"] = pd.to_datetime(panel["date"])

    if er_label_col not in panel.columns:
        if not raw_label_panel_path.exists():
            if allow_normalized_er_label and label_col in panel.columns:
                er_label_col = label_col
                er_source = str(panel_path)
            else:
                raise FileNotFoundError(
                    f"expected-return label {er_label_col!r} is absent from {panel_path} "
                    f"and raw-label panel is missing: {raw_label_panel_path}"
                )
        else:
            raw = pd.read_parquet(raw_label_panel_path, columns=["ticker", "date", er_label_col])
            raw["date"] = pd.to_datetime(raw["date"])
            panel = panel.merge(raw, on=["ticker", "date"], how="left", validate="many_to_one")
            er_source = str(raw_label_panel_path)

    if panel[er_label_col].notna().sum() == 0:
        raise ValueError(
            f"raw expected-return label {er_label_col!r} has no overlap with {panel_path}; "
            "check --raw-label-panel"
        )
    diagnostics = _label_scale_diagnostics(panel, er_label_col)
    if diagnostics["looks_cross_sectional_standardized"] and not allow_normalized_er_label:
        raise ValueError(
            f"EXPECTED-RETURN-LABEL CONTRACT FAIL: {er_label_col!r} looks cross-sectionally "
            "standardized; calibrator expected-return head must use raw return units"
        )
    return panel, diagnostics, er_source


def _csrank_norm_per_day(panel: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    out = panel.copy()
    out[feature_cols] = out.groupby("date")[feature_cols].rank(pct=True) - 0.5
    out[feature_cols] = out[feature_cols].fillna(0.0)
    return out


def _date_window_mask(dates: pd.Series, start: str | None, end: str | None) -> pd.Series:
    mask = pd.Series(True, index=dates.index)
    if start:
        mask &= dates >= pd.Timestamp(start)
    if end:
        mask &= dates < pd.Timestamp(end)
    return mask


def _history_start(data_start: str | None, seq_len: int) -> pd.Timestamp | None:
    if not data_start:
        return None
    return pd.Timestamp(data_start) - pd.Timedelta(days=seq_len * 5)


def _score_sequences(
    scorer: Any,
    panel: pd.DataFrame,
    *,
    data_start: str | None,
    data_end: str | None,
    batch_size: int,
    use_csranknorm_preprocessing: bool,
) -> pd.DataFrame:
    import torch  # noqa: PLC0415

    torch.set_num_threads(max(1, int(os.getenv("RENQUANT_TORCH_THREADS", "1"))))
    feature_cols = list(scorer.feature_cols)
    seq_len = int(scorer.seq_len)
    work = panel
    if data_end:
        work = work[work["date"] < pd.Timestamp(data_end)]
    start = _history_start(data_start, seq_len)
    if start is not None:
        work = work[work["date"] >= start]
    if work.empty:
        raise ValueError("PatchTST sequence replay frame is empty after date filters")

    log.info(
        "Sequence replay frame rows=%d tickers=%d dates=%s..%s",
        len(work),
        work["ticker"].nunique(),
        pd.Timestamp(work["date"].min()).date(),
        pd.Timestamp(work["date"].max()).date(),
    )
    ph = work[["ticker", "date", *feature_cols]].copy()
    if use_csranknorm_preprocessing:
        log.info("Applying CSRankNorm to %d feature columns", len(feature_cols))
        ph = _csrank_norm_per_day(ph, feature_cols)
    ph = ph.sort_values(["ticker", "date"])

    device = getattr(scorer, "device", "cpu")
    seq_batch: list[np.ndarray] = []
    tickers: list[str] = []
    dates_out: list[pd.Timestamp] = []
    chunks: list[pd.DataFrame] = []

    def flush() -> None:
        if not seq_batch:
            return
        x = torch.from_numpy(np.stack(seq_batch, axis=0)).to(device)
        with torch.no_grad():
            out = scorer.model(past_values=x)
        scores = out["score"].detach().cpu().numpy().astype(float)
        chunk = pd.DataFrame({
            "ticker": tickers.copy(),
            "date": dates_out.copy(),
            "panel_score": scores.reshape(-1),
        })
        loc = out.get("loc") if isinstance(out, dict) else None
        scale = out.get("scale") if isinstance(out, dict) else None
        if loc is not None:
            chunk["mu"] = loc.detach().cpu().numpy().astype(float).reshape(-1)
        if scale is not None:
            chunk["sigma"] = scale.detach().cpu().numpy().astype(float).reshape(-1)
        chunks.append(chunk)
        seq_batch.clear()
        tickers.clear()
        dates_out.clear()

    for ticker, group in ph.groupby("ticker", sort=False):
        group = group.sort_values("date")
        values = group[feature_cols].fillna(0.0).to_numpy(dtype=np.float32)
        dates = pd.to_datetime(group["date"]).reset_index(drop=True)
        valid_date = _date_window_mask(dates, data_start, data_end).to_numpy()
        for idx in range(seq_len - 1, len(group)):
            if not valid_date[idx]:
                continue
            seq_batch.append(values[idx - seq_len + 1: idx + 1])
            tickers.append(str(ticker))
            dates_out.append(pd.Timestamp(dates.iloc[idx]))
            if len(seq_batch) >= batch_size:
                flush()
    flush()
    if not chunks:
        raise ValueError("No PatchTST sequences were scored; check date window.")
    return pd.concat(chunks, ignore_index=True)


def _per_date_ic(frame: pd.DataFrame, score_col: str, label_col: str) -> list[float]:
    from scipy.stats import spearmanr  # noqa: PLC0415

    out: list[float] = []
    for _, group in frame.dropna(subset=[score_col, label_col]).groupby("date"):
        if len(group) < 5:
            continue
        ic, _ = spearmanr(group[score_col], group[label_col])
        if np.isfinite(ic):
            out.append(float(ic))
    return out


def _mean_or_none(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _score_metric_metadata(
    *,
    label_ics: list[float],
    er_ics: list[float],
    data_start: str | None,
    data_end: str | None,
) -> dict[str, float | int | str | None]:
    window = "cli_bounded_sequence_replay" if (data_start or data_end) else "full_available_sequence_replay"
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


def _metadata_value(checkpoint: dict[str, Any], sidecar: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if checkpoint.get(key) is not None:
            return checkpoint[key]
        if sidecar.get(key) is not None:
            return sidecar[key]
    return None


def fit_patchtst_calibrator(
    *,
    scorer_artifact: str | Path,
    out_path: str | Path,
    panel_path: str | Path = DEFAULT_PANEL,
    raw_label_panel_path: str | Path = DEFAULT_RAW_LABEL_PANEL,
    label_col: str | None = None,
    er_label_col: str | None = None,
    allow_normalized_er_label: bool = False,
    data_start: str | None = None,
    data_end: str | None = None,
    batch_size: int = 2048,
    method: str = "platt",
    min_rows: int = 1000,
) -> Path:
    scorer_path = _resolve_path(scorer_artifact, Path(""))
    out_path = _resolve_path(out_path, Path(""))
    panel_path = _resolve_path(panel_path, DEFAULT_PANEL)
    raw_label_panel_path = _resolve_path(raw_label_panel_path, DEFAULT_RAW_LABEL_PANEL)

    checkpoint = _load_checkpoint(scorer_path)
    sidecar = _load_sidecar(scorer_path)
    scorer_fp = _artifact_fingerprint(scorer_path, checkpoint, sidecar)
    model_label_col = label_col or _metadata_value(checkpoint, sidecar, "label_col", "label") or DEFAULT_LABEL
    chosen_er_label = er_label_col or _infer_raw_er_label(str(model_label_col))
    lookahead_days = int(
        _metadata_value(checkpoint, sidecar, "lookahead_days", "lookahead_days_used")
        or _infer_label_lookahead_days(str(model_label_col))
    )
    use_csranknorm = bool(checkpoint.get("uses_csranknorm_preprocessing", True))

    log.info("Loading PatchTST scorer: %s", scorer_path)
    scorer = _load_patchtst_scorer(scorer_path)

    log.info("Loading panel=%s raw_label_panel=%s", panel_path, raw_label_panel_path)
    panel, er_label_diag, er_label_source = _load_panel_with_raw_label(
        panel_path=panel_path,
        raw_label_panel_path=raw_label_panel_path,
        feature_cols=list(scorer.feature_cols),
        label_col=str(model_label_col),
        er_label_col=str(chosen_er_label),
        allow_normalized_er_label=allow_normalized_er_label,
    )
    log.info(
        "Panel rows=%d tickers=%d dates=%s..%s",
        len(panel),
        panel["ticker"].nunique(),
        pd.Timestamp(panel["date"].min()).date(),
        pd.Timestamp(panel["date"].max()).date(),
    )

    scored = _score_sequences(
        scorer,
        panel,
        data_start=data_start,
        data_end=data_end,
        batch_size=batch_size,
        use_csranknorm_preprocessing=use_csranknorm,
    )
    scored = scored.merge(
        panel[["ticker", "date", str(model_label_col), str(chosen_er_label)]],
        on=["ticker", "date"],
        how="left",
    )
    log.info(
        "Scored rows=%d tickers=%d dates=%s..%s",
        len(scored),
        scored["ticker"].nunique(),
        pd.Timestamp(scored["date"].min()).date(),
        pd.Timestamp(scored["date"].max()).date(),
    )

    label_ics = _per_date_ic(scored, "panel_score", str(model_label_col))
    er_ics = _per_date_ic(scored, "panel_score", str(chosen_er_label))
    log.info("Daily IC fit-window: model_label=%s raw_ER=%s", _mean_or_none(label_ics), _mean_or_none(er_ics))

    panel_scores: dict[str, pd.Series] = {}
    future_returns: dict[str, pd.Series] = {}
    for ticker, group in scored.groupby("ticker"):
        sorted_group = group.sort_values("date").set_index("date")
        panel_scores[str(ticker)] = sorted_group["panel_score"]
        future_returns[str(ticker)] = sorted_group[str(chosen_er_label)].dropna()

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
    metadata["scorer_artifact"] = str(scorer_path)
    metadata["scorer_artifact_fingerprint"] = scorer_fp
    metadata["scorer_model_content_fingerprint"] = scorer_fp
    metadata["scorer_val_ic"] = _metadata_value(checkpoint, sidecar, "best_val_ic", "val_ic")
    metadata.update(_score_metric_metadata(label_ics=label_ics, er_ics=er_ics, data_start=data_start, data_end=data_end))
    metadata["model_label_col"] = str(model_label_col)
    metadata["expected_return_label_col"] = str(chosen_er_label)
    metadata["expected_return_label_source"] = er_label_source
    metadata["expected_return_label_contract"] = "raw_return_units_required"
    metadata["expected_return_label_diagnostics"] = er_label_diag
    metadata["method"] = method
    metadata["calibration_scope"] = "patchtst_sequence_replay"
    metadata["uses_csranknorm_preprocessing"] = use_csranknorm
    metadata["lookahead_days_used"] = lookahead_days
    if data_start:
        metadata["data_window_start"] = data_start
    if data_end:
        metadata["data_window_end"] = data_end

    log.info("Saving calibrator: %s", out_path)
    calib.save(out_path, metadata=metadata)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scorer-artifact", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--raw-label-panel", type=Path, default=DEFAULT_RAW_LABEL_PANEL)
    parser.add_argument("--label-col", default=None)
    parser.add_argument("--er-label-col", default=None)
    parser.add_argument("--allow-normalized-er-label", action="store_true")
    parser.add_argument("--data-start", default=None)
    parser.add_argument("--data-end", default=None)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--method", default="platt", choices=["platt", "isotonic"])
    parser.add_argument("--min-rows", type=int, default=1000)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    fit_patchtst_calibrator(
        scorer_artifact=args.scorer_artifact,
        out_path=args.out,
        panel_path=args.panel,
        raw_label_panel_path=args.raw_label_panel,
        label_col=args.label_col,
        er_label_col=args.er_label_col,
        allow_normalized_er_label=args.allow_normalized_er_label,
        data_start=args.data_start,
        data_end=args.data_end,
        batch_size=args.batch_size,
        method=args.method,
        min_rows=args.min_rows,
    )
    return 0


__all__ = ["fit_patchtst_calibrator"]


if __name__ == "__main__":
    raise SystemExit(main())
