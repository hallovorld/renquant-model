#!/usr/bin/env python3
"""Re-derive a WF corpus's cutoff sanity and label maturity ON THE TRADING AXIS.

renquant-pipeline#228, acceptance criterion 3. This script checks two things
on a WF score corpus, given its own date axis:

  * no score date falls at or before its own fold's cutoff;
  * every score date's ``lookahead``-TRADING-day forward window ends inside
    the corpus's own span — else the corpus cannot establish that label.

SCOPE: this script does NOT compute a per-fold purge margin (train/cutoff
boundary vs. the next fold's start). That is a distinct, unimplemented
measurement — see renquant-pipeline#228 for its own prior finding on that
question. Do not read this tool's cutoff check as a substitute for it.

Root cause of the label-maturity defect: ``pd.offsets.BDay(n)`` and
``busday_count`` count BUSINESS days and do not skip market holidays, so a
window computed with either one lands before the true nth TRADING day
whenever a market holiday falls inside it — which happens often enough on
SPY's real trading-date history to matter. (This tool does not quote a
standalone SPY-axis-wide mean/median/max for that shortfall — the
mean/median/max are unit-dependent, ``short by n days`` differs under a
TRADING-day vs. calendar-day count, and no committed evidence log backs
either. See ``doc/research/evidence/2026-07-30-corpus-trading-axis-audit.md``
for the two numbers this tool DOES measure and back with a replay log: the
per-corpus unverifiable fraction and the per-corpus BDay-vs-axis shortfall.)

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
    """Exact: index the axis and step ``n`` positions. NaT where it runs off.

    Raises ``ValueError`` if any ``date`` is not itself on the axis.
    ``searchsorted`` returns an insertion point for an off-axis date (e.g. a
    weekend or holiday), which would silently treat it as the next trading
    session instead of failing on a malformed corpus.
    """
    idx = pd.DatetimeIndex(dates)
    off_axis = idx[~idx.isin(axis)]
    if len(off_axis):
        raise ValueError(
            f"{len(off_axis)} date(s) not on the trading axis (e.g. a weekend "
            f"or holiday): {sorted(off_axis.unique())[:5]}")
    pos = axis.searchsorted(idx)
    return pd.Series(
        [axis[p + n] if 0 <= p + n < len(axis) else pd.NaT for p in pos],
        index=idx)


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
