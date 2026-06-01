"""Train alpha158 plus sklearn LinearRegression/Ridge panel scorers."""
from __future__ import annotations

import argparse
from datetime import date
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .scorer import PanelLinearScorer

log = logging.getLogger("renquant_model_alpha158_linear.trainer")

DEFAULT_PANEL_FILENAME = "alpha158_qlib_dataset.parquet"
DEFAULT_LABEL = "fwd_5d_excess"
LABEL_COLUMNS = {"fwd_5d_excess", "fwd_20d_excess", "fwd_60d_excess"}
EXCLUDED_COLUMNS = {"ticker", "date", "split_label", *LABEL_COLUMNS}


def per_day_ic(preds: np.ndarray, labels: np.ndarray, dates: np.ndarray) -> tuple[float, float]:
    frame = pd.DataFrame({"pred": preds, "label": labels, "date": dates})
    ics: list[float] = []
    for _, group in frame.groupby("date"):
        if len(group) < 5:
            continue
        rho, _ = spearmanr(group["pred"], group["label"])
        if not np.isnan(rho):
            ics.append(float(rho))
    if not ics:
        return 0.0, 0.0
    return float(np.mean(ics)), float(np.median(ics))


def train_panel_linear(
    *,
    dataset: str | Path,
    output: str | Path,
    label: str = DEFAULT_LABEL,
    estimator: str = "ols",
    alpha: float = 1.0,
    train_end_date: str | None = None,
    val_days: int = 20,
) -> Path:
    dataset = Path(dataset).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    panel = pd.read_parquet(dataset).dropna(subset=[label]).copy()
    panel["date"] = pd.to_datetime(panel["date"])
    feat_cols = [col for col in panel.columns if col not in EXCLUDED_COLUMNS]
    if not feat_cols:
        raise ValueError(f"no feature columns found in {dataset}")

    if train_end_date is not None:
        train_end = pd.Timestamp(train_end_date)
        val_start = train_end - pd.Timedelta(days=int(val_days))
        train = panel[panel["date"] <= val_start]
        val = panel[(panel["date"] > val_start) & (panel["date"] <= train_end)]
        test = panel[panel["date"] > train_end]
    else:
        train = panel[panel["split_label"] == "train"]
        val = panel[panel["split_label"] == "val"]
        test = panel[panel["split_label"] == "test"]
    if train.empty:
        raise ValueError("training split is empty")

    stats_path = dataset.with_suffix(".stats.json")
    if stats_path.exists():
        sidecar = json.loads(stats_path.read_text(encoding="utf-8"))
        stats_cols = list(sidecar["feature_cols"])
        col_to_idx = {col: idx for idx, col in enumerate(stats_cols)}
        feature_means = np.array([sidecar["feature_means"][col_to_idx[col]] for col in feat_cols], dtype=float)
        feature_stds = np.array([sidecar["feature_stds"][col_to_idx[col]] for col in feat_cols], dtype=float)
    else:
        log.warning("stats sidecar missing at %s; using training-panel stats", stats_path)
        feature_means = train[feat_cols].mean().values.astype(float)
        feature_stds = train[feat_cols].std().values.astype(float)

    from sklearn.linear_model import LinearRegression, Ridge  # noqa: PLC0415

    if estimator == "ridge":
        model = Ridge(alpha=float(alpha), fit_intercept=False, copy_X=False)
    elif estimator == "ols":
        model = LinearRegression(fit_intercept=False, copy_X=False)
    else:
        raise ValueError(f"unknown estimator: {estimator!r}")
    model.fit(train[feat_cols].values, train[label].values)

    scorer = PanelLinearScorer.from_sklearn(
        model,
        feature_cols=feat_cols,
        feature_means=feature_means,
        feature_stds=feature_stds,
        metadata={
            "trained_date": str(date.today()),
            "label": label,
            "estimator": estimator,
            "alpha_l2": float(alpha) if estimator == "ridge" else 0.0,
            "n_train_rows": int(len(train)),
            "panel_shape": {
                "rows": int(len(panel)),
                "tickers": int(panel["ticker"].nunique()),
                "dates": int(panel["date"].nunique()),
            },
        },
    )

    train_preds = scorer.score(train[feat_cols])
    train_mean_ic, train_median_ic = per_day_ic(train_preds.values, train[label].values, train["date"].values)
    scorer.metadata["training_train_ic"] = train_mean_ic

    if len(val):
        val_preds = scorer.score(val[feat_cols])
        val_mean_ic, val_median_ic = per_day_ic(val_preds.values, val[label].values, val["date"].values)
    else:
        val_mean_ic = val_median_ic = None
    if len(test):
        test_preds = scorer.score(test[feat_cols])
        test_mean_ic, test_median_ic = per_day_ic(test_preds.values, test[label].values, test["date"].values)
    else:
        test_mean_ic = test_median_ic = None

    scorer.metadata.update(
        {
            "training_train_median_ic": train_median_ic,
            "val_mean_ic": val_mean_ic,
            "val_median_ic": val_median_ic,
            "test_mean_ic": test_mean_ic,
            "test_median_ic": test_median_ic,
            "oos_mean_ic": test_mean_ic,
        }
    )
    scorer.save(output)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, default=Path("data") / DEFAULT_PANEL_FILENAME)
    parser.add_argument("--label", default=DEFAULT_LABEL, choices=sorted(LABEL_COLUMNS))
    parser.add_argument("--estimator", default="ols", choices=["ols", "ridge"])
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-end-date", default=None)
    parser.add_argument("--val-days", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    train_panel_linear(
        dataset=args.dataset,
        output=args.output,
        label=args.label,
        estimator=args.estimator,
        alpha=args.alpha,
        train_end_date=args.train_end_date,
        val_days=args.val_days,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
