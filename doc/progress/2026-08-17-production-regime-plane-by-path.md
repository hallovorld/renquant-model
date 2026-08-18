# Production regime-label plane, consumed BY PATH (orch#985 item 1)

STATUS:    delivered. Research metrology ONLY — no serving path, no trading
           decision, no training-artifact publication changes. The WF gate's
           SANITY leg already used the production plane, so gate verdicts on
           the sanity leg are unchanged BY CONSTRUCTION; this PR moves the
           MODEL-repo research harnesses off the divergent stateless plane.

WHAT:      * `renquant_model_common/regime_plane.py` (new) — the by-path
             loader for the committed production-plane corpus that
             renquant-backtesting publishes
             (`doc/research/data/production_regime_labels.csv` +
             provenance manifest, cross-referenced PR). Env contract
             mirrored from `renquant_backtesting.analysis.regime_plane`
             (duplicating the two constants is deliberate: importing them is
             exactly what the boundary forbids):
             `RENQUANT_REGIME_PLANE=production|legacy_stateless` (default
             production, typos rejected) and `RENQUANT_REGIME_LABELS_PATH`
             (corpus override; default = sibling-checkout path, same layout
             the Makefile uses). NO new imports of renquant_pipeline /
             renquant_backtesting anywhere — the boundary AST tests pass
             untouched.
           * Site (ii) `renquant_model_patchtst/research_pipeline.py`:
             `RegimeDetectorContractTask` validates the golden windows on
             the production corpus by default (stamps plane + corpus
             path/sha + the publisher-manifest chain identity instead of
             stateless thresholds that do not describe this plane);
             `_load_regime_labels` (per-regime IC merge) reads the SAME
             corpus; `ResolvePathsTask`'s spy_path existence guard applies
             only on the legacy plane (SPY is not a production-plane
             contract input). Fail-CLOSED: corpus missing → contract fails
             with the remediation options, verdict `invalid_experiment`,
             labels None — never a silent fallback to the stateless plane.
           * Site (iii) `renquant_model_linear/trainer.py`: the regime map
             for per-regime IC comes from `_resolve_regime_map()` —
             production corpus by default (missing → loud warning + empty
             map), stateless `compute_hmm_regime_labels` only under the
             escape hatch.
           * NOT repointed (named residual, deliberate):
             `renquant_model_patchtst/sequence_training.py::
             ComputeRegimeLabelsTask` still computes stateless labels — they
             feed FiLM regime CONDITIONING, i.e. a TRAINING INPUT; flipping
             a training input's label source silently would change every
             future FiLM model, which deserves its own reviewed decision,
             not a rider on a metrology PR.

WHY/DIR:   orch#985 P2/P8: four label planes at 25-70% same-day agreement;
           every regime-keyed research conclusion (golden-window contracts,
           per-regime IC) was keyed to a plane serving never used. The
           import graph forbids computing the production chain here
           (tests/patchtst/test_import_boundaries.py FORBIDDEN_ROOT_IMPORTS;
           tests/test_model_common_import.py; "renquant-model never imports
           renquant_pipeline" — codex round-2 on model#65, frozen into
           tests/test_build_phase_a_inputs.py), so labels arrive as DATA —
           the same producer/consumer pattern as the frozen fold-provenance
           vectors.

EVIDENCE:  artifact:      renquant-backtesting corpus manifest
                          `memo_985_crosscheck.exact_match = true` (2,459
                          trading days / 413 BEAR / 57 episodes over the
                          #985 replica span) `[VERIFIED — publish-time
                          cross-check in the cross-referenced PR]`; golden
                          windows on the production corpus: covid_crash
                          BEAR 48/50, q2_2022_bear BEAR 53/62 majority,
                          calm_2017 BULL_CALM 228/251 majority — all three
                          PASS `[VERIFIED — measured on the committed
                          corpus]`
           prod or exp:   neither — research metrology; no trading behavior
                          change; sanity-leg gate verdicts unchanged BY
                          CONSTRUCTION (that leg always replayed the
                          production chain)
           existing data: corpus 2016-02-16..2026-08-17, 2,641 rows,
                          occupancy BULL_CALM 1929 / BEAR 419 /
                          BULL_VOLATILE 185 / CHOPPY 108 `[VERIFIED —
                          corpus manifest]`
           best-known?:   yes — first time the model-repo harnesses see the
                          plane that actually serves
           scope:         renquant-model only; corpus production lives in
                          renquant-backtesting (cross-referenced PR); the
                          chain-drift finding is an issue on
                          hallovorld/renquant-pipeline, not fixed here

TESTS:     baseline origin/main: 1603 passed / 9 skipped. After: 1616
           passed / 9 skipped — +13 new (plane resolution incl. typo
           rejection; sibling default + env override + actionable
           FileNotFoundError; corpus identity stamping; contract task
           production default PASS on fixture corpus, missing-corpus
           fail-closed incl. `_load_regime_labels` staying None, legacy
           escape hatch with threshold stamping preserved; linear trainer
           production default / missing-corpus-empty / legacy hatch), and
           3 existing stateless-plane tests pinned to the
           `legacy_stateless` hatch they now test (documented in each).
           Boundary AST tests untouched and green. All fixture-corpus
           based — no sibling checkout, no production data in tests.

ESCAPE HATCH: every repointed site honors
           `RENQUANT_REGIME_PLANE=legacy_stateless` for reproduction of
           historical results; documented at each site.
