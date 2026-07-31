# GOAL-4: the ensemble premise, evaluated against its own registered members

**Bottom line.** An ensemble needs members that (a) individually carry skill and (b) are
not redundant. **Every candidate member GOAL-4 has registered is measured, and none
clears a preregistered bar.** That is not a reason to close the lane — it is a reason to
stop treating "combine the models" as the next step, because there is nothing measured to
combine.

## The three registered members, as measured

| member | the measurement | clears its bar? |
|---|---|:--|
| **production XGB** | its traded estimand is reproduced by a **single sort on STD20** (**+0.2836** vs the model's **+0.2534**) and collapses to **−0.0554** when orthogonalised to STD60 | **no** — what it trades is a volatility tilt |
| **PatchTST** | margin over **its own 60-day-stale score** = **−0.0556 (t = −2.31)**, against the correctly calibrated **2.3646** at `n_eff = 8` | **no** — and the sign is negative |
| **certified clf** | **+0.0096 (t = +1.31)** | **no** |

`[VERIFIED — prior work, model#90; and the frozen §1 of doc/research/2026-07-30-goal4-phase0-ensemble-gain-prereg.md]`

Three independent subjects, three different reasons, the same answer.

## What tonight's two measurements add

1. **The power wall was mis-scaled, and the correction cuts both ways.** Phase-0's
   *"MDE is 47× a plausible gain"* divided by a **failing retrain candidate's** residual.
   Against the **deployed** recipe's `genuine_ic` of **+0.04153** the ratio is
   **0.0376 / 0.04153 = 0.91×** — the screen is **marginally powered, not hopeless**
   `[VERIFIED — 本次实测 2026-07-31, model#132]`.
2. **The one screen that showed a blend advantage does not survive a correct bar.**
   Naive `t = +6.19` → block `t` **1.47 / 1.51 / 1.46 / 1.35** at `L = 60/90/120/250`;
   **84.7%** of the advantage is in the tails; the two arms correlate **ρ = 0.831** day
   to day `[VERIFIED — 本次实测 2026-07-31, model#134]`.

So the design *can* detect an effect of the size the deployed recipe carries, and the
evidence it has does not contain one.

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
(`gap ≥ h`), with matched per-arm placebos. Specifically:

1. **Member viability first.** No blend is fitted, screened or scored while zero members
   have cleared. A combination of un-skilled members is a search over weights, and the
   search will find something.
2. **The bar is computed at the realised geometry**, never borrowed. On single-digit
   block counts the Student floor is `t(n−1)`, not 1.96 — the trap that already turned
   `−2.31` from "decisive" into "un-resolved".
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
