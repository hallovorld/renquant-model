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

## §2A INPUTS, ELIGIBILITY, AND THE DATE SPLIT — pinned here, not at run time

§2 claims the design is fixed before either partition is touched. That claim is only
true if the *inputs and the partition itself* are fixed too, and the first version of
this document left four choices to run time — corpus, eligibility, the split, and the
§4 estimator. Each could have moved the verdict after the U-shape was known, which is
precisely the HARKing hole §2 exists to close. They are pinned below.

**Inputs — the same two immutable files as the sibling study, digests re-verified:**

| input | sha256 | bytes |
|---|---|---|
| `momentum_factor_matrix_tr.parquet` | `85c27fc1d5a56a4c585c03db22dc8be0123badfc83ef23e46cdd358c704eb35a` | 76,310,040 |
| `total_return_close.parquet` | `8c23496ee351757ec1f953597f9705168542f67cc16f209385091bb60d741ac9` | 4,007,937 |

`[VERIFIED — shasum -a 256 on both files, this session; matches
doc/research/2026-07-30-momentum-total-return-prereg.md §3 independently rather than
by transcription]`. The runner re-verifies both and **REFUSES to proceed** on any
mismatch. Both are derived, read-only, from `RenQuant/data/ohlcv/<T>/1d.parquet`
(145 watchlist names + `SPY`), 364,736 rows × 3,161 dates, 2014-01-02 → 2026-07-29
`[VERIFIED — pd.read_parquet(...).shape / .date.nunique(), this session]`. The
*durable* pin is the committed raw manifest
`doc/research/data/2026-07-30-momentum-total-return/raw_input_manifest.json`
(`corpus_fingerprint_sha256=48728e24…`), which `raw_input_manifest.verify_or_abort()`
checks before any raw read; the two derived parquets are reproducible from it. That
matters because the derived files currently sit in a session scratchpad and are not
themselves durable — the manifest, not the scratchpad, is what makes this rerunnable.

**Eligibility, per `(date, ticker)`:** both `mom_12_1_tr` and `vol_60_tr` non-null
(the latter is needed by §4, so admitting a name without it would make the treatment
and control arms run on different samples), and the forward 120-trading-day label
exists. **Per date:** at least `MIN_NAMES = 20` eligible names, matching the sibling
harness. No liquidity, price or sector filter is applied — none is registered, so
none may be added.

**The split — chronological, 70% by admissible-date count, embargo carved from the
boundary.** Screen is the earlier partition; the holdout is later in time, so the
one-use test is also a genuine forward test. Resolved against the pinned corpus:

| partition | dates | blocks of 60 | remainder dropped | range |
|---|---|---|---|---|
| screen | 1,600 | 26 | 40 | 2016-12-29 → 2023-05-09 |
| embargo (used by neither) | 60 | — | — | 2023-05-10 → 2023-08-04 |
| **holdout (ONE use)** | **627** | **10** | **27** | **2023-08-07 → 2026-02-04** |

2,287 admissible dates in total `[VERIFIED — computed on the pinned matrix this
session: dropna on both signals, ≥20 names, date ≤ the last date with a 120-trading-day
forward label, which is 2026-02-04]`. The first admissible date is 2016-12-29 rather
than 2014-01-02 because `vol_250_tr`-era warmup and the 12-1 lookback consume the
opening years.

Two consequences worth stating rather than discovering at run time. The holdout gives
`n_blocks = 10`, so `t_{0.975,9} = 2.2622` `[DERIVED — scipy.stats.t.ppf(0.975, 9)]`,
and it clears §7's `n_blocks < 6` VOID floor with margin. And the 60-date embargo is
**shorter than the 120-trading-day label horizon**, so a screen date inside the last
60 admissible dates before the boundary still has a label window overlapping early
holdout dates. That is a real, bounded leak of the *label*, not of the design, and it
is disclosed here rather than papered over: the embargo is registered at 60 because
the estimator's block length is 60, and widening it to 120 would cost two holdout
blocks. **If the verdict is TWO-SIDED-SUPPORTED, the report must state the overlap and
re-run the holdout arm with a 120-date embargo as a robustness line** — a disclosed
robustness obligation, not a discretionary one.

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
the drop. §2A pins the holdout at `n_blocks = 10`, so the expected Student-t leg is
`t_{0.975,9} = 2.2622`; the neighbouring values are `t_{0.975,8} = 2.3060`,
`t_{0.975,7} = 2.3646`, `t_{0.975,5} = 2.5706`
`[DERIVED — scipy.stats.t.ppf(0.975, n−1), this session]`. Frozen at 1.96 this screen
would sit at **86.6% of the correct bar** at `n_blocks = 10` — i.e. 13.4% too low,
on the same convention as the 17% quoted for `t_{0.975,7}`
`[DERIVED — 1.96/2.2622 = 0.8664, this session]`; that error was caught in review on
model#113 before any run. Note the leg **rises** as blocks are lost, so a run that
ends up with fewer blocks than §2A predicts faces a *stricter* bar, not a looser one —
the failure direction is safe.

