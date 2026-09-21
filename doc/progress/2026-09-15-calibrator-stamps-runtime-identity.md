# 2026-09-15 — calibrator fit: stamp the identity the live runtime presents for an unstamped scorer

STATUS:   delivered, awaiting review — zero reviews at head.
WHAT:     `_artifact_fingerprint` in fit_calibrator_alpha158_fund.py now
          stamps an unstamped (pre-schema-v1) served scorer with the same
          0.8.1-denylist identity the live runtime presents
          (`_runtime_legacy_identity` calls the shared
          `stamp_artifact_metadata` shim `PanelScorer.load` already uses),
          instead of the schema-v1 allowlist hash the fit script computed on
          its own.
WHY/DIR:  root cause, reproduced read-only against the served scorer — the
          fit script and the runtime disagreed on which hash identifies an
          unstamped artifact (allowlist vs. denylist), so
          `monthly_calibrator_refresh` failed Step 3b's BINDING GATE on
          2026-09-01 and will fail the same way on 2026-10-01 without this
          change; the fifth occurrence of this class despite renquant-model#56
          already unifying both producers on one `model_content_sha256` (the
          runtime never calls that function for a legacy artifact at all).
EVIDENCE: see §4(b) below.
  artifact:      src/renquant_model_gbdt/fit_calibrator_alpha158_fund.py + tests/test_calibrator_stamps_runtime_identity.py (4 passed on this branch).
  prod or exp:   exp — fit-script fix; production untouched (the binding gate quarantines, it does not corrupt, on mismatch); takes effect once the umbrella advances its renquant-model pin.
  existing data: read-only reproduction 2026-09-15 against the live served scorer panel-ltr.alpha158_fund.json — verify_calibrator_scorer_binding.py: live pair pass; simulated fresh fit stamped the old way fail (BINDING MISMATCH); the same fit stamped with the runtime identity pass.
  best-known?:   yes — anti-vacuity: the same 4 tests run against origin/main's package (isolated copy) = 3 failed, 1 passed; this branch = 4 passed.
  scope:         src/renquant_model_gbdt/fit_calibrator_alpha158_fund.py and its test file only.
NEXT:     merge after review; lands live once the umbrella advances its
          renquant-model pin — the orchestrator ack row for
          com.renquant.monthly-calibrator-refresh exit 1 (orch#1124) names
          that pin advance as its clearing condition.

## Conclusion

`monthly_calibrator_refresh` (umbrella, 1st of the month 03:00) failed on
2026-09-01 at Step 3b, `SCORER/CALIBRATOR BINDING GATE FAILED`, and
quarantined the staged calibrator (production untouched — the gate works).
It will fail the same way on 2026-10-01 without this change. Root cause,
reproduced read-only on 2026-09-15 against the served scorer
`panel-ltr.alpha158_fund.json` `[VERIFIED]`:

- `fit_calibrator_alpha158_fund._artifact_fingerprint` stamps
  `model_content_sha256(payload)` — the schema-v1 ALLOWLIST hash —
  `sha256:0660bc89…` for that scorer.
- The runtime (`PanelScorer.load` → `renquant_common.model_fingerprint.
  stamp_artifact_metadata`) identifies the same UNSTAMPED (pre-schema-v1)
  artifact by the 0.8.1 DENYLIST hash: `sha256:2d5a0288…`. The binding check
  compares the calibrator's stamp against THAT.
- `scripts/verify_calibrator_scorer_binding.py`: live pair → `pass`; a
  simulated fresh fit stamped the fit script's way → `fail` (BINDING
  MISMATCH); the same fit stamped with the runtime identity → `pass`.

renquant-model#56 (2026-07-15) made both producers import ONE
`model_content_sha256`, but the runtime does not use that function for a
legacy artifact at all — so the fifth occurrence of this class (05-27,
06-22, 07-01, 07-14/16, 09-01) happened with #56 deployed
(`renquant-model` runtime pin 36085810 contains 5ef1c2d9).

## Change

`_artifact_fingerprint` order is now: (1) a schema-v1 stamped artifact's own
`model_content_fingerprint`; (2) for an unstamped artifact, the identity the
runtime presents — `_runtime_legacy_identity` asks the shared shim
`stamp_artifact_metadata` (the exact function `PanelScorer.load` calls;
DeprecationWarning suppressed for this one call, with the reason in the
docstring) rather than re-implementing either hash; (3) the historical
chain (v1 hash, then file hashes) when the shim cannot answer (e.g. the file
is not on disk).

## Evidence (§4(b))

- `tests/test_calibrator_stamps_runtime_identity.py` (4 tests): an unstamped
  artifact is stamped with the runtime identity, on a payload where the two
  hashes provably differ (`label_col` is denylisted in 0.8.1 but PREDICTIVE
  in v1; `best_iter`/`version`/`cv_folds` are kept by the denylist and
  absent from the allowlist — the served artifact carries all of them); a v1
  stamped artifact keeps its stamp; the helper's answer is the shim's, not a
  copy; a missing file falls through to the historical chain.
- Anti-vacuity: the same tests run against `origin/main`'s package
  (isolated copy, `-c /dev/null`): `3 failed, 1 passed`; this branch:
  `4 passed`. `[VERIFIED]`

## Deploy

The monthly job imports `renquant_model_gbdt` from the umbrella's pinned
runtime checkout (`.subrepo_runtime/repos/renquant-model`); this lands only
when the umbrella advances the renquant-model pin. The orchestrator ack
row for `com.renquant.monthly-calibrator-refresh` exit 1 (orch#1124) names
that as its clearing condition.
