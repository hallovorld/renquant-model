#!/usr/bin/env python3
"""§1/§3/§3.5/§4/§6 estimator for the FROZEN prereg
doc/research/2026-07-30-patchtst-closure-prereg-v2.md ("model#113").

*** NOT EXECUTED AGAINST REAL DATA. DO NOT RUN THIS AGAINST PT_P AS WIRED. ***

This study VOIDed at §0.1 before any treatment statistic was computed — see
doc/research/2026-07-30-patchtst-closure-v2-void.md. `PT_P` below points at
the 43-fold walk-forward RESEARCH corpus
(/Users/renhao/renquant_bundles/patchtst-wf-corpus-b4e47e2c, via the derived
wf-eval/scores.parquet used in the prior model#90 corrected-eval line). That
corpus is DISQUALIFIED as the treatment's score source: none of its 43
checkpoints' sha256 match the digest the live shadow path actually serves
(verified — tools/patchtst_closure_v2_identity_check.py,
doc/research/data/2026-07-30-patchtst-closure-v2/checkpoint_sha256_scan.csv).
§0.1 requires the digest of the file the study loads to EQUAL what serving
emits; it does not, so no number this module could produce is a valid
answer to the estimand.

This file is retained ONLY as the frozen §1/§3/§3.5/§4/§6 estimator
implementation (unit-tested via tests/test_patchtst_closure_v2_selfchecks.py
against synthetic data), ready for reuse WHEN a historical PatchTST score
corpus becomes available that is BOTH (a) long enough in span for the §3
block estimator at L=60 (needs on the order of 120+ admissible trading days)
and (b) verified via execution-emitted digest to correspond to what the live
shadow path actually served over that span. As of this run, no such corpus
exists — see the VOID doc for what would have to change.

There is no `main()` / CLI entry point in this file by design: nothing here
should be runnable-by-accident against the disqualified corpus.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patchtst_closure_v2_lib as L  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "doc/research/data/2026-07-30-patchtst-closure-v2"

# ---- frozen prereg constants -------------------------------------------
LABEL_COL = "fwd_60d_excess"
H = 60                              # §1 horizon
GATE_LAG = 60                       # §1 "L = 60 is the only gate"
DESCRIPTIVE_LAGS = [20, 40, 80]     # §1 "descriptive only"
BLOCK_LEN = 60                      # §3
N_PERM_CRIT = 200                   # §3.5
N_PERM_VALIDITY = 40                # §4.2
FALSE_PASS_CEILING = 0.10           # §4.2
POSITIVE_CONTROL_THIN_T = 2.5       # §7 clause 2

# ---- data sources --------------------------------------------------------
# PANEL: labels. XGB_P: prod XGB scores (positive control, §4.1). PT_P: the
# PatchTST walk-forward score corpus this study uses as the treatment's score
# time series — see §0.1 identity note in the results doc for what this IS
# and is NOT established to be.
PANEL = "/Users/renhao/git/github/RenQuant/data/transformer_v4_wl200_clean.parquet"
XGB_P = "/Users/renhao/git/github/RenQuant/data/exp/oos_pick_table_recipe_v2.parquet"
PT_P = ("/private/tmp/claude-502/-Users-renhao-git-github-renquant-orchestrator"
        "/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/wf-eval/scores.parquet")

RNG_BASE = 20260730


# --------------------------------------------------------------- loading
def load_panel():
    p = pd.read_parquet(PANEL, columns=["ticker", "date", LABEL_COL])
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    return p


def load_pt():
    d = pd.read_parquet(PT_P)[["date", "ticker", "raw", "fold_idx"]]
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    return d.rename(columns={"raw": "score"})


def load_xgb():
    d = pd.read_parquet(XGB_P)[["date", "name", "score"]]
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    return d.rename(columns={"name": "ticker"})


def to_matrix(df, date_col, key_col, val_col, names, date_index):
    piv = df.pivot_table(index=date_col, columns=key_col, values=val_col, aggfunc="first")
    piv = piv.reindex(index=date_index, columns=names)
    return piv.values.astype(float)


# --------------------------------------------------------------- subject build
class Subject:
    """One arm's fully-aligned data: a (n_score_dates, n_names) score matrix
    on a sorted, positionally-contiguous score axis, plus the label matrix on
    the shared label axis."""

    def __init__(self, name, sdf, panel, label_axis, log):
        self.name = name
        cnt = sdf.groupby("date")["score"].apply(lambda s: s.notna().sum())
        self.score_axis = pd.DatetimeIndex(sorted(cnt[cnt >= L.MIN_NAMES].index))
        self.names = sorted(set(sdf["ticker"]) & set(panel["ticker"]))
        self.Smat = to_matrix(sdf, "date", "ticker", "score", self.names, self.score_axis)
        self.label_axis = label_axis
        self.Lmat = to_matrix(panel, "date", "ticker", LABEL_COL, self.names, label_axis)
        L.assert_score_axis_positionally_contiguous(self.score_axis, self.label_axis)
        log(f"[{name}] score_axis n={len(self.score_axis)} "
            f"[{self.score_axis[0].date()}..{self.score_axis[-1].date()}] "
            f"n_names={len(self.names)}")

    def rows_for(self, L_lag, h=H):
        """admissible dates + the three aligned row-index arrays needed to
        compute d(t): fresh score rows, stale score rows, label rows."""
        adm = L.admissible_dates(self.score_axis, self.label_axis, L_lag, h)
        adm = pd.DatetimeIndex(adm)
        sd_pos = self.score_axis.get_indexer(adm)
        assert (sd_pos >= 0).all()
        lab_pos = self.label_axis.get_indexer(adm)
        assert (lab_pos >= 0).all()
        fresh_rows = sd_pos
        stale_rows = sd_pos - L_lag
        label_rows = lab_pos + h
        return adm, fresh_rows, stale_rows, label_rows


# --------------------------------------------------------------- d(t) + block
def compute_d_series(Smat, Lmat, fresh_rows, stale_rows, label_rows):
    n = len(fresh_rows)
    ic_fresh = np.full(n, np.nan)
    ic_stale = np.full(n, np.nan)
    for i in range(n):
        yv = Lmat[label_rows[i]]
        ic_fresh[i], _ = L.spearman_ic(Smat[fresh_rows[i]], yv)
        ic_stale[i], _ = L.spearman_ic(Smat[stale_rows[i]], yv)
    return ic_fresh - ic_stale, ic_fresh, ic_stale


def permute_within_date(Smat: np.ndarray, seed: int) -> np.ndarray:
    """Independently permute the valid (non-NaN) entries of EACH ROW (date)
    of Smat across the ticker axis. Reused for both the "fresh" and "stale"
    role of a given date's score, because the whole matrix is permuted once
    per draw — this is what "the subject's scores, through the identical
    harness" means (§3.5, §4.2), not a fresh permutation per use."""
    out = Smat.copy()
    rng = np.random.default_rng(seed)
    for i in range(Smat.shape[0]):
        row = Smat[i]
        valid = np.isfinite(row)
        idx = np.where(valid)[0]
        if len(idx) < 2:
            continue
        perm = rng.permutation(idx)
        out[i, idx] = row[perm]
    return out


