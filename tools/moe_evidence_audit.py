"""Read-only evidence audit for the panel/classifier MoE question.

The audit deliberately evaluates every score against the production panel's
``fwd_60d_excess`` label.  The classifier's stored label is retained only to
measure label-vintage differences, never used as a second outcome.  This keeps
the comparison on one fixed estimand.

It is an exploratory audit, not a model-selection or promotion runner:
the score corpora were available before this script existed.  The script writes
only a compact JSON report and never writes model or production-data artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLF = (
    REPO_ROOT
    / "doc/research/data/2026-08-01-clf-wf-lineage-bundle/clf_wf_scores.parquet"
)
DEFAULT_OUTPUT = REPO_ROOT / "doc/research/data/2026-08-08-moe-evidence-audit.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def block_summary(values: pd.Series, block_size: int) -> dict[str, float | int]:
    """Summarize complete chronological blocks; discard a partial final block."""
    values = values.dropna().astype(float).reset_index(drop=True)
    n_blocks = len(values) // block_size
    if n_blocks < 2:
        raise ValueError("need at least two complete blocks for a block summary")
    used = values.iloc[: n_blocks * block_size]
    blocks = used.groupby(np.arange(len(used)) // block_size).mean()
    standard_error = float(blocks.std(ddof=1) / np.sqrt(n_blocks))
    return {
        "block_size_dates": block_size,
        "n_blocks": int(n_blocks),
        "n_dates_used": int(len(used)),
        "n_dates_dropped": int(len(values) - len(used)),
        "mean": float(blocks.mean()),
        "block_standard_error": standard_error,
        "descriptive_t": float(blocks.mean() / standard_error)
        if standard_error > 0
        else float("nan"),
    }


def _date_metrics(group: pd.DataFrame, top_n: int) -> pd.Series:
    if len(group) < 30:
        return pd.Series(dtype=float)
    ranks = group[["panel", "clf", "label"]].rank(method="average", pct=True)
    equal_blend = (ranks["panel"] + ranks["clf"]) / 2.0

    def corr(left: pd.Series, right: pd.Series) -> float:
        return float(left.corr(right))

    return pd.Series(
        {
            "n_names": len(group),
            "ic_panel": corr(ranks["panel"], ranks["label"]),
            "ic_clf": corr(ranks["clf"], ranks["label"]),
            "ic_equal_blend": corr(equal_blend, ranks["label"]),
            "rank_corr_panel_clf": corr(ranks["panel"], ranks["clf"]),
            "top_n_panel": float(
                group.loc[ranks["panel"].nlargest(top_n).index, "label"].mean()
            ),
            "top_n_clf": float(
                group.loc[ranks["clf"].nlargest(top_n).index, "label"].mean()
            ),
            "top_n_equal_blend": float(
                group.loc[equal_blend.nlargest(top_n).index, "label"].mean()
            ),
        }
    )


def build_report(panel_path: Path, clf_path: Path, block_size: int, top_n: int) -> dict[str, Any]:
    panel = pd.read_parquet(panel_path)[["date", "name", "score", "fwd_60d_excess"]]
    panel = panel.rename(
        columns={"name": "ticker", "score": "panel", "fwd_60d_excess": "label"}
    )
    clf = pd.read_parquet(clf_path)[["date", "ticker", "raw", "fwd_60d_excess"]]
    clf = clf.rename(columns={"raw": "clf", "fwd_60d_excess": "label_clf"})
    for frame in (panel, clf):
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        frame["ticker"] = frame["ticker"].astype(str)

    joined = panel.merge(clf, on=["date", "ticker"], how="inner")
    joined = joined.dropna(subset=["panel", "clf", "label", "label_clf"])
    joined = joined.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)
    if joined.empty:
        raise ValueError("panel and classifier corpora have no common labeled rows")

    label_abs_diff = (joined["label"] - joined["label_clf"]).abs()
    daily = (
        joined.groupby("date", sort=True, group_keys=False)
        .apply(_date_metrics, top_n=top_n, include_groups=False)
        .dropna()
        .sort_index()
    )
    if daily.empty:
        raise ValueError("no common date has the minimum 30-name cross-section")
    for arm in ("clf", "equal_blend"):
        daily[f"delta_ic_{arm}"] = daily[f"ic_{arm}"] - daily["ic_panel"]
        daily[f"delta_top_n_{arm}"] = daily[f"top_n_{arm}"] - daily["top_n_panel"]

    metrics: dict[str, Any] = {}
    for arm in ("clf", "equal_blend"):
        metrics[arm] = {
            "mean_delta_ic": float(daily[f"delta_ic_{arm}"].mean()),
            "mean_delta_top_n_label": float(daily[f"delta_top_n_{arm}"].mean()),
            "delta_ic_blocks": block_summary(daily[f"delta_ic_{arm}"], block_size),
            "delta_top_n_label_blocks": block_summary(
                daily[f"delta_top_n_{arm}"], block_size
            ),
        }

    return {
        "schema": "moe-evidence-audit-v1",
        "purpose": "exploratory evidence audit; not a promotion or selection result",
        "inputs": {
            "panel_path": str(panel_path),
            "panel_sha256": sha256(panel_path),
            "classifier_path": str(clf_path),
            "classifier_sha256": sha256(clf_path),
            "evaluation_label": "panel fwd_60d_excess only",
        },
        "comparison_contract": {
            "arms": ["panel", "classifier", "equal_weight_rank_blend"],
            "free_parameters": 0,
            "top_n": top_n,
            "date_metric": "cross-sectional Spearman IC and mean panel-label outcome of top-N",
            "inference": (
                "complete non-overlapping chronological blocks; descriptive only; "
                "no pass/fail rule, no selection, no cost or turnover model"
            ),
        },
        "coverage": {
            "n_rows": int(len(joined)),
            "n_dates": int(len(daily)),
            "date_min": daily.index.min().date().isoformat(),
            "date_max": daily.index.max().date().isoformat(),
            "mean_names_per_date": float(daily["n_names"].mean()),
        },
        "label_vintage_difference": {
            "spearman": float(joined[["label", "label_clf"]].corr(method="spearman").iloc[0, 1]),
            "mean_absolute_difference": float(label_abs_diff.mean()),
            "max_absolute_difference": float(label_abs_diff.max()),
            "n_material_difference_gt_1pct": int((label_abs_diff > 0.01).sum()),
            "share_material_difference_gt_1pct": float((label_abs_diff > 0.01).mean()),
        },
        "daily_means": {
            key: float(daily[key].mean())
            for key in (
                "ic_panel",
                "ic_clf",
                "ic_equal_blend",
                "rank_corr_panel_clf",
                "top_n_panel",
                "top_n_clf",
                "top_n_equal_blend",
            )
        },
        "incremental_results": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True, help="panel OOS parquet")
    parser.add_argument("--classifier", type=Path, default=DEFAULT_CLF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--block-size", type=int, default=60)
    parser.add_argument("--top-n", type=int, default=3)
    args = parser.parse_args()
    report = build_report(args.panel, args.classifier, args.block_size, args.top_n)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
