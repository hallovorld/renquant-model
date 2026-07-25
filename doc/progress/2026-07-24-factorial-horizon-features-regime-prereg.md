# Relocate horizon x features x regime FACTORIAL prereg from orchestrator#574

STATUS:    in-progress
WHAT:      Relocates the horizon x features x regime factorial prereg study
           — design doc (`doc/research/2026-07-24-factorial-horizon-
           features-regime-prereg.md`), runner script
           (`scripts/research_factorial_hfr.py`), and the frozen I1/I2/I3 +
           M1/M2a/M2b/M3 interaction/Holm analyzer unit tests
           (`tests/gbdt/test_research_factorial_hfr_analyzer.py`) — from
           `hallovorld/renquant-orchestrator#574` into this repo. The
           initial move was byte-for-byte (only the test's `_SPEC_PATH`
           depth changed). **This pass (unattended fix-queue, round 8
           review) resolves the 3 remaining HIGH findings on the queued
           head** `cb63a474`:
           1. Fold-count/anchor mismatch — `N_SPLITS` now defaults to
              `ANCHOR_SPLITS` (3), matching the only anchor-validated fold
              count, instead of defaulting to an unvalidated 5. `--n-splits
              5 --skip-anchor` remains available as an explicit
              EXPLORATORY-ONLY path. Prereg §2/§4/§6/§7 revised to match
              (3-fold is now the primary design; runtime re-estimated at
              ≈52 min, linearly extrapolated from the 5-fold probe, not
              re-measured).
           2. 2x-block sensitivity — `run_interaction_tests()` now computes
              and persists `p_2x_block` (bootstrap at 2x the evaluation
              block) for the 3 PRIMARY contrasts (I1/I2/I3), reported
              alongside `p`, not gating `registered_verdict`.
           3. Per-seed data + manifest — the JSON bundle now serializes
              `clean_by_seed` (not just the seed-averaged `clean`) via new
              `serialize_cells`/`deserialize_cells` (exact inverse pair,
              pinned by a round-trip test), plus a `manifest` block
              (`data_digest`, `regime_label_digest`, `code_revision`,
              `command`) via new `build_manifest`.
           Still design-only — no results, study not run.
WHY/DIR:   `renquant-orchestrator/CLAUDE.md` sets a hard boundary: the repo
           owns pinned-subrepo orchestration and must not implement model-
           training internals. `scripts/research_factorial_hfr.py` imports
           `renquant_model_gbdt.panel_data` / `panel_trainer` and
           `xgboost`, rebuilds folds/normalization, and trains XGB cells —
           squarely model-training research. Per the umbrella multi-repo
           code-placement rule (new code goes in the repo that owns the
           subject; model research -> `renquant-model`, never the
           orchestrator), this PR is that move. This pass's 3 fixes are
           all bounded implementation-completeness findings on an
           already-frozen design (fold-count consistency, an already-
           specified sensitivity re-run, already-computed-but-unpersisted
           data) — not new research-design judgment calls.
EVIDENCE:
  artifact:      scripts/research_factorial_hfr.py,
                 tests/gbdt/test_research_factorial_hfr_analyzer.py (13
                 tests), doc/research/2026-07-24-factorial-horizon-
                 features-regime-prereg.md
  prod or exp:   experiment, design-only; no training run, no write. The
                 script refuses any output path containing
                 `artifacts/prod`, `artifacts/sim`, `strategy_config`,
                 `/data/`, `walkforward`, `panel-ltr`.
  existing data: no cell has been trained under this design in this PR;
                 this pass changes the harness (default fold count,
                 sensitivity reporting, bundle schema) and the prereg text
                 describing it, not any measured result.
  best-known?:   n/a — no IC/Sharpe claim is made by this PR.
  scope:         "3 HIGH findings from round-8 review fixed on
                 `scripts/research_factorial_hfr.py` +
                 `doc/research/2026-07-24-factorial-horizon-features-
                 regime-prereg.md`, 7 new tests added; full repo suite
                 re-verified: `python -m py_compile
                 scripts/research_factorial_hfr.py`,
                 `python scripts/research_factorial_hfr.py --help`
                 (exit 0), `pytest tests/gbdt/test_research_factorial_hfr_
                 analyzer.py` -> 13 passed, full `pytest -q
                 --ignore=tests/test_bundle_seal.py` -> 827 passed, 2
                 skipped, 0 failed"
NEXT:      Once this PR is reviewed/approved, orchestrator#574 (already
           reduced to a progress-doc-only relocation record and APPROVED)
           needs no further action. Running the study itself (an actual
           `--out` run, ≈52 min at the anchor-validated 3-fold default)
           still requires explicit operator direction, not an autonomous
           unattended fix pass (`AGENT-RETROSPECTIVE.md` §5, C3).
