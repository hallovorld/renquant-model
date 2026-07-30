# Progress: v1-vs-v2 PIT fundamentals A/B prereg (frozen)   (PR #107)

STATUS:   prereg FROZEN, no arm computed. This revision carries no result.

WHAT:     Adds `doc/research/2026-07-30-v1-v2-pit-ab-prereg.md`, freezing a
          two-stage design that decomposes "v2 (as-filed PIT fundamentals) vs
          v1 (shipped `sec_fundamentals_daily`)" into its two entangled causes
          before any comparison is run. v1 and v2 differ simultaneously in
          availability stamp, look-ahead, universe size, and feature count, so
          a naive two-arm A/B would be uninterpretable. A third arm,
          `B_v1_lag` (v1's values, re-stamped to fiscal-period-end + 60d), is
          registered so the look-ahead contribution (`B_v1 - B_v1_lag`) and the
          value/source contribution (`B_v1_lag - B_v2`) can each be read off
          independently. Stage B (the expensive model-level retrain) is gated
          on Stage A resolving `B_v1_lag - B_v2` at `|t| >= 3.16` with clean
          placebos — it is not licensed to run by this document alone.

WHY/DIR:  Registers the look-ahead in v1's `sec_fundamentals_daily` (measured
          this session: 90.37% of rows use fiscal-period-end + fixed 45d
          instead of `filed`; 77.6% of 10-Ks exceed 45d) as an explicit ARM to
          be quantified, not as noise to average away — so the eventual
          "is v2 worth shipping" verdict cannot silently launder the
          contamination into "v2 wasn't measurably better."

EVIDENCE: n/a — this PR registers a prereg design only, before any arm is
          computed. No model/data performance claim is made in this
          revision, so the §4(b) evidence block applies to the future
          results doc once Stage A is executed, not to this PR.

NEXT:     Execute Stage A (`B_v1`, `B_v1_lag`, `B_v2`, common 515-name /
          3-feature support, 6 tests + 2 descriptive contrasts) against the
          frozen design. Report a separate results PR against these immutable
          inputs. Stage B (model-level retrain) is registered separately and
          only if Stage A resolves `B_v1_lag - B_v2` at the frozen threshold.
