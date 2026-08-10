# MoE slow-state gating, Stage E diagnostics — the monthly gate finds NO support either, and cannot be powered

The one Stage-E run the frozen design allows (orch#966; harness executed
2026-08-10 on the sha-pinned corpus). STAGE E CARRIES NO VERDICT AUTHORITY
(mirrors condact model#215 §2b); this is hypothesis-refinement diagnostics,
stage-stamped, and the frozen Stage-C rule and clock are UNCHANGED by
anything here. This line tests the exact hypothesis the condact Stage-E
note left open — that the momentum edge concentrates at a MONTHLY
(regime-timescale) state rather than the daily state condact already
falsified.

## The estimand as implemented `[VERIFIED — committed stage-stamped artifact; slow-state verifier exit 0]`

S(t) = the cross-sectional standard deviation of the corpus's own **ROC60**
column across the universe present on the **last trading day of each
calendar month**, HELD for the following month (monthly cadence, causal:
S at end-of-month m uses only data ≤ end-of-m and is applied only to days
of m+1). A_raw[m] = 1 iff S[m] > the trailing-12-month median of the
monthly S series (min 12 months of history; earlier months inadmissible,
fail-closed). The activation applied to a test day d is A_raw[month(d) − 1]
— the end-of-previous-month evaluation, held. Contrast: mean daily
real_sig (= ic_real − ic_shuffle, the embargo-floor-robust DIFFERENCE) on
A=1 vs A=0 months, on the merged v2 embargoed CUTS test folds, bootstrapped
on the daily series (stationary block, mean block 21, 2,000 resamples,
seed 99 — imported from condact, not re-derived).

## The numbers `[VERIFIED — 2026-08-10-moe-slow-state-stageE-result.json; verifier exit 0; corpus pin 870f68eb… carried]`

| quantity | value |
|---|---|
| A=1 (high-slow-dispersion) months / A=0 months | **38 / 27** (effective units; month guard ≥12 each met) |
| A=1 days / A=0 days | 785 / 572; A flips in all 8 folds |
| mean daily real signal, A=1 | **+0.0157** |
| mean daily real signal, A=0 | **+0.0202** |
| A=1 bootstrap 95% CI | [−0.0278, +0.0552] — includes 0 |
| A=1 − A=0 contrast | **−0.0045**, CI [−0.0599, +0.0456] — includes 0, point estimate NEGATIVE |
| within-A placebo (shuffle-IC contrast) | CI does not exclude 0 on the positive side (gate 4 held) |
| gate arithmetic (NO authority) | KILL-shaped — gates [1,2]=[fail,fail], [3,4]=[hold,hold] |

Controls (run before the real read): positive (planted monthly-state
effect) recovered — contrast +0.130, CI [+0.101, +0.160], PASS; null (the
SAME planted data with the month labels SHUFFLED) collapsed — contrast CI
[−0.009, +0.067] covers 0, KILL. The machine can see a real slow gate when
one is planted and correctly reports its absence when the labels are
scrambled.

## Honest reading

1. **The monthly gate finds the same non-result as the daily gate — and
   leans the wrong way.** condact's daily ROC20 gate gave A=1 +0.0151 vs
   A=0 +0.0202; this slow monthly ROC60 gate gives +0.0157 vs +0.0202.
   Both say the momentum edge is if anything SLIGHTLY LOWER in
   high-dispersion states, with a CI that straddles 0. Moving the
   activation clock from daily to monthly did not uncover a hidden
   concentration. The last un-falsified routing axis returns null.
2. **The test cannot be powered — this is the load-bearing finding
   (#955).** A monthly gate over the v2 folds has ~65 effective
   observations (the distinct test-month cells), split 38 / 27 — NOT the
   ~1,350 test days. The bootstrap contrast SE is ≈0.027; to resolve a
   plausible +0.02 gate contrast at ~80% power the design needs ~14×
   more effective months (~900 months, ~77 years), and even a large
   +0.03 contrast needs ~6× (~34 years). Worse, the per-fold census shows
   the monthly state is PERSISTENT WITHIN A YEAR (fold-2024 is 8 A=1 / 1
   A=0; fold-2026 is 2 / 0), so the 65 months are less independent than
   even their count suggests. A monthly MoE gate over a ~7-year backtest
   is structurally under-powered; there is no near-term dataset that fixes
   this.
3. **Stage C is a multi-year clock and is honestly out of reach.** The
   frozen Stage-C rule requires ≥24 realized-label A=1 months AND ≥24 A=0
   months in the extension window (entry dates ≥ 2026-05-08). At ~1
   month accrued per month, and only if the state actually alternates,
   that guard is not reachable before ~2030+. The two-stage discipline
   correctly refuses to buy a confirmatory answer this design cannot
   afford — exactly the G-B BEAR-exit reachability verdict, applied to a
   slow gate.

## What this changes operationally

Nothing is deployed, nothing was going to be. This closes the MoE routing
line's cheapest remaining hypothesis: neither a daily nor a
monthly-regime dispersion state identifiably gates the momentum expert,
and the monthly axis additionally cannot be powered to policy grade from
existing data. model#214's KILL for a STANDING momentum arm stands.
Sector conditioning (a DIFFERENT axis, the L2-S successor line) and any
other condition variable are NEW dated preregs and may not inherit this
run's data — no substitute estimand is reached for here.
