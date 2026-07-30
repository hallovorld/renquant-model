# SCREEN DESIGN (FROZEN): can a volatility-conditioned momentum/reversion blend beat either alone?

**Frozen:** 2026-07-29, **before any arm was computed.** This revision of the
document contains **NO result**. The git history of this branch is the evidence:
the design commit precedes the results commit.

**Status:** SCREEN. A screen cannot confirm anything. §7 states the only two
outputs this screen is licensed to produce.

---

## 1. Why this question, and why it is not a fishing expedition

The operator's reading of the live scorer (2026-07-29): *"模型应该是综合考虑动量和
均值回归"* — momentum and mean-reversion should be considered together.

Two prior results constrain the answer, and both are recorded before the design:

1. **A prior sealed result already killed the unconditional version.**
   `mom_12_1`, `mom_6_1`, short-term reversal, MA200 and 52-week-high **all fail
   the 20/60d bar on 104** (memory: `canonical-price-trend-no-multiday-edge`),
   with **regime-conditioned** momentum named as the surviving lead. So "add a
   momentum factor" is a known-negative, and re-running it is a *replication*,
   not a discovery.
2. **A mechanism for *why* it keeps failing was measured today**
   (renquant-orchestrator#615). The live scorer's largest lever is `STD60`
   (marginal effect `+0.2301`, an order of magnitude above every price-trend
   feature); `spearman(STD60, annualized vol) = +0.821`; and the upstream 60%
   vol gate drops 35 of 144 names carrying **3.09×** the kept median `STD60`.
   The volatility axis is therefore both the dominant axis and a *truncated*
   one at serve time.

That supplies a specific, falsifiable hypothesis rather than a factor list:
**the sign of the price-trend effect depends on the volatility state**, which is
why an unconditional trend factor averages to nothing.

This document freezes the test of that one hypothesis.

## 2. Corpus, pinned

| input | sha256 |
|---|---|
| `RenQuant/data/alpha158_291_fundamental_dataset.parquet` | `7defdacf97f8eb057a9a56a2eb7bc6eb48bc33adb9fd00a2a6c36943be87daa5` |

725,547 rows, 178 columns. This is a **production data file, opened READ-ONLY**.
The runner pins it and **aborts** on a mismatch, so a different panel cannot
reproduce different numbers under this document's name.

**Label:** `fwd_60d_excess` — cross-sectionally z-scored per date at build time
(`RenQuant/scripts/build_alpha158_qlib.py:497`, *"CSZScoreNorm on label
(cross-sectional z per date)"*). Its moments are **measured in §0 of the runner
output, not assumed**. The statistic is therefore in **standard deviations, not
return**, and **no P&L claim may be made from it.**

## 3. Factor definitions, fixed now

All formulaic. **Nothing is fitted**, so there is no parameter to leak.

```
ROC{n} = close[t-n] / close[t]      # verified in code, build_alpha158_qlib.py:231
                                    # and renquant-base-data alpha158_ops.py:256
                                    # => ROC is INVERSE momentum
ret(n) = 1 / ROC{n} - 1             # the n-day return
mom60  =  ret(60)
rev5   = -ret(5)
rev20  = -ret(20)
volq   = per-date cross-sectional tercile of STD60   (0 = low, 1 = mid, 2 = high)
z(x)   = per-date cross-sectional z-score of x
```

## 4. Arms, fixed now. No arm may be added after seeing a result.

| id | arm | role |
|---|---|---|
| R1 | `mom60` | **replication** of a known negative |
| R2 | `rev5` | replication |
| R3 | `rev20` | replication |
| **N1** | `z(mom60)` where `volq==2`; `z(rev20)` where `volq==0`; `0` where `volq==1` | **THE HYPOTHESIS** |
| N2 | `0.5*z(mom60) + 0.5*z(rev20)` | the naive blend **N1 must beat** to mean anything |

N2 exists so that a positive N1 cannot be claimed as evidence for
*conditioning* when it is really evidence for *blending*. Without N2 this screen
would be uninterpretable.

## 5. Estimands — BOTH frozen, both reported for every arm, no best-of

| id | estimand |
|---|---|
| E1 | full cross-section Spearman IC per date |
| E2 | top-decile spread: `mean(label \| top k by arm)` − `mean(label \| rest)`, `k = round(0.10·n)`, `k ≥ 1` |

E2 is the cut the live buy path trades; E1 is the statistic every existing gate
reads. Reporting both is the point — a divergence between them is itself the
finding (renquant-model#101 registers exactly this divergence as a
measurement-design claim). Dates with `n < 20` scored names are dropped.

## 6. Estimator, fixed now

`renquant_model_common.lag_alignment.dependence_aware_mean`, `block_length = 60`
(the label horizon in trading days, so overlapping labels sit inside one block),
`n_boot = 2000`.

An arm **RESOLVES** only when all three views agree in sign: block `t`, the
moving-block bootstrap CI, and leave-one-block-out. Two of three is not a
result. No substitution after seeing an outcome.

**Controls.** Five label-shuffle arms (seeds 0–4): permute `fwd_60d_excess`
**within each date**, preserving the per-date cross-sectional distribution, then
recompute §5 unchanged. The arm's *score* is untouched — only the label moves.
An arm whose control `max |t|` exceeds its own `|t|` is **VOID**, not merely
weakened.

**Corpus false-flag rate.** Per renquant-model#101 §5 Amendment 1, the
`|t| > 2.0` bar's false-flag rate is corpus-geometry dependent and must be
measured, not assumed. This runner measures it on **30 clean shuffles** of arm
**N1 under E2**. Stated limitation, registered now: that is **one arm's score
geometry**, not all five, so it is reported as an estimate for this corpus and
not as a per-arm rate.

**Multiplicity.** 5 arms × 2 estimands = **10 tests**. Bonferroni at α=0.05
two-sided ⇒ **|t| < 2.81 is not even screen-interesting.** Registered now so it
cannot be relaxed after seeing a `t` of 2.4.

## 7. What this screen is licensed to output — only these two

1. **N1's E2 spread is materially above N2's AND above all of R1–R3, its
   controls are clean, and its `|t| ≥ 2.81`** ⇒ the *only* licensed action is to
   register a **confirmatory prereg on a corpus this screen has not touched.**
   No factor is added to any model, no config changes, no capital action.
2. **Anything else** ⇒ the momentum/reversion-balance hypothesis is **NOT
   supported on this corpus**, and no factor change is proposed. This includes
   the case where N1 looks good but N2 looks equally good — that would be
   evidence for blending, which is not the registered hypothesis.

## 8. Limits registered in advance, so they cannot be spun later

- **This corpus is CONSUMED by this screen** and can never confirm it. That is
  the price of running it, paid knowingly.
- **In-sample over the full panel history.** The factors are formulaic so no
  parameters leak, but the *arm set* was chosen by me with knowledge of prior
  results. This is why R1–R3 are labelled replications and only N1 is treated
  as a new test.
- **No cost, turnover, or capacity model.** `rev5` in particular turns over
  roughly daily; a positive `rev5` would very likely be **uninvestable after
  costs.** Recorded now so a positive R2 cannot later be presented as an
  opportunity.
- **No P&L number.** The label is z-scored per date (§2).
- The `STD60` tercile is computed **on the full panel cross-section**, which is
  *not* the vol-capped support the live path scores (orchestrator#615 §4). A
  positive N1 here would therefore still need a serving-support replication
  before it meant anything operationally. Registered as a limit, not discovered
  as an excuse.

---

**Nothing in this revision is a result.** The run follows in the next commit on
this branch.
