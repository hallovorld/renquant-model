#!/usr/bin/env python3
"""What is `fwd_60d_excess` in the production panel, actually? (GOAL-4 / GOAL-6)

Written because I was about to preregister a consensus study whose estimand was a
"top-decile spread in excess return", and the column that name points at is **not an
excess return**.

MEASURED 2026-08-01 on `RenQuant/data/alpha158_291_fundamental_dataset.parquet`
`[本次实测]`:

  * **2 599 of 2 599 dates** have `mean = 0` and `std = 1` — worst deviations `7.7e-17`
    and `1.2e-11`. The column is a **PER-DATE CROSS-SECTIONAL Z-SCORE**.
  * **0 nulls** anywhere, including on dates whose 60-trading-day forward window has not
    elapsed.

TWO CONSEQUENCES FOR ANY STUDY BUILT ON IT.

1. **No quantity in return units can be read off it.** A "top-decile spread" computed here
   is a spread in standard deviations of that date's cross-section, not basis points, and
   it cannot be summed, annualised, or compared to a cost. Reporting it as a return is the
   unit error this file exists to prevent.
2. **The label is present past the rawlabel frontier.** The rawlabel corpus stops at
   2026-04-28; the panel carries labels for **5 further dates** (2026-04-29 … 2026-05-05,
   **723 rows**). A per-date z-score is computable from any values, so its presence says
   nothing about whether the underlying 60-day window has elapsed.

WHAT THIS DOES **NOT** ESTABLISH. That the past-frontier labels are wrong. They may be
computed from data this file does not read, and the lockstep guard already refuses to
certify a rawlabel corpus against that tail. What is established is narrower and enough: a
study must not treat those rows as realised without checking, and must not treat any row's
label as a return.

Read-only.

Exit codes: ``0`` the column matches the z-score contract, ``1`` it does not, ``2``
usage/IO error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LABEL = "fwd_60d_excess"
TOL_MEAN = 1e-9
TOL_STD = 1e-6


def survey(panel: Path, label: str, frontier: str | None) -> dict:
    import pandas as pd  # noqa: PLC0415
    df = pd.read_parquet(panel, columns=["date", "ticker", label])
    df["date"] = pd.to_datetime(df["date"])
    g = df.groupby("date")[label]
    mean, std = g.mean(), g.std()
    n_dates = len(mean)
    ok_mean = int((mean.abs() <= TOL_MEAN).sum())
    ok_std = int(((std - 1).abs() <= TOL_STD).sum())
    out = {
        "panel": str(panel), "label": label,
        "n_rows": int(len(df)), "n_dates": n_dates,
        "n_nulls": int(df[label].isna().sum()),
        "dates_with_zero_mean": ok_mean,
        "dates_with_unit_std": ok_std,
        "worst_abs_mean": float(mean.abs().max()),
        "worst_abs_std_minus_one": float((std - 1).abs().max()),
        "is_per_date_zscore": ok_mean == n_dates and ok_std == n_dates,
    }
    if frontier:
        f = pd.Timestamp(frontier)
        past = [str(pd.Timestamp(x).date()) for x in mean.index if x > f]
        out["frontier"] = frontier
        out["dates_past_frontier"] = past
        out["rows_past_frontier"] = int((df["date"] > f).sum())
    out["not_established"] = (
        "That labels past the frontier are WRONG. A per-date z-score is computable from "
        "any values, so its presence says nothing about whether the 60-day window has "
        "elapsed — but neither does it show the row is unrealised. Check before using.")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--panel", required=True, type=Path)
    ap.add_argument("--label", default=LABEL)
    ap.add_argument("--frontier", default=None,
                    help="rawlabel corpus max date, to report rows beyond it")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        rep = survey(a.panel, a.label, a.frontier)
    except (OSError, ValueError, KeyError, ImportError) as exc:
        print(f"label-contract: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    else:
        print(f"  {Path(rep['panel']).name}  column {rep['label']!r}")
        print(f"    rows {rep['n_rows']:,}  dates {rep['n_dates']}  nulls {rep['n_nulls']}")
        print(f"    per-date mean==0 on {rep['dates_with_zero_mean']}/{rep['n_dates']}"
              f"   std==1 on {rep['dates_with_unit_std']}/{rep['n_dates']}")
        print(f"    worst |mean|={rep['worst_abs_mean']:.3e}  "
              f"worst |std-1|={rep['worst_abs_std_minus_one']:.3e}")
        print(f"    => PER-DATE Z-SCORE: {rep['is_per_date_zscore']}"
              f"  (so it is NOT a return; no bps may be read off it)")
        if "dates_past_frontier" in rep:
            print(f"    labels past frontier {rep['frontier']}: "
                  f"{len(rep['dates_past_frontier'])} date(s), "
                  f"{rep['rows_past_frontier']} rows  {rep['dates_past_frontier']}")
        print(f"\n  [not established] {rep['not_established']}")
    return 0 if rep["is_per_date_zscore"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
