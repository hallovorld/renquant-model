"""L3 meta-label experiment — 2026-08-09 execution attempt, re-scoped to
EXPLORATORY DIAGNOSTICS ONLY (no admissible prereg verdict; see
doc/research/2026-08-09-l3-meta-label-experiment.md §0).

Intended contract: doc/design/2026-08-09-l3-classifier-prereg.md (v1,
model#207) as amended by …-prereg-v2.md (v2, model#208). This run does NOT
count as that prereg's one execution: leg 3 is target-misaligned (§0.1),
and the guards below — min_train=300 rows, min_test=50 rows,
min_pre_dates=60, min_selected=10 for a fold uplift to be defined, plus the
quarterly BOUNDS grid from 2024-07-01 — were execution-time implementation
choices validated by pre-run controls, NOT frozen in v1/v2 (§0.2).

Input: the COMMITTED frozen CSV (hash re-checked at start, per the v2 NEXT
clause). External test: the frozen 34-row identifier list, outcomes joined
from trade_evaluations ONLY at evaluation time (the once-only read).
Determinism: no RNG anywhere except the placebo's per-seed shuffle
(random_state=seed, seeds 0..199, frozen in v1).
"""
import hashlib, json, sqlite3, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
FROZEN_DIR = HERE.parent.parent / "design" / "frozen"
CSV = FROZEN_DIR / "2026-08-09-l3-candidate-dataset-v2.csv"
CSV_SHA = "eecfd050a52fab53f9a5f366ac4d5a69e560d426dfe6c5fa3485ed0ebec45405"
EXT = FROZEN_DIR / "2026-08-09-l3-prereg-v2-external-eligible.txt"
DB = Path("/Users/renhao/git/github/RenQuant/data/runs.alpaca.db")
FEATS = ["panel_score", "mu", "rank_score", "n_candidates_that_date"]  # v2 S4
TAUS = [0.5, 0.6]
N_PLACEBO = 200            # v1
MIN_TRAIN, MIN_TEST, MIN_PRE, MIN_SEL = 300, 50, 60, 10

got = hashlib.sha256(CSV.read_bytes()).hexdigest()
assert got == CSV_SHA, f"frozen CSV drifted: {got}"

df = pd.read_csv(CSV, parse_dates=["run_date"])
n0 = len(df)
df = df.dropna(subset=FEATS + ["fwd_20d"]).reset_index(drop=True)
print(f"complete-case: {n0} -> {len(df)} ({n0-len(df)} dropped)")

BOUNDS = list(pd.date_range("2024-07-01", "2026-07-01", freq="QS"))

def folds_for(data):
    axis = sorted(data["run_date"].unique()); out = []
    for i, b in enumerate(BOUNDS):
        b_end = BOUNDS[i+1] if i+1 < len(BOUNDS) else pd.Timestamp("2026-12-31")
        test = data[(data["run_date"] >= b) & (data["run_date"] < b_end)]
        pre = [d for d in axis if d < b]
        if len(pre) < MIN_PRE or len(test) < MIN_TEST: continue
        train = data[data["run_date"] <= pre[-21]]   # 20-trading-day embargo
        if len(train) >= MIN_TRAIN: out.append((b, train, test))
    return out

def fit_predict(train, frame):
    mu_, sd_ = train[FEATS].mean(), train[FEATS].std().replace(0, 1)
    m = LogisticRegression(C=1.0, penalty="l2", max_iter=1000).fit(
        ((train[FEATS]-mu_)/sd_), train["win"])
    return m.predict_proba(((frame[FEATS]-mu_)/sd_))[:, 1]

def run_arm(data, gbdt=False):
    rows = []
    for b, train, test in folds_for(data):
        P = fit_predict(train, test)
        base = test["fwd_20d"].mean()
        r = {"fold": str(b.date()), "n_train": len(train), "n_test": len(test),
             "base_mean_fwd20": base,
             "auc": roc_auc_score(test["win"], P) if test["win"].nunique() > 1 else np.nan}
        for t in TAUS:
            sel = test["fwd_20d"][P >= t]
            r[f"uplift_{t}"] = (sel.mean() - base) if len(sel) >= MIN_SEL else np.nan
            r[f"n_sel_{t}"] = int(len(sel))
        for rt in ("live", "sim"):                       # v1: run_type split
            sub = test[test["run_type"] == rt]
            if len(sub) >= MIN_SEL:
                Ps = P[test["run_type"].values == rt]
                sel = sub["fwd_20d"][Ps >= 0.5]
                r[f"uplift_0.5_{rt}"] = (sel.mean() - sub["fwd_20d"].mean()) if len(sel) >= MIN_SEL else np.nan
        if gbdt:
            mu_, sd_ = train[FEATS].mean(), train[FEATS].std().replace(0, 1)
            g = GradientBoostingClassifier(max_depth=2, n_estimators=100,
                                           learning_rate=0.1, random_state=0).fit(
                ((train[FEATS]-mu_)/sd_), train["win"])
            Pg = g.predict_proba(((test[FEATS]-mu_)/sd_))[:, 1]
            r["gbdt_auc"] = roc_auc_score(test["win"], Pg) if test["win"].nunique() > 1 else np.nan
        rows.append(r)
    return pd.DataFrame(rows)

res_all = run_arm(df, gbdt=True)
res_live = run_arm(df[df["run_type"] == "live"].reset_index(drop=True))
res_all.to_csv(HERE/"2026-08-09-l3-exp-folds-all.csv", index=False)
res_live.to_csv(HERE/"2026-08-09-l3-exp-folds-liveonly.csv", index=False)

