# T18: blocking discharges T2 only if you do the arithmetic   (PR pending)

STATUS:    delivered

NOTE ON ORDERING: T18 is inserted after T12, not after T17, because the T17 row is still
in an unmerged PR (#125). If #125 lands first the rows will simply sit in numeric order;
neither depends on the other.
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

## Round 2 — my "option 2" was the same mistake the row exists to catch

Codex: *"option 2 is not an inferential remedy. Writing down a nonzero residual crossing
fraction under `L ≫ h` does not make ordinary block `t` tests, permutation calibration,
or their nominal degrees of freedom valid."* Correct, and it lands on exactly the
instinct that produced the original defect.

The first version said: `L ≫ h`, state the residual crossing fraction as a number, done.
That offers **disclosure as a remedy**. An honest number attached to an invalid statistic
is still an invalid statistic — and a template that accepts it invites the next study to
pick a larger arbitrary `L`, write a footnote, and reproduce the 2026-07-30 void with
better documentation. Stating the residual dependence is **necessary and not sufficient**.

Three registrable options now, replacing two:

1. a **gap ≥ `h`** between retained blocks — removes the dependence structurally;
2. **non-overlapping labels** — removes it at source;
3. `L ≫ h` **only together with** (a) a preregistered justification for why the residual
   is tolerable *for this estimand*, and (b) a **named inference method whose stated
   validity conditions cover that dependence**, registered before the run with its own
   failure condition. Explicitly disqualified: a null that permutes the dependence away,
   since it calibrates a different estimator than the one it certifies — which is what
   the failed study did.

Options 1–2 are preferred because their validity is structural; option 3 is a promise
about an estimator, and promises get checked.

**Second finding, also accepted:** `ceil(h/L)` is a **maximum span, not a count every
label achieves**. How many subsequent blocks a label reaches depends on the date's
position in its block — enumerating all positions at `L=60, h=120` gives spans of
{1, 2}, not a constant 2 [VERIFIED — enumerated this session]. Stated as a bound now.

**Added, because the honest options cost real power:** a line requiring the power budget
to be computed *before* freezing. On a 1,082-date window with `h = 120`, contiguous
`L = 120` gives 9 blocks and `L = 120` with a `120`-day gap gives **4** [VERIFIED —
computed 2026-07-30]. If the valid design cannot clear the floor, that is the finding and
it belongs in the registration — not discovered after a run has already spent the window,
which is how this line got here.

Also now required in the frozen text: the resulting **inferential unit and its degrees of
freedom**, since under all three options that number is generally *not* `n_blocks − 1` —
the specific thing the voided study got wrong.
