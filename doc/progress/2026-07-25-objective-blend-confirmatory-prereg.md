# 2026-07-25 — Confirmatory prereg: tail-aware blend objective vs production rank:pairwise

STATUS:    prereg frozen; confirmatory run RESTARTED after a review catch (below)
WHAT:      `doc/research/2026-07-25-objective-blend-confirmatory-prereg.md` (frozen
           decision rule) + `scripts/research_objective_blend_confirm.py` (executor)
           + committed screen evidence `doc/research/evidence/2026-07-25-objective-blend/`.
WHY/DIR:   Alpha-engine objective/harvest mismatch: the book harvests top-10 and the
           alpha is tail-carried, but production rank:pairwise spends its loss budget
           ordering the ~90% of the cross-section never traded. Single pre-named
           confirmatory arm earned by the 07-24 six-arm screen.
EVIDENCE:
  artifact:      doc/research/evidence/2026-07-25-objective-blend/screen-six-arm-result.json
                 (committed byte copy of the session artifact `objective_ab_result.json`) —
                 this file contains 4 of the screen session's arms; see narrowing below
  prod or exp:   EXPERIMENT — research harness on `alpha158_291_fundamental_dataset.parquet`
                 via renquant_model_gbdt public API; read-only; no prod artifact touched
  existing data: production recipe reproduced as the baseline arm in the same harness
                 (rank:pairwise, PANEL_LTR_PARAMS, 5 purged folds, 60d embargo,
                 per-arm matched within-date shuffled-label placebos, seeds 42/43/44)
  best-known?:   yes — first objective-function comparison on this book; no prior art
                 (E51/prune lines were feature-set changes, not objective changes)
  scope:         "on the 292-name survivorship panel, clean top-10 spread of the 3
                 committed cross-sectional tail-aware arms (top_decile_clf, big_run_clf,
                 rank_on_20d) exceeded the production rank_pairwise baseline by +21-28%
                 (each ns alone at 90%), per the 4-arm committed artifact" — screen-grade
                 only; levels inflated by survivorship; NOT evidence of a deployable gain.
                 NARROWED (model#68 review round 4, MED): the session is reported to have
                 run additional arms, including an absolute-threshold arm said to have
                 failed, but no artifact for those arms is committed to any repo — the
                 prior "all six arms reported, none cherry-picked" line is unverifiable
                 and has been removed. Only the 4 arms above back this evidence block.
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

## Replayable bundle + freeze-evidence fix (model#68 review round 3)

BLOCKER 1 and HIGH 2 were correct: the executor's `--out` JSON serialized
only aggregate means/CI/verdict, and "frozen BEFORE the run" had no
immutable evidence tying a run to this prereg commit. `scripts/research_objective_blend_confirm.py`
now persists the full per-date clean-spread series for both arms (raw and
winsorized ±50%), the per-seed per-date series, the paired `diff` series
the bootstrap CI is computed from, and a `manifest` (panel-file sha256,
prereg-file sha256, code revision, exact command, `run_started_at`/
`run_finished_at`). `serialize_result`/`deserialize_result`/
`verdict_from_bundle` are the exact replay path a reviewer runs against a
persisted bundle; pinned by a synthetic-data round-trip test in
`tests/gbdt/test_research_objective_blend_confirm.py` (15 tests, no panel/
xgboost/production dependency — exercises `decide_verdict`'s three branches,
`block_bootstrap_ci` determinism, and the serialize/deserialize round trip).
This fixes the executor going forward; the already-completed confirmatory
run behind model#70 predates this fix and its aggregate-only bundle is not
itself replayable — that gap is called out in model#70's own progress doc,
not silently carried forward.

## Relocation note

Same boundary ruling as model#67: the executor trains XGB via
renquant_model_gbdt, so the study lives here, not in the orchestrator. The
verdict, when it exists, still registers in the orchestrator's
`doc/research/VERDICTS.md` ledger with a cross-repo link.
