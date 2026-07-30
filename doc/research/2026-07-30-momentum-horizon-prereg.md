# PREREG (FROZEN): momentum, with the HOLDING HORIZON as the axis

**Frozen:** 2026-07-30, before any arm was computed and before the label was
built. **This revision contains NO result.** The git order is the evidence.

**Operator constraints, registered as binding:** at most **10 factors**; a
passing model goes to **SHADOW ONLY**, never straight to live.

---

## 1. Why this is not a re-run of a killed family

A prior sealed result killed `mom_12_1`, `mom_6_1`, reversal, MA200 and
52-week-high **on the 20/60d bar**. Two prior screens of mine
(`2026-07-29-vol-conditioned-…`, `2026-07-29-momentum-family-…`) returned
**0 of 18** tests clearing their bar. So the presumption is NEGATIVE and this
document does not pretend otherwise.

Three things are genuinely new, and only these three:

1. **The holding horizon becomes the AXIS, not a fixed constant.** Everything
   measured so far sat at `fwd_60d`. Sixty trading days is the documented
   crossover zone between short-horizon reversal and intermediate momentum, so
   every prior negative is consistent with "momentum does not work **at 60
   days**" — a much weaker claim than the one that was reported.
   `[ASSUMED — literature, not measured here: Jegadeesh-Titman 1993 formation
   12−1; Barroso & Santa-Clara 2015 volatility scaling]`
2. **Horizons beyond 60 days are now constructible.** The training panel carries
   `ROC5..ROC60` only, which is why `mom_12_1` proper was declared out of scope
   before. It is now built from OHLCV: 364,736 rows × 21 columns, 145 tickers,
   2014-01-02 → 2026-07-29 `[VERIFIED-prior — factor library build]`.
3. **A genuine screen/holdout separation**, so the horizon search cannot
   contaminate the confirmatory test.

## 2. Inputs, pinned

| input | sha256 / identity |
|---|---|
| `momentum_factor_matrix.parquet` | `544701bacb552f0fc0e4ea5e5099d2ece28b32cfa6f4dbd57df2757f92ff200e` |
| `RenQuant/data/ohlcv/<T>/1d.parquet` + `SPY` | production files, **READ-ONLY**, used ONLY to build the label |

The runner pins the matrix and **aborts** on mismatch.

**Factor-library validations carried forward** `[VERIFIED-prior]`: `mom_12_1`
hand-audited against `close[t−20]/close[t−250]` on three dates, matching to
`<1e-12`; `spearman(mom_250, mom_12_1) = 0.9489`, so the 20-day skip is
demonstrably applied and not a relabelled `mom_250`; warmup is **NaN**, never
zero-filled; `sector` coverage 145/145.

## 3. THE BINDING DATA LIMITATION, stated before any number

**The price series is split-adjusted but NOT dividend-adjusted**
`[VERIFIED-prior]`: across 111 dividend-paying names / 4,344 ex-dividend days,
mean same-day return is **−58.2 bp** on ex-div days versus **+8.5 bp** otherwise,
a **−66.7 bp (SE 3.2 bp)** difference against a mean per-event yield of +61.5 bp.

Consequences, registered now:

- Long-horizon momentum (`mom_250`, `mom_12_1`, `mom_12_2`) **understates total
  return** by roughly the trailing dividend yield, and the bias is
  **sector-correlated** — utilities/telecom/energy are penalised relative to
  software.
- **The LABEL inherits the same defect**, since it is also built from these
  closes. The bias therefore partially cancels in a cross-sectional rank
  statistic but **not exactly**, because factor and label span different windows.
- So a positive result here **cannot be attributed to momentum rather than to a
  dividend-yield tilt** without a total-return series. That confound is a
  registered limit on interpretation, not a footnote.

## 4. Label, fixed now — built by the runner, never pre-existing

For horizon `h ∈ {20, 60, 120, 250}` trading days:

```
fwd_h_excess(t) = (close[t+h]/close[t] − 1) − (SPY[t+h]/SPY[t] − 1)
then per-date cross-sectional z-score
```

The last `h` dates carry no label and are dropped. Units are therefore
**standard deviations of the per-date cross-section, not return** — **no P&L
claim is possible from this document.**

## 5. Arms — 7 arms over 7 factor inputs (operator cap: 10)

`z(·)` = per-date cross-sectional z-score.

| id | arm | motivation |
|---|---|---|
| A1 | `mom_12_1` | the canonical construction |
| A2 | `mom_6_1` | shorter formation |
| A3 | `hi52_prox` | 52-week-high proximity |
| A4 | `ma200_ratio` | trend-following classic |
| A5 | `mom_12_1 / vol_250` | volatility **scaling** |
| A6 | `mom_12_1` where `vol_60 > per-date median`, else 0 | volatility **gating** — the one construction that flipped sign positive in the prior screen (+0.0773) |
| A7 | `z(mom_12_1)` **within sector** | sector-neutral momentum |

