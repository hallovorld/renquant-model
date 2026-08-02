# GOAL-7 v2 prereg drafted: same candidate, gap-block inference (freeze candidate)

STATUS: planned (frozen registration; freeze happens ONLY on merge; NO run
has been executed before that).
WHAT: doc/research/2026-08-02-goal7-momentum-v2-prereg.md — the v2
preregistration: candidate/inputs/estimand carried from v1 BY DIGEST;
inference replaced by the Stage-0-proven gap-block geometry (h=20 blocks
`[VERIFIED — prior work, model#161 §3]`, gap=20
`[VERIFIED — prior work, model#173 gap>=h independence rule]`, block-t with
df-aware bars, no HAC/AR/bootstrap in the decision path); an adequacy valve
on the machine itself (|rho_1(block means)| >= 0.25
`[ASSUMED — design choice, not separately calibrated]` refuses); positive
AND negative controls adapted to the block machine with frozen rates
(>=80% / <=10% `[ASSUMED — design choice, not separately calibrated]`,
1,000 seeded reps `[ASSUMED — design choice, smaller than v1's 5,000]`);
v1's decision-map shape, MDE ceiling 0.06
`[VERIFIED — prior work, model#164 §4]`, placebo discipline, and
single-shot execution contract retained with a NEW predeclared run dir.
WHY/DIR: v1 sealed UNRESOLVED-METHOD — the AR(1) family honestly refused the
measured dependence (rho_1 0.9269, oscillatory
`[VERIFIED — prior work, model#189]`). v2 avoids dependence modeling instead
of fitting a bigger family that might also fail adequacy. Backlog anchor
model#190; operator mandate: keep exploring.
EVIDENCE:
  artifact:      doc/research/2026-08-02-goal7-momentum-v2-prereg.md
  prod or exp:   exp — preregistration text only; no execution, no statistic
  existing data: v1's published ACF + realized T=2378 (model#189, sealed
                 result sha 46118a12...) `[VERIFIED — prior work, model#189]`;
                 n_blocks 59 and the df=58 bar 2.0017 are DERIVED from that
                 realized T and marked as governed by the run's own realized
                 values
  best-known?:   yes — the only dependence-avoiding device already validated
                 in this program (Stage-0 gap-blocks + df-aware bars)
  scope:         docs-only; the runner diff is a separate PR gated on this
                 merge; where they disagree, this document governs
  r2 amendment:  §3 ordering gains (c′), the degenerate-scale valve —
                 `realized_block_sd` non-finite or `<= 0.0` publishes the
                 value and returns UNRESOLVED-METHOD before any control runs.
                 Grounded in MEASURED library behaviour rather than argued:
                 `numpy 2.0.2` gives four different outcomes for four
                 degenerate scales and THREE of them return silently, while
                 the one-sample t on the resulting constant vector is `inf`
                 — a value that clears ANY finite bar
                 `[VERIFIED — direct run, 2026-08-02]`. Without the valve the
                 licensed run's verdict would have been decided by a library
                 default that happens to PASS.
NEXT: codex review rounds (v1 needed five amendments — the review IS the
safety net) → merge = freeze → runner-diff PR → single --execute at the NEW
run dir → sealed verdict. AC6: N/A — research prereg.
