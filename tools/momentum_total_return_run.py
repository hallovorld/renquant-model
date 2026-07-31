#!/usr/bin/env python3
"""Run the FROZEN prereg doc/research/2026-07-30-momentum-total-return-prereg.md.

ONE primary confirmatory test, declared from theory before execution:
`A1 = mom_12_1_tr` (12-1 formation on the DIVIDEND-ADJUSTED total-return
series), estimand E2 top-decile spread, holding horizon h = 120 trading days,
measured on 2021-10-08..2026-07-29. There is NO empirical horizon selection --
that is what biased the previous run.

    python3 tools/momentum_total_return_run.py \
        --matrix  <sp>/mom-total-return/momentum_factor_matrix_tr.parquet \
        --tr      <sp>/mom-total-return/total_return_close.parquet \
        --json-out <sp>/mom-total-return/results.json

Both inputs are pinned by sha256 and the run ABORTS on mismatch. Nothing is
written outside --json-out. No production path is read or written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
from renquant_model_common.lag_alignment import dependence_aware_mean  # noqa: E402

# ------------------------------------------------------------------ §3 pins --
PIN_MATRIX = "85c27fc1d5a56a4c585c03db22dc8be0123badfc83ef23e46cdd358c704eb35a"
PIN_TR = "8c23496ee351757ec1f953597f9705168542f67cc16f209385091bb60d741ac9"

# --------------------------------------------------- §2 the declared primary --
ARM_PRIMARY = "A1_mom_12_1_tr"
H_PRIMARY = 120                    # declared from theory, NOT selected
HORIZONS_DESCRIPTIVE = (20, 60, 120, 250)

SCREEN_END = pd.Timestamp("2021-07-14")
HOLDOUT_START = pd.Timestamp("2021-10-08")

TOP_FRACTION, MIN_NAMES = 0.10, 20
N_PLACEBO, PLACEBO_BAR = 5, 2.0
N_FALSE_FLAG = 40                  # >= the template's 40 and the required 30
N_BOOT_REAL, N_BOOT_CTRL = 2000, 600
MIN_BLOCKS = 8                     # §2 pre-declared block-count floor

SHADOW_T = 2.2414                  # Bonferroni m=2: SECOND use of this window
PROGRAMME_T = 3.1019               # Bonferroni m=26 programme-wide
BENCH_NOTE = "label legs both on the same series as the factor (TR vs TR, px vs px)"


# =========================================================== the shuffle ======
def shuffle_within_date(f: pd.DataFrame, seed: int, ycol: str) -> np.ndarray:
    """Permute `ycol` WITHIN each `_dcode` group, independent of row order.

    Correct on an INTERLEAVED frame: each output row keeps a label drawn from
    its OWN date's pool. Uses a direct per-group permutation.
    """
    rng = np.random.default_rng(seed)
    y = f[ycol].to_numpy(copy=True)
    for idx in f.groupby("_dcode").indices.values():
        y[idx] = y[rng.permutation(idx)]
    return y


def _shuffle_BROKEN_lexsort(f: pd.DataFrame, seed: int, ycol: str) -> np.ndarray:
    """THE DEFECT THAT INVALIDATED THE PREVIOUS RUN. Never called by the study.

    Kept in the file for ONE reason: to be the negative control that proves the
    self-check below can actually FAIL. A self-check that only ever exercises
    the correct implementation passes on the broken code too, which is exactly
    how the previous run shipped an invalid control.

    It sorts the frame into (_dcode, random) order and then writes that sorted
    sequence back into ORIGINAL row positions positionally -- a within-date
    permutation only if rows already arrive grouped by date.
    """
    rng = np.random.default_rng(seed)
    order = np.lexsort((rng.random(len(f)), f["_dcode"].to_numpy()))
    return f[ycol].to_numpy()[order]


def _interleaved_frame() -> pd.DataFrame:
    """A frame that is deliberately NOT date-contiguous."""
    dates = ["d1", "d2", "d1", "d2"]
    f = pd.DataFrame({"date": dates, "y": [10.0, 20.0, 11.0, 21.0]})
    f["_dcode"] = pd.factorize(f["date"])[0]
    return f


def _big_interleaved_frame() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    d = np.repeat([f"d{i}" for i in range(7)], 11)
    rng.shuffle(d)                                   # interleave hard
    f = pd.DataFrame({"date": d, "y": np.arange(len(d), dtype=float)})
    f["_dcode"] = pd.factorize(f["date"])[0]
    return f


def _pools_respected(f: pd.DataFrame, out: np.ndarray) -> bool:
    """Every row's new label must come from its OWN date's label pool."""
    dv, yv = f["date"].to_numpy(), f["y"].to_numpy()
    for d in np.unique(dv):
        m = dv == d
        if not set(out[m]).issubset(set(yv[m])):
            return False
    return True


def _is_within_group_permutation(f: pd.DataFrame, out: np.ndarray) -> bool:
    dv, yv = f["date"].to_numpy(), f["y"].to_numpy()
    for d in np.unique(dv):
        m = dv == d
        if sorted(out[m]) != sorted(yv[m]):
            return False
    return True


def selfcheck_shuffle() -> dict:
    """§4 SELF-CHECK. Runs on INTERLEAVED frames and is PROVEN to reject the
    unsorted-frame implementation. Aborts the run on any failure."""
    print("SELF-CHECK — the within-date shuffle (Defect 1 of the aborted run)")
    small, big = _interleaved_frame(), _big_interleaved_frame()
    rep = {}

    # (a) the FIXED implementation must PASS on interleaved frames
    for nm, fr in (("4-row reproducer", small), ("77-row shuffled", big)):
        for seed in range(6):
            out = shuffle_within_date(fr, seed, "y")
            if not _pools_respected(fr, out):
                raise SystemExit(f"ABORT: fixed shuffle leaked on {nm} seed={seed}")
            if not _is_within_group_permutation(fr, out):
                raise SystemExit(f"ABORT: fixed shuffle not a permutation, {nm}")
    a = shuffle_within_date(big, 0, "y")
    b = shuffle_within_date(big, 1, "y")
    if np.array_equal(a, b):
        raise SystemExit("ABORT: shuffle ignores the seed")
    rep["fixed_passes_interleaved"] = True
    print("  (a) fixed impl: pools respected + within-group permutation + "
          "seed-sensitive on BOTH interleaved frames  -> PASS")

    # (b) THE CHECK MUST BE ABLE TO FAIL. Prove it rejects the broken impl.
    leaked_small = [s for s in range(6)
                    if not _pools_respected(small, _shuffle_BROKEN_lexsort(small, s, "y"))]
    leaked_big = [s for s in range(6)
                  if not _pools_respected(big, _shuffle_BROKEN_lexsort(big, s, "y"))]
    if not leaked_small or not leaked_big:
        raise SystemExit(
            "ABORT: the self-check FAILED TO REJECT the known-broken shuffle, so "
            "it is not a check. Refusing to run.")
    rep["broken_rejected_seeds_small"] = leaked_small
    rep["broken_rejected_seeds_big"] = leaked_big
    print(f"  (b) known-broken lexsort impl REJECTED on seeds {leaked_small} "
          f"(4-row) and {leaked_big} (77-row)  -> the check discriminates")

    # (c) the exact reproducer from the PR #105 review
    out0 = _shuffle_BROKEN_lexsort(small, 0, "y")
    print(f"  (c) PR#105 reproducer: dates [d1,d2,d1,d2] labels [10,20,11,21]")
    print(f"      broken -> {list(out0)}   (row 1 is d2 and must not hold 10/11)")
    print(f"      fixed  -> {list(shuffle_within_date(small, 0, 'y'))}")
    rep["reproducer_broken_output"] = [float(x) for x in out0]
    rep["reproducer_fixed_output"] = [float(x) for x in shuffle_within_date(small, 0, "y")]
    return rep


# ============================================================ plumbing ========
def check_pin(p: Path, want: str, allow: bool) -> str:
    d = hashlib.sha256(p.read_bytes()).hexdigest()
    if d == want:
        print(f"  {p.name}  sha256={d[:16]}…  PIN OK  ({p.stat().st_size:,} B)")
    elif allow:
        print(f"  WARNING pin mismatch {p.name}: {d}")
    else:
        raise SystemExit(f"ABORT: {p.name} sha256={d} != pinned {want}")
    return d


def per_date_z(v: pd.Series, keys) -> pd.Series:
    g = v.groupby(keys)
    return (v - g.transform("mean")) / g.transform("std").replace(0.0, np.nan)


def build_labels(tr: pd.DataFrame) -> pd.DataFrame:
    """§4 label. fwd_h_excess vs SPY, per-date cross-sectional z-score.

    Built TWICE: `_tr` (both legs on the total-return series) and `_px` (both
    legs on raw price). Mixing legs would smuggle the dividend back in.
    """
    w = {t: g.set_index("date").sort_index() for t, g in tr.groupby("ticker", observed=True)}
    spy = w["SPY"]
    rows = []
    for t, d in w.items():
        rec = {"date": d.index, "ticker": t}
        for sfx, col in (("_tr", "tr_close"), ("_px", "close")):
            c = d[col]
            b = spy[col].reindex(c.index).ffill()
            for h in HORIZONS_DESCRIPTIVE:
                rec[f"fwd_{h}{sfx}"] = ((c.shift(-h) / c - 1.0).to_numpy()
                                        - (b.shift(-h) / b - 1.0).to_numpy())
        rows.append(pd.DataFrame(rec))
    lab = pd.concat(rows, ignore_index=True)
    for sfx in ("_tr", "_px"):
        for h in HORIZONS_DESCRIPTIVE:
            lab[f"fwd_{h}{sfx}"] = per_date_z(lab[f"fwd_{h}{sfx}"], lab["date"])
    return lab


def build_arms(m: pd.DataFrame) -> dict[str, pd.Series]:
    """§5. Arms over 9 distinct factor columns (operator cap: 10)."""
    d = m["date"]
    zm = per_date_z(m["mom_12_1_tr"], d)
    gate = m["vol_60_tr"] > m["vol_60_tr"].groupby(d).transform("median")
    a6 = pd.Series(np.nan, index=m.index, dtype=float)
    a6[gate] = zm[gate]
    a6[~gate & m["vol_60_tr"].notna() & m["mom_12_1_tr"].notna()] = 0.0
    return {
        # THE PRIMARY
        "A1_mom_12_1_tr": m["mom_12_1_tr"],
        # descriptive companions, screen only, no claim
        "A2_mom_6_1_tr": m["mom_6_1_tr"],
        "A3_hi52_prox_tr": m["hi52_prox_tr"],
        "A4_ma200_ratio_tr": m["ma200_ratio_tr"],
        "A5_vol_scaled_tr": m["mom_12_1_tr"] / m["vol_250_tr"].where(m["vol_250_tr"] > 0),
        "A6_vol_gated_tr": a6,
        "A7_sector_neutral_tr": per_date_z(m["mom_12_1_tr"], [d, m["sector"]]),
        # §5b naive single-column baseline + the price twin control
        "B1_div_yield_252": m["div_yield_252"],
        "C1_mom_12_1_px": m["mom_12_1_px"],
    }


def per_date_stats(f: pd.DataFrame, score: str, y: str):
    d = f["date"]
    f = f[d.groupby(d).transform("size") >= MIN_NAMES]
    d = f["date"]
    if f.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    rx = f[score].groupby(d).rank(pct=True)
    ry = f[y].groupby(d).rank(pct=True)
    g = pd.DataFrame({"d": d.values, "x": rx.values, "y": ry.values})
    g["xy"], g["xx"], g["yy"] = g.x * g.y, g.x ** 2, g.y ** 2
    s = g.groupby("d").agg(n=("x", "size"), sx=("x", "sum"), sy=("y", "sum"),
                           sxy=("xy", "sum"), sxx=("xx", "sum"), syy=("yy", "sum"))
    cov = s.sxy / s.n - (s.sx / s.n) * (s.sy / s.n)
    e1 = (cov / np.sqrt((s.sxx / s.n - (s.sx / s.n) ** 2)
                        * (s.syy / s.n - (s.sy / s.n) ** 2))
          ).replace([np.inf, -np.inf], np.nan).dropna()
    rd = f[score].groupby(d).rank(ascending=False, method="first")
    k = np.maximum(1, np.round(f[score].groupby(d).transform("size") * TOP_FRACTION))
    t = f[y].groupby([d, rd <= k]).mean().unstack()
    if True not in t.columns or False not in t.columns:
        return e1, pd.Series(dtype=float)
    return e1, (t[True] - t[False]).dropna()


def agg(s: pd.Series, block: int, n_boot: int) -> dict:
    if len(s) < 3:
        return {"n": len(s), "mean": float("nan"), "t": float("nan"),
                "ci_low": float("nan"), "ci_high": float("nan"),
                "n_blocks": 0, "resolves": False}
    r = dependence_aware_mean(list(s.values), block_length=block, n_boot=n_boot)
    return {"n": int(len(s)), "mean": float(r.mean),
            "t": float("nan") if r.block_t is None else float(r.block_t),
            "ci_low": float(r.ci_low), "ci_high": float(r.ci_high),
            "n_blocks": int(r.n_blocks), "resolves": bool(r.resolves)}


def prep(sub: pd.DataFrame, arm: str, ycol: str) -> pd.DataFrame:
    """DROP nulls, then SORT BY DATE before anything touches the shuffle."""
    s = sub.dropna(subset=[arm, ycol]).sort_values(["date", "ticker"]).copy()
    s["_dcode"] = pd.factorize(s["date"])[0]
    return s


def measure(sub: pd.DataFrame, arm: str, ycol: str, block: int, *,
            controls: int = N_PLACEBO) -> dict:
    s = prep(sub, arm, ycol)
    if s.empty:
        return {}
    e1, e2 = per_date_stats(s, arm, ycol)
    out = {"rows": len(s), "E1": agg(e1, block, N_BOOT_REAL),
           "E2": agg(e2, block, N_BOOT_REAL)}
    if controls:
        c = []
        for seed in range(controls):
            sh = s.copy()
            sh[ycol] = shuffle_within_date(s, seed, ycol)
            _, x2 = per_date_stats(sh, arm, ycol)
            c.append(abs(agg(x2, block, N_BOOT_CTRL)["t"]))
        out["E2"]["ctl_max"] = float(np.nanmax(c))
        out["E2"]["ctl_all"] = [float(x) for x in c]
        out["placebos_clean"] = bool(np.nanmax(c) < PLACEBO_BAR)
    return out


def per_date_e2(sub: pd.DataFrame, arm: str, ycol: str) -> pd.Series:
    s = prep(sub, arm, ycol)
    return per_date_stats(s, arm, ycol)[1] if not s.empty else pd.Series(dtype=float)


def write_per_date_series(series_by_name: "dict[str, pd.Series]",
                          out_path: "str | Path",
                          paired: "pd.Series | None" = None,
                          provenance: "dict | None" = None) -> dict:
    """Persist the per-date statistic series this run already computed.

    WHY (GOAL-7 redesign §7, 2026-07-31). This runner COMPUTES per-date E2 via
    ``per_date_e2`` and then throws it away, keeping only summary JSON plus 10
    block means. That single omission is why the programme's own dependence
    assumption cannot be checked against its own data:

      * GOAL-4's Phase-0 screen persisted ``per_date_g_real.csv`` (508 rows), and
        that one file made a model-free, assumption-free dependence-preserving
        calibration possible — bootstrap the real series, no rho1 assumed.
      * Here the only handle is 10 block means, whose lag-1 autocorrelation has a
        standard error of 1/sqrt(10) = 0.316 — it cannot separate rho1 = 0 from
        rho1 = +0.5, i.e. it is underpowered by an order of magnitude against the
        effect it would need to detect.

    Costs one CSV (~16 KB at GOAL-4's size). Computes NOTHING new: every value
    written here is already produced by the run, so this cannot move a verdict.
    """
    import json as _json
    import pandas as _pd
    frame = _pd.DataFrame({k: v for k, v in series_by_name.items() if v is not None})

    # THE PAIRED CONTRAST IS THE ARTIFACT. Writing only `subject` and `baseline`
    # leaves the reader to re-derive `subj.index.intersection(base).- .dropna()`
    # themselves, and a different reconstruction gives a different calibration --
    # which is the whole thing this file exists to make reproducible. So the exact
    # series handed to `agg` is persisted as its own column, and the components are
    # kept beside it so the contrast can be checked rather than trusted.
    if paired is not None:
        frame = frame.join(paired.rename("paired_contrast"), how="outer")
    frame = frame.sort_index()
    frame.index.name = "date"
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out)

    meta = {
        "path": str(out),
        "columns": list(frame.columns),
        "n_rows": int(len(frame)),
        "n_paired": int(paired.notna().sum()) if paired is not None else 0,
        "first_date": str(frame.index.min()) if len(frame) else None,
        "last_date": str(frame.index.max()) if len(frame) else None,
        # Enough to interpret the CSV WITHOUT this source file. A research artifact
        # whose columns can only be decoded by reading the runner is not independent.
        "paired_contrast_definition": (
            "paired_contrast = subject - baseline on the intersection of their date "
            "indexes, NaN dropped. This is the exact series passed to agg(); do not "
            "re-derive it from the component columns."
        ),
        **(provenance or {}),
    }
    side = out.with_suffix(".meta.json")
    side.write_text(_json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    meta["sidecar"] = str(side)
    return meta


def holm(pairs: list[tuple[str, float]]) -> dict:
    """Holm-Bonferroni step-down over (name, |t|), normal approximation.

    Sort p ascending; reject while `p_i <= 0.05/(m-i)`; **at the first failure,
    STOP and reject nothing further** — that stopping rule is what makes Holm
    control FWER, and omitting it makes the procedure anti-conservative.

    BUGFIX, post-run and disclosed: the frozen revision computed
    `reject = (max p so far <= thr)`, which for ascending p reduces to the
    per-test condition `p_i <= thr_i` with NO step-down. That wrongly rejects a
    later test when an earlier one failed but the later one clears its own
    (larger) threshold — e.g. p = [0.001, 0.03, 0.04] wrongly rejected the third.
    It did NOT change this study's run: the only failing arm had the LARGEST p,
    so no test followed it and the outputs are identical (verified by re-running).
    """
    from math import erfc, sqrt
    p = [(n, erfc(abs(t) / sqrt(2))) for n, t in pairs]     # two-sided
    p.sort(key=lambda x: x[1])
    m, out, stopped = len(p), {}, False
    for i, (n, pv) in enumerate(p):
        thr = 0.05 / (m - i)
        if not stopped and pv > thr:
            stopped = True
        out[n] = {"p": pv, "threshold": thr, "reject": bool(not stopped)}
    return out


# ================================================================= main =======
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", required=True, type=Path)
    ap.add_argument("--tr", required=True, type=Path)
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--per-date-out", default=None,
                    help="CSV path for the per-date statistic series (GOAL-7 "
                         "redesign §7). Computes nothing new — persists what the "
                         "run already produced, so a later dependence-preserving "
                         "calibration needs no assumed rho1.")
    ap.add_argument("--allow-input-mismatch", action="store_true")
    ap.add_argument("--smoke", action="store_true",
                    help="exercise every code path on SCREEN dates with tiny "
                         "bootstraps; NEVER touches the primary or the holdout")
    a = ap.parse_args(argv)
    R: dict = {}

    R["selfcheck"] = selfcheck_shuffle()

    print("\n§3 INPUTS")
    R["pins"] = {"matrix": check_pin(a.matrix, PIN_MATRIX, a.allow_input_mismatch),
                 "tr": check_pin(a.tr, PIN_TR, a.allow_input_mismatch)}

    m = pd.read_parquet(a.matrix)
    m["date"] = pd.to_datetime(m["date"])
    tr = pd.read_parquet(a.tr)
    tr["date"] = pd.to_datetime(tr["date"])
    print(f"  matrix rows={len(m):,} tickers={m.ticker.nunique()} "
          f"{m.date.min().date()}->{m.date.max().date()}")

    print("\n§4 LABEL (built here from the pinned TR series)")
    lab = build_labels(tr)
    for sfx in ("_tr", "_px"):
        for h in HORIZONS_DESCRIPTIVE:
            s = lab[f"fwd_{h}{sfx}"]
            print(f"  fwd_{h:<3}{sfx}  non-null={s.notna().mean():.3f} "
                  f"mean={s.mean():+.5f} sd={s.std():.4f}")
    print(f"  -> per-date z-scored. UNITS ARE SD OF THE CROSS-SECTION, NOT RETURN.")
    print(f"  -> {BENCH_NOTE}")

    df = m.merge(lab, on=["date", "ticker"], how="inner")
    for k, v in build_arms(df).items():
        df[k] = v
    screen = df[df.date <= SCREEN_END]
    hold = df[df.date >= HOLDOUT_START]
    print(f"\n  screen rows={len(screen):,} dates={screen.date.nunique()} | "
          f"holdout rows={len(hold):,} dates={hold.date.nunique()} | "
          f"embargo discarded={len(df)-len(screen)-len(hold):,}")
    nb = hold.date.nunique() // H_PRIMARY
    print(f"  §2 block-count floor: holdout gives {nb} blocks of {H_PRIMARY} "
          f"(floor {MIN_BLOCKS}) -> {'OK' if nb >= MIN_BLOCKS else 'VOID'}")
    R["n_blocks_primary"] = int(nb)
    if nb < MIN_BLOCKS:
        print("  ABORT per §6: below the pre-declared block floor.")
        R["verdict"] = "VOID — below the declared block-count floor"
        if a.json_out:
            Path(a.json_out).write_text(json.dumps(R, indent=2, default=str))
        return 0

    if a.smoke:
        print("\n=== SMOKE (screen dates, tiny bootstrap, primary NOT computed) ===")
        s = measure(screen, ARM_PRIMARY, f"fwd_{H_PRIMARY}_tr", H_PRIMARY, controls=2)
        print(f"  screen path OK: rows={s['rows']:,} n_dates={s['E2']['n']} "
              f"blocks={s['E2']['n_blocks']} placebos={len(s['E2']['ctl_all'])}")
        b = measure(screen, "B1_div_yield_252", f"fwd_{H_PRIMARY}_tr", H_PRIMARY, controls=1)
        print(f"  baseline path OK: rows={b['rows']:,}")
        print(f"  holm() OK: {list(holm([('x', 3.0), ('y', 1.0)]).keys())}")
        print("  SMOKE PASSED. The holdout and the primary were not touched.")
        return 0

    # ---------------------------------------------------------- §5 PRIMARY ----
    ycol = f"fwd_{H_PRIMARY}_tr"
    print("\n" + "=" * 78)
    print(f"PRIMARY CONFIRMATORY TEST — {ARM_PRIMARY} @ h={H_PRIMARY}, "
          f"estimand E2, holdout {HOLDOUT_START.date()}..{hold.date.max().date()}")
    print("  (horizon DECLARED FROM THEORY in the frozen text; no selection)")
    print("=" * 78)
    pr = measure(hold, ARM_PRIMARY, ycol, H_PRIMARY)
    e2 = pr["E2"]
    print(f"  E2 spread   = {e2['mean']:+.4f} SD")
    print(f"  block t     = {e2['t']:+.3f}  on {e2['n_blocks']} blocks of {H_PRIMARY}")
    print(f"  bootstrap CI= [{e2['ci_low']:+.4f}, {e2['ci_high']:+.4f}]")
    print(f"  three views agree (resolves) = {e2['resolves']}")
    print(f"  placebos max|t| = {e2['ctl_max']:.2f} (bar {PLACEBO_BAR}) "
          f"clean={pr['placebos_clean']}  all={[round(x,2) for x in e2['ctl_all']]}")
    print(f"  E1 IC t     = {pr['E1']['t']:+.3f}  (secondary, registered)")
    R["primary"] = pr

    # -------------------------------- §5 corpus false-flag rate (clean nulls) --
    print("\n" + "=" * 78)
    print(f"CONTROL CALIBRATION — {N_FALSE_FLAG} CLEAN within-date shuffles of "
          f"the primary arm/horizon")
    print("=" * 78)
    s = prep(hold, ARM_PRIMARY, ycol)
    ff = []
    for seed in range(N_FALSE_FLAG):
        sh = s.copy()
        sh[ycol] = shuffle_within_date(s, 1000 + seed, ycol)
        _, x2 = per_date_stats(sh, ARM_PRIMARY, ycol)
        ff.append(abs(agg(x2, H_PRIMARY, N_BOOT_CTRL)["t"]))
    ff = np.array(ff, dtype=float)
    rate = float((ff >= PLACEBO_BAR).mean())
    r30 = float((ff[:30] >= PLACEBO_BAR).mean())
    print(f"  n={len(ff)}  |t| mean={ff.mean():.2f} p50={np.median(ff):.2f} "
          f"p95={np.quantile(ff,0.95):.2f} max={ff.max():.2f}")
    print(f"  FALSE-FLAG RATE at the |t|>={PLACEBO_BAR} bar: {rate:.1%} "
          f"({int((ff>=PLACEBO_BAR).sum())}/{len(ff)})")
    print(f"  ... over the first 30 shuffles: {r30:.1%}")
    print(f"  a bar is decorative if this exceeds ~10%")
    R["false_flag"] = {"n": len(ff), "rate": rate, "rate_first30": r30,
                       "mean": float(ff.mean()), "p95": float(np.quantile(ff, .95)),
                       "max": float(ff.max()), "all": [float(x) for x in ff]}

    # -------------------------------------------------- §5b NAIVE BASELINE ----
    print("\n" + "=" * 78)
    print("§5b NAIVE-BASELINE ARM — is this momentum, or the dividend-yield "
          "column it was built from?")
    print("=" * 78)
    b1 = measure(hold, "B1_div_yield_252", ycol, H_PRIMARY, controls=N_PLACEBO)
    print(f"  B1 div_yield_252 (long high): E2={b1['E2']['mean']:+.4f} "
          f"t={b1['E2']['t']:+.3f} clean={b1['placebos_clean']}")

    subj = per_date_e2(hold, ARM_PRIMARY, ycol)
    base = per_date_e2(hold, "B1_div_yield_252", ycol)
    common = subj.index.intersection(base.index)
    dpair = (subj.reindex(common) - base.reindex(common)).dropna()
    # Written AFTER dpair exists, so the file can carry the series actually tested
    # rather than the ingredients of one. The previous version wrote here, before
    # the intersection was formed.
    if a.per_date_out:
        R["per_date_series"] = write_per_date_series(
            {"subject": subj, "baseline": base}, a.per_date_out, paired=dpair,
            provenance={
                "subject_arm": ARM_PRIMARY,
                "baseline_arm": "B1_div_yield_252",
                "label_column": ycol,
                "label_horizon_trading_days": H_PRIMARY,
                "statistic": "per-date E2 (top-decile spread)",
                "matrix_sha256": R["pins"]["matrix"],
                "tr_sha256": R["pins"]["tr"],
            })
        print(f"  per-date series written: {R['per_date_series']['n_rows']} rows, "
              f"{R['per_date_series']['n_paired']} paired "
              f"-> {R['per_date_series']['path']}")
    pc = agg(dpair, H_PRIMARY, N_BOOT_REAL)
    print(f"  PAIRED contrast subject - baseline, same dates/blocks: "
          f"delta={pc['mean']:+.4f} t={pc['t']:+.3f} "
          f"CI=[{pc['ci_low']:+.4f},{pc['ci_high']:+.4f}] n={pc['n']}")

    # neutralised: per-date rank residual of the subject on the baseline
    s2 = prep(hold, ARM_PRIMARY, ycol)
    s2 = s2[s2["B1_div_yield_252"].notna()].copy()
    rx = s2[ARM_PRIMARY].groupby(s2["date"]).rank(pct=True)
    rb = s2["B1_div_yield_252"].groupby(s2["date"]).rank(pct=True)
    gg = pd.DataFrame({"d": s2["date"].values, "x": rx.values, "b": rb.values})
    st = gg.groupby("d").agg(mx=("x", "mean"), mb=("b", "mean"),
                             vb=("b", "var"), n=("b", "size"))
    cv = (gg.assign(xb=gg.x * gg.b).groupby("d")["xb"].mean()
          - st.mx * st.mb) * st.n / (st.n - 1)
    beta = (cv / st.vb).replace([np.inf, -np.inf], np.nan)
    s2["NEUT"] = (rx.values - (st.mx.reindex(gg.d).values
                  + beta.reindex(gg.d).values * (gg.b.values - st.mb.reindex(gg.d).values)))
    nt = measure(s2, "NEUT", ycol, H_PRIMARY, controls=N_PLACEBO)
    print(f"  NEUT (subject rank-orthogonalised to the baseline): "
          f"E2={nt['E2']['mean']:+.4f} t={nt['E2']['t']:+.3f} "
          f"clean={nt['placebos_clean']}")

    # conditional pooling: within baseline QUINTILES (n~145/date -> ~29/bucket)
    s3 = s2.copy()
    s3["q"] = s3.groupby("date")["B1_div_yield_252"].transform(
        lambda v: pd.qcut(v.rank(method="first"), 5, labels=False, duplicates="drop"))
    per = []
    for q, gq in s3.groupby("q"):
        e = per_date_stats(gq.assign(_dcode=pd.factorize(gq["date"])[0]),
                           ARM_PRIMARY, ycol)[1]
        if len(e):
            per.append(e.rename(f"q{int(q)}"))
    cond = pd.concat(per, axis=1).mean(axis=1).dropna() if per else pd.Series(dtype=float)
    cd = agg(cond, H_PRIMARY, N_BOOT_REAL)
    print(f"  COND (pooled WITHIN baseline quintiles, {len(per)} buckets): "
          f"E2={cd['mean']:+.4f} t={cd['t']:+.3f} "
          f"CI=[{cd['ci_low']:+.4f},{cd['ci_high']:+.4f}]")

    hb = holm([("paired_subject_minus_baseline", pc["t"]),
               ("neutralised", nt["E2"]["t"]), ("conditional_quintile", cd["t"])])
    print("  Holm-Bonferroni across the 3 registered §5b arms:")
    for k, v in hb.items():
        print(f"    {k:<32} p={v['p']:.4g} thr={v['threshold']:.4g} "
              f"reject_null={v['reject']}")
    R["baseline"] = {"B1": b1, "paired": pc, "neutralised": nt,
                     "conditional": cd, "holm": hb}

    # ------------------------------------- D1 the dividend-confound diagnostic --
    print("\n" + "=" * 78)
    print("D1 DATA DIAGNOSTIC (not a momentum claim) — was the prior run's")
    print("   monotone-with-horizon pattern a DIVIDEND TILT? Paired TR vs price.")
    print("=" * 78)
    print(f"  {'h':>5}{'E2 on TR':>12}{'E2 on price':>13}{'delta':>10}"
          f"{'delta t':>10}{'blocks':>8}")
    d1 = {}
    for h in HORIZONS_DESCRIPTIVE:
        a_ = per_date_e2(hold, ARM_PRIMARY, f"fwd_{h}_tr")
        b_ = per_date_e2(hold, "C1_mom_12_1_px", f"fwd_{h}_px")
        ci = a_.index.intersection(b_.index)
        dd = agg((a_.reindex(ci) - b_.reindex(ci)).dropna(), h, N_BOOT_REAL)
        d1[h] = {"tr": float(a_.reindex(ci).mean()), "px": float(b_.reindex(ci).mean()),
                 "delta": dd}
        print(f"  {h:>5}{a_.reindex(ci).mean():>+12.4f}{b_.reindex(ci).mean():>+13.4f}"
              f"{dd['mean']:>+10.4f}{dd['t']:>+10.2f}{dd['n_blocks']:>8}")
    print("  -> a LARGE positive delta means the price-only series was")
    print("     UNDERSTATING momentum; a delta ~0 means the dividend adjustment")
    print("     does not change the momentum conclusion either way.")
    R["D1"] = d1

    # ------------------------------------------- descriptive panel, SCREEN ----
    print("\n" + "=" * 78)
    print("DESCRIPTIVE PANEL — SCREEN dates only, TR series. §6 FORBIDS ANY")
    print("CLAIM FROM THIS TABLE. It selects nothing; the horizon was declared.")
    print("=" * 78)
    desc = {}
    arms = [k for k in build_arms(df) if k.startswith("A")]
    print(f"  {'arm':<22}{'h':>5}{'E2':>10}{'t':>8}{'ctl':>7}{'blocks':>8}")
    for arm in arms:
        for h in HORIZONS_DESCRIPTIVE:
            r = measure(screen, arm, f"fwd_{h}_tr", h, controls=3)
            if not r:
                continue
            desc[f"{arm}|{h}"] = r
            print(f"  {arm:<22}{h:>5}{r['E2']['mean']:>+10.4f}{r['E2']['t']:>+8.2f}"
                  f"{r['E2']['ctl_max']:>7.2f}{r['E2']['n_blocks']:>8}")
    R["descriptive_screen"] = desc

    # ------------------------------------------------------------ §6 verdict --
    print("\n" + "=" * 78)
    print("§6 VERDICT")
    print("=" * 78)
    t = abs(e2["t"])
    gates = {
        "placebos_clean": pr["placebos_clean"],
        "false_flag_rate_ok": rate <= 0.10,
        "three_views_agree": e2["resolves"],
        "beats_baseline_holm": hb["paired_subject_minus_baseline"]["reject"],
    }
    for k, v in gates.items():
        print(f"  gate {k:<24} = {v}")
    if not pr["placebos_clean"]:
        v = "VOID — the primary arm's placebos are not clean. Nothing licensed."
    elif rate > 0.10:
        v = (f"VOID — the control bar is decorative at this corpus geometry "
             f"(false-flag {rate:.0%} > 10%). Nothing licensed.")
    elif t < SHADOW_T:
        v = (f"UNRESOLVED — |t|={t:.2f} < {SHADOW_T} (Bonferroni m=2 for the "
             f"SECOND use of this window). A statement about POWER, never about "
             f"momentum. Nothing licensed.")
    elif not e2["resolves"]:
        v = "UNRESOLVED — the three views do not agree in sign. Nothing licensed."
    elif not gates["beats_baseline_holm"]:
        v = (f"UNRESOLVED / TILT-NOT-EXCLUDED — |t|={t:.2f} clears the bar but "
             f"the arm does NOT beat its naive dividend-yield baseline under the "
             f"paired Holm-corrected contrast (§5b.4). Nothing licensed.")
    elif t >= PROGRAMME_T:
        v = (f"RESOLVED at the programme bar ({PROGRAMME_T}) — SHADOW ONLY. "
             f"Promotion out of shadow needs its own registration on FORWARD dates.")
    else:
        v = (f"SHADOW-ELIGIBLE — |t|={t:.2f} >= {SHADOW_T}, placebos clean, three "
             f"views agree, beats the naive baseline. Licensed: build the model and "
             f"deploy to SHADOW ONLY. No capital, no sizing, no live path.")
    print("\n  " + v)
    print(f"\n  MULTIPLICITY, as registered: these are the SECOND use of "
          f"{HOLDOUT_START.date()}..{hold.date.max().date()}. The prior "
          f"(ABORTED/INVALID-CONTROL) run spent them on A2 mom_6_1 @ h=20. This "
          f"is not a virgin holdout and is not presented as one.")
    R["verdict"], R["gates"] = v, gates

    if a.json_out:
        Path(a.json_out).write_text(json.dumps(R, indent=2, default=str))
        print(f"\nwrote {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