# --------------------------------------------------------------- main compute
def run_subject_gate_lag(subj: Subject, log, perm_seed_offset: int):
    """All §3/§3.5/§4 quantities for one subject at the GATE lag (60)."""
    adm, fresh_rows, stale_rows, label_rows = subj.rows_for(GATE_LAG)
    d_real, ic_fresh_real, ic_stale_real = compute_d_series(
        subj.Smat, subj.Lmat, fresh_rows, stale_rows, label_rows)
    bs_real = L.block_t(d_real, block_len=BLOCK_LEN)

    # §3.5: 200 within-date permutations -> null |t| distribution
    null_abs_t = []
    perm_draws_cache = []  # keep the d_perm arrays for §4.3 / reuse
    for k in range(N_PERM_CRIT):
        seed = RNG_BASE + perm_seed_offset * 100000 + k
        Sperm = permute_within_date(subj.Smat, seed)
        d_perm, icf_p, ics_p = compute_d_series(
            Sperm, subj.Lmat, fresh_rows, stale_rows, label_rows)
        bs_perm = L.block_t(d_perm, block_len=BLOCK_LEN)
        if np.isfinite(bs_perm.t):
            null_abs_t.append(abs(bs_perm.t))
        perm_draws_cache.append((d_perm, icf_p, ics_p))
    log(f"[{subj.name}] real block_t={bs_real.t:+.4f} n_blocks={bs_real.n_blocks} "
        f"N_eval={bs_real.n_eval} dropped={bs_real.dropped_remainder} "
        f"| 200-perm null |t|: mean={np.mean(null_abs_t):.3f} "
        f"p95={np.percentile(null_abs_t, 95):.3f} max={np.max(null_abs_t):.3f}")

    return dict(adm=adm, fresh_rows=fresh_rows, stale_rows=stale_rows,
                label_rows=label_rows, d_real=d_real, ic_fresh_real=ic_fresh_real,
                ic_stale_real=ic_stale_real, block_stat=bs_real,
                null_abs_t_200=null_abs_t, perm_draws_200=perm_draws_cache)


