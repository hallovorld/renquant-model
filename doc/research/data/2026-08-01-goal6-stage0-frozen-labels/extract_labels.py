#!/usr/bin/env python3
"""One-shot extraction of the Stage-0 decision labels into an immutable committed
table. SOURCE = alpha158_291_fundamental_dataset, NOT the SS2-cited transformer_v4:
measured 2026-08-01, transformer_v4 carries 142 tickers and covers only 142/292 of the
corpus universe, while alpha158 covers 292/292 and its label values agree
byte-for-byte with transformer_v4's on their full 354,258-row intersection —
table (Amendment 3 clause 1, review round 1: a mutable panel path cannot freeze
decision data; a committed table can).

Reads the panel ONCE, keeps only the key + label columns, sorts canonically, writes
with fixed parquet settings, and prints both digests (source panel at extraction;
output table). Run once at amendment time; the committed output + its sha in the
amendment ARE the freeze. READ-ONLY on the panel."""
import hashlib
import sys
from pathlib import Path

import pandas as pd

PANEL = Path("/Users/renhao/git/github/RenQuant/data/alpha158_291_fundamental_dataset.parquet")
OUT = Path(__file__).resolve().parent / "labels.parquet"
COLS = ["ticker", "date", "fwd_5d_excess", "fwd_20d_excess", "fwd_60d_excess"]

panel_sha = hashlib.sha256(PANEL.read_bytes()).hexdigest()
df = pd.read_parquet(PANEL, columns=COLS)
df = df.sort_values(["date", "ticker"]).reset_index(drop=True)
df.to_parquet(OUT, engine="pyarrow", compression="zstd", index=False)
out_sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
print(f"rows={len(df)} dates={df['date'].nunique()} tickers={df['ticker'].nunique()}")
print(f"source_panel_sha256={panel_sha}")
print(f"labels_table_sha256={out_sha}")
print(f"bytes={OUT.stat().st_size}")
