#!/usr/bin/env python3
"""FROZEN PREREG EXECUTION — doc/research/2026-07-30-goal4-phase0-ensemble-gain-prereg.md
(renquant-model#114). Executes §3-§6 LITERALLY against the sealed manifest
(§2.5, tools/goal4_phase0_manifest.py). Read-only over all corpora; writes
only under doc/research/data/2026-07-30-goal4-phase0-ensemble-gain/.

Members: prod_XGB (benchmark), certified_clf, PatchTST (§2).
Combination: per-date equal-weight average of cross-sectional RANKS (§3).
Estimand: g(t) = IC_ensemble(t) - IC_benchmark(t), paired Spearman IC vs the
SAME r_{t->t+h}, h=60 trading days (§4).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import goal4_phase0_manifest as gm  # noqa: E402

OUT_DIR = gm.OUT_DIR
MANIFEST_PATH = gm.MANIFEST_PATH

# ---- frozen prereg constants -----------------------------------------------
LABEL_COL = "fwd_60d_excess"
HORIZON = 60                 # §4 h = 60 trading days
BLOCK_LEN = 60                # §4 blocks of 60 trading days
N_PERM = 200                  # §4/§5.2 200 within-date permutations
ALPHA_POS = 0.0523538966      # §5.1 positive control mixing weight
SEED_BASE = 20260730          # §5.1 positive-control RNG seed base

# ---- disclosed implementation constants (NOT in the frozen text) ----------
MIN_NAMES = 20                 # minimum cross-section per date for a usable Spearman IC
PERM_SEED_BASE = 900101        # deterministic base for §4/§5.2 permutation RNGs


def log(msg: str) -> None:
    print(msg)
    with open(OUT_DIR / "run.log", "a") as f:
        f.write(msg + "\n")


# ============================================================== data loading
def load_label(manifest: dict) -> pd.DataFrame:
    a = manifest["artifacts"]["label_corpus"]
    p = gm.ROOT_LIVE / a["path"] if a["root"] == "ROOT_LIVE" else gm.ROOT_BUNDLES / a["path"]
    df = pd.read_parquet(p, columns=["ticker", "date", LABEL_COL])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df.rename(columns={LABEL_COL: "label"})


def load_score(manifest: dict, key: str, ticker_col: str, score_col: str, rename_to: str) -> pd.DataFrame:
    a = manifest["artifacts"][key]
    p = gm.ROOT_LIVE / a["path"] if a["root"] == "ROOT_LIVE" else gm.ROOT_BUNDLES / a["path"]
    df = pd.read_parquet(p, columns=["date", ticker_col, score_col])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.rename(columns={ticker_col: "ticker", score_col: rename_to})
    if df.duplicated(subset=["date", "ticker"]).any():
        df = df.drop_duplicates(subset=["date", "ticker"])
    return df


# ============================================================ matrix builder
def build_joined(manifest: dict):
    label = load_label(manifest)
    pt = load_score(manifest, "patchtst_score_panel", "ticker", "raw", "PatchTST")
    clf = load_score(manifest, "certified_clf_score_panel", "ticker", "raw", "certified_clf")
    xgb = load_score(manifest, "prod_xgb_score_panel", "name", "score", "prod_XGB")

    joined = label.merge(pt, on=["date", "ticker"], how="inner") \
                  .merge(clf, on=["date", "ticker"], how="inner") \
                  .merge(xgb, on=["date", "ticker"], how="inner")
    return joined


def per_date_matrices(joined: pd.DataFrame):
    """Returns dates (sorted DatetimeIndex) and, per date, arrays of
    ticker, label, and the 3 member scores -- restricted to dates with
    >= MIN_NAMES names (all 4 columns present by construction of the inner join)."""
    joined = joined.sort_values(["date", "ticker"]).reset_index(drop=True)
    counts = joined.groupby("date").size()
    ok_dates = counts[counts >= MIN_NAMES].index
    joined = joined[joined["date"].isin(ok_dates)]
    dates = pd.DatetimeIndex(sorted(joined["date"].unique()))
    by_date = {d: g for d, g in joined.groupby("date")}
    return dates, by_date, joined


# =============================================================== statistics
def spearman_ic(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2:
        return np.nan
    rho, _ = sstats.spearmanr(x, y)
    return float(rho)


def rank_avg(*score_arrays: np.ndarray) -> np.ndarray:
    """Per-date equal-weight average of cross-sectional RANKS (§3)."""
    ranks = [sstats.rankdata(s) for s in score_arrays]
    return np.mean(ranks, axis=0)


def compute_g_series(by_date: dict, dates: pd.DatetimeIndex, member_cols: list[str],
                      permute_seed: int | None = None, _require_sorted: bool = True) -> pd.Series:
    """g(t) = IC_ensemble(t) - IC_benchmark(t) for each date, where ensemble =
    equal-weight rank average of member_cols (which MUST include 'prod_XGB'),
    benchmark = prod_XGB alone. If permute_seed is not None, the SAME
    within-date random permutation is applied to ALL member score columns
    jointly (§4 "within-date permutations of the member scores"), preserving
    cross-member redundancy while breaking the score<->label pairing.

    `_require_sorted` asserts the pairing operates on a date-SORTED frame
    (self-check requirement, prereg §0.3-equivalent inherited from the
    PatchTST closure prereg): each date's rows are looked up by exact date
    key in `by_date`, so a caller cannot silently leak rows across dates --
    but the ORDER `dates` is iterated in must itself be sorted, since the
    permutation seed is derived from each date's own calendar value
    independent of iteration order, NOT from position. We assert monotonic
    dates defensively and prove the assertion fires (see
    self_check_date_sort_assertion_fires below)."""
    if _require_sorted:
        arr = pd.DatetimeIndex(dates)
        assert arr.is_monotonic_increasing, "compute_g_series requires a date-sorted `dates` index"
    out = {}
    for d in dates:
        g = by_date[d]
        y = g["label"].to_numpy()
        scores = {c: g[c].to_numpy() for c in member_cols}
        if permute_seed is not None:
            rng = np.random.default_rng(permute_seed * 1_000_003 + int(d.strftime("%Y%m%d")))
            perm = rng.permutation(len(y))
            scores = {c: v[perm] for c, v in scores.items()}
        ens = rank_avg(*[scores[c] for c in member_cols])
        ic_ens = spearman_ic(ens, y)
        ic_bench = spearman_ic(scores["prod_XGB"], y)
        out[d] = ic_ens - ic_bench
    return pd.Series(out).sort_index()


def block_t(g_series: pd.Series, block_len: int = BLOCK_LEN):
    """§4 estimator: non-overlapping contiguous blocks of `block_len` DATES
    over the admissible dates; n_blocks = floor(N/block_len); remainder
    DROPPED (never equal-weighted). One-sample two-sided t over block means."""
    s = g_series.dropna().sort_index()
    n_eval = len(s)
    n_blocks = n_eval // block_len
    dropped = n_eval - n_blocks * block_len
    if n_blocks < 1:
        return dict(n_eval=n_eval, n_blocks=0, dropped=dropped, mean=np.nan,
                    se=np.nan, t=np.nan, block_means=[])
    kept = s.iloc[: n_blocks * block_len]
    grp = np.arange(len(kept)) // block_len
    block_means = pd.Series(kept.values, index=grp).groupby(level=0).mean()
    assert len(block_means) == n_blocks
    assert all((pd.Series(kept.index).groupby(grp).size() == block_len))  # no undersized block
    m = float(block_means.mean())
    if n_blocks < 2:
        return dict(n_eval=n_eval, n_blocks=n_blocks, dropped=dropped, mean=m,
                     se=np.nan, t=np.nan, block_means=block_means.tolist())
    se = float(block_means.std(ddof=1) / np.sqrt(n_blocks))
    t = m / se if se > 0 else np.nan
    return dict(n_eval=n_eval, n_blocks=n_blocks, dropped=dropped, mean=m, se=se,
                t=t, block_means=block_means.tolist())


# ------------------------------------------------------- self-checks (pre-treatment)
def self_check_permutation_rejects_unsorted(by_date: dict, dates: pd.DatetimeIndex) -> bool:
    """Prove the harness's date-sortedness assertion (compute_g_series'
    `_require_sorted`) actually FIRES on an unsorted `dates` index, not just
    that it exists in the source. Note on design: compute_g_series looks up
    each date's rows by exact date KEY in `by_date` (never by position), so
    there is no positional-leak-across-dates class of bug to reproduce here
    (unlike a matrix harness indexed by row position, where date order
    determines row alignment) -- the permutation seed is also a pure
    function of the date value, not of iteration order. The self-check
    therefore targets the one place order-independence is NOT automatic:
    the explicit `is_monotonic_increasing` assertion added specifically as
    this safety net. We prove it is live, not decorative."""
    shuffled = pd.DatetimeIndex(list(dates[:5][::-1]))  # deliberately unsorted
    try:
        compute_g_series(by_date, shuffled, ["PatchTST", "certified_clf", "prod_XGB"])
        return False  # did NOT reject -- self-check FAILS
    except AssertionError:
        return True


# ============================================================ positive control
def build_positive_control(by_date: dict, dates: pd.DatetimeIndex):
    """§5.1 synthetic member, closed-form construction."""
    synth_ic = {}
    synth_scores = {}
    for d in dates:
        g = by_date[d]
        tickers = g["ticker"].to_numpy()
        y = g["label"].to_numpy()
        n = len(y)
        order = np.argsort(tickers)  # ascending ticker tie-break
        rank_y = np.empty(n)
        rank_y[order] = sstats.rankdata(y[order], method="ordinal")
        u = sstats.norm.ppf((rank_y - 0.5) / n)

        rng = np.random.default_rng(SEED_BASE + int(d.strftime("%Y%m%d")))
        v = rng.standard_normal(n)
        rank_v = np.empty(n)
        order_v = np.argsort(tickers)
        rank_v[order_v] = sstats.rankdata(v[order_v], method="ordinal")
        e = sstats.norm.ppf((rank_v - 0.5) / n)

        synthetic = ALPHA_POS * u + np.sqrt(1 - ALPHA_POS ** 2) * e
        synth_scores[d] = synthetic
        synth_ic[d] = spearman_ic(synthetic, y)
    return synth_scores, pd.Series(synth_ic).sort_index()


def compute_g_series_control(by_date: dict, dates: pd.DatetimeIndex, synth_scores: dict,
                              permute_seed: int | None = None) -> pd.Series:
    out = {}
    for d in dates:
        g = by_date[d]
        y = g["label"].to_numpy()
        xgb = g["prod_XGB"].to_numpy()
        synth = synth_scores[d]
        if permute_seed is not None:
            rng = np.random.default_rng(permute_seed * 1_000_003 + int(d.strftime("%Y%m%d")) + 7)
            perm = rng.permutation(len(y))
            xgb = xgb[perm]
            synth = synth[perm]
        ens = rank_avg(synth, xgb)
        ic_ens = spearman_ic(ens, y)
        ic_bench = spearman_ic(xgb, y)
        out[d] = ic_ens - ic_bench
    return pd.Series(out).sort_index()


# =============================================================== redundancy
def redundancy_table(by_date: dict, dates: pd.DatetimeIndex):
    pairs = [("PatchTST", "certified_clf"), ("PatchTST", "prod_XGB"), ("certified_clf", "prod_XGB")]
    rows = []
    per_pair_series = {p: [] for p in pairs}
    for d in dates:
        g = by_date[d]
        for a, b in pairs:
            rho = spearman_ic(g[a].to_numpy(), g[b].to_numpy())
            per_pair_series[(a, b)].append(rho)
    table = {}
    for p, vals in per_pair_series.items():
        arr = np.array(vals, dtype=float)
        arr = arr[np.isfinite(arr)]
        table[f"{p[0]}_vs_{p[1]}"] = dict(mean=float(np.mean(arr)), p5=float(np.percentile(arr, 5)),
                                            p95=float(np.percentile(arr, 95)), n=int(len(arr)))
    return table


# ==================================================================== main
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "run.log").write_text("")  # fresh log this run

    if not MANIFEST_PATH.exists():
        log("REFUSE: sealed manifest missing (§2.5) -- not a bootstrap path.")
        return 1
    manifest = json.loads(MANIFEST_PATH.read_text())
    gm.verify(manifest)  # refuse-on-mismatch, before any statistic (§2.5)
    log(f"[manifest] VERIFIED root_digest={manifest['root_digest']}")

    joined = build_joined(manifest)
    dates, by_date, joined_flat = per_date_matrices(joined)
    log(f"[data] admissible dates after MIN_NAMES={MIN_NAMES} filter: {len(dates)} "
        f"({dates[0].date()} .. {dates[-1].date()}), rows={len(joined_flat)}, "
        f"tickers={joined_flat['ticker'].nunique()}")

    # ---------------------------------------------------- self-checks (pre-treatment)
    rejected = self_check_permutation_rejects_unsorted(by_date, dates)
    log(f"[self-check] date-sortedness assertion fires on a deliberately-unsorted "
        f"`dates` index (proves it is live, not decorative): {rejected}")
    if not rejected:
        log("VOID: self-check failed -- the assertion did not fire on unsorted input.")
        return 1

    # ----------------------------------------------------------- main estimator (§4)
    member_cols = ["PatchTST", "certified_clf", "prod_XGB"]
    g_real = compute_g_series(by_date, dates, member_cols)
    real_stats = block_t(g_real)
    log(f"[main] N_eval={real_stats['n_eval']} n_blocks={real_stats['n_blocks']} "
        f"dropped={real_stats['dropped']} mean(g)={real_stats['mean']:.5f} "
        f"t={real_stats['t']:.4f}")

    assert real_stats["n_blocks"] == real_stats["n_eval"] // BLOCK_LEN
    for bm in real_stats["block_means"]:
        assert np.isfinite(bm)
    log("[self-check] no undersized block in the retained partition: PASS "
        f"(every kept block has exactly {BLOCK_LEN} dates by construction)")

    # ----------------------------------------------- permutation null (§4 P95_null, §5.2, §5.3)
    log(f"[perm] running {N_PERM} within-date permutations ...")
    perm_ts = []
    non_taut_fracs = []
    for k in range(1, N_PERM + 1):
        g_perm = compute_g_series(by_date, dates, member_cols, permute_seed=PERM_SEED_BASE + k)
        st = block_t(g_perm)
        perm_ts.append(st["t"])
        diffs = (g_perm.reindex(g_real.index) - g_real).abs()
        non_taut_fracs.append(float((diffs > 1e-12).mean()))
    perm_ts = np.array(perm_ts, dtype=float)
    perm_ts_valid = perm_ts[np.isfinite(perm_ts)]
    P95_null = float(np.percentile(np.abs(perm_ts_valid), 95))
    t_crit_student = float(sstats.t.ppf(0.975, real_stats["n_blocks"] - 1)) if real_stats["n_blocks"] > 1 else np.nan
    T_crit = max(P95_null, t_crit_student) if np.isfinite(t_crit_student) else P95_null
    bound_leg = "P95_null" if P95_null >= t_crit_student else "student_t"
    log(f"[crit] P95_null={P95_null:.4f} t_0.975,{real_stats['n_blocks']-1}={t_crit_student:.4f} "
        f"T_crit={T_crit:.4f} (bound by {bound_leg})")

    obs_t = real_stats["t"]
    quantile_of_null = float((np.abs(perm_ts_valid) <= abs(obs_t)).mean()) if np.isfinite(obs_t) else np.nan
    log(f"[main] |t|={abs(obs_t):.4f} as a quantile of the null: {quantile_of_null:.4f}")

    false_pass_rate = float((np.abs(perm_ts_valid) >= T_crit).mean())
    log(f"[§5.2] null false-pass rate over {len(perm_ts_valid)} valid permutations: {false_pass_rate:.4f} "
        f"(ceiling 0.10)")

    non_taut_frac_mean = float(np.mean(non_taut_fracs))
    non_taut_frac_min = float(np.min(non_taut_fracs))
    log(f"[§5.3] non-tautology: mean frac of dates changed by permutation = {non_taut_frac_mean:.4f}, "
        f"min over {N_PERM} seeds = {non_taut_frac_min:.4f} (threshold >=0.95)")

    # ---------------------------------------------------------- positive control (§5.1)
    synth_scores, synth_ic_series = build_positive_control(by_date, dates)
    ctrl_mean_ic = float(synth_ic_series.mean())
    ctrl_construction_ok = abs(ctrl_mean_ic - 0.05) <= 0.01
    log(f"[§5.1] synthetic member realised mean per-date Spearman IC = {ctrl_mean_ic:.5f} "
        f"(target 0.05 +/- 0.01): construction {'OK' if ctrl_construction_ok else 'BROKEN -> VOID'}")

    g_ctrl_real = compute_g_series_control(by_date, dates, synth_scores)
    ctrl_stats = block_t(g_ctrl_real)
    log(f"[§5.1] control N_eval={ctrl_stats['n_eval']} n_blocks={ctrl_stats['n_blocks']} "
        f"dropped={ctrl_stats['dropped']} mean(g)={ctrl_stats['mean']:.5f} t={ctrl_stats['t']:.4f}")

    ctrl_perm_ts = []
    for k in range(1, N_PERM + 1):
        g_ctrl_perm = compute_g_series_control(by_date, dates, synth_scores, permute_seed=PERM_SEED_BASE + k)
        ctrl_perm_ts.append(block_t(g_ctrl_perm)["t"])
    ctrl_perm_ts = np.array(ctrl_perm_ts, dtype=float)
    ctrl_perm_valid = ctrl_perm_ts[np.isfinite(ctrl_perm_ts)]
    ctrl_P95_null = float(np.percentile(np.abs(ctrl_perm_valid), 95))
    ctrl_t_student = float(sstats.t.ppf(0.975, ctrl_stats["n_blocks"] - 1)) if ctrl_stats["n_blocks"] > 1 else np.nan
    ctrl_T_crit = max(ctrl_P95_null, ctrl_t_student) if np.isfinite(ctrl_t_student) else ctrl_P95_null
    ctrl_detected = bool(np.isfinite(ctrl_stats["t"]) and abs(ctrl_stats["t"]) >= ctrl_T_crit)
    log(f"[§5.1] control T_crit={ctrl_T_crit:.4f} (P95_null={ctrl_P95_null:.4f}, "
        f"t_0.975={ctrl_t_student:.4f}) observed|t|={abs(ctrl_stats['t']):.4f} "
        f"detected={ctrl_detected}")

    # --------------------------------------------------------------- redundancy (§5.4)
    redund = redundancy_table(by_date, dates)
    log(f"[§5.4] redundancy (descriptive only): {json.dumps(redund, indent=2)}")

    # -------------------------------------------------------------------- decision (§6)
    void_reasons = []
    if not ctrl_construction_ok:
        void_reasons.append("positive control construction broken (|mean-0.05|>0.01)")
    if not ctrl_detected:
        void_reasons.append("positive control NOT detected at |t|>=T_crit")
    if false_pass_rate > 0.10:
        void_reasons.append(f"null false-pass rate {false_pass_rate:.4f} > 0.10 ceiling")
    if non_taut_frac_min < 0.95:
        void_reasons.append(f"§5.3 non-tautology failed on >=1 seed (min frac changed={non_taut_frac_min:.4f})")
    n_survived_members = 3  # all 3 included per manifest (no exclusions)
    if n_survived_members < 2:
        void_reasons.append("fewer than 2 members survived the identity gate")

    if void_reasons:
        verdict = "VOID"
    elif real_stats["n_blocks"] < 6:
        verdict = "UNRESOLVED (underpowered)"
    elif np.isfinite(obs_t) and obs_t >= T_crit:
        verdict = "GO-PHASE-1"
    elif np.isfinite(obs_t) and obs_t <= -T_crit:
        verdict = "NO-GAIN"
    else:
        verdict = "UNRESOLVED"

    log(f"\n===== VERDICT (WITHHELD pending adversarial review, §7): {verdict} =====")
    if void_reasons:
        log("VOID reasons: " + "; ".join(void_reasons))

    results = {
        "prereg": "doc/research/2026-07-30-goal4-phase0-ensemble-gain-prereg.md (renquant-model#114)",
        "manifest_root_digest": manifest["root_digest"],
        "data": {"n_admissible_dates": len(dates), "first_date": str(dates[0].date()),
                 "last_date": str(dates[-1].date()), "min_names_per_date": MIN_NAMES,
                 "n_tickers": int(joined_flat["ticker"].nunique())},
        "self_checks": {
            "date_sortedness_assertion_fires_on_unsorted_input": rejected,
            "no_undersized_block": True,
        },
        "main": {
            "N_eval": real_stats["n_eval"], "n_blocks": real_stats["n_blocks"],
            "dropped_remainder_days": real_stats["dropped"], "mean_g": real_stats["mean"],
            "se": real_stats["se"], "t": real_stats["t"],
            "P95_null": P95_null, "t_crit_student": t_crit_student, "T_crit": T_crit,
            "T_crit_bound_by": bound_leg, "abs_t_quantile_of_null": quantile_of_null,
            "n_perm_valid": int(len(perm_ts_valid)), "n_perm_total": N_PERM,
        },
        "section_5_1_positive_control": {
            "realised_mean_ic": ctrl_mean_ic, "construction_ok": ctrl_construction_ok,
            "N_eval": ctrl_stats["n_eval"], "n_blocks": ctrl_stats["n_blocks"],
            "dropped_remainder_days": ctrl_stats["dropped"], "mean_g": ctrl_stats["mean"],
            "t": ctrl_stats["t"], "T_crit": ctrl_T_crit, "P95_null": ctrl_P95_null,
            "t_crit_student": ctrl_t_student, "detected": ctrl_detected,
        },
        "section_5_2_null_control": {
            "false_pass_rate": false_pass_rate, "ceiling": 0.10,
            "n_perm_valid": int(len(perm_ts_valid)),
        },
        "section_5_3_non_tautology": {
            "mean_frac_dates_changed": non_taut_frac_mean,
            "min_frac_dates_changed": non_taut_frac_min, "threshold": 0.95,
        },
        "section_5_4_redundancy_descriptive_only": redund,
        "verdict_WITHHELD_pending_adversarial_review": verdict,
        "void_reasons": void_reasons,
        "implementation_constants_not_in_frozen_text": {
            "MIN_NAMES": MIN_NAMES, "PERM_SEED_BASE": PERM_SEED_BASE,
            "permutation_construction": (
                "one shared random within-date permutation applied jointly to "
                "ALL member score columns per (seed, date), preserving cross-"
                "member redundancy while breaking score<->label pairing; "
                "mathematically equivalent to permuting the label vector once "
                "per (seed, date) for the resulting rank-correlation statistics"
            ),
        },
    }
    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True))

    g_real.rename("g").to_csv(OUT_DIR / "per_date_g_real.csv", header=True)
    synth_ic_series.rename("synthetic_ic").to_csv(OUT_DIR / "per_date_synthetic_control_ic.csv", header=True)
    g_ctrl_real.rename("g_control").to_csv(OUT_DIR / "per_date_g_positive_control.csv", header=True)

    log(f"\n[done] results written to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
