# Conditional-activation design proposal — the MoE condition axis

STATUS:    design proposal; no run. NOT a frozen prereg (review r3): the
           prereg freeze is the follow-up harness PR that commits the
           design doc's §5 executable analysis surface; nothing executes
           and no verdict of any kind may be recorded before that PR
           merges. Operator-directed 2026-08-10.

WHAT:      doc/design/2026-08-10-xgb-mom-conditional-activation-prereg.md
           — one activation variable (t−1 cross-sectional dispersion of
           the corpus's ROC20 column vs its 252d median; prices only,
           sidestepping the orch#930 regime-causality wall), in a hard
           two-stage structure: Stage E (the seen v2 folds) is
           hypothesis-refinement diagnostics with NO verdict authority;
           Stage C (corpus-extension window, entry dates ≥ 2026-05-08,
           unseen by every v2 training set and by the hypothesis) is the
           only confirmatory surface — per-day IC contrast,
           block-bootstrap CIs, a Stage-C-computable
           mechanism-not-calendar coverage guard (the historical 5-of-8
           fold check is demoted to a Stage-E diagnostic), a within-A
           placebo, and fail-closed n≥100 guards. §5 enumerates the
           freeze surface the harness PR must commit (extension scoring
           plan pinned to the fold-8 configuration with no refit,
           prediction artifact schema + hashes, timestamp/universe/
           missing-data rules, median warm-up, bootstrap RNG + algorithm
           as code, synthetic controls, fail-closed verdict machinery).

WHY/DIR:   model#214's admissible table shows real, recency-concentrated
           signal; the operator names this the MoE they want. The honest
           next step is TESTING whether an observable condition
           identifies the state — not assuming it. Sector stays in the
           L2-S successor line; one axis per experiment.

EVIDENCE:  artifact:      design doc; Stage E consumes model#213 frozen
                          artifacts verbatim; Stage C requires extension
                          predictions the harness PR must generate — the
                          v2 result artifacts are aggregate-only and
                          carry no daily predictions
           prod or exp:   experiment; corpus read-only
           existing data: model#214's committed result + the v2 harness
           best-known?:   yes — the mechanism-not-calendar guard exists
                          precisely to stop "activation = relabeled good
                          years"; the regime-label trap is named and
                          avoided
           scope:         Stage-C PASS → L2 weight-rule DESIGN only,
                          behind #931/#937 and review; KILL completes
                          the line.

TESTS:     none in this PR — docs only, and the doc claims no verdict
           authority; the harness PR commits the executable gate
           arithmetic, verifier, and synthetic controls BEFORE any run
           (the model#213 pattern).

NEXT:      harness-freeze PR (the §5 surface — the actual prereg) →
           Stage E diagnostics (no verdict authority) → Stage C
           confirmatory verdict emitted deterministically on the first
           date the frozen guards are met (~November 2026 by calendar
           arithmetic); earlier looks prohibited, fail-closed.
