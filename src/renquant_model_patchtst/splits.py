"""PatchTST split helpers backed by the canonical walk-forward splitter."""
from __future__ import annotations

import pandas as pd

from renquant_common.walk_forward_splits import (
    WalkForwardCut,
    assign_split_column,
    build_default_cuts,
)

DEFAULT_ALL_VAL_TAIL_PCT = 0.10
SPLITTER_IMPLEMENTATION = "renquant_common.walk_forward_splits.assign_split_column"


def build_all_tail_cut(
    panel: pd.DataFrame,
    *,
    val_tail_pct: float = DEFAULT_ALL_VAL_TAIL_PCT,
    date_col: str = "date",
) -> WalkForwardCut:
    """Build a synthetic full-data tail-validation cut for ``assign_split_column``."""
    if not 0.0 < float(val_tail_pct) < 1.0:
        raise ValueError(f"val_tail_pct must be in (0, 1), got {val_tail_pct!r}")
    dates = pd.to_datetime(panel[date_col]).dropna().sort_values().unique()
    if len(dates) < 2:
        raise ValueError("tail validation split requires at least two dates")
    n_val = max(1, int(len(dates) * float(val_tail_pct)))
    if n_val >= len(dates):
        raise ValueError(
            "tail validation split would leave no pre-validation dates; "
            f"n_dates={len(dates)} val_tail_pct={val_tail_pct}"
        )
    val_start = pd.Timestamp(dates[-n_val])
    val_end = pd.Timestamp(dates[-1]) + pd.offsets.BDay(1)
    return WalkForwardCut(
        name="all",
        train_start=pd.Timestamp(dates[0]),
        train_end=val_start,
        val_start=val_start,
        val_end=val_end,
    )


def assign_patchtst_split(
    panel: pd.DataFrame,
    cut_name: str,
    *,
    embargo_days: int,
    val_tail_pct: float = DEFAULT_ALL_VAL_TAIL_PCT,
    date_col: str = "date",
) -> pd.Series:
    """Assign train/embargo/val/test labels through the common splitter."""
    if cut_name == "all":
        if float(val_tail_pct) <= 0.0:
            return pd.Series("train", index=panel.index, dtype="object")
        cut = build_all_tail_cut(panel, val_tail_pct=val_tail_pct, date_col=date_col)
    else:
        cuts = {cut.name: cut for cut in build_default_cuts()}
        if cut_name not in cuts:
            raise ValueError(f"unknown cut {cut_name!r}; known: {sorted(cuts)}")
        cut = cuts[cut_name]
    return assign_split_column(
        panel,
        cut,
        date_col=date_col,
        embargo_days=embargo_days,
    )
