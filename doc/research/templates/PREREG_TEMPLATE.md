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