**Mandatory in the report:** `N_eval`, `n_blocks`, dropped remainder days, `P95_null`,
`t_{0.975,n_blocks−1}`, which leg bound `T_crit`, `|t|` as a quantile of the null, and
the realised screen/embargo/holdout date counts against §2A's pinned table (a
divergence means the corpus moved and the run is not the registered one).

## §4 THE CONTROL THAT MATTERS MOST — the volatility trap

**This is the clause that decides whether the result means anything.** `|z|` of
momentum is large exactly where the cross-section is dispersed, and on this programme a
model's apparent edge has already been shown to be a volatility ranking: the prod XGB's
traded estimand (+0.2534 SD) was reproduced by a **single sort on STD20** (+0.2836) and
collapsed to **−0.0554** when orthogonalised to STD60
`[VERIFIED — prior work, memory panel-signal-identity-capacity]`.

So, registered as a **kill condition, not a caveat**:

> Orthogonalise `u` to `|z_t(v)|` within date. If the top-decile spread of the
> residual fails `T_crit`, the verdict is **VOLATILITY-TILT** and the two-sided
> hypothesis is **not** supported, whatever the raw arm says.

**The volatility variable, named against this corpus.** The first version of this
clause said `STD60`. **There is no such column in the pinned matrix**
`[VERIFIED — column list of momentum_factor_matrix_tr.parquet, this session: the
volatility columns are vol_60_tr, vol_250_tr, vol_60_px, vol_250_px]` — `STD60` is
the name it carries in the *prod-XGB* study quoted above, a different corpus. Writing
a control against a column that does not exist is how a control silently becomes a
no-op, so it is pinned to this corpus's equivalent:

> `v = vol_60_tr` = `std(simple total-return daily returns, trailing 60, ddof=1)·√252`,
> `min_periods = 60` `[VERIFIED — tools/build_tr_factor_matrix.py:80]`.

**The estimator, fully specified.** Per date `t`, over that date's eligible names:
ordinary least squares of `u` on `|z_t(v)|` **with an intercept**, fitted on that date
alone; the residual is `u − (â + b̂·|z_t(v)|)`. Names missing either variable are
already excluded by §2A eligibility, so the regression drops nothing further and the
treatment and control arms run on **the same sample by construction**. The decile is
formed on the **residual** ranks, descending, ties broken by ascending ticker symbol
(deterministic — the same rule §5 uses, and the reason it is stated is that a
random tie-break would make the run irreproducible). `k = round(0.10·n)`, `k ≥ 1`, as
in §3.

Additionally, and reported alongside: pooling within volatility deciles (the residual
statistic computed inside each `vol_60_tr` decile, then averaged) must preserve the
sign.

## §5 THE OTHER ARMS

| arm | role | may it fail? |
|---|---|---|
| `u = \|z(mom_12_1_tr)\|` | **treatment** | yes |
| raw `z(mom_12_1_tr)`, same estimator | **reference** — the linear arm the U-shape says should be weak. Reported, **not a bar**; the hypothesis is not "beat the linear arm", it is "clear `T_crit` after §4" | — |
| synthetic member `u_pc` (§5.1) | **positive control** — must clear `T_crit`, else the harness cannot see a known non-zero effect and the screen is **VOID** | must pass |
| `u` on within-date permuted momentum | **null control** — false-pass rate over the 200 permutations against a **10%** validity ceiling; above it the screen is **VOID** | must fail |

### §5.1 The positive control, in closed form — and why it is NOT the prod XGB

The first version named "prod XGB top-decile spread" as the positive control. **That
is not pinnable right now.** The served checkpoint's identity is an open finding on
this programme: its digest matches none of the 43 rescored folds and it has only two
trading days of verified live history `[VERIFIED — prior work, memory
panel-signal-identity-capacity]`. A positive control whose *own* identity is
unresolved cannot certify a harness — if it failed, we could not tell whether the
harness is blind or the artifact is the wrong one. Pinning a version string to satisfy
the letter of the review would have been worse than the gap it closed.

So the control is constructed in closed form instead, mirroring the design merged in
model#114 §5.1 rather than inventing a second pattern:

For each admissible date `t`, over that date's eligible cross-section of size `n`:

1. `w = normal_scores(rank(r_{t→t+120}))` — ranks of the realised forward excess
   return mapped through `Φ⁻¹((i − 0.5)/n)`, ties broken by **ascending ticker
   symbol**.
