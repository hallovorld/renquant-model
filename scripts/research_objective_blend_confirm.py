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
import re
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


_RESULTS_SPLIT_RE = re.compile(rb"\n+(?:-{3,}\s*\n+)?## RESULTS")


def _frozen_prereg_bytes(raw: bytes) -> bytes:
    """The prereg's frozen decision-rule text only, excluding any
    `## RESULTS` section appended in place after the run (this repo's
    convention for preregs that record their own results, e.g. the
    blend-construction screen). The append also inserts a `---` horizontal
    rule directly above the heading as a visual separator (model#74 review,
    round 2): a plain `\\n## RESULTS` split leaves that rule attached to the
    "frozen" side, so its bytes differ from the pre-append file and
    `_prereg_freeze` misidentifies the append commit as a new freeze. The
    regex consumes an optional `---` rule (and its surrounding blank lines)
    together with the heading. Preregs that stay unmodified after freeze (no
    such heading — the confirmatory preregs, whose results land in a
    separate file) return their content unchanged."""
    m = _RESULTS_SPLIT_RE.search(raw)
    return raw if m is None else raw[:m.start()].rstrip() + b"\n"


def _is_shallow_repo(repo_dir: Path) -> bool:
    """True if `repo_dir` is a shallow clone (`actions/checkout@v4`'s
    default, fetch-depth 1) — model#74 review round 5 P1: a shallow clone
    can only ever show the checked-out boundary commit for a file's
    history, so `_prereg_freeze`'s self-consistency check (frozen-at-commit
    == frozen-on-disk) is trivially satisfied by that single commit even
    when the true freeze happened earlier and fell outside the shallow
    window. Unknown (git error) is treated as NOT shallow — this helper
    only widens the set of runs that fail closed, never narrows it."""
    proc = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=repo_dir,
                          capture_output=True, text=True)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _prereg_freeze(repo_dir: Path, prereg_path: Path = PREREG_PATH) -> tuple[str | None, str | None]:
    """(commit, digest) of the prereg's pre-run freeze — model#74 review
    BLOCKER: `git log -1` over the whole file picks up a LATER commit that
    only appended a `## RESULTS` section, stamping the manifest with the
    post-run edit instead of the actual pre-run freeze. This walks the
    file's full history and returns the last commit at which the FROZEN
    section (text before `## RESULTS`) changed — the true freeze point —
    with the digest of that frozen text only, not the whole (possibly
    RESULTS-amended) current file. Returns (None, None) if the frozen text
    at that commit doesn't match the frozen text on disk right now (history
    inconsistent with the working copy), or if `repo_dir` is a shallow
    clone (round 5 P1: truncated history must fail closed, never stamp a
    boundary commit as the freeze)."""
    if _is_shallow_repo(repo_dir):
        return None, None
    try:
        rel = str(prereg_path.relative_to(repo_dir))
    except ValueError:
        return None, None
    try:
        proc = subprocess.run(
            ["git", "log", "--format=%H", "--reverse", "--", rel],
            cwd=repo_dir, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None, None
    commits = proc.stdout.split()
    if not commits or not prereg_path.exists():
        return None, None
    current_frozen = _frozen_prereg_bytes(prereg_path.read_bytes())
    freeze_commit, freeze_frozen = None, None
    for sha in commits:
        show = subprocess.run(["git", "show", f"{sha}:{rel}"], cwd=repo_dir,
                              capture_output=True)
        if show.returncode != 0:
            continue
        frozen = _frozen_prereg_bytes(show.stdout)
        if frozen != freeze_frozen:
            freeze_commit, freeze_frozen = sha, frozen
    if freeze_frozen != current_frozen:
        return None, None
    return freeze_commit, hashlib.sha256(freeze_frozen).hexdigest()


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


def _repo_relative(path: Path, repo_dir: Path) -> str:
    """POSIX-relative form of `path` under `repo_dir`, else the absolute
    string unchanged (model#76 review round 2: the manifest's `prereg_path`/
    `command` must record the same repo-relative form the prereg's frozen
    invocation uses — a workstation-absolute path fails a literal comparison
    against the frozen command string even when the target file is
    identical)."""
    try:
        return path.resolve().relative_to(repo_dir).as_posix()
    except ValueError:
        return str(path)


def _canonicalize_command(argv: list[str], repo_dir: Path) -> str:
    """Repo-relative form of every in-repo absolute path token in `argv`, so
    `manifest["command"]` matches the prereg's frozen invocation regardless
    of whether the run happened to be launched with absolute or relative
    arguments. Tokens outside `repo_dir` (e.g. a cross-repo `--data-dir`)
    are left as-is — `data_path`/`data_dir` are workstation-local by design
    (model#73 review HIGH: `data_digest` + `producing_script.git_revision`
    are the portable proxies for that input, not the raw path)."""
    tokens = []
    for tok in argv:
        p = Path(tok)
        tokens.append(_repo_relative(p, repo_dir) if p.is_absolute() else tok)
    return " ".join(tokens)


def build_manifest(*, data_dir: Path, argv: list[str], run_started_at: str,
                    run_finished_at: str, panel: pd.DataFrame,
                    prereg_path: Path = PREREG_PATH) -> dict:
    """Reproducibility + pre-run-freeze manifest (model#68 review rounds
    3-4; model#73 review HIGH). `prereg_digest` proves which frozen
    decision-rule text the run executed against; a results PR is only an
    honest confirmatory read if `run_started_at` postdates the prereg's own
    frozen commit and this digest matches the prereg file at that commit.
    `row_count`/`date_range` plus `producing_script.git_revision` are a
    durable fingerprint for the input panel, independent of the
    workstation-absolute `data_path`. `prereg_path` defaults to this
    executor's own frozen 10-seed confirmatory prereg but is overridable
    (model#74/#75 review: a pre-registered replay under a different frozen
    seed set — a screen or a fresh-seed confirmatory — must stamp digest/
    commit against the prereg text actually governing that run, not this
    file's default)."""
    from renquant_model_gbdt.panel_data import PANEL_FILE
    repo_dir = Path(__file__).resolve().parents[1]
    panel_path = data_dir / PANEL_FILE
    data_digest = _sha256_file(panel_path)
    dates = pd.to_datetime(panel["date"])
    code_revision = _git_revision(repo_dir)
    prereg_commit, prereg_digest = _prereg_freeze(repo_dir, prereg_path)
    if prereg_commit is None or prereg_digest is None:
        raise RuntimeError(
            f"cannot resolve the pre-run freeze for {prereg_path} — the repo "
            "is a shallow clone or the file's git history is inconsistent "
            "with the working copy (model#74 review round 6 BLOCKER: a null "
            "prereg_commit/prereg_digest must never reach a written bundle). "
            "Remediation: re-checkout with full history, e.g. "
            "`git fetch --unshallow`, then re-run.")
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
        "prereg_path": _repo_relative(prereg_path, repo_dir),
        "prereg_digest": f"sha256:{prereg_digest}" if prereg_digest else None,
        "prereg_commit": prereg_commit,
        "code_revision": code_revision,
        "code_revision_parents": _git_revision_parents(repo_dir),
        "prereg_commit_is_ancestor_of_code_revision":
            _is_ancestor(prereg_commit, code_revision, repo_dir),
        "command": _canonicalize_command(argv, repo_dir),
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
    ap.add_argument("--seeds", default=None,
                    help="comma-separated seed override, e.g. '42,43,44'. Default is "
                         "the frozen 10-seed confirmatory SEEDS constant. For a "
                         "pre-registered replay under a different frozen seed set "
                         "(a screen or a fresh-seed confirmatory), this is the reviewed, "
                         "immutable run input the prereg cites — nothing else in the "
                         "executor may change.")
    ap.add_argument("--prereg-path", default=None,
                    help="override PREREG_PATH so the manifest's prereg_digest/"
                         "prereg_commit stamp against the prereg text actually "
                         "governing this run, instead of the default confirmatory prereg")
    args = ap.parse_args()
    out_path = Path(args.out)
    for bad in _FORBIDDEN:
        if bad in str(out_path.resolve()):
            raise SystemExit(f"refusing output near production: {bad!r}")
    seeds = tuple(int(s) for s in args.seeds.split(",")) if args.seeds else SEEDS
    repo_dir = Path(__file__).resolve().parents[1]
    prereg_path = Path(args.prereg_path).resolve() if args.prereg_path else PREREG_PATH
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
    print(f"panel {len(panel):,} · {len(folds)} folds · {len(seeds)} seeds", flush=True)

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
        for seed in seeds:
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
    for s in seeds:
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
    print(f"  guard: seeds positive {n_pos}/{len(seeds)} (need ≥{MIN_SEEDS_POSITIVE})", flush=True)
    print(f"  guard: winsorized ±50% diff {wins_diff:+.4f} (need ≥ 0)", flush=True)
    print(f"  VERDICT: {verdict}", flush=True)

    run_finished_at = datetime.now(timezone.utc).isoformat()
    manifest = build_manifest(data_dir=dd, argv=sys.argv, run_started_at=run_started_at,
                               run_finished_at=run_finished_at, panel=panel,
                               prereg_path=prereg_path)

    prereg_label = _repo_relative(prereg_path, repo_dir)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"prereg": prereg_label,
               "seeds": list(seeds), "diff_mean": float(diff.mean()),
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
