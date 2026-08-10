"""MoE slow-state machine-surface verifier (orch#966; condact §5.7 pattern).
Checks a committed slow-state artifact and exits 1 when: stage/kind fields are
absent or invalid; features_sha256 differs from the frozen v2 FEATS list (the
single source both this line and condact import); bootstrap parameters differ
from the frozen (block 21, 2000 resamples, seed 99); the slow axis is not the
frozen ROC60 with a 12-month median; a non-null admissible_verdict lacks the
design doc's countersign line; or a control carries a corpus sha."""
import ast, hashlib, json, sys
from pathlib import Path

FROZEN = Path(__file__).resolve().parent
HARNESS = FROZEN / "2026-08-09-xgbmom-v2-harness.py"  # FEATS single source (v2 harness, imported via condact)
DESIGN = FROZEN.parent / "2026-08-10-moe-slow-state-gating-prereg.md"


def harness_feats():
    tree = ast.parse(HARNESS.read_text())
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "FEATS":
            return ast.literal_eval(n.value)
    raise SystemExit("harness FEATS not found")


def check(path):
    a = json.loads(Path(path).read_text()); errs = []
    if a.get("artifact_kind") not in ("control", "result"):
        errs.append("artifact_kind missing/invalid")
    if a.get("stage") != "E-exploratory":
        errs.append("stage must be E-exploratory in this harness version "
                    "(C is a reviewed amendment)")
    if a.get("slow_axis") != "ROC60" or a.get("med_months") != 12:
        errs.append("slow axis drifted from the frozen ROC60 / 12-month median")
    want = hashlib.sha256(json.dumps(harness_feats()).encode()).hexdigest()
    if a.get("features_sha256") != want:
        errs.append("features_sha256 absent or differs from the frozen v2 list")
    b = a.get("bootstrap", {})
    if (b.get("mean_block"), b.get("n_resamples"), b.get("seed")) != (21, 2000, 99):
        errs.append(f"bootstrap params drifted: {b}")
    if a.get("admissible_verdict") is not None:
        marker = f"COUNTERSIGN: {Path(path).name} admissible_verdict={a['admissible_verdict']}"
        if marker not in DESIGN.read_text():
            errs.append("non-null admissible_verdict without doc countersignature")
    if a.get("artifact_kind") == "control" and a.get("corpus_sha256") is not None:
        errs.append("control must be corpus-inapplicable")
    return errs


if __name__ == "__main__":
    bad = False
    for p in sys.argv[1:]:
        e = check(p)
        print(f"FAIL {p}:\n  " + "\n  ".join(e) if e else f"VERIFIED {p}")
        bad = bad or bool(e)
    sys.exit(1 if bad else 0)
