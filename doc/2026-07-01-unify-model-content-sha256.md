# Unify calibrator/scorer `model_content_sha256` — fixes recurring fingerprint-mismatch fail-closed

**Date:** 2026-07-01 · **Author:** Claude · **Status:** PR open, fix landed here + renquant-common + renquant-pipeline

## The bug

`fit_calibrator_alpha158_fund.py::model_content_sha256` (this repo, stamps
`scorer_model_content_fingerprint` on every calibrator fit by
`monthly_calibrator_refresh.sh`) and `panel_scorer.py::model_content_sha256`
(renquant-pipeline, the RUNTIME-AUTHORITATIVE check in
`_assert_calibrator_matches_scorer`) were independently hand-copied and hashed
DIFFERENT field sets:

- This repo: ALLOWLIST style — an explicit 11-field dict, INCLUDING `label_col`.
- renquant-pipeline: DENYLIST style — excludes a curated mutable-metadata set,
  EXCLUDES `label_col`, keeps everything else (e.g. `kind`, which this repo's
  allowlist never included).

A calibrator fit here could never match the runtime check, **by construction**
— not transient drift. Fail-closed monthly: 2026-05-27, 2026-06-22, 2026-07-01.

## The fix

`fit_calibrator_alpha158_fund.py` deletes its own hand-copied
`model_content_sha256` and imports the identical function from
`renquant_common.model_fingerprint` (renquant-common `0.8.1`) — the same
function renquant-pipeline's `panel_scorer.py` now also imports. `__all__`
still exports `model_content_sha256` (now the imported name) so existing
importers are unaffected. `_artifact_fingerprint`'s call site is unchanged —
it just calls the (now-shared) `model_content_sha256` as before.

- `pyproject.toml` pin bumped to `renquant-common>=0.8.1,<0.9` — structural
  requirement, not just a range widen.
- New regression test `tests/gbdt/test_model_content_sha256_cross_repo.py`
  (this is the test that should have caught the original bug): given a
  synthetic panel-LTR payload, asserts the fit-time hash (this repo) equals
  the runtime hash (renquant-pipeline, imported as a CI sibling checkout),
  including after simulating post-fit promotion/WF-gate metadata stamping.
  Also pins that both entry points ARE the same function object, not a
  value-equal copy.

## Also checked (not touched)

- `renquant_model_patchtst/fit_calibrator.py::_artifact_fingerprint` does NOT
  independently recompute the hash — it only reads pre-stamped fingerprint
  fields (sidecar/checkpoint) with a raw-file-hash fallback. Not a divergent
  algorithm; left as-is.

## Dependency order

This PR depends on `renquant-common` PR (adds `renquant_common.model_fingerprint`,
bumps to 0.8.1) landing first. CI here checks out both `renquant-common` and
`renquant-pipeline` from `main`, so full green requires both companion PRs
merged first (the pipeline PR is not a hard blocker for this repo's own
import — only the common one is — but the new cross-repo test additionally
needs the pipeline PR merged to exercise the fixed runtime side rather than
the pre-fix one).
