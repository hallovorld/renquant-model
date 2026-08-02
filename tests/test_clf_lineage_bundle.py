"""Deterministic in-repo verification of the committed clf lineage bundle.

Review requirement on the lineage PR: a data-bearing PR must carry a verifier that
uses ONLY repo-contained paths — the rebuild script's /Users/... panel inputs are
provenance, not evidence CI can reach. Everything here recomputes from the committed
bytes: fold digests, the lineage root, order/count, artifact↔corpus alignment, and
the causal contract.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

B = Path(__file__).resolve().parent.parent / "doc/research/data/2026-08-01-clf-wf-lineage-bundle"


@pytest.fixture(scope="module")
def lineage() -> dict:
    return json.loads((B / "clf_lineage_manifest.json").read_text())


@pytest.fixture(scope="module")
def corpus() -> pd.DataFrame:
    df = pd.read_parquet(B / "clf_wf_scores.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df["cutoff"] = pd.to_datetime(df["cutoff"])
    return df


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_fold_count_order_and_digests_recompute(lineage):
    folds = lineage["folds"]
    assert len(folds) == 43
    cutoffs = [f["cutoff_date"] for f in folds]
    assert cutoffs == sorted(cutoffs), "folds must be cutoff-ordered"
    for f in folds:
        p = B / f["artifact_path"]
        assert p.is_file(), f["artifact_path"]
        assert _sha(p) == f["artifact_sha256"], f["cutoff_date"]


def test_lineage_root_sha_recomputes_from_committed_bytes(lineage):
    shas = [_sha(B / f["artifact_path"]) for f in lineage["folds"]]
    payload = (lineage["recipe_src_sha256"] + "\n" + "\n".join(shas) + "\n")
    assert hashlib.sha256(payload.encode()).hexdigest() == lineage["lineage_root_sha"]


def test_artifact_windows_align_with_the_committed_score_corpus(lineage, corpus):
    """The corpus is the CALLER-OWNED grid: per cutoff, its first scored date must
    equal the artifact's declared oos_window[0] — and the corpus, not the artifact,
    is the authority the gate consumes (backtesting#95's independent grid source)."""
    first_by_cutoff = corpus.groupby("cutoff")["date"].min()
    last_by_cutoff = corpus.groupby("cutoff")["date"].max()
    assert len(first_by_cutoff) == 43
    for f in lineage["folds"]:
        art = json.loads((B / f["artifact_path"]).read_text())
        cut = pd.Timestamp(f["cutoff_date"])
        assert cut in first_by_cutoff.index, f["cutoff_date"]
        corpus_first = first_by_cutoff[cut]
        corpus_last = last_by_cutoff[cut]
        assert pd.Timestamp(art["oos_window"][0]) == corpus_first, f["cutoff_date"]
        assert pd.Timestamp(art["oos_window"][1]) == corpus_last, f["cutoff_date"]


def test_causal_contract_holds_on_every_fold_against_the_corpus_grid(lineage, corpus):
    """effective_train_cutoff + embargo BDays < the CORPUS's first OOS date —
    the caller-grid form of the #94 contract, recomputed from committed bytes."""
    first_by_cutoff = corpus.groupby("cutoff")["date"].min()
    margins = []
    for f in lineage["folds"]:
        art = json.loads((B / f["artifact_path"]).read_text())
        etc = pd.Timestamp(art["effective_train_cutoff_date"])
        embargo = int(art["cutoff_embargo_days"])
        assert embargo == 60
        first_oos = first_by_cutoff[pd.Timestamp(f["cutoff_date"])]
        safe = etc + pd.offsets.BDay(embargo)
        assert safe < first_oos, (f["cutoff_date"], str(safe.date()), str(first_oos.date()))
        margins.append(len(pd.bdate_range(safe, first_oos)) - 1)
    assert min(margins) >= 1


def test_corpus_shape_matches_the_manifest_counts(corpus):
    man = json.loads((B / "clf_wf_manifest.json").read_text())
    c = man["counts"]
    assert len(corpus) == c["n_rows"] == 178191
    assert corpus["date"].nunique() == c["n_dates"] == 625
    assert corpus["ticker"].nunique() == c["n_tickers"] == 292
    assert corpus["fold_idx"].nunique() == c["n_folds"] == 43
