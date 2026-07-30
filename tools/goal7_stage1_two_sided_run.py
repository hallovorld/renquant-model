#!/usr/bin/env python3
"""Execute the FROZEN prereg doc/research/2026-07-30-goal7-stage1-two-sided-tail-prereg.md.

ONE registered question: does the two-sided transform `u = |z_t(mom_12_1_tr)|`
capture what a linear rank statistic cancels?  Nothing is designed here: the
transform (§1), the estimand and estimator (§3), the volatility kill condition
(§4), the arms (§5), the positive control (§5.1), the self-checks (§6) and the
decision rule (§7) are all fixed in the document, and the partition is fixed by
**AMENDMENT 4**, which is the sole authoritative partition (A4.6 makes both
"AMENDMENT 3" sections non-executable).

    python3 tools/goal7_stage1_two_sided_run.py \
        --matrix   <sp>/mom-total-return/momentum_factor_matrix_tr.parquet \
        --tr       <sp>/mom-total-return/total_return_close.parquet \
        --out-dir  doc/research/data/2026-07-30-goal7-stage1-two-sided-tail

READ-ONLY on the umbrella corpus.  Writes only under --out-dir.  Aborts on any
input-pin mismatch, on a missing or malformed raw-input manifest, and on any
divergence from the A4.4 partition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, t as student_t

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import raw_input_manifest  # noqa: E402
# The sibling harness this study reuses verbatim: its within-date permutation
# and the self-check that PROVES that permutation rejects an unsorted frame
# (§6, bullet 1).  Importing rather than re-implementing is the point --
# a re-implementation would not be "the identical harness".
from momentum_total_return_run import (  # noqa: E402
    build_labels,
    per_date_z,
    selfcheck_shuffle,
    shuffle_within_date,
)

# ------------------------------------------------------------------ §2A pins --
PIN_MATRIX = "85c27fc1d5a56a4c585c03db22dc8be0123badfc83ef23e46cdd358c704eb35a"
PIN_TR = "8c23496ee351757ec1f953597f9705168542f67cc16f209385091bb60d741ac9"
MANIFEST = raw_input_manifest.MOMENTUM_TOTAL_RETURN_PIN

# --------------------------------------------- AMENDMENT 2 / AMENDMENT 4 pins --
BURN_BOUNDARY = pd.Timestamp("2021-10-08")   # A2.2: burned for this hypothesis
EVAL_START = pd.Timestamp("2016-12-29")      # A4.4
EVAL_END = pd.Timestamp("2021-04-19")        # A4.4
PIN_N_EVAL = 1082                            # A4.4
PIN_N_BLOCKS = 18                            # A4.4
PIN_REMAINDER = 2                            # A4.4
PIN_DROPPED_DATES = ["2021-04-16", "2021-04-19"]      # A4.4
PIN_BLOCK_SPAN_END = pd.Timestamp("2021-04-15")       # A4.4
PIN_EXCLUDED_BAND = (pd.Timestamp("2021-04-20"), pd.Timestamp("2021-10-07"))
PIN_T_STUDENT = 2.1098                       # A4.4, t_{0.975,17}

# ------------------------------------------------------------ §2A / §3 / §4 --
H = 120                    # label horizon, trading days (declared from theory)
BLOCK = 60                 # §3 non-overlapping contiguous block length
TOP_FRACTION = 0.10        # §3 k = round(0.10 * n)
MIN_NAMES = 20             # §2A per-date admissibility floor
N_PERM = 200               # §3 / §5 permutations
MIN_BLOCKS_VOID = 6        # §7 VOID floor
NULL_FALSE_PASS_CEILING = 0.10   # §5 validity ceiling
NONTAUT_MIN_CHANGED = 0.95       # §5.1 non-tautology check
VOL_COL = "vol_60_tr"            # §4: named against THIS corpus, not "STD60"
MOM_COL = "mom_12_1_tr"

# ------------------------------------------------------------------- §5.1 pc --
SEED_BASE = 20260730
ALPHA_PC = 2.0 * math.sin(math.pi * 0.05 / 6.0)   # 0.0523538966
PC_IC_TARGET, PC_IC_TOL = 0.05, 0.01

# ---------------------------------------------------------------------------
# WHICH LABEL IS PRIMARY -- a resolved ambiguity, PRE-COMMITTED HERE, BEFORE THE
# RUN, and disclosed in the results document.
#
# §3 says "the mean forward excess return of the top-k names by u minus the
# cross-sectional mean".  §0's motivating decile table, §4's quoted "+0.2534 SD"
# and the whole document's units are the programme's per-date z-scored label
# (model#110's `fwd_120_tr`).  Those are two different objects: the z-scored one
# reweights each date by 1/sd_t.  The document does not disambiguate.
#
# PRIMARY  = the per-date z-scored label, on the ground that it is the object
#            whose deciles §0 measured and the units every quoted number in the
#            document is in.
# SECONDARY= the raw excess-return label, reported in full alongside with its own
#            null and its own T_crit, so the choice is auditable and neither
#            reading is hidden.  It is NOT the registered primary.
# ---------------------------------------------------------------------------
LABEL_PRIMARY = "z"
LABEL_SECONDARY = "raw"


# ============================================================== plumbing =====
def check_pin(p: Path, want: str) -> str:
    d = hashlib.sha256(p.read_bytes()).hexdigest()
    if d != want:
        raise SystemExit(f"ABORT: {p.name} sha256={d} != §2A pin {want}")
    print(f"  {p.name}  sha256={d[:16]}…  PIN OK  ({p.stat().st_size:,} B)")
    return d


class Panel:
    """The admissible evaluation panel, sorted by (date, ticker), with the
    static index machinery every arm and every permutation reuses."""

    def __init__(self, df: pd.DataFrame):
        df = df.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)
        self.df = df
        self.date_code = pd.factorize(df["date"])[0].astype(np.int64)
        self.ticker_code = pd.factorize(df["ticker"].astype(str),
                                        sort=True)[0].astype(np.int64)
        _, self.starts, self.counts = np.unique(self.date_code,
                                                return_index=True,
                                                return_counts=True)
        self.n_dates = len(self.starts)
        self.dates = pd.DatetimeIndex(df["date"].to_numpy()[self.starts])
        self.k = np.maximum(1, np.round(self.counts * TOP_FRACTION)).astype(np.int64)
        # flattened "take the first k_g rows of each date's ordering" index
        self.sel_pos = np.concatenate(
            [self.starts[g] + np.arange(self.k[g]) for g in range(self.n_dates)])
        self.sel_starts = np.concatenate([[0], np.cumsum(self.k)[:-1]])

    # -- per-date reductions -------------------------------------------------
    def gmean(self, v: np.ndarray) -> np.ndarray:
        return np.add.reduceat(v, self.starts) / self.counts

    def gz(self, v: np.ndarray) -> np.ndarray:
        """Per-date cross-sectional z-score (ddof=1, matching pandas .std())."""
        mu = self.gmean(v)
        d = v - np.repeat(mu, self.counts)
        var = np.add.reduceat(d * d, self.starts) / (self.counts - 1)
        sd = np.sqrt(var)
        if not np.all(sd > 0):
            raise SystemExit("ABORT: a date has zero cross-sectional dispersion")
        return d / np.repeat(sd, self.counts)

    def order_desc(self, score: np.ndarray) -> np.ndarray:
        """Rank descending by `score` within date, ties by ASCENDING ticker (§4)."""
        return np.lexsort((self.ticker_code, -score, self.date_code))

    def top_spread(self, score: np.ndarray, label: np.ndarray) -> np.ndarray:
        """§3 estimand, per date: mean(label | top-k by score) - mean(label)."""
        if np.isnan(score).any() or np.isnan(label).any():
            raise SystemExit("ABORT: NaN reached the estimand; §2A eligibility "
                             "forbids forward-fill and imputation, so a NaN here "
                             "is a plumbing defect, not a sample to drop.")
        order = self.order_desc(score)
        rows = order[self.sel_pos]
        top = np.add.reduceat(label[rows], self.sel_starts) / self.k
        return top - self.gmean(label)

    def residualise(self, u: np.ndarray, x: np.ndarray) -> np.ndarray:
        """§4: per-date OLS of u on x WITH AN INTERCEPT; return the residual."""
        mu, mx = self.gmean(u), self.gmean(x)
        du = u - np.repeat(mu, self.counts)
        dx = x - np.repeat(mx, self.counts)
        sxx = np.add.reduceat(dx * dx, self.starts)
        if not np.all(sxx > 0):
            raise SystemExit("ABORT: a date has zero variance in |z(vol_60_tr)|; "
                             "the §4 regression is undefined and is not silently "
                             "replaced by a demean.")
        b = np.add.reduceat(du * dx, self.starts) / sxx
        return du - np.repeat(b, self.counts) * dx


def block_t(per_date: np.ndarray, n_blocks: int) -> dict:
    """§3 estimator: contiguous non-overlapping 60-day blocks, remainder DROPPED,
    one-sample two-sided t over block means."""
    used = per_date[:n_blocks * BLOCK]
    bm = used.reshape(n_blocks, BLOCK).mean(axis=1)
    m, sd = float(bm.mean()), float(bm.std(ddof=1))
    tval = m / (sd / math.sqrt(n_blocks))
    return {"mean_per_date": float(per_date[:n_blocks * BLOCK].mean()),
            "block_mean": m, "block_sd": sd, "t": tval, "abs_t": abs(tval),
            "n_blocks": n_blocks, "block_means": [float(x) for x in bm]}


def normal_scores_asc(p: Panel, values: np.ndarray) -> np.ndarray:
    """Φ⁻¹((i-0.5)/n) on the ASCENDING within-date rank of `values`,
    ties broken by ascending ticker (§5.1 step 1)."""
    order = np.lexsort((p.ticker_code, values, p.date_code))
    pos = np.empty(len(values), dtype=np.int64)
    pos[order] = np.arange(len(values))
    i = pos - np.repeat(p.starts, p.counts)            # 0-based rank in date
    n = np.repeat(p.counts, p.counts)
    return norm.ppf((i + 0.5) / n)


def spearman_per_date(p: Panel, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Per-date Spearman correlation (Pearson on within-date ranks)."""
    ra = pd.Series(a).groupby(p.date_code).rank().to_numpy()
    rb = pd.Series(b).groupby(p.date_code).rank().to_numpy()
    za, zb = p.gz(ra), p.gz(rb)
    return np.add.reduceat(za * zb, p.starts) / (p.counts - 1)


