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
different cutoff. **The lane's CLI could not make one** `[本次实测 2026-08-01]`.

> **CORRECTION 2026-08-01.** The original sentence read *"the lane could not make one"*.
> That is false and is withdrawn. It is true of the **CLI** and false of the **lane**: a
> clf walk-forward corpus was built on 2026-07-29 and is committed in this repo at
> `doc/research/data/2026-07-29-clf-wf-closure-bundle/artifacts/clf-wf/`. Re-measured from
> the parquet itself, not from its manifest `[本次实测 2026-08-01]`: **178,191 rows, 43
> folds, 625 distinct OOS dates (2023-10-03 … 2026-03-31), 292 tickers**, every row
> labelled, `cal` ∈ (0.0147, 0.5006) with mean **0.0949** — a `binary:logistic`
> probability against a 0.10 base rate, i.e. clf's own output and not a `rank:pairwise`
> score. The 07-29 driver bypassed the CLI: it `importlib`-loads the trainer module and
> does the walk-forward slicing itself.
>
> The corpus reuses the GBDT manifest's 43-cutoff **grid** as its date axis (the driver
> asserts `len(cutoffs) == 43`) but **retrains the clf recipe at each cutoff**. Only the
> axis is shared — this is not the earlier error of quoting the GBDT lane's 43 folds as
> clf's.

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

**No corpus was built _by this change_.** This supplies the missing CLI handle; looping
the schedule is a compute run that needs its own prereg, and doing it here would be
running before freezing. A corpus built by a different route already exists — see the
correction above — so the absolute form of this sentence is withdrawn.
That clf *should* have a corpus, or that having one would change any verdict — the
0-of-85 measurement says the corpus the GATE reads contains no clf-recipe fold, which is
a statement about **gate admissibility**, not about whether out-of-sample evidence exists
at all — the 07-29 bundle shows it does. Neither says the evidence would be favourable.
Nothing about whether the clf lane's scores are any good.

## Tests

7. Suite: **1166 passed, 2 skipped**.
