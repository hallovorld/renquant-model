"""xgb_mom_60d prereg v2 verifier — the enforced machine surface (model#213).

Checks a committed v2 artifact (control or result JSON) against the
committed harness SOURCE (`2026-08-09-xgbmom-v2-harness.py`, read via ast —
the frozen text is the authority, nothing is re-derived) and exits 1 when:

  1. `admissible_verdict` is non-null without the design doc's literal
     countersignature line
     `COUNTERSIGN: <artifact-name> admissible_verdict=<verdict>`
     (the model#210/#212 machine-surface rule — the countersignature lives
     in the DOC, so an artifact can never countersign itself);
  2. `features_sha256` is absent or differs from the harness's frozen
     70-feature list;
  3. `fold_table` differs from the harness's frozen CUTS;
  4. any fold's `max_surviving_label_endpoint` is not strictly before its
     fold's test start (the P0 per-row purge invariant), or the purge log
     does not cover the fold table;
  5. the gate arithmetic (all four legs recomputed; >=6-of-the-fixed-8
     with an unrealized fold counted NON-positive) does not recompute from
     the artifact's own numbers;
  6. a real artifact's `corpus_sha256` differs from the prereg pin (also
     asserted to appear literally in the harness source, so the two files
     cannot drift apart silently).

Usage: python 2026-08-09-xgbmom-v2-verify.py <artifact.json> [...]
"""
import ast, hashlib, json, sys
from pathlib import Path

FROZEN = Path(__file__).resolve().parent
HARNESS = FROZEN / "2026-08-09-xgbmom-v2-harness.py"
DESIGN_DOC = FROZEN.parent / "2026-08-09-xgb-mom-60d-prereg-v2.md"
CORPUS_SHA256 = "870f68ebad5d2d87e2601f62310f34615d2d8d25df9d9cbf563629b13129bf7e"


def harness_constants():
    """FEATS / CUTS / CORPUS_SHA256 as literally committed in the harness."""
    tree = ast.parse(HARNESS.read_text())
    out = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in ("FEATS", "CUTS", "CORPUS_SHA256")):
            out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


def check(path):
    errs = []
    a = json.loads(Path(path).read_text())
    h = harness_constants()

    # 6. corpus pin — verifier vs harness, then artifact vs pin (real only)
    if h.get("CORPUS_SHA256") != CORPUS_SHA256:
        errs.append("harness corpus pin drifted from verifier pin")
    if a.get("corpus_sha256") is not None and a["corpus_sha256"] != CORPUS_SHA256:
        errs.append("corpus_sha256 differs from the prereg pin")

    # 2. frozen feature-list hash
    want_feats = hashlib.sha256(json.dumps(h["FEATS"]).encode()).hexdigest()
    if a.get("features_sha256") != want_feats:
        errs.append("features_sha256 absent or differs from the frozen list")

    # 3. literal fold table
    if [list(c) for c in a.get("fold_table", [])] != [list(c) for c in h["CUTS"]]:
        errs.append("fold_table differs from the frozen CUTS")

    # 4. per-fold purge invariant, covering every fold
    purge = a.get("purge_per_fold", [])
    if [e.get("test_start") for e in purge] != [c[2] for c in h["CUTS"]]:
        errs.append("purge_per_fold does not cover the fold table")
    for e in purge:
        ep = e.get("max_surviving_label_endpoint")
        if ep is not None and not ep < e["test_start"]:
            errs.append(f"purge violated: endpoint {ep} not before {e['test_start']}")
        if not 0 <= e.get("n_purged", -1) <= e.get("n_train_pre_purge", -1):
            errs.append(f"purge counts inconsistent at {e.get('test_start')}")

    # 5. gate arithmetic recomputed from the artifact's own numbers
    rs = [float("nan") if v is None else float(v)
          for v in a.get("real_signal_per_fold", [])]
    if len(rs) != len(h["CUTS"]):
        errs.append("real_signal_per_fold does not cover the fixed 8 folds")
    else:
        finite = [v for v in rs if v == v]
        mean = sum(finite) / len(finite) if finite else float("nan")
        n_pos = sum(1 for v in rs if v > 0)          # NaN counts non-positive
        legs = [mean > 0,
                n_pos >= 6,
                a.get("aa_seed_std", float("inf")) <= 0.01,
                sum(1 for v in rs[5:] if v > 0) >= 2
                or not (rs[7] > 0 and rs[5] <= 0 and rs[6] <= 0)]
        if abs(mean - a.get("mean_real_signal", float("inf"))) > 2e-4:
            errs.append("mean_real_signal does not recompute")
        if n_pos != a.get("n_folds_pos"):
            errs.append("n_folds_pos does not recompute")
        if legs != a.get("legs"):
            errs.append(f"legs recompute to {legs}, artifact says {a.get('legs')}")
        want = "PASS" if all(legs) else "KILL"
        if want != a.get("gate_arithmetic"):
            errs.append(f"gate_arithmetic recomputes to {want}")

    # 1. the machine-surface rule: non-null verdict needs the doc's countersign
    verdict = a.get("admissible_verdict")
    if verdict is not None:
        marker = f"COUNTERSIGN: {Path(path).name} admissible_verdict={verdict}"
        if marker not in DESIGN_DOC.read_text():
            errs.append(f"non-null admissible_verdict without countersignature "
                        f"(design doc lacks the literal line '{marker}')")
    return errs


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        sys.exit(2)
    bad = False
    for p in sys.argv[1:]:
        errs = check(p)
        if errs:
            bad = True
            print(f"FAIL {p}:\n  " + "\n  ".join(errs))
        else:
            print(f"VERIFIED {p}")
    sys.exit(1 if bad else 0)
