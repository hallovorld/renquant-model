# Relocated evidence — same-recipe booster divergence on the real panel

RELOCATED 2026-08-04 from `renquant-orchestrator` branch
`goal4/booster-divergence-on-the-real-panel` (PR orch#712, CLOSED
out-of-scope). The closure ruling, verbatim:

> `renquant-orchestrator` owns pinned-subrepo orchestration, and this PR
> hosts model-artifact evaluation. […] What must move, and where:
> 同-recipe boosters 在真实面板上的分歧度量 → `renquant-model`, with the
> source/provenance and the stated non-performance claims carried across.
> If orchestration ever needs the result, it consumes a versioned summary
> artifact, not the evaluator.

## Contents (byte-verbatim from the source branch)

- `CLAIMS-original-progress-doc.md` — the authored 2026-08-01 record. The
  headline: 12 distinct boosters under ONE config fingerprint
  (`sha256:f8fb2259b…`), scored on the live alpha158 panel's last 20
  sessions → **median top-decile disagreement 35.7%** (per-date median
  pairwise Spearman 0.854; worst pair/date 67% replaced). This CORRECTS
  orch#698's ~60% synthetic figure (~1.7× overstated as a description of
  production).
- `divergence.json`, `run.log` — the evidence corpus, as measured.
- `booster_real_panel_divergence.py` — the evaluator. MACHINE-LOCAL
  RUNNER: it reads the operator machine's live artifact tree and panel;
  it is preserved as provenance, not wired into this repo's CI.
- `test_booster_real_panel_divergence.py` — the original guard test
  (asserts the real median stays below 0.50). Same machine-local caveat;
  deliberately NOT under `tests/` so this repo's CI does not measure a
  disk it does not have.

## Non-performance claims (carried across, per the ruling)

The measurement quantifies IDENTITY divergence between same-recipe
boosters. It does not measure return differences, licenses no production
inference, and does not claim which booster is better. Its downstream
use is the GOAL-4/GOAL-8 ensemble premise (diversity exists to be
exploited) and the WF-gate identity-collapse record (34 artifacts → 14
boosters under one recipe hash, orch#769 item 10).
