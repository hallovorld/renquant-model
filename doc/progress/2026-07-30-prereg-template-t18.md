# T18: blocking discharges T2 only if you do the arithmetic   (PR pending)

STATUS:    delivered
WHAT:      Adds trap **T18** and section **§4a**: under an overlapping label, register the
           **crossing fraction** `min(1, h/L)` and the blocks touched `ceil(h/L)`, and
           pick either a gap of `h` between blocks or `L ≫ h` with the residual stated.
WHY/DIR:   T2 already names overlapping labels. A study on 2026-07-30 applied blocking,
           treated T2 as discharged, and was VOIDED because its block was **half** the
           label horizon.
EVIDENCE:  §1. No new model or data claim; every number is arithmetic or prior work.
NEXT:      Five frozen designs sit at `L = h` and none states its crossing fraction.
           Raised here as a template row, **not** as five challenges — see §3.

## §1 THE ARITHMETIC

A date at position `p` in a block ending at `L` has its label window reach `p + h`, so it
crosses whenever `p + h > L` `[DERIVED]`:

| `L` | `h` | crossing fraction `min(1,h/L)` | blocks touched `ceil(h/L)` |
|---:|---:|---:|---:|
| 60 | 120 | **1.00** | **2** |
| 60 | 60 | **1.00** | 1 |
| 120 | 120 | **1.00** | 1 |
| 120 | 60 | 0.50 | 1 |
| 240 | 60 | 0.25 | 1 |

## §2 A CORRECTION TO MY OWN FIRST REMEDY

Accepting the VOID, I wrote that *"a dependence-valid block must satisfy `L ≥ h`"*.
**Wrong.** At `L = h` the crossing fraction is still **1.00** — every date crosses; the
span merely drops from two adjacent blocks to one. I framed a reduction as a fix, one
round after accepting a defect of exactly that shape. §4a therefore requires **either** a
gap of `h` between retained blocks (removes the dependence) **or** `L ≫ h` with the
residual `h/L` written down as a number.

## §3 Scope — five designs, and why this is a template row

Sweeping the 29 frozen and result documents on `origin/main` for the `(block, horizon)`
pair `[VERIFIED — regex sweep over git show origin/main -- doc/research/*.md]`: the voided
study is the **only** one with `L < h`. **Five** sit at `L = h`:
`2026-07-29-traded-estimand-prereg`, `2026-07-30-goal4-phase0-ensemble-gain-prereg`,
`2026-07-30-patchtst-closure-prereg-v2`, `2026-07-30-v1-v2-pit-ab-prereg`, and
`2026-07-30-momentum-total-return-prereg` (120/120).

**I am not claiming those five are void.** `L = h` bounds the dependence to one adjacent
block, which some may absorb, and two use a permutation null whose calibration would need
separate examination. The claim is narrower and checkable: **none of them states its
crossing fraction**, so none has addressed it — the arithmetic above appears in none of
them, including the ones I wrote.
