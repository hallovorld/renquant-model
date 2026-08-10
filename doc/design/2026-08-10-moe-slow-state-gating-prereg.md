# MoE slow-state gating — design proposal (orch#966, the last un-falsified routing axis)

STATUS: design proposal + committed exploratory freeze surface — NOT a
confirmatory prereg. The file name keeps "prereg" for lineage with the
condact line (2026-08-10-xgb-mom-conditional-activation-prereg.md), whose
two-stage discipline this document mirrors verbatim on a single changed
axis. Stage E (exploratory) runs now and records NO verdict of any kind;
Stage C (confirmatory) is frozen here but is NOT invocable — the harness
refuses it by construction, and a C-capable harness is its own reviewed
amendment on unseen data. Operator directive 2026-08-10: everything from
EXISTING backtest data, no future accrual.

This proposal states the ONE MoE routing hypothesis that the frozen v2 /
condact / model#218 gates did not falsify. model#214 KILLed the momentum
expert as a STANDING arm. condact (Stage E, this same directory) found the
DAILY-dispersion state (ROC20, per-day) does not gate its edge — Stage-E
contrast CI [−0.0511, 0.0351] straddles 0. model#218 Stage E found NO
SUPPORT on the daily-dispersion axis either. What remains untested is a
SLOWER clock: the momentum edge may concentrate in a monthly-persistent
market state, invisible to a daily gate. This document tests exactly that,
and nothing else — one axis per experiment (the withdrawing-one-instrument
lesson: if this is null, it is reported null; no substitute estimand).

## 1 · Hypothesis

The xgb_mom_60d model's cross-sectional signal concentrates in market
states of high slow-horizon dispersion, where the state moves at MONTHLY
cadence and is identifiable AT DECISION TIME from prices alone — making a
conditional-weight MoE gate implementable without the regime-label
causality wall (orch#930/#931: the system's regime field is a close-of-run
audit value, NOT admissible as an activation input; this design never
touches it). The distinction from condact is ONLY the activation clock:
monthly-held ROC60 dispersion, not per-day ROC20 dispersion.

## 2 · Proposed experiment (single choices; frozen by this harness PR)

| element | frozen choice |
|---|---|
| model + folds + real-signal | condact's merged real-signal machinery VERBATIM (imported, not re-derived): the v2 embargoed CUTS (91-day gap > ~84-day label window), per-row purge, PARAMS, SEEDS (42,43,44), 70-feature list, corpus sha, the `daily_ics` per-day-IC function and the `bootstrap_contrast` block bootstrap. real_sig(day) = ic_real − ic_shuffle (within-date shuffle), the embargo-floor-robust DIFFERENCE — never absolute IC (WF-gate leakage-floor lesson) |
| slow state S(t) | cross-sectional std of the corpus's own **ROC60 column** (60-trading-day rate of change — the exact committed data, no recomputation) across the universe present on the **LAST TRADING DAY of each calendar month**; HELD for the following month (monthly cadence) |
| activation A(month) | A_raw[m] = 1 iff S[m] > the trailing-12-month median of the monthly S series (min 12 months of history; earlier months INADMISSIBLE, fail-closed, never back-filled). A applied to a test day d is A_raw[month(d) − 1] — the end-of-previous-month evaluation, held. Causal by construction: S[m] uses only data ≤ end-of-m and is applied only to days of m+1 |
| unit of analysis | per-DAY cross-sectional IC of the fold models' OOS predictions (real and within-date-shuffle), pooled over all embargoed-fold test days, each day carrying its month's held A |
| primary contrast | mean daily real_sig on A=1 months MINUS A=0 months |
| uncertainty | stationary block bootstrap on the daily real_sig series, mean block 21 trading days, 2,000 resamples, seed 99, percentile CIs — mirrored from condact for comparability; no borrowed critical values |
| guards | Stage-E reporting guard: n(A=1) ≥ 12 AND n(A=0) ≥ 12 distinct test MONTHS in each arm (the effective unit); day-guard n ≥ 100 each for gate arithmetic. Stage-C frozen guard: ≥ 24 realized-label MONTHS per arm (§2b) |