Factor inputs used: `mom_12_1, mom_6_1, hi52_prox, ma200_ratio, vol_250, vol_60,
sector` = **7 ≤ 10**. A5 and A6 separate scaling from gating, because the prior
screen found scaling worthless (`+0.0079, t=+0.20`) while gating flipped the sign
— that distinction is the single most informative prior and it is tested again on
new horizons rather than assumed.

## 6. Two phases, and the screen may NOT make a claim

**Phase S — SCREEN**, dates ≤ **2021-07-14** (1,896 dates / 183,532 rows).
All 7 arms × 4 horizons × 2 estimands = 56 measurements. **No significance claim
is permitted from Phase S.** Its ONLY output is a selection, by this mechanical
rule fixed now:

> Among (arm, horizon) pairs whose **5 within-date label-shuffle placebos all
> have `|block t| < 2.0`**, select the pair with the **largest E2 block `t`**.
> Ties (within 0.05) break toward the **longer formation window** (lower
> turnover). If no pair has clean placebos, the study returns **UNRESOLVED** and
> the holdout is NOT touched.

**Embargo** 2021-07-15 → 2021-10-07 (60 trading dates) is discarded entirely, so
no label straddles the boundary.

**Phase H — HOLDOUT**, dates ≥ **2021-10-08** (1,205 dates / 172,624 rows).
The selected pair is measured **exactly once**, with its own 5 placebos.

**The holdout is used once. No second look, whatever it returns.** If the runner
is re-executed on the same selection, that is the same test, not a new one.

**A registered asymmetry in the split** `[VERIFIED-prior]`: the split is 60% of
*dates* but only **50.3% of rows**, and the screen's `mom_250` non-null rate is
**0.811** vs the holdout's **0.995**, because only 2 of 145 names have pre-2016
history. So Phase S is thinner and noisier than Phase H. I am **not** rebalancing
it after the fact; it is recorded so a weak screen is read as weak power rather
than as absence of signal.

## 7. Estimands and estimator — unchanged from the three prior registrations

E1 full cross-section Spearman IC per date; E2 top-decile spread with
`k = round(0.10·n)`, `k ≥ 1`; dates with `n < 20` dropped.
`dependence_aware_mean`, `n_boot = 2000`, **`block_length = h`** (the horizon in
trading days, so overlapping labels sit inside one block). RESOLVES only when
block `t`, bootstrap CI and leave-one-block-out agree in sign.

Carried forward, not silently repeated: the control rule mechanically VOIDs any
near-null arm, since any control noise out-scores a `t` near zero. Disclosed in
the momentum screen, **not amended retroactively**; the runner prints each arm's
own `|t|` beside the control max.

## 8. Decision rule — two tiers, mapped to consequence

Programme-wide bookkeeping: 24 tests already registered + **1** confirmatory test
here = 25 ⇒ Bonferroni α=0.05 two-sided ⇒ **`|t| ≥ 3.08`**.

| holdout outcome | verdict | licensed action |
|---|---|---|
| placebos not all clean | **VOID** | nothing |
| `\|t\| < 1.96` | **UNRESOLVED** | nothing. This is a statement about power, never about momentum |
| `\|t\| ≥ 1.96`, clean placebos, all three views agree | **SHADOW-ELIGIBLE** | build the model and deploy it to **SHADOW ONLY**, per the operator's constraint. No capital, no sizing, no live path |
| `\|t\| ≥ 3.08` | **RESOLVED** in the programme sense | still shadow-first; promotion out of shadow needs its own registration on forward dates |

A single pre-declared test on untouched data justifies the 1.96 tier; the 3.08
tier is the programme bar and it is the one any "resolved" language must clear.
Declaring both, with the consequence attached to each, is the point — a single
threshold would either block a shadow experiment that costs nothing or license a
capital claim that the statistic cannot support.

No verdict may be revised by changing the horizon set, `k`, the block length, the
selection rule, or the split boundaries.

## 9. What a SHADOW-ELIGIBLE result would NOT license

No capital action. No sizing change. No expected-return claim — §4's units are
standard deviations. No claim that momentum beats the incumbent scorer, which was
never measured on this estimand. And per §3, no claim that the effect is momentum
rather than a dividend-yield tilt.

---

**Nothing in this revision is a result.**

---

# RESULT (appended after design commit `5a46041`)

