#!/usr/bin/env bash
# Phase A.0 smoke runner — first kill-gate experiment from the merged
# research plan (docs/patchtst_capability_research_proposal.md §"Phase
# A.0: Gate Smoke").
#
# Runs the actual research_pipeline ExperimentPipeline on the small
# synthetic fixture committed at tests/data/smoke_panel.parquet. This is
# the smallest end-to-end exercise of:
#   * detector_version plumbing (PR #12)
#   * placebo cross-split-leak fix (PR #9)
#   * regime-contract gate (RegimeDetectorContractTask)
#   * the full Task/Job/Pipeline machinery
#
# Wall-clock target: < 5 minutes on CPU. If it takes longer, something
# regressed in the data path or the trainer.
#
# Kill criteria (per merged plan):
#   - regime contract fails           → STOP, debug detector
#   - shuffle placebo IC > threshold  → STOP, debug shuffle path
#   - timeshift placebo IC > threshold → STOP, debug shift path
#   - any subprocess SystemExit → STOP, fix trainer surface
#
# Usage (run from renquant-model repo root):
#
#     ./scripts/run_phase_a0_smoke.sh
#
# Or directly:
#
#     PYTHONPATH=src python -m renquant_model_patchtst.research \
#         --phase range_find --configs B_tuned --cuts all \
#         --seeds 42 --epochs 2 --device cpu \
#         --dataset tests/data/smoke_panel.parquet \
#         --spy-path tests/data/smoke_spy.parquet \
#         --out-dir artifacts/phase_a0_smoke \
#         --no-regime-contract \
#         --label fwd_5d_excess \
#         --label-lookahead-days 5 \
#         --embargo-days 5 \
#         --val-tail-pct 0.15 \
#         --label-shift-days 5

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Allow override of the Python interpreter (CI / venv flexibility).
PYTHON="${PYTHON:-../RenQuant/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
    PYTHON="${PYTHON:-python3}"
fi

# Ensure sibling subrepos are on PYTHONPATH so renquant_common etc. resolve.
export PYTHONPATH="src:../renquant-common/src:../renquant-pipeline/src:../renquant-artifacts/src:../renquant-base-data/src:${PYTHONPATH:-}"

OUT_DIR="${OUT_DIR:-artifacts/phase_a0_smoke}"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

echo "[$(date)] Phase A.0 smoke starting → $OUT_DIR"

# The 'all' cut is the fixture's natural unit (no walk-forward cuts apply to
# the synthetic 200-day fixture). val_tail_pct=0.15 + embargo_days=5 +
# label_lookahead_days=5 leaves enough train rows for a competent ranker.
# --no-regime-contract because the synthetic SPY won't pass the canonical
# golden-window check; this smoke is about placebo gate + machinery, not
# about real-world regime detection.
"$PYTHON" -m renquant_model_patchtst.research \
    --phase range_find \
    --configs B_tuned \
    --cuts all \
    --seeds 42 \
    --epochs 2 \
    --device cpu \
    --dataset tests/data/smoke_panel.parquet \
    --spy-path tests/data/smoke_spy.parquet \
    --out-dir "$OUT_DIR" \
    --no-regime-contract \
    --label fwd_5d_excess \
    --label-lookahead-days 5 \
    --embargo-days 5 \
    --val-tail-pct 0.15 \
    --label-shift-days 5 \
    --detector-version v2026-05-31

RC=$?
echo "[$(date)] research run exit code: $RC"

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
echo "=== verdict ==="
if [ -f "$EXP_DIR/analysis.json" ]; then
    "$PYTHON" -c "
import json
d = json.load(open('$EXP_DIR/analysis.json'))
print(f\"verdict: {d.get('verdict')}\")
vi = d.get('verdict_inputs', {})
for k in ('delta_vs_baseline', 'se_pooled_ic', 'worst_cut_ic',
          'min_non_defensive_regime_ic', 'has_non_defensive_evidence',
          'dsr', 'pbo'):
    if k in vi:
        print(f\"  {k}: {vi[k]}\")
"
elif [ -f "$EXP_DIR/invalid_experiment.json" ]; then
    "$PYTHON" -c "
import json
d = json.load(open('$EXP_DIR/invalid_experiment.json'))
print(f\"verdict: invalid_experiment\")
pg = d.get('placebo_gate', {})
for kind in ('shuffle_placebo', 'timeshift_placebo'):
    g = pg.get(kind, {})
    print(f\"  {kind}: passed={g.get('passed')}, real_ic={g.get('real_ic_mean')}, placebo_ic={g.get('placebo_ic_mean')}, threshold={g.get('threshold')}\")
"
else
    echo "ERROR: no analysis.json or invalid_experiment.json in $EXP_DIR" >&2
    ls "$EXP_DIR/" >&2
    exit 1
fi
echo ""
echo "Phase A.0 smoke complete."
