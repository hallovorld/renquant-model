# Momentum TRAIN CLI `--params-version` — one CLI, two frozen clocks (model#199 item 2, model half)

**Date:** 2026-08-03 · `renquant-model` · GOAL-8 fast arm

STATUS:    CLI selection surface only; NO job change here (the weekly wrapper's
           second invocation is the orchestrator half of #199 item 2, its own
           PR in its own repo), NO serving change, nothing installed.
WHAT:      `tools/momentum_train_run.py --params-version {v0,v1_fast}`
           (default v0 — every existing invocation byte-identical in
           behavior). Selection dict `PARAMS_BY_VERSION` maps to the frozen
           accessors (`params_v0` / `params_v1_fast`, #200); the selected
           params flow to `train_momentum_artifact` and the dry-run plan.
           The dated-artifact basename stays `momentum_residual_v0.json` in
           BOTH lanes: the pipeline serving loader hardcodes exactly that
           basename (`momentum_residual_scorer.MOMENTUM_DATED_ARTIFACT_BASENAME`
           `[VERIFIED — read in renquant-pipeline this session]`), so a
           version-derived name would publish artifacts the current loader
           can never serve (`dated_artifact_missing` daily). Basename is a
           path convention, not an identity claim — identity is the
           artifact's kind/params_version/content_sha256, cross-checked
           against the ledger row by the loader. Pipeline follow-up (NOT in
           this PR): derive the basename from the ledger row, then version it.
WHY:       #199 build order item 2: the weekly Saturday job produces BOTH
           artifacts, v0 then v1_fast, each into its own ledger. The CLI is
           the tool that job runs, and it could only train v0.
TESTS:     5 new in `tests/test_momentum_train_package.py`: default-is-v0;
           flag selects 63/5; unknown version = argparse exit 2 (never falls
           back to v0); real-train path stamps kind `momentum_residual_v1_fast`
           + ledger row `params_version=v1_fast` under the SHARED basename;
           two out-roots = two independent single-row ledgers (fast genesis
           row has `prev_row_sha: null`, never chained onto the slow ledger).

EVIDENCE:

```
tests:  1533 passed / 0 failed, full suite, this worktree.  [VERIFIED — this session]
scope:  "one tool + its tests + this doc; no src/ package change, no job,
         no serving change; nothing produces a fast artifact until the
         orchestrator wrapper PR lands AND the run surface syncs."
```

## Revert

git revert; the flag is additive and default-preserving — the pinned weekly
job's existing invocation does not name it.
