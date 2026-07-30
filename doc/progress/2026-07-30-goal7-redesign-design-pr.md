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
