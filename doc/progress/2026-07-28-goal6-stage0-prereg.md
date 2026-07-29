# Progress: GOAL-6 Stage 0 prereg (frozen)

STATUS:   prereg FROZEN, no run yet. Docs only. A prior head of this PR added a
          results doc claiming Stage 0 had "executed exactly as frozen" while the
          three findings below were still open — that was a preregistration
          violation (results cannot be valid for a still-open design) and has been
          reverted (`git rm`) in this pass; Stage 0 has NOT run. This pass also (a)
          rewrote `doc/research/2026-07-28-goal6-stage0-amendment-1.md` to remove
          every specific corpus/coverage/result number for subject (c) — even
          hedged ones — replacing them with a pure forward-looking admission
          contract, per the reviewer's explicit "remove entirely, not conditionally"
          instruction; and (b) froze the parent's previously-undefined rebalance
          spacing, block construction, and `SE_HAC` estimator (Newey-West, Bartlett
          kernel, lag = h_min - 1).

WHAT:     Adds `doc/research/2026-07-28-goal6-stage0-prereg.md` — a measurement-only
          study: 3 statistics (IC, decile spread, top-decile hit rate) x 2 horizons
          (20d, 60d) on already-trained models, two nulls, block-level inference,
          plus IC-vs-horizon profiles. This pass fixes 3 open review findings: (1)
          PatchTST's source-artifact contract — model#85's 43-fold `scores.parquet`
          is not yet pinned to a stable, reviewable source contract this design can
          cite (model#91's queued corpus-index evidence shows the underlying corpus
          is not simply nonexistent, just not yet merged/citable here), so PatchTST
          is now explicitly OUT OF SCOPE for this Stage-0 run (XGB ranker +
          top-decile classifier only, both scored against the already-on-disk
          `data/exp/oos_pick_table_recipe_v2.parquet` corpus); (2)
          §5's decision rule now uses a paired contrast (`t_pair`, same permutation
          draws for both arms) with Holm-Bonferroni multiplicity control across
          H1's 3 pairwise tests, and H2's "equal or lower effect size" is a hard
          numeric gate (`d_20d ≤ d_60d`), not narrative; (3) §3's persistence-matched
          control now specifies score alignment (same-ticker `t-60`), unavailable-
          score handling (drop that cell only, report coverage), and its own
          block-level variance (computed on its own eligible-date subset).

WHY/DIR:  GOAL-6 Stage 0 (orchestrator design §5). No model is trained, promoted or
          killed by it; it decides which statistic and which measurement horizon
          Stages 1-2 should use. Opens with a mandatory known-trap checklist (T1-T8),
          each row naming a real past failure and how this design avoids it — T1 is
          this session's own defective shift-120 placebo.

EVIDENCE: artifact:      wf-eval/diagnostics.log (T1 lag-profile measurement — the
          defect that forced this design's null choice)
           prod or exp:   experiment — a GOAL-6 design-doc measurement; no
          production path touched, no promotion/kill decision
           existing data: the score's IC-vs-lag profile is +0.028 at lag 0, +0.071
          at 60d, peaks at +0.078 (t=3.21) at 100d — so a +120d shift sits near the
          PEAK of the score's own predictive profile rather than on a null, making
          `real - shift` structurally negative; replacement nulls measured clean
          (within-date permutation: -0.0008), with the persistence-matched
          control's own confound also measured (cross-sectional rank
          autocorrelation 0.59 @1d, 0.30 @60d)
           best-known?:   this is the first documented diagnosis of the shift-120
          placebo defect; supersedes treating shift-120 as a valid null anywhere
          it is still used as one (model#85 still uses it — flagged there
          separately, not fixed by this PR)
           scope:         this PR's own T1 finding + the Stage-0 design; no
          Stage-0 run has executed under this PR (the removed results doc's
          numbers do not carry evidentiary weight and are not reasserted here); no
          IC/Sharpe or model promotion/kill claim is made

NEXT:     Re-review with the 3 findings above addressed and the premature results
          doc removed. After approval, run Stage 0 (CPU-only, XGB-scope) as its own
          step, then open a SEPARATE results PR (§6) — never bundled with this
          prereg — with the H1/H2/H3 verdicts and an explicit recommendation for
          the Stage-2 primary statistic and measurement horizon. PatchTST rejoins
          Stage 0 once model#85 or model#91's corpus index is merged and this
          design cites its exact artifact path and row/date fingerprint.
