#!/usr/bin/env bash
# Phase A.0 placebo + data-machinery smoke runner.
#
# Runs the actual research_pipeline ExperimentPipeline on the small
# synthetic fixture committed at tests/data/smoke_panel.parquet. This is
# the smallest end-to-end exercise of:
#
#   * placebo cross-split-leak fix (PR #9)
#   * detector_version plumbing (PR #12)
#   * trainer-surface validation + trial argv assembly
#   * the full Task/Job/Pipeline machinery
#
# What this smoke does NOT exercise (intentional scope):
#
#   * RegimeDetectorContractTask — this script passes --no-regime-contract
#     because the synthetic SPY won't pass the canonical golden-window
#     check against real-history calm_2017 / covid_crash / q2_2022_bear
#     windows. Validating the detector itself is the job of the real-data
#     Phase A.0 run against the umbrella's full SPY parquet.
#   * PerRegimeICCallback — the trainer doesn't receive --spy-path here
#     (the B_tuned config doesn't forward it; only D_film does), so
#     per-regime IC will be empty. That's expected; per-regime
#     attribution is a real-data concern.
#   * Best-model selection via eval_min_regime_ic — falls back to
#     eval_loss when SPY isn't wired into the trainer. The smoke is
#     validating data-machinery + placebos, not best-model selection.
#
# Wall-clock target: < 5 minutes on CPU. If it takes longer, something
# regressed in the data path or the trainer.
#
# Kill criteria (per merged plan):
#   - shuffle placebo IC > threshold  → STOP, debug shuffle path
#   - timeshift placebo IC > threshold → STOP, debug shift path
#   - any subprocess SystemExit → STOP, fix trainer surface
#   - any artifact assembly failure → STOP, debug contract
#
# Usage (run from renquant-model repo root):
#
#     ./scripts/run_phase_a0_smoke.sh

# Note: NO `set -e` — we explicitly handle the research command's exit
# code (which is 2 on `invalid_experiment`, a meaningful verdict we want
# to print). `set -u` and `set -o pipefail` are still on for unset-var
# safety.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || { echo "ERROR: cannot cd to $REPO_ROOT" >&2; exit 1; }

# Python interpreter resolution. Honors $PYTHON if set + executable;
# else tries the umbrella's sibling venv; else falls back to system
# python3. The previous version had a fallback bug (re-using
# ${PYTHON:-python3} after PYTHON was already set) — this version
# checks explicitly.
if [ -n "${PYTHON:-}" ] && [ -x "$PYTHON" ]; then
    :   # respect explicit operator override
elif [ -x "../RenQuant/.venv/bin/python" ]; then
    PYTHON="../RenQuant/.venv/bin/python"
else
    PYTHON="$(command -v python3 || true)"
fi
if [ -z "${PYTHON:-}" ] || [ ! -x "$PYTHON" ]; then
    echo "ERROR: no usable python interpreter found (set \$PYTHON, install" >&2
    echo "       ../RenQuant/.venv, or have python3 on PATH)." >&2
    exit 1
fi
echo "using interpreter: $PYTHON"

# Ensure sibling subrepos are on PYTHONPATH so renquant_common etc. resolve.
export PYTHONPATH="src:../renquant-common/src:../renquant-pipeline/src:../renquant-artifacts/src:../renquant-base-data/src:${PYTHONPATH:-}"

OUT_DIR="${OUT_DIR:-artifacts/phase_a0_smoke}"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# Committed smoke strategy config — minimal stub so build_config_contract()
# in BuildSummaryTask doesn't fall back to the umbrella's strategy file
# (which doesn't exist in this repo).
#
# MUST be an absolute path. build_config_contract() resolves relative
# strategy_config paths against hf.REPO (= renquant-model/src in package
# mode), which would look for src/tests/data/smoke_strategy_config.json
# and fail. Absolute path bypasses that resolution.
SMOKE_STRATEGY_CONFIG="$REPO_ROOT/tests/data/smoke_strategy_config.json"
if [ ! -f "$SMOKE_STRATEGY_CONFIG" ]; then
    echo "ERROR: smoke strategy config missing at $SMOKE_STRATEGY_CONFIG" >&2
    exit 1
fi
# Same for dataset + spy-path: hf_trainer's REPO-relative resolution
# would otherwise look under src/. Use absolute paths.
SMOKE_DATASET="$REPO_ROOT/tests/data/smoke_panel.parquet"
SMOKE_SPY_PATH="$REPO_ROOT/tests/data/smoke_spy.parquet"
for path in "$SMOKE_DATASET" "$SMOKE_SPY_PATH"; do
    if [ ! -f "$path" ]; then
        echo "ERROR: smoke fixture missing at $path" >&2
        exit 1
    fi
done

echo "[$(date)] Phase A.0 smoke starting → $OUT_DIR"

