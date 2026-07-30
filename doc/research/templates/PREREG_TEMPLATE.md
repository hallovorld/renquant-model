# PREREG TEMPLATE — copy this, fill it, freeze it BEFORE running

Every section below is mandatory unless marked **confirmatory-only**. A
prereg missing a mandatory section is not frozen, it is a plan. The trap
list is not decoration: each row is a real failure this project has already
paid for, and several were paid for twice.

**Applicability gate.** Sections 5 and 7 are marked **confirmatory-only**:
required when this prereg's declared decision rule (§6) could change a
model's status (CLOSE/promote/kill) or trigger a production-facing action.
For routine diagnostics, data-quality checks, or exploratory work with no
such decision rule, write `N/A — non-confirmatory, no promote/kill/production
decision` under §5 and §7 and proceed; do not fabricate a false-pass rate or
adversarial review to fill the section.

---

## 0. Known-trap checklist (copy in full; add a line per new trap)

| # | the failure | how THIS design avoids it |
|---|---|---|
| T1 | a placebo sitting on the signal's own peak (a +120d shift against a profile peaking at 100d) | |
| T2 | naive per-date t on overlapping labels (+5.39 vs block-adjusted +0.70 on the same numbers) | |
| T3 | an invocation frozen without an end-to-end smoke on the exact environment (batch VOID) | |
| T4 | a multi-hour local run without `caffeinate` (5 hours lost to machine sleep) | |
| T5 | an absolute effect quoted without its matched null | |
| T6 | post-hoc subgroup or window search rescuing a dead result | |
| T7 | an experiment mutating a production input | |
| T8 | model/panel internals implemented in the orchestrator | |
| T9 | acting on a striking by-product of a DIFFERENT study | |
| T10 | confusing "the score is stale" with "the signal is long-horizon" | |
| T11 | cross-lag statistics on a drifting sample (`Y.shift(-lag)` nulls the NEWEST rows) | |
| T12 | paired arms drawn from different score windows (era term measured at 19–28%) | |
| T17 | a candidate compared to a naive baseline but never orthogonalised **both ways** — on 2026-07-30 the two-sided momentum arm died against volatility while volatility *survived* orthogonalisation to it (§5c) | |
| T18 | **contiguous blocks under an overlapping label** — blocking is treated as discharging T2, but the crossing fraction is `min(1, h/L)` and equals **1.00 whenever `L ≤ h`**; a 60-day block under a 120-day label voided a whole study on 2026-07-30. **Disclosing the residual is not a remedy**, and **a gap is not independence** — it removes label-window overlap only; §4a requires that plus an inference method whose validity covers what survives | |
| **T13** | **the estimand named only after seeing which one gives the preferred answer — HARKing.** Cost a retracted CLOSE. | |
| **T14** | **a control that cannot fail.** A bare sign-count control passed 37.5% of the time on signal-free input; zero-skill AR scores 50–55%. | |
| **T15** | **a digest cited against a bundle that was later appended to.** Cited `f6b6ef6d…`/44 files; the bundle was `901f0add…`/61. | |
| **T16** | **all placebos clean, and the effect is still a one-column tilt.** Placebos answer "is this noise?"; they CANNOT answer "is this a single raw column, reachable without a model" — a one-column tilt is not noise and survives shuffling exactly like a real effect. Requires §5b. | |

## 1. The question

One sentence. What decision changes depending on the answer?

## 2. The ESTIMAND, named before any computation (T13)

State the quantity in words AND as a formula, including exactly which sets are
held common. Where two natural definitions exist, name the one this prereg
tests **and** state that the other is a different question whose answer does
not bear on this rule.

> Worked example of why: pairing a fresh score against its own stale score can
> hold the LABEL date common (same outcome, fresh vs stale score → a
> persistence question) or the SCORE date common (same scoring days, outcomes
> `L` apart → a horizon question). **Both sets cannot be held common at once.**
> Choosing after seeing the answers is HARKing.

## 3. Data, subjects, and the exact input manifest

Every input path with its sha256 and byte count, plus the code revision. If
the inputs live in a bundle, the bundle must be **SEALED** at prereg time —
a digest citation is void the moment a file is appended (T15). The run should
re-verify each input digest and REFUSE to proceed on a mismatch.