def false_pass_rate(subj: Subject, fresh_rows, stale_rows, label_rows,
                     t_crit: float, perm_seed_offset: int, log):
    """§4.2: 40 independent within-date permutations of THIS subject's
    scores; fraction reaching |t| >= t_crit."""
    hits = 0
    abst = []
    for k in range(N_PERM_VALIDITY):
        seed = RNG_BASE + perm_seed_offset * 100000 + 900000 + k
        Sperm = permute_within_date(subj.Smat, seed)
        d_perm, _, _ = compute_d_series(Sperm, subj.Lmat, fresh_rows, stale_rows, label_rows)
        bs = L.block_t(d_perm, block_len=BLOCK_LEN)
        if np.isfinite(bs.t):
            abst.append(abs(bs.t))
            if abs(bs.t) >= t_crit:
                hits += 1
    rate = hits / N_PERM_VALIDITY
    log(f"[{subj.name}] §4.2 measured false-pass rate over {N_PERM_VALIDITY} draws: "
        f"{rate:.3%} (ceiling 10%) mean|t|={np.mean(abst):.3f} "
        f"p95|t|={np.percentile(abst, 95):.3f} max|t|={np.max(abst):.3f}")
    return rate, abst


def tautology_check(subj: Subject, fresh_rows, ic_fresh_real, perm_draws_200, log):
    """§4.3: assert the permutation CHANGES IC_fresh on >=95% of dates,
    averaged over the 200 cached draws (more robust than a single seed)."""
    n = len(fresh_rows)
    changed_frac_per_draw = []
    for (d_perm, icf_p, ics_p) in perm_draws_200:
        diff = np.abs(icf_p - ic_fresh_real)
        ok = np.isfinite(diff)
        changed = (diff[ok] > 1e-9)
        changed_frac_per_draw.append(float(np.mean(changed)) if ok.sum() else float("nan"))
    mean_changed = float(np.nanmean(changed_frac_per_draw))
    passed = mean_changed >= 0.95
    log(f"[{subj.name}] §4.3 tautology check: mean fraction of dates with "
        f"IC_fresh changed by permutation = {mean_changed:.3%} "
        f"(need >=95%) -> {'PASS' if passed else 'FAIL'}")
    return passed, mean_changed


# --------------------------------------------------------------- §6 gates
def gate_6_1_leave_one_ticker_out(subj: Subject, fresh_rows, stale_rows, label_rows,
                                   t_crit: float, log):
    n_names = len(subj.names)
    signs, passes = [], []
    base_sign = None
    for j in range(n_names):
        Sm = subj.Smat.copy(); Sm[:, j] = np.nan
        Lm = subj.Lmat.copy(); Lm[:, j] = np.nan
        d, _, _ = compute_d_series(Sm, Lm, fresh_rows, stale_rows, label_rows)
        bs = L.block_t(d, block_len=BLOCK_LEN)
        if not np.isfinite(bs.t):
            continue
        signs.append(np.sign(bs.mean))
        passes.append(abs(bs.t) >= t_crit)
    ref_sign = np.sign(np.median(signs)) if signs else np.nan
    sign_frac = float(np.mean(np.array(signs) == ref_sign)) if signs else float("nan")
    pass_frac = float(np.mean(passes)) if passes else float("nan")
    ok = (sign_frac >= 0.95) and (pass_frac >= 0.90)
    log(f"6.1 leave-one-ticker-out: n_refits={len(signs)} sign_preserved={sign_frac:.1%} "
        f"(need>=95%) |t|>=T_crit={pass_frac:.1%} (need>=90%) -> {'HOLDS' if ok else 'FAILS'}")
    return dict(n_refits=len(signs), sign_preserved_frac=sign_frac,
                t_crit_cleared_frac=pass_frac, holds=ok)


def gate_6_2_median_location(d_real, t_crit, log):
    bs = L.block_t(d_real, block_len=BLOCK_LEN, agg="median")
    ok = (np.sign(bs.mean) == np.sign(np.median(d_real))) and (abs(bs.t) >= t_crit)
    # sign check vs the real (mean-based) block stat's own sign, more precisely:
    log(f"6.2 median location: mean={bs.mean:+.5f} t={bs.t:+.3f} (need |t|>=T_crit) "
        f"-> {'HOLDS' if abs(bs.t) >= t_crit else 'FAILS'}")
    return dict(mean=bs.mean, t=bs.t, n_blocks=bs.n_blocks,
                holds=bool(abs(bs.t) >= t_crit))


