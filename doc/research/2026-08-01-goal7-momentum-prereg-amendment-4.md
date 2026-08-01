# Momentum prereg — Amendment 4 (visible, PRE-RUN): the §4.4 positive-control gate is unsatisfiable as frozen; executable replacement, validated

**Replaces the two §4.4 gate sentences with executable definitions. Filed after the
codex review of model#169 correctly rejected a runner-level reinterpretation as a
post-hoc change to a frozen criterion. Same lane as Amendments 1 and 2: the defect is
measured, the replacement is validated BEFORE any real-data execution.**

## The defect `[本次实测 2026-08-01, full 5,000 reps]`

§4.4 as frozen: "the committed pure-noise series' rejection rate under the full
protocol must lie within [0.0184, 0.0316]". The literal implementation — iid draws
tested against the worst-case `t*` — yields **0.0164**, below the band floor,
mechanically: `t* = max` over a family whose overlap-MA member carries by-construction
dependence the iid control does not have, so a true-iid null under-rejects against it.
A two-sided size band around α is satisfiable only against a matched null. (Probe-scale
0.0150 at reps=1200 first exposed this; the full-rep value confirms it.)

## The replacement (both §4.4 gates, now executable)

* **Gate 1 — positive control.** The committed fixture (iid N(0,1), n=756, sha256
  `ff859a68…`, pinned in the runner) takes the candidate's seat once: the frozen family
  is fitted to it and its bars calibrated exactly as for real data, Amendment-2
  adequacy rule included. Then EACH member's rejection rate — fresh seeded draws from
  that member (disjoint deterministic sub-streams, seed+1/seed+2) against ITS OWN
  bar — must lie in **[0.0184, 0.0316]**. Headline rate = the binding (max-bar)
  member's. The iid-vs-`t*` rate is PUBLISHED as a conservatism diagnostic with no α
  budget.
* **Gate 2 — machinery self-check.** The identical definition applied to the REAL
  candidate series' fitted family (this is what "series simulated from each admissible
  generator, pushed through the identical pipeline" executes as).
* Failure of either gate remains **UNRESOLVED-METHOD**, unchanged.

## Validation, EXECUTED before filing `[本次实测]`

Committed: `doc/research/data/2026-08-01-goal7-a4-validation/` — SELF-CONTAINED per
review: the script imports the VENDORED `goal7_momentum_inference_ref.py` beside it
(byte-identical to the reviewed #169 module, sha256 `38867d2c…` recorded in the JSON as
`inference_ref_sha256`), regenerates the fixture from its committed seed recipe and
pin-checks it, and uses no absolute path. Reproduce: `python
validate_gate_replacement.py`; verify: `--check` (re-runs and requires byte-identical
agreement with the committed JSON — VERIFIED at filing); fast bindings:
`tests/test_goal7_amendment4_evidence.py` (4 tests).

| machine | member rates | gate |
|---|---|---|
| correct (full 5,000 reps) | MA **0.0236**, AR **0.0274** (bars 2.7119 / 2.5434, AR p=6) | **PASS** |
| A: bar at wrong quantile 0.90 | MA 0.0945 | **FAIL** (caught) |
| C: mirror drift — bar at L=59, test at L=10 | MA 0.0765 | **FAIL** (caught) |
| B: cross-member bar confusion | 0.0220 (in band) | **NOT caught — limitation** |

Limitation B, stated not hidden: on this fixture the two member bars sit within ~0.17,
so cross-member confusion moves the rate too little to leave the band; seed-stream
REUSE is likewise band-invisible by construction (rate ≡ α). Both corruption classes
are covered by code review of the disjoint-sub-stream wiring, not by the band.

Because every quantity is seeded and deterministic, the correct-machine row IS the
value the runner's Gate 1 will reproduce at execution: predetermining a MACHINERY gate
is intended — the machine is proven calibrated before the study runs. **Self-voiding
clause:** if the runner's execution-time Gate-1 values differ from the committed
validation values, the run is VOID (it means the machinery changed after validation).

## Not claimed

That the replacement makes the study easier to pass — Gate 1/2 constrain the MACHINE,
not the candidate; H1's bar, placebo, and MDE ceiling are untouched. That corruption
class B is detectable by this gate — it measurably is not, on this fixture. That the
frozen sentence was wrong in intent — it was unexecutable as written, which is exactly
what pre-run probing of executable rules exists to catch (third instance, after F1 and
the adequacy envelope).