Verbatim: `doc/research/data/2026-07-30-m2.log`. JSON: `…/2026-07-30-m2.json`.
`[VERIFIED — this session]` matrix PIN OK; label built here, all four horizons
`sd = 0.9963`, `mean ≈ 0` — units are SD of the cross-section, **not return**.
Screen 183,532 rows / 1,896 dates; holdout 172,592 rows / 1,205 dates; embargo
8,580 rows discarded.

## §8 VERDICT: UNRESOLVED. Nothing is licensed.

Selection by the frozen §6 rule: **A2 `mom_6_1` @ h=20** (screen E2 `t = +3.16`,
placebos clean). Holdout, used once:

| | |
|---|---:|
| E2 spread | **+0.1314** |
| block `t` | **+1.51** |
| CI | `[+0.0265, +0.2462]` |
| three views agree | yes |
| placebos max \|t\| | **1.97** (bar 2.0 — clean by 0.03) |
| E1 IC `t` | −0.10 |

`|t| = 1.51 < 1.96` ⇒ **UNRESOLVED**, which §8 registered in advance as a
statement about **power**, never about momentum. No shadow model is built. The
result is reported exactly as the frozen rule dictates.

## The real finding: MY SELECTION RULE WAS STRUCTURALLY BIASED, and I have to own it

The screen table shows the traded spread rising **monotonically with holding
horizon** in 4 of 7 arms `[VERIFIED — this session]`:

| arm | h=20 | h=60 | h=120 | h=250 |
|---|---:|---:|---:|---:|
| A1 `mom_12_1` | +0.1369 | +0.2027 | +0.2738 | **+0.3165** |
| A2 `mom_6_1` | +0.1736 | +0.2568 | +0.3524 | **+0.4574** |
| A4 `ma200_ratio` | +0.1206 | +0.2089 | +0.2739 | **+0.3729** |
| A6 `vol_gated` | +0.1412 | +0.1945 | +0.2748 | **+0.3283** |
| A7 `sector_neutral` | +0.0809 | +0.1361 | +0.2018 | +0.1592 |
| A3 `hi52_prox` | −0.0235 | −0.0158 | −0.0036 | −0.0365 |
| A5 `vol_scaled` | +0.0989 | +0.1219 | +0.1978 | +0.1807 |

That is the shape the literature predicts and it is the first evidence on this
programme that **60 trading days was the wrong place to look.** Registering the
horizon as the axis is what surfaced it.

**But the rule I froze then selected the horizon where the effect is SMALLEST.**
Because `block_length = h`, the number of independent blocks falls roughly
**12×** from h=20 (~57 blocks on 1,142 dates) to h=250 (~4.5 blocks)
`[DERIVED]`. Block `t` therefore **falls as the horizon rises even while the
effect grows**, so a rule that maximises `t` is a rule that prefers short
horizons. A2's selected h=20 spread (+0.1736) is the **smallest of its four**.

**My control rule compounds it in the same direction.** With few blocks the
placebo `|t|` distribution widens, so the fixed `|t| < 2.0` bar false-flags more
often at long horizons — visible in the table: 5 of 7 arms are PLACEBO-DIRTY at
h=250, versus 2 of 7 at h=60. This is exactly the corpus-geometry dependence
registered in the traded-estimand prereg's Amendment 1, now biting on the horizon
axis.

So **two of my own frozen rules both discriminated against the horizon the theory
points at.** I cannot repair that here: §8 forbids revising a verdict by changing
the selection rule, and this verdict is UNRESOLVED.

## Honest accounting of what the holdout cost

The holdout was spent on **one** pair, A2 @ h=20. The other 27 (arm, horizon)
pairs are unseen on it. That does **not** make the holdout fresh: a second use of
the same dates is a second test on the same data and must be registered with that
multiplicity stated. It is weaker evidence than a virgin holdout, and any
follow-up must say so rather than present the holdout as untouched.

## What a corrected registration would have to fix — stated, not executed

1. **Select on effect size subject to a minimum block count**, not on `t` — or
   pre-declare the horizon from theory (12−1 at a long horizon) and skip the
   empirical selection entirely, which removes the bias by removing the choice.
2. **Make the control bar horizon-aware**, calibrated per block count, since a
   fixed `|t| < 2.0` is not the same test at 57 blocks and at 4.5.
3. Obtain a **dividend-adjusted** series. §3's confound stands unchanged: the
   monotone rise with horizon is *also* what a dividend-yield tilt would produce
   in a price-only series, since the omitted dividend accumulates with the
   horizon. **This is the single most likely alternative explanation for the
   table above and it is not ruled out by anything measured here.**

## What is NOT claimed

Not that momentum works. Not that the screen table is evidence — §6 forbids it
and the table's monotone pattern has an unexcluded dividend explanation. Not that
`mom_6_1` at a long horizon would pass; it was never tested on the holdout. No
P&L: units are SD. No model built, nothing deployed, not even to shadow.
