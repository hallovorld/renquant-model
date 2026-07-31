#!/usr/bin/env python3
"""Applies the FROZEN §3 rules of model#90 MECHANICALLY to results.json.
No thresholds beyond the ones written in the prereg."""
import json
from pathlib import Path

OUT = Path(__file__).parent
R = json.load(open(OUT / "results.json"))
C = R["comparative"]
SUBS = ["prod_XGB", "certified_clf", "PatchTST"]
L = []


def p(s=""):
    print(s); L.append(s)


def f(c, k="t"):
    v = c.get(k)
    return float("nan") if v is None else float(v)


p("=" * 92)
p("CORRECTED SIGNAL EVALUATION — model#90 frozen prereg, mechanical verdicts")
p(f"alignment primitive: {R['meta']['alignment_primitive']}")
p(f"labels: {R['meta']['label_source']} :: {R['meta']['label_col']}")
p(f"universe: 142-name intersection | block_len={R['meta']['block_len']} "
  f"| persist_lag={R['meta']['persist_lag']}d | perm_seeds={R['meta']['perm_seeds']}")
p("=" * 92)

p("\n### HARNESS SELF-TEST (control on the code, not a decision statistic)")
for k, v in R["self_test"].items():
    p(f"  {k:22s} IC={v['ic_real_mean']:+.4f} real_t={v['ic_real_t']:+.2f} "
      f"d_vs_perm_t={v['ic_d_vs_perm_t']:+.2f} d_vs_persist_t={v['ic_d_vs_persist_t']:+.2f}")

# ------------------------------------------------------------------ Q1 table
p("\n### Q1 TABLE — subject x {IC, spread} x {permutation, persistence}")
p("    d = REAL - null, block-level (block=60 score dates = the label horizon)")
p(f"{'subject':16s} {'stat':7s} {'REAL mean':>10s} {'REAL t':>7s} | "
  f"{'d_perm mean':>11s} {'d_perm t':>9s} | {'d_pers mean':>11s} {'d_pers t':>9s} | "
  f"{'n_eff':>5s} {'n_dates':>7s}")
p("-" * 108)
for s in SUBS:
    q = C[s]["q1_table"]
    for st in ("ic", "spread"):
        a, b, c = q[st]["real"], q[st]["d_vs_perm"], q[st]["d_vs_persist"]
        p(f"{s:16s} {st:7s} {a['mean']:+10.5f} {f(a):+7.2f} | "
          f"{b['mean']:+11.5f} {f(b):+9.2f} | {c['mean']:+11.5f} {f(c):+9.2f} | "
          f"{a['n_eff']:5d} {a['n_dates']:7d}")
p("\n  arm sample (both arms of every paired comparison, T12):")
for s in SUBS:
    a = C[s]["arm_sample"]
    p(f"    {s:16s} n={a['n']:4d} [{a['first']}..{a['last']}]  "
      f"lag0_evaluable={a['lag0_evaluable']} persist_eligible={a['persist_eligible']} "
      f"dropped_vs_lag0={a['dropped_vs_lag0']}")

# ------------------------------------------------------------------ Q1 rule
p("\n### Q1 VERDICTS — rule: t_d >= +1.0 FRESH-INFORMATIVE; <= -1.0 "
  "PERSISTENCE-DRIVEN; else UNRESOLVED (IC at 60d)")
q1 = {}
for s in SUBS:
    t = f(C[s]["q1_table"]["ic"]["d_vs_persist"])
    v = ("FRESH-INFORMATIVE" if t >= 1.0 else
         "PERSISTENCE-DRIVEN" if t <= -1.0 else "UNRESOLVED")
    q1[s] = v
    p(f"    {s:16s} t_d={t:+.3f}  ->  {v}")

ctrl = q1["prod_XGB"]
ctrl_ok = (ctrl == "FRESH-INFORMATIVE")
p(f"\n  POSITIVE-CONTROL CHECK (§3): prod XGB = {ctrl}")
if ctrl_ok:
    p("    -> control PASSES (not UNRESOLVED, not PERSISTENCE-DRIVEN). "
      "The design retains sensitivity; the other subjects' verdicts stand as computed.")
else:
    p("    -> control FAILS. Per §3 ALL verdicts become UNRESOLVED.")
    for s in SUBS:
        q1[s] = "UNRESOLVED (forced by control failure)"

