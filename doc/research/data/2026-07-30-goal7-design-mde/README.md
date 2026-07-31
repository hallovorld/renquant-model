# GOAL-7 Stage 1 redesign — design MDE calibration

Produced by `python3 tools/goal7_design_mde.py --reps-null 8000 --reps-power 4000
--executed --sensitivity --json-out mde.json`.

**This is a calibration of the harness geometry, not a run of the hypothesis.** It
touches no momentum score, no label and no panel. It simulates a per-date statistic
whose *dependence structure* is the one overlapping `h`-day labels impose, and asks each
candidate design how large a constant per-date effect must be before the design detects
it at 5% with 80% probability.

| file | what it is |
|---|---|
| `run.log` | full stdout: candidate table, executed-design sizes, sensitivity band |
| `mde.json` | the same, machine-readable |

## Inputs

| input | value | provenance |
|---|---|---|
| `N` | 1082 trading days (2016-12-29 → 2021-04-19) | `[VERIFIED — redesign doc §2]` |
| `rho1` | 0.94, realised lag-1 autocorr of the per-date statistic at `h = 120` | `[VERIFIED — redesign doc §1, from the Stage-1 run]` |
| overlap share `c2` | 0.9479 | `[DERIVED — rho1 / (1 − 1/h)]` |
| `c2` at `h = 20` | carried over from `h = 120` | `[ASSUMED]` — sensitivity band reported |

## Units

`g` is in units of `sigma_x`, the per-date statistic's own SD. An economically
meaningful conversion needs `sigma_x` from a clean run, and no clean run exists.

## The two controls that make the numbers non-vacuous

* contiguous blocks at crossing 1.00 must **over-reject** at their own bar — otherwise
  the simulated dependence is doing nothing and every MDE is measuring an empty harness;
* gap-separated blocks must land at **nominal 5%** — otherwise the harness inflates
  everything equally and still cannot tell a broken design from a repaired one.

Both are asserted in `tests/test_goal7_design_mde.py`.
