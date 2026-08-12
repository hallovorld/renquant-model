# Momentum TRAIN CLI: receipt dir is injectable — tests stop writing the prod path

STATUS:    fix landed on branch; model suite green (1576 passed, 1 skipped).
           Behaviour-invariant for the real weekly job. Cleaning the 40+
           already-leaked files in the operator's live dir is a SEPARATE
           operator-gated cleanup — NOT in this PR (no live-tree writes).

WHAT:      `tools/momentum_train_run.py` — the receipt output dir is no longer
           a fixed module constant baked into the emit path. Added an
           injection seam:
             - `RECEIPTS_DIR` stays the production default (value UNCHANGED:
               `<RQ>/logs/promote_shadow_patchtst`).
             - new `RECEIPTS_DIR_ENV = "MOMENTUM_RECEIPTS_DIR"` + a
               `resolve_receipts_dir(cli_arg=None)` resolver with precedence
               `--receipts-dir` > `$MOMENTUM_RECEIPTS_DIR` > `RECEIPTS_DIR`.
             - `receipts_dir` is threaded `main` → `_reconcile_or_refuse` →
               `_emit_receipt_or_warn` → `emit_ledger_append_receipt` (the last,
               orch#909's public writer, keeps its EXISTING signature — it
               already took `receipts_dir` as its first arg; content/format
               and the monitor contract are untouched).
             - new optional `--receipts-dir` CLI flag.
           `tests/test_momentum_train_package.py` — `_wire_fake_cli_surfaces`
           now `monkeypatch.setenv(RECEIPTS_DIR_ENV, tmp_path/"receipts")`, so
           EVERY real-run CLI test emits into pytest's tmp. Added 3 tests
           (one behaviour-invariance, one HARD guard, one flag-precedence).

WHY/DIR:   The defect [VERIFIED 2026-08-11]: `_emit_receipt_or_warn` hardcoded
           the module constant `RECEIPTS_DIR` (the operator's REAL prod receipt
           dir the orchestrator scorer-identity monitor reads). Every rc-0
           TRAINED/RECONCILED CLI test path emits a receipt, and every such
           test routes through `_wire_fake_cli_surfaces` with NO isolation of
           that constant — so `pytest` wrote receipts into the live prod dir.
           Ground truth: `<RQ>/logs/promote_shadow_patchtst/` held 44 leaked
           `*__out*.json` whose `lane` is a `pytest-of-renhao` tmp path and
           `cutoff:null` — unmistakable test output. This is the "Never write
           production paths" / "tests that measure the operator's disk" /
           decision-ledger test-write incident class. Fix = make WHERE tests
           write injectable; production keeps writing the same dir.

EVIDENCE:  artifact:      seam quoted — `_emit_receipt_or_warn` line 247 now
                          calls `emit_ledger_append_receipt(receipts_dir, …)`
                          (was `RECEIPTS_DIR`); `main` line 359 resolves
                          `receipts_dir = resolve_receipts_dir(a.receipts_dir)`
                          [VERIFIED — read back from the committed diff].
                          Behaviour-invariance: with no flag and no env,
                          `resolve_receipts_dir()` returns `RECEIPTS_DIR`
                          verbatim, and `RECEIPTS_DIR`'s literal value is
                          unchanged — asserted by
                          `test_receipts_dir_defaults_to_the_prod_monitor_path_when_uninjected`.
           prod or exp:   fresh clone in an isolated scratchpad worktree
                          (`hallovorld/renquant-model`, NOT the live tree /
                          NOT `.subrepo_runtime`); PYTHONPATH pointed at the
                          real sibling `src/` READ-ONLY to run the suite. The
                          live prod receipt dir was NOT written: count stayed
                          44 and `find -mmin` showed zero modifications across
                          both the targeted and the full-suite runs
                          [VERIFIED — 2026-08-11].
           existing data: the merged receipt-writer (`emit_ledger_append_receipt`,
                          orch#909) and `tests/test_momentum_ledger_receipts.py`
                          (already tmp-isolated — it passes an explicit
                          `receipts` dir) are unchanged in behaviour.
           best-known?:   yes — env + CLI seam with the prod path as the
                          untouched default is the minimal behaviour-invariant
                          fix; no receipt content/format or monitor-contract
                          change.
           scope:         `tools/momentum_train_run.py` (seam only, no runtime
                          content change) + `tests/test_momentum_train_package.py`
                          (isolation + 3 new tests) + this progress doc. NO
                          live-tree / umbrella / production-path writes; the 44
                          already-leaked files are left for a separate
                          operator-gated cleanup.
TESTS:     `pytest -q` full model suite: 1576 passed, 1 skipped, 0 failed
           (the 1 skip = the orchestrator-monitor end-to-end test, importorskip
           since the orchestrator is intentionally off the model pythonpath).
           Guard test proving no prod write:
           `test_cli_receipt_write_never_touches_the_prod_receipts_dir`
           (monkeypatches `RECEIPTS_DIR` to a non-existent tmp stand-in, runs a
           full rc-0 CLI, asserts that dir is STILL absent while the injected
           dir holds exactly the one emitted receipt).

NEXT:      re-request codex review; do NOT self-merge. After merge + pin sync,
           the operator's separate cleanup can safely delete the 44 leaked
           `*__out*.json` (all `cutoff:null`, tmp `lane`) from the live dir.
