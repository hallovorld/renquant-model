# GOAL-4 A1.9 — the pinned plausibility bound was not reproducible   (PR pending)

STATUS:    planned  (registration + tool; NO re-run executed, no verdict moves)
WHAT:      Commits `tools/goal4_plausibility_bound.py` — a fully specified, seeded
           construction producing an ALTERNATIVE plausibility bound `P = +0.01355` —
           plus 8 tests, and registers it as A1.9. A1.8's rule and its `P = +0.01897`
           ceiling both stand, but +0.01897's own construction is NOT made reproducible
           by this PR; A1.9 instead proves the GOAL-4 disposition is invariant
           whichever bound is used, and A1.9.1 registers a GATE: the re-run may not be
           ADJUDICATED against +0.01897 while its construction is unrecorded.
WHY/DIR:   A1.8 pinned `P` against codex's finding that the bound was adjustable, but
           stated the RULE without the CONSTRUCTION and committed no code. An
           independent re-derivation returned +0.01355 against A1.8's +0.01897 (s.e.
           0.00274 vs 0.00267). A threshold in a frozen prereg that cannot be
           recomputed from the document is pinned in name only.
EVIDENCE:
  artifact:      tools/goal4_plausibility_bound.py (+ tests/test_goal4_plausibility_bound.py)
  prod or exp:   experiment — prereg registration tool; no live-surface change (see
                 "Live-surface impact" below)
  existing data: doc/progress/2026-07-30-goal4-amendment1-empirical-control.md registers
                 A1.8's ceiling P = +0.01897 (s.e. 0.00267), sourced from a Monte Carlo
                 construction described in prose only; grep of doc/research/ and tools/
                 at that commit found no committed generating code for that number.
  best-known?:   worse (smaller, less generous-to-the-hypothesis) than A1.8's +0.01897 —
                 this construction's +0.01355 does NOT replace the registered ceiling; it
                 is recorded as the best REPRODUCIBLE lower estimate, run via
                 `python tools/goal4_plausibility_bound.py` -> P = +0.01355 (s.e. 0.00274).
  scope:         this is tools/goal4_plausibility_bound.py, experiment, vs existing
                 registered ceiling A1.8 P=+0.01897 (unreproducible) — disposition
                 (UNRESOLVED, NO-GAIN closed) is invariant across both bounds since
                 MDG=+0.07180 exceeds both (3.78x / 5.30x); 8/8 tests pass.
NEXT:      If the equations behind +0.01897 are recorded, they supersede this estimate
           and the tool is updated to match.

## The defect is one level up from the one A1.8 fixed

Codex's #119 finding was that the plausibility bound had no source, quantity or rule,
so the UNRESOLVED-vs-NO-GAIN disposition stayed adjustable after seeing the screen.
A1.8 fixed that — it gives a rule and a number. But it does not give the construction
that satisfies the rule's two constraints at once (a member *exactly as strong as the
incumbent* **and** at redundancy 0.404), and no generating code was committed. So the
number cannot be recomputed by anyone holding only the document.

That is the same shape this amendment chain has been closing round after round — a
quantity fixed while its construction stays open. This PR does NOT close it for A1.8's
own number: `+0.01897`'s construction is still nowhere on record and is not
reconstructed here (see "Honest limits" below). What it commits instead is a second,
fully specified construction (`+0.01355`) plus a proof that the GOAL-4 disposition does
not depend on which of the two bounds is used — an invariance argument, not a
reproduction of the registered threshold.

## What is registered, and what deliberately is not

**Registered:** the construction. Gaussian copula on `(r, b, m)`, Spearman targets
mapped to Pearson by `ρ = 2·sin(π·ρ_s/6)`, the implied matrix **verified positive
definite and aborting if not** — a triple of Spearman targets need not be jointly
realisable, and nudging it into shape would silently change which quantity `P` measures.
Ensemble = per-date equal-weight average of member **ranks**, per §3, so `P` is a
**gain** in the decision rule's units rather than an IC. Seeded, no calibration loop.

**Not changed:** the ceiling stays A1.8's `+0.01897`, and its construction stays
unreproducible — this PR does not make that number recomputable, only the alternative
`+0.01355` is. `+0.01355` is recorded as an independently reproducible lower estimate
and is what CI asserts.

**Correcting my own reasoning for keeping the larger value.** I first wrote that
adopting the smaller re-derivation "would weaken the argument in this document's own
favour". That has the direction backwards. The rule is `MDG > P → UNRESOLVED`, so a
*smaller* `P` makes UNRESOLVED — the verdict this document already predicts — **easier
to reach**. Swapping in my own smaller number would be self-serving, and that, not
"generosity", is the real reason not to do it. A1.8's framing is sound for its own
purpose (a large `P` makes "underpowered" harder to claim, so the claim is robust when
it survives); what was wrong was my label for it and the inference I drew.

## Why this is safe to land: the disposition is invariant — and invariance is not enough

`MDG = +0.07180` exceeds both candidate bounds — 3.78× at +0.01897, 5.30× at +0.01355 —
so A1.8's registered outcome (UNRESOLVED, NO-GAIN closed) holds either way. **The tool
asserts that invariance and exits 1 if it breaks.** If a future geometry makes the two
constructions disagree about the outcome, that surfaces as a failure before any re-run
is adjudicated, rather than being discovered afterwards by whoever prefers one number.

But codex's BLOCKER on this PR is right that **invariance across two bounds is weaker
than reproducibility of the operative one**, and the first version of these documents
claimed the latter in its title, headings and summary while delivering the former. That
is the overclaim, and it is the more serious half of the finding — an artifact that
says "closed" is worse than the gap it describes, because it stops anyone looking.

So A1.9.1 gives the gap teeth: **the re-run may not be ADJUDICATED against `+0.01897`
while its construction is unrecorded.** Producing it is fine; deciding with it is not.
Until the equations are committed the operative comparison uses the reproducible
`+0.01355`. This costs nothing today, which is precisely why it is registered now
rather than argued when one of the numbers happens to suit someone. Note the fallback
runs in the self-serving direction flagged above — accepted deliberately, because an
unauditable threshold is the worse defect: a bias that is stated and bounded can be
checked, a number nobody can recompute cannot.

## Honest limits

- **I did not resolve which construction produced +0.01897.** A1.8 attributes it to
  empirical α-calibration at the panel width per A1.2, and the *sign* of the
  disagreement is what that correction predicts — a genuinely stronger synthetic member
  yields a larger gain — but the equations are not recorded, so I could not reproduce
  it and did not guess at it.
- This is a reproducibility fix, not a power fix. GOAL-4 Phase 0 remains underpowered on
  this panel; a re-run can VOID or return UNRESOLVED and cannot conclude against
  ensembling.

## Live-surface impact

None. One tool, one test file, one amendment section. No re-run executed, no config,
artifact, state or launchd change, no pin advance.
