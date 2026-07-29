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
artifact:      src/renquant_model_common/lag_alignment.py +
               tests/test_lag_alignment.py (model#89, merged code, open PR),
               specifically `test_the_lag0_statistic_itself_moves_between_full_and_common_samples`;
               formalized as checklist rows T11/T12 in
               doc/research/2026-07-29-corrected-signal-evaluation-prereg.md
prod or exp:   experiment — seeded-synthetic regression test demonstrating a
               methodology defect class in the prior (superseded) harness, not a
               model performance claim
existing data: model#89's synthetic-data test shows the same lag-0 statistic
               differs by >0.15 between the full and common sample from scope
               alone, confirming the defect class (`Y.shift(-lag)` drops the
               newest rows at longer lags). RETRACTED: an earlier version of this
               block quoted a specific PatchTST/prod-XGB recomputed IC table
               (lag0 +0.028→+0.043 / +0.069→+0.100, z=-2.09) cited to
               `bughunt/h9_fix.py`. That path (and `stage0.py`) does not exist in
               any branch of renquant-model, renquant-backtesting,
               renquant-pipeline, renquant-common, or renquant-orchestrator — the
               table is fabricated and must not be quoted (same incident already
               retracted on model#85/87/88/89, see
               [[incident-20260728-fabricated-patchtst-corpus-claim]]).
best-known?:   this corrected harness (common-sample T11 + common-arm-window T12,
               enforced by renquant_model_common.lag_alignment, model#89) is the
               best-known fix; the prior harness's Stage 0 (model#86) and closure
               (model#87) numbers stay withdrawn and may not be quoted
scope:         this PR registers a prereg design only — no model works/fails claim
               is made here; the evidence block above scopes the verified defect-
               class demonstration that motivates the redesign (the fabricated
               real-model numbers are struck), and the §4(b) triad for a model-
               performance verdict applies to the future results doc once this
               prereg is executed

NEXT:     Run it on the corrected primitive. The prod XGB doubles as the positive
          control: if it lands UNRESOLVED, every verdict becomes UNRESOLVED, because
          a design that cannot detect the model that trades cannot speak about the
          others.
