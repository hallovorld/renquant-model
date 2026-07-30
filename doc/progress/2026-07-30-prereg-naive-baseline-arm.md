# Progress: prereg template — §5b naive-baseline arm made testable, decoupled from an unpinned result   (PR #108)

STATUS:    delivered — fix applied to this head in response to codex's two
           CHANGES_REQUESTED reviews (both submitted 2026-07-30).

WHAT:      Adds trap **T16** and **§5b NAIVE-BASELINE ARM** to
           `doc/research/templates/PREREG_TEMPLATE.md`: any confirmatory
           subject whose estimand is a cross-sectional selection statistic
           (IC, decile spread, hit rate) must register a naive
           single-column baseline, a rank-orthogonalised neutralised arm, a
           within-baseline-decile conditional-pooling arm, and a decision
           rule stated as a testable gate.

           This fix, on top of the original commit:
           1. Removed the unpinned `+0.2534 sd` / block `t +3.25` / `STD20
              +0.2836 sd` / `-0.0554` narrative from both the T16 trap row
              and the §5b prose, replacing it with the general
              methodological rationale it was illustrating. No artifact in
              this repo pins those numbers (grepped `doc/research/` and
              full git history for `0.2534`/`0.2836`/`STD20` — the only hit
              is this PR's own commit), so template-governing text is not
              the place to carry them (codex BLOCKER).
           2. Bullet 1 now requires the baseline to be frozen and
              fingerprinted BEFORE execution: attribution method, frozen
              artifact/checkpoint path + sha256, transform, missing-value
              rule, direction, one-column portfolio construction —
              mirroring §3's existing input-provenance convention (codex
              P1: "not reproducibly selected or operationalized").
           3. Bullet 4 now registers a testable gate: a paired contrast on
              the SAME folds/blocks as §4's primary estimator, the
              estimator + inference rule for that difference, how the
              predeclared margin (§6) applies to the difference rather than
              to each arm's marginal significance, and family-wise error
              handling when multiple baseline/neutralised/conditional arms
              are registered (codex P1: "comparing two separately
              significant t statistics does not establish that the subject
              beats the baseline").
           4. Restored the blank line before `## 1.` that the original
              commit had dropped when it inserted the T16 row.

WHY/DIR:   Continues the prereg-template line (see
           `doc/progress/2026-07-29-prereg-template.md`): every trap row
           exists because a real confirmatory subject paid for it once. §5b
           closes the gap that a clean placebo panel is structurally unable
           to detect a naive single-column tilt — placebos test "is this
           noise", not "is this a raw column". Codex's two reviews
           (2026-07-30) held this head to LONG agreement #5 (no number
           without a provenance tag / evidence surface, applied here to
           template text, not just study results) and to making "beat the
           baseline" an actual testable gate rather than an unoperationalized
           aspiration. Both are now named in the frozen text.

EVIDENCE:  n/a — docs/template-only change; no model, data, or production
           claim is made. The fix's entire point is to remove the one
           specific-number claim the original text made without a pinned
           artifact, per codex's own suggested resolution ("compress the
           template to the general methodological rationale"). Only
           `doc/research/templates/PREREG_TEMPLATE.md` is touched in this
           PR; verify via `git diff main...prereg/require-naive-baseline-arm`.

NEXT:      Use §5b's frozen text on the next confirmatory subject whose
           estimand is a cross-sectional selection statistic — the open
           momentum/reversion and v1/v2 PIT workstreams are the first
           candidates that will need to register a baseline arm under this
           section.
