"""Structural tests for the decomposed PatchTST sequence-training pipeline.

The Tasks call the heavy real trainer (torch/transformers/data), so behaviour is
verified by smoke runs; here we pin the Task/Job/Pipeline DECOMPOSITION so it
can't silently regress to a monolith.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from pathlib import Path

import pandas as pd

import renquant_model_patchtst.hf_trainer as hf
from renquant_model_patchtst.sequence_training import (
    DataPrepJob,
    EvaluateJob,
    PersistModelJob,
    RecordTrainingRunTask,
    SequenceTrainingContext,
    TrainJob,
    build_sequence_training_pipeline,
)


def test_pipeline_has_four_ordered_jobs() -> None:
    p = build_sequence_training_pipeline()
    assert p.name == "patchtst-sequence-training"
    assert [type(j).__name__ for j in p.jobs] == [
        "DataPrepJob", "TrainJob", "EvaluateJob", "PersistModelJob",
        "RecordTrainingRunJob"]


def test_jobs_decompose_into_single_responsibility_tasks() -> None:
    assert [type(t).__name__ for t in DataPrepJob().tasks] == [
        "LoadPanelTask", "ComputeRegimeLabelsTask", "BuildDatasetsTask"]
    assert [type(t).__name__ for t in TrainJob().tasks] == [
        "BuildModelTask", "BuildTrainerTask", "RunTrainingTask"]
    assert [type(t).__name__ for t in EvaluateJob().tasks] == [
        "EvaluateTask", "DumpValPredsTask", "BuildSummaryTask"]
    assert [type(t).__name__ for t in PersistModelJob().tasks] == ["PersistModelTask"]


def test_persist_job_skipped_unless_save_model() -> None:
    off = SequenceTrainingContext(args=argparse.Namespace(save_model=False))
    on = SequenceTrainingContext(args=argparse.Namespace(save_model=True))
    assert PersistModelJob().should_skip(off) is True
    assert PersistModelJob().should_skip(on) is False


def test_train_one_is_a_thin_delegate_to_the_pipeline() -> None:
    # Guards against re-monolithising train_one (was ~205 lines pre-decomposition).
    assert "run_sequence_training" in hf.train_one.__code__.co_names
    import inspect
    assert len(inspect.getsource(hf.train_one).splitlines()) < 15


def test_compute_regime_labels_task_threads_detector_version(
    tmp_path: Path, monkeypatch,
) -> None:
    """W0.P0.2: ComputeRegimeLabelsTask must pass args.detector_version
    through to compute_hmm_regime_labels. Without this the trainer-side
    HMM labels would ignore the spec's detector choice."""
    from renquant_model_patchtst.sequence_training import ComputeRegimeLabelsTask

    spy = tmp_path / "spy.parquet"
    spy.write_bytes(b"")

    captured: dict = {}

    def fake_compute(spy_path, *, detector_version=None):
        captured["spy_path"] = spy_path
        captured["detector_version"] = detector_version
        return pd.DataFrame({"date": [], "regime": []})

    monkeypatch.setattr(
        "renquant_common.hmm_regime_labels.compute_hmm_regime_labels",
        fake_compute,
    )
    # hf.REPO / a.spy_path is the resolved path; using an absolute SPY path
    # via Path(...) lets us bypass the REPO prefix logic for this unit test.
    monkeypatch.setattr(hf, "REPO", tmp_path)

    ctx = SequenceTrainingContext(args=argparse.Namespace(
        spy_path=spy.name,  # under tmp_path
        detector_version="v2026-05-31",
        film_regime_cond=False,
    ))
    assert ComputeRegimeLabelsTask().run(ctx) is True
    assert captured["detector_version"] == "v2026-05-31"


def test_compute_regime_labels_task_defaults_to_v20260531_when_missing(
    tmp_path: Path, monkeypatch,
) -> None:
    """Backward compat: older script entrypoints whose argparse doesn't
    expose --detector-version (e.g. ad-hoc smoke runs) MUST still get the
    research-correct detector by default, not legacy."""
    from renquant_model_patchtst.sequence_training import ComputeRegimeLabelsTask

    spy = tmp_path / "spy.parquet"
    spy.write_bytes(b"")

    captured: dict = {}

    def fake_compute(spy_path, *, detector_version=None):
        captured["detector_version"] = detector_version
        return pd.DataFrame({"date": [], "regime": []})

    monkeypatch.setattr(
        "renquant_common.hmm_regime_labels.compute_hmm_regime_labels",
        fake_compute,
    )
    monkeypatch.setattr(hf, "REPO", tmp_path)

    # argparse.Namespace WITHOUT detector_version — simulating an old script.
    ctx = SequenceTrainingContext(args=argparse.Namespace(
        spy_path=spy.name,
        film_regime_cond=False,
    ))
    assert ComputeRegimeLabelsTask().run(ctx) is True
    assert captured["detector_version"] == "v2026-05-31"


def test_record_training_run_writes_canonical_training_columns(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = tmp_path / "sim_runs.db"
    _make_training_runs_db(db)
    monkeypatch.setenv("RENQUANT_TRAINING_DB", str(db))
    monkeypatch.setenv("RENQUANT_STRATEGY_NAME", "renquant_104")
    monkeypatch.setenv("RENQUANT_TRAIN_TRIGGER", "unit")
    def fake_run(args, **kwargs):
        stdout = "abc1234\n" if "rev-parse" in args else ""
        return subprocess.CompletedProcess(args, 0, stdout, "")

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    ctx = SequenceTrainingContext(
        args=argparse.Namespace(
            device="mps",
            cut="cut1_covid",
            seed=42,
            epochs=3,
            cross_stock_attn=True,
            film_regime_cond=False,
            training_window_years=5.0,
        ),
        panel=pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-02"]),
            "ticker": ["AAPL", "MSFT", "AAPL"],
        }),
        feat_cols=["alpha_1", "alpha_2"],
        out_dir=tmp_path / "out",
        best_val_ic=0.123,
        final_metrics={"train_ic": 0.456},
        config_contract={"config_fingerprint": "sha256:config"},
        summary={"n_features": 2, "trained_watchlist_n": 2},
    )

    assert RecordTrainingRunTask().run(ctx) is True

    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            """SELECT commit_sha, train_ic, n_rows, feature_cols, n_dates,
                      n_features, n_tickers, trigger, deterministic,
                      training_window_years
               FROM training_runs"""
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    (
        commit_sha,
        train_ic,
        n_rows,
        feature_cols,
        n_dates,
        n_features,
        n_tickers,
        trigger,
        deterministic,
        years,
    ) = row
    assert commit_sha == "abc1234"
    assert train_ic == 0.456
    assert n_rows == 3
    assert json.loads(feature_cols) == ["alpha_1", "alpha_2"]
    assert n_dates == 2
    assert n_features == 2
    assert n_tickers == 2
    assert trigger == "unit"
    assert deterministic == 0
    assert years == 5.0


def _make_training_runs_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("""
            CREATE TABLE training_runs (
                run_id TEXT PRIMARY KEY,
                run_date TIMESTAMP NOT NULL,
                strategy TEXT, artifact_type TEXT, config_json TEXT,
                oos_mean_ic REAL, train_ic REAL, n_rows INTEGER,
                feature_cols TEXT, artifact_path TEXT, commit_sha TEXT,
                elapsed_sec REAL, trigger TEXT, n_tickers INTEGER,
                n_dates INTEGER, n_features INTEGER, device TEXT,
                deterministic INTEGER, training_window_years REAL, notes TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()
