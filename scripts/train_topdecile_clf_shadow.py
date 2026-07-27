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

Provenance: stamps TOP-LEVEL ``effective_train_cutoff_date`` (the max
panel date actually trained on, AFTER the label dropna — computed from
the data) so the runtime shadow health record sees the training cutoff
instead of degrading with ``missing_train_cutoff``; see the placement
note in ``main()`` for why top-level (not metadata-nested) is required
and fingerprint-safe.

SHADOW-ONLY GUARD: refuses any output path whose resolved path components
do not include a literal ``shadow`` component, or that include a
production-marker component (fail-closed on path components, not a
substring match — see ``refuse_non_shadow``).

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

from renquant_common.model_fingerprint import model_content_sha256
from renquant_model_gbdt.panel_data import attach_inference_smoke

# The frozen classifier params — byte-identical to the confirmatory
# executor's CLF block (single source of the frozen construction).
CLF_PARAMS = {"objective": "binary:logistic", "eta": 0.05, "max_depth": 5,
              "min_child_weight": 50, "subsample": 0.7, "colsample_bytree": 0.7,
              "verbosity": 0, "eval_metric": "logloss"}
N_ROUNDS = 100
LABEL = "fwd_60d_excess"
TOP_DECILE = 0.9

_FORBIDDEN_COMPONENTS = frozenset({"prod", "production", "strategy_config", "walkforward", "walk_forward"})


def refuse_non_shadow(path: Path) -> Path:
    """Fail-closed shadow-only output guard, checked on path COMPONENTS (not
    substring): a path like ``/tmp/production-shadow/model.json`` or
    ``/tmp/prod/shadow.json`` must be refused even though the string
    "shadow" appears somewhere in it — only a literal ``shadow`` directory
    component makes a path shadow-only, and any production-marker component
    refuses regardless."""
    resolved = path.resolve()
    components = [p.lower() for p in resolved.parts]
    if "shadow" not in components:
        raise SystemExit(f"refusing non-shadow output {resolved!r}: this trainer only "
                         "emits SHADOW artifacts (pipeline#213 rollout step 3); the "
                         "resolved path must contain a literal 'shadow' path component")
    hit = _FORBIDDEN_COMPONENTS.intersection(components)
    if hit:
        raise SystemExit(f"refusing output near production: path component(s) {sorted(hit)!r}")
    return path


def top_decile_label(train: pd.DataFrame, label: str = LABEL) -> pd.Series:
    """1{row's label is in its date's top decile} — the frozen construction."""
    return (train.groupby("date")[label].rank(pct=True) >= TOP_DECILE).astype(float)


def effective_train_cutoff(train: pd.DataFrame, label: str = LABEL) -> str:
    """Honest training-data cutoff: the max panel date actually trained on,
    computed AFTER the ``label`` dropna — rows with a NaN forward label are
    never trained on, so when a trailing window of panel dates has no
    ``fwd_60d`` label yet the raw panel max would overstate freshness by up
    to the label lookahead. Computed from the data, never hardcoded."""
    kept = train.dropna(subset=[label])
    if kept.empty:
        raise SystemExit(f"effective_train_cutoff: no rows with a non-NaN "
                         f"{label!r} label — refusing to stamp a cutoff")
    return pd.Timestamp(kept["date"].max()).strftime("%Y-%m-%d")


def stamp_contract(artifact: dict, booster, feat_cols: list[str]) -> dict:
    """Layer the production-compatible provenance/config contract onto the core
    v3 payload, reusing the SAME functions the umbrella's contract pipeline
    (``panel_data.StampFingerprintTask`` / ``AttachSmokeTask``) calls — so a
    shadow-slot fingerprint check sees the same ``config_fingerprint`` /
    ``metadata`` fields a production artifact carries.

    Must run BEFORE any shadow-only bookkeeping is added: this is what
    creates ``artifact["metadata"]`` (via ``attach_inference_smoke``), the
    OPERATIONAL-classified envelope the shadow-only fields nest into (see
    ``main()`` below) — new UNNESTED top-level keys are refused by
    ``model_content_sha256`` (``UnclassifiedKeyError``) because they are not
    in renquant-common's PREDICTIVE_KEYS/OPERATIONAL_KEYS tables, and that
    table is a modeling-contract change owned by that repo, not this script.
    """
    artifact["config_fingerprint"] = model_content_sha256(artifact)
    attach_inference_smoke(artifact, booster, feat_cols)
    return artifact


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
    # TOP-LEVEL, deliberately NOT nested under the "metadata" envelope: the
    # serving runtime (renquant-pipeline ``PanelScorer.load``) builds
    # ``scorer.metadata`` from TOP-LEVEL payload keys via
    # ``stamp_artifact_metadata``, and the shadow health record reads
    # ``scorer.metadata["effective_train_cutoff_date"]``
    # (``shadow_scoring.py``; a missing value degrades the shadow with
    # ``missing_train_cutoff``) — a metadata-nested copy would only surface
    # through a DEPRECATED flatten shim. Unlike the shadow-only fields below,
    # this key is SAFE at the top level: it is already classified OPERATIONAL
    # in renquant-common's fingerprint tables ("training-window provenance"),
    # so ``model_content_sha256`` / ``config_fingerprint`` are unchanged by
    # it. Stamped BEFORE stamp_contract so the hasher's total-classification
    # check validates the key at train time.
    cutoff = effective_train_cutoff(train)
    artifact["effective_train_cutoff_date"] = cutoff
    stamp_contract(artifact, booster, feat_cols)
    # Nested under the already-OPERATIONAL "metadata" envelope (schema-v1
    # classifies TOP-LEVEL keys and treats a nested value as one atomic unit
    # of its parent's classification) — NOT new top-level keys, which
    # renquant-common's total-classification hasher refuses outright
    # (Codex P1: a bare shadow_role/blend_spec/classifier_label_spec made
    # the artifact permanently unfingerprintable).
    artifact["metadata"]["shadow_role"] = "blend_clf_leg"
    artifact["metadata"]["blend_spec"] = {
        "formula": "z(prod_score) + z(clf_score) per date",
        "prereg": "model#75 doc/research/2026-07-25-blend-confirmatory-v2-prereg.md"}
    artifact["metadata"]["classifier_label_spec"] = {
        "kind": "top_decile_membership", "base_label": LABEL,
        "threshold_pct": TOP_DECILE}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact))
    pos_rate = float(y.mean())
    print(f"wrote {out}")
    print(f"rows={len(train):,} feats={len(feat_cols)} pos_rate={pos_rate:.3f} "
          f"trained_date={artifact.get('trained_date')} "
          f"effective_train_cutoff_date={cutoff}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