## 4. Statistics, nulls, and the estimator

- statistics, enumerated;
- nulls, one per statistic, each computed on the same sample as its arm;
- **the estimator, named exactly** (e.g. fold-level t vs block t with a stated
  block length). An unregistered estimator voids the verdict (T13's cousin).
- dependence handling: block length ≥ the label overlap, never the lag (T11);
  and prefer `dependence_aware_mean`, which requires block t, bootstrap CI and
  leave-one-block-out to agree in sign.

## 4a. BLOCK/LABEL OVERLAP — state the crossing fraction (T18)

Blocking is the standard answer to T2 (overlapping labels). **It only works if the block is
long relative to the label horizon, and "long" is arithmetic, not a feeling.**

A date at position `p` in a block ending at `L` has its label window reach `p + h`, so it
crosses the block end whenever `p + h > L`. Therefore:

> **crossing fraction = `min(1, h / L)`**  ·  **subsequent blocks touched ≤ `ceil(h / L)`**

`ceil(h/L)` is a **maximum span, not a count every label achieves.** How many subsequent
blocks a given label reaches into depends on the date's position within its block: only
dates near the block end span the full `ceil(h/L)`, and dates near the start span one
fewer `[VERIFIED — enumerated over all positions, this session: at L=60, h=120 the
per-date span is {1, 2}, not a constant 2]`. Report it as a bound.

| `L` | `h` | crossing fraction | blocks touched |
|---:|---:|---:|---:|
| 60 | 120 | **1.00** | **2** |
| 60 | 60 | **1.00** | 1 |
| 120 | 120 | **1.00** | 1 |
| 120 | 60 | 0.50 | 1 |
| 240 | 60 | 0.25 | 1 |

**`L = h` is not a fix.** It still crosses on **every** date; it only reduces the span from
two adjacent blocks to one. Stating `L ≥ h` as the requirement — which I did, in the first
correction of the study that failed on this — frames a reduction as a solution. The same
instinct produced the "`L ≫ h` plus a disclosed number" option below, which a second
review had to remove: **shrinking a dependence and reporting it are both easy to mistake
for eliminating it.**

### Disclosure is NOT a remedy

The first version of this section offered "`L ≫ h`, with the crossing fraction stated as
a number" as a sufficient option. **It is not, and that error is the same one the section
exists to prevent, one level up.** Writing down a nonzero crossing fraction does not make
ordinary block-`t`, permutation calibration, or their nominal degrees of freedom valid —
it only records that they are invalid. A large arbitrary `L` plus a disclosed number
leaves exactly the study that failed on 2026-07-30, with a bigger `L` and a footnote.

An honest number attached to an invalid statistic is still an invalid statistic. Stating
the residual dependence is **necessary and not sufficient**.

**Register one of these, explicitly:**

1. a **gap of at least `h` between retained blocks**, so no label window reaches the next
   retained block — this removes **label-window overlap**, which is the mechanism this
   row is about; or
2. **non-overlapping labels** (sample dates at least `h` apart), which removes
   label-window overlap at source; or
3. `L ≫ h` **together with both**: (a) a **preregistered justification** for why the
   residual dependence at that `h/L` is tolerable for this estimand, and (b) a **named
   inference method whose stated validity conditions cover that dependence** — e.g. a
   block/circular bootstrap on the date axis, or a HAC estimator with its bandwidth and
   the assumptions it needs — registered **before** the run, with its own failure
   condition. A null that permutes the dependence away does not qualify: it calibrates a
   different estimator than the one it certifies.

> ⚠️ **None of these establishes independence, and an earlier version of this row said
> option 1 did.** It called a gap *"the only construction that removes the dependence
> rather than shrinking it"*. That is wrong in the same way as the `L = h` mistake above:
> a gap of `h` removes **label-window overlap** — the specific channel by which adjacent
> blocks share a label — and nothing else. **Predictor persistence, market regimes, and
> any dependence that outlives the label horizon survive it untouched.** Momentum is
> persistent; regimes span quarters. Removing one known channel is not removing
> dependence.
>
> So options 1 and 2 close the channel this row catalogues; they do **not** license a
> plain Student-`t` bar on the surviving blocks. That still needs option 3's second
> clause — an inference method whose validity conditions cover whatever dependence
> remains, or an argued case that the blocks really are independent.
>
> **A simulation showing correct size under an assumed dependence model does not
> discharge this.** It shows the arithmetic is self-consistent under the model it was
> given; a data-generating process cannot exhibit a channel it was not handed. Only a
> dependence-preserving calibration **on the real series** — or an argued independence
> case — establishes the bar. Caught on renquant-model#128, 2026-07-31, where exactly
> that simulation was reported as "the first measured confirmation".

Options 1 and 2 are preferred because they remove a channel *structurally* rather than
modelling it. Option 3 is a promise about an estimator, and promises get checked.

Whichever is chosen, **state `L`, `h`, the crossing fraction and the maximum blocks
touched in the frozen text**, so a reader can check the relation without re-deriving it —
and state the resulting inferential unit and its degrees of freedom, since under options
1–3 that number is generally **not** `n_blocks − 1`.

**Budget the power before freezing.** Options 1 and 2 cost blocks, often severely: on a
1,082-date window with `h = 120`, contiguous `L = 120` gives 9 blocks while `L = 120`
with a `120`-day gap gives **4** `[VERIFIED — computed 2026-07-30]`. If the valid design
cannot clear the power floor, that is the finding, and it belongs in the registration
rather than being discovered after a run has spent the window.

**What earned this.** On 2026-07-30 a screen registered 60-trading-day blocks under a
120-trading-day label, reported `n_blocks = 18` and used `t_{0.975,17}`, and was **VOIDED**:
adjacent block means shared 60 days of every label window, so 18 was never the number of
independent units. The run's own reported lag-1 autocorrelation of **0.94** was the symptom,
logged as a caveat instead of read as evidence the inferential unit was wrong. A sweep of
the 29 frozen and result documents then found that study was the only one with `L < h` —
but **five** sit at `L = h`, and **none states its crossing fraction**. That is why this is
a template row and not five separate challenges.

## 5. Control calibration (T14) — confirmatory-only, see Applicability gate

Skip this section at BASELINE tier and say so explicitly rather than leaving
it blank. At CONFIRMATORY tier it is mandatory: a control arm is only a
control if it can FAIL. Report, before the real run:

- the control's measured **false-pass rate** under a signal-free null matched
  to the treatment's autocorrelation, over ≥ 40 replications;
- if that rate exceeds ~10%, the control is decorative and the rule must be
  strengthened before freezing.

## 5b. NAIVE-BASELINE ARM — mandatory wherever a statistic could be a tilt (T16)

**A clean placebo panel does not license an interpretation.** Placebos test the
null "this is noise". They are structurally incapable of testing "this is a single
raw column, reachable without a model", because a one-column tilt is not noise —
it survives every label shuffle exactly as a real effect does. A cross-sectional
selection statistic (IC, decile spread, hit rate) can be reproduced by a single
dominant input column with no model, no training and no fit; a clean control
panel does not rule this out, because the control panel was never asked that
question.

**Register, before running:**

1. **At least one naive single-column baseline arm**, chosen from the model's own
   most-used inputs — not from a list of plausible-sounding factors. If a feature
   attribution exists, take the top-|effect| feature; if not, say how the
   candidate was chosen and why that choice could not have been made to lose.
   Freeze and fingerprint the baseline exactly as §3 requires for inputs, BEFORE
   execution: the attribution method; the frozen artifact/checkpoint path +
   sha256 it was read from; the feature's transform (raw / rank / z-score) and
   missing-value rule; the direction (long high or long low); and the
   one-column portfolio construction (e.g. rank-sorted long-short deciles). An
   unfrozen baseline specification is a knob, not a baseline (T13's cousin).
2. **A neutralised arm**: the subject's score rank-orthogonalised to each
   baseline. Report both the raw and the neutralised effect.
3. **A conditional-pooling arm**: the effect pooled within deciles of each
   baseline. An effect that survives shuffling but dies inside its own deciles is
   a tilt.
4. **A testable gate on beating the baseline, not two separately significant
   numbers.** Register: the paired contrast between the subject and each
   baseline, computed on the SAME folds/blocks as the primary estimator (§4);
   the estimator and confidence/inference rule for that DIFFERENCE (e.g.
   block-paired t on the per-block delta, using §4's block length); how the
   predeclared margin (§6) applies to the paired difference, not to each arm's
   marginal significance; and, when more than one baseline / neutralised /
   conditional arm is registered, the family-wise error handling (e.g.
   Holm-Bonferroni across the registered arms). A verdict is licensed only if
   the subject beats its baselines under that corrected, paired comparison —
   never by each side independently clearing significance.

**Applicability.** Mandatory for any confirmatory subject whose estimand is a
cross-sectional selection statistic (IC, decile spread, hit rate). Optional, but
say so explicitly, for a pure timing or event-study estimand where no
cross-sectional column ordering exists.

**Not satisfiable retroactively.** Adding baselines after seeing the subject's
number and choosing which to report is T13 wearing a lab coat. Name them in the
frozen text.

## 5c. ORTHOGONALISATION ASYMMETRY — mandatory when a naive baseline is in play (T17)

§5b asks whether a naive baseline **matches** the candidate. That is not enough: two
correlated statistics can each look strong beside the other while only one of them carries
the payoff. The question that settles direction is **which survives orthogonalisation to
which**, and it must be registered before the run, in both directions.

Register, for candidate `C` and naive baseline `B`:

1. `C ⊥ B` — the candidate residualised on the baseline, per date, OLS with intercept.
2. `B ⊥ C` — the baseline residualised on the candidate, the same way.
3. `B` alone, unresidualised.

and the reading, fixed in advance:

| `C ⊥ B` clears | `B ⊥ C` clears | reading |
|---|---|---|
| yes | no | the candidate carries it; the baseline is a proxy for the candidate |
| **no** | **yes** | **the baseline carries it; the candidate is a veneer.** Whatever `C` scores raw, the hypothesis is NOT supported |
| yes | yes | two partly-independent effects; report both and claim neither as the other |
| no | no | neither survives; the shared component carries it and neither is identified |

**Registered as a KILL condition, not a diagnostic.** If the `no / yes` cell obtains, the
verdict is fixed by that cell alone — the raw arm's own significance may not be cited
against it. Making this a decision rule rather than a caveat is the whole point: a caveat
gets narrated around.

**What earned this section.** On 2026-07-30, GOAL-7 Stage 1 registered exactly this as its
§4 and the `no / yes` cell obtained: the raw two-sided momentum arm cleared at
`|t| = 3.270` while `C ⊥ B` reached only `1.644` against a `T_crit` of `2.110` — and the
adversarial review then measured the other direction, where `B` (`z(vol_60_tr)`) **alone**
paid **+0.3477 SD, `t = +4.610`**, more than the candidate, and survived orthogonalisation
to `C`. Verdict: VOLATILITY-TILT, nothing licensed. Without the second direction the
result would have read as "the candidate is weakened", not "the candidate is a veneer".

The same axis had already accounted for a second subject: the production XGB's traded
estimand was reproduced by a single `STD20` sort and collapsed to `−0.0554` orthogonalised
to `STD60`. **Two of two subjects on this panel.** On this corpus the default prior for any
new cross-sectional statistic is that it is the volatility axis again, so `B` should be a
volatility statistic unless there is a stated reason otherwise.

## 6. Decision rule

Thresholds, and what each verdict AUTHORISES (usually: opening a reviewed PR,
never a live change). Ties, ambiguity, broken arms and invalid controls all
resolve to the conservative branch, named explicitly.

## 7. Publication discipline — confirmatory-only, see Applicability gate

At BASELINE tier, ordinary review suffices; say so and move on. At
CONFIRMATORY tier this is mandatory.

**Commission an adversarial review BEFORE publishing a verdict, not after.**
On 2026-07-29 a CLOSE was withheld pending attack; the attack destroyed it on
six counts. Publishing on the author's own reasoning would have produced the
second retraction on the same question in one day. The reviewer's brief must
say "assume the conclusion is wrong and try to break it", and a confirmation
that lists no residual risk is a failed review.

## 8. Discipline

Read-only over production; scratch-only writes; every number provenance-tagged
per LONG rule #10; negative and inconclusive results reported with the same
prominence as positive ones; frozen — any change is a timestamped amendment
written BEFORE the affected run, never an edit.
