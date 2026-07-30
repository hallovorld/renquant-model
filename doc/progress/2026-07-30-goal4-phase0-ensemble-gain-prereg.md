# GOAL-4 Phase-0 ensemble-gain screen — frozen registration   (PR pending)

STATUS:    planned  (frozen registration; NO run has been executed)
WHAT:      Gives GOAL-4 its first acceptance criterion. Registers a cheap, decisive
           screen: does an unfitted equal-weight rank-average of the existing scorers
           beat the DEPLOYED scorer, measured as a within-date paired difference on
           identical rows, against a finite-sample critical value?
WHY/DIR:   GOAL-4 has had zero work for weeks and the cause is structural — it never
           had a measurable pass condition, so it could only be discussed. Its record
           is also easy to misstate: #569 claimed KILL, independent re-verification
           returned WEAKENED because the PatchTST checkpoint was mistraced, and #569
           was reverted via #570. GOAL-4 is neither killed nor delivered; it is
           undefined. This defines it.
EVIDENCE:  n/a — this PR makes NO model or data claim. Every number it cites is
           tagged as prior work with a reference; nothing was measured for it.
NEXT:      Establish each member's served-artifact identity (abort gate), seal the
           bundle, run. Verdict withheld pending adversarial review.

## The one argument this design refuses to make

The tempting shortcut is: every candidate member is individually insignificant,
therefore the ensemble is null. **That is wrong, and the prereg registers why so it
cannot be used later.** Two members each carrying a small true edge, each individually
underpowered, can combine into a detectable one — variance reduction is precisely the
mechanism an ensemble exists to exploit. Individual insignificance under low power
does not establish zero edge. So the combination is tested **directly**.

That is also why this screen is worth running rather than skipping, despite prior
numbers that look discouraging: `genuine_ic` above the placebo floor is **+0.00079**
`[VERIFIED — prior work, renquant-backtesting#83]`, the prod XGB's traded estimand is
reproduced by a single STD20 sort and collapses to −0.0554 orthogonalised to STD60
`[VERIFIED — prior work, memory panel-signal-identity-capacity]`, and the tail
statistic has led IC on 4 of 4 subjects while clearing no bar
`[VERIFIED — prior work, same memory]`.

## Two design choices that decide whether the result means anything

**The benchmark is registered a priori as the PRODUCTION scorer.** "Does the ensemble
beat the best member?" is biased when *best* is read off the same data — the winner's
margin is inflated by selection. Naming the deployed scorer in advance removes the
choice entirely, and it is the operationally relevant comparison anyway: an ensemble
that cannot beat the incumbent is not worth deploying.

**The positive control is a synthetic member with a KNOWN inserted edge (IC ≈ +0.05).**
The harness must detect that gain or the screen is VOID. Without it, a "no gain"
result would be indistinguishable from a harness incapable of seeing one — the same
failure that sank a design on this programme when a signal-free control passed its bar
37.5% of the time `[VERIFIED — prior work, 2026-07-29 closure retraction, count 4]`.

## Calibration, carried over from a defect caught hours ago

The critical value is one symbol, `T_crit = max(P95_null, t_{0.975, n_blocks-1})`,
used for treatment, both controls and every gate. Frozen at 1.96 this screen would
have used a bar about **17% too low** at `n_blocks = 8`, where the correct Student-t
value is **2.3646** `[DERIVED — scipy.stats.t.ppf(0.975, 7)]`. That error was mine, in
PR #113, and codex caught it before any run; it is not repeated here. The block
arithmetic clause (`floor(N_eval/60)`, remainder dropped, never equal-weighted) comes
from a second defect found today, where 10 blocks were formed instead of 9 and a
5-day trailing block was equal-weighted, inflating a headline `t` by 15.6%
`[VERIFIED — prior work, model#110 ERRATUM]`.

## Live-surface impact

None. Two documents. §6 states explicitly that GO-PHASE-1 licenses writing a Phase-1
design and nothing else — no deployment, no config or artifact edit, no launchd
change, no pin advance.
