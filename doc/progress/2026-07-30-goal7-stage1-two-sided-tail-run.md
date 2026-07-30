# GOAL-7 Stage 1 — executed: VOLATILITY-TILT (verdict WITHHELD pending adversarial review)

STATUS:    done (run executed, verdict WITHHELD per §8 until the appended adversarial
           review and its disposition are in the file); the evaluation window is now
           SPENT — §2 registered it as used ONCE
WHAT:      Executed the frozen prereg doc/research/2026-07-30-goal7-stage1-two-sided-tail-prereg.md
           (model#117) exactly as written, under AMENDMENT 4 — the sole authoritative
           partition (A4.6 makes both sections titled "AMENDMENT 3" non-executable).
           Nothing was designed: transform, estimand, estimator, partition, critical
           value, controls and decision rule were all fixed before the run.
           VERDICT: VOLATILITY-TILT. The raw two-sided arm u = |z_t(mom_12_1_tr)|
           clears (+0.2381 SD, |t| = 3.270 >= T_crit = 2.1098); orthogonalised per §4
           to |z_t(vol_60_tr)| it does not (+0.1161 SD, |t| = 1.644). §4 registers that
           as a KILL CONDITION, not a caveat, so the two-sided hypothesis is NOT
           supported whatever the raw arm says. NOTHING IS LICENSED — no Stage-2
           design, no scorer, no config/artifact/state/launchd change, no capital.
WHY/DIR:   §4 exists because a model's apparent edge on this programme has already been
           shown to be a volatility ranking (prod XGB +0.2534 SD reproduced by a single
           sort on STD20, collapsing to -0.0554 orthogonalised). |z| of momentum is
           large exactly where the cross-section is dispersed: corr(u, |z(vol_60_tr)|)
           = +0.4066 pooled here. Residualising removes 51% of the spread and half the
           t, leaving a statistic that a permutation of u beats 12.5% of the time.
           §7 predicted this outcome verbatim ("VOLATILITY-TILT is the outcome I expect
           to have to report if the raw arm looks good") and registered it as a distinct
           verdict so it could not be narrated away. It was not.
EVIDENCE:  doc/research/2026-07-30-goal7-stage1-two-sided-tail-results.md
           doc/research/data/2026-07-30-goal7-stage1-two-sided-tail/{results.json,run.log}
           tools/goal7_stage1_two_sided_run.py, tests/test_goal7_stage1_estimator.py
           - partition realised vs A4.4 pins: N_eval 1082/1082, n_blocks 18/18,
             dropped remainder 2/2 (2021-04-16, 2021-04-19), window 2016-12-29 ->
             2021-04-19, blocks span -> 2021-04-15, names/date min 126 median 128,
             0 dates lost to the <20-name rule, excluded band 120 dates / 16,226 rows
             -> ALL MATCH, no shortfall to attribute  [VERIFIED - run.log]
           - T_crit legs: P95_null 2.0960 (raw harness) / 2.0562 (residual harness),
             t_{0.975,17} = 2.1098 -> T_crit = 2.1098, bound by the STUDENT-T LEG in
             both harnesses  [VERIFIED - results.json T_crit]
           - arms (primary label): u raw +0.2381 SD |t| 3.270 CLEARS, null quantile
             0.990; u residualised +0.1161 SD |t| 1.644 FAILS, null quantile 0.875;
             reference z(mom) +0.2116 SD |t| 2.009 fails; positive control |t| 8.137
             clears  [VERIFIED - results.json arms.z]
           - controls: positive-control mean per-date Spearman IC +0.044347 (|dev|
             0.005653 <= 0.01, alpha NEVER re-calibrated); null false-pass 4.5% / 5.0%
             vs a 10% ceiling; non-tautology 100.0000% of dates changed; the within-date
             permutation is PROVEN to reject the known-broken unsorted-frame
             implementation on seeds 0-5  [VERIFIED - run.log]
           - inputs: matrix sha256 85c27fc1..., tr sha256 8c23496e..., raw-input pin
             corpus_fingerprint 48728e24... / config f52d096e... verified through
             verify_or_abort(), which refuses on a MISSING or MALFORMED manifest, not
             only a mismatching one  [VERIFIED - run.log]
           - label identity: the primary label is bit-for-bit model#110's fwd_120_tr on
             346,807 paired rows, max|diff| = 0.0  [VERIFIED - run.log]
           - suite: origin/main @6658078 = 1047 passed / 2 skipped; this branch = 1058
             passed / 2 skipped (+11 estimator tests)  [VERIFIED - make test, both trees]
           - verdict is IDENTICAL under both readings of §3's label wording (z-scored
             primary and raw-excess-return secondary, both run in full with their own
             nulls)  [VERIFIED - results.json arms.z / arms.raw]
NEXT:      1. Append the commissioned adversarial review + its disposition VERBATIM to
              §10 of the results doc; the verdict stays WITHHELD until then (§8).
           2. No Stage-2 work. GOAL-7 does not have a formulation that survives the
              volatility control on this window, and the window is spent.
           3. Carry forward, if GOAL-7 is re-pitched: §5.1's positive-control constant
              is mis-calibrated at finite cross-section width (the closed-form alpha
              inverts the ASYMPTOTIC Spearman-Pearson relation; the van-der-Waerden
              construction realises ~0.020 at n=31, ~0.043 at n=128, ~0.049 at n=512
              [VERIFIED - Monte-Carlo of the registered construction, this session]).
              It passed here with 0.0043 of margin because this corpus is 128 names
              wide. On a narrower panel the same correct code VOIDs the screen. Fix the
              constant in the NEXT registration, never in a running one.
           4. A re-test of the two-sided hypothesis needs dates OUTSIDE this corpus:
              2021-10-08 onward is burned (it is where the U-shape was observed) and
              2016-12-29 -> 2021-04-19 is now spent.
