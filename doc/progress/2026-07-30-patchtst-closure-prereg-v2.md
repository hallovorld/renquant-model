# PatchTST closure prereg v2 — era-free paired estimand   (PR pending)

STATUS:    planned  (frozen registration; NO run has been executed)
WHAT:      Replaces the retracted model#87 closure design with a preregistration
           whose estimand is a within-evaluation-date PAIRED difference, so the era
           offset that carried ~70% of the old effect cannot enter by construction.
           Adds measured (not assumed) null-control false-pass rates, a single
           theory-chosen lag instead of a 4-lag sign count, name/robust-location
           robustness gates, and fail-closed artifact-identity gates.
WHY/DIR:   PatchTST is the one scorer on this programme with a measured negative
           persistence margin — its 60-day-old score predicted forward-60d better
           than its fresh score. Two attempts to close it have been retracted, so
           the question is open and blocking the GOAL-4 sub-question of whether it
           contributes independent information. It is also live-reachable: a
           fallback path can make a stale PatchTST the PRIMARY scorer, which is
           sell-only because its scores are intrinsically all-negative.
EVIDENCE:  n/a — this PR makes NO model or data claim. It registers the rule that
           will adjudicate one. Every prior number it cites is tagged as prior work
           with a reference; nothing was measured for this document.
NEXT:      Seal the evidence bundle (§0.2), run the §0 abort gates, and only then
           execute. The verdict is withheld pending adversarial review (§9).

CORRECTIONS: the first frozen revision set every threshold at `|t| >= 1.96` while
§3 defines a one-sample `t` over a deliberately single-digit number of blocks. At the
expected `n_blocks = 8` the two-sided 5% Student-t critical value is **2.3646**
`[VERIFIED — scipy.stats.t.ppf(0.975, 7)]`, so the **destructive** KILL rule was
materially too permissive, and so were the positive-control, null-false-pass and §6
robustness gates. Caught by codex on PR #113 before any run. Replaced by a single
registered symbol `T_crit = max(P95_null, t_{0.975, n_blocks-1})` (new §3.5), used
identically for treatment, both controls and every robustness gate; no gate now
carries its own number. The permutation leg uses **200** draws, because the 40 in
§4.2 locate a 95th percentile only between the 38th and 39th order statistic and are
too coarse to serve as a threshold — those 40 remain a separate validity check.

**This correction changes the study's own prior expectation, and that is recorded
rather than smoothed over.** The measurement that made PatchTST look decisively
persistence-driven is `d = −0.0556, t = −2.31` on `n_eff = 8`
`[VERIFIED — prior work, model#90]`. `|−2.31| < 2.3646`, so **it does not clear the
correctly calibrated bar** — it cleared only the 1.96 approximation. The honest prior
expectation is UNRESOLVED unless the §1 paired estimand raises power by removing the
era variance the old slicing carried. That is a testable hypothesis about power, not
a rationalisation, and §5 does not permit any other verdict if it fails.

## What the retraction demanded, and where each demand is discharged

The 2026-07-29 retraction withdrew the CLOSE on six counts and ended with an
instruction: a new prereg naming the estimand up front and a bias-corrected
estimator `[VERIFIED — prior work, doc/research/2026-07-29-patchtst-closure-retraction.md]`.

| retraction count | discharged in |
|---|---|
| 1 — estimand chosen AFTER seeing which produced a CLOSE (HARKing) | §1: one estimand, defined before any number exists, with its reason stated in the same paragraph |
| 2 — ~70% of the effect was an era offset | §1: both arms are evaluated on the IDENTICAL `(date, ticker, forward-return)` rows, so no era term can enter the difference. Structural, not a covariate adjustment |
| 3 — "both arms share every row" true of labels, false of score eras | §1: the residual score-era asymmetry is stated as a registered LIMITATION before the run, not discovered afterwards |
| 4 — the control could not fail (signal-free XGB passed 37.5%) | §4.2: the sign-count statistic is gone; the false-pass rate is MEASURED over 40 permutations against a registered 10% VOID ceiling |
| 5 — used a different estimator than the one frozen | §3: exactly one estimator, with self-checks in §0.3 |
| 6 — my own three-view standard resolved only 2 of 4 lags | §1: a single registered gate lag (L=60=h), chosen on theory; other lags are descriptive and may not enter the decision |

