# Condact harness corpus-pin read — fixed via ast on the v2 source   (PR #217)

STATUS:    delivered — one-commit bug fix on the merged condact harness
           (fix commit 6e5fb61); still NO real Stage-E read has
           completed (the failed invocation exited on the assert path
           before touching data — fail-closed held).

WHAT:      doc/design/frozen/2026-08-10-condact-harness.py `--real`
           path: the corpus pin is now read from the committed v2
           harness SOURCE via `ast` (Assign to `CORPUS_SHA256`,
           `ast.literal_eval`), replacing the `_v2.CORPUS_SHA256`
           module-attribute read. 11 insertions, 3 deletions, no other
           file.

WHY/DIR:   the v2 harness defines `CORPUS_SHA256` inside `main()`
           [VERIFIED — grep: 2026-08-09-xgbmom-v2-harness.py:122 is
           indented inside main(); importing the module yields
           hasattr(m,"CORPUS_SHA256") == False], so the first real
           Stage-E invocation died with AttributeError before the
           corpus assert could pass. Committed-text-is-authority is the
           same pattern the v2 verifier already uses; per the merged
           model#215 §5 closing rule, this PR is the visible amendment
           surface for the deviation.

EVIDENCE:  artifact:      doc/design/frozen/2026-08-10-condact-harness.py
           prod or exp:   experiment tooling; corpus read-only, nothing
                          real was read or written
           existing data: pin recovered by the fixed lookup =
                          870f68ebad5d2d87e2601f62310f34615d2d8d25df9d9cbf563629b13129bf7e
                          [VERIFIED — ast walk over the committed v2
                          source, this session], identical to the v2
                          prereg pin at harness line 122
           best-known?:   yes — reads the frozen committed text, not
                          runtime module state
           scope:         "this fixes the condact harness --real pin
                          read only; gates/controls/verifier untouched"

TESTS:     py_compile of the harness [VERIFIED — exit clean, this
           session]; the ast lookup reproduced standalone finds the pin
           and the `assert _pin` guard holds. No new pytest — the
           frozen-harness dir is design-surface code with committed
           control JSONs as its test fixture (unchanged by this PR).

NEXT:      merge → the ONE Stage-E run (exploratory diagnostics, no
           verdict authority) recorded in 2026-08-10-condact-harness.md
           can actually execute.
