"""The public fold-scoring contract: fail-closed validation + corpus golden."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from renquant_model_gbdt.fold_scoring import load_fold_scorer

B = Path(__file__).resolve().parent.parent / "doc/research/data/2026-08-01-clf-wf-lineage-bundle"


def _real_artifact() -> dict:
    lin = json.loads((B / "clf_lineage_manifest.json").read_text())
    return json.loads((B / lin["folds"][10]["artifact_path"]).read_text())


def test_stringified_norm_kind_is_refused_at_load():
    art = _real_artifact()
    art["feature_norm_kind"] = str(art["feature_norm_kind"])
    with pytest.raises(ValueError, match="stringified-norm_kind incident"):
        load_fold_scorer(art)


def test_missing_fields_and_keyset_mismatches_are_refused():
    art = _real_artifact()
    broken = dict(art); broken.pop("booster_raw_json")
    with pytest.raises(ValueError, match="missing required fields"):
        load_fold_scorer(broken)
    art2 = _real_artifact()
    art2["feature_stds"] = {k: v for k, v in list(art2["feature_stds"].items())[:-1]}
    with pytest.raises(ValueError, match="keyed exactly by feature_cols"):
        load_fold_scorer(art2)


def test_scorer_scores_the_real_artifact_and_preserves_the_index():
    art = _real_artifact()
    score = load_fold_scorer(art)
    rng = np.random.default_rng(5)
    frame = pd.DataFrame(rng.normal(size=(30, len(art["feature_cols"]))),
                         columns=art["feature_cols"],
                         index=pd.Index([f"T{i:02d}" for i in range(30)], name="ticker"))
    s = score(frame)
    assert list(s.index) == list(frame.index)
    assert s.between(0, 1).all()             # clf probabilities


def test_GOLDEN_reproduces_the_committed_corpus(request):
    """The contract's substantive guarantee: recipe-transform scoring of a whole
    OOS window reproduces the committed corpus < 1e-6. Loud-skip without the panel."""
    panel_path = Path("/Users/renhao/git/github/RenQuant/data/alpha158_291_fundamental_dataset.parquet")
    if not panel_path.is_file():
        pytest.skip("panel absent — the fail-closed loader tests above still run in CI")
    lin = json.loads((B / "clf_lineage_manifest.json").read_text())
    f = lin["folds"][10]
    art = json.loads((B / f["artifact_path"]).read_text())
    score = load_fold_scorer(art)
    corpus = pd.read_parquet(B / "clf_wf_scores.parquet")
    corpus["date"] = pd.to_datetime(corpus["date"])
    corpus["cutoff"] = pd.to_datetime(corpus["cutoff"])
    panel = pd.read_parquet(panel_path)
    panel["date"] = pd.to_datetime(panel["date"])
    w0, w1 = art["oos_window"]
    window = panel[(panel["date"] >= w0) & (panel["date"] <= w1)]
    frames = []
    for d, sub in window.groupby("date"):
        s = score(sub.set_index("ticker"))
        frames.append(pd.Series(s.values,
                                index=pd.MultiIndex.from_arrays([[d]*len(s), s.index])))
    got = pd.concat(frames)
    exp_rows = corpus[corpus["cutoff"] == pd.Timestamp(f["cutoff_date"])]
    expect = pd.Series(exp_rows["cal"].values,
                       index=pd.MultiIndex.from_frame(exp_rows[["date", "ticker"]]))
    j = pd.DataFrame({"e": expect, "g": got}).dropna()
    assert len(j) > 3000
    assert float((j["e"] - j["g"]).abs().max()) < 1e-6


def test_unnamed_index_is_refused_unconditionally():
    """Review round 1: the ticker-index guarantee must not depend on a 'ticker'
    column existing — an unnamed index is refused, full stop."""
    art = _real_artifact()
    score = load_fold_scorer(art)
    frame = pd.DataFrame(np.zeros((5, len(art["feature_cols"]))),
                         columns=art["feature_cols"])   # unnamed RangeIndex
    with pytest.raises(ValueError, match="TICKER-INDEXED"):
        score(frame)
