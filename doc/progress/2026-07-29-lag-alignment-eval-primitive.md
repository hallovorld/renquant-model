# Progress: lag-alignment evaluation primitive

STATUS:   delivered (module + 13 tests). Makes the 2026-07-28/29 harness defect
          unrepresentable rather than merely documented.
          Fix (codex): (1) date-only alignment did not guarantee a common
          `(date, ticker)` sample in an unbalanced panel — added
          `common_panel_members` to close that gap, 3 new tests. (2) the
          evidence citation pointed only at local scratch space, not
          independently inspectable by a reviewer — the derived-statistics
          output (not the multi-GB corpus, which stays quarantined per its
          own prereg) is now committed at
          `doc/research/evidence/2026-07-29-lag-alignment-defect/`, with
          sha256 hashes recorded there.

WHAT:     Adds `src/renquant_model_common/lag_alignment.py` and its tests:
          `lag_evaluable_dates` / `align_lags` / `lagged_label_frame` /
          `common_panel_members`. Cross-lag comparisons must run on the
          INTERSECTION of every lag's evaluable score dates (`align_lags`)
          AND, since a cross-sectional panel is rarely balanced, the same
          `(date, ticker)` pairs (`common_panel_members`) — a shared date
          with a different constituent set per lag is not actually a shared
          cross-section. Rows without a lagged target are dropped rather
          than NaN-filled; an empty or under-sized intersection raises
          instead of returning a plausible-looking number; and the per-lag
          cost of reaching the common sample is reported, not hidden.

WHY/DIR:  A walk-forward study concluded "IC rises with label lag" across two models
          and a frozen follow-up returned CLOSE on that basis. Both were mostly a
          changing SAMPLE. The mechanism is a line that reads as obviously correct,
          `Y.shift(-lag)`, which nulls the NEWEST `lag` rows — so every longer lag
          silently drops the most recent dates. Documenting that in a retraction does
          not stop the next study from repeating it; a primitive that refuses the
          unsafe comparison does.

EVIDENCE: artifact:      `doc/research/evidence/2026-07-29-lag-alignment-defect/
          h9_fix.py` + `h9_results.json`, committed (sha256 in that dir's
          README) `[VERIFIED — direct read + hash, this session]` — holding
          the sample common moved lag-0 IC from +0.028 to +0.043 (PatchTST)
          and +0.069 to +0.100 (prod XGB); the PatchTST rise lost 60% of its
          size and the prod XGB profile REVERSED (z = -2.09), removing the
          two-model corroboration entirely. The second form of the same
          defect: an arm built from `scores[L:N]` compared against one from
          `scores[0:N-L)` carries an era term measured at 19-28% of the
          statistic.
           prod or exp:   code + a committed derived-statistics evidence
          snapshot; no production artifact touched.
           existing data: the 43-fold PatchTST WF corpus the evidence script
          reads from stays in quarantined local scratch per its own prereg's
          data-handling contract — not committed, not claimed reproducible
          from this PR alone; the committed evidence is the derived OUTPUT,
          not the corpus.
           best-known?:   n/a — utility module + evidence snapshot, no
          model/statistic ranking claim.
           scope:         "library code + a committed evidence artifact; no
          model claim is made, so the §4(b) sanity triad does not apply."
          Test suite 13/13 `[VERIFIED — pytest tests/test_lag_alignment.py,
          this session]`, including one test that reproduces the mechanism
          end-to-end: on synthetic data whose recent era carries no skill,
          the SAME lag-0 statistic differs by >0.15 between the full and the
          common sample; and 3 new tests for `common_panel_members`
          (unbalanced-panel membership drop, min_rows guard, empty-input
          guard).

NEXT:     Port the Stage-0 / closure harnesses onto this primitive (including
          `common_panel_members`, not just `align_lags`) before any of their
          numbers are quoted again, and re-derive the parked horizon prereg
          (model#88) from a corrected measurement rather than the withdrawn
          profile.
