from __future__ import annotations

import subprocess
from pathlib import Path

from renquant_model_patchtst import hf_trainer as hf


def test_resolve_runtime_path_prefers_current_worktree(monkeypatch, tmp_path):
    spy = tmp_path / "data" / "ohlcv" / "SPY" / "1d.parquet"
    spy.parent.mkdir(parents=True)
    spy.write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(hf, "REPO", Path("/fallback/data/root"))

    assert hf.resolve_runtime_path("data/ohlcv/SPY/1d.parquet") == spy


def test_resolve_strategy_config_prefers_strategy_subrepo(monkeypatch, tmp_path):
    strategy_cfg = tmp_path / "renquant-strategy-104" / "configs" / "strategy_config.json"
    legacy_dir = tmp_path / "RenQuant" / "backtesting" / "renquant_104"
    legacy_cfg = legacy_dir / "strategy_config.json"
    strategy_cfg.parent.mkdir(parents=True)
    legacy_dir.mkdir(parents=True)
    strategy_cfg.write_text("{}", encoding="utf-8")
    legacy_cfg.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("RENQUANT_STRATEGY_CONFIG", raising=False)
    monkeypatch.setattr(hf, "DEFAULT_STRATEGY_REPO_CONFIG", strategy_cfg)
    monkeypatch.setattr(hf, "STRATEGY_DIR", legacy_dir)

    assert hf.resolve_strategy_config_path() == strategy_cfg.resolve()


def test_git_head_uses_model_repo_not_runtime_data_root(monkeypatch, tmp_path):
    calls = {}

    def fake_run(args, *, cwd, capture_output, text, check):
        calls["cwd"] = cwd
        return subprocess.CompletedProcess(args, 0, "abc123\n", "")

    monkeypatch.setattr(hf, "REPO", tmp_path / "RenQuant")
    monkeypatch.setattr(hf.subprocess, "run", fake_run)

    assert hf.git_head() == "abc123"
    assert calls["cwd"] == hf.MODEL_REPO
