"""MoE slow-state gating harness — the orch#966 monthly-cadence freeze surface.

The ONE routing hypothesis the frozen v2/condact gates did not falsify: the
momentum expert's edge may be gated by a SLOW-moving (monthly-cadence) market
state, not the daily-dispersion state that model#218 Stage E already found NO
SUPPORT for. This harness is the condact machine surface (model#215 §5) with a
single axis change — the activation clock — and NOTHING else re-derived.

Implements, as committed code (no execution-time interpretation):
- REAL-SIGNAL: imported VERBATIM from the merged condact harness
  (2026-08-10-condact-harness.py), which itself imports the v2 harness
  (2026-08-09-xgbmom-v2-harness.py). FEATS, CUTS (91-day-embargo gaps),
  PARAMS, LABEL, SEEDS, the per-row purge, the within-date shuffle leg, the
  daily-IC function `daily_ics`, and the stationary block bootstrap
  `bootstrap_contrast` (block 21, 2000 resamples, seed 99) are the SAME
  objects the condact line uses — not copies. real_sig(day) = ic_real −
  ic_shuffle, the embargo-floor-robust DIFFERENCE (WF-gate leakage-floor
  lesson: trust placebo-clean differences, never absolute IC).
- SLOW STATE S(t): the cross-sectional std of the corpus's own ROC60 column
  across the universe present on the LAST TRADING DAY of each calendar month;
  HELD for the following month (monthly cadence). Causal by construction —
  S at the end of month m uses only data ≤ end-of-m, and is applied only to
  days of month m+1 (all strictly later). No regime label (inadmissible per
  orch#930/#931); no look-ahead.
- ACTIVATION A(month): A_raw[m] = 1 iff S[m] > the trailing-12-month median
  of the monthly S series (min 12 months of history; earlier months
  INADMISSIBLE — fail-closed, never back-filled). A applied to a test day d
  is A_raw[month(d) − 1] (the end-of-previous-month evaluation, held).
- CONTRAST: mean real_sig on A=1 months vs A=0 months, on the embargoed v2
  CUTS test folds, bootstrapped on the daily series (block 21, B 2000,
  seed 99 — mirrored from condact for comparability).
- CONTROLS with hard exit codes (--control positive|null): positive plants a
  monthly-state effect (ROC60 dispersion gates the label) and must be
  recovered (PASS); null SHUFFLES the month labels on the SAME planted data
  and the contrast must collapse (KILL). Run BEFORE the first real read.
- FAIL-CLOSED: Stage-C gate arithmetic is NOT invocable here (--stage C
  refuses by construction; C is its own reviewed amendment). admissible_verdict
  is null until the design doc countersigns.

Stage E (--stage E, the seen v2 folds) carries NO verdict authority and its
artifacts are stamped stage=E-exploratory (exactly like condact Stage E). It is
a diagnostic. The monthly cadence makes the EFFECTIVE sample the number of
distinct test MONTHS, not days — the harness reports per-fold month counts and
the total effective month count so the reader can judge power honestly (#955)."""
import argparse, json, sys
import numpy as np, pandas as pd

# Reuse the condact real-signal machinery VERBATIM (import, do not re-derive).
# condact hardcodes the live-checkout absolute path to the v2 harness; we mirror
# that convention and import condact itself from the same frozen directory. These
# files are committed/frozen and never modified by this line.
sys.path.insert(0, '/Users/renhao/git/github/renquant-model/doc/design/frozen')
import importlib.util as _il
_spec = _il.spec_from_file_location(
    "condact", "/Users/renhao/git/github/renquant-model/doc/design/frozen/2026-08-10-condact-harness.py")
_ca = _il.module_from_spec(_spec)
try: _spec.loader.exec_module(_ca)
except SystemExit: pass
FEATS, CUTS, PARAMS, LABEL = _ca.FEATS, _ca.CUTS, _ca.PARAMS, _ca.LABEL
SEEDS = _ca.SEEDS
NBOOT, BLOCK = _ca.NBOOT, _ca.BLOCK          # 2000, 21 — from condact
daily_ics = _ca.daily_ics                    # per-day IC on embargoed CUTS folds
bootstrap_contrast = _ca.bootstrap_contrast  # stationary geometric block bootstrap

SLOW_FEAT = "ROC60"   # the slow-state axis (60-trading-day rate of change; EXISTS in corpus)
MED_MONTHS = 12       # trailing-12-month median window for the activation threshold
MIN_DAYS = 100        # day guard (mirror condact) for gate-arithmetic admissibility
MIN_MONTHS_E = 12     # Stage-E month-guard: >= 12 test months in EACH arm to report a contrast
MONTH_MIN_C = 24      # Stage-C FROZEN guard (doc only): >= 24 realized-label months per arm


