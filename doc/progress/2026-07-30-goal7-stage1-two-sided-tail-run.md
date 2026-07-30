# GOAL-7 Stage 1 — executed, then WITHDRAWN: the registered inferential unit is invalid

STATUS:    done (run executed) — but the VERDICT IS WITHDRAWN. Round-2 adversarial
           review found the frozen estimator averages 60-day blocks while every label
           is a 120-day forward return, so adjacent block means share half of each
           label horizon and `df = 17` is not a valid inferential unit. Reclassified
           **UNRESOLVED — invalid inferential unit**; VOLATILITY-TILT is withdrawn and
           this run licenses NOTHING and may not be cited as a preregistered result.
           See CORRECTION 1 in the results doc.
           The evaluation window is still SPENT — §2 registered it as used ONCE, and a
           design defect does not un-spend it.
WHAT:      Executed the frozen prereg doc/research/2026-07-30-goal7-stage1-two-sided-tail-prereg.md
           (model#117) exactly as written, under AMENDMENT 4 — the sole authoritative
           partition (A4.6 makes both sections titled "AMENDMENT 3" non-executable).
           Nothing was designed: transform, estimand, estimator, partition, critical
           value, controls and decision rule were all fixed before the run.
           VERDICT AS RUN (**WITHDRAWN** — see STATUS and CORRECTION 1; retained
           here because what the run produced is still a fact worth recording, it
           just is not a preregistered result):
           VOLATILITY-TILT. The raw two-sided arm u = |z_t(mom_12_1_tr)|
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
           - §8 ADVERSARIAL REVIEW, appended VERBATIM at results §10, disposition
             §10.1: "NOT UPHELD as a challenge to the verdict — VOLATILITY-TILT stands."
           The reviewer re-implemented the estimand independently from the pinned
           parquets and reproduced every headline to six decimals. Two MATERIAL
           findings, both accepted, both now in the doc, and they cut opposite ways:
           - the KILL leg is STRONGER than the doc argued. The asymmetry test (which
             I then re-measured myself): z(vol_60_tr) alone pays +0.3477 SD t=+4.610,
             MORE than the two-sided arm, and volatility SURVIVES orthogonalisation
             to u (+0.2300, t=+2.597) while u does NOT survive orthogonalisation to
             volatility. Direction of explanation identified, not asserted.
           - the RAW leg is WEAKER than its 0.990 null quantile implies. u's per-date
             statistic has lag-1 autocorrelation 0.94; the REGISTERED null permutes
             within date and destroys that persistence, so it is anti-conservative.
             Under persistence-preserving nulls the raw arm's p is 0.044 / 0.24, not
             0.010. A defect in the registered DESIGN, not the execution. I did not
             swap the bar after seeing the result — that is the move prereg
             discipline forbids — I disclosed the direction.
           Also accepted: residual-arm power was never stated (MDE 0.1490 SD vs
           observed 0.1161 = 77.9% of MDE, power 34.2% — so "did not clear" and "a
           real 0.116 SD effect this window could not see" are NOT distinguishable);
           "largely a dispersion ranking" overstated corr=+0.4066 (per-date R2 = 0.183)
           and was deleted; 5 provenance-tag defects repaired; the n=512 Monte-Carlo
           figure corrected +0.049 -> +0.048; the input_digests_match gate was a
           literal True (the "guard that validates the wrong object" shape) and is
           fixed in code AFTER the run — results.json was produced by 97245c2.
NEXT:      1. No Stage-2 work. GOAL-7 does not have a formulation that survives the
              volatility control on this window, and the window is spent.
           2. Carry forward, if GOAL-7 is re-pitched: §5.1's positive-control constant
              is mis-calibrated at finite cross-section width (the closed-form alpha
              inverts the ASYMPTOTIC Spearman-Pearson relation; the van-der-Waerden
              construction realises +0.021 at n=31, +0.041 at n=128, +0.048 at n=512,
              +0.050 at n=4096  [VERIFIED - tools/goal7_stage1_postreview_diagnostics.py,
              postreview_diagnostics.json]). It passed here with 0.0043 of realised
              margin, but the EXPECTED margin above the VOID floor was only ~0.0015,
              i.e. a ~29% prior chance of a spurious VOID. On a narrower panel the same
              correct code VOIDs outright. Fix the constant in the NEXT registration,
              never in a running one.
           3. Carry forward: the REGISTERED null (independent within-date permutation)
              cannot calibrate a persistent score. Any future registration on this
              programme that permutes within date must either preserve the score's
              cross-date persistence or state that its bar is anti-conservative.
           4. A re-test of the two-sided hypothesis needs dates OUTSIDE this corpus:
              2021-10-08 onward is burned (it is where the U-shape was observed) and
              2016-12-29 -> 2021-04-19 is now spent.

## Round-2 review: the verdict is withdrawn, and the defect is mine

The reviewer found that the frozen estimator treats 60-trading-day blocks as
independent while every label is a **120-trading-day** forward return. Adjacent blocks
share 60 days of each label horizon, so `n_blocks = 18` is not 18 independent
observations, `t_{0.975,17} = 2.1098` is not the right bar, and the registered
within-date permutation null destroys the temporal dependence the treatment arm carries
— it calibrates a different estimator than the one it certifies. Accepted.

**I wrote the amendments that should have caught it.** Amendments 3 and 4 pinned the
partition, the calendar and the critical value to four decimals, and argued at length
about whether a 60- or 120-date embargo was right — while the *estimator* underneath
was averaging 60-day blocks against a 120-day label the whole time. Both amendments
made the wrong quantity more precise. Pinning a bar harder does not help when the bar
sits on the wrong unit, and I was the one writing the guards.

**One correction to the review, recorded because scope depends on it.** It cites the
lag-1 autocorrelation of **0.94**; that is the *per-date statistic*, not the block
means. The governing quantity is the block-mean lag-1 autocorrelation: **+0.2311** raw,
**+0.2592** residual [VERIFIED — recomputed from results.json block_means, this
session], matching the +0.224 already in the results doc. Real and disqualifying for
`df = 17`; not 0.94-severe. Citing a per-date autocorrelation as a block-mean one is
the same class of error as the defect being fixed.

**What survives, and why it does not rescue the verdict.** Dependence understates
variance, so it inflates `|t|` — every `t` here is optimistic, and correcting can only
shrink them. First-order corrected: raw +3.2702 → **+2.5843** (still clears), residual
+1.6437 → **+1.2607** (still fails), consistent with the HAC and re-blocking checks
already in the doc. The direction is stable and the kill leg fails harder once
dependence is honoured.

But a conclusion that survives corrections chosen *after* seeing the data is not a
preregistered finding. The entire value of this document was a bar fixed before the
run; recomputing the bar afterwards returns it to an ordinary post-hoc analysis. So
VOLATILITY-TILT is withdrawn rather than defended, and the dependence-adjusted numbers
are recorded as diagnostics carrying no licence.

**The likely real finding.** At the pinned 1,082-date window, genuinely disjoint label
windows (120d blocks + 120d gaps) give **4 blocks** — below §7's own `n_blocks < 6`
VOID floor; contiguous 120d gives 9, and only by tolerating the same overlap in weaker
form [VERIFIED — computed this session]. A dependence-valid Stage 1 on this window is
probably **underpowered by construction**. That is a fact about the corpus, not about
momentum, and it belongs in a design that says so up front — the third consecutive line
here where the correctly-specified test turns out to lack the power to run.

## Live-surface impact

None. Documents and analysis only. No config, artifact, state or launchd change.
