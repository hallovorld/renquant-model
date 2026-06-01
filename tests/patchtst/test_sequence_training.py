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
import pytest

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


def test_build_model_task_dispatches_to_patchtst_by_default() -> None:
    """PR #17 dispatch contract: default --model patchtst yields
    HFPatchTSTRanker; an args.Namespace missing the attribute entirely
    also yields PatchTST (backward-compat for older entrypoints)."""
    from renquant_model_patchtst.sequence_training import BuildModelTask

    n_features = 4
    common_args = dict(
        seq_len=24, patch_length=8, d_model=16, n_heads=2, n_layers=2,
        distributional_head=False, film_regime_cond=False, cross_stock_attn=False,
    )

    # Case 1: explicit --model patchtst
    ctx_explicit = SequenceTrainingContext(
        args=argparse.Namespace(model="patchtst", **common_args),
        feat_cols=[f"f{i}" for i in range(n_features)],
    )
    assert BuildModelTask().run(ctx_explicit) is True
    assert ctx_explicit.model.__class__.__name__ == "HFPatchTSTRanker"

    # Case 2: backward-compat — older args.Namespace without `model` attr
    ctx_no_attr = SequenceTrainingContext(
        args=argparse.Namespace(**common_args),
        feat_cols=[f"f{i}" for i in range(n_features)],
    )
    assert BuildModelTask().run(ctx_no_attr) is True
    assert ctx_no_attr.model.__class__.__name__ == "HFPatchTSTRanker"


def test_build_model_task_dispatches_to_patchtsmixer_when_selected() -> None:
    """PR #17 contract: --model patchtsmixer yields HFPatchTSMixerRanker.
    PatchTST-only flags (distributional_head, film_regime_cond,
    cross_stock_attn) MUST be accepted-but-ignored so the same trial argv
    works across model families."""
    import torch
    from renquant_model_patchtst.sequence_training import BuildModelTask

    n_features = 4
    ctx = SequenceTrainingContext(
        args=argparse.Namespace(
            model="patchtsmixer",
            seq_len=24, patch_length=8, d_model=16, n_heads=2, n_layers=2,
            # PatchTST-only flags — set True but should be no-op for mixer:
            distributional_head=True, film_regime_cond=True, cross_stock_attn=True,
        ),
        feat_cols=[f"f{i}" for i in range(n_features)],
    )
    assert BuildModelTask().run(ctx) is True
    assert ctx.model.__class__.__name__ == "HFPatchTSMixerRanker"
    # Output contract for patchtsmixer: only "score" key regardless of
    # the PatchTST-flag settings. No "loc"/"df"/"scale" from a dist head.
    out = ctx.model(past_values=torch.randn(2, 24, n_features))
    assert set(out.keys()) == {"score"}
    assert out["score"].shape == (2,)


def test_build_parser_accepts_model_choices() -> None:
    """hf_trainer's CLI exposes --model {patchtst,patchtsmixer}."""
    p = hf.build_parser()
    dests = {a.dest for a in p._actions}
    assert "model" in dests, "hf_trainer build_parser missing --model dest"
    # Defaults to PatchTST (backward compat with existing scripts).
    args = p.parse_args([])
    assert args.model == "patchtst"
    # patchtsmixer is accepted.
    args_mix = p.parse_args(["--model", "patchtsmixer"])
    assert args_mix.model == "patchtsmixer"


def test_build_parser_rejects_unknown_model_choice() -> None:
    """Typos / unknown models fail at argparse, not silently."""
    p = hf.build_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["--model", "stockmixer-lite"])


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


# ---- PR #17 review BLOCKERS — model-aware artifact identity ------------


def test_model_kind_from_args_known_choices() -> None:
    from renquant_model_patchtst.sequence_training import (
        MODEL_KIND_PATCHTST,
        MODEL_KIND_PATCHTSMIXER,
        model_kind_from_args,
    )
    assert model_kind_from_args(argparse.Namespace(model="patchtst")) == MODEL_KIND_PATCHTST
    assert model_kind_from_args(argparse.Namespace(model="patchtsmixer")) == MODEL_KIND_PATCHTSMIXER
    # Missing attr → default PatchTST (back-compat).
    assert model_kind_from_args(argparse.Namespace()) == MODEL_KIND_PATCHTST


def test_model_kind_from_args_rejects_unknown() -> None:
    import pytest as _pytest
    from renquant_model_patchtst.sequence_training import model_kind_from_args
    with _pytest.raises(ValueError, match="unknown --model"):
        model_kind_from_args(argparse.Namespace(model="lstm_typo"))


