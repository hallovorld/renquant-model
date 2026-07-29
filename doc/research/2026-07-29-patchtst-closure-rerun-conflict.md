# PatchTST closure re-run — a CONFLICT, deliberately not a verdict

Date: 2026-07-29. Status: **UNRESOLVED — no verdict claimed.**

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

## Why no verdict is being claimed

The 2026-07-29 adversarial bug hunt recomputed the ORIGINAL closure arms on a
common score-date set and reported the opposite: **PatchTST p = 4/4 → 0/4 and
the control 4/4 → 1/4 (INVALID)**, which under the same rule gives
INCONCLUSIVE. That recomputation is what retracted the first CLOSE.

So two computations, each built to be sample-stable, disagree on both the
treatment and the control. At least one construction is wrong, and I do not
yet know which. Possible sources, none yet eliminated:

1. **What "common" ranges over.** This run intersects SCORE dates evaluable at
   every lag. The bug hunt may have intersected label-side eligibility, which
   is a different set.
2. **Which axis the persistence shift walks.** Here the stale score is taken
   `L` positions back on the score-date axis and re-attached to the same label
   date. An implementation that instead shifts the LABEL produces a different
   pairing with the same description in prose.
3. **Coverage after the join.** Restricting to the common sample before versus
   after the ticker-level merge changes which `(date, ticker)` pairs survive —
   precisely the unbalanced-panel gap that `align_lag_pairs` exists for, and
   which THIS run does not use (it aligns on dates only).

Item 3 is the most likely and the most embarrassing: the pair-level primitive
was written for exactly this hazard two rounds ago, and this run used the
date-level one.

## What happens next, and what must not

Next: re-run BOTH constructions under `align_lag_pairs`, with the two
implementations diffed line by line, and let the frozen rule decide once they
agree. If they still disagree, neither may be quoted.

Must not: pick the construction whose answer is preferred. A CLOSE verdict was
already published once on this question and retracted; publishing a second one
on the strength of one of two conflicting computations would be the same
error with better tooling.

PatchTST's status therefore remains **UNRESOLVED**.
