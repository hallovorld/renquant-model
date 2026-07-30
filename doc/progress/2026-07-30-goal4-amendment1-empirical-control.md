# The GOAL-4 positive control could not pass; the design was mine   (PR pending)

STATUS:    planned  (registered amendment; NO re-run has been executed)
WHAT:      Replaces §5.1's closed-form `α` with an empirical calibration on the panel's
           own geometry, and derives the acceptance band from the calibration's standard
           error instead of asserting `±0.01`.
WHY/DIR:   model#118 executed the frozen prereg and VOIDed on §5.1. The frozen text
           worked as intended — it forbade adjusting `α` and forced a VOID rather than a
           tuned pass. The defect is in the design, which I wrote.
EVIDENCE:  §1. No re-run has been executed against this amendment.
NEXT:      Re-run the whole frozen sequence from §2, not just the control — no arm of the
           study has a result.

## §1 EVIDENCE, including a retraction of my own first account

§5.1 fixed `α` from `ρ_s = (6/π)·arcsin(ρ/2)`. **That identity is asymptotic**, so at
finite width the realised IC is not 0.05 and the `|mean − 0.05| ≤ 0.01` assertion was
unreachable — the control could not pass however correct the implementation.

I first said the real-panel shortfall exceeded clean simulation, implying a further
undiagnosed component. **That was wrong, and for a familiar reason: I compared against the
wrong width.** The universe is 145 tickers; the panel's mean admissible rows per date is
**115.4** (`364736 / 3161`) `[VERIFIED — tr_matrix_metadata.json]`. At the realised width,
2000 draws, seed 20260730 `[VERIFIED — scipy Monte Carlo, this session]`:

| n | mean realised Spearman | s.e. | 3·s.e. band |
|---:|---:|---:|---|
| **115** | **0.04232** | 0.00207 | **[0.03610, 0.04855]** |
| 141 | 0.04028 | 0.00196 | [0.03440, 0.04616] |

model#118's measured **0.03681** falls **inside** the n=115 band. So **finite-sample bias
at the panel's actual width explains the whole failure**, and the fix is sufficient rather
than merely necessary. The "further component" claim is retracted here rather than left
standing.

## §2 The replacement

Calibrate `α` **on the panel's own per-date admissible sets and rank structure**, not on a
synthetic iid cross-section of nominal width — the 145-vs-115 error above is exactly what
calibrating against an idealisation costs. Bisection to a mean realised IC of 0.05, 2000
draws, seed 20260730, tolerance `1e-4`, ≤40 iterations. The acceptance band is **derived**
as `±3` standard errors of that calibration (≈ `±0.006` at 2000 draws) rather than
asserted. No `α` reaching 0.05 ⇒ VOID. `α` is still never hand-adjusted after seeing a
result.

## §3 The generalisation

Two of my designs failed the same way within hours: a **1.96** critical value frozen for a
`t` over single-digit blocks, and an **asymptotic** identity frozen as an exact
finite-sample target. Both are large-sample quantities applied at small `n`; both were
caught by review or by a control, not by me. Registered practice: **any constant derived
from an asymptotic argument is re-derived at the realised sample geometry before freezing,
and its tolerance derived from that same computation.**

## §4 Live-surface impact

None. One document. No re-run has been executed and nothing about the four outcomes or
their licences changes.
