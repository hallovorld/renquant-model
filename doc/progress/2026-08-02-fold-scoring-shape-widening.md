# fold_scoring v0.2.1: means/stds accepted as dict OR feature_cols-aligned list (issue #187, Option B)

STATUS: complete (implementation + tests); awaits codex review.
WHAT: `load_fold_scorer` now accepts `feature_means`/`feature_stds` in either
committed artifact shape: a dict keyed exactly by `feature_cols` (the clf
lineage-bundle shape, unchanged) OR an ordered list with one entry per feature
(the gbdt WF-window shape). A list is accepted ONLY when
`len == len(feature_cols)` and is converted internally to the dict form keyed
by `feature_cols` order; the writer-alignment assumption is stated in the
module contract and the docstring and guarded by that length equality — a
mismatch refuses naming BOTH lengths. TYPE strictness is unchanged in both
branches: a str (the 2026-08-01 stringified-norm_kind incident class) or any
other non-dict/non-list type refuses loudly BY INCIDENT NAME, and the dict
branch keeps the key-set==feature_cols check with its existing message.
Version 0.2.0 → 0.2.1 (additive; `>=0.2.0,<0.3` consumer pins unaffected).
The heavyweight `import xgboost` moved AFTER the fail-closed validation block
(behaviour-preserving for valid artifacts) so every refusal path is
exercisable by synthetic fixtures that need no booster.
WHY/DIR: issue #187 measured two REAL permanent artifact families with two
shapes; the dict-only contract refused every gbdt window artifact, forcing
backtesting#100 to ship a re-keying adapter. The contract-owner decision on
#187 is Option B — one widening with STRICT verification, because
adapter-per-consumer re-derives the same re-keying at every call site (how
twin implementations breed).
EVIDENCE:
  artifact:      src/renquant_model_gbdt/fold_scoring.py (widening + contract
                 docstring), pyproject.toml (0.2.1 + note),
                 tests/test_fold_scoring_contract.py (+5: real gbdt window
                 loads+scores; list/dict forms score IDENTICALLY on the same
                 frame; length-mismatch names both lengths; str refused by
                 incident name; float refused, not defaulted)
  prod or exp:   prod-adjacent — public contract module consumed by the WF
                 gate lineage lane (backtesting#96/#100); no serving-surface
                 write
  existing data: both real committed families load through the PUBLIC api:
                 clf fold doc/research/data/2026-08-01-clf-wf-lineage-bundle
                 folds[10] (dict, 172 keys) and gbdt window
                 doc/research/data/2026-08-02-jobb-gbdt-depth-extension-run001/
                 window_artifacts/2019-01-14/panel-ltr.json (list, 172 entries
                 aligned to 172 feature_cols) `[VERIFIED — pytest 2026-08-02]`;
                 the GOLDEN corpus-reproduction test also PASSED on this
                 machine (panel present), so the dict path is regression-proof
                 to <1e-6 `[VERIFIED — same run]`
  best-known?:   yes — the #187 decision comment is the spec; strict length
                 guard is the strongest verification available for a writer
                 that persists no key names
  scope:         tests/test_fold_scoring_contract.py 12 passed (7 prior + 5
                 new); make test 1431 passed, 0 failed `[VERIFIED — pytest
                 2026-08-02, both counts measured]`
NEXT: codex review → merge; then backtesting#100's `gbdt_window_scorer_factory`
adapter removal rides that PR's next revision (recorded on #187 — not touched
here).
AC6: N/A — contract widening in the model repo; no orchestrator run surface.
