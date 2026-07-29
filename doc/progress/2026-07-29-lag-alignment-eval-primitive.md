# Progress: lag-alignment evaluation primitive

STATUS:   delivered (module + 24 tests). Makes the 2026-07-28/29 harness defect
          unrepresentable rather than merely documented.
          Fix (codex round 1): (1) date-only alignment did not guarantee a
          common `(date, ticker)` sample in an unbalanced panel — added
          `align_lag_pairs` / `lag_evaluable_pairs` / `PairAlignment`, the
          recommended primitive for any real (unbalanced) panel; a balanced
          panel provably reduces to the date-only `align_lags` result. (2)
          the module's justification cited session-local scratch numbers a
          reviewer cannot inspect — removed; the mechanism is explained
          without them and the committed, runnable test suite is the
          evidence instead.
          Consolidation note: an earlier commit on this branch added a
          different, redundant function (`common_panel_members`) solving
          the same (date, ticker)-membership problem as a post-hoc filter
          over pre-built per-lag frames. Removed it in favor of
          `align_lag_pairs`, which computes the same guarantee directly and
          is the one the docstring now recommends — one API per guarantee,
          not two.

WHAT:     Adds `src/renquant_model_common/lag_alignment.py` and its tests:
          `lag_evaluable_dates` / `align_lags` / `lagged_label_frame` (the
          date-only primitives, correct for a balanced panel) and
          `lag_evaluable_pairs` / `align_lag_pairs` / `PairAlignment` (the
          `(date, ticker)`-pair primitives — prefer these for any real
          panel). Cross-lag comparisons must run on the SAME `(date,
          ticker)` pairs at every lag, not merely the same dates — a shared
          date with a different constituent set per lag is not actually a
          shared cross-section. Rows without a lagged target are dropped
          rather than NaN-filled; an empty or under-sized intersection
          raises instead of returning a plausible-looking number; and the
          per-lag cost of reaching the common sample is reported, not
          hidden.

WHY/DIR:  A walk-forward study concluded "IC rises with label lag" across two models
          and a frozen follow-up returned CLOSE on that basis. Both were mostly a
          changing SAMPLE. The mechanism is a line that reads as obviously correct,
          `Y.shift(-lag)`, which nulls the NEWEST `lag` rows — so every longer lag
          silently drops the most recent dates. Documenting that in a retraction does
          not stop the next study from repeating it; a primitive that refuses the
          unsafe comparison does.

EVIDENCE: artifact:      `src/renquant_model_common/lag_alignment.py` +
          `tests/test_lag_alignment.py` `[VERIFIED - this PR's diff]`. The
          module's justification does NOT rest on session-local scratch
          numbers a reviewer cannot inspect (codex round-1 HIGH) - the
          committed, runnable test suite is the evidence instead.
           prod or exp:   experiment/code-only - a library primitive plus
          synthetic-data tests; no production artifact, model, or claim.
           existing data: none cited as motivation beyond the mechanism
          itself (`Y.shift(-lag)` nulls the newest rows by construction,
          verifiable by reading the function).
           best-known?:   n/a - utility module, no model/statistic ranking.
           scope:         "library code + synthetic-data tests only; no
          model claim is made, so the §4(b) sanity triad does not apply to
          this PR. `test_the_lag0_statistic_itself_moves_between_full_and_
          common_samples` demonstrates the mechanism on generated data with
          a designed effect, not a real-study replay."
          Suite: 24/24 `[VERIFIED - PYTHONPATH=src pytest
          tests/test_lag_alignment.py, this session]`, including one test
          that reproduces the mechanism end-to-end on synthetic data - with
          a recent era carrying no skill, the SAME lag-0 statistic differs
          by >0.15 between the full and the common sample - six that pin
          the unbalanced-panel case (a delisted key is dropped exactly
          where its lagged row is missing; a date-only rule would have
          compared pairs across lags that the pair rule excludes; a
          balanced panel reduces to the date-only special case), and the
          dependence-aware-inference tests added afterward (moving-block
          bootstrap + leave-one-block-out agreement, not a bare block-t on
          8-12 blocks).

NEXT:     Port the Stage-0 / closure harnesses onto `align_lag_pairs` (not the
          date-only `align_lags`) before any of their numbers are quoted again,
          and re-derive the parked horizon prereg (model#88) from a corrected
          measurement rather than the withdrawn profile.
