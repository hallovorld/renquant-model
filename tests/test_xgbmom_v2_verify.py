"""The v2 prereg's machine surface is ENFORCED, not promised (model#213 review r5).

The committed verifier must (a) verify both committed control artifacts
clean, and fail closed on: (b) a non-null admissible_verdict lacking the
design doc's countersignature, (c) feature-hash drift or absence — the r5
finding itself, (d) a fold-table edit, (e) a purge endpoint touching its
test interval, (f) gate arithmetic that no longer recomputes.
"""
import json
import subprocess
import sys
from pathlib import Path

FROZEN = Path(__file__).resolve().parents[1] / "doc" / "design" / "frozen"
VERIFIER = FROZEN / "2026-08-09-xgbmom-v2-verify.py"
CONTROLS = [
    FROZEN / "2026-08-09-xgbmom-v2-control-positive.json",
    FROZEN / "2026-08-09-xgbmom-v2-control-null.json",
]


def run_verifier(*paths):
    return subprocess.run(
        [sys.executable, str(VERIFIER), *map(str, paths)],
        capture_output=True, text=True,
    )


def mutated(tmp_path, fn):
    """Copy the positive control (same filename, so the countersign lookup
    behaves identically), apply fn to the dict, return the new path."""
    artifact = json.loads(CONTROLS[0].read_text())
    fn(artifact)
    p = tmp_path / CONTROLS[0].name
    p.write_text(json.dumps(artifact))
    return p


def test_committed_controls_verify_clean():
    r = run_verifier(*CONTROLS)
    assert r.returncode == 0, r.stdout + r.stderr


def test_non_null_verdict_without_countersign_fails_closed(tmp_path):
    p = mutated(tmp_path, lambda a: a.update(admissible_verdict="PASS"))
    r = run_verifier(p)
    assert r.returncode == 1
    assert "countersign" in r.stdout.lower()


def test_missing_features_sha256_fails(tmp_path):
    p = mutated(tmp_path, lambda a: a.pop("features_sha256"))
    assert run_verifier(p).returncode == 1


def test_feature_hash_drift_fails(tmp_path):
    p = mutated(tmp_path, lambda a: a.update(features_sha256="0" * 64))
    assert run_verifier(p).returncode == 1


def test_fold_table_edit_fails(tmp_path):
    def fn(a):
        a["fold_table"][0][2] = "2019-02-01"  # v1's leaky test start
    assert run_verifier(mutated(tmp_path, fn)).returncode == 1


def test_purge_endpoint_inside_test_interval_fails(tmp_path):
    def fn(a):
        a["purge_per_fold"][0]["max_surviving_label_endpoint"] = \
            a["purge_per_fold"][0]["test_start"]
    assert run_verifier(mutated(tmp_path, fn)).returncode == 1


def test_gate_arithmetic_drift_fails(tmp_path):
    p = mutated(tmp_path, lambda a: a.update(n_folds_pos=99))
    assert run_verifier(p).returncode == 1
