# Progress: GOAL-6 Stage 0 prereg (frozen)

STATUS:   prereg FROZEN, no run yet. Docs only.

WHAT:     Adds `doc/research/2026-07-28-goal6-stage0-prereg.md` — a measurement-only
          study: 3 statistics (IC, decile spread, top-decile hit rate) x 2 horizons
          (20d, 60d) on already-trained models, two nulls, block-level inference,
          plus IC-vs-horizon profiles.

WHY/DIR:  GOAL-6 Stage 0 (orchestrator design §5). No model is trained, promoted or
          killed by it; it decides which statistic and which measurement horizon
          Stages 1-2 should use. Opens with a mandatory known-trap checklist (T1-T8),
          each row naming a real past failure and how this design avoids it — T1 is
          this session's own defective shift-120 placebo.

EVIDENCE: the defect that forced T1 `[VERIFIED — wf-eval/diagnostics.log]`: the
          score's IC-vs-lag profile is +0.028 at lag 0, +0.071 at 60d and peaks at
          **+0.078 (t=3.21) at 100d**, so a +120d shift sits near the PEAK of the
          score's real predictive profile rather than on a null — making
          `real - shift` structurally negative. Replacement nulls are within-date
          permutation (measured clean: -0.0008) and a persistence-matched control
          (cross-sectional rank autocorrelation 0.59 @1d, 0.30 @60d). No IC/Sharpe
          claim is made by this PR, so the §4(b) triad applies to the results doc.

NEXT:     Run Stage 0 (CPU-only; the 43-fold scoring precedent ran 11s/fold), then a
          results doc with the H1/H2/H3 verdicts and an explicit recommendation for
          the Stage-2 primary statistic and measurement horizon.
