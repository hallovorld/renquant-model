# A gap-honest block test on these series has df = 3–4, and the frozen bar is a normal quantile

## What was being attempted

model#154 showed the frozen v1-vs-v2 Stage-A gate (`|t| >= 3.29`) is produced by
`dependence_aware_mean`, whose blocks are contiguous with **gap = 0** and whose own
docstring says it "must not present the comparison as inference". The obvious next step
was to build the dependence-preserving replacement and calibrate it.

Building it surfaced something more basic than a calibration constant.

## The finding [本次实测 2026-08-01]

A gap of `h = 60` between blocks of length 60 consumes 120 trading days per independent
unit. On the committed per-date series that leaves:

| series | n dates | gap-separated blocks | df | t\*(.05) | t\*(Bonferroni 49) |
|---|---:|---:|---:|---:|---:|
| selftest pure_noise | 640 | 5 | 4 | 2.78 | **8.56** |
| inter142 certified_clf | 565 | 5 | 4 | 2.78 | **8.56** |
| inter142 prod_XGB | 448 | 4 | 3 | 3.18 | **12.84** |
| inter142 PatchTST | 565 | 5 | 4 | 2.78 | **8.56** |

The prereg's **3.29** is `Φ⁻¹(1 − 0.05/(2·49)) = 3.2848` — a **normal** quantile. At the df
a gap-honest scheme actually leaves, the corresponding Student bar is **8.56–12.84**, i.e.
the frozen bar is understated by **2.6×–3.9×** `[推导 from the two columns]`.

This is the "borrowed critical value on small n" shape: the block statistic is computed
correctly and then compared to a large-sample bar that its own df does not support.

## This is a POWER problem, not a threshold problem

Raising the bar to 8.56 does not rescue the design; it states its cost. A study with 4–5
independent units cannot resolve a small IC difference at a family-wise α over 49 tests,
whatever the bar is called. **That has to be on the record before anything is frozen**,
because a prereg that fixes a method without stating its power is how an underpowered run
becomes an "inconclusive" result that reads like evidence of absence.

## I am withholding my own size numbers

The tool also measures the empirical size of the naive gap=0 procedure by resampling the
re-centred series (H0 by construction — no alternative is touched). Those numbers are
**not published here**, because the instrument is degenerate at these donor counts: with
4–5 donor blocks, `prod_XGB` returned an *identical* size at two different bars
(`|t|>=1.96` and `|t|>=3.29`), which is the signature of a near-degenerate replicate
distribution, not a measurement. The code is committed so the limitation is auditable, and
it prints the donor count next to every size so no reader can take one without the other.

The reason the instrument is degenerate is the finding above: there is not enough
gap-separated data to bootstrap with.

## What this means for the merit prereg codex asked for

`[codex on orch#731]` asked for the complete merit preregistration — method, calibration
acceptance criteria, α, failure handling, provenance — to live in this repo. It cannot be
frozen as if the method choice were the only open question. Any such prereg must state,
up front, that a gap-honest scheme on the currently committed series has **df = 3–4**, and
either accept that power or change the design (longer series, shorter horizon, or an
estimand that does not require gap-separated daily blocks).

## Not claimed

That the gap=0 procedure's true size is any particular number — I withheld mine and said
why. That 8.56 is the right bar to adopt; it is what the *stated* family and α imply at
the *available* df, which is an argument about the design, not a recommendation to run at
that bar. That a gap of exactly `h` is sufficient — `lag_alignment.py` says gap ≥ h is
necessary and not sufficient, and nothing here changes that.
