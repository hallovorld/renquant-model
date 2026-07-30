# GOAL-7 Stage 1 — the payoff is two-sided, so a ranker is the wrong object   (PR pending)

STATUS:    planned  (frozen registration; NO run has been executed)
WHAT:      Registers one question for GOAL-7: does `|z(mom_12_1_tr)|` — a two-sided
           transform with no free parameters — clear a finite-sample bar on a
           once-used date holdout, AFTER being orthogonalised to volatility?
WHY/DIR:   GOAL-7 is a standalone momentum model for shadow, at most ten factors, and
           the operator specified it must consider momentum AND mean reversion.
           model#110 measured why that is right and why a ranker is wrong: the decile
           profile of forward excess return against 12−1 momentum is U-SHAPED
           (d0 +0.135, middle −0.03…−0.09, d9 +0.375), rank correlation with decile
           only +0.27, full-cross-section IC t = +0.589 ≈ 0. Both extremes pay and the
           middle does not, so a linear ranker cancels the two ends against each other.
AMENDMENT 3 (2026-07-30, before any run): codex was right that Amendment 2 fixed a
contamination defect by re-opening a mutability one. The partition is now COMPUTED from
the benchmark's trading-day index and frozen: window 2016-12-29..2021-04-19, N_eval=1082,
n_blocks=18, dropped remainder 2, Student-t leg t_(0.975,17)=2.1098. The binding
separation rule is that no evaluation date's label may use a return from the burned
period, which supersedes the 60-day embargo because this design has ONE once-used window
and no second partition for an embargo to separate. Correction: Amendment 2 called the
uncontaminated window "shorter"; it is LONGER (18 blocks vs 10), so removing the
contamination increases power. The cost is regime, not power.

EVIDENCE:  n/a — this PR makes NO model or data claim. Every number is tagged as prior
           work with a reference; nothing was measured for it.
NEXT:      Run the §6 self-checks against the Amendment 3 partition, then the screen.
           Verdict withheld pending adversarial review.

## Review round 1 — the registration was not executable, and now is

Codex's BLOCKER was correct and is the reason this document is worth more than it was:
§2 claimed the design was "fixed before either partition is touched", but four choices
were still open at run time — corpus/eligibility, the exact split, the positive-control
artifact, and the §4 residualisation estimator. Each could have moved the verdict
*after* the U-shape was known, which is exactly the hole §2 exists to close. A prereg
that names its HARKing risk and then leaves the knobs unturned is worse than one that
does neither, because it reads as protected.

Pinned in the new §2A and the amended §4/§5.1, all against the corpus rather than
asserted:

* **Inputs** — the sibling study's two immutable parquets, digests re-verified by
  `shasum` this session rather than transcribed from the sibling document. (The
  distinction matters: I have previously tagged a number `[VERIFIED]` when what I had
  verified was my *transcription* of it.) The durable pin is the committed
  `raw_input_manifest.json`, since the derived parquets sit in a scratchpad.
* **Split** — chronological 70%, computed: screen 1,600 dates / embargo 60 / holdout
  **627 dates = 10 blocks**, remainder 27 dropped, 2023-08-07 → 2026-02-04. So
  `t_{0.975,9} = 2.2622` and the `n_blocks < 6` VOID floor clears with margin.
* **§4 named a column that does not exist.** `STD60` is the prod-XGB study's name, not
  this corpus's — the pinned matrix carries `vol_60_tr`. A control written against a
  missing column is how a control silently becomes a no-op, which is the
  guard-validates-the-wrong-object shape this programme keeps hitting. Now pinned to
  `vol_60_tr` with the estimator fully specified (per-date OLS **with intercept**,
  deciles on residual ranks, ties by ascending ticker).
* **Positive control is no longer the prod XGB.** Codex asked which artifact/version;
  the honest answer is that none is pinnable — the served checkpoint matches none of
  the 43 rescored folds. A control whose own identity is unresolved cannot certify a
  harness. Replaced with the closed-form synthetic member merged in model#114 §5.1
  (`α = 0.0523538966`, date-derived seed, `|mean IC − 0.05| ≤ 0.01` asserted, never
  re-calibrated).

Disclosed rather than papered over: the 60-date embargo is **shorter than the
120-trading-day label horizon**, so late-screen labels overlap early-holdout dates. A
TWO-SIDED-SUPPORTED verdict now carries a mandatory 120-date-embargo robustness re-run.

> Round-1 figures above are kept as written for auditability. **Two are superseded by
> round 2:** the split (screen 1,600 / holdout 627 / `n_blocks = 10`) and the
> 120-embargo robustness obligation, which round 2 discharges by adopting 120 as the
> registered primary. See "Review round 2" below.

## The one clause that decides whether the result will mean anything

§4, and it is registered as a **kill condition rather than a caveat**: `|z|` of momentum
is large exactly where the cross-section is dispersed, and this programme has already
been burned by that. The prod XGB's traded estimand (+0.2534 SD) was reproduced by a
single sort on STD20 (+0.2836) and collapsed to −0.0554 when orthogonalised to STD60
`[VERIFIED — prior work, memory panel-signal-identity-capacity]`. So if the residual
after orthogonalising `u` to `|z(vol_60_tr)|` fails the bar, the verdict is
**VOLATILITY-TILT** and the hypothesis is not supported no matter what the raw arm says.
That is the outcome I expect to have to report if the raw arm looks good.

## The HARKing problem, stated rather than managed away

