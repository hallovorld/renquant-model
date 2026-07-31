# The runner already computes the per-date series and throws it away

**Date:** 2026-07-31 · `renquant-model` · GOAL-7 · implements the §7 requirement added to `model#128`

STATUS:    additive output + 8 tests. **Computes nothing new. Default OFF.**
WHAT:      `--per-date-out` writes the per-date statistic series the run already
           produced (`per_date_e2` for the subject and baseline arms) to CSV.
WHY/DIR:   Without it, the programme's own dependence assumption cannot be checked
           against its own data — see §1.

EVIDENCE:  §4(b) block; model-specific fields filled and marked.

```
artifact:      tools/momentum_total_return_run.py (new writer + CLI flag)
prod or exp:   experiment — research runner; no production artifact, no scorer
existing data: `per_date_e2(sub, arm, ycol) -> pd.Series` already exists at line 299
               and is called twice (subject, baseline) at the paired-contrast site.
               Persisted output today: summary JSON + `robustness.json.block_means`
               (10 values). No per-date row is written anywhere.
               [VERIFIED — this session]
best-known?:   NOT APPLICABLE as a model-variant comparison — nothing is trained,
               fitted or scored. As a fix: the minimal one — persist what exists,
               rather than adding a computation a frozen harness would have to
               re-justify.
scope:         "this is tools/momentum_total_return_run.py, EXPERIMENT, an additive
                write behind a default-off flag; every statistic, verdict and gate
                is unchanged, and a run without the flag is byte-identical."
```

NEXT:      Pass `--per-date-out` on the next GOAL-7 run. Then the dependence
           calibration is exact for the harness and needs no `rho1` from elsewhere.

## 1. Why this matters more than its size

`model#128` §7 recorded the measurement that motivates it:

- **GOAL-4's Phase-0 screen persisted `per_date_g_real.csv`** (508 rows). That one file
  made a **model-free, assumption-free** dependence-preserving calibration possible —
  bootstrap the real series, no `rho1` assumed anywhere.
- **This runner persisted 10 block means.** Their lag-1 autocorrelation has a standard
  error of `1/sqrt(10) = 0.316` `[DERIVED]`, so it **cannot separate `rho1 = 0` from
  `rho1 = +0.5`** — underpowered by an order of magnitude against the effect it would
  need to detect. Every MDE in the redesign's §3.1 therefore stays conditional on a
  `rho1` measured on a **different** programme.

One CSV (~16 KB at GOAL-4's size) removes that conditionality permanently.

## 2. Why it is safe to add to a frozen harness

The writer is a **pure read**: it takes series the run has already produced, aligns
them on date, sorts, and writes. It computes no statistic and touches no gate. The
flag defaults to `None`, so a run without it is byte-identical to today's.

The test that enforces this is `test_writing_CANNOT_alter_the_series` — if
persistence ever mutates its inputs, the feature is changing the run it was added to
observe, and that test fails.

## 3. Two real properties, not just happy paths

- **Alignment is on date, not position.** Subject and baseline have different date sets
  in the real run (`common = subj.index.intersection(base.index)` a few lines below the
  write site), so a positional write would silently pair unrelated dates.
- **An empty series still writes a readable file.** A run with no admissible dates must
  leave evidence *of that*, not nothing — the same reason a refusal is not a skip.

## 4. Mutation check

| mutation | tests that fail |
|---|---:|
| drop `sort_index()` | **1** |
| stop filtering `None` series | **1** |

8 tests pass; `--help` shows the flag; the module parses.

## 5. What this does NOT do

It does not run anything, does not change any published number, and does not make the
existing void Stage-1 result reconstructible — that run is gone. It makes the **next**
one checkable.

## Review round 1 — the artifact persisted the ingredients, not the series tested

Codex: the CSV was written **before** the runner formed
`common = subj.index.intersection(base.index)` and `dpair = (subj - base).dropna()`,
so a later reader had to guess that alignment, and a different guess yields a different
calibration — the exact thing this file exists to prevent.

Fixed by moving the write **after** `dpair` exists and persisting it as its own
`paired_contrast` column, with `subject` and `baseline` kept beside it so the contrast
can be *checked* rather than trusted.

**A sidecar `<name>.meta.json`** now carries what is needed to read the CSV without
this source file: subject and baseline arm names, label column and horizon, the
statistic, both input sha256 pins, and an explicit
`paired_contrast_definition` telling the reader **not** to re-derive the column.

**One correction to my own first test.** I wrote
`test_the_contrast_is_NOT_recoverable_by_naive_subtraction` — and it failed, because
pandas aligns on subtraction, so `(subj - base).dropna()` equals the runner's
intersection-then-dropna **exactly**. My anti-vacuity check caught my own overstatement
of the defect.

The real gap is narrower and still real: **the reader must guess which operation was
performed.** Reconstructions that are entirely reasonable a priori — filling the gaps
instead of dropping them, or keeping the union — give a different series and therefore
a different calibration. The replacement test asserts that the equivalent
reconstruction *is* equivalent (so the record is honest) and that those two plausible
alternatives *do* diverge (so the persisted column is load-bearing).

Ordering is also pinned in the source itself: `test_the_runner_writes_AFTER_forming_dpair`
fails if a future edit hoists the write back above the intersection, which would
re-create the ambiguity without breaking any value assertion.

**And the first version of that load-bearing claim was false.** I wrote in the commit
that dropping `paired=dpair` fails the suite. It did not: **12 tests still passed.**
Every value test calls `write_per_date_series` directly, so they verify the *writer*
and say nothing about whether the *runner* still hands it the paired series. A correct
writer plus a call site that stopped using it is exactly the regression this PR is
about, and nothing would have caught it.

Added `test_the_runner_actually_PASSES_dpair_to_the_writer`, which asserts the call
site. Re-verified properly: with `paired=None` the suite now reports **1 failed / 12
passed**, and **13 passed** on restore `[VERIFIED — both runs this session]`.

The claim in commit `5c85708` was wrong when written and is corrected here rather than
quietly fixed — I checked load-bearing, got an answer that contradicted what I had
already written, and the honest move is to record that the check found something.
