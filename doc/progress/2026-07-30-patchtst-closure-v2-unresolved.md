# PatchTST closure v2 — executed, UNRESOLVED (underpowered) per §7.1

STATUS:    done — UNRESOLVED (underpowered); adversarial review returned and is
           appended verbatim with my disposition (ACCEPTED IN FULL)
WHAT:      Executed the FROZEN prereg
           doc/research/2026-07-30-patchtst-closure-prereg-v2.md (model#113)
           literally, in order. All three §0 abort gates PASS. §0.1's digest
           assertion disqualifies the 43-fold walk-forward research corpus every
           prior attempt on this line used (0 of 43 checkpoint sha256 match the
           live served digest 07046963...c07571) and admits only the
           digest-verified live score dates — which number 2. MEASURED on that
           series: N_eval = 0, n_blocks = 0, dropped = 0. n_blocks < 6, so §7's
           pre-committed clause 1 fires: UNRESOLVED (underpowered). No T_crit,
           no treatment t, no control and no §6 gate is computable, and none was
           fabricated. Third non-resolution of this question.
WHY/DIR:   Two prior verdicts on this question were retracted, both for
           deviating from frozen text. This attempt's first draft did it again
           in a subtler way: I reported VOID (identity) by folding a span
           requirement into §0.1, which contains no span clause. The
           commissioned adversarial review caught it, showed §0.1 was actually
           SATISFIED, and pointed at §7.1 as the pre-committed rule that
           applies. It also named the framing as mildly self-serving, since VOID
           reads as a clean plumbing finding while UNRESOLVED logs a third
           failure to resolve. I accepted in full and re-disposed. The
           withhold-pending-review discipline is the only thing that has worked
           on this question, and it worked again.
EVIDENCE:  doc/research/2026-07-30-patchtst-closure-v2-unresolved.md (full
           walkthrough + review verbatim + disposition);
           doc/research/data/2026-07-30-patchtst-closure-v2/ (sealed bundle,
           root_digest acf3d3ace40f43a61e11b21feae255d981c7b5422179fe1e6b5d8f9189371c06,
           7 files, 17523 bytes — VERIFY OK, and independently recomputed
           without corpus_index.py; supersedes the 5-file root 9b0ab79e...1d47cb
           per the §0.2 re-index disclosure in the results doc);
           tools/patchtst_closure_v2_identity_check.py (§0.1 evidence);
           tools/patchtst_closure_v2_power_measure.py (§3/§7 measurement);
           tools/patchtst_closure_v2_lib.py +
           tests/test_patchtst_closure_v2_selfchecks.py (§0.3, 16/16 passed —
           12 original + 4 permutation regression tests added on review).
           Full suite: origin/main baseline (clean worktree) 1031 passed /
           2 skipped; this branch 1047 passed / 2 skipped (+16 = the new
           self-check tests; no regressions).
NEXT:      §7.1's own prescribed deliverable is "what would raise n_blocks".
           Three routes, in the results doc: (a) let shadow_scorer_health.jsonl
           accumulate ~420 contiguous scored trading days behind a stable
           checkpoint (~20 months — the honest cost of the registered lag);
           (b) re-score history with the ACTUAL served checkpoint, which is
           static and digest-known — the only route to a powered answer on a
           useful timescale, and it needs its own walk-forward-honest prereg
           because the served checkpoint's effective_train_cutoff_date is
           2024-11-13; (c) close the plumbing gap (model_content_sha256 is
           stamped on only 2 of 17 hf_patchtst score dates; trained_date is
           absent from the health-record schema). Do NOT substitute the WF
           research corpus as a proxy — that is the #569 error class §0.1
           exists to forbid. Separately and NOT contingent on this verdict
           (§8): RenQuant#546 (a stale PatchTST can become primary => sell-only
           book) is a safety defect that must be fixed regardless.
