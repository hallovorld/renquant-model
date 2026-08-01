# Progress: momentum runner, Stage A (GOAL-7) — STACKED ON model#167

WHAT: `tools/goal7_momentum_run.py` — precondition verification + feature assembly for
the frozen prereg (model#164 + Amendment 1 pending as model#168). `--execute` REFUSES
(exit 4) until the inference stage lands in a follow-up revision; `--preflight` verifies
every §2/§7 precondition and prints the JSON verdict.

LIVE PREFLIGHT `[本次实测 2026-08-01]`: on this branch the prereg/amendment docs are
absent (branch bases predate the #164 merge) → correctly UNRESOLVED-DATA, exit 3 — while
all four pinned digests VERIFY against today's tree (panel, sector snapshot, hac_se.py,
combined OHLCV over 292/292). The refusal path and the digest path are both exercised by
reality before any review.

RUNNER-DECLARED CONSTANT, as the prereg delegated: `MIN_SIDE_OBS = 30` for F5's per-side
beta floor. Justified by measurement, not taste: the minimum down-day count in ANY
rolling 252-day SPY window since 2016 is **97** (p1 = 99; minimum up-day count 108)
`[本次实测]` — 30 is a pure OLS-validity floor no realized calendar window approaches;
it can bind only via missing data, where nan → the ≥3-of-5 rule is the designed path.

DEPENDENCIES, explicit: stacked on #167 (the feature engine — merge it first); implements
the AMENDED F1 and therefore refuses on a tree without Amendment 1 (model#168). The
validated TR construction is IMPORTED from `tools/build_total_return_series.py`, never
restated.

Tests: 4 runner (assembly counts/visibility/nan discipline; execute-refusal; usage;
the declared constant bounded by the measurement) + the 9 engine tests. No IC, no label
statistic, no real-data scoring anywhere.
