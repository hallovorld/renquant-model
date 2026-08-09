"""Verifier for the L3 meta-label experiment record — recomputes every leg
from the COMMITTED artifacts alone and fails on any drift from the summary.

leg1/leg2 from the folds + placebo CSVs; leg4 from the pooled per-row
predictions (regenerated deterministically from the frozen dataset — same
folds, same model — and committed); leg3 from the external CSV. Exits 1 on
any mismatch with 2026-08-09-l3-exp-summary.json.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).resolve().parent
S = json.loads((HERE/"2026-08-09-l3-exp-summary.json").read_text())
bad = []

f = pd.read_csv(HERE/"2026-08-09-l3-exp-folds-all.csv")
u = f["uplift_0.5"].dropna()
leg1 = bool(len(u) and u.median() > 0 and (u > 0).mean() >= 2/3)
if abs(u.median()-S["median_uplift_0.5"]) > 1e-12: bad.append("median_uplift")
if leg1 != S["leg1_fold_consistency"]: bad.append("leg1")

p = pd.read_csv(HERE/"2026-08-09-l3-exp-placebo.csv")["placebo_median_uplift"]
if len(p) != S["n_placebo"]: bad.append("n_placebo")
p95 = float(np.nanquantile(p.values.astype(float), 0.95))
if abs(p95-S["placebo_p95"]) > 1e-12: bad.append("placebo_p95")
if bool(u.median() > p95) != S["leg2_placebo"]: bad.append("leg2")

pp = pd.read_csv(HERE/"2026-08-09-l3-exp-pooled-predictions.csv")
logit = np.log(np.clip(pp["P"], 1e-6, 1-1e-6)/(1-np.clip(pp["P"], 1e-6, 1-1e-6)))
cal = LogisticRegression(C=1e6, max_iter=1000).fit(
    logit.values.reshape(-1, 1), pp["win"])
slope = float(cal.coef_[0][0])
if abs(slope-S["cal_slope"]) > 1e-6: bad.append(f"cal_slope {slope}")
if bool(0.5 <= slope <= 2.0) != S["leg4_calibration"]: bad.append("leg4")

e = pd.read_csv(HERE/"2026-08-09-l3-exp-external.csv")
if len(e) != 34: bad.append("external_n")
sel = e["fwd_return"][e["P"] >= 0.5]
leg3 = bool(len(sel) and (sel.mean()-e["fwd_return"].mean()) >= 0)
if leg3 != S["leg3_external"]: bad.append("leg3")

verdict = "PASS" if all(S[k] for k in
    ("leg1_fold_consistency", "leg2_placebo", "leg3_external",
     "leg4_calibration")) else "KILL"
if verdict != S["verdict"]: bad.append("verdict")
if bad:
    print("DRIFT:", bad); sys.exit(1)
print(f"VERIFIED — all four legs recomputed from committed artifacts; "
      f"verdict {verdict} (median uplift {u.median():+.6f}, p95 {p95:+.6f}, "
      f"slope {slope:+.6f}, external n_sel {int((e['P']>=0.5).sum())}/34)")
