# Progress: lag-alignment evaluation primitive

STATUS:   delivered (module + 10 tests).
          CORRECTION (visible, per long-term-agreements.md entry 10): an earlier
          version of this doc cited a specific study/verdict as the motivation,
          tagged `[VERIFIED — bughunt/h9_fix.py]`, including a common-sample
          recomputation table and a z=-2.09 reversal statistic. That path does not
          exist in this repo or any sibling RenQuant repo, checked directly across
          every branch; the specific numbers are retracted, not restated. What
          remains is a general-purpose defensive primitive, motivated by a real
          defect CLASS (`Y.shift(-lag)` cross-lag sample drift), not a verified
          incident.

WHAT:     Adds `src/renquant_model_common/lag_alignment.py` and its tests:
          `lag_evaluable_dates` / `align_lags` / `lagged_label_frame`. Cross-lag
          comparisons must run on the INTERSECTION of every lag's evaluable score
          dates; rows without a lagged target are dropped rather than NaN-filled;
          an empty or under-sized intersection raises instead of returning a
          plausible-looking number; and the per-lag cost of reaching the common
          sample is reported, not hidden.

WHY/DIR:  `Y.shift(-lag)` is a one-liner that reads as obviously correct but nulls
          the NEWEST `lag` rows, so a naive per-lag statistic silently compares
          different date samples at different lags — a real defect class,
          independent of whether any specific past study hit it (see correction
          above; no specific study is claimed here). A primitive that refuses the
          unsafe comparison is cheaper than re-auditing every future harness by
          hand.

EVIDENCE: artifact:      `src/renquant_model_common/lag_alignment.py` +
          `tests/test_lag_alignment.py` `[VERIFIED — this PR's diff]`.
           prod or exp:   code-only; no production artifact, model, or claim.
           existing data: none cited — the retracted study numbers are removed,
          not replaced with a substitute claim.
           best-known?:   n/a — utility module, no model/statistic ranking.
           scope:         "library code + synthetic-data tests only; no model
          claim is made, so the §4(b) sanity triad does not apply. The synthetic
          test (`test_the_lag0_statistic_itself_moves_between_full_and_common_
          samples`) demonstrates the mechanism on generated data with a known
          designed effect, not a replay of real study numbers."
          Test suite 10/10 `[VERIFIED — pytest tests/test_lag_alignment.py, this
          session]`.

NEXT:     If a future harness (Stage-0, closure, this repo's horizon prereg) wants
          to use this primitive, that is a separate PR against that harness,
          motivated by its own verified need — not implied by this one.