## 2b · TWO-STAGE STRUCTURE (the post-selection blocker, accepted in full)

The hypothesis, variable, and threshold were formed AFTER inspecting the
same eight v2 folds — re-slicing those predictions cannot be confirmatory.
This proposal is therefore two stages with hard separation, identical to
condact:

**Stage E (exploratory, the seen folds)**: the §2/§3 analysis runs on the
v2 OOS predictions but carries NO verdict authority — its output is
hypothesis-refinement diagnostics, and no PASS/KILL is recorded from it.
Its committed artifacts are marked `stage: "E-exploratory"`, `artifact_kind`
∈ {control, result}, `admissible_verdict: null`.

**Stage C (confirmatory, unseen data — rule stated here, frozen before
anyone looks)**: the SAME rule (monthly-held ROC60 dispersion vs its
trailing-12-month median, definition and threshold immutable from this
document onward) is evaluated on the corpus EXTENSION window (entry dates
from 2026-05-08 onward — data outside every v2 training set and outside the
fold windows that generated the hypothesis, requiring the orch#939 corpus
extension). The §3 gates and §2 bootstrap apply in their Stage-C forms.
VERDICT TIMING IS DETERMINISTIC, NOT DISCRETIONARY: the confirmatory
verdict is recorded on the first date the frozen sample guards (≥ 24
distinct calendar MONTHS with A=1 AND ≥ 24 with A=0, each with REALIZED
fwd_60d labels in the extension window) are met. Earlier looks at the
extension outcomes are prohibited and the harness refuses to emit Stage-C
gate arithmetic before the guards are met (fail-closed, `--stage C` not
invocable in this harness version). Below the guards, no number is
published.

The honest sentence for the operator, in the doc where it belongs: a
monthly gate accrues ~1 effective observation per month, so a confirmatory
answer to "does a slow state gate this model" cannot be conjured from the
seen folds NOR read quickly from a fresh window — Stage C's clock (§6) is
the price of a real answer, and that clock is long.

## 3 · Gates (all required for a Stage-C PASS; Stage E records no verdict)

1. real_sig on A=1 months > 0 (bootstrap 95% CI excludes 0);
2. the A=1 − A=0 contrast > 0 (bootstrap 95% CI excludes 0);
3. mechanism-not-calendar (Stage-C form): at the verdict date, A=1 months
   and A=0 months must EACH span ≥ 24 distinct calendar months of the
   extension window (the §2b/§6 deterministic clock enforces this; an
   activation that is one contiguous calendar block is a calendar reading,
   not a mechanism reading). The Stage-E per-fold month census is a
   DIAGNOSTIC only — no verdict authority;
4. within-A placebo: the same contrast computed on the shuffle ICs must NOT
   exclude 0 on the positive side.

