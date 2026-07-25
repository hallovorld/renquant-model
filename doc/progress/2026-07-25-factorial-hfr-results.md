# 2026-07-25 — Factorial H×F×R results: NULL ×7, OFAT rehabilitated

STATUS:    results PR for the merged model#67 prereg (frozen law), executed on the
           model#71-fixed executor
WHAT:      `doc/research/2026-07-25-factorial-hfr-results.md` + evidence bundle
           `doc/research/evidence/2026-07-25-factorial-hfr/factorial_hfr_result.json`
           (the frozen analyzer's own verdict bundle, incl. per-date/per-seed clean
           series — replayable via the analyzer functions frozen in the executor).
WHY/DIR:   Executes the frozen analyzer against a fresh run; per prereg the results
           PR may not redefine the estimator, the Holm family, or the block.
EVIDENCE:
  artifact:      evidence/2026-07-25-factorial-hfr/factorial_hfr_result.json
  prod or exp:   EXPERIMENT, read-only; production regime labels from the 5-task
                 chain (prod config + prod GMM artifact, computed 2026-07-24)
  existing data: anchor reproduced +0.0489 vs +0.0488 expected (provenance:
                 production 3-fold CV vs fwd_60d label)
  best-known?:   frozen analyzer's own output; no post-hoc statistics added
  scope:         "all seven registered tests null at resolution ~±0.01-0.02 on the
                 survivorship panel; BULL_VOLATILE/CHOPPY precommitted non-registrable;
                 NULL ≠ zero; run-1 (spurious VOID, model#71) quarantined — only this
                 run's numbers are citable"
NEXT:      VERDICTS row in orchestrator (cross-repo, PROVISIONAL); any H/F/R re-pitch
           requires a NEW frozen prereg with a mechanism (R4).
