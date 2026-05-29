"""Structural tests for the decomposed PatchTST sequence-training pipeline.

The Tasks call the heavy real trainer (torch/transformers/data), so behaviour is
verified by smoke runs; here we pin the Task/Job/Pipeline DECOMPOSITION so it
can't silently regress to a monolith.
"""
from __future__ import annotations

import argparse

import renquant_model_patchtst.hf_trainer as hf
from renquant_model_patchtst.sequence_training import (
    DataPrepJob,
    EvaluateJob,
    PersistModelJob,
    SequenceTrainingContext,
    TrainJob,
    build_sequence_training_pipeline,
)


def test_pipeline_has_four_ordered_jobs() -> None:
    p = build_sequence_training_pipeline()
    assert p.name == "patchtst-sequence-training"
    assert [type(j).__name__ for j in p.jobs] == [
        "DataPrepJob", "TrainJob", "EvaluateJob", "PersistModelJob"]


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
