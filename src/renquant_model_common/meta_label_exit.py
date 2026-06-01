"""Meta-label exit labeling and training CLIs."""
from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from renquant_common import PurgedKFold


log = logging.getLogger("renquant_model_common.meta_label_exit")

PATH_TRIGGER_COLUMNS: tuple[str, ...] = (
    "trigger_stop_loss",
    "trigger_trailing_stop",
    "trigger_single_day_loss",
    "trigger_max_hold",
)

FEATURE_COLUMNS: tuple[str, ...] = (
    "date", "ticker",
    "cum_pnl_pct", "peak_gain_pct", "drawdown_from_peak_pct",
    "days_held", "consec_underwater_days",
    "prev_day_return", "gap_open_pct", "realized_vol_20d",
    "spy_5d_ret", "spy_20d_ret", "spy_60d_ret",
    "spy_realized_vol_20d",
    "regime_code", "regime_just_switched", "regime_confidence",
    "panel_score_current", "panel_score_at_entry", "panel_score_delta",
    "panel_score_rank_among_holdings",
    "mu_current", "sigma_current",
    "position_weight", "sector_concentration",
    "portfolio_drawdown_now", "n_concurrent_exits_this_bar",
    "trigger_stop_loss", "trigger_trailing_stop",
    "trigger_single_day_loss", "trigger_max_hold",
    "any_trigger",
    "fwd_5d_ret", "fwd_20d_ret",
)


def apply_triple_barrier(
    close: pd.Series,
    *,
    entry_idx: pd.Timestamp,
    entry_price: float,
    pt_mult: float,
    sl_mult: float,
    sigma_daily: float,
    max_horizon_days: int,
    return_terminal_sign: bool = False,
) -> tuple[int, pd.Timestamp, float] | None:
    if entry_idx not in close.index:
        return None
    pos = close.index.get_loc(entry_idx)
    end_pos = min(pos + 1 + max_horizon_days, len(close))
    window = close.iloc[pos + 1:end_pos]
    if window.empty:
        return None
    upper = entry_price * (1.0 + pt_mult * sigma_daily) if pt_mult > 0 else float("inf")
    lower = entry_price * (1.0 - sl_mult * sigma_daily) if sl_mult > 0 else float("-inf")
    for hit_date, price in window.items():
        if not np.isfinite(price):
            continue
        if price >= upper:
            return 1, hit_date, float(price)
        if price <= lower:
            return -1, hit_date, float(price)
    terminal_date = window.index[-1]
    terminal_price = float(window.iloc[-1])
    if return_terminal_sign:
        delta = terminal_price - entry_price
        if delta > 0:
            return 1, terminal_date, terminal_price
        if delta < 0:
            return -1, terminal_date, terminal_price
    return 0, terminal_date, terminal_price


def _has_path_rule_trigger(row: pd.Series) -> bool:
    for col in PATH_TRIGGER_COLUMNS:
        try:
            if int(row.get(col, 0) or 0) == 1:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _resolve_sigma_daily(row: pd.Series, default_sigma_daily: float) -> float:
    value = row.get("realized_vol_20d", None)
    if value is None or not math.isfinite(float(value)) or float(value) == 0.0:
        return default_sigma_daily
    return float(value) / math.sqrt(252.0)


def _fwd_geometric_return(close: pd.Series, anchor: pd.Timestamp, window: int) -> float:
    if anchor not in close.index:
        return float("nan")
    pos = close.index.get_loc(anchor)
    if pos + window >= len(close):
        return float("nan")
    p0 = float(close.iloc[pos])
    p1 = float(close.iloc[pos + window])
    if not (math.isfinite(p0) and math.isfinite(p1)) or p0 <= 0:
        return float("nan")
    return p1 / p0 - 1.0


