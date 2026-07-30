# T17: register the residualisation both ways, as a shared-variation diagnostic   (PR #125)

STATUS:    delivered
WHAT:      Adds trap **T17** and section **§5c**: when a naive baseline is in play,
           register the residualisation in **both** directions before the run, with the
           four outcomes fixed in advance and **conditional on a dependence-valid design**.
WHY/DIR:   §5b already asks whether a naive baseline *matches* the candidate. It does not
           separate the candidate's own contribution from what the two share.
EVIDENCE:  n/a — this PR makes **no** model or data claim. See §2.
NEXT:      none — the template is the deliverable.

## §1 What changed after review

The first revision of this PR grounded §5c in the numeric result of model#124 and asserted
a "two of two subjects" volatility prior. **Both are withdrawn.**

model#124 is VOID: its 60-trading-day blocks sit under a 120-trading-day label, so the
block means it treated as independent are not, and neither arm is established — a
comparison between two arms on an invalid inferential unit does not become valid because
one number is larger. Citing those figures to motivate a template row would propagate a
retracted result into every future preregistration.

The "two of two" prior is withdrawn for a second reason as well: the other subject
(`2026-07-29-traded-estimand-prereg`) is itself one of five designs sitting at `L = h`,
which T18/§4a shows still crosses on **every** date. So **no study on this panel has
demonstrated the volatility axis under a design that discharges §4a**, and §5c now says
exactly that.

## §2 The epistemic claim is narrowed

Review: *"two directional residualisations are a valuable precommitted diagnostic against
shared variation, but they do not themselves identify causal direction or settle which
factor is the signal."* Accepted. §5c now:

- calls itself a **shared-variation diagnostic**, not a causal test;
- states explicitly that an asymmetry is consistent with `C` being a noisy proxy for `B`,
  with both proxying a third unmeasured factor, and with the arms having different
  measurement error — **none of which it separates**;
- describes each cell as an **admissibility** outcome for the registered hypothesis rather
  than a statement about which variable is "the signal";
- makes the whole section **inert unless §4a is discharged**: if the inferential unit is
  invalid, §5c produces no verdict at all.

What survives unchanged is the discipline: register both directions **in advance**, and in
the `no / yes` cell the raw arm's own significance may not be cited against the verdict.

## §3 The baseline-choice line, downgraded

§5c still suggests a volatility statistic as the default `B`, but now as **a prior about
where to look**, explicitly not an established finding, with the reason stated. That is the
strongest form the evidence currently supports.
