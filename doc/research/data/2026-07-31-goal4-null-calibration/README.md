# GOAL-4 Phase-0 — dependence-preserving null calibration

Produced by `python3 tools/goal4_null_calibration.py --reps 6000 --reps-power 3000`.

Supplies **prerequisite 1** of `doc/design/2026-07-30-goal4-power-wall-and-options.md`:
the *empirical false-positive calibration at the realised geometry*, over a
**circular block bootstrap** of the screen's own per-date statistic series. It needs no
model of the dependence, because the screen persisted `per_date_g_real.csv`.

**It does not revive the screen.** The Phase-0 result stays UNRESOLVED and `t = -1.0025`
remains uncitable as evidence against an ensemble under any bar produced here.

| file | what it is |
|---|---|
| `run.log` | full stdout: measured autocorrelation, `b` sweep, repaired geometries, MDE |
| `calibration.json` | the same, machine-readable |

## The instrument reports its own bias

A circular block bootstrap at `b = 60` on `n = 508` leaves ~9 resampling units, and
repeated blocks widen the null **even on i.i.d. input**. Every row therefore carries
`size_iid_baseline`, measured by pushing i.i.d. Gaussian noise of the same length and
dispersion through the identical path. **Read `size_excess_over_baseline`.** A raw size
against a nominal 0.05 would charge the data for a distortion the bootstrap introduced.

## Controls

* the bootstrap must **respond** to dependence — the real series (`ρ₁ = +0.7317`) must
  calibrate to a wider null than the near-independent synthetic control (`ρ₁ = −0.0412`);
* the instrument must **not** be assumed exact — a test asserts the i.i.d. baseline is
  NOT 0.05, which is why the baseline column exists.

Both are in `tests/test_goal4_null_calibration.py`.
