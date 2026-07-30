# T17: compare to a baseline BOTH ways, or you cannot tell veneer from signal   (PR pending)

STATUS:    delivered
WHAT:      Adds trap **T17** and section **§5c** to the prereg template: when a naive
           baseline is in play, register the orthogonalisation in **both directions** and
           fix the reading in advance, as a KILL condition rather than a diagnostic.
WHY/DIR:   §5b already asks whether a naive baseline *matches* the candidate. GOAL-7
           Stage 1 showed that is not enough — the direction of survival is what settles
           whether the candidate is the signal or its veneer.
EVIDENCE:  §1. This PR makes no new model or data claim; every number is prior work.
NEXT:      none — the template is the deliverable.

## §1 EVIDENCE — what earned the section

GOAL-7 Stage 1 (model#124) registered this as its §4 kill condition and the decisive cell
obtained `[VERIFIED — prior work, model#124 results.json and its appended adversarial
review]`:

| arm | spread | `\|t\|` | clears 2.110? |
|---|---|---|---|
| raw `u = \|z(mom_12_1_tr)\|` | +0.2381 SD | 3.270 | yes |
| `C ⊥ B` — `u ⊥ \|z(vol_60_tr)\|` | +0.1161 SD | **1.644** | **no** |
| `B` alone — `z(vol_60_tr)` | **+0.3477 SD** | **+4.610** | yes |

and `B` **survived** orthogonalisation to `C` while `C` did not survive orthogonalisation
to `B`. Verdict **VOLATILITY-TILT**, nothing licensed.

**Without the second direction this reads as "the candidate is weakened."** With it, it
reads as "the candidate is a veneer on the baseline" — a different conclusion, reached
from the same raw arm.

## §2 Why it is a KILL condition and not a caveat

A caveat gets narrated around; a registered cell does not. §5c fixes all four
`(C ⊥ B, B ⊥ C)` outcomes in advance, and in the `no / yes` cell the raw arm's own
significance **may not be cited against the verdict**.

## §3 The prior this encodes

Volatility has now accounted for the apparent effect on **two of two** subjects tested on
this panel: the production XGB's traded estimand (reproduced by a single `STD20` sort,
collapsing to `−0.0554` orthogonalised to `STD60`) and the two-sided momentum transform.
So §5c states that `B` should be a volatility statistic unless there is a stated reason
otherwise. That is a prior about **this corpus**, recorded as such, not a general claim
about momentum.