def slow_activation(panel, counts_out=None, shuffle_months=False, seed=13):
    """S(month) = cross-sectional std of ROC60 on the LAST trading day of each
    calendar month across the universe present that day; A_raw[m] = S[m] >
    trailing-12-month median (min 12 months of history); A held for the
    following month: A_applied[month m] = A_raw[m−1]. Returns (A_applied indexed
    by 'YYYY-MM', S series, A_raw series)."""
    # last trading day of each month, on the corpus's OWN calendar
    adf = pd.DataFrame({"date": sorted(panel["date"].unique())})
    adf["ym"] = adf["date"].str[:7]
    last_day = adf.groupby("ym")["date"].max()
    sub = panel[panel["date"].isin(set(last_day.values))].copy()
    sub["ym"] = sub["date"].str[:7]
    S = sub.groupby("ym")[SLOW_FEAT].std().sort_index()          # skipna std
    if counts_out is not None:
        miss = sub.assign(_m=sub[SLOW_FEAT].isna()).groupby("ym")["_m"].sum()
        counts_out["roc60_excluded_per_eval_month"] = {
            str(m): int(v) for m, v in miss.items() if v > 0}
    med = S.rolling(MED_MONTHS, min_periods=MED_MONTHS).median()
    A_raw = pd.Series(np.where(S > med, 1.0, 0.0), index=S.index)
    A_raw[med.isna() | S.isna()] = np.nan                        # warm-up / undefined-std: fail-closed
    if shuffle_months:                                           # null control placebo
        rng = np.random.default_rng(seed)
        valid = A_raw.dropna().index
        A_raw.loc[valid] = rng.permutation(A_raw.loc[valid].values)
    months = list(S.index)
    A_applied = pd.Series(index=months, dtype=float)             # iloc[0] stays NaN (no predecessor)
    for i in range(1, len(months)):
        A_applied.iloc[i] = A_raw.iloc[i - 1]                    # end-of-previous-month, HELD
    return A_applied, S, A_raw


def assign_A(df, A_applied):
    return df["date"].str[:7].map(A_applied)


def _month_counts(frame):
    ym = frame["date"].str[:7]
    return (int(ym[frame.A == 1].nunique()), int(ym[frame.A == 0].nunique()))


def gates(panel, shuffle_months=False):
    real = pd.concat([daily_ics(panel, FEATS, s, False) for s in SEEDS]
                     ).groupby(["date", "fold"], as_index=False).ic.mean()
    shuf = pd.concat([daily_ics(panel, FEATS, s, True) for s in SEEDS]
                     ).groupby(["date", "fold"], as_index=False).ic.mean()
    counts = {}
    A_applied, S, A_raw = slow_activation(panel, counts, shuffle_months)
    for df in (real, shuf):
        df["A"] = assign_A(df, A_applied)
    r = real.dropna(subset=["A"]); s = shuf.dropna(subset=["A"])
    n1, n0 = int((r.A == 1).sum()), int((r.A == 0).sum())        # DAYS
    m1, m0 = _month_counts(r)                                    # distinct test MONTHS (effective N)
    # per-fold month + day census (the power surface)
    per_fold = {}
    for fold, gg in r.groupby("fold"):
        ym = gg["date"].str[:7]
        per_fold[str(fold)] = {
            "months_A1": int(ym[gg.A == 1].nunique()),
            "months_A0": int(ym[gg.A == 0].nunique()),
            "months_total": int(ym.nunique()),
            "days_A1": int((gg.A == 1).sum()),
            "days_A0": int((gg.A == 0).sum())}
    eff_months = int(sum(v["months_total"] for v in per_fold.values()))
    base = {"stage": "E-exploratory",
            "slow_axis": SLOW_FEAT, "med_months": MED_MONTHS,
            "n_A1_days": n1, "n_A0_days": n0,
            "n_A1_months": m1, "n_A0_months": m0,
            "effective_months_total": eff_months,
            "month_guard_min_per_arm": MIN_MONTHS_E,
            "month_guard_met": bool(m1 >= MIN_MONTHS_E and m0 >= MIN_MONTHS_E),
            "per_fold": per_fold,
            "roc60_exclusions": counts.get("roc60_excluded_per_eval_month", {})}
    if n1 < MIN_DAYS or n0 < MIN_DAYS:
        base.update({"admissible": False, "why": f"day guard n1={n1} n0={n0}",
                     "artifact_kind": None, "admissible_verdict": None})
        return base
    rs = r.merge(s, on=["date", "fold"], suffixes=("_r", "_s"))
    rs["real_sig"] = rs.ic_r - rs.ic_s
    arr = rs.sort_values("date")
    ci1, cid = bootstrap_contrast(arr.date.values, arr.real_sig.values, arr.A_r.values)
    g1 = bool(ci1[0] > 0)                                        # real_sig on A=1 > 0
    g2 = bool(cid[0] > 0)                                        # A=1 − A=0 contrast > 0
    folds_with_A1 = int(r[r.A == 1].fold.nunique())
    g3 = bool(folds_with_A1 >= 5)                                # coverage
    _, cid_s = bootstrap_contrast(arr.date.values, arr.ic_s.values, arr.A_r.values)
    g4 = bool(not (cid_s[0] > 0))                                # within-A placebo (shuffle ICs)
    import hashlib as _h
    base.update({
        "admissible": True,
        "features_sha256": _h.sha256(json.dumps(FEATS).encode()).hexdigest(),
        "bootstrap": {"algo": "stationary-geometric", "mean_block": BLOCK,
                      "n_resamples": NBOOT, "seed": 99},
        "mean_real_sig_A1": round(float(rs[rs.A_r == 1].real_sig.mean()), 4),
        "mean_real_sig_A0": round(float(rs[rs.A_r == 0].real_sig.mean()), 4),
        "ci_A1": [round(float(x), 4) for x in ci1],
        "ci_contrast": [round(float(x), 4) for x in cid],
        "folds_with_A1": folds_with_A1,
        "gates": [g1, g2, g3, g4],
        "gate_arithmetic": "PASS" if all([g1, g2, g3, g4]) else "KILL",
        "admissible_verdict": None, "artifact_kind": None})
    return base


