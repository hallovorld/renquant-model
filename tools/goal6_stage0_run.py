#!/usr/bin/env python3
"""Runner for the FROZEN GOAL-6 Stage-0 measurement study. (model#160 thread)

Implements `doc/research/2026-07-28-goal6-stage0-prereg.md` as amended by
Amendment 1, Amendment 2 (the H2(c) discriminator SUSPENSION), and Amendment 3
(single-vintage committed labels; deterministic gap-separated blocks; arm (b)'s
pinned scoring table). No model is trained, promoted, or killed by this study —
it selects the Stage-1/2 measurement statistic and horizon.

Execution discipline (momentum-chain precedent): this runner performs the real
study only under `--execute`, is expected to run ONCE after this PR merges, and
its full JSON output is committed verbatim in a SEPARATE results PR (§6 of the
prereg). `--preflight` verifies every input digest and amendment-presence gate
and touches nothing else.

FORMERLY RUNNER-DECLARED, NOW AMENDMENT-OWNED: the permutation seed values
(`20260801 + i`), the `t_pair` seed-aggregation object (per-date seed mean →
gap-block t), the H2 cross-horizon blocking (h = 60 on the eligible-date
intersection), and the across-seed dispersion diagnostic are all FROZEN by
Stage-0 Amendment 4 — this runner implements them and gates on the amendment's
presence; nothing here is a runner choice anymore.

Exit codes: 0 preflight clean / run complete; 2 usage; 3 input-verification or
gate refusal (UNRESOLVED-DATA).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

REPO = Path(__file__).resolve().parent.parent

# ---- frozen by the prereg + amendments; the runner only restates ----------------
FROZEN = {
    "horizons": (20, 60),
    "n_perm_seeds": 20,
    "holm_family_alpha": 0.10,
    "own_t_bar": 2.0,
    "persistence_lag_positions": 60,     # t-60 trading days on the corpus date grid
    "profile_lags": tuple(range(0, 161, 20)),
    "se_hac_L": 19,                      # h_min - 1; DIAGNOSTIC ONLY per Amendment 2
    # Amendment 3 pins:
    "labels_sha256": "b1981eef13984d1a260eab06a883a76affb55fee820b388917f404f57b2faf02",
    "clf_scores_sha256": "1da3fcfab06af1e597ac0eb83dff4741ed3dd027de8b8a6b4d58979f5bc4efe4",
    # the XGB corpus's own manifest-defined CONTENT identity (canonical re-sort +
    # 10dp float formatting — the manifest's provenance anchor, not a byte sha):
    "xgb_corpus_content_sha256":
        "ba964b407ec1e0a5a25b5f733c91588822e24c3e56b8f53c71096c2cc57b0125",
}
PERM_SEEDS = tuple(20260801 + i for i in range(FROZEN["n_perm_seeds"]))

LABELS = REPO / "doc/research/data/2026-08-01-goal6-stage0-frozen-labels/labels.parquet"
CLF_SCORES = (REPO / "doc/research/data/2026-07-29-clf-wf-closure-bundle/"
                     "artifacts/clf-wf/clf_wf_scores.parquet")
PREREG = REPO / "doc/research/2026-07-28-goal6-stage0-prereg.md"
AMENDMENTS = tuple(
    REPO / f"doc/research/2026-07-28-goal6-stage0-amendment-1.md" if i == 1 else
    REPO / f"doc/research/2026-08-01-goal6-stage0-amendment-{i}.md"
    for i in (1, 2, 3, 4, 5))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def xgb_corpus_content_sha(df: pd.DataFrame) -> str:
    """The corpus manifest's canonical content hash — MIRRORS
    renquant_backtesting.analysis.pick_table.canonical_table_content_hash exactly
    (column order date|name|score|decile_rank|fwd_60d_excess|regime; date as
    %Y-%m-%d; floats to .10f strings; sort by (date, name); '|'-joined lines with
    a trailing newline). Cross-checked against the committed manifest anchor at
    development time; any drift in either implementation fails preflight loudly."""
    canon = df[["date", "name", "score", "decile_rank", "fwd_60d_excess", "regime"]].copy()
    canon["date"] = pd.to_datetime(canon["date"]).dt.strftime("%Y-%m-%d")
    canon["name"] = canon["name"].astype(str)
    canon["score"] = canon["score"].astype(float).map(lambda v: f"{v:.10f}")
    canon["decile_rank"] = canon["decile_rank"].astype(int)
    canon["fwd_60d_excess"] = canon["fwd_60d_excess"].astype(float).map(lambda v: f"{v:.10f}")
    canon["regime"] = canon["regime"].astype(str)
    canon = canon.sort_values(["date", "name"]).reset_index(drop=True)
    lines = ["|".join(str(v) for v in row)
             for row in canon.itertuples(index=False, name=None)]
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


# ------------------------------------------------------------- block geometry ----
def gap_blocks(T: int, h: int) -> list[tuple[int, int]]:
    """Amendment 3 rev 2: retained [2kh, 2kh+h), gap discarded, terminal partial
    retained window DISCARDED. Returns [start, end) index pairs."""
    out = []
    k = 0
    while True:
        s, e = 2 * k * h, 2 * k * h + h
        if e > T:
            break
        out.append((s, e))
        k += 1
    return out


def n_eff(T: int, h: int) -> int:
    return (T - h) // (2 * h) + 1 if T >= h else 0


def gap_block_t(series: np.ndarray, h: int) -> dict:
    """Gap-block t of a per-date series: block means over retained windows.
    Reports the TERMINAL PARTIAL retained window's dropped-date count, as
    Amendment 3 requires (gap windows are discarded by design, not 'dropped')."""
    v = np.asarray(series, float)
    T = len(v)
    blocks = gap_blocks(T, h)
    next_start = 2 * len(blocks) * h
    dropped_tail = max(0, T - next_start)
    means = [float(np.nanmean(v[s:e])) for s, e in blocks
             if np.isfinite(v[s:e]).any()]
    N = len(means)
    if N < 2:
        return {"t": None, "n_eff": N, "df": max(N - 1, 0),
                "mean": (means[0] if means else None),
                "dropped_tail_dates": dropped_tail}
    m = float(np.mean(means))
    se = float(np.std(means, ddof=1) / np.sqrt(N))
    return {"t": (m / se if se > 0 else None), "n_eff": N, "df": N - 1,
            "mean": m, "se": se, "dropped_tail_dates": dropped_tail}


def bartlett_hac_se(v: np.ndarray, L: int) -> float:
    """Frozen SE_HAC (per-date series). DIAGNOSTIC ONLY under Amendment 2."""
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    n = len(v)
    if n < 3:
        return float("nan")
    d = v - v.mean()
    total = float(d @ d) / n
    for k in range(1, min(L, n - 1) + 1):
        total += 2.0 * (1.0 - k / (L + 1.0)) * (float(d[:-k] @ d[k:]) / n)
    return float(np.sqrt(total / n)) if total > 0 else float("nan")


# ------------------------------------------------------------ per-date statistics
def per_date_stats(scores: pd.Series, labels: pd.Series) -> dict | None:
    """The three frozen statistics for one date. `scores`/`labels` share an index
    (tickers); non-finite pairs dropped pairwise."""
    df = pd.DataFrame({"s": scores, "y": labels}).dropna()
    if len(df) < 20:                      # a decile needs at least 2 names
        return None
    ic = sstats.spearmanr(df["s"], df["y"]).statistic
    q = pd.qcut(df["s"].rank(method="first"), 10, labels=False)
    top, bot = df["y"][q == 9], df["y"][q == 0]
    return {"ic": float(ic),
            "spread": float(top.mean() - bot.mean()),
            "hit": float((top > 0).mean()),
            "n": len(df)}


STAT_KEYS = ("ic", "spread", "hit")


def build_effect_series(arm: pd.DataFrame, labels: dict, h: int,
                        rng_seeds=PERM_SEEDS) -> dict:
    """Per-date REAL stats, per-seed permutation stats, and persistence-arm stats
    for one scoring arm at one horizon.

    `arm`: columns [date, ticker, score] (sorted dates).
    `labels`: {(date) -> pd.Series(label by ticker)} for this horizon.
    Returns per-date arrays aligned on the arm's eligible dates.
    """
    dates = sorted(d for d in arm["date"].unique() if d in labels)
    by_date = {d: g.set_index("ticker")["score"] for d, g in arm.groupby("date")}
    real = {k: [] for k in STAT_KEYS}
    perm = {k: np.zeros((len(rng_seeds), len(dates))) for k in STAT_KEYS}
    eligible = []
    for d in dates:
        st = per_date_stats(by_date[d], labels[d])
        if st is None:
            continue
        i = len(eligible)
        eligible.append(d)
        for k in STAT_KEYS:
            real[k].append(st[k])
        lab = labels[d].reindex(by_date[d].index)
        finite = lab.dropna().index
        for s_i, seed in enumerate(rng_seeds):
            # per-date offset must be PROCESS-STABLE (Python's str hash is salted);
            # the date's own yyyymmdd integer is deterministic everywhere.
            rng = np.random.default_rng(seed * 100_000_000
                                        + int(pd.Timestamp(d).strftime("%Y%m%d")))
            shuffled = pd.Series(rng.permutation(lab.loc[finite].to_numpy()),
                                 index=finite)
            pst = per_date_stats(by_date[d].loc[finite], shuffled)
            for k in STAT_KEYS:
                perm[k][s_i, i] = pst[k] if pst else np.nan
    n_el = len(eligible)
    for k in STAT_KEYS:
        perm[k] = perm[k][:, :n_el]
    # persistence arm: same ticker's score 60 positions earlier on the arm's grid
    grid = sorted(by_date)
    pos = {d: i for i, d in enumerate(grid)}
    persist = {k: [] for k in STAT_KEYS}
    persist_dates, persist_cov = [], {"cells_real": 0, "cells_persist": 0}
    lagN = FROZEN["persistence_lag_positions"]
    for d in eligible:
        i = pos[d]
        if i < lagN:
            continue
        old = by_date[grid[i - lagN]]
        cur = by_date[d]
        common = cur.index.intersection(old.index)
        persist_cov["cells_real"] += len(cur)
        persist_cov["cells_persist"] += len(common)
        st = per_date_stats(old.reindex(common), labels[d].reindex(common))
        if st is None:
            continue
        persist_dates.append(d)
        for k in STAT_KEYS:
            persist[k].append(st[k])
    return {"dates": eligible,
            "real": {k: np.array(v) for k, v in real.items()},
            "perm": perm,
            "persist": {"dates": persist_dates,
                        "stats": {k: np.array(v) for k, v in persist.items()},
                        "coverage": persist_cov}}


# ----------------------------------------------------------------- decisions ----
def holm(pvals: dict[str, float], alpha: float) -> dict[str, bool]:
    """Holm-Bonferroni over a small closed family; None p-values never pass."""
    items = sorted(((p if p is not None else 1.0), k) for k, p in pvals.items())
    out, m = {}, len(items)
    crossed = False
    for rank, (p, k) in enumerate(items):
        bar = alpha / (m - rank)
        if crossed or p > bar:
            crossed = True
            out[k] = False
        else:
            out[k] = True
    return out


def two_sided_p(t: float | None, df: int) -> float | None:
    if t is None or df < 1:
        return None
    return float(2 * sstats.t.sf(abs(t), df))


def _veto_passes(v: dict | None) -> bool:
    """§5 Veto (all hypotheses): REAL − persistence must be positive at t ≥ 1.0."""
    return (v is not None and v.get("t") is not None
            and v["t"] >= 1.0 and (v.get("mean") or 0) > 0)


def decide_h1(contrasts: dict, own_t: dict, veto: dict | None = None) -> dict:
    """H1 per §5: both tail-vs-IC contrasts Holm-significant IN FAVOUR OF the tail
    statistic AND each tail's own REAL−perm t ≥ 2.0 — and NO statistic can be
    declared SUPPORTED-winner if its REAL − persistence veto fails."""
    veto = veto or {}
    alpha = FROZEN["holm_family_alpha"]
    pv = {k: two_sided_p(c["t"], c["df"]) for k, c in contrasts.items()}
    sig = holm(pv, alpha)
    fav = {k: (contrasts[k]["mean"] or 0) > 0 for k in contrasts}
    spread_ok = sig["spread_vs_ic"] and fav["spread_vs_ic"] and (own_t["spread"] or 0) >= FROZEN["own_t_bar"]
    hit_ok = sig["hit_vs_ic"] and fav["hit_vs_ic"] and (own_t["hit"] or 0) >= FROZEN["own_t_bar"]
    ic_favoured = any(sig[k] and not fav[k] for k in ("spread_vs_ic", "hit_vs_ic"))
    if spread_ok and hit_ok:
        vetoes = {k: _veto_passes(veto.get(k)) for k in ("spread", "hit")}
        if all(vetoes.values()):
            winner = "spread" if (own_t["spread"] or 0) >= (own_t["hit"] or 0) else "hit"
            return {"verdict": "SUPPORTED", "primary_statistic": winner,
                    "veto": vetoes}
        # §5 requires BOTH tails for SUPPORTED; a vetoed required tail cannot be
        # substituted by the other — the hypothesis is INCONCLUSIVE and Stage 2
        # keeps the current production choice (IC).
        return {"verdict": "INCONCLUSIVE", "primary_statistic": "ic",
                "why": "§5 persistence veto: a required tail statistic failed "
                       "REAL − persistence positive at t ≥ 1.0",
                "veto": vetoes}
    if ic_favoured or (not spread_ok and not hit_ok):
        return {"verdict": "REFUTED" if not (spread_ok or hit_ok) else "INCONCLUSIVE",
                "primary_statistic": "ic"}
    return {"verdict": "INCONCLUSIVE", "primary_statistic": "ic"}


def decide_h2(t_pair: dict, own_t_20: float | None, d20: float | None,
              d60: float | None, veto20: dict | None = None,
              veto60: dict | None = None) -> dict:
    """H2 per §5 as amended by Amendment 2: (a)+(b) required; a failure of (c) is
    graded INCONCLUSIVE, never REFUTED (the SE_HAC discriminator is SUSPENDED).
    The §5 all-hypotheses persistence veto applies to EACH arm the comparison
    uses — both the 20d and the 60d persistence controls of the selected
    statistic must be positive at t ≥ 1.0."""
    a = t_pair["t"] is not None and t_pair["t"] >= FROZEN["own_t_bar"] and (t_pair["mean"] or 0) > 0
    b = (own_t_20 or 0) >= FROZEN["own_t_bar"]
    c = (d20 is not None and d60 is not None and d20 <= d60)
    if a and b and c:
        vetoes = {"h20": _veto_passes(veto20), "h60": _veto_passes(veto60)}
        if not all(vetoes.values()):
            failed = [k for k, ok in vetoes.items() if not ok]
            return {"verdict": "INCONCLUSIVE", "a": a, "b": b, "c": c,
                    "veto_passed": False, "veto": vetoes,
                    "why": "§5 persistence veto: REAL − persistence not positive "
                           f"at t ≥ 1.0 on {'/'.join(failed)}"}
        return {"verdict": "SUPPORTED", "a": a, "b": b, "c": c,
                "veto_passed": True, "veto": vetoes}
    if a and b and not c:
        return {"verdict": "INCONCLUSIVE", "a": a, "b": b, "c": c,
                "why": "Amendment 2: (c) discriminator suspended — never REFUTED on (c)"}
    return {"verdict": "REFUTED" if not (a and b) else "INCONCLUSIVE",
            "a": a, "b": b, "c": c}


def stage2_recommendation(h1: dict, h2: dict, own60: dict | None,
                          veto60_stat: dict | None) -> dict:
    """Amendment 5: the Stage-2 hand-off. H2 SUPPORTED -> (H1 statistic, 20d).
    H1 SUPPORTED but H2 not -> the 20d-selected tail carries into the 60d regime
    ONLY if confirmed AT 60d (own REAL-perm t >= 2.0 AND the 60d persistence veto
    passes); otherwise IC per the tie rule. Everything else -> (H1 statistic, 60d),
    which is IC whenever H1 did not support a tail."""
    stat = h1.get("primary_statistic", "ic")
    if h2.get("verdict") == "SUPPORTED":
        return {"statistic": stat, "measurement_horizon": 20}
    out = {"statistic": stat, "measurement_horizon": 60}
    if h1.get("verdict") == "SUPPORTED" and stat != "ic":
        confirmed = (own60 is not None and own60.get("t") is not None
                     and own60["t"] >= FROZEN["own_t_bar"]
                     and _veto_passes(veto60_stat))
        out["cross_horizon_confirmation"] = {
            "own_t_60": (own60 or {}).get("t"),
            "veto_60_passed": _veto_passes(veto60_stat),
            "confirmed": confirmed,
        }
        if not confirmed:
            out["statistic"] = "ic"
            out["why"] = ("Amendment 5 guard: the 20d-selected statistic failed 60d "
                          "confirmation; Stage 2 keeps IC")
    return out


# ------------------------------------------------------------------ preflight ----
def verify_preconditions(xgb_df: pd.DataFrame | None,
                         xgb_path: Path | None = None) -> dict:
    """`xgb_df` is the ALREADY-LOADED corpus frame — identity is verified on the
    exact object execution will consume (no second read, no swap window between
    preflight and load). `xgb_path` is recorded for the report only."""
    out: dict = {"checks": {}, "unresolved": []}

    def check(name, ok, detail=""):
        out["checks"][name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            out["unresolved"].append(name)

    check("prereg_present", PREREG.is_file(), str(PREREG))
    for i, p in zip((1, 2, 3, 4, 5), AMENDMENTS):
        check(f"amendment_{i}_present", p.is_file(), str(p))
    check("labels_digest", LABELS.is_file() and _sha(LABELS) == FROZEN["labels_sha256"],
          "Amendment 3 clause 1 — fail-closed, no live-path fallback")
    check("clf_scores_digest",
          CLF_SCORES.is_file() and _sha(CLF_SCORES) == FROZEN["clf_scores_sha256"],
          "Amendment 3 clause 3")
    if xgb_df is None:
        check("xgb_corpus_provided", False,
              "--xgb-corpus is a REQUIRED explicit input (no workstation default)")
    else:
        check("xgb_corpus_content_digest",
              xgb_corpus_content_sha(xgb_df) == FROZEN["xgb_corpus_content_sha256"],
              "the corpus manifest's canonical content identity, verified on the "
              "loaded frame itself")
        out["xgb_corpus_resolved_path"] = str(xgb_path) if xgb_path else None
    out["ok"] = not out["unresolved"]
    return out


# -------------------------------------------------------------------- execute ----
def execute(xgb_path: Path, json_out: Path | None) -> int:
    xgb_df = pd.read_parquet(xgb_path) if xgb_path.is_file() else None
    pre = verify_preconditions(xgb_df, xgb_path)
    if not pre["ok"]:
        print(json.dumps({"status": "UNRESOLVED-DATA", "preflight": pre},
                         indent=2, sort_keys=True))
        return 3

    lab = pd.read_parquet(LABELS)
    lab["date"] = pd.to_datetime(lab["date"])
    labels_by = {h: {d: g.set_index("ticker")[f"fwd_{h}d_excess"]
                     for d, g in lab.groupby("date")} for h in FROZEN["horizons"]}

    xgb = xgb_df.rename(columns={"name": "ticker"})
    xgb["date"] = pd.to_datetime(xgb["date"])
    clf = pd.read_parquet(CLF_SCORES).rename(columns={"cal": "score"})
    clf["date"] = pd.to_datetime(clf["date"])
    clf = clf[clf["date"].isin(set(xgb["date"].unique()))][["date", "ticker", "score"]]

    arms = {"xgb": xgb[["date", "ticker", "score"]], "clf": clf}
    report: dict = {"status": "COMPLETED", "preflight": pre,
                    "perm_seeds": list(PERM_SEEDS), "arms": {}}

    for arm_name, arm in arms.items():
        arm_rep: dict = {}
        eff = {}
        for h in FROZEN["horizons"]:
            e = build_effect_series(arm, labels_by[h], h)
            eff[h] = e
            T = len(e["dates"])
            hrep: dict = {"n_dates": T, "n_eff": n_eff(T, h)}
            for k in STAT_KEYS:
                perm_mean = np.nanmean(e["perm"][k], axis=0)
                delta = e["real"][k] - perm_mean
                bt = gap_block_t(delta, h)
                # Amendment 4 item 5: the across-seed dispersion of the per-date
                # per-seed effect, published so the 20-draw Monte-Carlo noise
                # floor is visible next to the decision statistic it feeds.
                delta_seeds = e["real"][k][None, :] - e["perm"][k]
                seed_sd = np.nanstd(delta_seeds, axis=0, ddof=1)
                hrep[k] = {
                    "real_mean": float(np.nanmean(e["real"][k])),
                    "perm_mean": float(np.nanmean(perm_mean)),
                    "delta_block": bt,
                    "across_seed_sd": {"mean": float(np.nanmean(seed_sd)),
                                       "max": float(np.nanmax(seed_sd))},
                    "se_hac_diagnostic": bartlett_hac_se(delta, FROZEN["se_hac_L"]),
                }
            # persistence arm (its own dates, own blocks)
            pers = e["persist"]
            if pers["dates"]:
                idx = {d: i for i, d in enumerate(e["dates"])}
                sel = [idx[d] for d in pers["dates"]]
                hrep["persistence"] = {
                    "coverage": pers["coverage"],
                    "n_dates": len(pers["dates"]),
                    **{k: {"real_minus_persist_block":
                           gap_block_t(e["real"][k][sel] - pers["stats"][k], h)}
                       for k in STAT_KEYS}}
            arm_rep[f"h{h}"] = hrep
        # H1 horizon: FROZEN at 20d by Amendment 5 (13 vs 4 gapped blocks; the
        # Holm 3-family needs |t| >= 3.740 at df=3 — structurally near-unresolvable
        # at 60d). The cross-horizon confirmation guard below is the same amendment.
        h1_h = 20
        e = eff[h1_h]
        perm_means = {k: np.nanmean(e["perm"][k], axis=0) for k in STAT_KEYS}
        deltas = {k: e["real"][k] - perm_means[k] for k in STAT_KEYS}
        contrasts = {
            "spread_vs_ic": gap_block_t(deltas["spread"] - deltas["ic"], h1_h),
            "hit_vs_ic": gap_block_t(deltas["hit"] - deltas["ic"], h1_h),
            "spread_vs_hit": gap_block_t(deltas["spread"] - deltas["hit"], h1_h),
        }
        own_t = {k: gap_block_t(deltas[k], h1_h)["t"] for k in STAT_KEYS}
        # §5 persistence veto inputs at the H1 horizon (each stat's REAL − persist)
        pers20 = eff[h1_h]["persist"]
        veto20 = {}
        if pers20["dates"]:
            idx20 = {d: i for i, d in enumerate(eff[h1_h]["dates"])}
            sel20 = [idx20[d] for d in pers20["dates"]]
            veto20 = {k: gap_block_t(eff[h1_h]["real"][k][sel20]
                                     - pers20["stats"][k], h1_h)
                      for k in STAT_KEYS}
        h1 = decide_h1(contrasts, own_t, veto20)
        arm_rep["H1"] = {"contrasts": contrasts, "own_t": own_t, **h1}
        # H2 on the H1-selected statistic, 20d vs 60d on common dates, blocks at 60
        stat = h1["primary_statistic"]
        common = sorted(set(eff[20]["dates"]) & set(eff[60]["dates"]))
        i20 = {d: i for i, d in enumerate(eff[20]["dates"])}
        i60 = {d: i for i, d in enumerate(eff[60]["dates"])}
        d20 = np.array([(eff[20]["real"][stat] - np.nanmean(eff[20]["perm"][stat], axis=0))[i20[d]] for d in common])
        d60 = np.array([(eff[60]["real"][stat] - np.nanmean(eff[60]["perm"][stat], axis=0))[i60[d]] for d in common])
        t_pair = gap_block_t(d20 - d60, 60)
        own20 = gap_block_t(d20, 20)["t"]
        pers60 = eff[60]["persist"]
        veto60 = {}
        if pers60["dates"]:
            idx60p = {d: i for i, d in enumerate(eff[60]["dates"])}
            sel60 = [idx60p[d] for d in pers60["dates"]]
            veto60 = {k: gap_block_t(eff[60]["real"][k][sel60]
                                     - pers60["stats"][k], 60)
                      for k in STAT_KEYS}
        h2 = decide_h2(t_pair, own20, float(np.nanmean(d20)), float(np.nanmean(d60)),
                       veto20.get(stat), veto60.get(stat))
        arm_rep["H2"] = {"statistic": stat, "t_pair_blocks_at_60": t_pair,
                         "d20_mean": float(np.nanmean(d20)),
                         "d60_mean": float(np.nanmean(d60)), **h2}
        own60_stat = gap_block_t(
            eff[60]["real"][stat] - np.nanmean(eff[60]["perm"][stat], axis=0), 60) \
            if stat in eff[60]["real"] else None
        arm_rep["stage2_recommendation"] = stage2_recommendation(
            h1, h2, own60_stat, veto60.get(stat))
        # H3 profile (descriptive): IC of score(t) vs fwd_20d label at t+lag
        grid = sorted(labels_by[20])
        gpos = {d: i for i, d in enumerate(grid)}
        by_date = {d: g.set_index("ticker")["score"] for d, g in arm.groupby("date")}
        profile = {}
        for lag in FROZEN["profile_lags"]:
            vals = []
            for d in eff[20]["dates"]:
                j = gpos.get(d)
                if j is None or j + lag >= len(grid):
                    continue
                st = per_date_stats(by_date[d], labels_by[20][grid[j + lag]])
                if st:
                    vals.append(st["ic"])
            profile[str(lag)] = {"mean_ic": (float(np.mean(vals)) if vals else None),
                                 "n_dates": len(vals)}
        arm_rep["H3_profile_lag_ic"] = profile
        report["arms"][arm_name] = arm_rep

    txt = json.dumps(report, indent=2, sort_keys=True, default=str)
    print(txt)
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(txt + "\n")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--execute", action="store_true")
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--xgb-corpus", type=Path, required=True,
                    help="explicit path to oos_pick_table_recipe_v2.parquet — no "
                         "workstation default; content identity is verified on load")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    if args.preflight:
        df = pd.read_parquet(args.xgb_corpus) if args.xgb_corpus.is_file() else None
        pre = verify_preconditions(df, args.xgb_corpus)
        print(json.dumps(pre, indent=2, sort_keys=True))
        return 0 if pre["ok"] else 3
    return execute(args.xgb_corpus, args.json_out)


if __name__ == "__main__":
    raise SystemExit(main())
