# Progress: v1-vs-v2 PIT fundamentals A/B prereg (frozen)   (PR #107)

STATUS:   prereg FROZEN, amended three times. AMENDMENT 1/2 are in the research
          doc; AMENDMENT 2c is added here.

          Correction to an earlier version of this line, which said "no arm
          computed. This revision carries no result." The research doc DOES
          contain a STAGE A RESULT section. It is now explicitly SUPERSEDED
          AND VOID, retained for audit only, on three independent grounds:
            1. it used the +60d synthetic `B_v1_lag` that Amendment 2a
               RETIRED and replaced with v2's real per-fact `filed` date, so
               the arms do not implement the current design;
            2. it reads its verdict against `|t| >= 3.24`, which Amendment 2b
               superseded upward to `3.29` after counting the gate contrast
               into the multiplicity family;
            3. it applied a `max |t| <= 2.0` placebo bar that did NOT exist in
               the frozen text when the arms ran — an unregistered decision
               rule that decided a VOID which fed the Stage-B gate check.

          AMENDMENT 2c (this push) closes (3) for the future by registering
          the placebo rule NUMERICALLY before the re-execution Amendment 2a
          forces: a control cell is CLEAN iff max |t| over the registered
          placebo seeds < 2.0, on the same statistic, aggregation unit and
          common support as the real arms. Deliberately NOT family-corrected —
          a control bar must be EASY to fail, since its job is to catch
          contamination; widening it would make a broken control harder to
          detect. Registered now, so it governs only the re-execution and does
          not retroactively legitimise the void numbers.

          NET: the Stage-B gate is UNDETERMINED, not closed. No capability
          claim in either direction is licensed. Unaffected and still standing:
          v2 is preferred on CORRECTNESS grounds, registered in advance by SS5.

WHAT:     Adds `doc/research/2026-07-30-v1-v2-pit-ab-prereg.md`, freezing a
          two-stage design that decomposes "v2 (as-filed PIT fundamentals) vs
          v1 (shipped `sec_fundamentals_daily`)" into its two entangled causes
          before any comparison is run. v1 and v2 differ simultaneously in
          availability stamp, look-ahead, universe size, and feature count, so
          a naive two-arm A/B would be uninterpretable. A third arm,
          `B_v1_lag`, isolates the two contributions: `B_v1 - B_v1_lag` reads
          off the look-ahead contribution alone, `B_v1_lag - B_v2` the
          value/source contribution alone. AMENDMENT 1 split the estimand per
          feature (no combination rule, 18 arm-tests). AMENDMENT 2 (review
          fix) redefined `B_v1_lag`'s stamp from an estimated +60d constant to
          v2's own real `filed` date per fact — the +60d p95 was not actually
          conservative for the full corpus — and made the Stage B gate
          contrast confirmatory (counted in the family, primary estimand E1,
          E2 sign-corroboration required) instead of descriptive. Stage B
          (the expensive model-level retrain) is gated on at least one
          feature's `B_v1_lag - B_v2` (E1) resolving at `|t| >= 3.29` with
          clean placebos and E2 sign-agreement — it is not licensed to run by
          this document alone.

WHY/DIR:  Registers the look-ahead in v1's `sec_fundamentals_daily` (measured
          this session: 90.37% of rows use fiscal-period-end + fixed 45d
          instead of `filed`; 77.6% of 10-Ks exceed 45d) as an explicit ARM to
          be quantified, not as noise to average away — so the eventual
          "is v2 worth shipping" verdict cannot silently launder the
          contamination into "v2 wasn't measurably better."

EVIDENCE: artifact:      no committed script; the 90.37% / 77.6% / 515 / 100
                         figures were measured ad hoc, interactively, against
                         the shipped `sec_fundamentals_daily` parquet (v1) and
                         `data/edgar_pit/` (v2 — itself flagged UNVERIFIED in
                         this doc's own §7) in this session. The companion
                         `renquant-base-data` PR #57 independently re-measured
                         and committed the v1-side 90.37%/77.6% figures (its
                         own `[VERIFIED-now]`-tagged evidence block), which
                         corroborates but does not replace this artifact gap.
                         `tools/v1_v2_pit_ab_run.py` (uncommitted, this
                         worktree) is the Stage-A runner that will recompute
                         all figures mechanically once it executes.
          prod or exp:   experiment — a research-only design comparison; v2's
                         own provenance is independently flagged UNVERIFIED
                         (§7), so nothing here is a production claim.
          existing data: no prior committed audit of v1's 45d-fallback
                         coverage or v2's PIT-violation count existed before
                         this session, other than the now-committed base-data
                         #57 evidence block for the v1 side.
          best-known?:   yes — first and only measurement taken for the v2
                         side and for the joint (515-name, 3-feature) common
                         support; the v1 side is now corroborated by #57.
          scope:         this is a design-freeze prereg for renquant-model,
                         experiment-only, no arm computed, no model/data
                         performance claim; the design-input figures above are
                         ad hoc and not yet reproducible from a committed
                         script for the v2/common-support side — re-verify via
                         `tools/v1_v2_pit_ab_run.py` before trusting them
                         further.

NEXT:     Execute Stage A (`B_v1`, `B_v1_lag`, `B_v2`, common 515-name /
          3-feature support, 18 arm-tests + 6 counted gate-tests + 2
          descriptive contrasts, per AMENDMENT 1/2) against the frozen
          design. Report a separate results PR against these immutable
          inputs. Stage B (model-level retrain) is registered separately and
          only if Stage A resolves the AMENDMENT 2 gate rule.
