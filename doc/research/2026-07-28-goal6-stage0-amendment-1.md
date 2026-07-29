# AMENDMENT 1 to the GOAL-6 Stage 0 prereg (model#86)

Written 2026-07-28, **before** the affected run, per the parent prereg §6
("any change is an AMENDMENT file with its own timestamp, written before the
affected run").

## What this amendment adds

A future-artifact contract for a possible third subject, (c) the certified
top-decile classifier, alongside the parent's subjects (a) and (b). This
amendment asserts NO corpus, NO coverage figure, and NO prior result for
subject (c) — none of those are settled from this vantage point, and per
this project's control contract a no-run prereg may not carry any such
claim, hedged or not. What follows is a contract: IF a corpus for subject
(c) is later verified to exist, THEN it is admitted under the rules below;
nothing about its existence, size, or any measurement of it is asserted
here.

## Admission contract (frozen; applies only once independently satisfied)

Subject (c) becomes covered by Stage 0 only when ALL of the following are
verified, at execution time, by whoever runs Stage 0 — not assumed from any
prior PR, comment, or draft:

1. **Resolvable artifact.** An explicit, checked-in artifact path AND git
   commit/run-id, OR an explicit scratch path with a recorded content hash,
   naming subject (c)'s walk-forward scoring corpus. A path that cannot be
   resolved and hashed at execution time does not satisfy this contract.
2. **Fold-count and date-axis parity.** The corpus's fold count and cutoff
   dates are read directly from its own manifest at execution time and
   reported in the results doc — not carried over from any earlier draft —
   and must share the same date axis as subjects (a)/(b) for the
   cross-sectional universe restriction in item 4 below to apply.
3. **Leakage discipline**, checked directly against the actual artifact,
   not assumed: an in-code (or equivalent, directly-run) assertion that
   `effective_train_cutoff + 60 BDay < first OOS score date` fails for any
   fold that violates it; the realized embargo margin per fold is measured
   and reported, not stated in advance; a negative control at embargo 0
   must be checked and must NOT pass under the same rule that a positive
   embargo passes.
4. **Universe restriction for the three-way comparison.** If the clf
   corpus's ticker universe is a strict superset of subjects (a)/(b)'s,
   comparative tables are computed on the name intersection; the clf's own
   full-universe figures are reported alongside as descriptive, so a
   breadth difference can never masquerade as a model difference.
5. **`cal` semantics.** If this recipe ships no external calibrator, `cal`
   is the model's own probability output and `raw` the pre-sigmoid margin;
   if `Spearman(raw, cal) = 1.0` (checked directly against the real
   corpus, not assumed), rank statistics are identical either way and the
   "calibrated vs raw" limb is reported as N/A for this subject rather than
   silently duplicated.

## What this amendment does NOT change

No statistic, null, horizon, inference method, hypothesis, or decision
rule from the parent prereg is altered. This amendment only adds an
admission contract for a possible third subject; it does not touch the
parent's §5 rule. Subjects (a) and (b) have not been evaluated under this
design either — Stage 0 as a whole has not run (parent progress doc
STATUS: "no run yet") — so there is no H1/H2/H3 verdict of any kind for
this amendment to reference, disturb, or presuppose. PatchTST (model#85 /
model#87) is not part of Stage 0 under any subject label; its own status
is tracked and resolved entirely on its own PRs, not here.