def synthetic(seed=7):
    """One planted dataset: ROC60 dispersion is HIGH in monthly super-blocks
    (6 months each), and the label carries signal ONLY in those high-dispersion
    months. A slow-state activation should recover the gate (positive control);
    shuffling the month labels should destroy it (null control)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2016-01-04", "2026-05-07")
    tick = [f"T{i:03d}" for i in range(60)]
    n = len(dates) * len(tick)
    dstr = dates.strftime("%Y-%m-%d")
    df = pd.DataFrame({"date": np.repeat(dstr, len(tick)),
                       "ticker": np.tile(tick, len(dates))})
    ym = pd.Series(dates.strftime("%Y-%m"))
    uniq_months = list(dict.fromkeys(ym.tolist()))
    block = {m: ((i // 6) % 2) for i, m in enumerate(uniq_months)}   # 1 = high-dispersion super-block
    hi_by_date = ym.map(block).values                               # per calendar day
    hi = np.repeat(hi_by_date, len(tick))                           # per row
    for c in FEATS:
        if c == SLOW_FEAT:
            df[c] = rng.normal(size=n) * np.where(hi == 1, 2.5, 0.8)
        else:
            df[c] = rng.normal(size=n)
    f = 0.6 * df["RANK60"].values + 0.4 * df["SUMP20"].values
    noise = rng.normal(scale=1.0, size=n)
    df[LABEL] = 0.35 * f * hi.astype(float) + noise                 # signal only in high-dispersion months
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", choices=["positive", "null"])
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--stage", choices=["E"], default="E",
        help="C is NOT invocable here: Stage-C gate arithmetic requires the "
             "orch#939 extension corpus AND every month/clock guard; this "
             "harness version REFUSES C by construction (fail-closed) and a "
             "C-capable version is its own reviewed amendment")
    ap.add_argument("--confirm-966-merged", action="store_true")
    a = ap.parse_args()
    if a.real:
        if not a.confirm_966_merged:
            print("REFUSED: gated on the orch#966 slow-state design merge"); sys.exit(2)
        import ast as _ast, hashlib
        # the v2 harness defines CORPUS_SHA256 inside main(); read the pin from
        # its SOURCE via ast (the committed text is the authority — same pattern
        # as the condact/v2 verifiers), not from module attributes
        _pin = None
        _src = "/Users/renhao/git/github/renquant-model/doc/design/frozen/2026-08-09-xgbmom-v2-harness.py"
        for _n in _ast.walk(_ast.parse(open(_src).read())):
            if isinstance(_n, _ast.Assign) and getattr(_n.targets[0], "id", "") == "CORPUS_SHA256":
                _pin = _ast.literal_eval(_n.value)
        assert _pin, "corpus pin not found in the v2 harness source"
        cp = "/Users/renhao/git/github/RenQuant/data/alpha158_291_fundamental_dataset.parquet"
        assert hashlib.sha256(open(cp, "rb").read()).hexdigest() == _pin, "corpus drifted from prereg pin"
        panel = pd.read_parquet(cp)
        panel["date"] = pd.to_datetime(panel["date"]).dt.strftime("%Y-%m-%d")
        r = gates(panel); r["artifact_kind"] = "result"; r["corpus_sha256"] = _pin
    else:
        r = gates(synthetic(), shuffle_months=(a.control == "null"))
        r["artifact_kind"] = "control"; r["corpus_sha256"] = None
    print(json.dumps(r, indent=1))
    if a.control == "positive": sys.exit(0 if r.get("gate_arithmetic") == "PASS" else 1)
    if a.control == "null":     sys.exit(0 if r.get("gate_arithmetic") == "KILL" else 1)
