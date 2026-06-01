"""Fit calibrators for alpha158 linear panel scorers."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from renquant_model_common.global_calibrator import fit_global_calibrator

from .scorer import PanelLinearScorer

log = logging.getLogger("renquant_model_alpha158_linear.calibrator")

DEFAULT_PANEL_FILENAME = "alpha158_qlib_dataset.parquet"
DEFAULT_RAW_LABEL_PANEL_FILENAME = "transformer_dataset_engineered.parquet"
DEFAULT_LABEL = "fwd_5d_excess"


def fit_alpha158_linear_calibrator(
    *,
    data_dir: str | Path,
    scorer_artifact: str | Path,
    out_path: str | Path,
    dataset: str | Path | None = None,
    raw_label_panel: str | Path | None = None,
    label_col: str = DEFAULT_LABEL,
    method: str = "isotonic",
    lookahead_days: int = 5,
    threshold: float = 0.0,
    min_rows: int = 1000,
    allow_normalized_er_label: bool = False,
) -> Path:
    data_dir = Path(data_dir).expanduser().resolve()
    dataset = Path(dataset).expanduser().resolve() if dataset else data_dir / DEFAULT_PANEL_FILENAME
    raw_label_panel = (
        Path(raw_label_panel).expanduser().resolve()
        if raw_label_panel
        else data_dir / DEFAULT_RAW_LABEL_PANEL_FILENAME
    )
    scorer_artifact = Path(scorer_artifact).expanduser().resolve()
    out_path = Path(out_path).expanduser().resolve()

    panel = pd.read_parquet(dataset)
    panel["date"] = pd.to_datetime(panel["date"])
    scorer = PanelLinearScorer.load_path(scorer_artifact)
    feat_cols = scorer.feature_cols

    if raw_label_panel.exists():
        raw_panel = pd.read_parquet(raw_label_panel, columns=["ticker", "date", label_col])
        raw_panel["date"] = pd.to_datetime(raw_panel["date"])
        if label_col in panel.columns:
            panel = panel.drop(columns=[label_col])
        panel = panel.merge(raw_panel, on=["ticker", "date"], how="inner", validate="many_to_one")
    elif not allow_normalized_er_label:
        raise FileNotFoundError(f"raw-label panel is required for expected-return units: {raw_label_panel}")
    elif label_col not in panel.columns:
        raise KeyError(f"label column not found in normalized panel: {label_col}")

    panel["raw_score"] = scorer.score(panel[feat_cols])
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)

    panel_scores: dict[str, pd.Series] = {}
    future_returns: dict[str, pd.Series] = {}
    for ticker, group in panel.groupby("ticker"):
        group = group.sort_values("date")
        scores = pd.Series(group["raw_score"].values, index=group["date"], name=str(ticker))
        rets = pd.Series(group[label_col].values, index=group["date"], name=str(ticker))
        valid = (~scores.isna()) & (~rets.isna())
        if valid.sum() == 0:
            continue
        panel_scores[str(ticker)] = scores[valid]
        future_returns[str(ticker)] = rets[valid]

    calib = fit_global_calibrator(
        panel_scores,
        future_returns,
        lookahead_days=int(lookahead_days),
        threshold=float(threshold),
        threshold_mode="absolute",
        method=method,
        min_rows=int(min_rows),
    )
    metadata = {
        "scorer_artifact": str(scorer_artifact),
        "scorer_kind": "panel_linear",
        "scorer_train_ic": scorer.metadata.get("training_train_ic"),
        "scorer_test_ic": scorer.metadata.get("test_mean_ic"),
        "expected_return_label_col": label_col,
        "expected_return_label_source": str(raw_label_panel) if raw_label_panel.exists() else str(dataset),
        "expected_return_label_contract": "raw_return_units_required",
        "method": method,
    }
    calib.save(out_path, metadata=metadata)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--raw-label-panel", type=Path, default=None)
    parser.add_argument("--scorer-artifact", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label-col", default=DEFAULT_LABEL)
    parser.add_argument("--method", default="isotonic", choices=["isotonic", "platt"])
    parser.add_argument("--lookahead", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.0)
    parser.add_argument("--min-rows", type=int, default=1000)
    parser.add_argument("--allow-normalized-er-label", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    fit_alpha158_linear_calibrator(
        data_dir=args.data_dir,
        dataset=args.dataset,
        raw_label_panel=args.raw_label_panel,
        scorer_artifact=args.scorer_artifact,
        out_path=args.out,
        label_col=args.label_col,
        method=args.method,
        lookahead_days=args.lookahead,
        threshold=args.threshold,
        min_rows=args.min_rows,
        allow_normalized_er_label=args.allow_normalized_er_label,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