# Run the research command WITHOUT `set -e` so we can handle exit code 2
# (invalid_experiment is a meaningful verdict, not a script failure).
set +e
"$PYTHON" -m renquant_model_patchtst.research \
    --phase range_find \
    --configs B_tuned \
    --cuts all \
    --seeds 42 \
    --epochs 2 \
    --device cpu \
    --dataset "$SMOKE_DATASET" \
    --spy-path "$SMOKE_SPY_PATH" \
    --strategy-config "$SMOKE_STRATEGY_CONFIG" \
    --out-dir "$OUT_DIR" \
    --no-regime-contract \
    --label fwd_5d_excess \
    --label-lookahead-days 5 \
    --embargo-days 5 \
    --val-tail-pct 0.15 \
    --label-shift-days 5 \
    --detector-version v2026-05-31
RC=$?
set -e

echo "[$(date)] research run exit code: $RC"

# Exit code policy:
#   0 → verdict produced (any verdict except invalid_experiment)
#   2 → verdict was invalid_experiment (NOT a script failure)
#   other → real failure
if [ "$RC" -ne 0 ] && [ "$RC" -ne 2 ]; then
    echo "ERROR: research command returned unexpected exit code $RC" >&2
    exit "$RC"
fi

# Surface the verdict + placebo numbers so operator sees them without
# digging through artifacts/.
EXP_DIR="$(ls -td "$OUT_DIR"/* 2>/dev/null | head -n 1)"
if [ -z "$EXP_DIR" ]; then
    echo "ERROR: no experiment directory created under $OUT_DIR" >&2
    exit 1
fi

echo ""
echo "=== experiment_dir ==="
echo "$EXP_DIR"
echo ""
echo "=== experiment summary ==="
# Print the summary AND determine the gate-pass exit code in one shot.
# A run that ended with all 3 trials failed (FileNotFoundError, etc.) is
# NOT a green smoke even though the harness recorded an `invalid_experiment`
# verdict — operator should see RC≠0 and know to investigate.
"$PYTHON" - "$EXP_DIR" <<'PY'
import json
import sys
from pathlib import Path

exp_dir = Path(sys.argv[1])
gates_failed: list[str] = []

# Aggregate completeness — same surface ValidateResultCompletenessTask writes.
agg_path = exp_dir / "aggregate_results.json"
n_failed = 0
n_missing = 0
n_planned = 0
if agg_path.exists():
    agg = json.loads(agg_path.read_text())
    comp = agg.get("completeness", {})
    n_failed = int(comp.get("n_failed", 0))
    n_missing = int(comp.get("n_missing", 0))
    n_planned = int(comp.get("planned", 0))
    print(f"completeness: {n_planned - n_failed - n_missing}/{n_planned} ok "
          f"(failed={n_failed}, missing={n_missing})")
    if n_failed > 0:
        gates_failed.append(f"{n_failed} trials failed")
        ids = comp.get("failed_trial_ids", [])
        if ids:
            print(f"  failed_trial_ids: {ids}")
    if n_missing > 0:
        gates_failed.append(f"{n_missing} trials missing")

# Placebo gates — same surface PlaceboGateJob writes.
placebo_path = exp_dir / "placebo_gate.json"
if placebo_path.exists():
    pg = json.loads(placebo_path.read_text())
    for kind in ("shuffle_placebo", "timeshift_placebo"):
        g = pg.get(kind, {})
        passed = g.get("passed")
        print(f"placebo {kind}: passed={passed} "
              f"real_ic={g.get('real_ic_mean')} placebo_ic={g.get('placebo_ic_mean')} "
              f"threshold={g.get('threshold')} "
              f"(n_real={g.get('n_real')}/n_placebo={g.get('n_placebo')})")
        if g.get("hard_gate", True) and not passed:
            gates_failed.append(f"{kind} did not pass")

# Verdict
if (exp_dir / "analysis.json").exists():
    a = json.loads((exp_dir / "analysis.json").read_text())
    print(f"verdict: {a.get('verdict')}")
    vi = a.get("verdict_inputs", {})
    for k in ("delta_vs_baseline", "se_pooled_ic", "worst_cut_ic",
              "min_non_defensive_regime_ic", "has_non_defensive_evidence",
              "dsr", "pbo"):
        if k in vi:
            print(f"  {k}: {vi[k]}")
elif (exp_dir / "invalid_experiment.json").exists():
    d = json.loads((exp_dir / "invalid_experiment.json").read_text())
    print(f"verdict: invalid_experiment")
    gates_failed.append("verdict = invalid_experiment")
else:
    print("ERROR: no analysis.json or invalid_experiment.json — broken artifact assembly", file=sys.stderr)
    sys.exit(3)

if gates_failed:
    print("", file=sys.stderr)
    print("SMOKE FAILED — gates that did not pass:", file=sys.stderr)
    for g in gates_failed:
        print(f"  - {g}", file=sys.stderr)
    sys.exit(2)

print("")
print("All smoke gates passed.")
PY
SUMMARY_RC=$?

if [ "$SUMMARY_RC" -ne 0 ]; then
    # Non-zero summary exit means a gate didn't pass; operator must
    # investigate before treating this as a green smoke.
    echo "Phase A.0 smoke INCOMPLETE — see gate failures above." >&2
    exit "$SUMMARY_RC"
fi
echo ""
echo "Phase A.0 smoke complete."