def test_compute_regime_labels_does_not_require_spy_for_patchtsmixer(
    tmp_path: Path,
) -> None:
    """PR #17 review HIGH-2: ``--film-regime-cond`` is PatchTST-only.
    For PatchTSMixer the flag should be accepted-but-ignored, NOT raise
    FileNotFoundError when SPY parquet is missing."""
    from renquant_model_patchtst.sequence_training import (
        ComputeRegimeLabelsTask, SequenceTrainingContext)
    missing_spy = tmp_path / "definitely_does_not_exist.parquet"
    ctx = SequenceTrainingContext(args=argparse.Namespace(
        spy_path=str(missing_spy),
        film_regime_cond=True,         # would historically raise
        model="patchtsmixer",          # but mixer ignores FiLM
        detector_version="v2026-05-31",
    ))
    # Monkey-patch hf.REPO so spy_path resolves under tmp_path (still missing).
    monkey = type("M", (), {"REPO": tmp_path})
    import renquant_model_patchtst.hf_trainer as _hf
    real_repo = _hf.REPO
    _hf.REPO = tmp_path
    try:
        assert ComputeRegimeLabelsTask().run(ctx) is True
    finally:
        _hf.REPO = real_repo
    # No SPY → no labels — that's fine for patchtsmixer
    assert ctx.hmm_labels is None


def test_compute_regime_labels_still_requires_spy_for_patchtst_film() -> None:
    """Counter-check: PatchTST + FiLM + missing SPY must STILL raise."""
    import pytest as _pytest
    from renquant_model_patchtst.sequence_training import (
        ComputeRegimeLabelsTask, SequenceTrainingContext)
    ctx = SequenceTrainingContext(args=argparse.Namespace(
        spy_path="/tmp/never_exists.parquet",
        film_regime_cond=True,
        model="patchtst",
        detector_version="v2026-05-31",
    ))
    import renquant_model_patchtst.hf_trainer as _hf
    real_repo = _hf.REPO
    _hf.REPO = Path("/")
    try:
        with _pytest.raises(FileNotFoundError, match="FiLM regime"):
            ComputeRegimeLabelsTask().run(ctx)
    finally:
        _hf.REPO = real_repo


def test_research_planning_uses_model_aware_filenames(tmp_path: Path) -> None:
    """PR #17 review BLOCKER-1: TrialSpec.val_preds_path / summary_path
    must use the model-kind prefix (hf_patchtsmixer for G_patchtsmixer)
    so PatchTSMixer artifacts don't collide with PatchTST in the same
    trial dir AND so the harness can locate them post-train."""
    from renquant_model_patchtst.research_pipeline import _model_kind_for_extras
    from renquant_model_patchtst.sequence_training import (
        MODEL_KIND_PATCHTST, MODEL_KIND_PATCHTSMIXER)

    assert _model_kind_for_extras(["--lr", "1e-3"]) == MODEL_KIND_PATCHTST
    assert _model_kind_for_extras(["--model", "patchtst", "--lr", "1e-3"]) == MODEL_KIND_PATCHTST
    assert _model_kind_for_extras(["--lr", "1e-3", "--model", "patchtsmixer"]) == MODEL_KIND_PATCHTSMIXER
    # Linear family — distinct trainer convention (PR #18 union into helper)
    assert _model_kind_for_extras(["--model", "dlinear"]) == "dlinear"
    assert _model_kind_for_extras(["--model", "nlinear"]) == "nlinear"
    # Unknown --model fail-fast at planning time (PR #18 reviewer
    # follow-up): a typo would otherwise burn trial compute and only
    # surface as missing val_preds during result aggregation.
    import pytest as _pytest
    with _pytest.raises(ValueError, match="unsupported --model"):
        _model_kind_for_extras(["--model", "lstm_typo"])


def test_research_configs_include_patchtsmixer() -> None:
    """PR #17 review HIGH-3: research CLI must expose PatchTSMixer
    through ExperimentPipeline so placebos / DSR/PBO / promotion gates
    apply to the baseline."""
    from renquant_model_patchtst.research import configs as research_configs
    cfgs = research_configs(spy_path="dummy.parquet")
    assert "G_patchtsmixer" in cfgs, (
        "research.configs must expose G_patchtsmixer so the harness can "
        "compare PatchTSMixer head-to-head with the PatchTST family")
    extras = cfgs["G_patchtsmixer"]
    assert "--model" in extras
    idx = extras.index("--model")
    assert extras[idx + 1] == "patchtsmixer"
