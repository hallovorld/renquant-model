"""FROZEN PREREG EXECUTION — step 2: statistics + mechanical verdict.

Arms:  score in {raw, cal} x label in {real, shift120, shuffle(5 seeds)}
Stats: per-date Spearman rank IC; per-date top-decile - bottom-decile spread.
Aggregation: fold mean -> across-fold t over the 43 folds (DECISION statistic).
Also reports naive per-date t and a 3-consecutive-fold block t.

Shift placebo convention matches the WF gate
(training_panel/pp_panel_training.py L2038): label@t = original_label@(t+N),
i.e. .shift(-N) on the per-ticker date-indexed series, N=120 trading days.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

W = Path("/private/tmp/claude-502/-Users-renhao-git-github-renquant-"
         "orchestrator/428feb92-8ee7-4b4f-afed-1e4fa82ef367/scratchpad/"
         "wf-eval")
PANEL = Path("/Users/renhao/git/github/RenQuant/data/"
             "transformer_v4_wl200_clean.parquet")
LABEL = "fwd_60d_excess"
SHIFT_DAYS = 120
SHUFFLE_SEEDS = [0, 1, 2, 3, 4]
DECILE = 0.10


def tstat(x: np.ndarray) -> tuple[float, float, float, int]:
    x = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    n = len(x)
    if n < 2:
        return float("nan"), float("nan"), float("nan"), n
    m = x.mean()
    se = x.std(ddof=1) / np.sqrt(n)
    return m, se, (m / se if se > 0 else float("nan")), n


def per_date_stats(df: pd.DataFrame, score_col: str,
                   y_col: str) -> pd.DataFrame:
    """Per-date rank IC and decile spread."""
    out = []
    for d, g in df.groupby("date", sort=True):
        g = g[[score_col, y_col]].dropna()
        if len(g) < 20:
            continue
        s, y = g[score_col].values, g[y_col].values
        ic = sstats.spearmanr(s, y).statistic
        r = pd.Series(s).rank(pct=True).values
        top, bot = y[r > 1 - DECILE], y[r <= DECILE]
        spread = (top.mean() - bot.mean()
                  if len(top) >= 3 and len(bot) >= 3 else np.nan)
        out.append((d, ic, spread, len(g)))
    return pd.DataFrame(out, columns=["date", "ic", "spread", "n"])


def aggregate(pds: pd.DataFrame, fold_of_date: pd.Series,
              stat: str) -> dict:
    """fold means -> across-fold t (decision), naive per-date t, block-3 t."""
    v = pds.dropna(subset=[stat]).copy()
    v["fold_idx"] = v["date"].map(fold_of_date)
    fold_means = v.groupby("fold_idx")[stat].mean()
    m, se, t, n = tstat(fold_means.values)
    _, _, t_naive, n_dates = tstat(v[stat].values)
    blocks = fold_means.groupby(fold_means.index // 3).mean()
    _, _, t_block, n_blocks = tstat(blocks.values)
    return {"mean": m, "se": se, "t_fold": t, "n_folds": n,
            "t_naive": t_naive, "n_dates": n_dates,
            "t_block3": t_block, "n_blocks": n_blocks,
            "fold_means": fold_means}


def main() -> None:
    sc = pd.read_parquet(W / "scores.parquet")
    sc["date"] = pd.to_datetime(sc["date"])
    fold_of_date = sc.drop_duplicates("date").set_index("date")["fold_idx"]

    panel = pd.read_parquet(PANEL, columns=["date", "ticker", LABEL])
    panel["date"] = pd.to_datetime(panel["date"])

    # real label
    lab = panel.pivot(index="date", columns="ticker", values=LABEL).sort_index()
    # shift placebo: label@t = original_label@(t+120 trading days)
    lab_shift = lab.shift(-SHIFT_DAYS)

    real = lab.stack().rename("y_real").reset_index()
    shift = lab_shift.stack().rename("y_shift").reset_index()
    df = sc.merge(real, on=["date", "ticker"], how="left")
    df = df.merge(shift, on=["date", "ticker"], how="left")

    # shuffle placebos: permute the REAL label within each date
    rng_cols = []
    for seed in SHUFFLE_SEEDS:
        rng = np.random.default_rng(seed)
        col = f"y_shuf{seed}"
        df[col] = np.nan
        for d, g in df.groupby("date", sort=True):
            idx = g.index[g["y_real"].notna()]
            vals = df.loc[idx, "y_real"].values
            df.loc[idx, col] = rng.permutation(vals)
        rng_cols.append(col)

    results, fold_tables = {}, {}
    for score_col in ["raw", "cal"]:
        # real + shift
        for arm, y in [("real", "y_real"), ("shift120", "y_shift")]:
            pds = per_date_stats(df, score_col, y)
            fold_tables[(score_col, arm)] = pds
            for stat in ["ic", "spread"]:
                a = aggregate(pds, fold_of_date, stat)
                results[f"{score_col}|{arm}|{stat}"] = a
        # shuffle: per-date average over the 5 seeds
        seed_pds = [per_date_stats(df, score_col, c) for c in rng_cols]
        merged = seed_pds[0][["date"]].copy()
        for stat in ["ic", "spread"]:
            merged[stat] = np.nanmean(
                np.vstack([p.set_index("date")[stat]
                           .reindex(merged["date"]).values
                           for p in seed_pds]), axis=0)
        fold_tables[(score_col, "shuffle")] = merged
        for stat in ["ic", "spread"]:
            results[f"{score_col}|shuffle|{stat}"] = aggregate(
                merged, fold_of_date, stat)

    # PAIRED real - placebo differences, fold-level dispersion
    diffs = {}
    for score_col in ["raw", "cal"]:
        for pl in ["shift120", "shuffle"]:
            for stat in ["ic", "spread"]:
                a = results[f"{score_col}|real|{stat}"]["fold_means"]
                b = results[f"{score_col}|{pl}|{stat}"]["fold_means"]
                common = a.index.intersection(b.index)
                dvals = (a.loc[common] - b.loc[common])
                m, se, t, n = tstat(dvals.values)
                ci_lo = m - 1.684 * se if np.isfinite(se) else np.nan
                ci_hi = m + 1.684 * se if np.isfinite(se) else np.nan
                blocks = dvals.groupby(dvals.index // 3).mean()
                _, _, t_block, nb = tstat(blocks.values)
                diffs[f"{score_col}|real-{pl}|{stat}"] = {
                    "mean": m, "se": se, "t_fold": t, "n_folds": n,
                    "ci90_lo": ci_lo, "ci90_hi": ci_hi,
                    "t_block3": t_block, "n_blocks": nb,
                    "fold_means": dvals}
    # export
    def clean(d):
        return {k: {kk: (float(vv) if isinstance(vv, (int, float, np.floating))
                         else vv)
                    for kk, vv in v.items() if kk != "fold_means"}
                for k, v in d.items()}

    payload = {"arms": clean(results), "differences": clean(diffs),
               "shift_days": SHIFT_DAYS, "shuffle_seeds": SHUFFLE_SEEDS,
               "decile": DECILE, "label": LABEL}
    (W / "results.json").write_text(json.dumps(payload, indent=2))

    fm = pd.DataFrame({k: v["fold_means"] for k, v in results.items()
                       if "|ic" in k or "|spread" in k})
    fm.to_csv(W / "fold_means.csv")
    dm = pd.DataFrame({k: v["fold_means"] for k, v in diffs.items()})
    dm.to_csv(W / "fold_diffs.csv")

    # ---- report ----
    def row(label, a):
        return (f"{label:<34} {a['mean']:+.5f}  t_fold={a['t_fold']:+6.2f} "
                f"(n={a['n_folds']:>2})  t_naive={a['t_naive']:+7.2f}  "
                f"t_blk3={a['t_block3']:+6.2f}")

    print("=" * 96)
    print("ARMS  (fold-level mean; t_fold = DECISION dispersion over folds)")
    print("=" * 96)
    for stat in ["ic", "spread"]:
        print(f"\n--- {stat.upper()} ---")
        for score_col in ["raw", "cal"]:
            for arm in ["real", "shift120", "shuffle"]:
                print(row(f"{score_col:<4} {arm}",
                          results[f"{score_col}|{arm}|{stat}"]))
    print("\n" + "=" * 96)
    print("REAL - PLACEBO  (paired per fold)")
    print("=" * 96)
    for k, v in diffs.items():
        print(f"{k:<34} {v['mean']:+.5f}  t_fold={v['t_fold']:+6.2f} "
              f"(n={v['n_folds']:>2})  CI90=[{v['ci90_lo']:+.5f},"
              f"{v['ci90_hi']:+.5f}]  t_blk3={v['t_block3']:+6.2f}")

    # ---- FROZEN DECISION RULE ----
    d = diffs["raw|real-shift120|ic"]
    t_d = d["t_fold"]
    sp = diffs["raw|real-shift120|spread"]
    cal_d = diffs["cal|real-shift120|ic"]
    print("\n" + "=" * 96)
    print("FROZEN DECISION RULE (prereg §3)")
    print("=" * 96)
    print(f"  d  = fold mean(real IC - shift120 IC) = {d['mean']:+.5f}")
    print(f"  t_d (fold-level, n={d['n_folds']})     = {t_d:+.3f}")
    print(f"  90% CI on d                  = [{d['ci90_lo']:+.5f}, "
          f"{d['ci90_hi']:+.5f}]")
    print(f"  decile-spread arm sign agrees: {np.sign(sp['mean']) == np.sign(d['mean'])}"
          f"  (spread d={sp['mean']:+.5f}, t={sp['t_fold']:+.2f})")
    print(f"  calibrated arm d={cal_d['mean']:+.5f} t={cal_d['t_fold']:+.2f} "
          f"(raw d={d['mean']:+.5f})")
    if t_d >= 2.0:
        verdict = "GO-candidate (check spread sign + calibrated arm)"
    elif t_d <= 0.5:
        verdict = "KILL-candidate (requires CI upper bound below smallest useful effect)"
    else:
        verdict = "UNDERPOWERED"
    print(f"\n  ==> mechanical bucket: {verdict}")


if __name__ == "__main__":
    main()
