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


# --- delta, second session ---------------------------------------------------------
# The five tests above were written by the concurrent claude session and are the
# substantive verifier; they are stronger than the version I had written in parallel
# (which I discarded), because they check the embargo MARGIN and pin each artifact's
# declared oos_window to the corpus's first/last date rather than merely to membership.
#
# Three gaps remain, and each is an instance of a shape this programme keeps hitting.


def test_the_manifest_DECLARES_the_root_rule_the_test_implements(lineage):
    """`root_rule` is a field in the shipped manifest, and nothing above reads it.

    So the test hardcodes one formula while the bundle publishes another string, and a
    divergence between them is invisible: the test keeps passing and the document keeps
    lying. That is the `asserted-instead-of-measured` shape, one level up — the rule is
    the artifact's own description of how it may be checked, so it has to be the rule
    that gets checked.
    """
    assert lineage["root_rule"] == (
        "sha256(recipe_src_sha256 + LF + LF-joined ordered fold shas + LF)")
    assert lineage["schema"] == "clf-lineage-manifest-v1"


def test_the_root_is_ORDER_SENSITIVE(lineage):
    """Anti-vacuity for the root recompute.

    "LF-joined ORDERED fold shas" is load-bearing: if the rule sorted instead, a
    manifest whose folds had been permuted would recompute clean and the ordering test
    would be the only thing standing between a shuffled lineage and a green suite.
    Swapping two digests must move the root.
    """
    shas = [f["artifact_sha256"] for f in lineage["folds"]]
    shas[0], shas[1] = shas[1], shas[0]
    payload = lineage["recipe_src_sha256"] + "\n" + "\n".join(shas) + "\n"
    assert hashlib.sha256(payload.encode()).hexdigest() != lineage["lineage_root_sha"]


def test_every_path_this_verifier_READS_is_inside_this_repository(lineage):
    """The review's actual requirement, made a test instead of a docstring.

    The finding was "use only paths inside this repo". The module says so in prose at
    the top; nothing enforces it, so the first convenient absolute path added later
    reintroduces exactly the defect — a verifier CI cannot run, passing locally on the
    one machine that has the umbrella checkout.
    """
    repo = Path(__file__).resolve().parent.parent
    read = [B / "clf_lineage_manifest.json", B / "clf_wf_manifest.json",
            B / "clf_wf_scores.parquet",
            *(B / f["artifact_path"] for f in lineage["folds"])]
    assert len(read) == 46, len(read)
    for p in read:
        assert p.is_file(), p
        assert p.resolve().is_relative_to(repo), p
    for f in lineage["folds"]:  # ...and no manifest path escapes the bundle
        assert not f["artifact_path"].startswith("/") and ".." not in f["artifact_path"]
