# xgb_mom_60d v2 executed as frozen — KILL (5/8 vs 6/8), admissible

STATUS:    completed outcome; one execution, zero deviations; the
           machine-surface verifier is green on the committed result.

WHAT:      doc/research/2026-08-10-xgb-mom-60d-v2-verdict.md + the result
           JSON committed beside the frozen harness/controls/verifier.
           Gate arithmetic KILL: mean real signal +0.0257 (leg 1 pass),
           5/8 folds positive vs the fixed 6/8 bar (leg 2 fail), A/A
           0.0007, recency strong (2025 +0.085, 2026 +0.091).
           admissible_verdict stays null pending review countersignature
           per the frozen protocol.

WHY/DIR:   The operator asked for their momentum model; this is its
           admissible verdict, one day after the v1 run was voided. The
           pre-run prediction is settled visibly in the record: direction
           right (KILL), magnitude wrong (clean signal HIGHER than the
           leaky diagnostic).

EVIDENCE:  artifact:      2026-08-09-xgbmom-v2-result.json [VERIFIED —
                          committed verifier exit 0: gate arithmetic,
                          feature sha, fold table, per-fold purge
                          entries/endpoints, corpus pin all enforced];
                          purge counts 0/fold [VERIFIED — per-row
                          machinery active; 91-day gaps clear every
                          endpoint]; controls green committed.
           prod or exp:   experiment; corpus read-only; nothing served
           existing data: the merged v2 prereg + its frozen artifacts
           best-known?:   yes — the conditional-activation follow-up is
                          named as a NEW prereg with its inherited
                          serving gates; nothing smuggled
           scope:         no arm enters; P0 sweep pre-publication clean
                          (only the unrelated #209).

TESTS:     committed verifier green on result + both controls.

NEXT:      review countersigns the verdict (or contests it); the
           conditional-activation prereg is drafted only on operator
           interest; the serving chain (#931/#937) remains the gate for
           ANY deployment.
