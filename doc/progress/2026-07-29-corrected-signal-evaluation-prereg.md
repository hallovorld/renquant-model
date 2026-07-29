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

EVIDENCE: the defect and its measured size `[VERIFIED - bughunt/h9_fix.py]`: holding
          the sample common moved lag-0 IC from +0.028 to +0.043 (PatchTST) and +0.069
          to +0.100 (prod XGB); the PatchTST rise lost 60% and the prod XGB profile
          reversed (z = -2.09). The second form: closure's REAL arm read scores[L:N]
          against PERSIST's scores[0:N-L), an era term worth 19-28% of the statistic.
          Both are now checklist rows T11/T12 with the primitive enforcing them. No
          model claim is made by this PR, so the §4(b) triad applies to the results
          doc.

NEXT:     Run it on the corrected primitive. The prod XGB doubles as the positive
          control: if it lands UNRESOLVED, every verdict becomes UNRESOLVED, because
          a design that cannot detect the model that trades cannot speak about the
          others.
