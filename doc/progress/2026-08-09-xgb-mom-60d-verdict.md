# xgb_mom_60d executed once — NO ADMISSIBLE VERDICT (re-scoped r1)

STATUS:    completed execution, inadmissible against its own prereg;
           re-scoped to exploratory diagnostics on review r1. No verdict
           is recorded against model#211's §3 gate.

WHAT:      doc/research/2026-08-09-xgb-mom-60d-verdict.md + committed
           artifacts (harness, raw result JSON, both pre-run control
           JSONs, verifier). The KILL recorded by the first push is
           withdrawn in a visible corrections section: the folds carry
           no purge/embargo for the 60-trading-day label (train labels
           overlap every test window), the corpus sha was not checked at
           execution, and the feature list came from a mutable
           scratchpad. Raw arithmetic retained with the inadmissibility
           reasons stated beside it; no fold-pattern inference drawn.

WHY/DIR:   Phase-2 step 5 of the operator's re-planning. The honest
           status of the momentum-learner question is UNANSWERED at
           admissible standards; answering it requires a NEW dated
           prereg with execution-enforced corpus/features and an
           embargo ≥ the realized 60d label horizon before every fold.

EVIDENCE:  artifact:      2026-08-09-xgbmom-result.json — raw per-fold
                          output, aggregate-only, contaminated by the
                          train-label overlap [VERIFIED — verifier
                          rechecks its internal arithmetic, exit 0; it
                          cannot establish corpus/feature/fold
                          provenance, which is reason 4 of the
                          inadmissibility]. Controls: positive PASS
                          (+0.3715 planted), null KILL (−0.0027),
                          reproduced under the r1-hardened harness.
           prod or exp:   experiment; corpus read-only; nothing served
           existing data: the frozen WF corpus only
           best-known?:   n/a — no admissible measurement of this
                          hypothesis exists; this artifact is a data
                          point, not a conclusion
           scope:         no arm enters the system; deployment blocked;
                          #211's gate remains unexecuted in the
                          admissible sense.

TESTS:     data/2026-08-09-xgbmom-verify.py exit 0 [VERIFIED — run r1];
           both synthetic controls rerun under the hardened harness
           reproduce the committed control JSONs [VERIFIED — run r1].

NEXT:      Phase-2 ⑥ (freshness checker full-window) and Phase-3 items;
           any momentum-learner retry starts from a NEW dated prereg
           with embargoed folds — nothing is scheduled.
