# The gap-separated-block construction has 4–5 blocks to work with on these series

**Scope: this diagnostic is about ONE construction, not about the series.** It measures how
much material a scheme that spaces blocks by at least the label horizon would retain. It
says nothing about what a validated HAC estimator, a dependence-preserving bootstrap on the
full series, or a differently precommitted estimand could do with the same data.

## Why this is a third PR, and it was not a content problem

model#156 was closed with *"the requested method-scope correction was not applied. It
still says the present series cannot support the intended preregistration."* That was true
of what the reviewer could see and false of the branch.

The correction **was** committed (`6829e36`) and pushed. What was not updated was the **PR
description**: `gh pr create --body "$(cat <doc>)"` snapshots the file at creation time and
subsequent pushes do not refresh it. So the commit said one thing and the PR body said the
superseded thing, and the PR body is what gets read first.

I had verified the pushed *file* before reporting — the right object for a different
question. Recording it here because "the artifact I fixed is not the artifact under review"
is the same shape as the defects this document is about.

## Review history, because each round narrowed a real overreach

`[codex on model#155]` — the first version converted a **necessary** spacing condition into
an independent-unit df and a Student critical value. Spacing removes shared label windows
and nothing else; predictor persistence, common factor exposure and longer-range dependence
survive it, so spaced blocks are not shown to be independent and no degrees of freedom
follow from counting them. Accepted; no threshold is asserted anywhere below.

`[codex on model#156]`:

> 4-5 spaced blocks do not establish that the committed series as a whole cannot support
> any intended preregistration. A validated HAC, bootstrap, or differently precommitted
> estimand could use the full dependent series … avoid the unsupported assertion that a
> 49-test family cannot resolve a small difference without a defined effect size and valid
> null.

Also accepted, and both halves were mine to fix. I had written "the present series cannot
support the intended preregistration" — a statement about the *data* derived from a fact
about *one construction* — and I had asserted a power conclusion with no effect size and no
valid null in hand. Both are removed rather than softened.

## The measurement `[本次实测 2026-08-01]`

At `gap = h = 60`, spacing consumes 120 trading days per retained block. On the committed
per-date series:

| series | n dates | spaced blocks retained |
|---|---:|---:|
| selftest pure_noise | 640 | **5** |
| inter142 certified_clf | 565 | **5** |
| inter142 prod_XGB | 448 | **4** |
| inter142 PatchTST | 565 | **5** |

The tool additionally prints, bracketed and labelled `[illustrative only]`, the Student
values that *would* apply *if* those blocks were independent. They are **not applicable
thresholds**, they are not quoted here as numbers to clear, and the tool states so in its
own output.

## What this does and does not license

**Does:** it rules out the gap-separated-block construction as the basis for the proposed
small-effect Stage-A test on these series — 4–5 retained blocks is very little material for
that route, and the route's own necessary condition is all it buys.

**Does not:** it does not evaluate the series. A validated HAC standard error, a
dependence-preserving bootstrap over the full dependent series, or a re-specified estimand
are untouched by this measurement and remain open.

**No power claim is made.** Assessing whether any family size can resolve a difference
requires a defined effect size and a valid null, and this document has neither.

## My own size numbers are withheld

The tool can also measure the empirical size of the naive `gap = 0` block-t by resampling
the re-centred series (H0 by construction — no alternative is touched). Those numbers are
**not published**: at 4–5 donor blocks the resampling is degenerate, and `prod_XGB`
returned an *identical* size at two different bars, which is a signature of a degenerate
replicate distribution rather than a measurement. The code ships so the limitation is
auditable, and it prints the block count beside every size so neither can be read alone.

## Not claimed

That spaced blocks are independent — that is exactly what is not established, which is why
no threshold appears here. That the series cannot support inference. That the naive
procedure's true size is any particular number. That `gap = h` is the correct spacing; the
necessary condition is `gap ≥ h`, and necessity is not sufficiency.
