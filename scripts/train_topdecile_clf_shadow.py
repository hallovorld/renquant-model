#!/usr/bin/env python
"""Train the top-decile classifier SHADOW artifact (pipeline#213 §5 step 3).

Productionizes the classifier leg of the CONFIRMED blend objective
(model#74/#75/#76: screen -> frozen prereg -> disjoint-seed confirmatory,
+0.0687 CI90 [+0.0156,+0.1269]). The artifact is a standard v3 panel
scorer (kind ``panel_ltr_xgboost`` so the existing ``PanelScorer.load``
path serves it unchanged); its scores are the classifier probabilities,
and the BLEND is computed downstream (z(prod)+z(clf) per date) by the
readout job — never inside the scorer.

Label: per-date TOP-DECILE MEMBERSHIP of ``fwd_60d_excess`` (the frozen
construction). Params: the confirmatory executor's frozen CLF params.
Normalization: the production ``build_normalization`` pipeline, stamped
into the artifact so serving normalizes identically to training.

SHADOW-ONLY GUARD: refuses any output path that does not contain
``shadow`` and any path containing production markers.

Usage::

    python scripts/train_topdecile_clf_shadow.py \
        --data-dir /Users/renhao/git/github/RenQuant/data \
        --out .../artifacts/shadow/panel-clf.top-decile.fwd60.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# The frozen classifier params — byte-identical to the confirmatory
# executor's CLF block (single source of the frozen construction).
CLF_PARAMS = {"objective": "binary:logistic", "eta": 0.05, "max_depth": 5,
              "min_child_weight": 50, "subsample": 0.7, "colsample_bytree": 0.7,
              "verbosity": 0, "eval_metric": "logloss"}
N_ROUNDS = 100
LABEL = "fwd_60d_excess"
TOP_DECILE = 0.9

_FORBIDDEN = ("artifacts/prod", "strategy_config", "walkforward")


def refuse_non_shadow(path: Path) -> Path:
    s = str(path.resolve())
    if "shadow" not in s:
        raise SystemExit(f"refusing non-shadow output {s!r}: this trainer only "
                         "emits SHADOW artifacts (pipeline#213 rollout step 3)")
    for bad in _FORBIDDEN:
        if bad in s:
            raise SystemExit(f"refusing output near production: {bad!r}")
    return path


def top_decile_label(train: pd.DataFrame, label: str = LABEL) -> pd.Series:
    """1{row's label is in its date's top decile} — the frozen construction."""
    return (train.groupby("date")[label].rank(pct=True) >= TOP_DECILE).astype(float)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    out = refuse_non_shadow(Path(args.out))

    import xgboost as xgb
    from renquant_model_gbdt.panel_data import load_panel, build_normalization
    from renquant_model_gbdt.panel_trainer import (
        build_model_artifact, panel_training_matrix)

    data_dir = Path(args.data_dir)
    train, feat_cols, label = load_panel(data_dir, label=LABEL)
    train = train.dropna(subset=[LABEL])
    y = top_decile_label(train)
    mu, sd, norm_kind, clip_lo, clip_hi = build_normalization(train, feat_cols,
                                                              data_dir)
    X = panel_training_matrix(train, feat_cols, mu, sd, norm_kind)
    order = np.argsort(train["date"].values, kind="stable")
    d = xgb.DMatrix(X.values[order].astype(np.float64), label=y.values[order])
    booster = xgb.train(dict(CLF_PARAMS, seed=args.seed), d,
                        num_boost_round=N_ROUNDS)

    artifact = build_model_artifact(
        booster, feat_cols, mu, sd, train,
        params=dict(CLF_PARAMS, seed=args.seed),
        num_boost_round=N_ROUNDS, feature_norm_kind=norm_kind,
        feature_raw_clip_low=clip_lo, feature_raw_clip_high=clip_hi,
        label_used=LABEL, lookahead_days=60,
        training_notes=(
            "SHADOW top-decile classifier — the clf leg of the CONFIRMED "
            "blend objective (model#74/#75/#76; evidence "
            "doc/research/evidence/2026-07-25-blend-confirmatory-v2/). "
            "Scores are P(top decile of fwd_60d_excess). The blend "
            "z(prod)+z(clf) is computed by the readout job, not here. "
            "NOT a production scorer; deployment gated by pipeline#213's "
            "frozen forward readout."),
    )
    artifact["shadow_role"] = "blend_clf_leg"
    artifact["blend_spec"] = {"formula": "z(prod_score) + z(clf_score) per date",
                              "prereg": "model#75 doc/research/2026-07-25-blend-confirmatory-v2-prereg.md"}
    artifact["classifier_label_spec"] = {"kind": "top_decile_membership",
                                         "base_label": LABEL,
                                         "threshold_pct": TOP_DECILE}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact))
    pos_rate = float(y.mean())
    print(f"wrote {out}")
    print(f"rows={len(train):,} feats={len(feat_cols)} pos_rate={pos_rate:.3f} "
          f"trained_date={artifact.get('trained_date')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
