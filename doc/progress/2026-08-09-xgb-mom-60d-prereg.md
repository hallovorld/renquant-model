# xgb_mom_60d prereg — the operator's momentum model, frozen

STATUS:    design only; no training run. Phase-2 step 5 of the operator's
           2026-08-09 re-planning, pulled forward (it does not depend on
           the corpus extension, orch#939).

WHAT:      doc/design/2026-08-09-xgb-mom-60d-prereg.md — an xgboost
           learner on an EXPLICIT 70-column price-momentum feature list
           (volume family excluded with reason), identical folds/params/
           seeds to the reviewed run_wf convention plus the 2026 fold,
           per-fold shuffle-floor placebo, four deterministic PASS/KILL
           legs, full-feature baseline recorded as context not gate.

WHY/DIR:   Terminology reconciliation revealed the operator's "momentum
           model" = a learned momentum panel, which does not exist in the
           system. This is it, behind the same discipline that killed and
           reclassified weaker work this week. Corpus hash pinned; every
           runner constant is in the doc (runner-guards-are-prereg-content).

EVIDENCE:  artifact:      corpus sha256 pinned [VERIFIED — hashed];
                          feature list resolved from the corpus columns
                          [VERIFIED — 70 matched, 10 volume excluded];
                          fold convention [VERIFIED — replay sidecar
                          fold_train_end 2025-12-31]
           prod or exp:   experiment; read-only corpus; nothing served
           existing data: the frozen WF corpus (726,128 rows)
           best-known?:   yes — PASS explicitly does NOT deploy: shadow
                          candidacy is additionally gated on #937/#939
           scope:         one execution post-merge, same day.

TESTS:     none — prose contract; zero live choices by construction.

NEXT:      merge → execute once (WF + shuffle ×3 seeds + baseline) →
           PASS/KILL published with committed CSV + verifier.
