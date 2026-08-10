# Conditional-activation prereg — the MoE condition axis, frozen

STATUS:    design only; no run. Operator-directed 2026-08-10.

WHAT:      doc/design/2026-08-10-xgb-mom-conditional-activation-prereg.md
           — one frozen activation variable (t−1 cross-sectional
           dispersion vs its 252d median; prices only, sidestepping the
           orch#930 regime-causality wall), per-day IC contrast on the
           merged v2 artifacts' pooled OOS predictions, block-bootstrap
           CIs, four gates including mechanism-not-calendar and a
           within-A placebo, fail-closed n≥100 guards.

WHY/DIR:   model#214's admissible table shows real, recency-concentrated
           signal; the operator names this the MoE they want. The honest
           next step is TESTING whether an observable condition
           identifies the state — not assuming it. Sector stays in the
           L2-S successor line; one axis per experiment.

EVIDENCE:  artifact:      design doc; consumes model#213 frozen artifacts
                          verbatim (no retraining freedom)
           prod or exp:   experiment; corpus read-only
           existing data: model#214's committed result + the v2 harness
           best-known?:   yes — gate 3 exists precisely to stop
                          "activation = relabeled good years"; the
                          regime-label trap is named and avoided
           scope:         PASS → L2 weight-rule DESIGN only, behind
                          #931/#937 and review; KILL completes the line.

TESTS:     none — prose contract; the execution harness will carry its
           own synthetic controls per the house standard.

NEXT:      review + merge → harness + controls → one execution → verdict
           same day.
