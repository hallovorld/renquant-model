"""Negative control: prove the per-fold leakage assertion FAILS the fold (raises)
rather than warning, when the embargo is removed. READ-ONLY."""
import importlib.util, json
from pathlib import Path
import numpy as np, pandas as pd
RQ = Path("/Users/renhao/git/github/RenQuant"); DATA = RQ/"data"
spec = importlib.util.spec_from_file_location("_r", "/Users/renhao/git/github/renquant-model/scripts/train_topdecile_clf_shadow.py")
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
from renquant_model_gbdt.panel_data import load_panel
train_all, feat_cols, label = load_panel(DATA, label=r.LABEL)
cut, w0, LOOK = pd.Timestamp("2023-10-02"), pd.Timestamp("2023-10-03"), 60

def check(embargo):
    eff = cut - pd.offsets.BDay(max(0, embargo))
    train = train_all[train_all["date"] < eff]
    etc = pd.Timestamp(r.effective_train_cutoff(train, r.LABEL))
    safe = etc + pd.offsets.BDay(LOOK)
    if not safe < w0:
        raise AssertionError(f"LEAKAGE embargo={embargo}: etc {etc.date()} + {LOOK}BDay "
                             f"= {safe.date()} >= first OOS date {w0.date()}")
    return f"PASS embargo={embargo}: etc {etc.date()} -> safe {safe.date()} < {w0.date()}"

print(check(60))                       # the recipe's own embargo
for bad in (0, 30, 55):
    try:
        print(check(bad)); raise SystemExit(f"FAIL: assertion did NOT fire at embargo={bad}")
    except AssertionError as e:
        print(f"[fired] {e}")
print("[OK] assertion fires (raises) on every leaky embargo; passes at the recipe's 60")
