# 2026-07-26 — shadow artifact trainer: top-decile classifier (pipeline#213 step 3)

STATUS:    trainer script + tests; NO artifact produced by this PR
WHAT:      scripts/train_topdecile_clf_shadow.py — trains the clf leg of the
           CONFIRMED blend (frozen construction: per-date top-decile membership
           of fwd_60d_excess, frozen CLF params, production normalization stamped
           into a standard v3 artifact via build_model_artifact; kind stays
           panel_ltr_xgboost so PanelScorer.load serves it unchanged). Blend is
           computed downstream by the readout job, never inside the scorer.
WHY/DIR:   model#76 (merged) closed the reopening chain with an independent-draw
           CONFIRMED verdict, which per its own frozen consequence unblocks the
           PARKED shadow design at renquant-pipeline#213 §5. This PR is rollout
           step 3: the clf-leg trainer that will produce the shadow artifact the
           blend needs. It is code-only (no artifact, no production write); the
           next rollout PRs (artifact production, pipeline shadow-slot wiring,
           orchestrator readout) follow per pipeline#213 §5.
EVIDENCE:
  artifact:      tests/gbdt/test_train_topdecile_clf_shadow.py — 3 passed
                 (output guard incl. prod-path refusal; per-date 10% label
                 property; params drift-guard against the confirmatory executor)
  prod or exp:   script only; shadow-only output guard enforced
  existing data: the "CONFIRMED blend" this trainer's construction is frozen from
                 is model#76's independent-draw result (merged 35a291e):
                 doc/research/evidence/2026-07-25-blend-confirmatory-v2/confirmatory-bundle.json,
                 diff +0.0687, CI90 [+0.0156, +0.1269], seeds 9/10, w50 guard +0.0117
                 (doc/research/2026-07-26-blend-confirmatory-v2-results.md)
  best-known?:   reuses build_model_artifact for v3-contract consistency; the cited
                 bundle is the most recent (and only out-of-draw) confirmatory result
                 in this line — model#74 (screen) and model#75 (prereg freeze) are
                 its prerequisites, not independent evidence
  scope:         "this PR's own evidence is code-only (unit tests, no model/data
                 claim); the CONFIRMED-blend construction it implements is backed by
                 model#76's EXPERIMENT-grade bundle above, not by this PR; authorizes
                 no deployment — artifact production + slot wiring are the next
                 rollout PRs per pipeline#213 §5"
NEXT:      on merge -> produce the shadow artifact (additive, shadow dir) ->
           pipeline shadow-slot PR -> orchestrator readout job (operator grant
           at the launchd step).
