#!/usr/bin/env python3
"""Amendment 4 pre-run validation: the replacement SS4.4 gates are (a) satisfiable on
a correct machine and (b) FAIL on deliberately corrupted machines.

SELF-CONTAINED (review round 1 on model#172): everything this script needs lives in
its own directory or is regenerated from a committed seed --
  * the inference implementation is the vendored ``goal7_momentum_inference_ref.py``
    beside this file (byte-identical to the reviewed #169 module; its sha256 is
    recorded in the output as ``inference_ref_sha256``);
  * the positive-control fixture is REGENERATED from its committed recipe
    (iid N(0,1), n=756, ``np.random.default_rng(20260801 + 7)``, Python-float repr
    lines) and asserted against the pinned sha before use -- no cross-branch file
    dependency.
No real market data is touched anywhere here.

Reproduce:  python validate_gate_replacement.py            (rewrites the JSON)
Verify:     python validate_gate_replacement.py --check    (re-runs, then requires
            byte-identical agreement with the committed validation_output.json)

Because every quantity is seeded and deterministic, the correct-machine rows ARE the
values the runner's control gate will reproduce at execution -- predetermining a
MACHINERY gate is the point: the machine is proven calibrated before the study runs.
"""
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INF_PATH = HERE / "goal7_momentum_inference_ref.py"

spec = importlib.util.spec_from_file_location("inf_ref", INF_PATH)
INF = importlib.util.module_from_spec(spec)
spec.loader.exec_module(INF)

import numpy as np  # noqa: E402

# --- regenerate the committed fixture from its recipe and pin-check it -----------
rng_fix = np.random.default_rng(20260801 + 7)
noise = rng_fix.standard_normal(756)
buf = io.StringIO()
buf.write("x\n")
for v in noise:
    buf.write(f"{float(v)!r}\n")
fixture_sha = hashlib.sha256(buf.getvalue().encode()).hexdigest()
assert fixture_sha == INF.FROZEN_INFERENCE["positive_control_sha256"], (
    "regenerated fixture does not match the pinned sha -- recipe or pin drifted")

cfg = dict(INF.FROZEN_INFERENCE)
cfg["envelope_rule"] = "bootstrap_max"
out = {
    "inference_ref_sha256": hashlib.sha256(INF_PATH.read_bytes()).hexdigest(),
    "fixture_sha256": fixture_sha,
    "fixture_recipe": "iid N(0,1), n=756, np.random.default_rng(20260801 + 7), "
                      "header 'x' + Python-float repr lines",
    "n": len(noise), "band": list(cfg["gate_band"]),
}

# --- positive arm: full-rep own-bar rates on a CORRECT machine -------------------
cal = INF.calibrate_bar(noise, cfg)
assert cal["status"] == "calibrated", cal
mach = INF.machinery_self_check(noise, cal, cfg)          # reps = 5000, seeds +1/+2
n = len(noise)
iid = INF._rejection_rate(lambda r: r.standard_normal(n), cal["t_star"], cfg["L"],
                          np.random.default_rng(cfg["seed"] + 3), cfg["reps"],
                          cfg["gate_band"])
out["correct_machine"] = {
    "bars": cal["bars"], "t_star": cal["t_star"], "ar_p": cal["ar_fit"]["p"],
    "overlap_ma": mach["overlap_ma"], "ar_resample": mach["ar_resample"],
    "gate_ok": mach["ok"],
    "iid_vs_t_star_diagnostic": iid,
}

# --- negative arms: corrupted machines must FAIL the replacement gate ------------
NEG_REPS = 2000  # SE ~ sqrt(.025*.975/2000) ~ 0.0035; failures below are >> 3 SE
var = float(noise.var())
fit = INF.fit_ar(noise, cfg["ar_p_max"])

def rate(gen, bar, seed_off):
    return INF._rejection_rate(gen, bar, cfg["L"],
                               np.random.default_rng(cfg["seed"] + seed_off),
                               NEG_REPS, cfg["gate_band"])

# corruption A: bar calibrated at the WRONG quantile (0.90) -- bars too low
cfg_q = {**cfg, "quantile": 0.90}
cal_q = INF.calibrate_bar(noise, cfg_q)
neg_a = {
    "overlap_ma": rate(lambda r: INF.gen_overlap_ma(r, n, cfg["h"], var),
                       cal_q["bars"]["overlap_ma"], 1),
    "ar_resample": rate(lambda r: INF.gen_ar_resample(r, n, fit["phi"], fit["resid"]),
                        cal_q["bars"]["ar_resample"], 2),
}
neg_a["gate_ok"] = neg_a["overlap_ma"]["ok"] and neg_a["ar_resample"]["ok"]

# corruption B: cross-member bar confusion (AR draws tested at the MA bar)
neg_b = {"ar_draws_at_ma_bar": rate(
    lambda r: INF.gen_ar_resample(r, n, fit["phi"], fit["resid"]),
    cal["bars"]["overlap_ma"], 2)}
neg_b["gate_ok"] = neg_b["ar_draws_at_ma_bar"]["ok"]

# corruption C: mirror drift -- bar calibrated with T at L=59, test statistic
# computed at L=10 (under-corrects the MA(19) dependence, inflating |T|)
def rate_L(gen, bar, seed_off, L):
    return INF._rejection_rate(gen, bar, L,
                               np.random.default_rng(cfg["seed"] + seed_off),
                               NEG_REPS, cfg["gate_band"])
neg_c = {"ma_draws_tested_at_L10": rate_L(
    lambda r: INF.gen_overlap_ma(r, n, cfg["h"], var),
    cal["bars"]["overlap_ma"], 1, 10)}
neg_c["gate_ok"] = neg_c["ma_draws_tested_at_L10"]["ok"]

out["corrupted_machines"] = {
    "A_wrong_quantile_0.90": neg_a,
    "B_cross_member_bar_confusion": neg_b,
    "C_mirror_drift_L10_test_vs_L59_bar": neg_c,
    "neg_reps": NEG_REPS,
}
out["verdict"] = {
    "replacement_gate_passes_on_correct_machine": bool(mach["ok"]),
    "replacement_gate_fails_on_A": not neg_a["gate_ok"],
    "replacement_gate_fails_on_B": not neg_b["gate_ok"],
    "replacement_gate_fails_on_C": not neg_c["gate_ok"],
    "limitation_B": ("NO TEETH on this fixture: the two member bars sit within "
                     "~0.17 of each other, so cross-member confusion moves the "
                     "rate too little to leave the band. Documented, not hidden; "
                     "disjoint seed sub-streams are enforced by code review, and "
                     "seed-stream REUSE is likewise band-invisible by construction "
                     "(rate == alpha exactly)."),
}
txt = json.dumps(out, indent=2, sort_keys=True) + "\n"
target = HERE / "validation_output.json"
if "--check" in sys.argv:
    committed = target.read_text()
    if committed != txt:
        print("MISMATCH: recomputed output differs from the committed JSON")
        sys.exit(1)
    print("VERIFIED: recomputed output is byte-identical to the committed JSON")
    sys.exit(0)
target.write_text(txt)
print(txt)
