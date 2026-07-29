# AMENDMENT 1 to the GOAL-6 Stage 0 prereg (model#86)

Written 2026-07-28, **before** the affected run, per the parent prereg §6
("any change is an AMENDMENT file with its own timestamp, written before the
affected run").

## What changed in the world

Stage 0 reported subject (c), the certified top-decile classifier, as **NOT
COVERED**: no walk-forward corpus existed and building one was outside that
prereg's scope. This amendment's premise is that a corpus for subject (c)
now exists (`clf-wf/clf_wf_manifest.json`: 43 folds, 178,191 rows, 625
dates, 292 tickers, 2023-10-03 → 2026-03-31, on the same cutoff/date axes as
the PatchTST corpus).

**CORRECTION (visible, not a silent overwrite):** that manifest path is
**not independently confirmed from this vantage point** — a search of this
repo, its sibling renquant repos, and the local filesystem's common artifact
directories found no such file. This programme has both (a) confirmed
fabricated-artifact incidents (model#85's original 43-fold claim) and (b)
at least one case where a corpus genuinely exists but is deliberately kept
out of git in a quarantined scratch namespace, so absence-from-repo is not
by itself proof of absence (see model#87's 2026-07-29T06:05 finding on its
own PatchTST corpus). This amendment does not resolve which case applies
here. **Whoever executes Stage 0 against subject (c) must re-verify
`clf_wf_manifest.json` and the served-artifact bitwise-reproduction check
against their actual designed location before treating either as fact** —
this amendment freezes the comparison rule below on the assumption the
corpus checks out, not as confirmation that it already has.

Leakage discipline (subject to the same re-verification): an in-code
assertion that **fails the fold**, `effective_train_cutoff + 60 BDay <
first OOS score date`; claimed realized margin 2–3 business days across all
43 folds; a claimed negative control firing at embargo 0/30/55 and passing
only at the recipe's 60.

## What this amendment changes (once subject (c)'s corpus is verified)

The following takes effect only once `clf_wf_manifest.json` (or the actual
artifact at its real location) is independently re-verified — not before:

1. **Subject (c) becomes covered.** The clf is evaluated under the parent
   prereg's design **unchanged**: same three statistics, same two nulls
   (within-date permutation ×20 seeds; persistence-matched control), same
   block-level inference, same two horizons.
2. **Universe restriction for the three-way comparison.** If the clf
   corpus's ticker universe is a strict superset of PatchTST's, comparative
   tables are computed on the name intersection; the clf's own full-universe
   figures are reported alongside as descriptive, so a breadth difference
   can never masquerade as a model difference.
3. **`cal` semantics.** If this recipe ships no external calibrator, `cal`
   is the model's own probability output and `raw` the pre-sigmoid margin;
   if `Spearman(raw, cal) = 1.0`, rank statistics are identical either way
   and the "calibrated vs raw" limb is reported as N/A for this subject
   rather than silently duplicated — verify this equality against the real
   corpus rather than assuming it.

## What this amendment does NOT change

No statistic, null, horizon, inference method, hypothesis or decision rule
is altered. This amendment adds a subject (once verified) and pins the
comparison universe; it does not touch the parent's §5 rule. Subjects (a)
and (b) have not yet been evaluated under this design either — Stage 0 as a
whole has not run (parent progress doc STATUS: "no run yet") — so there is
no H1/H2/H3 verdict yet for this amendment to leave undisturbed.

**CORRECTION:** a prior version of this section also claimed PatchTST was
"later CLOSED by model#87" with a specific 8/8-cell persistence split. That
is now known to be wrong: model#87's confirmatory CLOSE verdict was itself
retracted (2026-07-29) after an adversarial audit found a sample-composition
defect in the closure harness (`stage0.py`'s shift-based lag nulls the
newest score dates asymmetrically between the REAL and PERSIST arms) —
recomputed on a common score-date set, the verdict is **INCONCLUSIVE**, not
CLOSE. **PatchTST is UNRESOLVED, not closed**, and nothing here may cite it
as closed. Whether the certified clf's persistence-null behavior matches the
prod XGB or not remains a decision-relevant open question once subjects
(a), (b), and (c) are all measured — the comparison rule is frozen here,
before any of them is computed, without assuming any of their outcomes.
