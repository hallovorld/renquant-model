#!/usr/bin/env python
"""CONFIRMATORY: blend objective vs production rank:pairwise (10 seeds).

Implements doc/research/2026-07-25-objective-blend-confirmatory-prereg.md.
Decision rule frozen there; this script only executes it.

Read-only against production; writes only to the given --out path (refuses
production-adjacent paths).

The `--out` bundle is analysis-replayable (model#68 review rounds 3-4): it
carries the per-date clean-spread series for both arms (raw and winsorized
±50%), the per-seed per-date series, the paired `diff` series the bootstrap
CI is computed from, and a `manifest` (panel-file digest, prereg-file
digest, code revision, command, run start/finish timestamps). A reviewer
reloads the bundle with `deserialize_result` and recomputes the CI, both
guards, and the verdict via `verdict_from_bundle` rather than trusting the
printed aggregates. `serialize_result`/`deserialize_result` are the exact
inverse pair, pinned by a round-trip test in
`tests/gbdt/test_research_objective_blend_confirm.py`. `run_started_at` in
the manifest, compared against the prereg file's git log timestamp, is the
auditable pre-run boundary: a legitimate confirmatory run's manifest
postdates the frozen prereg commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import warnings
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

LAB = "fwd_60d_excess"
SEEDS = tuple(range(42, 52))          # 10 seeds — prereg-frozen
N_ROUNDS, EMBARGO, TOP_N = 100, 60, 10
BLK, N_BOOT, BOOT_SEED = 60, 10_000, 20260725
MIN_SEEDS_POSITIVE = 8                # prereg guard (a): >= 8/10 seeds positive
_FORBIDDEN = ("artifacts/prod", "artifacts/sim", "strategy_config", "/data/",
              "walkforward", "panel-ltr")
PREREG_PATH = (Path(__file__).resolve().parents[1] / "doc" / "research"
                / "2026-07-25-objective-blend-confirmatory-prereg.md")
# Durable locator for the training panel's producing job (model#73 review
# HIGH): the parquet itself is gitignored/workstation-local, but the ETL
# script that builds it is git-tracked in the owning repo, so its revision
# is a portable, non-workstation-path fingerprint for the input.
_BASE_DATA_REPO = Path("/Users/renhao/git/github/renquant-base-data")
_PANEL_BUILDER_SCRIPT = "src/renquant_base_data/alpha158_fund_panel.py"

CLF = {"objective": "binary:logistic", "eta": 0.05, "max_depth": 5,
       "min_child_weight": 50, "subsample": 0.7, "colsample_bytree": 0.7,
       "verbosity": 0, "eval_metric": "logloss"}


def block_bootstrap_ci(diff, block: int = BLK, n_boot: int = N_BOOT,
                        seed: int = BOOT_SEED) -> tuple[float, float]:
    """Moving-block bootstrap 90% CI of mean(diff). Pure function: the live
    run and a reloaded bundle get an identical CI from the same series."""
    d = np.asarray(diff.values if isinstance(diff, pd.Series) else diff, dtype=float)
    rng = np.random.default_rng(seed)
    starts = np.arange(max(len(d) - block + 1, 1))
    n_blocks = int(np.ceil(len(d) / block))
    boots = np.array([np.concatenate(
        [d[i:i + block] for i in rng.choice(starts, size=n_blocks, replace=True)]
    )[:len(d)].mean() for _ in range(n_boot)])
    return float(np.percentile(boots, 5)), float(np.percentile(boots, 95))


def decide_verdict(ci_lo: float, diff_mean: float, n_pos: int, wins_diff: float,
                    min_pos: int = MIN_SEEDS_POSITIVE) -> str:
    """Prereg decision rule, verbatim: CONFIRMED needs the CI lower bound > 0
    AND >= min_pos seed signs positive AND the winsorized ±50% guard (b) >=
    0; REFUTED if the point estimate is <= 0; else INCONCLUSIVE."""
    if ci_lo > 0 and n_pos >= min_pos and wins_diff >= 0:
        return "CONFIRMED"
    if diff_mean <= 0:
        return "REFUTED"
    return "INCONCLUSIVE"


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_revision(repo_dir: Path) -> str:
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir,
                              capture_output=True, text=True, check=True)
        return proc.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _git_revision_parents(repo_dir: Path) -> list[str]:
    """Parent SHAs of `code_revision` (model#73 review BLOCKER 1): lets a
    reviewer confirm the run's checkout is the declared merge commit on
    `main`, not an unmerged branch head mislabeled as main.

    Reads the raw commit object via `git cat-file -p HEAD` rather than a
    graph-traversal command like `git log --format=%P`: on a shallow clone
    (model#73 review round 5 — GitHub Actions checks out at depth 1) git
    treats the fetched boundary commit as parentless for traversal, so
    `%P` comes back empty even though the true parent SHA is part of the
    commit object's own content and is present locally regardless of
    clone depth."""
    try:
        proc = subprocess.run(["git", "cat-file", "-p", "HEAD"], cwd=repo_dir,
                              capture_output=True, text=True, check=True)
        return [line.split()[1] for line in proc.stdout.splitlines()
                if line.startswith("parent ")]
    except (OSError, subprocess.CalledProcessError, IndexError):
        return []


def _prereg_commit(repo_dir: Path) -> str | None:
    """Immutable commit that last froze the prereg text (model#73 review
    BLOCKER 2: "no immutable prereg_commit ... binding"). `prereg_digest`
    proves *which* text; this proves *which commit* froze it, so a reviewer
    can check the run happened after the freeze by git ancestry, not just a
    wall-clock timestamp (a wall-clock claim is exactly what BLOCKER 1
    caught being wrong)."""
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(PREREG_PATH.relative_to(repo_dir))],
            cwd=repo_dir, capture_output=True, text=True, check=True)
        return proc.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def _is_ancestor(ancestor: str | None, descendant: str | None, repo_dir: Path) -> bool | None:
    """True if `ancestor` is a git ancestor of (or equal to) `descendant` —
    the ancestor check BLOCKER 2 asked for for `prereg_commit` vs
    `code_revision`. None if either SHA is unknown."""
    if not ancestor or not descendant:
        return None
    proc = subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, descendant],
                          cwd=repo_dir, capture_output=True, text=True)
    return proc.returncode == 0


def _producing_script_revision() -> str | None:
    """Git revision of the ETL script that built the training panel — the
    durable locator model#73 review HIGH asked for, since the parquet
    itself carries only a workstation-absolute `data_path`."""
    if not (_BASE_DATA_REPO / _PANEL_BUILDER_SCRIPT).exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", _PANEL_BUILDER_SCRIPT],
            cwd=_BASE_DATA_REPO, capture_output=True, text=True, check=True)
        return proc.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def build_manifest(*, data_dir: Path, argv: list[str], run_started_at: str,
                    run_finished_at: str, panel: pd.DataFrame) -> dict:
    """Reproducibility + pre-run-freeze manifest (model#68 review rounds
    3-4; model#73 review HIGH). `prereg_digest` proves which frozen
    decision-rule text the run executed against; a results PR is only an
    honest confirmatory read if `run_started_at` postdates the prereg's own
    frozen commit and this digest matches the prereg file at that commit.
    `row_count`/`date_range` plus `producing_script.git_revision` are a
    durable fingerprint for the input panel, independent of the
    workstation-absolute `data_path`."""
    from renquant_model_gbdt.panel_data import PANEL_FILE
    repo_dir = Path(__file__).resolve().parents[1]
    panel_path = data_dir / PANEL_FILE
    data_digest = _sha256_file(panel_path)
    prereg_digest = _sha256_file(PREREG_PATH)
    dates = pd.to_datetime(panel["date"])
    code_revision = _git_revision(repo_dir)
    prereg_commit = _prereg_commit(repo_dir)
    return {
        "data_path": str(panel_path),
        "data_digest": f"sha256:{data_digest}" if data_digest else None,
        "row_count": int(len(panel)),
        "date_range": [str(dates.min().date()), str(dates.max().date())],
        "producing_script": {
            "repo": "renquant-base-data",
            "path": _PANEL_BUILDER_SCRIPT,
            "git_revision": _producing_script_revision(),
        },
        "prereg_path": str(PREREG_PATH),
        "prereg_digest": f"sha256:{prereg_digest}" if prereg_digest else None,
        "prereg_commit": prereg_commit,
        "code_revision": code_revision,
        "code_revision_parents": _git_revision_parents(repo_dir),
        "prereg_commit_is_ancestor_of_code_revision":
            _is_ancestor(prereg_commit, code_revision, repo_dir),
        "command": " ".join(argv),
        "run_started_at": run_started_at,
        "run_finished_at": run_finished_at,
    }


def serialize_result(clean_series: dict, diff: pd.Series, wins_diff_series: pd.Series) -> dict:
    """JSON-safe view of every per-date/per-seed series behind the reported
    aggregates — without this a reviewer cannot recompute the CI or either
    guard from the bundle (model#68 review round 3, BLOCKER 1)."""
    def series(s):
        return {str(d): float(v) for d, v in s.items()}

    def by_seed(df: pd.DataFrame):
        return {str(seed): series(df[seed].dropna()) for seed in df.columns}

    return {
        "blend_clean_by_date": series(clean_series["blend"]),
        "rank60_clean_by_date": series(clean_series["rank60"]),
        "blend_clean_w50_by_date": series(clean_series["blend_w50"]),
        "rank60_clean_w50_by_date": series(clean_series["rank60_w50"]),
        "blend_by_seed": by_seed(clean_series["blend_by_seed"]),
        "rank60_by_seed": by_seed(clean_series["rank60_by_seed"]),
        "diff_by_date": series(diff),
        "wins_diff_by_date": series(wins_diff_series),
    }


def deserialize_result(payload: dict) -> dict:
    """Inverse of `serialize_result` — rebuilds the pandas Series/DataFrame
    shapes `verdict_from_bundle` expects, including the int seed columns
    JSON's string-only object keys drop."""
    def series(d):
        return pd.Series({k: v for k, v in d.items()}).sort_index()

    def frame(by_seed):
        return pd.DataFrame({int(seed): series(d) for seed, d in by_seed.items()})

    return {
        "blend_clean_by_date": series(payload["blend_clean_by_date"]),
        "rank60_clean_by_date": series(payload["rank60_clean_by_date"]),
        "blend_clean_w50_by_date": series(payload["blend_clean_w50_by_date"]),
        "rank60_clean_w50_by_date": series(payload["rank60_clean_w50_by_date"]),
        "blend_by_seed": frame(payload["blend_by_seed"]),
        "rank60_by_seed": frame(payload["rank60_by_seed"]),
        "diff_by_date": series(payload["diff_by_date"]),
        "wins_diff_by_date": series(payload["wins_diff_by_date"]),
    }


def verdict_from_bundle(bundle: dict, min_pos: int = MIN_SEEDS_POSITIVE) -> dict:
    """Recompute the CI, both guards, and the verdict from a
    `deserialize_result` bundle — the exact replay path a reviewer runs
    end to end against a persisted `--out` file."""
    diff = bundle["diff_by_date"]
    wins_diff_mean = float(bundle["wins_diff_by_date"].mean())
    lo, hi = block_bootstrap_ci(diff)

    by_seed_a, by_seed_b = bundle["blend_by_seed"], bundle["rank60_by_seed"]
    seed_signs = []
    for s in by_seed_a.columns:
        if s not in by_seed_b.columns:
            continue
        ca, cb = by_seed_a[s].dropna(), by_seed_b[s].dropna()
        common = ca.index.intersection(cb.index)
        seed_signs.append(float((ca[common] - cb[common]).mean()))
    n_pos = sum(1 for x in seed_signs if x > 0)

    verdict = decide_verdict(lo, float(diff.mean()), n_pos, wins_diff_mean, min_pos)
    return {"diff_mean": float(diff.mean()), "ci90": [lo, hi], "seeds_positive": n_pos,
            "winsorized_w50_diff": wins_diff_mean, "verdict": verdict}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/Users/renhao/git/github/RenQuant/data")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out_path = Path(args.out)
    for bad in _FORBIDDEN:
        if bad in str(out_path.resolve()):
            raise SystemExit(f"refusing output near production: {bad!r}")
    run_started_at = datetime.now(timezone.utc).isoformat()

    import xgboost as xgb
    from renquant_model_gbdt.panel_data import load_panel, build_normalization
    from renquant_model_gbdt.panel_trainer import (
        PANEL_LTR_PARAMS, panel_training_matrix, train_xgb)

    dd = Path(args.data_dir)
    panel, feats, _ = load_panel(dd, label=LAB)
    panel["date"] = pd.to_datetime(panel["date"])
    nb = partial(build_normalization, data_dir=dd)
    dates = np.array(sorted(panel["date"].unique()))
    folds = []
    for vi in np.array_split(np.arange(len(dates)), 6)[1:]:
        e = int(vi[0]) - EMBARGO
        if e > 0 and len(vi):
            folds.append({"tr": set(dates[:e]), "va": set(dates[vi])})
    print(f"panel {len(panel):,} · {len(folds)} folds · {len(SEEDS)} seeds", flush=True)

    def predict(tr, va, arm, seed):
        if arm == "rank60":
            mu, sd, k, _, _ = nb(tr, feats)
            b, _ = train_xgb(tr, feats, label=LAB,
                             params=dict(PANEL_LTR_PARAMS, seed=seed),
                             num_boost_round=N_ROUNDS, feature_means=mu,
                             feature_stds=sd, feature_norm_kind=k)
            return b.predict(xgb.DMatrix(
                panel_training_matrix(va, feats, mu, sd, k).values.astype(np.float64)))
        # blend = z(rank60) + z(top-decile classifier), per date
        p1 = predict(tr, va, "rank60", seed)
        y = (tr.groupby("date")[LAB].rank(pct=True) >= 0.9).astype(float)
        mu, sd, k, _, _ = nb(tr, feats)
        X = panel_training_matrix(tr, feats, mu, sd, k).values.astype(np.float64)
        b = xgb.train(dict(CLF, seed=seed), xgb.DMatrix(X, label=y.values),
                      num_boost_round=N_ROUNDS)
        p2 = b.predict(xgb.DMatrix(
            panel_training_matrix(va, feats, mu, sd, k).values.astype(np.float64)))
        d = va[["date"]].copy()
        d["p1"], d["p2"] = p1, p2

        def z(s):
            return (s - s.mean()) / (s.std() or 1.0)

        return (d.groupby("date")["p1"].transform(z)
                + d.groupby("date")["p2"].transform(z)).values

    def run(arm, placebo, seed):
        out = {}
        for f in folds:
            tr = panel[panel["date"].isin(f["tr"])].dropna(subset=[LAB])
            va = panel[panel["date"].isin(f["va"])]
            if placebo:
                tr = tr.copy()
                rng = np.random.default_rng(seed)
                tr[LAB] = tr.groupby("date")[LAB].transform(
                    lambda s: rng.permutation(s.values))
            p = predict(tr, va, arm, seed)
            sub = va[["date", "ticker", LAB]].copy()
            sub["score"] = p
            for d_, g in sub.dropna().groupby("date"):
                if len(g) >= 30:
                    out.setdefault(d_, []).append(g)
        return out

    def spread(cells, wins=None):
        r = {}
        for d_, gs in cells.items():
            vs = []
            for g in gs:
                v = g[LAB] if wins is None else g[LAB].clip(-wins, wins)
                vs.append(v.loc[g.nlargest(TOP_N, "score").index].mean() - v.mean())
            r[d_] = float(np.mean(vs))
        return pd.Series(r).sort_index()

    clean_series = {}
    for arm in ("rank60", "blend"):
        seed_clean, seed_clean_w = {}, {}
        for seed in SEEDS:
            t0 = time.time()
            rc = {d_: gs for d_, gs in run(arm, False, seed).items()}
            pc = {d_: gs for d_, gs in run(arm, True, seed).items()}
            r, p = spread(rc), spread(pc)
            rw, pw = spread(rc, wins=0.5), spread(pc, wins=0.5)
            c = r.index.intersection(p.index)
            seed_clean[seed] = (r[c] - p[c])
            seed_clean_w[seed] = (rw[c] - pw[c])
            print(f"  {arm} seed {seed}: clean {seed_clean[seed].mean():+.4f} "
                  f"w50 {seed_clean_w[seed].mean():+.4f} [{time.time()-t0:.0f}s]",
                  flush=True)
        df = pd.DataFrame(seed_clean)
        dfw = pd.DataFrame(seed_clean_w)
        clean_series[arm] = df.mean(axis=1).sort_index()
        clean_series[arm + "_w50"] = dfw.mean(axis=1).sort_index()
        clean_series[arm + "_by_seed"] = df

    a = clean_series["blend"]
    b_ = clean_series["rank60"]
    c = a.index.intersection(b_.index)
    diff = (a[c] - b_[c]).sort_index()
    # guard (b), EXACTLY as frozen in the prereg: winsorized-±50% clean-spread
    # difference must be >= 0 (blend minus rank60, seed-averaged, common dates)
    aw = clean_series["blend_w50"]
    bw = clean_series["rank60_w50"]
    cw = aw.index.intersection(bw.index)
    wins_diff_series = (aw[cw] - bw[cw]).sort_index()
    wins_diff = float(wins_diff_series.mean())

    lo, hi = block_bootstrap_ci(diff)

    by_seed_a = clean_series["blend_by_seed"]
    by_seed_b = clean_series["rank60_by_seed"]
    seed_signs = []
    for s in SEEDS:
        ca = by_seed_a[s].dropna()
        cb = by_seed_b[s].dropna()
        cc = ca.index.intersection(cb.index)
        seed_signs.append(float((ca[cc] - cb[cc]).mean()))
    n_pos = sum(1 for x in seed_signs if x > 0)

    verdict = decide_verdict(lo, float(diff.mean()), n_pos, wins_diff)

    print("\n" + "=" * 70, flush=True)
    print("CONFIRMATORY RESULT (prereg 2026-07-25)", flush=True)
    print("=" * 70, flush=True)
    print(f"  blend clean spread : {a.mean():+.4f}/60d", flush=True)
    print(f"  rank60 clean spread: {b_.mean():+.4f}/60d", flush=True)
    print(f"  paired diff        : {diff.mean():+.4f}  90% CI [{lo:+.4f},{hi:+.4f}]", flush=True)
    print(f"  guard: seeds positive {n_pos}/10 (need ≥{MIN_SEEDS_POSITIVE})", flush=True)
    print(f"  guard: winsorized ±50% diff {wins_diff:+.4f} (need ≥ 0)", flush=True)
    print(f"  VERDICT: {verdict}", flush=True)

    run_finished_at = datetime.now(timezone.utc).isoformat()
    manifest = build_manifest(data_dir=dd, argv=sys.argv, run_started_at=run_started_at,
                               run_finished_at=run_finished_at, panel=panel)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"prereg": "doc/research/2026-07-25-objective-blend-confirmatory-prereg.md",
               "seeds": list(SEEDS), "diff_mean": float(diff.mean()),
               "ci90": [lo, hi], "seeds_positive": n_pos,
               "winsorized_w50_diff": wins_diff, "verdict": verdict,
               "blend_clean": float(a.mean()), "rank60_clean": float(b_.mean()),
               "per_seed_diff_means": seed_signs,
               "manifest": manifest,
               "series": serialize_result(clean_series, diff, wins_diff_series)},
              open(out_path, "w"), indent=2)
    print(f"\nwrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
