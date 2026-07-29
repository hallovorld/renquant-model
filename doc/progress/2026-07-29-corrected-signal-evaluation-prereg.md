# Progress: corrected signal-evaluation prereg (frozen)

STATUS:   prereg FROZEN, run not executed. Supersedes the measurement portions of
          model#86 and model#87.

WHAT:     Adds `doc/research/2026-07-29-corrected-signal-evaluation-prereg.md`: three
          subjects (prod XGB, certified clf, PatchTST) under one design, on the
          142-name intersection, with every cross-lag and cross-arm comparison pinned
          to the common sample produced by `renquant_model_common.lag_alignment`
          (model#89). Three registered questions with conservative default branches.

WHY/DIR:  The prior harness computed cross-lag statistics on a drifting sample, so
          neither Stage 0's profile nor the closure verdict may be quoted. Re-running
          them under a corrected harness is a NEW test and needs its own registration
          rather than an amendment to a compromised one.

EVIDENCE:
artifact:      bughunt/h9_fix.py (ad hoc repro script, not committed), measuring
               cross-lag sample drift; formalized as checklist rows T11/T12 in
               doc/research/2026-07-29-corrected-signal-evaluation-prereg.md
prod or exp:   experiment — bug-hunt repro of a methodology defect in the prior
               (superseded) harness, not a model performance claim
existing data: prior drifting-sample harness reported lag-0 IC +0.028 (PatchTST) /
               +0.069 (prod XGB); holding the sample common instead measured +0.043
               (PatchTST) / +0.100 (prod XGB) — the PatchTST rise lost 60% of its
               apparent size and the prod XGB profile reversed sign (z = -2.09)
               `[VERIFIED - bughunt/h9_fix.py]`. Separately, the closure test's REAL
               arm read scores[L:N] against PERSIST's scores[0:N-L), an era term
               worth 19-28% of the statistic (T12).
best-known?:   this corrected harness (common-sample T11 + common-arm-window T12,
               enforced by renquant_model_common.lag_alignment, model#89) is the
               best-known fix; the prior harness's Stage 0 (model#86) and closure
               (model#87) numbers are withdrawn and may not be quoted
scope:         this PR registers a prereg design only — no model works/fails claim
               is made here; the evidence block above scopes the bug-measurement
               that motivates the redesign, and the §4(b) triad for a model-
               performance verdict applies to the future results doc once this
               prereg is executed

NEXT:     Run it on the corrected primitive. The prod XGB doubles as the positive
          control: if it lands UNRESOLVED, every verdict becomes UNRESOLVED, because
          a design that cannot detect the model that trades cannot speak about the
          others.
