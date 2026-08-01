#!/usr/bin/env python3
"""Amendment 4 pre-run validation: the replacement §4.4 gates are (a) satisfiable on
a correct machine and (b) FAIL on deliberately corrupted machines.

Subject: the committed positive-control fixture (iid N(0,1), n=756, sha ff859a68…)
from model#169. The inference module is imported from the #169 branch worktree; its
HEAD sha is recorded in the output. No real market data is touched anywhere here.

Because every quantity is seeded and deterministic, the positive rows BELOW ARE the
values the runner's control gate will reproduce at execution — predetermining a
MACHINERY gate is the point: the machine is proven calibrated before the study runs.
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

RUNNER_WT = Path("/Users/renhao/git/github/renquant-model-wt-momrun")
INF_PATH = RUNNER_WT / "tools/goal7_momentum_inference.py"
FIXTURE = RUNNER_WT / "tools/data/goal7_positive_control_noise.csv"

spec = importlib.util.spec_from_file_location("inf", INF_PATH)
INF = importlib.util.module_from_spec(spec)
spec.loader.exec_module(INF)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

noise = pd.read_csv(FIXTURE, float_precision="round_trip")["x"].to_numpy()
assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == \
    INF.FROZEN_INFERENCE["positive_control_sha256"]

cfg = dict(INF.FROZEN_INFERENCE)
cfg["envelope_rule"] = "bootstrap_max"
out = {"inference_module_head": subprocess.run(
    ["git", "-C", str(RUNNER_WT), "rev-parse", "HEAD"],
    capture_output=True, text=True).stdout.strip(),
    "fixture_sha256": INF.FROZEN_INFERENCE["positive_control_sha256"],
    "n": len(noise), "band": list(cfg["gate_band"])}

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
NEG_REPS = 2000  # SE ≈ sqrt(.025*.975/2000) ≈ 0.0035; failures below are >> 3 SE
var = float(noise.var())
fit = INF.fit_ar(noise, cfg["ar_p_max"])

def rate(gen, bar, seed_off):
    return INF._rejection_rate(gen, bar, cfg["L"],
                               np.random.default_rng(cfg["seed"] + seed_off),
                               NEG_REPS, cfg["gate_band"])

# corruption A: bar calibrated at the WRONG quantile (0.90) — bars too low
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

# corruption C: mirror drift — bar calibrated with T at L=59, test statistic
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
                     "~0.1 of each other, so cross-member confusion moves the "
                     "rate too little to leave the band. Documented, not hidden; "
                     "disjoint seed sub-streams are enforced by code review, and "
                     "seed-stream REUSE is likewise band-invisible by construction "
                     "(rate == alpha exactly)."),
}
txt = json.dumps(out, indent=2, sort_keys=True)
Path(__file__).parent.joinpath("validation_output.json").write_text(txt + "\n")
print(txt)