def gate_6_3_winsorized_label(subj: Subject, fresh_rows, stale_rows, label_rows,
                               t_crit: float, log):
    Lm = subj.Lmat.copy()
    for r in range(Lm.shape[0]):
        row = Lm[r]
        ok = np.isfinite(row)
        if ok.sum() < 2:
            continue
        mu, sd = np.nanmean(row[ok]), np.nanstd(row[ok])
        if sd > 0:
            Lm[r] = np.clip(row, mu - sd, mu + sd)
    d, _, _ = compute_d_series(subj.Smat, Lm, fresh_rows, stale_rows, label_rows)
    bs = L.block_t(d, block_len=BLOCK_LEN)
    ok = abs(bs.t) >= t_crit
    log(f"6.3 winsorized label (±1SD): mean={bs.mean:+.5f} t={bs.t:+.3f} "
        f"-> {'HOLDS' if ok else 'FAILS'}")
    return dict(mean=bs.mean, t=bs.t, n_blocks=bs.n_blocks, holds=bool(ok))


def gate_6_4_leave_one_block_out(d_real, t_crit, log, require_t_crit_every_refit=False):
    n_eval = len(d_real)
    blocks = L.block_partition_indices(n_eval, BLOCK_LEN)
    L.assert_no_undersized_block(blocks, BLOCK_LEN)
    bmeans = np.array([np.mean(d_real[s:e]) for (s, e) in blocks])
    n = len(bmeans)
    ref_sign = np.sign(np.mean(bmeans))
    signs_ok, ts = [], []
    for i in range(n):
        rest = np.delete(bmeans, i)
        m = float(np.mean(rest))
        se = float(np.std(rest, ddof=1) / np.sqrt(len(rest))) if len(rest) > 1 else np.nan
        t = m / se if (se and se > 0) else np.nan
        ts.append(t)
        signs_ok.append(np.sign(m) == ref_sign)
    sign_all = bool(all(signs_ok))
    t_crit_all = bool(all(np.isfinite(t) and abs(t) >= t_crit for t in ts))
    holds = sign_all and (t_crit_all if require_t_crit_every_refit else True)
    log(f"6.4 leave-one-block-out: n_blocks={n} sign_preserved_in_all={sign_all} "
        f"|t|>=T_crit_in_all={t_crit_all} "
        f"(magnitude requirement {'ACTIVE' if require_t_crit_every_refit else 'not required by base rule'}) "
        f"-> {'HOLDS' if holds else 'FAILS'}")
    return dict(n_blocks=n, refit_ts=ts, sign_preserved_all=sign_all,
                t_crit_cleared_all=t_crit_all, holds=holds)


def gate_6_5_chronological_halves(d_real, log):
    n = len(d_real)
    half = n // 2
    first, second = d_real[:half], d_real[half:]
    s1, s2 = np.sign(np.mean(first)), np.sign(np.mean(second))
    ok = bool(s1 == s2)
    log(f"6.5 chronological halves: mean(first)={np.mean(first):+.5f} "
        f"mean(second)={np.mean(second):+.5f} same_sign={ok} -> "
        f"{'HOLDS (KILL still licensed)' if ok else 'FAILS (era-local, KILL NOT licensed)'}")
    return dict(mean_first=float(np.mean(first)), mean_second=float(np.mean(second)),
                same_sign=ok, holds=ok)


def gate_6_6_mechanism_sanity(subj: Subject, adm, fresh_rows, stale_rows, log):
    """Reported, NOT gated: lag-L score autocorrelation alongside d."""
    rhos = []
    for i in range(len(fresh_rows)):
        ic, n = L.spearman_ic(subj.Smat[fresh_rows[i]], subj.Smat[stale_rows[i]])
        if np.isfinite(ic):
            rhos.append(ic)
    mean_rho = float(np.mean(rhos)) if rhos else float("nan")
    log(f"6.6 mechanism sanity (reported, not gated): mean lag-{GATE_LAG} score "
        f"autocorrelation = {mean_rho:+.4f} over {len(rhos)} dates")
    return dict(mean_lag_autocorrelation=mean_rho, n_dates=len(rhos))
