# AMENDMENT 1 to the corrected signal-evaluation prereg (model#90)

Written 2026-07-29 in response to a review finding, BEFORE the affected
recomputation. Per the parent prereg §4, changes are amendments with their own
timestamp, never edits.

## 1. The defect being fixed (codex HIGH — correct)

The parent's §2 fixes `block_length` = the arm's own **label horizon**. Q2's
lag profile instead used `block_length = L`, the lag. At L = 20 and L = 40
that treats observations carrying **overlapping 60-day forward labels** as if
they were 20- or 40-day blocks.

**The lag does not shorten the label overlap.** A shorter block means more
blocks, and more blocks means a larger t for the same effect — so the error is
**anti-conservative** exactly where the profile's short lags are, which is
where an apparent "rise" would be manufactured. This is the same family as the
sample-drift defect the parent prereg was written to fix, one level down.

## 2. The frozen rule (replaces Q2's block choice)

For every lag `L` and every arm:

```
block_length = max(label_horizon_trading_days, L)
```

with the parent's common-sample eligibility unchanged: all lags evaluated on
`align_lags(...).dates` (or `align_lag_pairs` for an unbalanced panel), both
arms of any paired comparison restricted to the same sample before any
statistic is computed, and `n_eff` printed per row.

At the traded horizon this means `block_length = 60` for L ≤ 60 and `L`
beyond. No lag may use a block shorter than the label overlap it inherits.

## 3. Inference procedure (tightened, not loosened)

Every effect is reported through
`renquant_model_common.dependence_aware_mean` (model#89, MERGED
2026-07-29T08:39:02Z), which returns **three views** — block t, a moving-block
bootstrap CI, and leave-one-block-out bounds — and marks an effect resolved
only when all three agree in sign. A block t on 8–12 blocks leans on a normal
approximation it has not earned; requiring agreement is strictly stricter than
the parent's t-only reading and cannot rescue a result the parent would have
rejected.

## 4. Provenance of the inputs (codex, second finding — also correct)

The parent cited numbers from a session-scratch path, which another reviewer
cannot audit and which disappears with the session. The evaluation artifacts
are now retained at
`/Users/renhao/renquant_bundles/corrected-eval-20260729/` and content-addressed
with the reviewed tool from model#91:

- root digest `f6b6ef6d5055600df190da9d56c32453e31b71c54ff5beeda88e12caac0df38a`
  over **44 files** `[VERIFIED — tools/corpus_index.py generate]`.

Any number quoted from those artifacts is now falsifiable by recomputation
rather than by trust. Numbers that cannot be tied to that root must be removed
rather than re-asserted.

## 5. What this amendment does NOT change

No subject, statistic, null, hypothesis or decision rule is altered. Q2's
verdict must be RECOMPUTED under §2; the parent's recorded Q1 and Q3 verdicts
were computed at the traded horizon where `max(60, L) = 60` already held, so
they are unaffected — but that claim is itself checked in the results rather
than assumed.
