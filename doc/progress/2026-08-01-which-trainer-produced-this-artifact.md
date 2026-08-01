# GOAL-3 R3 — re-measured today, still true, and now runnable

**Date:** 2026-08-01 · `renquant-model`

## R3 re-measured

The twin registry's R3 records three trainers for one model and says the pinned
orchestrator one is what runs. Both identification signatures re-checked against the served
`prod/panel-ltr.alpha158_fund.json` `[本次实测 2026-08-01]`:

| signature | measured | verdict |
|---|---|---|
| `training_notes` | exactly `alpha158 + SEC fund panel-LTR, self-contained subrepo training` | matches `train_gbdt.py:354` |
| `params` keys | 8, **no `nthread`** | `train_production_model.py:58` hardcodes `"nthread"` in the dict, so its output cannot lack it — **ruled out** |

All three trainer files still exist. **R3 holds.**

## A citation that had drifted

The registry cites `train_gbdt.py:228` for the notes literal. It is now at **:354**. A
registry whose value is that its citations are *checkable* should be corrected — noted
here, not done here, because the registry lives in `renquant-orchestrator`.

## Why make it runnable

R3's cost line: *"I pointed a delegated retrain at the wrong twin **twice** before this was
settled; its metadata came out non-production-shaped (`nthread: 14`)."* It was settled by a
hand-read. `tools/artifact_producer_signature.py` makes the same read mechanical, so a
third mis-pointing is caught by running something rather than by remembering.

## The claim is deliberately bounded

It reports **`consistent_with`**, never **`produced_by`** — asserted by a test over the
source, not promised in prose. A signature is evidence about the **shape of the output**,
not a record of which process ran; two trainers could converge.

`undecidable` is a real verdict in **both** directions:

- matching **several** profiles → undecidable, not a pick;
- matching **none** → undecidable, *not* "produced by none". An artifact that matches
  nothing has not been attributed, and has not been shown to come from outside the three.

And a subtlety the tests pin: **`nthread` being present does not rule the orchestrator
trainer out** — `train_gbdt.py` adds it only when `--nthread` is passed (`:327`). It merely
stops ruling the umbrella trainer out, after which both match and the honest answer is
`undecidable`. Reading presence as exclusion would have inverted the signature.

## Not claimed

That the served artifact was produced by `train_gbdt.py` — only that its shape is
consistent with that trainer and inconsistent with the umbrella one. That the third trainer
(`panel_trainer.py`) is excluded; it has no distinguishing signature encoded here and is
therefore not profiled rather than silently cleared.

## Tests

11. Suite: **1177 passed, 2 skipped**.
