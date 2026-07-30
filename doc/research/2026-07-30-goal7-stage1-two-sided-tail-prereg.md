# PREREG — GOAL-7 Stage 1: is the payoff TWO-SIDED rather than a ranking?

**FROZEN. No run has been executed against this document.** Nothing live changes on
any outcome. This registers **one** question. It does not design a scorer, and a pass
does not authorise building one — see §7.

## §0 Why this question, and why not a ranker

The operator's brief for GOAL-7 is a **standalone** momentum model, at most ten
factors, deployed to **shadow** only, and — stated explicitly — one that considers
**both momentum and mean reversion**.

model#110 measured something that decides the shape of that model, and it is not what
a momentum scorer is usually built as. Its decile profile of forward excess return
against `mom_12_1_tr` (h = 120 trading days, per-date z-scored label, so units are SD
of the cross-section) is `[VERIFIED — prior work, doc/research/2026-07-30-momentum-total-return-prereg.md:652]`:

| d0 | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 | d9 |
|---|---|---|---|---|---|---|---|---|---|
| **+0.135** | −0.001 | −0.071 | −0.078 | −0.091 | −0.089 | −0.036 | −0.033 | −0.049 | **+0.375** |

**Both extremes pay. The middle does not.** Rank correlation of the profile with
decile number is only **+0.27** and the full-cross-section IC is `t = +0.589` ≈ 0
`[VERIFIED — prior work, same file:656-657]`. That is not a weak ranking; it is a
**U-shape that a linear rank statistic cancels by construction** — the losers' tail
and the winners' tail push the correlation in opposite directions.

Read plainly: the biggest losers reverting and the biggest winners continuing are the
*same* profile, and the operator's instinct that the model must hold both is what the
data shows. A cross-sectional momentum **ranker** would be the wrong object; it would
average the two ends into the flat middle.

So Stage 1 asks exactly one thing: **does a two-sided transform capture what the
linear one cancels?**

## §1 THE REGISTERED TRANSFORM — fixed now, not searched

> `u(t, i) = |z_t(mom_12_1_tr)|`

the **absolute** cross-sectional z-score of 12−1 momentum on dividend-adjusted
total-return prices, per date. No free parameters, no threshold, no fitted knee. It is
the simplest function that is large at both ends and small in the middle, which is the
shape §0 measured.

**Not registered and not admissible in this stage:** any fitted breakpoint, any
piecewise or quantile-dependent weighting, any per-side coefficient. Those are exactly
the knobs that would let the transform be tuned to the profile that motivated it.

## §2 THE HARKING PROBLEM, NAMED BEFORE THE RUN

The U-shape was found **post hoc**, in a study whose own verdict was
UNRESOLVED / TILT-NOT-EXCLUDED. Registering a transform that fits it is only honest if
the registration precedes the run and the evaluation is not on the sample that
suggested it. Two consequences, both binding:

1. **Split by DATE, screen and holdout, with a 60-trading-day embargo between them.
   The holdout is used ONCE.** The transform, the estimand, the estimator and the
   critical value are all fixed in this document before either partition is touched.
2. **The residual risk cannot be fully removed and is stated instead of hidden.** The
   U-shape was observed on the full sample, so a holdout carved from that same sample
   is not independent of the observation that motivated the design. Therefore **a pass
   here is SCREEN-INTERESTING, not licensed**, and §7 says what it does and does not
   buy. Genuinely independent confirmation would need dates outside this corpus and
   this stage does not claim it.

## §3 ESTIMAND, ESTIMATOR, CRITICAL VALUE

**Primary estimand — the tail statistic, not IC.** Top-decile spread of `u`:
`k = round(0.10 · n)`, `k ≥ 1`; the mean forward excess return of the top-`k` names by
`u` minus the cross-sectional mean, per date. This choice is not opportunistic: on this
programme the tail statistic has led IC on **4 of 4** independent subjects
`[VERIFIED — prior work, memory panel-signal-identity-capacity]`, and every house gate
adjudicating on whole-cross-section IC has been measured as the lower-powered
statistic (IC `t = 1.15` against top-10 spread `t = 2.92` on identical data).

**Estimator, frozen.** Non-overlapping contiguous blocks of 60 trading days over the
admissible dates; `n_blocks = floor(N_eval / 60)`; **the remainder is DROPPED, never
equal-weighted** — model#110 formed 10 blocks where 9 was correct and equal-weighted a
5-day trailing block, inflating its headline `t` by 15.6%
`[VERIFIED — prior work, model#110 ERRATUM]`. One-sample two-sided `t` over block means.

**Critical value, one symbol everywhere:**

> `T_crit = max( P95_null , t_{0.975, n_blocks−1} )`