## Three defects committed TODAY that this design deliberately forecloses

Not hypothetical — each was found in the last few hours and each is written into a
clause here:

1. **Block arithmetic.** model#110 formed 10 blocks where 9 was correct and
   equal-weighted a 5-day trailing block, inflating its headline `t` by **15.6%**
   `[VERIFIED — prior work, model#110 ERRATUM]`. §3 freezes
   `n_blocks = floor(N_eval / 60)` with the remainder **dropped**, and §0.3 asserts
   no undersized block exists.
2. **Gates all in one dimension.** model#110's frozen design contained only
   date-dimension gates; the effect then died on the two it omitted — dropping 5 of
   145 names took `t` +3.258 → +1.871, a median spread gave +1.964
   `[VERIFIED — prior work, model#110 robustness table]`. §6.1–6.3 register name,
   robust-location and outlier gates up front.
3. **A tautological negative control.** 34 non-payers matched bit-for-bit, but
   their `dividend` is exactly 0.0 every row, so the factor is identically 1.0 and
   the series are equal *whatever the algorithm does*
   `[VERIFIED — prior work, model#110 negative-control correction]`. §4.3 requires
   the permutation control to be shown to CHANGE the statistic before it counts.

## The asymmetry, and why it is registered rather than convenient

A KILL requires all §6 gates; a RETAIN does not. This study can only *remove* a
scorer, so the destructive verdict carries the heavier burden. That is not licence
to soften the other direction: `|t| < T_crit` is UNRESOLVED and stays UNRESOLVED, and
§5 states that a third UNRESOLVED on this question is a finding about the corpus's
POWER, to be reported as such rather than narrated toward a conclusion.

**There is exactly one decision threshold and it is `T_crit` (§3.5).** No other
number in either document may adjudicate an outcome. The `2.5` in §7 is **not** a
threshold: it is a *conservatism trigger*. If the positive control passes with
`|t| < 2.5` the treatment's verdict is unchanged, but a KILL additionally requires
leave-one-block-out to hold at `|t| >= T_crit` in every refit rather than merely
preserving sign. Its preregistered rationale: on the comparable harness the positive
control's own margin was 0.23 of a t `[VERIFIED — prior work, model#90]`, and a
control that barely demonstrates the harness can see a real effect is weak evidence
that the harness's *negative* reading is trustworthy — so the destructive verdict
picks up an extra requirement rather than the bar moving. 2.5 is a round number just
above the `t_{0.975, 7} = 2.3646` floor `[DERIVED — scipy.stats.t.ppf(0.975, 7)]`,
chosen before any control was run; it is not derived from data and is not permitted
to substitute for `T_crit` in any outcome.

§7 pre-commits the power consequences before the run: `n_blocks < 6` forces
UNRESOLVED (underpowered) regardless of the point estimate, and a positive control
passing at `|t| < 2.5` tightens the KILL requirement.

## The safety point that is NOT contingent on the verdict

§8 states it and it belongs in the durable record: the fallback-config hazard gets
fixed **either way**. A fallback path can make a 623-day-stale PatchTST the primary
scorer, and its intrinsically all-negative scores make that a **sell-only** book
`[VERIFIED — prior work, RenQuant#546]`; a sell-only day has already starved the
live book once `[VERIFIED — prior work, memory incident-20260716-book-drained-to-cash]`.
A stale scorer must not become primary whether or not it has edge. If this study
returns UNRESOLVED a third time, #546 still gets fixed — the study must not become
the excuse for leaving it open.

## Live-surface impact

None. This PR adds two documents. No config, artifact, state file, launchd job or
pin is touched, and §8 forecloses a KILL being read as licence to touch any of them
outside the CONTAINMENT PROTOCOL.