2. `e = normal_scores(rank(g))`, `g` drawn from
   `numpy.random.default_rng(SEED_BASE + int(t.strftime("%Y%m%d")))`,
   `SEED_BASE = 20260730`. The seed is a pure function of the date, so the control is
   bit-reproducible and independent of iteration order.
3. `u_pc = α·w + sqrt(1 − α²)·e`, with

> `α = 2·sin(π · 0.05 / 6) = 0.0523538966`
> `[DERIVED — 2*math.sin(math.pi*0.05/6); check (6/math.pi)*math.asin(α/2) =
> 0.0500000000, this session]`

giving a **population** Spearman IC of exactly `+0.05` against the realised return.

**Asserted, never re-calibrated:** the realised mean per-date Spearman IC of `u_pc`
must satisfy `|mean − 0.05| ≤ 0.01`. If it does not, **the construction is broken and
the screen VOIDs** — `α` is not adjusted to bring it into range. Registering a closed
form is what makes that assertion able to fail the run instead of tuning it.

`u_pc` is monotone where the treatment `u` is two-sided, and that is deliberate: what
this control certifies is that the **top-decile-spread estimator with the §3 blocking
and `T_crit`** can detect a real inserted effect at all. It does not certify that the
harness can detect a *U-shape*; no control here does, and the report must not claim it.
`u_pc` never enters a treatment arm.

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
| **VOID** | positive control fails, its §5.1 construction assertion `\|mean IC − 0.05\| ≤ 0.01` fails, an input digest mismatches §2A, null false-pass > 10%, non-tautology check fails, or `n_blocks < 6` |

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

---

# AMENDMENT 2 — the chosen holdout is CONTAMINATED by the motivating observation

Registered 2026-07-30, before any run. Amendment 1 pinned the corpus, the split
arithmetic, the positive control and the residualisation estimator — all correct and all
retained. This amendment does not reopen any of them. It corrects the one thing pinning
the split made checkable: **which sample the hypothesis was read off.**

## A2.1 The finding

model#110 §4 states it verbatim: **"Mean label z by `mom_12_1_tr` decile *on the
holdout*"** `[VERIFIED — doc/research/2026-07-30-momentum-total-return-prereg.md §4]`.
That study's holdout is **2021-10-08 → 2026-07-29**
`[VERIFIED — tr_matrix_metadata.json `split`, doc/research/data/2026-07-30-momentum-total-return/]`.

Amendment 1's holdout is **2023-08-07 → 2026-02-04**, which lies **entirely inside** it.

So the partition this screen was going to treat as its one-use holdout is a strict subset
of the sample the U-shape was observed on. Evaluating there is not an out-of-sample test
of the hypothesis; it is a re-analysis of the observation that generated it, with a
holdout that is not one. §2 was written to prevent exactly this and, as published, walked
into it — the failure was not in §2's reasoning but in never checking *where* the
motivating profile came from.

## A2.2 Registered consequence

**The evaluation partition is the part of the screen that predates the contamination:**

> **2016-12-29 → 2021-10-07**, used ONCE.

- **2021-10-08 → 2026-07-29 is BURNED for this hypothesis** and may not be used in Stage 1
  in any arm, including descriptive ones. That covers Amendment 1's entire holdout and the
  tail of its screen.
- The 60-trading-day embargo and every eligibility rule from Amendment 1 apply unchanged,
  now at the new boundary.
- `n_blocks` is therefore **not** Amendment 1's pinned 10. It is recomputed from the
  realised admissible dates in this window under the frozen `floor(N_eval / 60)` rule with
  the remainder dropped, and §7's `n_blocks < 6` clause applies to whatever that yields.
  **If the uncontaminated window cannot supply 6 blocks, the registered answer is
  UNRESOLVED (underpowered) and Stage 1 does not run against a contaminated one instead.**

Amendment 1's disclosed embargo-vs-label-horizon leak (60 < 120) is unaffected in kind and
still applies at the new boundary; its robustness line — re-running with a 120-date embargo
— is retained.

## A2.3 Why this is a real cost, stated rather than minimised

This trades a 627-date holdout for a shorter, older window, and older data is not
free: the 2016-2021 regime is not the one the model trades today. **That is the price of
the hypothesis having been discovered post hoc, and it is the honest price.** The
alternative — testing on the sample the pattern was read off — produces a number that
cannot distinguish signal from the reason the study was written.

§7's limit therefore tightens rather than relaxes: a pass on this window is
**SCREEN-INTERESTING on a pre-2021 regime**, and licenses only writing the Stage-2 design.
It does not license a claim about the current regime, which would need dates that do not
exist uncontaminated in this corpus.
