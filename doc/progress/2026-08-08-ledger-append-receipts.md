# Ledger-append receipts — the writer emits the evidence

STATUS:    delivered. Both momentum ledgers (slow + fast) now emit a
           promotion-receipt on every successful append, at both append call
           sites (fresh train and crash-reconcile). No monitor change needed.

WHAT:      tools/momentum_train_run.py gains emit_ledger_append_receipt (+ a
           warn-only wrapper) and RECEIPTS_DIR; both append sites capture the
           ledger file digest BEFORE the append and emit after success.
           tests/test_momentum_ledger_receipts.py — 4 tests incl. a
           cross-repo end-to-end against the REAL orchestrator monitor.

WHY/DIR:   2 of the 5 original "silent scorer swap" CRITICALs were legitimate
           ledger appends that can never assemble a promote/rollback event —
           the append is neither. orch#909 made receipts safe (identity-
           transition matching, prefix-aware); this PR is the writer side it
           was the prerequisite for.

EVIDENCE:  artifact:      scorer_identity_monitor.py contract (read this
                          session): a ledger lane is keyed by the LEDGER
                          FILE's byte digest as stamped in run bundles — NOT
                          the artifact content sha. The receipt therefore
                          carries the FILE digest straddling the append.
                          Catching that before coding corrected my own
                          task-spec, which had named the artifact sha — the
                          validate-the-wrong-object trap, again.
           prod or exp:   experiment tooling — the writer runs in the weekly
                          job; receipts land in the dir the monitor already
                          reads (logs/promote_shadow_patchtst; the dir NAME
                          is patchtst-flavoured — renaming is a monitor+ops
                          change, deliberately not bundled here).
           existing data: appends emitted nothing; every append alarmed as an
                          unexplained boundary forever.
           best-known?:   yes — first writer-side evidence for any ledger lane.
           scope:         renquant-model only. Zero monitor change: filename
                          carries the ledger dir stem for collision-freedom
                          (two lanes, same second) and the monitor's payload
                          promoted_at fallback parses the date — an existing
                          contract, not a new one.

           Failure semantics: a receipt-write failure WARNS and does not fail
           a run whose append already succeeded — the monitor going CRITICAL
           on the unexplained boundary is the DESIGNED backstop for a missing
           receipt (fail-closed at the system level, never silent). A FAILED
           append emits nothing (tested).

TESTS:     4 passed: genesis omits identity_before (absent, not null — the
           monitor's _side_matches contract); second append carries the prior
           FILE digest; failed append emits no receipt; and the end-to-end:
           the real monitor marks the ledger boundary explained by exactly
           this receipt while an unrelated lane's swap in the SAME window
           stays CRITICAL. Full-suite delta vs main: identical pre-existing
           environment failures (3, same names on both), no new failures.

NEXT:      after merge + the next weekly fast-lane run, re-run the monitor
           backfill and confirm the two ledger-append CRITICALs from the
           original five resolve to INFO with receipt evidence, while the
           07-31..08-03 lifecycle pair stays as classified by orch#908.
