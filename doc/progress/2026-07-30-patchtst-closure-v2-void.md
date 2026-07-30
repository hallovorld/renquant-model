# PatchTST closure v2 — executed, VOID (identity) at §0.1

STATUS:    done — VOID (identity), pending adversarial review before merge
WHAT:      Executed the FROZEN prereg
           doc/research/2026-07-30-patchtst-closure-prereg-v2.md (model#113)
           literally. §0.1 (artifact identity, established by execution) fails
           before any statistic is computed: the live shadow path's served
           PatchTST checkpoint (sha256 07046963…c07571, confirmed via
           shadow_scorer_health.jsonl + an independent re-hash) does not match
           ANY of the 43 checkpoints in the only span-adequate historical score
           corpus available (the walk-forward research corpus this line's prior
           attempts used), and the only genuinely digest-verified live score
           history is 2 trading days long — nowhere near the ~120+ admissible
           trading days the frozen §3 estimator needs at L=60. Disposition per
           §0/§5: VOID (identity). No d(t), block t, T_crit, control, or §6 gate
           was computed. Built and unit-tested (§0.3) the frozen §1/§3/§3.5/§4/§6
           estimator anyway, for reuse once the identity gap closes; it is NOT
           wired to run against the disqualified corpus (no CLI entry point,
           loud docstring warning).
WHY/DIR:   This is the THIRD attempt at this question (model#87 retracted,
           07-29 second CLOSE withheld-then-destroyed by review, this one
           VOIDed at the gate specifically designed after the #569 mistrace
           precedent to catch exactly this failure mode). The gate did its job:
           it caught a mismatch that would otherwise have produced a plausible-
           looking but meaningless number. GOAL-4's PatchTST sub-question
           remains open; #546 (fallback-config sell-only hazard) is explicitly
           NOT contingent on this study per §8 and stays unresolved either way.
EVIDENCE:  doc/research/2026-07-30-patchtst-closure-v2-void.md (full §0.1
           walkthrough); doc/research/data/2026-07-30-patchtst-closure-v2/
           (sealed bundle, root_digest 9b0ab79e6b1b0bea3a7ddbcb42391b2026b8c226ce70ac1dddb3ff151b1d47cb,
           5 files); tools/patchtst_closure_v2_identity_check.py (reproducible
           identity scan); tools/patchtst_closure_v2_lib.py +
           tests/test_patchtst_closure_v2_selfchecks.py (12/12 passed, estimator
           self-checks against synthetic data only). Full suite:
           origin/main baseline (clean worktree) 1031 passed / 2 skipped; this
           branch 1043 passed / 2 skipped (+12 = the new self-check tests, no
           regressions).
NEXT:      Identity-plumbing fix (out of this PR's scope): either (a) let
           shadow_scorer_health.jsonl (or an equivalent execution-identity log)
           accumulate ~6 months of history behind the currently-serving
           checkpoint before re-attempting at L=60, or (b) backfill/maintain a
           runs.alpaca_shadow.db-style digest-stamped score history
           continuously from now. Do NOT substitute the WF research corpus as
           a "close enough" proxy — that is the exact error class §0.1 exists
           to forbid. #546 (fallback hazard) should be tracked and fixed
           independently of this study's disposition.
