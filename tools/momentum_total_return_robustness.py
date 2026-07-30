#!/usr/bin/env python3
"""Post-run robustness on the PRIMARY. Diagnostics only -- the §6 verdict is
already fixed by the frozen rule and NOTHING here can revise it.

R1 LOOK-AHEAD PROOF. R[t] = prod_{s>t} g[s] uses FUTURE dividends, so TR[t]
   depends on information after t. Prove numerically that every statistic used
   is invariant to the anchor, i.e. that the future-dividend dependence cancels:
   rebuild the TR series anchored at an EARLY date (a forward-cumulative index
   that uses only dividends up to t) and confirm the factors are identical.
   If they are, there is no look-ahead; if not, the study is contaminated.
R2 LEAVE-ONE-BLOCK-OUT on the primary: with only 10 blocks, would dropping any
   single block flip the sign or kill the t?
R3 is E2 driven by a handful of dates? per-block means, worst/best dates.
R4 E1 vs E2: a tail-driven effect should show a weak IC and a strong spread.
R5 the NaN-fill window: does excluding ATI/BA/INTC change the primary?
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SP = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator"
          "/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/mom-total-return")
WT = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator"
          "/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/mom-tr-71824")
sys.path.insert(0, str(WT / "tools"))
sys.path.insert(0, str(WT / "src"))
import momentum_total_return_run as T  # noqa: E402

tr = pd.read_parquet(SP / "total_return_close.parquet")
tr["date"] = pd.to_datetime(tr["date"])

# ============================================================== R1 ============
print("=" * 78)
print("R1  LOOK-AHEAD PROOF — is the backward anchor information-bearing?")
print("=" * 78)
print("  Algebra first. TR[t] = P[t]/R[t] with R[t] = prod_{s>t} g[s]. Then")
print("    mom_12_1(t) = TR[t-20]/TR[t-250] - 1")
print("                = (P[t-20]/P[t-250]) * (R[t-250]/R[t-20]) - 1")
print("    and R[t-250]/R[t-20] = prod over t-250 < s <= t-20 of g[s],")
print("  i.e. ONLY dividends INSIDE the formation window, all of them <= t-20.")
print("  Every future dividend cancels. Same for the label, where the surviving")
print("  product is prod over t < s <= t+h -- which is exactly the reinvested")
print("  cash a holder earns over the forward window, not leakage.")
print("\n  Numerical proof: rebuild a FORWARD-cumulative index that at every t")
print("  uses ONLY dividends up to t, then compare the factors.")

FWD = {}
for t_, g in tr.groupby("ticker", observed=True):
    g = g.set_index("date").sort_index()
    p, d = g["close"].to_numpy(), g["dividend"].to_numpy()
    gg = np.ones_like(p)
    ev = d > 0
    gg[ev] = 1.0 + d[ev] / p[ev]
    # forward index: F[t] = P[t] * prod_{s<=t} g[s]  (uses only s <= t)
    FWD[t_] = pd.Series(p * np.cumprod(gg), index=g.index)

BACK = {t_: g.set_index("date").sort_index()["tr_close"]
        for t_, g in tr.groupby("ticker", observed=True)}

def mom_12_1(c):
    return c.shift(20) / c.shift(250) - 1.0

def hi52(c):
    return c / c.rolling(251, min_periods=251).max()

def ma200(c):
    return c / c.rolling(201, min_periods=201).mean()

def vol250(c):
    return c.pct_change().rolling(250, min_periods=250).std(ddof=1) * np.sqrt(252)

worst = {}
for nm, fn in (("mom_12_1", mom_12_1), ("hi52_prox", hi52),
               ("ma200_ratio", ma200), ("vol_250", vol250)):
    mx = 0.0
    for t_ in BACK:
        a, b = fn(BACK[t_]), fn(FWD[t_])
        m = a.notna() & b.notna()
        if m.any():
            mx = max(mx, float((a[m] - b[m]).abs().max()))
    worst[nm] = mx
    print(f"    {nm:<14} max|backward-anchored - forward-only| = {mx:.3e}")
# ratio of the two series must be a per-ticker CONSTANT
consts = []
for t_ in BACK:
    r = (BACK[t_] / FWD[t_]).dropna()
    consts.append(float(r.max() / r.min() - 1.0))
print(f"    per-ticker ratio BACK/FWD: max relative spread = {max(consts):.3e}")
print("    -> the two series differ by a pure per-ticker CONSTANT, so every")
print("       ratio statistic is identical. NO LOOK-AHEAD in any factor used.")
print("    -> the ONLY anchor-sensitive quantity is the LEVEL of TR[t], which")
print("       the prereg §3.2 explicitly forbids using. That prohibition is")
print("       load-bearing, not stylistic.")

# ============================================================== setup =========
m = pd.read_parquet(SP / "momentum_factor_matrix_tr.parquet")
m["date"] = pd.to_datetime(m["date"])
lab = T.build_labels(tr)
df = m.merge(lab, on=["date", "ticker"], how="inner")
for k, v in T.build_arms(df).items():
    df[k] = v
hold = df[df.date >= T.HOLDOUT_START]
ARM, H = T.ARM_PRIMARY, T.H_PRIMARY
YC = f"fwd_{H}_tr"
e2 = T.per_date_e2(hold, ARM, YC)
print(f"\n  primary per-date E2 series: n={len(e2)} mean={e2.mean():+.4f}")

# ============================================================== R2 ============
print("\n" + "=" * 78)
print("R2  LEAVE-ONE-BLOCK-OUT on the primary (only 10 blocks)")
print("=" * 78)
v = e2.values
blocks = [v[i:i + H] for i in range(0, len(v), H)]
bm = np.array([b.mean() for b in blocks])
print(f"  {len(blocks)} blocks of {H}; per-block mean E2:")
for i, (b, bmi) in enumerate(zip(blocks, bm)):
    d0 = e2.index[i * H]
    d1 = e2.index[min((i + 1) * H, len(e2)) - 1]
    print(f"    block {i:>2}  {str(pd.Timestamp(d0).date())}..{str(pd.Timestamp(d1).date())}"
          f"  n={len(b):>4}  mean={bmi:+.4f}")
print(f"\n  blocks positive: {int((bm > 0).sum())}/{len(bm)}")
n = len(bm)
print(f"  {'dropped':>8}{'mean':>10}{'t':>9}")
ts = []
for i in range(n):
    k = np.delete(bm, i)
    t_ = k.mean() / (k.std(ddof=1) / np.sqrt(len(k)))
    ts.append(t_)
    print(f"  {i:>8}{k.mean():>+10.4f}{t_:>+9.2f}")
print(f"\n  full-sample block t = {bm.mean()/(bm.std(ddof=1)/np.sqrt(n)):+.3f}")
print(f"  LOBO t range = [{min(ts):+.2f}, {max(ts):+.2f}]   "
      f"sign flips = {sum(1 for x in ts if x <= 0)}   "
      f"drops below 1.96 = {sum(1 for x in ts if abs(x) < 1.96)}   "
      f"drops below 3.10 = {sum(1 for x in ts if abs(x) < 3.1019)}")

# ============================================================== R3 ============
print("\n" + "=" * 78)
print("R3  is E2 carried by a few dates?")
print("=" * 78)
print(f"  per-date E2: mean={e2.mean():+.4f} p50={e2.median():+.4f} "
      f"sd={e2.std():.4f}  positive dates={(e2>0).mean():.1%}")
srt = e2.sort_values()
for frac in (0.01, 0.05, 0.10):
    k = int(len(e2) * frac)
    trimmed = srt.iloc[k:-k] if k else srt
    print(f"  trim {frac:.0%} each tail: mean={trimmed.mean():+.4f} "
          f"(n={len(trimmed)})")
print(f"  mean after dropping the 10 BEST dates : "
      f"{srt.iloc[:-10].mean():+.4f}")
print(f"  mean after dropping the 10 WORST dates: {srt.iloc[10:].mean():+.4f}")
print("  -> a broad effect barely moves under trimming; a few-date artifact "
      "collapses.")
yr = e2.groupby(pd.DatetimeIndex(e2.index).year).agg(["size", "mean"])
print("\n  by calendar year:")
print(yr.to_string(float_format=lambda x: f"{x:+.4f}"))

# ============================================================== R4 ============
print("\n" + "=" * 78)
print("R4  E1 (full-cross-section IC) vs E2 (top-decile spread)")
print("=" * 78)
s = T.prep(hold, ARM, YC)
e1, e2b = T.per_date_stats(s, ARM, YC)
print(f"  E1 per-date IC: mean={e1.mean():+.4f} sd={e1.std():.4f} "
      f"block t={T.agg(e1,H,2000)['t']:+.3f}")
print(f"  E2 per-date   : mean={e2b.mean():+.4f} sd={e2b.std():.4f} "
      f"block t={T.agg(e2b,H,2000)['t']:+.3f}")
print("  Decompose E2 into its two legs (top decile vs rest), per date:")
d = s["date"]
rd = s[ARM].groupby(d).rank(ascending=False, method="first")
k = np.maximum(1, np.round(s[ARM].groupby(d).transform("size") * T.TOP_FRACTION))
top = s[YC][rd <= k].groupby(d[rd <= k]).mean()
rest = s[YC][rd > k].groupby(d[rd > k]).mean()
print(f"    top-decile mean label z  = {top.mean():+.4f} "
      f"(block t={T.agg(top,H,2000)['t']:+.2f})")
print(f"    rest mean label z        = {rest.mean():+.4f} "
      f"(block t={T.agg(rest,H,2000)['t']:+.2f})")
# decile monotonicity: is the whole curve ordered, or only the tail?
s2 = s.copy()
s2["dec"] = s2.groupby("date")[ARM].transform(
    lambda x: pd.qcut(x.rank(method="first"), 10, labels=False, duplicates="drop"))
prof = s2.groupby("dec")[YC].mean()
print("\n  mean label z by factor decile (0 = lowest momentum):")
print("   " + "  ".join(f"d{int(i)}={x:+.3f}" for i, x in prof.items()))
sp = float(np.corrcoef(prof.index.astype(float), prof.values)[0, 1])
print(f"  rank-correlation of the decile profile with decile number = {sp:+.4f}")
print("  -> a monotone profile is a broad effect; a flat middle with only the")
print("     top decile up is a tail effect, consistent with a weak E1.")

# ============================================================== R5 ============
print("\n" + "=" * 78)
print("R5  the dividend-NaN names (ATI/BA/INTC) sit INSIDE the primary window")
print("    (NaN block 2025-07-28..2026-07-29). Drop them and re-measure.")
print("=" * 78)
sub = hold[~hold.ticker.isin(["ATI", "BA", "INTC"])]
r = T.measure(sub, ARM, YC, H, controls=3)
print(f"  excluding the 3 names: E2={r['E2']['mean']:+.4f} t={r['E2']['t']:+.3f} "
       f"n={r['E2']['n']} placebo max={r['E2']['ctl_max']:.2f}")
print(f"  full sample          : E2={e2.mean():+.4f} t="
      f"{bm.mean()/(bm.std(ddof=1)/np.sqrt(n)):+.3f}")
# and: does the NaN window itself matter? restrict to dates BEFORE the NaN block
pre = hold[hold.date < pd.Timestamp("2025-07-28")]
rp = T.measure(pre, ARM, YC, H, controls=3)
print(f"  holdout dates BEFORE the NaN block starts: E2={rp['E2']['mean']:+.4f} "
      f"t={rp['E2']['t']:+.3f} n={rp['E2']['n']} blocks={rp['E2']['n_blocks']}")

json.dump({"lookahead_max_factor_diff": worst,
           "anchor_ratio_max_rel_spread": max(consts),
           "block_means": [float(x) for x in bm],
           "lobo_t": [float(x) for x in ts],
           "decile_profile": {str(int(i)): float(x) for i, x in prof.items()},
           "decile_monotonicity_corr": sp,
           "drop3_names": r["E2"], "pre_nan_window": rp["E2"]},
          open(SP / "05_robustness.json", "w"), indent=2)
print(f"\nwrote {SP/'05_robustness.json'}")
