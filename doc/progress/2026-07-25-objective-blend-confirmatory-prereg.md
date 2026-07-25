# 2026-07-25 — Confirmatory prereg: tail-aware blend objective vs production rank:pairwise

STATUS:    prereg frozen; confirmatory run RESTARTED after a review catch (below)
WHAT:      `doc/research/2026-07-25-objective-blend-confirmatory-prereg.md` (frozen
           decision rule) + `scripts/research_objective_blend_confirm.py` (executor)
           + committed screen evidence `doc/research/evidence/2026-07-25-objective-blend/`.
WHY/DIR:   Alpha-engine objective/harvest mismatch: the book harvests top-10 and the
           alpha is tail-carried, but production rank:pairwise spends its loss budget
           ordering the ~90% of the cross-section never traded. Single pre-named
           confirmatory arm earned by the 07-24 six-arm screen.
EVIDENCE (screen, §4(b)):
  artifact:      doc/research/evidence/2026-07-25-objective-blend/screen-six-arm-result.json
                 (committed byte copy of the session artifact `objective_ab_result.json`)
  prod or exp:   EXPERIMENT — research harness on `alpha158_291_fundamental_dataset.parquet`
                 via renquant_model_gbdt public API; read-only; no prod artifact touched
  existing data: production recipe reproduced as the baseline arm in the same harness
                 (rank:pairwise, PANEL_LTR_PARAMS, 5 purged folds, 60d embargo,
                 per-arm matched within-date shuffled-label placebos, seeds 42/43/44)
  best-known?:   yes — first objective-function comparison on this book; no prior art
                 (E51/prune lines were feature-set changes, not objective changes)
  scope:         "on the 292-name survivorship panel, clean top-10 spread of the three
                 cross-sectional tail-aware objectives exceeded the production objective
                 by +21-28% (each ns alone at 90%); the absolute-threshold arm was
                 negative; all six arms reported, none cherry-picked" — screen-grade
                 only; levels inflated by survivorship; NOT evidence of a deployable gain
NEXT:      run the fixed executor (10 seeds); results in a SEPARATE PR; CONFIRMED →
           shadow design PR; REFUTED → NULL; INCONCLUSIVE → shadow-forward per the
           frozen rule.

## Review catch acknowledged (this is why the run restarted)

Codex round-1 HIGH was correct and material: the prereg froze guard (b) as
"winsorized-±50% diff ≥ 0" but the first executor substituted a trimmed-mean
surrogate. A verdict from the surrogate would not have been the frozen verdict.
The in-flight run was killed BEFORE any contrast was read (only baseline-arm
per-seed levels had printed); the executor now computes the winsorized ±50%
clean-spread series per seed and applies the frozen guard verbatim. No
decision-rule text changed.

## Relocation note

Same boundary ruling as model#67: the executor trains XGB via
renquant_model_gbdt, so the study lives here, not in the orchestrator. The
verdict, when it exists, still registers in the orchestrator's
`doc/research/VERDICTS.md` ledger with a cross-repo link.
