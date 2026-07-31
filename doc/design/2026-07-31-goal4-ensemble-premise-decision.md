# GOAL-4: the ensemble premise, evaluated against its own registered members

**Bottom line — NARROWED after codex on model#136.** An ensemble needs members that (a)
individually carry skill and (b) are not redundant. **Not one registered member has been
shown to carry skill** — and, equally, **not one has been shown not to**. The estimates
below are descriptive; no validated inference procedure exists to adjudicate them. That
is not a reason to close the lane, and it is not a verdict against the members. It is a
reason to stop treating *"combine the models"* as the next step, because **the premise is
unmeasured** — there is nothing established to combine.

## The three registered members, as measured — DESCRIPTIVE ESTIMATES

| member | the measurement | status |
|---|---|:--|
| **production XGB** | its traded estimand is reproduced by a **single sort on STD20** (**+0.2836** vs the model's **+0.2534**) and collapses to **−0.0554** when orthogonalised to STD60 | **not established** — the traded estimand is reproducible by a volatility tilt |
| **PatchTST** | margin over **its own 60-day-stale score** = **−0.0556**, block `t = −2.31` at `n_eff = 8` | **un-adjudicated** — see the bar caveat below |
| **certified clf** | **+0.0096**, block `t = +1.31` | **un-adjudicated** |

`[VERIFIED — prior work, model#90; and the frozen §1 of doc/research/2026-07-30-goal4-phase0-ensemble-gain-prereg.md]`

> **WHY "un-adjudicated" AND NOT "does not clear"** (codex on model#136). An earlier
> version of this table called `2.3646` *"the correctly calibrated"* floor and used it to
> declare every member non-clearing. `t(n−1)` is a **reference** threshold, correct only
> if the block means are i.i.d. Normal. **No null calibration for the block statistic was
> ever supplied here**, and the supporting #134 geometry has **`gap = 0` on every row** —
> so the blocks share label windows and the i.i.d. premise fails at the necessary
> condition, let alone the sufficient one (model#137).
>
> Fixing the *normal-vs-Student* error was real progress — comparing a block-`t` to 1.96
> on single-digit block counts is a defect at seven sites in this programme. **It did not
> make the comparison calibrated.** An instrument that cannot license *"clears"* cannot
> license *"does not clear"* either; the XGB row is different because it rests on a
> reproduction, not on a threshold.

Three independent subjects, three different reasons, and the same *absence* of an
established result.

## What tonight's two measurements add

1. **BOTH power ratios are WITHDRAWN — 47× and 0.91× alike.** Phase-0's *"MDE is 47× a
   plausible gain"* divided by a failing retrain candidate's residual, and I "corrected"
   it to **0.91×** against the deployed recipe's `genuine_ic`. Codex on model#132: the
   numerator is not a valid detection floor — model#129's null is a
   **dependence-sensitivity diagnostic** whose MDE is explicitly **non-decisional** — and
   the denominator is **the wrong estimand**: a deployed *single-recipe* `genuine_ic` is
   not an *ensemble increment*. **Accepted in full.** What survives is only the provenance
   correction: the prereg named `+0.00079` "the production recipe's `genuine_ic`", which
   is the wrong subject; the deployed recipe reads **+0.04153**
   `[VERIFIED — model#132]`.

   **The uncomfortable part:** I flagged the category error in this very document —
   *"neither number is an ensemble gain"* — and then used the ratio as a headline anyway.
   Naming a defect does not license using the thing that has it. **GOAL-4's power is
   unmeasured; it is not 47×-short and it is not marginal.**
2. **The one screen that showed a blend advantage does not survive a correct bar.**
   Naive `t = +6.19` → block `t` **1.47 / 1.51 / 1.46 / 1.35** at `L = 60/90/120/250`;
   **84.7%** of the advantage is in the tails; the two arms correlate **ρ = 0.831** day
   to day `[VERIFIED — 本次实测 2026-07-31, model#134]`.

So what the design can detect is **unknown**, and the evidence it has contains no
demonstrated blend advantage. Those are two separate gaps, and neither is a power claim.

## The redundancy ceiling, stated conditionally

For an equal-weight two-member blend the IC amplification ceiling is
`√(2 / (1 + ρ))`. At the **measured** ρ = 0.831 that is **1.045×** — at most **+4.5%**
over a single member `[DERIVED]`.

**This is conditional and must not be quoted flatly.** The 0.831 was measured between two
*configurations* (`blend_clean` vs `rank60_clean`), not between two ensemble *members*,
and the formula assumes equal member IC and equal variance, which they do not have
(sd 0.844 vs 0.735). It is an order-of-magnitude statement: **at correlations in this
range, blending buys percent, not multiples.**

## Registered decision rule, frozen before any further GOAL-4 run

GOAL-4 does not proceed to a combination study until **at least two** members each clear
a preregistered, dependence-aware bar **individually**, on a gap-honest geometry
(`gap ≥ h`), with matched per-arm placebos.

> **THE FREEZE IS A DEFAULT, NOT A VERDICT — and it has an unblocking condition**
> (codex on model#136). As written, this rule blocked a combination study on the basis
> of members "not clearing" a bar that **is not calibrated**. That is the same
> instrument doing the blocking that cannot do the adjudicating, and a freeze resting on
> it would be unliftable by construction: no procedure exists to produce the "clears"
> that would release it.
>
> So the rule is split:
>
> * **What holds today, on no inferential claim at all:** no combination study, because
>   the premise is *unmeasured* and a blend over members of unknown skill is a search
>   over weights that will find something. This is a **prior-discipline** freeze
>   (`[DERIVED]` from rule 1 below), and it needs no bar to justify it.
> * **What the freeze may NOT do until a validated procedure exists:** cite any member's
>   block-`t` as evidence *against* it. `−2.31` and `+1.31` are inputs awaiting an
>   instrument, not findings.
> * **The unblocking condition, stated so it is reachable:** a dependence-preserving
>   null for the block statistic on a `gap ≥ h` geometry — a bootstrap of each arm's own
>   persisted per-date series is sufficient and is the cheap route (GOAL-4's Phase-0
>   screen already demonstrated it with 508 real rows). Once that exists, this rule
>   becomes evidential and either releases or binds **on measurement**.

Specifically:

1. **Member viability first.** No blend is fitted, screened or scored while zero members
   have cleared. A combination of un-skilled members is a search over weights, and the
   search will find something.
2. **The bar is computed at the realised geometry**, never borrowed, and **`t(n−1)` is
   not that bar**. On single-digit block counts the Student *reference* is `t(n−1)`, not
   1.96 — the trap that already turned `−2.31` from "decisive" into "un-resolved". But
   correcting normal→Student only removes one error; the bar itself must come from a
   **null calibrated at the realised geometry, with `gap ≥ h` between blocks**. Until
   that null exists, no `t` in this lane is compared to any threshold at all.
3. **Redundancy is measured before combination, not after.** Two members whose per-date
   series correlate above 0.8 do not need a blend study; they need a different second
   member.
4. **Persist the per-date series of every arm.** The GOAL-7 total-return run cannot be
   recalibrated today because it did not, and that is a permanent, unrecoverable loss
   (see model#131).

## What this is NOT

**Not a KILL.** #569 claimed one, independent re-verification downgraded it to WEAKENED
on a mistraced checkpoint, and #570 reverted it. Nothing here re-litigates that. The
statement is narrower and better supported: **the premise is unmeasured, the members are
individually un-skilled as measured, and the next action is member viability — not
combination.**

**Not a claim that any member is refuted.** `+0.0096 (t = +1.31)` and `−0.0556 (t = −2.31)`
are both **un-resolved**, not negative results.
