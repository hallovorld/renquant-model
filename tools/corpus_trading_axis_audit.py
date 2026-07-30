#!/usr/bin/env python3
"""Re-derive a WF corpus's purge margin and label maturity ON THE TRADING AXIS.

renquant-pipeline#228, acceptance criterion 3. Both quantities have been
ASSERTED on this programme and both assertions were wrong:

  * a corpus manifest stamped ``all_purge_ok: true`` while the true margin was
    <= 0 on 30 of 43 folds (minimum -4), with 19 folds carrying real
    return-window overlap;
  * two sha256-pinned corpora were treated as label-verified while 9.6% of
    their score dates have a 60-TRADING-day forward window ending past the
    corpus's own last date.

Root cause of both: ``pd.offsets.BDay(n)`` and ``busday_count`` count BUSINESS
days and do not skip market holidays. Measured on SPY's real trading dates
2016-01-04 -> 2026-07-29 (2,597 cutoffs), ``BDay(60)`` falls BEFORE the true
60th trading day on 99.8% of cutoffs, short by mean 2.23 / median 2 / max 6
TRADING days.

A trap worth naming: ``BDay(60)`` spans exactly 12 weeks = 84 calendar days and
``ceil(60*7/5)`` is ALSO 84, so switching the unit alone fixes nothing.
Holidays are the whole defect. This tool therefore avoids calendar arithmetic
entirely and indexes the axis.

    python3 tools/corpus_trading_axis_audit.py \\
        --corpus <wf_scores.parquet> --axis <ohlcv>/SPY/1d.parquet --lookahead 60

READ-ONLY. Prints a report and exits non-zero if any check fails, so it is
usable as a gate rather than only as a script.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def load_axis(path: Path) -> pd.DatetimeIndex:
    """The trading-date axis, from a real price series. Never a calendar."""
    df = pd.read_parquet(path)
    idx = (df.index if isinstance(df.index, pd.DatetimeIndex)
           else pd.to_datetime(df["date"], errors="coerce"))
    return pd.DatetimeIndex(idx).dropna().sort_values().unique()


def nth_trading_day_after(axis: pd.DatetimeIndex, dates, n: int):
    """Exact: index the axis and step ``n`` positions. NaT where it runs off."""
    pos = axis.searchsorted(pd.DatetimeIndex(dates))
    return pd.Series(
        [axis[p + n] if 0 <= p + n < len(axis) else pd.NaT for p in pos],
        index=pd.DatetimeIndex(dates))


def audit(corpus: pd.DataFrame, axis: pd.DatetimeIndex, lookahead: int) -> dict:
    corpus = corpus.copy()
    corpus["date"] = pd.to_datetime(corpus["date"])
    out: dict = {"rows": len(corpus), "dates": corpus["date"].nunique(),
                 "span": (corpus["date"].min(), corpus["date"].max())}
    if "fold_idx" in corpus:
        out["folds"] = int(corpus["fold_idx"].nunique())

    # 1. score dates must fall strictly after their own fold cutoff
    if "cutoff" in corpus:
        corpus["cutoff"] = pd.to_datetime(corpus["cutoff"])
        out["rows_at_or_before_cutoff"] = int((corpus["date"] <= corpus["cutoff"]).sum())

    # 2. label maturity: the lookahead-th trading day after each score date must
    #    be inside the corpus's own span, or the corpus cannot verify its label
    uniq = pd.DatetimeIndex(sorted(corpus["date"].unique()))
    fwd_end = nth_trading_day_after(axis, uniq, lookahead)
    last = corpus["date"].max()
    unverifiable = fwd_end[(fwd_end.isna()) | (fwd_end > last)]
    out["n_dates"] = len(uniq)
    out["n_unverifiable_dates"] = len(unverifiable)
    out["frac_unverifiable"] = len(unverifiable) / max(len(uniq), 1)
    out["first_unverifiable"] = (unverifiable.index.min()
                                 if len(unverifiable) else None)
    out["needs_data_through"] = (fwd_end.get(out["first_unverifiable"])
                                 if out["first_unverifiable"] is not None else None)

    # 3. how far short a BDay bound would have been, on this corpus's own dates
    bd = pd.DatetimeIndex(uniq) + pd.offsets.BDay(lookahead)
    true_end = nth_trading_day_after(axis, uniq, lookahead)
    ok = true_end.notna()
    if ok.any():
        # `.astype("timedelta64[D]")` is rejected on newer pandas; divide instead.
        delta = pd.TimedeltaIndex(true_end[ok].values - bd[ok.values])
        short_cal = (delta / pd.Timedelta(days=1)).to_numpy().astype(int)
        out["bday_short_cal_mean"] = float(short_cal.mean())
        out["bday_short_cal_max"] = int(short_cal.max())
        out["bday_short_frac"] = float((short_cal > 0).mean())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", required=True, type=Path)
    ap.add_argument("--axis", required=True, type=Path,
                    help="a real price series, e.g. <ohlcv>/SPY/1d.parquet")
    ap.add_argument("--lookahead", type=int, default=60,
                    help="label horizon in TRADING days")
    ap.add_argument("--max-unverifiable-frac", type=float, default=0.0,
                    help="gate: fail above this fraction of unverifiable dates")
    a = ap.parse_args(argv)

    axis = load_axis(a.axis)
    r = audit(pd.read_parquet(a.corpus), axis, a.lookahead)
    print(f"corpus: {a.corpus.name}")
    print(f"  rows={r['rows']} dates={r['n_dates']} "
          f"folds={r.get('folds', '-')} "
          f"span={r['span'][0].date()} -> {r['span'][1].date()}")
    print(f"  axis: {len(axis)} trading days from {a.axis}")
    if "rows_at_or_before_cutoff" in r:
        print(f"  rows with score_date <= own cutoff: {r['rows_at_or_before_cutoff']}")
    print(f"  label maturity, {a.lookahead} TRADING days:")
    print(f"    unverifiable score dates: {r['n_unverifiable_dates']}/{r['n_dates']} "
          f"= {r['frac_unverifiable']:.1%}")
    if r["first_unverifiable"] is not None:
        print(f"    earliest: {r['first_unverifiable'].date()} — its label needs "
              f"data through {r['needs_data_through'].date()}")
        print("    NOTE: unverifiable != immature. The label may be complete in the "
              "panel; the CORPUS cannot establish it. Do not describe such a "
              "corpus as label-verified.")
    if "bday_short_cal_mean" in r:
        print(f"  a BDay({a.lookahead}) bound on these dates would be SHORT on "
              f"{r['bday_short_frac']:.1%} of them, by mean "
              f"{r['bday_short_cal_mean']:+.2f} / max {r['bday_short_cal_max']:+d} "
              f"calendar days")
    failed = []
    if r.get("rows_at_or_before_cutoff", 0) > 0:
        failed.append("score dates at or before their own cutoff")
    if r["frac_unverifiable"] > a.max_unverifiable_frac:
        failed.append(f"unverifiable label fraction {r['frac_unverifiable']:.1%} > "
                      f"{a.max_unverifiable_frac:.1%}")
    if failed:
        print("\nFAIL: " + "; ".join(failed))
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
