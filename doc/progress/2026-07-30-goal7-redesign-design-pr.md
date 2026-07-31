# A design PR, before a prereg — because 44:3 is the actual problem   (PR pending)

STATUS:    in-progress  (DESIGN FOR DISCUSSION — nothing frozen, no run may execute)
WHAT:      Puts the GOAL-7 Stage 1 redesign up as a **design document for review**,
           with four candidate approaches and an explicit request that the approach be
           settled before anything is frozen.
WHY/DIR:   Over the last day this line produced **44 prereg commits and 3 design
           commits**. Every rejected preregistration was a DESIGN error caught at review
           of a FROZEN artifact — an adjustable threshold, a control that could not fire,
           an unsourced bound, a contaminated holdout, an invalid inferential unit. A
           freeze is the wrong place to find out a design is wrong.
EVIDENCE:  n/a — makes no model or data claim. §2's arithmetic is `N/h` on a stated window.
NEXT:      Review settles B-vs-C (§5). Only then does a preregistration get written.

## The number that made this necessary

`44` prereg commits to `3` design commits in twenty hours
`[VERIFIED — git log origin/main --since=20h, grep -c]`. That ratio is the methodology
defect, not any single rejected document.

## What is being decided

Not "how do we fix the statistics" — that part is settled and dull (HAC with lag ≥ the
label horizon is the textbook treatment, and it is what should have been written first).

The real question is whether to test **the hypothesis that was actually raised**, at the
~9 independent-equivalent observations the uncontaminated window supports and a likely
*"cannot tell"*, or to register the **short-horizon** version as its own separate
question, which has far more statistical grip but is a different claim and must not be
dressed up as a rescue of the first.

## The thing I got wrong before this

I recommended **parking GOAL-7** on the grounds that a redesign would probably return
"cannot tell". That was letting my own design error set the research agenda, and it is
withdrawn. A goal is not disproven by my having measured it badly.

## Review round N — `gap >= h` does not establish independence, and I claimed it did

Codex: *"`gap >= h` removes direct label-window overlap, but it does not make the
separated block statistics independent. Predictor persistence, market regimes, and
dependence beyond the label horizon can still correlate blocks."* Accepted.

**What the arithmetic buys, precisely.** A gap of `h` removes *label-window overlap* —
the exact mechanism that made adjacent 60-day blocks share half of every 120-day label.
That is real and checkable. It does **not** remove dependence: momentum is persistent
and regimes span quarters, either of which can correlate blocks separated by a gap sized
only to the label horizon. **Removing one known dependence channel is not removing
dependence**, and I wrote it as though it were.

That error is not confined to this PR. The **T18 template row** I wrote calls a gap
*"the only construction that removes the dependence rather than shrinking it"*. Same
overstatement, in the artifact meant to stop the next study making it. Flagged here; it
needs the same correction on that PR.

**The simulation was labelled a measurement.** §3.1a called the 0.0473 / 0.0508 / 0.0495
false-positive rates *"the first measured confirmation that `gap >= h` does what §3.1
claims"*. They are simulation outputs conditional on an assumed `ρ`/`c²` — and the
Sensitivity paragraph two lines below **already conceded that `c²` is an assumption**, so
the document contradicted itself within one section. Relabelled as conditional
sensitivity analysis. §3.1b had the same shape with real geometries feeding simulated
sizes; real inputs on one axis do not make the output a measurement.

**Every critical value in §3 is now UNRESOLVED**, with a banner over the table saying
so, and the `dependence-valid?` column reads NOT ESTABLISHED for A / C′ / C″ instead of
**valid**.

**The recommendation survives, on a different footing.** Review is right that the MDE
ranking cannot prefer B over C while the bars are unestablished — `0.995 vs 0.447 σ_x`
decides nothing today. But the argument for B never needed it: **B asks the question the
U-shape actually posed** and C asks a different one, which §4 already refuses as a
horizon-search rescue. So B is recommended on *legitimacy of the question*, and the
recommendation does not move if a valid calibration later reverses the power ordering.

**Nothing is runnable.** Before execution the design owes a dependence-preserving,
preregistered null calibration on the real pre-2021 series — not a simulation under an
assumed DGP — or an argued case that the required block independence holds.

`[VERIFIED — this session]` 30 tests pass; the MDE tool and block arithmetic are
untouched, only what the document claims about them.
