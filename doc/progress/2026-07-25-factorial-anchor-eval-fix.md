# 2026-07-25 — factorial executor: anchor checked at the wrong eval horizon (spurious VOID)

STATUS:    executor fix; prereg §§0-6 text UNCHANGED
WHAT:      `scripts/research_factorial_hfr.py` — (1) the anchor statistic is now the
           anchor cell's raw IC at its OWN fwd_60d eval (`raw_at_60d_eval`), matching
           what the prereg's 0.0488 was validated against (production 3-fold CV = IC
           vs the fwd_60d label); (2) the anchor cell now trains FIRST and the gate
           fires immediately, restoring fail-closed.
WHY/DIR:   First execution of the merged prereg VOIDed spuriously: the executor
           compared the anchor cell's raw IC at the 20d PRIMARY eval (+0.0304)
           against the 60d-validated expectation (0.0488 ± 0.010). A 60d-trained
           model's IC at a 20d eval is a DIFFERENT statistic; the check could never
           pass. Bug originated in the pre-relocation draft and survived 9 review
           rounds — recorded here as the mirror case of the model#68 round-1 catch
           (executor infidelity cuts both ways).
EVIDENCE:
  artifact:      voided-run console (session task bacq0wwmd): anchor line printed
                 "+0.0304 vs +0.0488 -> FAIL" where +0.0304 equals the anchor cell's
                 raw@20d — the wiring, not the market, failed the check
  prod or exp:   EXPERIMENT, read-only
  existing data: 0.0488 anchor provenance: production evaluate_walk_forward_cv at
                 3 folds vs fwd_60d (orchestrator #575 memo evidence); this-harness
                 5-fold 60d-eval raw ≈ +0.0472/+0.0481 (horizon_matched evidence) —
                 both consistent with the 60d-eval statistic, not the 20d one
  best-known?:   yes — minimal fix; alternative (re-baselining the anchor at 20d
                 eval) REJECTED because it would amend frozen §5 semantics post-run
  scope:         "the VOID verdict of run 1 is itself void; run 1's 24 cell summaries
                 printed before the gate and are QUARANTINED (not citable); the study
                 rerun is the first readable execution"
NEXT:      rerun; results in a separate PR; cell-table exposure disclosed there too.
