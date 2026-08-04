# Relocated evidence — the divergence is structured: consensus among same-recipe boosters

RELOCATED 2026-08-04 from `renquant-orchestrator` branch
`goal4/booster-consensus-structure` (sibling of PR orch#712; that PR's
out-of-scope closure ruling — model-artifact evaluation belongs in
`renquant-model` — applies identically, so this measurement moves in the
same batch; see the neighboring
`2026-08-01-booster-real-panel-divergence/RELOCATION.md` for the ruling
verbatim).

## Contents (byte-verbatim from the source branch)

- `CLAIMS-original-progress-doc.md` — the authored 2026-08-01 record. The
  headline: over the same 12 boosters / 20 sessions / 3,528 top-decile
  slots, the 35.7% disagreement is NOT uniform churn — **66.9% of traded
  slots already carry a ≥7/12 majority**; single-voter names are 29.8% of
  NAMES but only 6.2% of SLOTS. There is a stable consensus core plus a
  churning fringe.
- `consensus.json`, `run.log` — the evidence corpus, as measured.
- `booster_consensus_structure.py` — the evaluator. MACHINE-LOCAL RUNNER
  (reads the operator machine's live artifact tree/panel); preserved as
  provenance, not wired into CI.
- `test_booster_consensus_structure.py` — the original guard test, same
  machine-local caveat, deliberately NOT under `tests/`.

## Non-performance claims (carried across)

Vote structure is an IDENTITY property, not a performance ranking: no
returns are measured, no booster is claimed better, nothing is licensed
for production. Downstream use: the GOAL-8 ensemble premise (a majority
core suggests cheap consensus scoring is meaningful) and the S3 MoE
design discussion — as preregistered inputs, never as a verdict.
