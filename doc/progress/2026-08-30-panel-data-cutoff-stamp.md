# orch#906: the panel trainer stamps a MEASURED binding data cutoff

STATUS:   delivered. `build_model_artifact` now stamps
          `metadata.data_cutoff_date` (max LABELED row date) and
          `metadata.feature_cutoff_date` (max row date) COMPUTED from the
          training frame it consumed — never asserted from window arithmetic
          or the wall clock. `BuildArtifactTask` merges the driver's
          `extra_artifact_fields["metadata"]` one level deep instead of
          clobbering, so the orchestrator's `training_contract` and the
          trainer's stamps coexist.
WHY/DIR:  the daily `RenQuant 104 model freshness UNKNOWN` alert
          (orch#906/#745/#941): the served panel artifact carries NO binding
          data cutoff, and the monitor refuses `trained_date` by design ("a
          fresh build over stale data is not fresh"), so `rq104`
          model-freshness reads `worst=UNKNOWN` every day. The producer is
          the only honest place to measure the cutoff — the two blockers
          orch#906 recorded are resolved here: (1) the training frame IS in
          scope inside `build_model_artifact` (it already reads
          `train["date"]` for `panel_shape`); (2) the stamp lives under
          `metadata`, which `renquant_common.model_fingerprint` classifies
          OPERATIONAL (denylisted in the legacy 0.8.1 hash), so the content
          hash — the byte-identity that matters — is untouched, pinned by a
          test.
EVIDENCE:
  artifact:      `panel_trainer.training_data_cutoffs` +
                 `build_model_artifact` stamp; `pipeline.BuildArtifactTask`
                 metadata merge; `tests/gbdt/test_data_cutoff_stamp.py`
                 (9 tests: measured-not-clock, no-fabrication on unusable
                 frames, hash neutrality, merge-not-clobber, job==direct).
                 Existing parity/pipeline/signature/cross-repo suites green
                 [VERIFIED — pytest run 2026-08-30].
  prod or exp:   exp — behaviour reaches production only after merge + the
                 orchestrator retrain lane runs against this checkout.
  existing data: served `panel-ltr.alpha158_fund.json` has 0 of 6 binding
                 cutoff axes, `trained_date=2026-08-02` only
                 [VERIFIED — json.load, 2026-08-30]; the retrain log's
                 labeled-data end (2026-05-05) is exactly what this stamp
                 would have carried.
  best-known?:   yes — measured from the consumed frame at the one point
                 where the frame is authoritative; absent-when-unmeasurable
                 (fail-closed downstream) instead of fabricated.
  scope:        one helper + one stamp site + one merge fix + tests. No
                training math, no fingerprint, no umbrella file touched.
NEXT:      merge THIS PR first, then renquant-orchestrator
           `fix/rq104-freshness-data-cutoff` (its `_validate_scorer_artifact`
           refuses unstamped artifacts fail-closed and would fail the weekly
           retrain lane until this stamp exists in the sibling checkout).
           Cross-linked in both PR bodies.
REVIEW:    codex (haorensjtu-dev).
