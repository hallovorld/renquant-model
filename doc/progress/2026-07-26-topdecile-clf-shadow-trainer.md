# 2026-07-26 — shadow artifact trainer: top-decile classifier (pipeline#213 step 3)

STATUS:    delivered
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
  artifact:      tests/gbdt/test_train_topdecile_clf_shadow.py — 6 passed
                 (fail-closed output guard on path COMPONENTS incl. two
                 substring-only bypass repros; per-date 10% label property;
                 params drift-guard against the confirmatory executor;
                 stamp_contract adds config_fingerprint + inference-smoke
                 metadata and pins that it must run before the shadow-only
                 bookkeeping fields are added)
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

ROUND-2 FIX (Codex HIGH 1 + HIGH 2, both fixed): the trainer originally
wrote the bare `build_model_artifact()` payload plus shadow-only bookkeeping
fields, with no config-fingerprint/inference-smoke contract stamping and a
substring-only (not path-component) shadow guard. Fixed by adding
`stamp_contract()` (reuses `renquant_common.model_fingerprint.
model_content_sha256` + `panel_data.attach_inference_smoke`, called BEFORE
the shadow-only fields since those are deliberately unclassified in the
fingerprint tables and would hard-error `model_content_sha256`), and by
rewriting `refuse_non_shadow` to check `path.resolve().parts` for a literal
`shadow` component plus a production-marker component denylist (was:
substring match on the joined path string, which both `/tmp/prod/shadow.json`
and `/tmp/production-shadow/model.json` bypassed).
Verified: `pytest -q tests/gbdt/test_train_topdecile_clf_shadow.py` -> 6
passed; `pytest -q tests/gbdt/` -> 113 passed, no regressions. No
production-path writes in the diff.

ROUND-3 FIX (Codex MED 1 + P1, both fixed): (1) `STATUS:` above used
freeform text instead of a C5-canonical value (`delivered | in-progress |
planned | rejected`) — normalized to `delivered` (the doc's own WHY/DIR
already states this PR is code-only, no artifact produced). (2)
`stamp_contract()` fixes `config_fingerprint`/`metadata` before `main()`
added `shadow_role`/`blend_spec`/`classifier_label_spec` as bare NEW
top-level keys — those three keys are absent from renquant-common's
`PREDICTIVE_KEYS`/`OPERATIONAL_KEYS`, so every later
`model_content_sha256()`/`verify()` of the written artifact hard-failed with
`UnclassifiedKeyError`, making the artifact permanently unfingerprintable.
Fixed by nesting all three fields under `artifact["metadata"]` instead
(already OPERATIONAL-classified; schema v1 treats a nested value as one
atomic unit of its parent key's classification, so no renquant-common table
change is needed). Added
`test_full_artifact_with_shadow_fields_is_fingerprint_verifiable`, an
end-to-end test that runs the actual `stamp_contract` + metadata-nesting
sequence and round-trips the final artifact through
`model_content_sha256()`/`stamp()`/`verify()`.
Verified: `pytest -q tests/gbdt/test_train_topdecile_clf_shadow.py` -> 7
passed; `pytest -q tests/gbdt/` -> 114 passed, no regressions.