The U-shape was found post hoc, in a study whose own verdict was UNRESOLVED. §2 fixes
the transform, estimand, estimator and critical value before either partition is
touched, splits by date with an embargo, and uses the holdout once. But the U-shape was
observed on the full sample, so a holdout carved from it is **not independent of the
observation that motivated the design**. §2 records that, and §7 limits a pass to
SCREEN-INTERESTING accordingly. Independent confirmation would need dates outside this
corpus and this stage does not claim it.

## Why the primary statistic is the tail and not IC

The tail statistic has led IC on **4 of 4** independent subjects on this programme and
cleared no preregistered bar on any of them `[VERIFIED — prior work, memory
panel-signal-identity-capacity]`, and on identical data whole-cross-section IC read
`t = 1.15` against a top-10 spread of `t = 2.92`. Every house gate adjudicates on the
lower-powered statistic. Using the tail here is the registered choice, not a
convenience — and it is the same statistic the motivating study used as its primary.

## What a pass does and does not buy

TWO-SIDED-SUPPORTED licenses **writing** the Stage-2 design for a ≤10-factor standalone
scorer for SHADOW. It does not authorise building it, no config/artifact/state/launchd
change, no capital. The ten-factor budget is deliberately NOT spent here: Stage 1 tests
one transform precisely so the budget is not committed before the formulation is known
to have anything — the cheap-screen-before-cathedral rule.

## Review round 2 — Amendment 3: the partition, computed instead of promised

Codex was right that Amendment 2 reopened what Amendment 1 had closed. Burning
2021-10-08 onward was correct, but leaving `n_blocks` to be "recomputed" at run time
means the partition and its power condition are still mutable when the run starts —
and a mutable partition is not a registration, whatever the surrounding prose says.
Amendment 3 computes them against the pinned corpus and supersedes the stale figures
in place (§2A's table, §3's `n_blocks = 10`) rather than editing history.

Measured `[VERIFIED — computed on the §2A-pinned matrix, this session]`:

* uncontaminated admissible window **1,202 dates, 2016-12-29 → 2021-10-07**
* **evaluation 1,082 dates → `n_blocks = 18`**, trailing remainder **2** dropped and
  named (2021-04-16, 2021-04-19), so the drop is checkable
* **`t_{0.975,17} = 2.1098`**

Two things worth flagging beyond what was asked.

**`n_blocks = 18` — nearly double Amendment 1's 10.** Amendment 2 registered
"UNRESOLVED (underpowered)" as a live outcome if the uncontaminated window could not
supply 6 blocks. It supplies 18, so that branch does not fire. Burning the
contaminated period cost regime relevance, not power — the honest framing is that the
older window is *longer*, and A2.3's stated cost stands as a regime cost only.

**I tightened the embargo from 60 to 120 rather than pinning the 60 codex asked to see
named.** Amendment 1 disclosed that a 60-date embargo is shorter than the
120-trading-day label horizon, so late-evaluation labels reach forward into excluded
dates — and post-Amendment-2 those excluded dates are the *contaminated* ones, which
is precisely the leak this chain exists to close. At Amendment 1's geometry closing it
cost 2 of 10 blocks and was disclosed instead; at this geometry it costs **1 of 19**
(60 → 19 blocks, `t` 2.1009; 120 → 18 blocks, `t` 2.1098). Paying one block to remove
the leak entirely, before any arm runs, in the direction that makes the test harder,
is the obvious trade. Consequence: Amendment 1's 120-embargo robustness obligation is
**discharged, not carried** — there is no 60/120 gap left to re-run. Both sets of
figures are recorded so the choice is auditable.

## Review round 3 — Amendment 4: two Amendment 3s, one specification

Two sections titled "AMENDMENT 3" were written concurrently against the same review —
mine and another session's. Codex caught it: an executable spec cannot ask readers to
reconcile contradictory clauses. Amendment 4 is the single authoritative partition;
both A3s are marked NOT EXECUTABLE in place and retained unedited.

**They agreed on every number** (eval 2016-12-29 → 2021-04-19, `N_eval = 1082`,
`n_blocks = 18`, `t_{0.975,17} = 2.1098`) — I recomputed both routes independently
before reconciling rather than assuming the agreement. The conflict was in the rule:
mine registered a 120-date **embargo band**; the other derived the same dates from a
**label-overlap rule**.

**I withdrew my own framing.** An embargo separates a screen partition from a holdout.
This design has one once-used window and no second partition, so there is nothing for
an embargo to separate — and naming those 120 dates as one invites a future reader to
think a usable second partition exists. The other session's rule is the correct object
and is strictly stronger; the dates are identical either way.

Two things I pinned that neither A3 did:

* **Calendar source of truth.** A3-b counted the 120 steps on `SPY/1d.parquet`; A4.3
  names the **corpus's own** index, since the label is built from the corpus's prices.
  I checked whether it mattered: the two indices are **identical date-for-date** over
  their common range (1,452 dates, 2016-01-04 → 2021-10-07) and both give last-eval
  2021-04-19 [VERIFIED — element-wise comparison + the 120-step on each, this session].
  Named anyway — "they agreed when I checked" is not a specification.
* **A3-b's last open quantity is closed.** It held `N_eval` could still fall at run
  time because the ≥20-name rule "cannot be evaluated without the corpus". It can:
  every date in the window carries ≥ **126** eligible names (median 128), so the rule
  drops **zero** dates [VERIFIED — per-date eligible-name counts, this session].
  `N_eval = 1082` is realised, not an upper bound, and §7's `n_blocks < 6` branch
  cannot fire on this partition.

## Live-surface impact

Still none. Documents only. No run has been executed.
