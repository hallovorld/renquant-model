"""Shared synthetic D-C2-layout crypto store for the crypto family tests.

No network, no real data: bars are deterministic (seeded) daily UTC OHLCV
frames written to ``{root}/crypto_ohlcv/{SLUG}/1d.parquet`` — the store
contract the model side consumes (base-data #41, D-C2).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CRYPTO_OHLCV_DIRNAME = "crypto_ohlcv"


def make_crypto_store(
    root: Path,
    slugs: list[str],
    *,
    n_days: int = 240,
    seed: int = 7,
    start: str = "2024-01-01",
    tz_aware: bool = True,
) -> Path:
    """Write deterministic synthetic daily UTC bars for each slug."""
    dates = pd.date_range(start, periods=n_days, freq="D", tz="UTC" if tz_aware else None)
    for i, slug in enumerate(slugs):
        rng = np.random.default_rng(seed + i)
        rets = rng.normal(loc=0.0008, scale=0.03, size=n_days)
        close = 100.0 * (2.0 + i) * np.cumprod(1.0 + rets)
        open_ = np.concatenate([[close[0]], close[:-1]])
        high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0, 0.005, n_days)))
        low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0, 0.005, n_days)))
        volume = rng.lognormal(mean=10.0, sigma=0.4, size=n_days)
        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )
        df.index.name = "date"
        out = root / CRYPTO_OHLCV_DIRNAME / slug
        out.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out / "1d.parquet")
    return root
