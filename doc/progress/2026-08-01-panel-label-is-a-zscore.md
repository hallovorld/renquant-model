# GOAL-4 — the prereg I was about to write had the wrong estimand

**Date:** 2026-08-01 · `renquant-model`

## What stopped it

Next in the GOAL-4 line was a preregistered study: *does consensus across the 12
same-recipe boosters beat a single arm?* Capacity checked out — 2 599 labelled dates
against the 1 200 that `h = 60` needs at floor 20.

Then I checked the label itself, and the estimand I had in mind — *"top-decile spread in
excess return"* — does not exist in this panel `[本次实测 2026-08-01]`:

| | |
|---|--:|
| dates | 2 599 |
| dates with per-date `mean = 0` | **2 599** |
| dates with per-date `std = 1` | **2 599** |
| worst `\|mean\|` | 7.7 × 10⁻¹⁷ |
| worst `\|std − 1\|` | 1.2 × 10⁻¹¹ |
| nulls | **0** |

**`fwd_60d_excess` is a per-date cross-sectional z-score.** Not an excess return.

## The two consequences

1. **No quantity in return units can be read off it.** A "spread" here is in standard
   deviations of that date's cross-section — it cannot be summed, annualised, or compared
   to a cost. Reporting it as basis points is a unit error, and it is the one I was about
   to freeze into a prereg.
2. **The label exists past the rawlabel frontier.** The rawlabel corpus stops at
   2026-04-28; the panel carries labels for **5 further dates** — 2026-04-29 … **2026-05-05**
   — **723 rows**. Note 05-05 is *newer than the 2026-05-04 panel max I measured earlier
   tonight*: **the panel was rebuilt mid-session**, which is itself worth knowing before
   quoting any panel number from a few hours ago.

## What is NOT established

**That the past-frontier labels are wrong.** A per-date z-score is computable from any
values, so its presence says nothing about whether the 60-day window has elapsed — and
equally, it does not show the rows are unrealised. The lockstep guard already refuses to
certify a rawlabel corpus against that tail. What is established is narrower and enough for
a study design: **do not treat those rows as realised without checking, and do not treat
any row's label as a return.**

## Tests

7, including the discriminating one: a **raw-return** column (non-zero cross-sectional
mean) must NOT be recognised as z-scored, and a **single** non-conforming date breaks the
contract — "mostly z-scored" is not the contract, because one unstandardised date changes
what a pooled statistic means.

Suite: **1170 passed, 2 skipped**.

## Next

The consensus prereg is **not** written this round, deliberately. Its estimand has to be
restated in the units the data actually has (a rank/IC statistic, or a spread explicitly
labelled in cross-sectional SDs), and its date range has to exclude or justify the 5
past-frontier dates. Freezing it before that would have been freezing a unit error.
