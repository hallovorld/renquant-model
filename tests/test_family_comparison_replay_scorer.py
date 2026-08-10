"""Auditable control surface for scripts/family_comparison_replay_scorer.py.

Synthetic rehearsal fixture (adapted from the orchestrator rehearsal's
make_fixture mechanics): a small fake frozen corpus + extension panel pair
built in tmp_path, and a fixture harness carrying the SAME constant names
and shapes as the real frozen v2 harness (FEATS/CUTS/PARAMS/SEEDS/
CORPUS_SHA256). CORPUS_SHA256 is the TRUE sha of the fixture corpus, so
the scorer's pin assertion is exercised for real, not bypassed -- the sha
assertion is parameterized only through the harness argument, exactly as
in production.

Controls:
  (a) planted-signal recovery -- the corpus label is a monotone function
      of one feature, so the fold-8 boosters must recover that ordering
      in replay_score on the extension window;
  (b) determinism -- two end-to-end runs produce byte-identical CSVs;
  (c) manifest integrity -- the recorded output sha matches the file.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCORER = Path(__file__).resolve().parents[1] / "scripts" / "family_comparison_replay_scorer.py"

TICKERS = [f"T{i:02d}" for i in range(30)]
FEATS = ["ROC5", "ROC20", "RANK10", "RANK60", "BETA10", "MAX20", "MIN20", "RSV10"]
LABEL60 = "fwd_60d_excess"
W0, W1 = "2026-05-20", "2026-07-31"
CUTS = [("2016-01-01", "2018-12-31", "2019-04-01", "2019-12-31"),
        ("2016-01-01", "2019-12-31", "2020-04-01", "2020-12-31"),
        ("2016-01-01", "2020-12-31", "2021-04-01", "2021-12-31"),
        ("2016-01-01", "2021-12-31", "2022-04-01", "2022-12-31"),
        ("2016-01-01", "2022-12-31", "2023-04-01", "2023-12-31"),
        ("2016-01-01", "2023-12-31", "2024-04-01", "2024-12-31"),
        ("2016-01-01", "2024-12-31", "2025-04-01", "2025-12-31"),
        ("2016-01-01", "2025-12-31", "2026-04-01", "2026-05-07")]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def fixture_dir(tmp_path_factory):
    """Small synthetic corpus/extension pair + pin-true fixture harness."""
    fix = tmp_path_factory.mktemp("family_comparison_fixture")
    rng = np.random.default_rng(12345)

    # fake frozen corpus: the label is PLANTED as a monotone function of
    # ROC5, so a correct fold-8 replay must rank the extension by ROC5
    cdates = pd.bdate_range("2025-06-02", "2026-05-07").strftime("%Y-%m-%d")
    n = len(cdates) * len(TICKERS)
    corpus = pd.DataFrame({"date": np.repeat(cdates, len(TICKERS)),
                           "ticker": np.tile(TICKERS, len(cdates))})
    for c in FEATS:
        corpus[c] = rng.normal(size=n)
    corpus[LABEL60] = corpus["ROC5"].values + 0.1 * rng.normal(size=n)
    corpus_path = fix / "corpus_fixture.parquet"
    corpus.to_parquet(corpus_path, index=False)

    # fixture harness: same constant names/shapes as the real v2 harness;
    # CORPUS_SHA256 is the true fixture-corpus sha (pin assert exercised)
    harness_path = fix / "harness_fixture.py"
    harness_path.write_text(
        '"""FIXTURE harness -- synthetic stand-in for the frozen v2 harness."""\n'
        f"FEATS = {FEATS!r}\n"
        f"CUTS = {CUTS!r}\n"
        'PARAMS = {"objective": "rank:pairwise", "eta": 0.05, "max_depth": 5,\n'
        '          "min_child_weight": 5, "subsample": 0.7,\n'
        '          "colsample_bytree": 0.7, "nthread": 4, "verbosity": 0}\n'
        "SEEDS = (42, 43, 44)\n"
        f'CORPUS_SHA256 = "{_sha256(corpus_path)}"\n')

    # extension panel: features only + the planted ground-truth column
    # (the scorer never reads _planted; the test uses it as the oracle)
    edates = pd.bdate_range(W0, W1).strftime("%Y-%m-%d")
    ne = len(edates) * len(TICKERS)
    ext = pd.DataFrame({"date": np.repeat(edates, len(TICKERS)),
                        "ticker": np.tile(TICKERS, len(edates))})
    for c in FEATS:
        ext[c] = rng.normal(size=ne)
    ext["_planted"] = ext["ROC5"].values
    ext.to_parquet(fix / "ext_planted.parquet", index=False)
    return fix


def _run(fix: Path, out_csv: Path):
    res = subprocess.run(
        [sys.executable, str(SCORER), str(fix / "harness_fixture.py"),
         str(fix / "corpus_fixture.parquet"), str(fix / "ext_planted.parquet"),
         W0, W1, str(out_csv)],
        capture_output=True, text=True)
    assert res.returncode == 0, f"scorer failed:\n{res.stdout}\n{res.stderr}"
    return res


def test_end_to_end_controls(fixture_dir, tmp_path):
    out1 = tmp_path / "run1.csv"
    _run(fixture_dir, out1)
    pred = pd.read_csv(out1)

    # output contract: exactly the prediction surface, no labels
    assert list(pred.columns) == ["date", "ticker", "replay_score"]
    edates = pd.bdate_range(W0, W1).strftime("%Y-%m-%d")
    assert len(pred) == len(edates) * len(TICKERS)
    assert pred.date.min() >= W0 and pred.date.max() <= W1

    # (a) planted-signal recovery: per-date Spearman between replay_score
    # and the planted ordering must be strongly positive
    ext = pd.read_parquet(fixture_dir / "ext_planted.parquet")
    merged = pred.merge(ext[["date", "ticker", "_planted"]], on=["date", "ticker"])
    assert len(merged) == len(pred)
    ics = merged.groupby("date").apply(
        lambda g: g["replay_score"].corr(g["_planted"], method="spearman"),
        include_groups=False)
    assert ics.mean() > 0.5, f"planted ordering not recovered: mean IC {ics.mean():.3f}"

    # (c) manifest integrity: recorded output sha matches the file, and the
    # recorded input pins match independently recomputed hashes
    manifest = json.loads((tmp_path / "run1.csv.manifest.json").read_text())
    assert manifest["output_csv_sha256"] == _sha256(out1)
    assert manifest["frozen_corpus_sha256"] == _sha256(fixture_dir / "corpus_fixture.parquet")
    assert manifest["ext_parquet_sha256"] == _sha256(fixture_dir / "ext_planted.parquet")
    assert manifest["harness_sha256"] == _sha256(fixture_dir / "harness_fixture.py")
    assert manifest["seeds"] == [42, 43, 44]
    assert manifest["n_rows"] == len(pred)
    assert manifest["fold8_train_rows"] > 0

    # (b) determinism: a second end-to-end run is byte-identical
    out2 = tmp_path / "run2.csv"
    _run(fixture_dir, out2)
    assert out2.read_bytes() == out1.read_bytes()
    manifest2 = json.loads((tmp_path / "run2.csv.manifest.json").read_text())
    assert manifest2["output_csv_sha256"] == manifest["output_csv_sha256"]


def test_sha_pin_mismatch_fails_closed(fixture_dir, tmp_path):
    # a corpus that drifted from the harness pin must be refused
    drifted = tmp_path / "corpus_drifted.parquet"
    df = pd.read_parquet(fixture_dir / "corpus_fixture.parquet")
    df.iloc[0, df.columns.get_loc(LABEL60)] += 1.0
    df.to_parquet(drifted, index=False)
    res = subprocess.run(
        [sys.executable, str(SCORER), str(fixture_dir / "harness_fixture.py"),
         str(drifted), str(fixture_dir / "ext_planted.parquet"),
         W0, W1, str(tmp_path / "out.csv")],
        capture_output=True, text=True)
    assert res.returncode != 0
    assert "harness pin" in (res.stdout + res.stderr)