`P95_null` = 95th percentile of `|t|` from **200** within-date permutations of `u`
through the identical harness. The Student-t leg uses the **realised** `n_blocks` after
the drop; for reference `t_{0.975,7} = 2.3646`, `t_{0.975,8} = 2.3060`
`[DERIVED — scipy.stats.t.ppf(0.975, n−1)]`. Frozen at 1.96 this screen would run a bar
~17% too low; that error was caught in review on model#113 before any run.

**Mandatory in the report:** `N_eval`, `n_blocks`, dropped remainder days, `P95_null`,
`t_{0.975,n_blocks−1}`, which leg bound `T_crit`, and `|t|` as a quantile of the null.

## §4 THE CONTROL THAT MATTERS MOST — the volatility trap

**This is the clause that decides whether the result means anything.** `|z|` of
momentum is large exactly where the cross-section is dispersed, and on this programme a
model's apparent edge has already been shown to be a volatility ranking: the prod XGB's
traded estimand (+0.2534 SD) was reproduced by a **single sort on STD20** (+0.2836) and
collapsed to **−0.0554** when orthogonalised to STD60
`[VERIFIED — prior work, memory panel-signal-identity-capacity]`.

So, registered as a **kill condition, not a caveat**:

> Orthogonalise `u` to `|z_t(STD60)|` within date. If the top-decile spread of the
> residual fails `T_crit`, the verdict is **VOLATILITY-TILT** and the two-sided
> hypothesis is **not** supported, whatever the raw arm says.

Additionally, and reported alongside: pooling within volatility deciles (the residual
statistic computed inside each `STD60` decile, then averaged) must preserve the sign.

## §5 THE OTHER ARMS

| arm | role | may it fail? |
|---|---|---|
| `u = \|z(mom_12_1_tr)\|` | **treatment** | yes |
| raw `z(mom_12_1_tr)`, same estimator | **reference** — the linear arm the U-shape says should be weak. Reported, **not a bar**; the hypothesis is not "beat the linear arm", it is "clear `T_crit` after §4" | — |
| prod XGB top-decile spread, same dates | **positive control** — must clear `T_crit`, else the harness cannot see a known non-zero effect and the screen is **VOID** | must pass |
| `u` on within-date permuted momentum | **null control** — false-pass rate over the 200 permutations against a **10%** validity ceiling; above it the screen is **VOID** | must fail |

**Non-tautology check** (§4.3 of the sibling preregs, and for the same reason): assert
the permutation changes the statistic on ≥95% of dates. model#110 shipped a negative
control that was algebraically forced to agree — 34 non-payers matched bit-for-bit
because their adjustment factor was identically 1.0
`[VERIFIED — prior work, model#110 negative-control correction]`.

## §6 SELF-CHECKS BEFORE THE TREATMENT

Each must pass or the screen VOIDs:
- the within-date permutation is asserted to **reject** an unsorted frame — a helper
  that leaked labels across dates on a ticker-major frame aborted model#105;
- no undersized block exists;
- prices are the **dividend-adjusted total-return** series (model#110), and the
  adjustment's own validation is cited rather than re-assumed: ex-dividend-day gap
  **−66.6bp (t=−20.6) → −4.8bp (t=−1.55)** `[VERIFIED — prior work, model#110 §4]`;
- the screen/holdout partition is by date with a 60-trading-day embargo, and the
  embargoed row count is reported.

## §7 DECISION RULE, AND WHAT A PASS BUYS

| outcome | condition |
|---|---|
| **TWO-SIDED-SUPPORTED** | `\|t\| ≥ T_crit` on the holdout **after** §4 orthogonalisation, controls valid |
| **VOLATILITY-TILT** | raw arm clears but the §4 residual does not |
| **UNRESOLVED** | `\|t\| < T_crit` |
| **VOID** | positive control fails, null false-pass > 10%, non-tautology check fails, or `n_blocks < 6` |

**TWO-SIDED-SUPPORTED licenses exactly one thing: writing the Stage-2 design for a
standalone scorer of at most ten factors, to be deployed to SHADOW only.** It does not
authorise building it, does not authorise any config, artifact, state or launchd
change, and does not authorise capital. The ten-factor budget carries forward as a
hard constraint and is not spent here — Stage 1 tests one transform precisely so the
factor budget is not committed before the formulation is known to have anything.

**UNRESOLVED licenses nothing**, and given §2's numbers it is a plausible outcome: the
motivating study's own robustness arms sat at `t` +1.871 / +1.964 / +1.990 against a
bar the correct calibration puts at 2.3060
`[VERIFIED — prior work, model#110 robustness table]` `[DERIVED — t.ppf(0.975, 8)]`.

**VOLATILITY-TILT is the outcome I expect to have to report if the raw arm looks
good**, and it is registered as a distinct verdict rather than a footnote so it cannot
be narrated away.

## §8 PUBLICATION DISCIPLINE

The verdict is **withheld pending adversarial review**, appended verbatim with its
disposition before merge. On this programme that is the only thing that has worked on
a contested question: a CLOSE was published and retracted, a second was withheld, and
the commissioned review destroyed it.