# ------------------------------------------------------------------ Q2
p("\n### Q2 — lag profile on ONE common sample per subject (T11)")
for s in SUBS:
    la = C[s]["lag_alignment"]
    p(f"\n  {s}: common sample n={la['n_common_dates']} "
      f"[{la['first']}..{la['last']}]  dropped_per_lag={la['dropped_per_lag']}")
    prof = C[s]["lag_profile"]
    mx = C[s]["lag_profile_maximal_sample_DIAGNOSTIC"]
    v0 = C[s]["lag_vs_lag0_paired_ic"]
    p(f"    {'lag':>4s} {'IC(common)':>11s} {'IC t':>7s} | "
      f"{'paired d vs lag0':>16s} {'d t':>7s} | {'IC(maximal-DIAG)':>17s} {'n_max':>6s}")
    for lg in R["meta"]["profile_lags"]:
        k = str(lg)
        d = v0.get(k)
        ds = f"{d['mean']:+16.5f} {f(d):+7.2f}" if d else f"{'(base)':>16s} {'-':>7s}"
        p(f"    {lg:4d} {prof[k]['ic']['mean']:+11.5f} {f(prof[k]['ic']):+7.2f} | {ds} | "
          f"{mx[k]['ic']['mean']:+17.5f} {mx[k]['n_dates']:6d}")

xg = C["prod_XGB"]["lag_vs_lag0_paired_ic"]
best = max(xg.items(), key=lambda kv: (f(kv[1]) if f(kv[1]) == f(kv[1]) else -9e9))
p(f"\n  prod XGB best lag>0 vs lag0: lag={best[0]} t={f(best[1]):+.3f} "
  f"(rule needs t >= +2.0)")
xgb_pass = f(best[1]) >= 2.0
agree = [s for s in SUBS if s != "prod_XGB"
         and C[s]["lag_vs_lag0_paired_ic"].get(best[0], {}).get("mean", -1) > 0]
p(f"  other subjects agreeing in direction at lag {best[0]}: {agree or 'none'}")
q2 = "PROFILE-CONFIRMED" if (xgb_pass and agree) else "PROFILE-WITHDRAWN"
if not ctrl_ok:
    q2 = "PROFILE-WITHDRAWN (conservative branch; control failed)"
p(f"  Q2 VERDICT: {q2}"
  + ("" if q2.startswith("PROFILE-CONFIRMED") else
     "  -> the parked horizon prereg (model#88) STAYS PARKED"))

# ------------------------------------------------------------------ Q3
p("\n### Q3 — tail spread vs IC: which arm's (REAL - permutation) block t is higher?")
p("    rule: winner must lead by >= 1.0 AND have its own t >= 2.0; else INCONCLUSIVE")
q3 = {}
for s in SUBS:
    ti = f(C[s]["q1_table"]["ic"]["d_vs_perm"])
    ts = f(C[s]["q1_table"]["spread"]["d_vs_perm"])
    w, wt, lt = ("spread", ts, ti) if ts >= ti else ("ic", ti, ts)
    ok = (wt - lt) >= 1.0 and wt >= 2.0
    q3[s] = f"{w.upper()} wins" if ok else "INCONCLUSIVE"
    p(f"    {s:16s} IC t={ti:+.2f}  spread t={ts:+.2f}  "
      f"lead={wt - lt:+.2f} (need >=1.0) winner_t={wt:+.2f} (need >=2.0) -> {q3[s]}")
    r0 = C[s]["q3_full_lag0_sample"]
    p(f"{'':20s} robustness on full lag-0 sample (n={r0['n_dates']}): "
      f"IC t={f(r0['ic_d_vs_perm']):+.2f}  spread t={f(r0['spread_d_vs_perm']):+.2f}")
overall_q3 = "INCONCLUSIVE" if any(v == "INCONCLUSIVE" for v in q3.values()) else \
             (list(q3.values())[0] if len(set(q3.values())) == 1 else "INCONCLUSIVE")
if not ctrl_ok:
    overall_q3 = "INCONCLUSIVE (conservative branch; control failed)"
p(f"  Q3 VERDICT: {overall_q3}  -> production keeps IC"
  if overall_q3.startswith("INCONCLUSIVE") else f"  Q3 VERDICT: {overall_q3}")

# ------------------------------------------------------------------ own univ
p("\n### DESCRIPTIVE — own universe, subject's own carried label (not comparative)")
for s in SUBS:
    o = R["own_universe"][s]
    if "note" in o:
        p(f"    {s:16s} {o['note']}")
        continue
    q = o["q1_table"]
    p(f"    {s:16s} n_names={o['n_names_universe']:4d} arm_n={o['arm_sample']['n']:4d}  "
      f"IC={q['ic']['real']['mean']:+.5f}(t={f(q['ic']['real']):+.2f})  "
      f"d_vs_persist t={f(q['ic']['d_vs_persist']):+.2f}  "
      f"spread={q['spread']['real']['mean']:+.4f}(t={f(q['spread']['real']):+.2f})  "
      f"n_eff={q['ic']['real']['n_eff']}")

p("\n" + "=" * 92)
p("SUMMARY")
for s in SUBS:
    p(f"  Q1 {s:16s} {q1[s]}")
p(f"  Q2 {q2}")
p(f"  Q3 {overall_q3}")
p("=" * 92)

(OUT / "verdict.log").write_text("\n".join(L) + "\n")
json.dump({"q1": q1, "q2": q2, "q3": q3, "q3_overall": overall_q3,
           "control": ctrl, "control_ok": ctrl_ok},
          open(OUT / "verdict.json", "w"), indent=2)