PASS earns a conditional-weight rule PROPOSAL for the L2 allocation layer
(the mom expert's weight scaled by A(month)) — design only, behind the
serving gates (#931/#937) and its own review. KILL is a completed outcome:
the momentum edge is not gated by an identifiable slow state either, and
model#214's KILL for a STANDING arm stands. Either verdict closes the last
un-falsified routing axis.

## 4 · What this does not test

Sector conditioning (the L2-S successor line owns it; one axis per
experiment); any regime-label input (inadmissible per #930); the DAILY
dispersion axis (condact / model#218 already found NO SUPPORT); book-level
economics (IC-level only; the #927 cost lessons precede any deployment
claim); no threshold, feature, median-window, or cadence search — ROC60,
the 12-month median, the monthly last-trading-day clock, and the held-one-
month application are single frozen choices, and any variant is a new dated
prereg.

## 5 · The freeze surface — what this harness PR commits before any run

The model#213 pattern (harness + verifier + controls land first, no
execution-time interpretation). Committed in this PR:

1. **Real-signal reuse** — `2026-08-10-moe-slow-state-harness.py` imports
   the merged condact harness (which imports the v2 harness) and reuses
   FEATS, CUTS, PARAMS, LABEL, SEEDS, `daily_ics`, and `bootstrap_contrast`
   as the SAME objects — the fold-defining constants live IN the frozen v2
   table (runner-guards-are-prereg-content lesson), never re-derived here.
2. **Slow-state definition + application** — S(month) from the ROC60 column
   on each month's last trading day; A_raw vs the trailing-12-month median
   (min 12 months, fail-closed warm-up); A held for the following month;
   ROC60-missing rows excluded from each evaluation-day std with the
   exclusion count persisted per evaluation month.
3. **Bootstrap implementation** — stationary block bootstrap on the daily
   real_sig series, mean block 21, 2,000 resamples, seed 99, committed as
   code (reused from condact).
4. **Controls** — `2026-08-10-moe-slow-state-control-positive.json`
   (planted monthly-state effect: ROC60 dispersion gates the label —
   recovered, PASS) and `...-control-null.json` (the SAME planted data with
   the month labels SHUFFLED — contrast collapses, CI covers 0, KILL), both
   run under the frozen rules BEFORE the first real read, with hard exit
   codes.
5. **Fail-closed verdict machinery** — the harness refuses Stage-C gate
   arithmetic (`--stage C` not invocable) and refuses `--real` without the
   corpus-sha assertion (read from the v2 harness source via ast) and the
   explicit orch#966 confirmation flag; the verifier
   (`2026-08-10-moe-slow-state-verify.py`) enforces stage/kind fields, the
   frozen ROC60/12-month axis, the features_sha256 against the v2 FEATS,
   the bootstrap params, and the model#213 countersign rule on any non-null
   verdict.

Any deviation the harness needs makes THAT change the visible, reviewed
amendment surface — never an execution-time interpretation.

## 6 · Power note — the #955 lesson, stated honestly (the finding, whatever the contrast)

Monthly cadence is the whole point AND the whole problem. A daily gate over
the v2 test folds carries ~1,350 test days; a monthly gate over the SAME
folds carries the number of distinct test MONTHS — the corpus is
2016-01-04..2026-05-07 (125 calendar months), the v2 test windows are
April–December of 2019–2025 plus 2026-04..05, i.e. ~65 test-month cells,
and the activation splits them into A=1 and A=0 arms of ~30 months each.
Those ~30 months per arm are the EFFECTIVE independent observations for the
contrast — NOT the ~700 days per arm. Within any month every test day
shares one held A value, so the days are not independent evidence about the
state; the block-21 daily bootstrap (≈ one month) approximately respects
this, but the honest denominator is the month count, which the harness
reports per fold and in total (`effective_months_total`, `n_A1_months`,
`n_A0_months`).

Consequence, computed not asserted: with ~30 months per arm and a monthly
real_sig standard deviation on the order of IC noise, the contrast's
standard error is roughly √2 · sd(monthly real_sig) / √30. For any effect
size a slow gate could plausibly carry, this is a LOW-POWER test on the
seen folds — and Stage C is worse: the extension window (2026-05-08 onward)
accrues months one at a time, so the §3 gate-3 requirement of ≥ 24 A=1 AND
≥ 24 A=0 realized-label months is not reachable for YEARS (order
2030+ by calendar arithmetic, and only if the state actually alternates).
This is itself a finding, in the G-B BEAR-exit-reachability tradition: a
monthly MoE gate over a ~7-year backtest is structurally under-powered, and
a confirmatory monthly gate on go-forward data is a multi-year clock. The
research note records the exact Stage-E month split and the resulting power
verdict; the operator's decision to route capital on a slow state cannot be
bought at policy grade from this or any near-term dataset.

## 7 · Countersign block (model#213 duty)

No non-null `admissible_verdict` exists in any committed artifact of this
line. Should Stage C ever be run under its own reviewed amendment and
produce an admissible verdict, the verifier requires a line of the exact
form below to appear in THIS document before it will pass:

<!-- COUNTERSIGN: <artifact-filename> admissible_verdict=<PASS|KILL> -->
