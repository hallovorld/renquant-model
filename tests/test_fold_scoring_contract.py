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


def test_a_frame_indexed_by_the_WRONG_NAME_is_also_refused():
    """Anti-vacuity pair for the test above.

    `test_unnamed_index_is_refused_unconditionally` is satisfied by an implementation
    written `if frame.index.name is None: raise` — which would accept a frame indexed by
    `symbol`, or by `date`, and return a Series carrying that index while the published
    contract says ticker. The guarantee is that the index IS ticker, not merely that it
    is named; one test per direction is what makes that difference visible.
    """
    art = _real_artifact()
    score = load_fold_scorer(art)
    frame = pd.DataFrame(np.zeros((5, len(art["feature_cols"]))),
                         columns=art["feature_cols"],
                         index=pd.Index(["a", "b", "c", "d", "e"], name="symbol"))
    with pytest.raises(ValueError, match="TICKER-INDEXED"):
        score(frame)


def test_the_public_api_is_published_at_a_version_a_consumer_can_PIN():
    """Review round 1(2), the half that has no test yet.

    The version bump to 0.2.0 IS the remedy: a consumer declaring `renquant-model` with
    no floor can resolve to 0.1.0, where `fold_scoring` does not exist — the hidden
    cross-repo contract this module was created to end. Left untested, a later edit
    drops the floor and the remedy dies silently while the module still imports fine on
    every developer's machine, because they all have the source checked out.

    Regex rather than `tomllib`: this repo supports Python 3.10, where `tomllib` does
    not exist, and adding a parser dependency to read one field is the worse trade.
    """
    import re
    text = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    project = text.split("[project]", 1)[1]
    raw = re.search(r'^version = "([^"]+)"', project, re.M).group(1)
    assert tuple(int(x) for x in raw.split(".")[:2]) >= (0, 2), (
        f"fold_scoring was published at 0.2.0; pyproject now says {raw}, so a consumer "
        "pinning >=0.2.0 would no longer resolve to a package carrying it")
    # ...and the API needs xgboost, which lives in the `gbdt` extra — so a consumer's
    # pin has to carry the extra, not just the version.
    gbdt = re.search(r'^gbdt = \[([^\]]*)\]', text, re.M).group(1)
    assert "xgboost" in gbdt, gbdt
