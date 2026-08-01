# Feasibility: gap-separating these series leaves 4–5 blocks, which cannot support the intended prereg

## What was being attempted

model#154 showed the frozen v1-vs-v2 Stage-A gate (`|t| >= 3.29`) is produced by
`dependence_aware_mean`, whose blocks are contiguous with **gap = 0** and whose own
docstring says it "must not present the comparison as inference". The obvious next step
was to build the dependence-preserving replacement and calibrate it.

Building it surfaced something more basic than a calibration constant.

## Reframed after review `[codex on model#155]`

> *"it still converts that necessary spacing condition into an independent-unit df and
> Student critical value … df=3–4 and the 8.56/12.84 bars are conditional illustrations,
> not valid inferential thresholds."*

Correct, and it is the defect this programme keeps cataloguing, committed by me: I took a
**necessary** condition (gap ≥ h) and spent it as though it were **sufficient**, deriving
df and a Student bar from a block count. Removing shared label windows does not remove
predictor persistence, common factor exposure, or longer-range dependence — my own "Not
claimed" section said so and the table above it ignored it.

So this is a **feasibility / power diagnostic**, not a gap-honest test, and the bracketed
bars below are illustrative of what *would* follow *if* the blocks were independent —
which is not shown.

## The measurement [本次实测 2026-08-01]

A gap of `h = 60` between blocks of length 60 consumes 120 trading days per independent
unit. On the committed per-date series that leaves:

| series | n dates | gap-separated blocks | *(if independent)* df | *(illustrative)* t\*(.05) | *(illustrative)* t\*(Bonf 49) |
|---|---:|---:|---:|---:|---:|
| selftest pure_noise | 640 | 5 | 4 | 2.78 | **8.56** |
| inter142 certified_clf | 565 | 5 | 4 | 2.78 | **8.56** |
| inter142 prod_XGB | 448 | 4 | 3 | 3.18 | **12.84** |
| inter142 PatchTST | 565 | 5 | 4 | 2.78 | **8.56** |

The load-bearing number is the middle column: **4–5 blocks**. That is how much material a
scheme that merely removes direct label overlap would have to work with on the currently
committed series.

The bracketed columns are **not thresholds**. They say what a Student bar would be if those
4–5 blocks were independent, and nothing here establishes that they are. The prereg's
**3.29** is `Φ⁻¹(1 − 0.05/(2·49)) = 3.2848`, a **normal** quantile; the honest statement is
not "the right bar is 8.56" but **"no bar is currently justified, and there is very little
material to justify one with."**

## This is a POWER problem, and not one a different threshold fixes

Raising the bar does not rescue the design. Whatever null is eventually justified, it will
be built on 4–5 gap-separated blocks, and a family-wise α over 49 tests on that much
material cannot resolve a small IC difference. **That has to be on the record before anything is frozen**,
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
why. That 8.56/12.84 are applicable bars — they are illustrations of an independence
assumption that is **not** established, kept only to show the order of magnitude the
design would have to clear. That a gap of exactly `h` is sufficient — `lag_alignment.py` says gap ≥ h is
necessary and not sufficient, and this document's first revision violated its own caveat
on exactly that point.
