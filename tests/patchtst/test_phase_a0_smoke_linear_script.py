"""Structural tests for scripts/run_phase_a0_smoke_linear.sh.

PR #18 ships the linear-baseline smoke runner (sibling to PR #13's
PatchTST smoke). These tests pin:

  * the script exists, is executable, and uses the safe set-flags
  * the harness model-aware filename helper (_model_kind_for_extras)
    returns the right prefix per --model selection
  * the regime-column drop-before-merge fix in NormalizePredictionSchemaTask

These are scope-disjoint from the smoke script's runtime exit-code
contract (which is exercised end-to-end on the small synthetic fixture
in CI). They guarantee the file-level + harness-level pieces are wired
correctly so a script regression can't slip past pytest.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pandas as pd
import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_phase_a0_smoke_linear.sh"
PATCHTST_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_phase_a0_smoke.sh"


# ---- Script file structure ---------------------------------------------


def test_smoke_script_exists() -> None:
    assert SCRIPT_PATH.exists(), f"missing: {SCRIPT_PATH}"


def test_smoke_script_is_executable() -> None:
    """Operator-facing scripts must be `chmod +x` checked-in (else cron
    invocations fail with Permission denied)."""
    mode = SCRIPT_PATH.stat().st_mode
    assert mode & stat.S_IXUSR, f"{SCRIPT_PATH} is not executable"


def test_smoke_script_uses_safe_set_flags() -> None:
    """No `set -e` — we explicitly handle exit codes 0/2. `set -u` and
    `set -o pipefail` ARE on (per PR #13 LOW-finding fix)."""
    body = SCRIPT_PATH.read_text()
    assert "set -uo pipefail" in body
    # `set -e` (alone or as part of `set -eo`) would prevent us from
    # capturing exit code 2 (gate failure) from the research command.
    assert "set -e\n" not in body or "set +e" in body  # local `set -e` after explicit guard ok


def test_smoke_script_uses_absolute_paths_for_fixtures() -> None:
    """PR #13 BLOCKER fix carried forward: trainer's REPO-relative path
    resolution requires absolute paths for fixtures (else they resolve
    against src/ and FileNotFoundError)."""
    body = SCRIPT_PATH.read_text()
    for var in ("SMOKE_STRATEGY_CONFIG", "SMOKE_DATASET", "SMOKE_SPY_PATH"):
        # Each fixture path must be derived from REPO_ROOT (absolute), not
        # plain relative "tests/data/..."
        assert f'{var}="$REPO_ROOT/tests/data/' in body, (
            f"{var} must be derived from $REPO_ROOT (absolute path) to "
            f"survive REPO-relative trainer path resolution")


def test_smoke_script_python_resolution_has_no_fallback_bug() -> None:
    """PR #13 LOW-finding fix carried forward: the previous
    `PYTHON=${PYTHON:-python3}` after `PYTHON` was already set didn't
    fall back. The explicit if/elif/else chain does."""
    body = SCRIPT_PATH.read_text()
    assert "if [ -n \"${PYTHON:-}\" ] && [ -x \"$PYTHON\" ]" in body, (
        "Python resolution must use explicit if/elif/else chain")


def test_smoke_script_kind_aligned_with_patchtst_smoke() -> None:
    """The linear smoke should mirror the PatchTST smoke's gate-printing
    surface so operators see the same shape regardless of which trainer
    ran. The gate-failure exit policy differs (linear smoke gates only
    on machinery, not model quality on tiny fixture), but the SECTIONS
    printed must be: completeness, placebo {shuffle,timeshift}, verdict."""
    body = SCRIPT_PATH.read_text()
    # These string templates appear in the embedded Python heredoc that
    # generates the runtime summary (the f-strings substitute `kind` /
    # values at print time).
    for section in ("completeness:",
                    'placebo {kind}: passed={passed} ',
                    'verdict:'):
        assert section in body, f"missing section in summary block: {section!r}"
    # Verify both placebo kinds are iterated over.
    for kind in ("shuffle_placebo", "timeshift_placebo"):
        assert kind in body, f"missing placebo kind: {kind!r}"


def test_smoke_script_default_config_is_kernel_3() -> None:
    """L_dlinear (kernel=25) over-smooths a seq_len=24 fixture; smoke
    defaults to L_dlinear_k3 so a fresh operator run learns something
    on the tiny synthetic. Real research stays with L_dlinear."""
    body = SCRIPT_PATH.read_text()
    assert "L_dlinear_k3" in body


# ---- Harness model-aware filename helper -------------------------------


def test_model_kind_for_extras_defaults_to_hf_patchtst() -> None:
    """Existing PatchTST configs (no --model flag, or --model patchtst)
    keep writing hf_patchtst_* — backward compat invariant."""
    from renquant_model_patchtst.research_pipeline import _model_kind_for_extras
    assert _model_kind_for_extras([]) == "hf_patchtst"
    assert _model_kind_for_extras(["--lr", "1e-3"]) == "hf_patchtst"
    assert _model_kind_for_extras(["--model", "patchtst"]) == "hf_patchtst"


def test_model_kind_for_extras_dispatches_to_linear_models() -> None:
    """The linear trainer writes {args.model}_* (e.g. dlinear_*); the
    harness must follow suit or trials are marked failed by
    ValidateResultCompletenessTask."""
    from renquant_model_patchtst.research_pipeline import _model_kind_for_extras
    assert _model_kind_for_extras(["--model", "dlinear", "--lr", "1e-3"]) == "dlinear"
    assert _model_kind_for_extras(["--lr", "1e-3", "--model", "nlinear"]) == "nlinear"


def test_model_kind_for_extras_unknown_fails_fast_at_planning() -> None:
    """Unknown --model values fail-fast at trial-matrix planning (PR #18
    reviewer follow-up): a typo would otherwise burn a trial's compute
    and only surface later as ValidateResultCompletenessTask missing
    val_preds, which is wasteful + harder to debug."""
    from renquant_model_patchtst.research_pipeline import _model_kind_for_extras
    with pytest.raises(ValueError, match="unsupported --model"):
        _model_kind_for_extras(["--model", "lstm_typo"])


# ---- Harness regime-column drop-before-merge fix ----------------------


def test_normalize_prediction_schema_drops_trainer_regime_before_merge(
    tmp_path: Path,
) -> None:
    """The linear trainer's val_preds emits a `regime` column (used for
    in-trainer per-regime IC logging). Without dropping it, pandas
    `merge` auto-renames to regime_x/regime_y and downstream
    `df.dropna(subset=["regime"])` raises KeyError."""
    from renquant_model_patchtst.research_pipeline import (
        ExperimentContext, ExperimentSpec, NormalizePredictionSchemaTask,
        TrialContext, TrialSpec)

    # Build a val_preds parquet that mimics what linear trainer writes —
    # WITH a `regime` column (all None, matching no-SPY case).
    val_preds = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02"] * 3),
        "ticker": ["A", "B", "C"] * 2,
        "pred": [0.1, -0.2, 0.3, -0.1, 0.2, -0.3],
        "label": [0.5, -0.4, 0.6, -0.2, 0.4, -0.5],
        "regime": [None] * 6,  # trainer emits this
    })
    vp_path = tmp_path / "dlinear_all_seed42_val_preds.parquet"
    val_preds.to_parquet(vp_path, index=False)

    # Build a regime_labels frame as if HMM computed BULL_CALM for both days
    regime_labels = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "regime": ["BULL_CALM", "BULL_CALM"],
    })

    spec = ExperimentSpec(
        phase="range_find", configs=["L"], cuts=["all"], seeds=[42], epochs=1,
        dataset=Path(""), spy_path=Path(""), data_dir=Path(""),
        strategy_config=None, out_dir=tmp_path, device="cpu", scheduler="linear",
    )
    exp_ctx = ExperimentContext(spec=spec, experiment_dir=tmp_path)
    trial_spec = TrialSpec(
        trial_id="L_all_s42_real", config_name="L", cut="all", seed=42,
        trial_kind="real", argv=[], out_dir=tmp_path, val_preds_path=vp_path,
        summary_path=tmp_path / "summary.json",
    )
    trial_ctx = TrialContext(
        experiment=exp_ctx, spec=trial_spec,
        trainer_runner=lambda a: None, parser_builder=lambda: None,
        regime_labels=regime_labels,
    )

    # Must not raise KeyError
    assert NormalizePredictionSchemaTask().run(trial_ctx) is True

    # The merged regime should be the HMM-computed value, NOT the
    # trainer's None — proving the drop-then-merge order is right.
    normalized = pd.read_parquet(trial_ctx.normalized_preds_path)
    assert "regime" in normalized.columns
    assert "regime_x" not in normalized.columns
    assert "regime_y" not in normalized.columns
    assert (normalized["regime"] == "BULL_CALM").all()
