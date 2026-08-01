# Feasibility: gap-separating these series leaves 4–5 blocks

Supersedes the branch closed as model#155. Written from scratch rather than patched —
the closed branch was a partial edit that left one sentence still asserting the thing the
review rejected, and I reported it as reframed without checking the old wording was gone.

## What the review asked for

`[codex on model#155]`:

> it still converts that necessary spacing condition into an independent-unit df and
> Student critical value … Reframe the document/tool output as a gap-separated
> feasibility/power diagnostic; do not call it a gap-honest block test or report a Student
> bar as applicable until the block-independence/null-calibration assumption is justified.
> Keep the sound conclusion that the present series cannot support the intended
> preregistration.

Both points accepted. Spacing blocks by at least the label horizon removes **shared label
windows** and nothing else. Predictor persistence, common factor exposure and longer-range
dependence all survive it, so spaced blocks are not shown to be independent, and no degrees
of freedom follow from counting them.

## The measurement `[本次实测 2026-08-01]`

How much material would a scheme that removes direct label overlap have to work with, at
`gap = h = 60` on the committed per-date series?

| series | n dates | **gap-separated blocks** |
|---|---:|---:|
| selftest pure_noise | 640 | **5** |
| inter142 certified_clf | 565 | **5** |
| inter142 prod_XGB | 448 | **4** |
| inter142 PatchTST | 565 | **5** |

That count is the finding. A gap of 60 between blocks of 60 costs 120 trading days per
retained block, so a ~2-year daily series yields single digits.

The tool also prints, in brackets and labelled `[illustrative only]`, the Student values
that *would* apply *if* those blocks were independent. **They are not applicable
thresholds** and are not quoted here as numbers to clear; they are printed solely to show
the order of magnitude such a design would face, and the tool says so in its own output.

## Why this settles the preregistration question

The v1-vs-v2 Stage-A gate is preregistered at `|t| ≥ 3.29`, which is
`Φ⁻¹(1 − 0.05/(2·49))` — a large-sample **normal** quantile over a 49-test family. Whatever
null is eventually justified for these arms, it will be built from **4–5** spaced blocks.
A family-wise α over 49 tests, on that much material, cannot resolve a small IC
difference.

So the honest statement is **not** "the bar should be higher". It is:

* no bar is currently justified, because block independence is not established; and
* there is very little material with which to justify one.

**The present series cannot support the intended preregistration.** That conclusion is
unchanged from the closed branch and is the part worth keeping.

## My own size numbers are withheld

The tool can also measure the empirical size of the naive `gap = 0` block-t by resampling
the re-centred series (H0 by construction — no alternative is touched). Those numbers are
**not published**: at 4–5 donor blocks the resampling is degenerate, and `prod_XGB`
returned an *identical* size at two different bars, which is a signature of a degenerate
replicate distribution rather than a measurement. The code ships anyway so the limitation
is auditable, and it prints the block count beside every size so neither can be read alone.

The reason it is degenerate is the finding above: there is not enough spaced material to
resample.

## Not claimed

That the spaced blocks are independent — that is exactly what is *not* established, and it
is why no threshold is asserted anywhere in this document. That the naive procedure's true
size is any particular number. That `gap = h` is the right spacing; the necessary
condition is `gap ≥ h`, and necessity is not sufficiency. That a longer series would fix
it — that is arithmetic worth doing, not a result.