u = res_all["uplift_0.5"].dropna()
leg1 = bool(len(u) and u.median() > 0 and (u > 0).mean() >= 2/3)
print(f"LEG1: median {u.median():+.6f} share>0 {(u>0).mean():.3f} -> {leg1}")

plc = []
for s in range(N_PLACEBO):
    d2 = df.copy()
    d2["win"] = d2.groupby("run_date")["win"].transform(
        lambda x: x.sample(frac=1, random_state=s).values)
    pu = run_arm(d2)["uplift_0.5"].dropna()
    plc.append(pu.median() if len(pu) else np.nan)
pd.Series(plc, name="placebo_median_uplift").to_csv(HERE/"2026-08-09-l3-exp-placebo.csv", index=False)
p95 = float(np.nanquantile(np.array(plc, dtype=float), 0.95))
leg2 = bool(len(u) and u.median() > p95)
print(f"LEG2: real {u.median():+.6f} vs placebo p95 {p95:+.6f} -> {leg2}")

pooled_P, pooled_y = [], []
for b, train, test in folds_for(df):
    pooled_P.append(fit_predict(train, test)); pooled_y.append(test["win"].values)
P = np.concatenate(pooled_P); y = np.concatenate(pooled_y)
logit = np.log(np.clip(P, 1e-6, 1-1e-6)/(1-np.clip(P, 1e-6, 1-1e-6)))
cal = LogisticRegression(C=1e6, max_iter=1000).fit(logit.reshape(-1, 1), y)
slope = float(cal.coef_[0][0]); intercept = float(cal.intercept_[0])
leg4 = bool(0.5 <= slope <= 2.0)
print(f"LEG4: slope {slope:.4f} intercept {intercept:+.4f} -> {leg4}")

# external, ONCE: frozen 34 ids; features from the frozen dataset (same join
# as training rows); outcomes from trade_evaluations read only here
ids = [l.split("|") for l in EXT.read_text().strip().splitlines()]
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
ev = pd.read_sql_query(
    "SELECT run_id, ticker, action, horizon_days, fwd_return FROM trade_evaluations", con)
con.close()
ev["key"] = ev.run_id + "|" + ev.ticker + "|" + ev.action + "|" + ev.horizon_days.astype(str)
want = {"|".join(i) for i in ids}
evx = ev[ev.key.isin(want)].copy()
assert len(evx) == 34, f"frozen external list resolves to {len(evx)} rows, not 34 -> leg3 KILL by drift"
evx["run_date"] = pd.to_datetime(evx["run_id"].str[:10])
feat_rows = df.drop_duplicates(subset=["run_date", "ticker"]).set_index(["run_date", "ticker"])
fl = folds_for(df)
recs = []
for i, (b, train, test) in enumerate(fl):
    b_end = fl[i+1][0] if i+1 < len(fl) else pd.Timestamp("2026-12-31")
    sub = evx[(evx["run_date"] >= b) & (evx["run_date"] < b_end)]
    if not len(sub): continue
    feats = feat_rows.loc[list(zip(sub["run_date"], sub["ticker"]))][FEATS].reset_index(drop=True)
    Pe = fit_predict(train, feats)
    recs.append(pd.DataFrame({"key": sub["key"].values, "P": Pe,
                              "fwd_return": sub["fwd_return"].values}))
ext = pd.concat(recs) if recs else pd.DataFrame()
ext.to_csv(HERE/"2026-08-09-l3-exp-external.csv", index=False)
n_covered = len(ext)
sel = ext["fwd_return"][ext["P"] >= 0.5] if n_covered else pd.Series(dtype=float)
if n_covered < 34:
    leg3, ext_note = False, f"only {n_covered}/34 frozen rows fall inside a fold's test span -> fail-closed"
elif len(sel) == 0:
    leg3, ext_note = False, "zero of 34 rows clear tau=0.5 -> uplift undefined -> fail-closed"
else:
    upl = float(sel.mean() - ext["fwd_return"].mean())
    leg3, ext_note = bool(upl >= 0), f"uplift {upl:+.6f} on n_sel {len(sel)}/34"
print(f"LEG3: {ext_note} -> {leg3}")

gate = "PASS" if (leg1 and leg2 and leg3 and leg4) else "KILL"
summary = {"as_run_gate_arithmetic": gate, "admissible_verdict": None,
           "admissibility_note": (
               "gate arithmetic over an inadmissible run (leg 3 "
               "target-misaligned, fold guards unfrozen) — exploratory "
               "diagnostics only, NOT a prereg verdict; see "
               "doc/research/2026-08-09-l3-meta-label-experiment.md §0"),
           "leg1_fold_consistency": leg1,
           "leg2_placebo": leg2, "leg3_external": leg3, "leg4_calibration": leg4,
           "median_uplift_0.5": float(u.median()) if len(u) else None,
           "share_folds_positive": float((u > 0).mean()) if len(u) else None,
           "placebo_p95": p95, "cal_slope": slope, "cal_intercept": intercept,
           "external_note": ext_note, "n_folds": int(len(res_all)),
           "n_rows_complete_case": int(len(df)), "n_dropped": int(n0-len(df)),
           "input_csv_sha256": CSV_SHA, "n_placebo": N_PLACEBO,
           "guards": {"min_train": MIN_TRAIN, "min_test": MIN_TEST,
                       "min_pre_dates": MIN_PRE, "min_selected": MIN_SEL}}
(HERE/"2026-08-09-l3-exp-summary.json").write_text(json.dumps(summary, indent=2)+"\n")
print(json.dumps(summary, indent=2))