def label_snapshots(
    snapshot_df: pd.DataFrame,
    close_paths: Mapping[str, pd.Series],
    *,
    pt_mult: float = 10.0,
    sl_mult: float = 10.0,
    default_sigma_daily: float = 0.01,
    fwd_window: int = 20,
    fwd_short_window: int = 5,
) -> pd.DataFrame:
    out = snapshot_df.copy()
    for col in ("fwd_5d_ret", "fwd_20d_ret", "meta_label"):
        if col not in out.columns:
            out[col] = float("nan")
    if out.empty:
        return out
    out = out.reset_index(drop=True)
    for index, row in out.iterrows():
        ticker = str(row["ticker"]) if pd.notna(row.get("ticker")) else None
        date_value = row.get("date")
        if not ticker or pd.isna(date_value):
            continue
        close = close_paths.get(ticker)
        if close is None or close.empty:
            continue
        anchor = pd.Timestamp(date_value)
        if anchor not in close.index:
            continue
        out.at[index, "fwd_5d_ret"] = _fwd_geometric_return(close, anchor, fwd_short_window)
        out.at[index, "fwd_20d_ret"] = _fwd_geometric_return(close, anchor, fwd_window)
        try:
            any_trigger = int(row.get("any_trigger", 0) or 0)
        except (TypeError, ValueError):
            any_trigger = 0
        if any_trigger != 1 or not _has_path_rule_trigger(row):
            continue
        result = apply_triple_barrier(
            close,
            entry_idx=anchor,
            entry_price=float(close.loc[anchor]),
            pt_mult=pt_mult,
            sl_mult=sl_mult,
            sigma_daily=_resolve_sigma_daily(row, default_sigma_daily),
            max_horizon_days=fwd_window,
            return_terminal_sign=True,
        )
        if result is None:
            continue
        afml_label, _, _ = result
        out.at[index, "meta_label"] = 1 if afml_label == -1 else 0
    return out


def load_close_paths(tickers: list[str], data_dir: str | Path) -> dict[str, pd.Series]:
    root = Path(data_dir).expanduser().resolve() / "ohlcv"
    out: dict[str, pd.Series] = {}
    for ticker in tickers:
        path = root / ticker / "1d.parquet"
        if not path.exists():
            continue
        frame = pd.read_parquet(path)
        if "close" not in frame.columns:
            continue
        if "date" in frame.columns:
            index = pd.to_datetime(frame["date"])
        else:
            index = pd.to_datetime(frame.index)
        out[ticker] = pd.Series(pd.to_numeric(frame["close"], errors="coerce").to_numpy(), index=index)
    return out


def generate_meta_labels(
    *,
    snapshots: str | Path,
    out: str | Path,
    data_dir: str | Path,
    pt_mult: float = 10.0,
    sl_mult: float = 10.0,
    default_sigma_daily: float = 0.01,
    fwd_window: int = 20,
) -> dict[str, Any]:
    snapshots = Path(snapshots)
    frame = pd.read_parquet(snapshots)
    tickers = sorted(frame["ticker"].dropna().astype(str).unique())
    close_paths = load_close_paths(tickers, data_dir)
    labeled = label_snapshots(
        frame,
        close_paths=close_paths,
        pt_mult=pt_mult,
        sl_mult=sl_mult,
        default_sigma_daily=default_sigma_daily,
        fwd_window=fwd_window,
    )
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    labeled.to_parquet(out_path, index=False)
    return {
        "ok": True,
        "out": str(out_path),
        "rows": int(len(labeled)),
        "n_labeled": int(labeled["meta_label"].notna().sum()),
        "n_triggered": int(pd.to_numeric(labeled.get("any_trigger"), errors="coerce").fillna(0).sum()),
    }


