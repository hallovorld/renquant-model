#!/usr/bin/env python
"""Regenerate ``smoke_panel.parquet`` + ``smoke_spy.parquet`` — the
Phase A.0 smoke fixtures committed at ``tests/data/``.

Phase A.0 (per ``docs/patchtst_capability_research_proposal.md``) is the
first kill-gate experiment in the research plan: real-vs-placebo IC must
separate cleanly on a known-clean fixture before any wider sweep runs.

The fixtures here let the smoke run in CI / on CPU in seconds, without
the umbrella's full 346k-row real panel. They also serve as the test
substrate for asserting the data pipeline contract (csrank_norm, winsor
bounds, train/val split, placebo mutations) holds under the same
``ExperimentPipeline`` machinery that production runs use.

Design constraints (so the fixture exercises the gate non-trivially):

  1. Real label has a learnable signal — one feature linearly drives
     the label. A trained ranker should achieve val IC > 0.
  2. Other features are pure noise. Confirms that the model
     discriminates signal from noise, not just memorizes labels.
  3. Shuffle-label placebo must give val IC ≈ 0. Confirms the placebo
     actually breaks the signal channel.
  4. Time-shift placebo MUST keep train labels within the train split
     after the PR #9 cross-split-leak fix. Synthetic SPY covers the
     date range so the regime contract task has data.
  5. Small enough that the full Phase A.0 (1 cut × 1 seed × placebos)
     runs in < 5 minutes on CPU.

Seed is pinned so the fixture is reproducible across platforms and CI.

Run from the renquant-model repo root::

    PYTHONPATH=src python tests/data/_regen_smoke_panel.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260531
N_DATES = 200            # ~10 months of business days
N_TICKERS = 12           # cross-sectional ranker needs enough per-day cohort
LABEL_COL = "fwd_5d_excess"
LOOKAHEAD_DAYS = 5       # short horizon → quick label maturation
START_DATE = "2024-01-02"

# Feature design — one signal column, rest noise. The signal-to-label
# relationship is intentionally mild (rho ~ 0.15-0.25 cross-sectionally
# per day) so the model has to actually learn, not memorize.
N_NOISE_FEATURES = 8
SIGNAL_FEATURE = "alpha_signal"
NOISE_FEATURES = [f"noise_{i:02d}" for i in range(N_NOISE_FEATURES)]
ALL_FEATURES = [SIGNAL_FEATURE, *NOISE_FEATURES]
SIGNAL_TO_LABEL_BETA = 0.6   # per-day OLS slope; cross-sectional noise σ=1


def regen_panel(out_path: Path) -> Path:
    """Build the smoke panel (multi-ticker, multi-date, signal+noise+label)."""
    rng = np.random.default_rng(SEED)
    dates = pd.bdate_range(START_DATE, periods=N_DATES)
    tickers = [f"T{i:02d}" for i in range(N_TICKERS)]

    rows: list[dict] = []
    for d in dates:
        # Each ticker draws its own (signal, noise...) cross-section per day.
        signal = rng.standard_normal(N_TICKERS)
        # Label = beta * signal + cross-sectional Gaussian noise. The noise σ
        # is chosen so per-day Spearman(signal, label) is positive but well
        # below 1.0 — a learnable but not trivial signal.
        label_noise = rng.standard_normal(N_TICKERS) * 1.0
        label = SIGNAL_TO_LABEL_BETA * signal + label_noise
        noise = rng.standard_normal((N_TICKERS, N_NOISE_FEATURES))
        for i, ticker in enumerate(tickers):
            row = {
                "date": d,
                "ticker": ticker,
                SIGNAL_FEATURE: float(signal[i]),
                LABEL_COL: float(label[i]),
            }
            for j, fname in enumerate(NOISE_FEATURES):
                row[fname] = float(noise[i, j])
            rows.append(row)

    df = pd.DataFrame(rows)
    # Sort by (ticker, date) so the sequence builder picks up the right
    # chronological windows per ticker — matches load_panel_with_split.
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return out_path


def regen_spy(out_path: Path) -> Path:
    """Build a synthetic SPY OHLCV covering the smoke panel date range.

    The HMM detector needs at least 30 days of SPY history before it
    emits regime labels (bootstrap window). We build a slightly wider
    range than the panel + a calm bull profile so the v2026-05-31
    detector labels the period as BULL_CALM (panel period is
    'all'-cut, doesn't need a specific regime, but the SPY parquet
    must exist for the trainer's PerRegimeICCallback to wire).
    """
    rng = np.random.default_rng(SEED + 1)
    # Pad with 60 days of pre-history so 20-day vol windows + 30-day
    # bootstrap are populated.
    start = pd.Timestamp(START_DATE) - pd.offsets.BDay(60)
    end = pd.Timestamp(START_DATE) + pd.offsets.BDay(N_DATES + 10)
    dates = pd.bdate_range(start, end)
    # Calm uptrend: drift +6 bp/day, vol ~0.5%/day → annualized ~8%.
    rets = rng.normal(0.0006, 0.005, len(dates))
    prices = 400.0 * np.exp(np.cumsum(rets))   # starting near SPY's mid-range
    df = pd.DataFrame({
        "open":   prices * 0.999,
        "high":   prices * 1.003,
        "low":    prices * 0.997,
        "close":  prices,
        "volume": rng.integers(8_000_000, 12_000_000, len(dates)),
    }, index=dates)
    df.index.name = "date"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path)
    return out_path


def main() -> int:
    here = Path(__file__).resolve().parent
    panel_out = regen_panel(here / "smoke_panel.parquet")
    spy_out = regen_spy(here / "smoke_spy.parquet")
    panel_df = pd.read_parquet(panel_out)
    spy_df = pd.read_parquet(spy_out)
    print(f"wrote {panel_out} ({panel_out.stat().st_size} bytes)")
    print(f"  panel: {len(panel_df)} rows × "
          f"{panel_df['ticker'].nunique()} tickers × "
          f"{panel_df['date'].nunique()} dates")
    print(f"  features: {SIGNAL_FEATURE} (signal) + "
          f"{len(NOISE_FEATURES)} noise")
    print(f"  label: {LABEL_COL}  beta={SIGNAL_TO_LABEL_BETA}")
    print(f"wrote {spy_out} ({spy_out.stat().st_size} bytes)")
    print(f"  spy: {len(spy_df)} business days, "
          f"{spy_df.index[0].date()} .. {spy_df.index[-1].date()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
