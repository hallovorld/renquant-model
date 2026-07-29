# Progress: GOAL-6 Stage 0 results

STATUS:   delivered. Frozen prereg (model#86) executed with no design deviations;
          all three hypotheses resolved under §5.

WHAT:     Adds `doc/research/2026-07-28-goal6-stage0-results.md` — the decision grid
          (2 subjects x 3 statistics x 2 horizons x 2 nulls, block-level t), the
          IC-vs-horizon profiles, the verdicts, coverage gaps and disclosures.

WHY/DIR:  H1 INCONCLUSIVE and H2 NOT SUPPORTED, so Stage 2 keeps the current
          production choices (IC, 60d) rather than an unvalidated switch — the frozen
          rule's own default. H3 SUPPORTED for PatchTST, descriptive only.

EVIDENCE: `[VERIFIED — goal6-stage0/results.json, results_xgb.json]` The decisive
          result is the persistence-matched null: XGB's REAL-minus-persistence is
          positive in all 6 cells (+0.34..+1.59) while PatchTST's is negative in all 6
          (-0.79..-2.31) — a 60-trading-day-old PatchTST score predicts today's forward
          return better than today's score. Consistent with its lag profile (lag-0 IC
          +0.0278 vs lag-60 +0.0705, predicting -0.043 against -0.056 measured
          `[DERIVED]`). Permutation nulls clean (+0.0008..+0.0013); fold-level
          cross-check reproduces the 43-fold run to 2dp. Top-decile clf NOT covered —
          no WF corpus exists and building one is forbidden by the prereg; the
          `h2_xgb_score_*` files were rejected as in-sample. No promotion/kill claim is
          made, so the §4(b) triad does not apply.

NEXT:     (1) correct the GOAL-6 design: its "20d buys power" claim is measured false —
          20d gives ~3x the blocks but proportionately less effect, so the power ratio
          is flat; (2) PatchTST's closure, if any, needs its own frozen prereg with a
          kill rule — Stage 0 deliberately does not pronounce one; (3) the clf coverage
          gap is a real Stage-1 input: no WF corpus exists for the certified recipe.
