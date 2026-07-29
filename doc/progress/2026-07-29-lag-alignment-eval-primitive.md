# Progress: lag-alignment evaluation primitive

STATUS:   delivered (module + 10 tests). Makes the 2026-07-28/29 harness defect
          unrepresentable rather than merely documented.

WHAT:     Adds `src/renquant_model_common/lag_alignment.py` and its tests:
          `lag_evaluable_dates` / `align_lags` / `lagged_label_frame`. Cross-lag
          comparisons must run on the INTERSECTION of every lag's evaluable score
          dates; rows without a lagged target are dropped rather than NaN-filled;
          an empty or under-sized intersection raises instead of returning a
          plausible-looking number; and the per-lag cost of reaching the common
          sample is reported, not hidden.

WHY/DIR:  A walk-forward study concluded "IC rises with label lag" across two models
          and a frozen follow-up returned CLOSE on that basis. Both were mostly a
          changing SAMPLE. The mechanism is a line that reads as obviously correct,
          `Y.shift(-lag)`, which nulls the NEWEST `lag` rows — so every longer lag
          silently drops the most recent dates. Documenting that in a retraction does
          not stop the next study from repeating it; a primitive that refuses the
          unsafe comparison does.

EVIDENCE: `[VERIFIED — bughunt/h9_fix.py, recomputed on a common score-date set]`
          holding the sample common moved lag-0 IC from +0.028 to +0.043 (PatchTST)
          and +0.069 to +0.100 (prod XGB); the PatchTST rise lost 60% of its size and
          the prod XGB profile REVERSED (z = -2.09), removing the two-model
          corroboration entirely. The second form of the same defect: an arm built
          from `scores[L:N]` compared against one from `scores[0:N-L)` carries an era
          term measured at 19-28% of the statistic. Test suite 10/10
          `[VERIFIED — pytest tests/test_lag_alignment.py]`, including one test that
          reproduces the mechanism end-to-end: on synthetic data whose recent era
          carries no skill, the SAME lag-0 statistic differs by >0.15 between the full
          and the common sample. No model claim is made here, so the §4(b) triad does
          not apply.

NEXT:     Port the Stage-0 / closure harnesses onto this primitive before any of their
          numbers are quoted again, and re-derive the parked horizon prereg (model#88)
          from a corrected measurement rather than the withdrawn profile.