# ================================================================== main =====
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", required=True, type=Path)
    ap.add_argument("--tr", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    a = ap.parse_args(argv)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    R: dict = {"prereg": "doc/research/2026-07-30-goal7-stage1-two-sided-tail-prereg.md",
               "authoritative_partition": "AMENDMENT 4 (A4.2/A4.4)"}

    # ------------------------------------------------------------- §6 checks --
    print("=" * 78)
    print("§6 SELF-CHECKS (each must pass or the screen VOIDs)")
    print("=" * 78)
    R["selfcheck_shuffle"] = selfcheck_shuffle()

    print("\n  raw-input manifest (refuses on MISSING or MALFORMED, not just "
          "mismatching):")
    raw_input_manifest.verify_or_abort(MANIFEST)
    man = json.loads(MANIFEST.read_text())
    R["raw_input_manifest"] = {
        "path": str(MANIFEST.relative_to(TOOLS.parent)),
        "corpus_fingerprint_sha256": man["corpus_index"]["root_digest_sha256"],
        "config_sha256": man["config"]["sha256"],
        "n_raw_inputs": man["universe"]["n"]}

    print("\n§2A INPUT PINS")
    R["pins"] = {"matrix": check_pin(a.matrix, PIN_MATRIX),
                 "tr": check_pin(a.tr, PIN_TR)}

    # ------------------------------------------------------------ the corpus --
    m = pd.read_parquet(a.matrix)
    m["date"] = pd.to_datetime(m["date"])
    tr = pd.read_parquet(a.tr)
    tr["date"] = pd.to_datetime(tr["date"])
    cal = pd.DatetimeIndex(np.sort(m["date"].unique()))
    print(f"\n  matrix rows={len(m):,} tickers={m.ticker.nunique()} "
          f"dates={len(cal)} {cal[0].date()}→{cal[-1].date()}")
    R["corpus"] = {"rows": int(len(m)), "tickers": int(m.ticker.nunique()),
                   "dates": int(len(cal)), "first": str(cal[0].date()),
                   "last": str(cal[-1].date())}

    # A4.3: the corpus's OWN trading-day index is the calendar of record.
    ok = [i for i in range(len(cal) - H) if cal[i + H] < BURN_BOUNDARY]
    last_eval = cal[max(ok)]
    print(f"\n  A4.2 rule — last t whose {H}th following corpus trading day "
          f"precedes the burn {BURN_BOUNDARY.date()}: {last_eval.date()} "
          f"(its {H}th following day is {cal[max(ok) + H].date()})")
    if last_eval != EVAL_END:
        raise SystemExit(f"ABORT: A4.2 cutoff resolves to {last_eval.date()}, "
                         f"not the pinned {EVAL_END.date()}. The corpus moved.")
    R["a4_2_cutoff"] = {"last_eval_date": str(last_eval.date()),
                        "its_120th_following_day": str(cal[max(ok) + H].date()),
                        "burn_boundary": str(BURN_BOUNDARY.date())}

    # ------------------------------------------------- §2A label + eligibility --
    print("\n§2A LABEL — forward 120-trading-day excess return vs SPY, both legs "
          "on the TOTAL-RETURN series")
    w = {t_: g.set_index("date").sort_index()
         for t_, g in tr.groupby("ticker", observed=True)}
    # Every ticker's own row index is contiguous in the corpus calendar, so a
    # 120-row forward shift IS a 120-trading-day forward window. Asserted, not
    # assumed (§2A "a complete 120-trading-day forward return").
    gapped = [t_ for t_, d in w.items()
              if not (np.diff(cal.get_indexer(d.index)) == 1).all()]
    if gapped:
        raise SystemExit(f"ABORT: {len(gapped)} ticker(s) have interior calendar "
                         f"gaps, so a 120-row shift is not a 120-trading-day "
                         f"window: {gapped[:5]}")
    print(f"  contiguity: 0 of {len(w)} tickers have interior calendar gaps "
          f"→ a 120-row forward shift is a complete 120-trading-day window")

    spy = w["SPY"]
    rows = []
    for t_, d in w.items():
        c = d["tr_close"]
        b = spy["tr_close"].reindex(c.index).ffill()
        rows.append(pd.DataFrame({
            "date": d.index, "ticker": t_,
            "fwd_raw": ((c.shift(-H) / c - 1.0).to_numpy()
                        - (b.shift(-H) / b - 1.0).to_numpy())}))
    lab = pd.concat(rows, ignore_index=True)
    lab["fwd_z"] = per_date_z(lab["fwd_raw"], lab["date"])

    # Identity check against model#110's own build_labels: the primary label must
    # be bit-for-bit the object §0's decile table was measured on.
    sib = build_labels(tr)[["date", "ticker", f"fwd_{H}_tr"]]
    chk = lab.merge(sib, on=["date", "ticker"], how="inner")
    both = chk["fwd_z"].notna() & chk[f"fwd_{H}_tr"].notna()
    dmax = float((chk.loc[both, "fwd_z"] - chk.loc[both, f"fwd_{H}_tr"]).abs().max())
    if not (both.sum() > 0 and dmax == 0.0):
        raise SystemExit(f"ABORT: primary label is not identical to model#110's "
                         f"fwd_{H}_tr (max|diff|={dmax})")
    print(f"  primary label == model#110 build_labels()['fwd_{H}_tr'] exactly "
          f"on {int(both.sum()):,} paired rows (max|diff|={dmax:.1e})")
    R["label_identity_vs_model110"] = {"paired_rows": int(both.sum()),
                                       "max_abs_diff": dmax}

    df = m[["date", "ticker", MOM_COL, VOL_COL]].merge(
        lab, on=["date", "ticker"], how="inner")
    elig = df.dropna(subset=[MOM_COL, VOL_COL, "fwd_raw", "fwd_z"]).copy()
    cnt = elig.groupby("date").size()
    keep = cnt[cnt >= MIN_NAMES].index
    elig = elig[elig["date"].isin(keep)]

    # ------------------------------------------------- A4.4 partition, checked --
    ev = elig[(elig["date"] >= EVAL_START) & (elig["date"] <= EVAL_END)].copy()
    p = Panel(ev)
    ev = p.df          # every column read below MUST come from the SORTED frame
    n_eval = p.n_dates
    n_blocks = n_eval // BLOCK
    remainder = n_eval % BLOCK
    dropped = [str(d.date()) for d in p.dates[n_blocks * BLOCK:]]
    band = elig[(elig["date"] >= PIN_EXCLUDED_BAND[0])
                & (elig["date"] <= PIN_EXCLUDED_BAND[1])]
    print("\n" + "=" * 78)
    print("A4.4 PARTITION — realised vs pinned")
    print("=" * 78)
    print(f"  {'quantity':<34}{'realised':>18}{'pinned':>16}")
    for nm, got, want in (("N_eval", n_eval, PIN_N_EVAL),
                          ("n_blocks", n_blocks, PIN_N_BLOCKS),
                          ("dropped remainder", remainder, PIN_REMAINDER)):
        print(f"  {nm:<34}{got:>18}{want:>16}"
              f"{'   MATCH' if got == want else '   ***DIVERGENT***'}")
    print(f"  {'eval window':<34}{str(p.dates[0].date()) + '→' + str(p.dates[-1].date()):>18}"
          f"{'2016-12-29→2021-04-19':>26}")
    print(f"  {'blocks span end':<34}"
          f"{str(p.dates[n_blocks * BLOCK - 1].date()):>18}"
          f"{str(PIN_BLOCK_SPAN_END.date()):>16}")
    print(f"  {'dropped dates':<34}{str(dropped):>18}{str(PIN_DROPPED_DATES):>16}")
    print(f"  admissible names per date: min={int(p.counts.min())} "
          f"median={int(np.median(p.counts))} max={int(p.counts.max())} "
          f"(A4.5 pinned min 126 / median 128; floor {MIN_NAMES})")
    print(f"  dates in window dropped by the <{MIN_NAMES}-name rule: "
          f"{int(((cnt[(cnt.index >= EVAL_START) & (cnt.index <= EVAL_END)]) < MIN_NAMES).sum())}")
    print(f"  excluded band (label would touch the burn): "
          f"{band['date'].nunique()} dates {PIN_EXCLUDED_BAND[0].date()}→"
          f"{PIN_EXCLUDED_BAND[1].date()}, {len(band):,} rows")
    R["partition"] = {
        "N_eval": int(n_eval), "N_eval_pinned": PIN_N_EVAL,
        "n_blocks": int(n_blocks), "n_blocks_pinned": PIN_N_BLOCKS,
        "dropped_remainder": int(remainder), "dropped_remainder_pinned": PIN_REMAINDER,
        "dropped_dates": dropped, "dropped_dates_pinned": PIN_DROPPED_DATES,
        "eval_first": str(p.dates[0].date()), "eval_last": str(p.dates[-1].date()),
        "blocks_span_end": str(p.dates[n_blocks * BLOCK - 1].date()),
        "names_per_date_min": int(p.counts.min()),
        "names_per_date_median": float(np.median(p.counts)),
        "names_per_date_max": int(p.counts.max()),
        "dates_dropped_by_min_names": int(
            ((cnt[(cnt.index >= EVAL_START) & (cnt.index <= EVAL_END)]) < MIN_NAMES).sum()),
        "excluded_band_dates": int(band["date"].nunique()),
        "excluded_band_rows": int(len(band)),
        "eval_rows": int(len(ev))}
    diverged = [nm for nm, got, want in
                (("N_eval", n_eval, PIN_N_EVAL), ("n_blocks", n_blocks, PIN_N_BLOCKS),
                 ("remainder", remainder, PIN_REMAINDER))if got != want]
    if diverged or dropped != PIN_DROPPED_DATES:
        raise SystemExit(f"ABORT (§3 mandatory check): the realised partition "
                         f"diverges from A4.4 ({diverged}, dropped={dropped}). "
                         f"The corpus moved and this is not the registered run.")
    if n_blocks < MIN_BLOCKS_VOID:
        R["verdict"] = "UNRESOLVED (underpowered)"
        (a.out_dir / "results.json").write_text(json.dumps(R, indent=2, default=str))
        print("\nVERDICT: UNRESOLVED (underpowered) — n_blocks < 6 (§7 / A3-b §A3.3)")
        return 0
    # §6 bullet 2: no undersized block exists.
    sizes = [BLOCK] * n_blocks
    if any(s != BLOCK for s in sizes) or n_blocks * BLOCK > n_eval:
        raise SystemExit("ABORT: an undersized block exists")
    print(f"  §6 no-undersized-block check: {n_blocks} blocks × {BLOCK} dates "
          f"= {n_blocks * BLOCK} used, {remainder} dropped (never equal-weighted) → PASS")

    t_student = float(student_t.ppf(0.975, n_blocks - 1))
    print(f"  t_{{0.975,{n_blocks - 1}}} = {t_student:.4f} "
          f"(A4.4 pins {PIN_T_STUDENT})")
    if round(t_student, 4) != PIN_T_STUDENT:
        raise SystemExit("ABORT: Student-t leg does not match the pinned 2.1098")

    # --------------------------------------------------------------- the arms --
    mom = ev[MOM_COL].to_numpy(float)
    vol = ev[VOL_COL].to_numpy(float)
    L = {"z": ev["fwd_z"].to_numpy(float), "raw": ev["fwd_raw"].to_numpy(float)}
    z_mom = p.gz(mom)
    u = np.abs(z_mom)                       # §1 THE REGISTERED TRANSFORM
    x_vol = np.abs(p.gz(vol))               # §4 |z_t(v)|, v = vol_60_tr
    u_resid = p.residualise(u, x_vol)       # §4 residual

    corr_u_x = float(np.corrcoef(u, x_vol)[0, 1])
    print(f"\n  §4 setup: corr(u, |z(vol_60_tr)|) = {corr_u_x:+.4f} pooled; "
          f"per-date OLS with intercept, residual arm = top decile by residual rank")

    # -------------------------------------------------------- §5.1 pos control --
    print("\n" + "=" * 78)
    print("§5.1 POSITIVE CONTROL — closed form, asserted, never re-calibrated")
    print("=" * 78)
    wpc = normal_scores_asc(p, L["raw"])
    g = np.empty(len(ev), dtype=float)
    for gi in range(p.n_dates):
        s, n = p.starts[gi], p.counts[gi]
        rng = np.random.default_rng(SEED_BASE + int(p.dates[gi].strftime("%Y%m%d")))
        g[s:s + n] = rng.random(n)
    e = normal_scores_asc(p, g)
    u_pc = ALPHA_PC * wpc + math.sqrt(1.0 - ALPHA_PC ** 2) * e
    ic_pc = spearman_per_date(p, u_pc, L["raw"])
    ic_mean = float(np.mean(ic_pc[:n_blocks * BLOCK]))
    print(f"  α = 2·sin(π·0.05/6) = {ALPHA_PC:.10f}; (6/π)·asin(α/2) = "
          f"{(6 / math.pi) * math.asin(ALPHA_PC / 2):.10f}")
    print(f"  realised mean per-date Spearman IC = {ic_mean:+.6f} "
          f"(target {PC_IC_TARGET}, tolerance ±{PC_IC_TOL})")
    pc_construction_ok = abs(ic_mean - PC_IC_TARGET) <= PC_IC_TOL
    print(f"  |mean − 0.05| = {abs(ic_mean - PC_IC_TARGET):.6f} → "
          f"{'PASS' if pc_construction_ok else 'FAIL → VOID'}")
    R["positive_control_construction"] = {
        "alpha": ALPHA_PC, "target_ic": PC_IC_TARGET, "tol": PC_IC_TOL,
        "realised_mean_ic": ic_mean, "abs_dev": abs(ic_mean - PC_IC_TARGET),
        "passes": bool(pc_construction_ok), "seed_base": SEED_BASE}

    # ------------------------------------------------------ nulls (200 perms) --
    print("\n" + "=" * 78)
    print(f"NULL CONTROL — {N_PERM} within-date permutations of u, through the "
          f"IDENTICAL harness")
    print("=" * 78)
    shuf_frame = pd.DataFrame({"u": u})
    shuf_frame["_dcode"] = p.date_code
    nulls: dict[str, dict[str, list]] = {}
    changed_frac = None
    for lb in (LABEL_PRIMARY, LABEL_SECONDARY):
        nulls[lb] = {"raw": [], "resid": []}
    for seed in range(N_PERM):
        up = shuffle_within_date(shuf_frame, seed, "u")
        upr = p.residualise(up, x_vol)
        for lb in (LABEL_PRIMARY, LABEL_SECONDARY):
            nulls[lb]["raw"].append(abs(block_t(p.top_spread(up, L[lb]),
                                                n_blocks)["t"]))
            nulls[lb]["resid"].append(abs(block_t(p.top_spread(upr, L[lb]),
                                                  n_blocks)["t"]))
        if seed == 0:
            # §5.1 non-tautology: the permutation must CHANGE the statistic
            base = p.top_spread(u, L[LABEL_PRIMARY])
            perm = p.top_spread(up, L[LABEL_PRIMARY])
            changed_frac = float(np.mean(base != perm))
    nontaut_ok = changed_frac >= NONTAUT_MIN_CHANGED
    print(f"  non-tautology: the permutation changes the per-date statistic on "
          f"{changed_frac:.4%} of dates (floor {NONTAUT_MIN_CHANGED:.0%}) → "
          f"{'PASS' if nontaut_ok else 'FAIL → VOID'}")
    R["non_tautology"] = {"frac_dates_changed": changed_frac,
                          "floor": NONTAUT_MIN_CHANGED, "passes": bool(nontaut_ok)}

    tcrit = {}
    for lb in (LABEL_PRIMARY, LABEL_SECONDARY):
        tcrit[lb] = {}
        for harness in ("raw", "resid"):
            arr = np.array(nulls[lb][harness], dtype=float)
            p95 = float(np.quantile(arr, 0.95))
            tc = max(p95, t_student)
            tcrit[lb][harness] = {
                "P95_null": p95, "t_student": t_student, "T_crit": tc,
                "binding_leg": "P95_null" if p95 >= t_student else "t_student",
                "null_mean": float(arr.mean()), "null_median": float(np.median(arr)),
                "null_max": float(arr.max()),
                "false_pass_rate_vs_Tcrit": float((arr >= tc).mean()),
                "false_pass_rate_vs_t_student": float((arr >= t_student).mean()),
                "all_abs_t": [float(v) for v in arr]}
    for harness in ("raw", "resid"):
        c = tcrit[LABEL_PRIMARY][harness]
        print(f"  [{harness:<5}] P95_null={c['P95_null']:.4f}  "
              f"t_0.975,{n_blocks - 1}={t_student:.4f}  → T_crit={c['T_crit']:.4f} "
              f"(bound by {c['binding_leg']})  "
              f"false-pass vs T_crit={c['false_pass_rate_vs_Tcrit']:.1%}  "
              f"vs t-leg={c['false_pass_rate_vs_t_student']:.1%}")
    R["T_crit"] = tcrit

    # ------------------------------------------------------------- every arm --
    print("\n" + "=" * 78)
    print("ARMS (primary label = per-date z-scored forward 120d excess return)")
    print("=" * 78)
    arms = {"treatment_u": ("raw", u),
            "treatment_u_residualised": ("resid", u_resid),
            "reference_z_mom": ("raw", z_mom),
            "positive_control_u_pc": ("raw", u_pc)}
    res: dict = {}
    for lb in (LABEL_PRIMARY, LABEL_SECONDARY):
        res[lb] = {}
        for nm, (harness, score) in arms.items():
            st = block_t(p.top_spread(score, L[lb]), n_blocks)
            c = tcrit[lb][harness]
            arr = np.array(nulls[lb][harness], dtype=float)
            st["harness"] = harness
            st["T_crit"] = c["T_crit"]
            st["binding_leg"] = c["binding_leg"]
            st["clears_T_crit"] = bool(st["abs_t"] >= c["T_crit"])
            st["null_quantile_of_abs_t"] = float((arr <= st["abs_t"]).mean())
            res[lb][nm] = st
    print(f"  {'arm':<28}{'harness':>8}{'spread':>11}{'|t|':>9}{'T_crit':>9}"
          f"{'clears':>8}{'null q':>9}")
    for nm in arms:
        s = res[LABEL_PRIMARY][nm]
        print(f"  {nm:<28}{s['harness']:>8}{s['block_mean']:>+11.4f}"
              f"{s['abs_t']:>9.3f}{s['T_crit']:>9.3f}{str(s['clears_T_crit']):>8}"
              f"{s['null_quantile_of_abs_t']:>9.3f}")
    R["arms"] = res

    # --------------------------------- §4 addendum: pooling within vol deciles --
    print("\n§4 addendum — residual statistic pooled WITHIN vol_60_tr deciles")
    dec = pd.Series(vol).groupby(p.date_code).rank(method="first", pct=True)
    dec = np.minimum((dec.to_numpy() * 10).astype(int), 9)
    pooled = {}
    for lb in (LABEL_PRIMARY, LABEL_SECONDARY):
        per_bucket = []
        for b in range(10):
            mask = dec == b
            sub = ev[mask]
            pb = Panel(sub.assign(_r=u_resid[mask]))
            s = pb.top_spread(pb.df["_r"].to_numpy(float),
                              pb.df["fwd_z" if lb == "z" else "fwd_raw"].to_numpy(float))
            per_bucket.append(pd.Series(s, index=pb.dates))
        avg = pd.concat(per_bucket, axis=1).mean(axis=1).reindex(p.dates)
        if avg.isna().any():
            raise SystemExit("ABORT: vol-decile pooling produced a missing date")
        st = block_t(avg.to_numpy(float), n_blocks)
        pooled[lb] = st
    ps = pooled[LABEL_PRIMARY]
    same_sign = (np.sign(ps["block_mean"])
                 == np.sign(res[LABEL_PRIMARY]["treatment_u_residualised"]["block_mean"]))
    print(f"  pooled-within-vol-decile residual spread = {ps['block_mean']:+.4f} "
          f"(|t|={ps['abs_t']:.3f}); full-cross-section residual "
          f"{res[LABEL_PRIMARY]['treatment_u_residualised']['block_mean']:+.4f} "
          f"→ sign preserved = {bool(same_sign)}")
    R["vol_decile_pooled_residual"] = {"stats": pooled,
                                       "sign_preserved": bool(same_sign)}

    # ------------------------------------------------------------ §7 verdict --
    print("\n" + "=" * 78)
    print("§7 VERDICT")
    print("=" * 78)
    lb = LABEL_PRIMARY
    pc = res[lb]["positive_control_u_pc"]
    raw_arm = res[lb]["treatment_u"]
    rsd_arm = res[lb]["treatment_u_residualised"]
    # Gate on BOTH harnesses' nulls (the stricter direction), not just the raw one.
    fp_rate = max(tcrit[lb][h]["false_pass_rate_vs_Tcrit"] for h in ("raw", "resid"))
    gates = {
        "positive_control_clears_T_crit": bool(pc["clears_T_crit"]),
        "positive_control_construction_ic_ok": bool(pc_construction_ok),
        # Read back from the recorded digests, NOT a literal True. check_pin()
        # already aborts on a mismatch, so this can only ever be True in a run
        # that completes -- but a gate whose value is a constant is the "guard
        # that validates the wrong object" shape, and a reader cannot tell the
        # difference between "checked" and "asserted" from the output.
        "input_digests_match": bool(R["pins"]["matrix"] == PIN_MATRIX
                                    and R["pins"]["tr"] == PIN_TR),
        "null_false_pass_rate_le_10pct": bool(fp_rate <= NULL_FALSE_PASS_CEILING),
        "non_tautology_ok": bool(nontaut_ok),
        "n_blocks_ge_6": bool(n_blocks >= MIN_BLOCKS_VOID)}
    for k, v in gates.items():
        print(f"  gate {k:<38} = {v}")
    if not all(gates.values()):
        verdict = ("VOID — " + ", ".join(k for k, v in gates.items() if not v)
                   + " failed (§7).")
    elif rsd_arm["clears_T_crit"]:
        verdict = (f"TWO-SIDED-SUPPORTED — the §4 residual arm |t|="
                   f"{rsd_arm['abs_t']:.3f} ≥ T_crit={rsd_arm['T_crit']:.3f}, "
                   f"controls valid. SCREEN-INTERESTING on a pre-2021 regime "
                   f"(A2.3); licenses ONLY writing the Stage-2 design.")
    elif raw_arm["clears_T_crit"]:
        verdict = (f"VOLATILITY-TILT — the raw arm clears (|t|="
                   f"{raw_arm['abs_t']:.3f} ≥ {raw_arm['T_crit']:.3f}) but the §4 "
                   f"residual does not (|t|={rsd_arm['abs_t']:.3f} < "
                   f"{rsd_arm['T_crit']:.3f}). The two-sided hypothesis is NOT "
                   f"supported. Nothing licensed.")
    else:
        verdict = (f"UNRESOLVED — neither the raw arm (|t|={raw_arm['abs_t']:.3f}) "
                   f"nor the §4 residual (|t|={rsd_arm['abs_t']:.3f}) reaches "
                   f"T_crit. Nothing licensed.")
    print("\n  " + verdict)
    print("\n  PUBLICATION DISCIPLINE (§8): this verdict is WITHHELD pending "
          "adversarial review.")
    R["gates"] = gates
    R["verdict"] = verdict
    R["verdict_status"] = "WITHHELD pending adversarial review (§8)"

    (a.out_dir / "results.json").write_text(json.dumps(R, indent=2, default=str))
    print(f"\nwrote {a.out_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
