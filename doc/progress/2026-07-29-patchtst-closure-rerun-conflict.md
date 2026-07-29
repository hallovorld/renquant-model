# Progress: closure re-run conflicts with the audit — recorded, not resolved

STATUS:   NO VERDICT. Two sample-stable constructions of the same frozen test
          disagree; the conflict is recorded and the reconciliation is the next step.

WHAT:     Adds `doc/research/2026-07-29-patchtst-closure-rerun-conflict.md`: the
          re-run of model#87's frozen rule under the corrected primitive, its numbers,
          the direct conflict with the bug hunt's recomputation, three candidate causes,
          and an explicit refusal to declare a verdict.

WHY/DIR:  model#87's rule is frozen and merged; only its instrument was defective. A
          re-run is legitimate. Publishing its answer while a second sample-stable
          computation says the opposite is not.

EVIDENCE: this run `[VERIFIED - recomputed 2026-07-29 over bundle f6b6ef6d.../wf-eval]`:
          PatchTST negative at all four lags (block t -1.01, -1.39, -1.53, -1.88) =>
          p = 4/4; prod XGB control positive at all four (+1.30, +1.36, +1.76, +1.71)
          => VALID. Mechanically CLOSE. The bug hunt's recomputation of the ORIGINAL
          arms on a common score-date set reported p = 0/4 with the control at 1/4
          (INVALID) => INCONCLUSIVE, and that is what retracted the first CLOSE.
          Leading suspect for the divergence, stated against my own result: this run
          aligned on DATES only, while `align_lag_pairs` - written two rounds ago for
          exactly the unbalanced-panel hazard - was not used.

NEXT:     Re-run both constructions under `align_lag_pairs` with the implementations
          diffed line by line, and let the frozen rule decide once they agree. If they
          still disagree, neither may be quoted. PatchTST stays UNRESOLVED.
