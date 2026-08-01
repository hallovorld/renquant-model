# Amendment 2a — which v2 column is "the real filed date"? Measured, not chosen

**Date:** 2026-08-01 · `renquant-model` · GOAL-6 main line (v1-vs-v2 PIT A/B)

## The blocker this addresses

`tools/v1_v2_pit_ab_run.py` **aborts at startup** until Amendment 2a is implemented in
code. 2a requires `restamp_v1()` to join v1's values to **v2's real `filed` date per
fact**, replacing the retired `+60d` synthetic constant — and it leaves the column
explicitly **TBD**:

> *"column name TBD against v2's actual schema — **not guessed here** to avoid shipping a
> second silently-wrong implementation"*

That refusal was correct. `data/edgar_pit/` offers **three** date columns, and they are not
interchangeable.

## Measured `[本次实测 2026-08-01]`

`tools/v2_filed_column_census.py` (committed with this doc), against
`RenQuant/data/edgar_pit/`:

| file | column | rows | distinct tickers |
|---|---|---:|---:|
| `filing_dates.parquet` | `filing_date` | 36,564 | **831** |
| `asfiled_period_records.parquet` | `avail` | 34,629 | 788 |
| `available_at_v2.parquet` | `available_v2` | 12,361 | **272** |

| pair | joined | identical | median Δ | max Δ |
|---|---:|---:|---:|---:|
| `filing_date` vs `available_v2` | 12,361 | **8.5%** | **−1 d** | 1 d |
| `filing_date` vs `avail` | 32,411 | **0.0%** | −1 d | 60 d |
| `available_v2` vs `avail` | 10,807 | 88.8% | 0 d | 633 d |

## What the numbers say

**`available_v2` and `avail` are availability stamps, not filing dates.** Against
`filing_date` they are systematically **one day later** — 8.5% and 0.0% identical with a
median Δ of −1 day. A uniform +1 day is a **convention** (next-day availability), which is
the correct thing for an availability column to be and the wrong thing for "the real
`filed` date" to be.

**Coverage is the part that would have bitten silently.** `available_v2` covers **272**
distinct tickers. The prereg's common support is **515 names**. Joining `restamp_v1()`
against it would have **shrunk the `B_v1_lag` arm below the registered support** while
every other arm kept 515 — the exact "silently-wrong implementation" 2a was written to
avoid, and invisible in any summary that reports only ICs.

`filing_dates.filing_date` is the only literal filed date and the only candidate whose
coverage (831) exceeds the registered support.

## What this does NOT do

**It does not choose.** Selecting the column is an amendment to a frozen prereg and
belongs in that document, argued against these numbers — not decided in a tool that was
written to inform the decision. The census exits **non-zero while the candidates
disagree**, so "the TBD is resolved" cannot be inferred from a green run.

It also does not run Stage A, touch the runner's abort, or make any claim about v1 vs v2.

## A number of mine this supersedes

An interactive pass earlier in this session reported the `filing_date` ↔ `available_v2`
delta as **median +1, max 634**. The committed script reports **median −1, max 1**. Both
differences are explicable — the sign is subtraction order, and the max collapses because
the committed join also keys on `form`, which the ad-hoc one did not.

**The committed number supersedes the ad-hoc one.** That is the whole reason this ships as
a script: the prereg's own EVIDENCE block records that the 90.37% / 77.6% / 515 figures
were *"measured ad hoc, interactively"* with *"no committed script"*, and an unrepeatable
number is an assertion with a citation attached — including when it is mine, and including
when it is only off by a join key.
