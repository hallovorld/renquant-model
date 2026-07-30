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
