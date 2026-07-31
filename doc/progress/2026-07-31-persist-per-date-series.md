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
