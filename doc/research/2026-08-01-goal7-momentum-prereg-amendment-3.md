# Momentum prereg — Amendment 3 (visible, PRE-RUN): the pinned inputs refresh daily; paths move to a verified snapshot

**Amends §2's input PATHS only. Every digest is unchanged. Filed before any execution.**

## The defect, discovered by an unrelated failure `[本次实测 2026-08-01]`

Running the clf bundle's committed `verify_recipe_fidelity.py` failed on feature-means
mismatch — and the root cause was not infidelity but **input drift**: its manifest pinned
panel `7c0c6447…`, while today's panel is `55811f63…`, because
`data/alpha158_291_fundamental_dataset.parquet` is refreshed by the daily job (it ran
this morning at 05:30 and grew 352,838 → 354,258 rows this week).

The momentum prereg pinned **that same daily-moving file**. Its own UNRESOLVED-DATA rule
— correct as a tamper guard — therefore gives the study an execution window that closes
at the **next daily refresh (~05:30 tomorrow)**, after which every execution fails on a
routine refresh indistinguishable, to the rule, from corruption. A freeze that pins a
moving path pins a deadline, not an input.

## The remedy, executed before this filing

The exact pinned bytes were still on disk. They are snapshotted to the experiment area
(the `data/exp/` corpus space, additive, nothing overwritten):

```
data/exp/momentum_prereg_inputs_20260801/
  panel.parquet          sha256 55811f63…  == the frozen §2 pin, byte-identical
  ticker_sectors.json    sha256 ec26bb1e…  == the frozen §2 pin, byte-identical
  ohlcv/<T>/1d.parquet   combined digest 4d4638a9…  == the frozen §2 pin (292/292)
```

All three verified equal by recomputation at copy time `[本次实测]`; total 791 MB.

## The amendment (paths only; digests, list, and rule untouched)

§2's input paths become the snapshot paths above. The digests are IDENTICAL, so the
runner's verification arithmetic does not change by a byte; the UNRESOLVED-DATA rule
keeps guarding against tamper and loss, and stops encoding a hidden deadline.

## Not claimed

That the daily refresh is wrong — it is the pipeline working. That the clf bundle's
fidelity NO VERDICT is discharged — the opposite: it is now **permanently unverifiable
as committed** (its pinned panel bytes no longer exist anywhere), which is recorded here
as the cost of pinning moving paths without snapshotting, and is exactly what this
amendment prevents for the momentum study.
