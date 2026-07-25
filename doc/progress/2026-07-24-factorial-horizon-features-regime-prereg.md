# Relocate horizon x features x regime FACTORIAL prereg from orchestrator#574

STATUS:    in-progress
WHAT:      Relocates the horizon x features x regime factorial prereg study
           — design doc (`doc/research/2026-07-24-factorial-horizon-
           features-regime-prereg.md`), runner script
           (`scripts/research_factorial_hfr.py`), and the frozen I1/I2/I3 +
           M1/M2a/M2b/M3 interaction/Holm analyzer unit tests
           (`tests/gbdt/test_research_factorial_hfr_analyzer.py`) — from
           `hallovorld/renquant-orchestrator#574` into this repo. The move
           is byte-for-byte: the only change is the test file's
           `_SPEC_PATH` relative-path depth (`parents[1]` -> `parents[2]`)
           to account for living under `tests/gbdt/` here instead of
           `tests/` in the orchestrator repo. No design, estimator, or
           decision-rule change. Still design-only — no results, study not
           run.
WHY/DIR:   `renquant-orchestrator/CLAUDE.md` sets a hard boundary: the repo
           owns pinned-subrepo orchestration and must not implement model-
           training internals. `scripts/research_factorial_hfr.py` imports
           `renquant_model_gbdt.panel_data` / `panel_trainer` and
           `xgboost`, rebuilds folds/normalization, and trains XGB cells —
           squarely model-training research. Six consecutive Codex review
           rounds on orchestrator#574 raised the same HIGH finding after
           every other blocker (progress-doc shape, commit attribution,
           anchor-gate ordering, the unfrozen interaction/Holm analyzer)
           was independently fixed. Per the umbrella multi-repo code-
           placement rule (new code goes in the repo that owns the
           subject; model research -> `renquant-model`, never the
           orchestrator), this PR completes that move so orchestrator#574
           can shrink to coordination only.
EVIDENCE:
  artifact:      scripts/research_factorial_hfr.py,
                 tests/gbdt/test_research_factorial_hfr_analyzer.py (6
                 tests), doc/research/2026-07-24-factorial-horizon-
                 features-regime-prereg.md
  prod or exp:   experiment, design-only; no training run, no write. The
                 script refuses any output path containing
                 `artifacts/prod`, `artifacts/sim`, `strategy_config`,
                 `/data/`, `walkforward`, `panel-ltr`.
  existing data: byte-identical relocation from orchestrator#574 (only the
                 test's relative-path-depth constant changed for the new
                 `tests/gbdt/` location); the design, the frozen decision
                 rule (prereg SS5), and the analyzer code are unmodified.
  best-known?:   n/a — no cell has been trained under this design; no
                 IC/Sharpe claim is made by this PR.
  scope:         "pure relocation + one path-depth fix, no design or
                 analysis-code change; correctness re-verified in this
                 repo's env: `python -m py_compile
                 scripts/research_factorial_hfr.py`,
                 `python scripts/research_factorial_hfr.py --help`
                 (exit 0), and
                 `pytest tests/gbdt/test_research_factorial_hfr_analyzer.py`
                 -> 6 passed"
NEXT:      `renquant-orchestrator#574` is being reduced in the same pass
           to drop the relocated files and to point its own progress doc
           at this PR. Once this PR is reviewed/approved, orchestrator may
           coordinate the sealed, versioned run bundle this study
           eventually produces, but must not re-implement the study.
           Running the study itself (an actual `--out` run, ~87 min at
           the exploratory 5-fold default, or the anchor-validated 3-fold
           default) still requires explicit operator direction, not an
           autonomous unattended fix pass (`AGENT-RETROSPECTIVE.md` SS5,
           C3) — that item carries over unchanged from orchestrator#574.
