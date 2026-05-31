"""CLI-surface tests for renquant_model_patchtst.research.

Pins the argparse → ExperimentSpec wiring so CLI flag changes can't
silently degrade the spec the harness runs against.

Specifically guards `--no-regime-contract`, the operator escape hatch
for known detector mislabels (e.g. calm_2017 → BULL_VOLATILE — tracked
separately). Bypass is temporary scaffolding; the default MUST stay
strict (require_regime_contract=True) so detector regressions can't
silently degrade Tier-3 evaluation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from renquant_model_patchtst.research import _parse_phase


def _capture_spec_from_main(argv: list[str], monkeypatch: pytest.MonkeyPatch):
    """Stub run_experiment + hf_trainer so we can inspect the ExperimentSpec
    that the CLI would have run.  Returns (spec, exit_code)."""
    captured: dict = {}

    def fake_run_experiment(spec, *, trainer_runner, parser_builder):
        captured["spec"] = spec

        class _Ctx:
            verdict = "promote_to_confirm"
            experiment_dir = Path("/tmp/x")

        return _Ctx()

    monkeypatch.setattr("renquant_model_patchtst.research.run_experiment",
                        fake_run_experiment)
    # Stub hf module so the `import renquant_model_patchtst.hf_trainer` at
    # main() entry doesn't pull torch.
    import sys
    fake_hf = type(sys)("renquant_model_patchtst.hf_trainer")
    fake_hf.train_single_run = lambda *a, **kw: {}
    fake_hf.build_parser = lambda: None
    monkeypatch.setitem(sys.modules, "renquant_model_patchtst.hf_trainer",
                        fake_hf)

    from renquant_model_patchtst.research import main as research_main
    rc = research_main(argv)
    return captured.get("spec"), rc


def test_default_argv_keeps_regime_contract_strict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """No CLI bypass → require_regime_contract=True (PRIME DIRECTIVE default)."""
    argv = [
        "--phase", "range_find",
        "--configs", "B_tuned",
        "--cuts", "cut1_covid",
        "--seeds", "42",
        "--epochs", "1",
        "--device", "cpu",
        "--out-dir", str(tmp_path),
    ]
    spec, rc = _capture_spec_from_main(argv, monkeypatch)
    assert rc == 0
    assert spec.require_regime_contract is True


def test_no_regime_contract_flag_disables_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """--no-regime-contract → require_regime_contract=False (operator opt-in)."""
    argv = [
        "--phase", "range_find",
        "--configs", "B_tuned",
        "--cuts", "cut1_covid",
        "--seeds", "42",
        "--epochs", "1",
        "--device", "cpu",
        "--out-dir", str(tmp_path),
        "--no-regime-contract",
    ]
    spec, rc = _capture_spec_from_main(argv, monkeypatch)
    assert rc == 0
    assert spec.require_regime_contract is False


def test_no_regime_contract_is_independent_of_no_placebos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The two bypass switches must be orthogonal — bypassing detector
    contract MUST NOT silently disable placebo gates, and vice versa."""
    argv = [
        "--phase", "range_find",
        "--configs", "B_tuned",
        "--cuts", "cut1_covid",
        "--seeds", "42",
        "--epochs", "1",
        "--device", "cpu",
        "--out-dir", str(tmp_path),
        "--no-regime-contract",   # bypass detector contract only
    ]
    spec, rc = _capture_spec_from_main(argv, monkeypatch)
    assert rc == 0
    assert spec.require_regime_contract is False
    assert spec.require_placebos is True  # untouched


def test_phase_aliases_resolve() -> None:
    """Sanity: phase aliases survive (covered indirectly by other tests but
    pinning here so a future refactor doesn't drop them)."""
    assert _parse_phase("0") == "range_find"
    assert _parse_phase("1") == "doe"
    assert _parse_phase("2") == "confirm"
    assert _parse_phase("range-find") == "range_find"
    with pytest.raises(SystemExit):
        _parse_phase("bogus")


# ---- W0.P0.2: --detector-version plumbing (PR #11 implementation plan) ----


def test_research_cli_default_detector_version_is_v20260531(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Default CLI invocation must use the post-fix detector so Phase A.0
    can run without the calm_2017 mislabel hard-failing the contract."""
    argv = [
        "--phase", "range_find",
        "--configs", "B_tuned",
        "--cuts", "cut1_covid",
        "--seeds", "42",
        "--epochs", "1",
        "--device", "cpu",
        "--out-dir", str(tmp_path),
    ]
    spec, rc = _capture_spec_from_main(argv, monkeypatch)
    assert rc == 0
    assert spec.detector_version == "v2026-05-31"


def test_research_cli_can_explicitly_override_to_legacy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`--detector-version legacy` opts back into the pre-fix detector for
    backward-compat experiments (e.g. reproducing pre-PR #3 numbers)."""
    argv = [
        "--phase", "range_find",
        "--configs", "B_tuned",
        "--cuts", "cut1_covid",
        "--seeds", "42",
        "--epochs", "1",
        "--device", "cpu",
        "--out-dir", str(tmp_path),
        "--detector-version", "legacy",
    ]
    spec, rc = _capture_spec_from_main(argv, monkeypatch)
    assert rc == 0
    assert spec.detector_version == "legacy"


def test_research_cli_detector_version_independent_of_regime_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`--no-regime-contract` and `--detector-version` are orthogonal —
    bypassing the contract MUST NOT silently flip the detector version."""
    argv = [
        "--phase", "range_find",
        "--configs", "B_tuned",
        "--cuts", "cut1_covid",
        "--seeds", "42",
        "--epochs", "1",
        "--device", "cpu",
        "--out-dir", str(tmp_path),
        "--no-regime-contract",
    ]
    spec, rc = _capture_spec_from_main(argv, monkeypatch)
    assert rc == 0
    assert spec.detector_version == "v2026-05-31"   # default still applies
    assert spec.require_regime_contract is False
