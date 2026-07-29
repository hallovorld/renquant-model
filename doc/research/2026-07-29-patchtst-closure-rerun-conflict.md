# PatchTST closure re-run — the conflict is RESOLVED (different estimands)

Date: 2026-07-29. Status: **RESOLVED as a definitional difference, not an
error. A CLOSE follows from the frozen rule — submitted for adversarial
review rather than declared settled.**

> ## Resolution (added after the conflict was traced to source)
>
> The two computations were never estimating the same quantity.
>
> The persistence arms differ from the real arms by an **L-shift between the
> score date and the label date**. You therefore cannot hold BOTH sets common:
>
> * hold the **label date** common → the two arms read scores from dates `t`
>   and `t−L` against the SAME forward window. This is *"for the same
>   outcome, does today's score beat the L-day-old one?"* — **the persistence
>   question the frozen rule asks.**
> * hold the **score date** common → the two arms are scored on the same
>   dates but must be judged against forward windows `L` apart. This is
>   *"does this score predict the near window or the far one better?"* — a
>   **horizon** question.
>
> The audit's `common-SD` arms hold SCORE dates common `[VERIFIED — bughunt/
> h6_closure.py: "'common-SD' = both arms recomputed on the SAME SCORE-date
> set"]`, so its `p = 0/4` and invalid control are correct answers to the
> horizon question and simply do not bear on the persistence rule.
>
> The audit's PRIMARY criticism of the original `closure.py` remains valid and
> is not being waved away: that code paired on the label date **without**
> restricting to a common sample, so REAL ran on `corpus[L:N]` and PERSIST on
> `corpus[0:N−L)` — different eras. This re-run removes exactly that: both
> arms are columns of ONE merged frame, so they share every row.
> `[VERIFIED — 68,870 rows / 485 dates / 142 tickers at L=60, identical for
> both arms by construction]`
>
> My own leading suspect — that date-level rather than pair-level alignment
> caused the divergence — is REFUTED: rerunning under `align_lag_pairs` gives
> **numerically identical** results (−0.0101 / −0.0274 / −0.0458 / −0.0480,
> t −1.01 / −1.39 / −1.53 / −1.88, p = 4/4).
>
> **Implied verdict: CLOSE.** Not declared settled here. A CLOSE was published
> on this question once and retracted; this one reverses the basis of that
> retraction, so it belongs in front of an adversarial reviewer before it
> changes PatchTST's recorded status. Until then: **UNRESOLVED-pending-review.**

model#87's closure rule is frozen and merged; its earlier results were
retracted because the harness computed cross-lag arms on a drifting sample.
This is a re-run of the SAME frozen rule with the corrected instrument
(`renquant_model_common.align_lags` + `dependence_aware_mean`, model#89).

## What this run measured

Construction: the persistence arm is the same model's score from `L` positions
earlier on the score-date axis, joined to the SAME label date and ticker; both
arms are then restricted to `align_lags(dates, dates, [0,20,40,60,80]).dates`
— one common sample for every lag (T11), both arms on identical dates (T12).
`block_length = 60`, 1200 bootstrap resamples.

**PatchTST** (88,750 rows, 625 dates → 545 common)
`[VERIFIED — recomputed 2026-07-29 over the content-addressed bundle
f6b6ef6d…/wf-eval]`:

| lag | mean d | block t | bootstrap 90% CI | leave-one-block-out | rule |
|---|---|---|---|---|---|
| 20 | −0.0101 | −1.01 | [−0.0320, +0.0075] | [−0.0147, −0.0051] | negative |
| 40 | −0.0274 | −1.39 | [−0.0640, +0.0079] | [−0.0377, −0.0137] | negative |
| 60 | −0.0458 | −1.53 | [−0.0871, −0.0037] | [−0.0492, −0.0213] | negative |
| 80 | −0.0480 | −1.88 | [−0.0952, −0.0062] | [−0.0615, −0.0338] | negative |

→ `p = 4/4` at the rule's `block t ≤ −1.0`.

**Positive control, prod XGB** (147,066 rows, 508 dates → 428 common):
+0.0159 (t +1.30), +0.0302 (+1.36), +0.0394 (+1.76), +0.0495 (+1.71) —
**positive at 4/4**, so the control is VALID by the rule's ≥3 requirement.

Mechanically, `p = 4/4` with a valid control is **CLOSE** under model#87 §3.

## Why the two computations disagreed (superseded analysis, kept for the record)

The 2026-07-29 adversarial bug hunt recomputed the ORIGINAL closure arms on a
common score-date set and reported the opposite: **PatchTST p = 4/4 → 0/4 and
the control 4/4 → 1/4 (INVALID)**, which under the same rule gives
INCONCLUSIVE. That recomputation is what retracted the first CLOSE.

At the time this section was first written, three candidate causes were
listed as unexamined, with "which axis the persistence shift walks / pair-
level vs date-level alignment" (then item 3) flagged as the leading suspect.
**That suspicion is refuted** — see the Resolution block at the top: rerunning
under `align_lag_pairs` reproduces this run's numbers exactly
(−0.0101/−0.0274/−0.0458/−0.0480, identical to three decimal places), so
date-vs-pair alignment was never the source of the disagreement. The actual
source is the estimand difference explained in the Resolution block: the
audit's `common-SD` construction and this run's persistence-arm construction
answer different questions (horizon vs. persistence) and are not in conflict
about the same quantity — there is no remaining "which construction is
wrong" question to resolve by further re-running.

## What happens next, and what must not

The re-run planned here (both constructions under `align_lag_pairs`) has
already happened — see the Resolution block. What remains is NOT another
re-run; it is adversarial review of the estimand-difference explanation
itself, since a CLOSE verdict was already published once on this question
and retracted, and reversing that on the strength of a single author's
re-analysis (however carefully reasoned) would repeat the same error with
better tooling.

Must not: treat "the implied verdict is CLOSE" as PatchTST's recorded status
before that review happens.

PatchTST's status therefore remains **UNRESOLVED-pending-adversarial-review**
— not because the two computations are unreconciled (they are, as of the
Resolution block above), but because a reversal of a previously-retracted
verdict needs an independent check before it is recorded, not just a
same-author explanation.
