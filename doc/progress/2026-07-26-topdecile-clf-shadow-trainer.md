# 2026-07-26 — shadow artifact trainer: top-decile classifier (pipeline#213 step 3)

STATUS:    trainer script + tests; NO artifact produced by this PR
WHAT:      scripts/train_topdecile_clf_shadow.py — trains the clf leg of the
           CONFIRMED blend (frozen construction: per-date top-decile membership
           of fwd_60d_excess, frozen CLF params, production normalization stamped
           into a standard v3 artifact via build_model_artifact; kind stays
           panel_ltr_xgboost so PanelScorer.load serves it unchanged). Blend is
           computed downstream by the readout job, never inside the scorer.
EVIDENCE:
  artifact:      tests/gbdt/test_train_topdecile_clf_shadow.py — 3 passed
                 (output guard incl. prod-path refusal; per-date 10% label
                 property; params drift-guard against the confirmatory executor)
  prod or exp:   script only; shadow-only output guard enforced
  existing data: frozen construction from model#74/#75/#76 (all MERGED)
  best-known?:   reuses build_model_artifact for v3-contract consistency
  scope:         authorizes no deployment; artifact production + slot wiring are
                 the next rollout PRs per pipeline#213 §5
NEXT:      on merge -> produce the shadow artifact (additive, shadow dir) ->
           pipeline shadow-slot PR -> orchestrator readout job (operator grant
           at the launchd step).
