# AMENDMENT 1 to the GOAL-6 Stage 0 prereg (model#86)

Written 2026-07-28, **before** the affected run, per the parent prereg §6
("any change is an AMENDMENT file with its own timestamp, written before the
affected run").

## What changed in the world

Stage 0 reported subject (c), the certified top-decile classifier, as **NOT
COVERED**: no walk-forward corpus existed and building one was outside that
prereg's scope. A corpus now exists
`[VERIFIED — clf-wf/clf_wf_manifest.json]`: 43 folds, 178,191 rows, 625
dates, 292 tickers, 2023-10-03 → 2026-03-31, on the SAME cutoff and date
axes as the PatchTST corpus (set-equal, zero symmetric difference).

Recipe fidelity is proven rather than asserted: a full-sample fit through
the driver's exact code path reproduces the SERVED artifact
`panel-clf.top-decile.fwd60.json` **bitwise** (identical `booster_raw_json`,
max absolute prediction difference **0.0** over 20k rows). The folds are the
same recipe, windowed.

Leakage discipline: an in-code assertion that **fails the fold**,
`effective_train_cutoff + 60 BDay < first OOS score date`; realized margin
2–3 business days across all 43 folds; a negative control fires at embargo
0/30/55 and passes only at the recipe's 60.

## What this amendment changes

1. **Subject (c) becomes covered.** The clf is evaluated under the parent
   prereg's design **unchanged**: same three statistics, same two nulls
   (within-date permutation ×20 seeds; persistence-matched control), same
   block-level inference, same two horizons.
2. **Universe restriction for the three-way comparison.** The clf corpus
   carries 292 tickers against PatchTST's 142, and the 142 are a strict
   subset. Comparative tables are computed on the **142-name intersection**;
   the clf's own 292-name figures are reported alongside as descriptive, so
   a breadth difference can never masquerade as a model difference.
3. **`cal` semantics recorded.** This recipe ships no external calibrator:
   `cal` is the model's own `binary:logistic` probability (the served score)
   and `raw` the pre-sigmoid margin, with Spearman(raw, cal) = 1.0 exactly.
   Rank statistics are therefore identical either way; the "calibrated vs
   raw" limb is reported as N/A for this subject rather than silently
   duplicated.

## What this amendment does NOT change

No statistic, null, horizon, inference method, hypothesis or decision rule
is altered. This amendment adds a subject and pins the comparison universe;
it does not touch the parent's §5 rule, and it cannot be used to revisit the
H1/H2/H3 verdicts already recorded for subjects (a) and (b).

The prior finding that matters most carries over as the thing to check
first: the persistence-matched null split PatchTST (negative in 8/8 cells,
later CLOSED by model#87) from the prod XGB (positive in 8/8). Whether the
certified clf behaves like the model that survived or the model that did not
is the single most decision-relevant number in the programme, and it is
frozen here before it is computed.