def select_path_rule_training_events(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "meta_label" not in frame.columns:
        return frame.iloc[0:0].copy()
    work = frame[frame["meta_label"].notna()].copy()
    if work.empty:
        return work
    mask = pd.Series(False, index=work.index)
    for col in PATH_TRIGGER_COLUMNS:
        if col in work.columns:
            mask |= pd.to_numeric(work[col], errors="coerce").fillna(0).astype(int).eq(1)
    return work[mask].copy().reset_index(drop=True)


def feature_columns(frame: pd.DataFrame) -> list[str]:
    return [
        col for col in FEATURE_COLUMNS
        if col in frame.columns and col not in {"date", "ticker", "fwd_5d_ret", "fwd_20d_ret"}
    ]


def train_meta_label_xgb(
    *,
    labels: str | Path,
    out: str | Path,
    n_splits: int = 5,
    label_horizon_days: int = 20,
    pct_embargo: float = 0.01,
    max_depth: int = 4,
    learning_rate: float = 0.05,
    n_estimators: int = 200,
    subsample: float = 0.8,
    default_threshold: float = 0.5,
    min_events: int = 100,
) -> dict[str, Any]:
    import xgboost as xgb
    from sklearn.metrics import precision_score, recall_score, roc_auc_score

    raw = pd.read_parquet(labels)
    raw_labeled = int(raw["meta_label"].notna().sum()) if "meta_label" in raw.columns else 0
    frame = select_path_rule_training_events(raw)
    n_events = len(frame)
    if n_events < min_events:
        raise RuntimeError(f"Only {n_events} path-rule labelled events out of {raw_labeled}; need >= {min_events}")
    balance = float(frame["meta_label"].mean())
    cols = feature_columns(frame)
    frame["_event_dt"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("_event_dt").reset_index(drop=True)
    x = frame[cols].fillna(0.0).to_numpy(dtype=np.float64)
    y = frame["meta_label"].astype(int).to_numpy()

    embargo_days = int(round(max(0.0, pct_embargo) * frame["_event_dt"].nunique()))
    cv = PurgedKFold(
        n_splits=n_splits,
        embargo_days=max(0, embargo_days),
        lookahead_days=label_horizon_days,
    )
    aucs: list[float] = []
    precisions: list[float] = []
    recalls: list[float] = []
    oof_proba = np.full(len(x), np.nan)

    for train_idx, test_idx in cv.split(frame, date_col="_event_dt"):
        if len(train_idx) < 10 or len(test_idx) < 2 or len(set(y[train_idx])) < 2:
            continue
        clf = xgb.XGBClassifier(
            max_depth=max_depth,
            learning_rate=learning_rate,
            n_estimators=n_estimators,
            subsample=subsample,
            tree_method="hist",
            n_jobs=-1,
            random_state=42,
            eval_metric="auc",
        )
        clf.fit(x[train_idx], y[train_idx])
        proba = clf.predict_proba(x[test_idx])[:, 1]
        oof_proba[test_idx] = proba
        pred = (proba >= default_threshold).astype(int)
        try:
            aucs.append(float(roc_auc_score(y[test_idx], proba)))
        except Exception:  # noqa: BLE001
            aucs.append(float("nan"))
        precisions.append(float(precision_score(y[test_idx], pred, zero_division=0)))
        recalls.append(float(recall_score(y[test_idx], pred, zero_division=0)))
    if not aucs:
        raise RuntimeError("no CV folds produced metrics")

    threshold_table: list[dict[str, float]] = []
    mask = ~np.isnan(oof_proba)
    for threshold in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]:
        if not mask.any():
            continue
        pred = (oof_proba[mask] >= threshold).astype(int)
        precision = float(precision_score(y[mask], pred, zero_division=0))
        recall = float(recall_score(y[mask], pred, zero_division=0))
        f1 = 2 * precision * recall / max(precision + recall, 1e-9)
        threshold_table.append({"threshold": threshold, "precision": precision, "recall": recall, "f1": float(f1)})
    best_threshold = max(threshold_table, key=lambda row: row["f1"])["threshold"] if threshold_table else default_threshold

    final = xgb.XGBClassifier(
        max_depth=max_depth,
        learning_rate=learning_rate,
        n_estimators=n_estimators,
        subsample=subsample,
        tree_method="hist",
        n_jobs=-1,
        random_state=42,
        eval_metric="auc",
    )
    final.fit(x, y)
    booster = final.get_booster()
    importance = booster.get_score(importance_type="gain")
    importance_rows = []
    for key, gain in importance.items():
        try:
            name = cols[int(key.lstrip("f"))]
        except Exception:  # noqa: BLE001
            name = key
        importance_rows.append({"feature": name, "gain": float(gain)})
    importance_rows.sort(key=lambda row: -row["gain"])

    payload = {
        "version": 1,
        "kind": "meta_label_exit_xgb",
        "trained_date": pd.Timestamp.utcnow().date().isoformat(),
        "feature_cols": cols,
        "booster_raw_json": booster.save_raw(raw_format="json").decode("utf-8"),
        "default_threshold": float(best_threshold),
        "cv_metrics": {
            "auc_mean": float(np.nanmean(aucs)),
            "auc_std": float(np.nanstd(aucs)),
            "precision_at_05_mean": float(np.mean(precisions)),
            "recall_at_05_mean": float(np.mean(recalls)),
            "n_splits": int(n_splits),
            "threshold_sweep": threshold_table,
            "best_threshold_by_f1": float(best_threshold),
        },
        "feature_importance": importance_rows[:30],
        "training_data_summary": {
            "n_events": int(n_events),
            "n_raw_labeled_events": int(raw_labeled),
            "training_event_filter": "path_rule_triggers_only",
            "class_balance": balance,
            "fwd_window_days": int(label_horizon_days),
            "feature_count": len(cols),
        },
    }
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload), encoding="utf-8")
    return {"ok": True, "out": str(out_path), "n_events": int(n_events), "auc_mean": payload["cv_metrics"]["auc_mean"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate-labels")
    gen.add_argument("--snapshots", required=True)
    gen.add_argument("--out", required=True)
    gen.add_argument("--data-dir", type=Path, default=Path("data"))
    gen.add_argument("--pt-mult", type=float, default=10.0)
    gen.add_argument("--sl-mult", type=float, default=10.0)
    gen.add_argument("--default-sigma-daily", type=float, default=0.01)
    gen.add_argument("--fwd-window", type=int, default=20)
    gen.add_argument("--json", action="store_true")

    train = sub.add_parser("train")
    train.add_argument("--labels", required=True)
    train.add_argument("--out", required=True)
    train.add_argument("--n-splits", type=int, default=5)
    train.add_argument("--label-horizon-days", type=int, default=20)
    train.add_argument("--pct-embargo", type=float, default=0.01)
    train.add_argument("--max-depth", type=int, default=4)
    train.add_argument("--learning-rate", type=float, default=0.05)
    train.add_argument("--n-estimators", type=int, default=200)
    train.add_argument("--subsample", type=float, default=0.8)
    train.add_argument("--default-threshold", type=float, default=0.5)
    train.add_argument("--min-events", type=int, default=100)
    train.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    if args.command == "generate-labels":
        summary = generate_meta_labels(
            snapshots=args.snapshots,
            out=args.out,
            data_dir=args.data_dir,
            pt_mult=args.pt_mult,
            sl_mult=args.sl_mult,
            default_sigma_daily=args.default_sigma_daily,
            fwd_window=args.fwd_window,
        )
    else:
        summary = train_meta_label_xgb(
            labels=args.labels,
            out=args.out,
            n_splits=args.n_splits,
            label_horizon_days=args.label_horizon_days,
            pct_embargo=args.pct_embargo,
            max_depth=args.max_depth,
            learning_rate=args.learning_rate,
            n_estimators=args.n_estimators,
            subsample=args.subsample,
            default_threshold=args.default_threshold,
            min_events=args.min_events,
        )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
