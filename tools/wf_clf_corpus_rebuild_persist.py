"""Walk-forward clf corpus REBUILD with per-fold artifact persistence + lineage
manifest (GOAL-6 Job A, model#180; the renquant-backtesting#94 Stage-1b on-ramp).

COPIED from the committed closure-bundle driver `wf_clf_corpus.py` (provenance:
doc/research/data/2026-07-29-clf-wf-closure-bundle/artifacts/clf-wf/) with exactly two
additions, both AFTER each fold's booster is trained: (1) the fold artifact is
PERSISTED with the #94 admissibility fields self-carried (feature contract,
cutoff_date, cutoff_embargo_days, effective_train_cutoff_date, booster bytes, content
sha); (2) a lineage manifest is written at the end:
`lineage_root_sha = sha256(recipe_src_sha256 + "\n" + "\n".join(ordered fold shas)
+ "\n")` per the merged #94 identity model. The RECIPE and the corpus arithmetic are
byte-unchanged from the original driver.

Original driver docstring follows.

Walk-forward OOS score corpus for the CERTIFIED top-decile classifier recipe.

GOAL-6 Stage 0 coverage gap: the classifier leg of the confirmed blend
(model#74/#75/#76, served as artifacts/shadow/panel-clf.top-decile.fwd60.json)
has only ONE full-sample fit and therefore no walk-forward out-of-sample
evidence. This driver produces that corpus.

RECIPE IS NOT CHANGED. Every modelling decision is imported live from
``renquant-model/scripts/train_topdecile_clf_shadow.py`` and the
``renquant_model_gbdt`` primitives it calls:

    CLF_PARAMS, N_ROUNDS, LABEL, TOP_DECILE   (frozen confirmatory block)
    top_decile_label()                        (frozen label construction)
    effective_train_cutoff()                  (honest post-dropna cutoff)
    build_normalization()                     (PIT refit of fund robust-z)
    panel_training_matrix()                   (train-space feature transform)

The ONLY thing this driver adds is the walk-forward *slicing*: per fold it
restricts training to ``date < cutoff - lookahead BDay`` using the recipe's own
``load_panel`` cutoff contract (``panel_data.load_panel`` L78-84,
``infer_label_lookahead_days``), then scores the fold's disjoint OOS window.

READ-ONLY over RenQuant/data and the WF manifest. Writes only under this
scratchpad directory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RQ = Path("/Users/renhao/git/github/RenQuant")
DATA = RQ / "data"
# The 43-fold prod-recipe grid (2023-10-02 .. 2026-03-02, 21-day cadence) —
# the SAME grid the PatchTST WF corpus uses, read read-only from the committed
# prod manifest so the three subjects share one cutoff axis.
WF_MANIFEST = (RQ / "backtesting/renquant_104/artifacts/sim/"
               "walkforward_manifest_gbdt_prod_recipe_v2.calibrated.json")
RECIPE_SRC = Path("/Users/renhao/git/github/renquant-model/scripts/"
                  "train_topdecile_clf_shadow.py")
OUT = (Path(__file__).resolve().parent.parent / "doc/research/data/2026-08-01-clf-wf-lineage-bundle")
LAST_FOLD_TRADING_DAYS = 21  # matches wf-eval/score_folds.py
SEED = 42  # the served artifact's seed


def _load_recipe():
    spec = importlib.util.spec_from_file_location("_recipe", RECIPE_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_head(repo: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=0,
                    help="smoke: only run the first N folds (0 = all)")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    t_start = time.time()
    recipe = _load_recipe()
    from renquant_model_gbdt.panel_data import (
        build_normalization, infer_label_lookahead_days, load_panel)
    from renquant_model_gbdt.panel_trainer import panel_training_matrix
    import xgboost as xgb

    LABEL = recipe.LABEL
    LOOKAHEAD = infer_label_lookahead_days(LABEL)  # 60, from the label name

    manifest = json.loads(WF_MANIFEST.read_text())
    cutoffs = [pd.Timestamp(r["cutoff_date"]) for r in manifest["retrains"]]
    assert len(cutoffs) == 43, f"expected the 43-fold grid, got {len(cutoffs)}"
    assert all(int(r["lookahead_days"]) == LOOKAHEAD for r in manifest["retrains"]), \
        "grid lookahead disagrees with the recipe's label lookahead"

    # ---- panel, loaded ONCE (load_panel with no cutoff == the recipe's own
    # full-sample load: read parquet -> to_datetime -> feat_cols -> dropna(label))
    train_all, feat_cols, label = load_panel(DATA, label=LABEL)
    assert label == LABEL
    panel_raw = pd.read_parquet(DATA / "alpha158_291_fundamental_dataset.parquet")
    panel_raw["date"] = pd.to_datetime(panel_raw["date"])
    all_dates = np.sort(panel_raw["date"].unique())
    print(f"[panel] labeled={train_all.shape} raw={panel_raw.shape} "
          f"feats={len(feat_cols)} dates "
          f"{pd.Timestamp(all_dates[0]).date()}..{pd.Timestamp(all_dates[-1]).date()}",
          flush=True)

    n_folds = len(cutoffs) if args.folds <= 0 else min(args.folds, len(cutoffs))
    rows, fold_prov = [], []
    _persisted_folds: list[tuple[str, str]] = []
    for i in range(n_folds):
        cut = cutoffs[i]
        t0 = time.time()

        # --- WF slice: the recipe's OWN cutoff contract (panel_data.load_panel
        # L79-82): effective_cutoff = cutoff - lookahead BDay; train strictly
        # before it. train_all is already label-dropna'd, same as load_panel.
        effective_cutoff = cut - pd.offsets.BDay(max(0, LOOKAHEAD))
        train = train_all[train_all["date"] < effective_cutoff]
        if train.empty:
            raise ValueError(f"fold {i} {cut.date()}: no training rows")

        # --- OOS window: disjoint, (cut, next_cut]; last fold = next 21 sessions.
        if i + 1 < len(cutoffs):
            window = [d for d in all_dates if cut < d <= cutoffs[i + 1]]
        else:
            window = [d for d in all_dates if d > cut][:LAST_FOLD_TRADING_DAYS]
        if not window:
            raise ValueError(f"fold {i} {cut.date()}: empty OOS window")
        w0, w1 = pd.Timestamp(window[0]), pd.Timestamp(window[-1])

        # --- LEAKAGE ASSERTION (fails the fold, does not warn).
        # Same contract the prod corpus / WF gate enforce
        # (run_wf_gate._validate_static_sanity_oos_contract):
        #     effective_train_cutoff + lookahead BDay < first OOS score date
        # effective_train_cutoff is the recipe's own honest post-dropna max
        # training date, NOT the nominal cutoff.
        etc = pd.Timestamp(recipe.effective_train_cutoff(train, LABEL))
        safe_last_label = etc + pd.offsets.BDay(max(0, LOOKAHEAD))
        if not safe_last_label < w0:
            raise AssertionError(
                f"LEAKAGE fold {i} cutoff={cut.date()}: effective_train_cutoff "
                f"{etc.date()} + {LOOKAHEAD}BDay = {safe_last_label.date()} "
                f">= first OOS date {w0.date()}")
        if not etc < w0:
            raise AssertionError(f"fold {i}: train cutoff {etc.date()} >= {w0.date()}")

        # --- fit: the frozen recipe, verbatim (label, normalization, matrix,
        # date-stable row order, params, rounds, seed).
        y = recipe.top_decile_label(train, LABEL)
        mu, sd, norm_kind, clip_lo, clip_hi = build_normalization(
            train, feat_cols, DATA)
        X = panel_training_matrix(train, feat_cols, mu, sd, norm_kind)
        order = np.argsort(train["date"].values, kind="stable")
        dmat = xgb.DMatrix(X.values[order].astype(np.float64),
                           label=y.values[order])
        booster = xgb.train(dict(recipe.CLF_PARAMS, seed=SEED), dmat,
                            num_boost_round=recipe.N_ROUNDS)

        # --- score the OOS window with the fold's OWN normalization.
        oos = panel_raw[panel_raw["date"].isin(set(window))]
        Xo = panel_training_matrix(oos, feat_cols, mu, sd, norm_kind)
        do = xgb.DMatrix(Xo.values.astype(np.float64))
        prob = booster.predict(do)
        margin = booster.predict(do, output_margin=True)

        # --- Job A addition: persist THIS fold's artifact (the #94 admissibility
        # fields, self-carried, mirroring the gbdt window artifacts).
        fold_dir = OUT / "fold_artifacts" / str(cut.date())
        fold_dir.mkdir(parents=True, exist_ok=True)
        fold_art = {
            "kind": "panel-clf-top-decile",
            "recipe_src": str(RECIPE_SRC),
            "fold_index": i,
            "cutoff_date": str(cut.date()),
            "cutoff_embargo_days": int(LOOKAHEAD),
            "effective_train_cutoff_date": str(etc.date()),
            "oos_window": [str(w0.date()), str(w1.date())],
            "n_train_rows": int(len(train)),
            "seed": int(SEED),
            "feature_cols": list(feat_cols),
            "feature_means": {k: float(v) for k, v in zip(feat_cols, list(mu))},
            "feature_stds": {k: float(v) for k, v in zip(feat_cols, list(sd))},
            "feature_norm_kind": str(norm_kind),
            "booster_raw_json": booster.save_raw("json").decode("utf-8"),
        }
        fold_path = fold_dir / "panel-clf.top-decile.json"
        fold_path.write_text(json.dumps(fold_art, sort_keys=True))
        _persisted_folds.append((str(cut.date()), _sha256(fold_path)))
        rows.append(pd.DataFrame({
            "fold_idx": i,
            "cutoff": cut,
            "date": oos["date"].values,
            "ticker": oos["ticker"].astype(str).values,
            "raw": np.asarray(margin, dtype=float),
            "cal": np.asarray(prob, dtype=float),
            "fwd_60d_excess": oos[LABEL].astype(float).values,
        }))
        fold_prov.append({
            "fold_idx": i,
            "cutoff_date": cut.date().isoformat(),
            "nominal_effective_cutoff": effective_cutoff.date().isoformat(),
            "effective_train_cutoff_date": etc.date().isoformat(),
            "lookahead_days": LOOKAHEAD,
            "safe_last_label_date": safe_last_label.date().isoformat(),
            "oos_start": w0.date().isoformat(),
            "oos_end": w1.date().isoformat(),
            "n_oos_dates": len(window),
            "n_oos_rows": int(len(oos)),
            "n_train_rows": int(len(train)),
            "train_pos_rate": round(float(y.mean()), 6),
            "leakage_margin_bdays": int(np.busday_count(
                safe_last_label.date(), w0.date())),
        })
        print(f"[fold {i:02d}] cut={cut.date()} etc={etc.date()} "
              f"oos={w0.date()}..{w1.date()} n_dates={len(window)} "
              f"n_rows={len(oos)} train={len(train):,} "
              f"{time.time() - t0:.1f}s (elapsed {time.time() - t_start:.0f}s)",
              flush=True)

    out = pd.concat(rows, ignore_index=True)
    # disjointness: no date scored by two folds
    per_date_folds = out.groupby("date")["fold_idx"].nunique()
    assert per_date_folds.max() == 1, "OOS windows are NOT disjoint"

    suffix = f".{args.tag}" if args.tag else ""
    corpus = OUT / f"clf_wf_scores{suffix}.parquet"
    out.to_parquet(corpus, index=False)

    prov = {
        "subject": "top-decile classifier (blend clf leg)",
        "recipe": {
            "recipe_id": recipe.RECIPE_ID,
            "provenance_schema_version": recipe.PROVENANCE_SCHEMA_VERSION,
            "source": str(RECIPE_SRC),
            "source_sha256": _sha256(RECIPE_SRC),
            "renquant_model_head": _git_head(RECIPE_SRC.parents[1]),
            "driver": str(Path(__file__).resolve()),
            "driver_sha256": _sha256(Path(__file__).resolve()),
            "params": dict(recipe.CLF_PARAMS, seed=SEED),
            "num_boost_round": recipe.N_ROUNDS,
            "label": LABEL,
            "label_construction": {"kind": "top_decile_membership",
                                   "threshold_pct": recipe.TOP_DECILE},
            "lookahead_days": LOOKAHEAD,
            "n_features": len(feat_cols),
        },
        "inputs": {
            "panel": str(DATA / "alpha158_291_fundamental_dataset.parquet"),
            "panel_sha256": _sha256(DATA / "alpha158_291_fundamental_dataset.parquet"),
            "alpha_stats": str(DATA / "alpha158_qlib_dataset.stats.json"),
            "alpha_stats_sha256": _sha256(DATA / "alpha158_qlib_dataset.stats.json"),
            "fundamentals": str(DATA / "sec_fundamentals_daily.parquet"),
            "fundamentals_sha256": _sha256(DATA / "sec_fundamentals_daily.parquet"),
            "cutoff_grid_manifest": str(WF_MANIFEST),
            "cutoff_grid_manifest_sha256": _sha256(WF_MANIFEST),
        },
        "leakage_contract": (
            "per fold, IN CODE, raising AssertionError (fold fails, no warning): "
            "effective_train_cutoff_date + lookahead_days BDay < first OOS score "
            "date. effective_train_cutoff_date is the recipe's own "
            "effective_train_cutoff() = max panel date trained on AFTER the "
            "fwd_60d_excess dropna. Training slice itself is the recipe's own "
            "load_panel contract: date < cutoff_date - lookahead BDay."),
        "schema": {
            "fold_idx": "int, 0..42",
            "cutoff": "fold cutoff date (grid)",
            "date": "OOS score date",
            "ticker": "name",
            "raw": "pre-sigmoid booster margin (output_margin=True)",
            "cal": "P(top decile of fwd_60d_excess) — the SERVED score "
                   "(binary:logistic sigmoid). NOTE: the recipe carries NO "
                   "external calibrator (unlike the prod GBDT and PatchTST "
                   "corpora, whose `cal` is a fitted Platt/global calibrator); "
                   "`cal` here is the model's own probability output and is a "
                   "monotone transform of `raw`.",
            "fwd_60d_excess": "realized label at (date, ticker); NaN where unlabeled",
        },
        "counts": {
            "n_folds": int(out["fold_idx"].nunique()),
            "n_rows": int(len(out)),
            "n_dates": int(out["date"].nunique()),
            "n_tickers": int(out["ticker"].nunique()),
            "date_min": str(pd.Timestamp(out["date"].min()).date()),
            "date_max": str(pd.Timestamp(out["date"].max()).date()),
            "n_rows_with_label": int(out["fwd_60d_excess"].notna().sum()),
        },
        "folds": fold_prov,
        "wall_seconds": round(time.time() - t_start, 1),
        "smoke_only_folds": None if args.folds <= 0 else n_folds,
    }
    (OUT / f"clf_wf_manifest{suffix}.json").write_text(json.dumps(prov, indent=2))

    # --- Job A addition: the lineage manifest (renquant-backtesting#94 identity
    # model). recipe identity component = the recipe SOURCE sha (train script),
    # the same provenance anchor the corpus manifest records.
    recipe_sha = _sha256(RECIPE_SRC)
    ordered_shas = [sha for _, sha in _persisted_folds]
    root = hashlib.sha256(
        (recipe_sha + "\n" + "\n".join(ordered_shas) + "\n").encode("utf-8")
    ).hexdigest()
    lineage = {
        "schema": "clf-lineage-manifest-v1",
        "identity_model": "renquant-backtesting#94 (merged 2026-08-01)",
        "recipe_src_sha256": recipe_sha,
        "lineage_root_sha": root,
        "folds": [{"cutoff_date": c, "artifact_sha256": sha,
                   "artifact_path": f"fold_artifacts/{c}/panel-clf.top-decile.json"}
                  for c, sha in _persisted_folds],
        "root_rule": "sha256(recipe_src_sha256 + LF + LF-joined ordered fold shas + LF)",
    }
    (OUT / f"clf_lineage_manifest{suffix}.json").write_text(json.dumps(lineage, indent=2))
    print(json.dumps({"lineage_root_sha": root,
                      "n_persisted_folds": len(_persisted_folds)}, indent=2),
          flush=True)
    print(json.dumps({k: prov[k] for k in ("counts", "wall_seconds")}, indent=2),
          flush=True)
    print(f"[OK] disjoint windows; wrote {corpus}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
