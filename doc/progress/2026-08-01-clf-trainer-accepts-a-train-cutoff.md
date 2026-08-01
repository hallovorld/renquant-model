# GOAL-6 — the clf lane could not produce a walk-forward corpus, because its trainer had no cutoff

**Date:** 2026-08-01 · `renquant-model`

## The blocker, named mechanically

The GOAL-6 lane *"clf WF 语料补齐"* says the certified clf recipe has no out-of-sample
corpus. Measured earlier today: clf's recipe projection matches **0 of 85** walk-forward
corpus folds.

The reason is not scheduling. `scripts/train_topdecile_clf_shadow.py` took exactly three
arguments — `--data-dir`, `--out`, `--seed` — and `effective_train_cutoff()` computes the
cutoff as *"the max panel date actually trained on"*. It trained on whatever the data
directory held and then **reported where that ended**.

A walk-forward corpus is a series of **point-in-time** artifacts, each trained to a
different cutoff. **The lane could not make one** `[本次实测 2026-08-01]`.

## The change

`--train-cutoff YYYY-MM-DD`, defaulting to `None` (existing behaviour, unchanged — this
trainer already produced a deployed shadow artifact and altering that silently would
invalidate it).

`renquant_orchestrator.build_wf_manifest` builds the GBDT corpus by looping a fold schedule
and re-running `train_gbdt --train-cutoff` per cutoff. This gives the clf trainer the same
handle, so the **same schedule** can be looped for this recipe.

## The load-bearing detail: where the truncation goes

**Before `build_normalization`.** That function fits feature means/stds/clips on `train`.
Truncating *after* it would give every fold post-cutoff moments — a corpus that looks valid
and is worthless, which is worse than not having one. Two tests assert the ordering against
the source (`cut_at < norm_at`, and also before the label and the training matrix).

Three further properties, each pinned:

- **`<=`, not `<`** — a fold trained "to 2024-01-31" includes that session, which is what
  the GBDT schedule's cutoffs mean.
- **An empty result refuses**, rather than fitting on zero rows and cheerfully stamping a
  cutoff.
- **`effective_train_cutoff` then reports the truncated max**, so the stamp describes the
  fold rather than the data directory — a consequence of the ordering, and tested as one.
- `top_decile_label` ranks **within date**, so truncation cannot change the labels of rows
  it keeps. That is what makes a per-fold retrain comparable to the full one.

## Not done, and not claimed

**No corpus was built.** This supplies the missing handle; looping the schedule is a
compute run that needs its own prereg, and doing it here would be running before freezing.
That clf *should* have a corpus, or that having one would change any verdict — the
0-of-85 measurement says the evidence does not exist, not that it would be favourable.
Nothing about whether the clf lane's scores are any good.

## Tests

7. Suite: **1166 passed, 2 skipped**.
