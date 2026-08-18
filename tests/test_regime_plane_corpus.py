"""Production regime-label plane consumed BY PATH (orch#985 ranked item 1).

The model families may not import renquant_pipeline / renquant_backtesting
(boundary tests; codex round-2 on model#65), so production-chain labels
arrive as the committed corpus renquant-backtesting publishes. These tests
cover the loader contract, the plane escape hatch, and the two repointed
harness sites — all against fixture corpora (no sibling checkout, no
production data).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path

import pandas as pd
import pytest

from renquant_model_common import regime_plane as rp


def _write_manifest(corpus: Path, *, series_sha256: str | None = None) -> Path:
    """Publisher-manifest sidecar; sha defaults to the true corpus hash."""
    p = rp.corpus_manifest_path(corpus)
    p.write_text(json.dumps({
        "series_sha256": series_sha256
        or hashlib.sha256(corpus.read_bytes()).hexdigest(),
        "generated_on": "2026-08-17",
        "chain": {"renquant_pipeline.kernel.regime": {"sha256": "x"}},
    }))
    return p


def _write_fixture_corpus(tmp_path: Path, *, manifest: bool = True) -> Path:
    """A corpus whose labels satisfy REGIME_GOLDEN_WINDOWS."""
    frames = []
    for start, end, regime in [
        ("2017-01-01", "2017-12-31", "BULL_CALM"),
        ("2020-02-20", "2020-04-30", "BEAR"),
        ("2022-04-01", "2022-06-30", "BEAR"),
    ]:
        dates = pd.bdate_range(start, end)
        frames.append(pd.DataFrame({"date": dates, "regime": regime}))
    df = pd.concat(frames, ignore_index=True)
    df["confidence"] = 0.9
    df["source"] = "fixture"
    corpus = tmp_path / "production_regime_labels.csv"
    df.assign(date=df["date"].dt.strftime("%Y-%m-%d")).to_csv(corpus, index=False)
    if manifest:
        _write_manifest(corpus)
    return corpus


def _write_raw_corpus(tmp_path: Path, rows: list[str]) -> Path:
    """Two-column corpus from literal rows, with a MATCHING manifest —
    isolates the series-validity checks from the provenance hash check."""
    corpus = tmp_path / "production_regime_labels.csv"
    corpus.write_text("date,regime\n" + "\n".join(rows) + "\n")
    _write_manifest(corpus)
    return corpus


# ── plane + loader contract ─────────────────────────────────────────────────

def test_plane_default_is_production(monkeypatch):
    monkeypatch.delenv(rp.REGIME_PLANE_ENV, raising=False)
    assert rp.resolve_regime_plane() == rp.PLANE_PRODUCTION


def test_plane_rejects_typo(monkeypatch):
    monkeypatch.setenv(rp.REGIME_PLANE_ENV, "prod")
    with pytest.raises(ValueError, match=rp.REGIME_PLANE_ENV):
        rp.resolve_regime_plane()


def test_default_corpus_path_is_sibling_backtesting():
    p = rp.default_corpus_path()
    assert p.name == "production_regime_labels.csv"
    assert "renquant-backtesting" in p.parts


def test_env_path_override_wins(monkeypatch, tmp_path):
    corpus = _write_fixture_corpus(tmp_path)
    monkeypatch.setenv(rp.REGIME_LABELS_PATH_ENV, str(corpus))
    assert rp.resolve_corpus_path() == corpus
    df = rp.load_production_regime_labels()
    assert {"date", "regime"} <= set(df.columns)
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_missing_corpus_raises_actionable(monkeypatch, tmp_path):
    monkeypatch.setenv(rp.REGIME_LABELS_PATH_ENV, str(tmp_path / "absent.csv"))
    with pytest.raises(FileNotFoundError) as exc:
        rp.load_production_regime_labels()
    msg = str(exc.value)
    assert rp.REGIME_LABELS_PATH_ENV in msg
    assert rp.PLANE_LEGACY_STATELESS in msg


def test_corpus_identity_stamps_manifest(monkeypatch, tmp_path):
    corpus = _write_fixture_corpus(tmp_path)
    ident = rp.corpus_identity(corpus)
    assert ident["corpus_path"] == str(corpus)
    assert len(ident["corpus_sha256"]) == 64
    assert ident["manifest_series_sha256"] == ident["corpus_sha256"]
    assert "renquant_pipeline.kernel.regime" in ident["chain"]


# ── provenance contract: manifest REQUIRED, hash verified before parse ──────
# codex review on model#228: a stale/tampered corpus must not run under the
# recorded production chain identity.

def test_missing_manifest_rejected(tmp_path):
    corpus = _write_fixture_corpus(tmp_path, manifest=False)
    with pytest.raises(ValueError, match="provenance manifest missing"):
        rp.load_production_regime_labels(corpus)


def test_malformed_manifest_rejected(tmp_path):
    corpus = _write_fixture_corpus(tmp_path)
    rp.corpus_manifest_path(corpus).write_text("{not json")
    with pytest.raises(ValueError, match="provenance manifest unreadable"):
        rp.load_production_regime_labels(corpus)


def test_manifest_without_series_sha_rejected(tmp_path):
    corpus = _write_fixture_corpus(tmp_path)
    rp.corpus_manifest_path(corpus).write_text(
        json.dumps({"generated_on": "2026-08-17"})
    )
    with pytest.raises(ValueError, match="lacks a series_sha256"):
        rp.load_production_regime_labels(corpus)


def test_series_hash_mismatch_rejected(tmp_path):
    corpus = _write_fixture_corpus(tmp_path)
    # tamper AFTER publish: bytes no longer match manifest.series_sha256
    corpus.write_text(
        corpus.read_text() + "2024-01-02,BEAR,0.9,tampered\n"
    )
    with pytest.raises(ValueError, match="stale or tampered"):
        rp.load_production_regime_labels(corpus)


# ── series validity: consumers must not silently join an invalid plane ──────

def test_duplicate_dates_rejected(tmp_path):
    corpus = _write_raw_corpus(tmp_path, [
        "2020-01-02,BEAR", "2020-01-02,BEAR", "2020-01-03,BEAR",
    ])
    with pytest.raises(ValueError, match="duplicate dates"):
        rp.load_production_regime_labels(corpus)


def test_non_monotonic_dates_rejected(tmp_path):
    corpus = _write_raw_corpus(tmp_path, [
        "2020-01-03,BEAR", "2020-01-02,BEAR",
    ])
    with pytest.raises(ValueError, match="not monotonically increasing"):
        rp.load_production_regime_labels(corpus)


def test_unknown_regime_label_rejected(tmp_path):
    corpus = _write_raw_corpus(tmp_path, [
        "2020-01-02,BEAR", "2020-01-03,SIDEWAYS",
    ])
    with pytest.raises(ValueError, match="unknown regime labels"):
        rp.load_production_regime_labels(corpus)


def test_null_regime_label_rejected(tmp_path):
    corpus = _write_raw_corpus(tmp_path, [
        "2020-01-02,BEAR", "2020-01-03,",
    ])
    with pytest.raises(ValueError, match="null regime labels"):
        rp.load_production_regime_labels(corpus)


# ── site (ii): RegimeDetectorContractTask ───────────────────────────────────

def _contract_ctx(tmp_path: Path):
    from renquant_model_patchtst import research_pipeline as rpip

    spec_kwargs = dict(
        phase="range_find",
        configs=["B_tuned"],
        cuts=["cut1"],
        seeds=[42],
        epochs=1,
        dataset=tmp_path / "panel.parquet",
        spy_path=tmp_path / "spy.parquet",
        data_dir=tmp_path,
        strategy_config=None,
        out_dir=tmp_path / "out",
        device="cpu",
        scheduler="linear",
        require_regime_contract=True,
    )
    spec = rpip.ExperimentSpec(**spec_kwargs)
    return rpip, rpip.ExperimentContext(spec=spec, trial_plan=[])


def test_contract_task_production_default_passes_on_fixture(
    monkeypatch, tmp_path,
):
    corpus = _write_fixture_corpus(tmp_path)
    monkeypatch.delenv(rp.REGIME_PLANE_ENV, raising=False)
    monkeypatch.setenv(rp.REGIME_LABELS_PATH_ENV, str(corpus))
    rpip, ctx = _contract_ctx(tmp_path)
    assert rpip.RegimeDetectorContractTask().run(ctx) is True
    rc = ctx.regime_contract
    assert rc["passed"] is True
    assert rc["regime_plane"] == rp.PLANE_PRODUCTION
    assert rc["module"] == "renquant_model_common.regime_plane"
    assert rc["corpus"]["corpus_path"] == str(corpus)
    assert "thresholds" not in rc  # stateless constants do not describe this plane
    assert set(rc["golden_window_counts"]) == {
        "covid_crash", "q2_2022_bear", "calm_2017",
    }


def test_contract_task_production_missing_corpus_fails_closed(
    monkeypatch, tmp_path,
):
    monkeypatch.delenv(rp.REGIME_PLANE_ENV, raising=False)
    monkeypatch.setenv(rp.REGIME_LABELS_PATH_ENV, str(tmp_path / "absent.csv"))
    rpip, ctx = _contract_ctx(tmp_path)
    assert rpip.RegimeDetectorContractTask().run(ctx) is False
    rc = ctx.regime_contract
    assert rc["passed"] is False
    assert rc["regime_plane"] == rp.PLANE_PRODUCTION
    assert any("corpus missing" in f for f in rc["failures"])
    assert ctx.verdict == "invalid_experiment"
    # and the label loader stays closed too — no stateless fallback
    from renquant_model_patchtst.research_pipeline import _load_regime_labels
    assert _load_regime_labels(ctx) is None


def test_contract_task_legacy_escape_hatch(monkeypatch, tmp_path):
    monkeypatch.setenv(rp.REGIME_PLANE_ENV, rp.PLANE_LEGACY_STATELESS)

    def fake_compute(spy_path, *, detector_version=None):
        dates = pd.date_range("2017-01-01", "2023-12-31", freq="B")
        return pd.DataFrame({"date": dates, "regime": ["BULL_CALM"] * len(dates)})

    monkeypatch.setattr(
        "renquant_common.hmm_regime_labels.compute_hmm_regime_labels",
        fake_compute,
    )
    rpip, ctx = _contract_ctx(tmp_path)
    ctx.spec.spy_path.write_bytes(b"")
    rpip.RegimeDetectorContractTask().run(ctx)
    rc = ctx.regime_contract
    assert rc["regime_plane"] == rp.PLANE_LEGACY_STATELESS
    assert rc["module"] == "renquant_common.hmm_regime_labels"
    assert "thresholds" in rc  # legacy stamping preserved verbatim


def test_load_regime_labels_production_uses_corpus(monkeypatch, tmp_path):
    corpus = _write_fixture_corpus(tmp_path)
    monkeypatch.delenv(rp.REGIME_PLANE_ENV, raising=False)
    monkeypatch.setenv(rp.REGIME_LABELS_PATH_ENV, str(corpus))
    rpip, ctx = _contract_ctx(tmp_path)
    ctx.regime_contract = {"passed": True}
    labels = rpip._load_regime_labels(ctx)
    assert labels is not None
    assert set(labels["regime"].unique()) == {"BULL_CALM", "BEAR"}


# ── site (iii): linear trainer regime map ───────────────────────────────────

def _linear_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        spy_path=str(tmp_path / "spy.parquet"),
        detector_version="v2026-05-31",
    )


def test_linear_regime_map_production_default(monkeypatch, tmp_path):
    from renquant_model_linear import trainer as lt

    corpus = _write_fixture_corpus(tmp_path)
    monkeypatch.delenv(rp.REGIME_PLANE_ENV, raising=False)
    monkeypatch.setenv(rp.REGIME_LABELS_PATH_ENV, str(corpus))
    regime_map = lt._resolve_regime_map(_linear_args(tmp_path))
    assert len(regime_map) > 0
    assert set(regime_map.values()) == {"BULL_CALM", "BEAR"}


def test_linear_regime_map_production_missing_corpus_empty(
    monkeypatch, tmp_path, caplog,
):
    from renquant_model_linear import trainer as lt

    monkeypatch.delenv(rp.REGIME_PLANE_ENV, raising=False)
    monkeypatch.setenv(rp.REGIME_LABELS_PATH_ENV, str(tmp_path / "absent.csv"))
    with caplog.at_level(logging.WARNING):
        regime_map = lt._resolve_regime_map(_linear_args(tmp_path))
    assert regime_map == {}
    assert any("production regime corpus unavailable" in r.message
               for r in caplog.records)


def test_linear_regime_map_legacy_escape_hatch(monkeypatch, tmp_path):
    from renquant_model_linear import trainer as lt

    monkeypatch.setenv(rp.REGIME_PLANE_ENV, rp.PLANE_LEGACY_STATELESS)

    def fake_compute(spy_path, *, detector_version=None):
        dates = pd.date_range("2020-01-01", periods=10, freq="B")
        return pd.DataFrame({"date": dates, "regime": ["CHOPPY"] * len(dates)})

    monkeypatch.setattr(
        "renquant_common.hmm_regime_labels.compute_hmm_regime_labels",
        fake_compute,
    )
    args = _linear_args(tmp_path)
    Path(args.spy_path).write_bytes(b"")
    regime_map = lt._resolve_regime_map(args)
    assert set(regime_map.values()) == {"CHOPPY"}
