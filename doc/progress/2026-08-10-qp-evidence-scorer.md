# qp evidence scorer — nested per-fold gate-fit/validation/test replay (PR A)

STATUS:    executed ONCE; scores + stamps + manifest committed on this
           branch. Model-side half of the MERGED qp re-enable evidence
           freeze (renquant-orchestrator doc/design/
           2026-08-10-qp-reenable-evidence-prereg.md, orch#955; doc
           sha256 d2392aa19fc7…, pinned in the manifest). The
           orchestrator's PR B stays join-only (orch#953-P0 boundary):
           labels, joining, the daily statistic, bootstrap, and the
           verdict all live THERE — none of them exists in this repo.

WHAT:      scripts/qp_evidence_scorer.py — per v2-CUTS fold (CUTS
           ast-read from doc/design/frozen/2026-08-09-xgbmom-v2-
           harness.py; corpus sha asserted == the harness pin ==
           870f68ebad5d…):

           (i) boundaries train_end = last corpus session <= CUTS[f][1];
           validation_start = train_end − 251 sessions (252-session
           validation segment); gate_fit_end = the session before
           validation_start — all recorded per fold.
           (ii) GATE-FIT models: panel leg via
           renquant_model_gbdt.panel_trainer.train_xgb
           (PANEL_LTR_PARAMS verbatim incl. seed 42, 100 rounds, the
           prod artifact's 172-column feature contract — feature_cols
           read from backtesting/renquant_104/artifacts/prod/
           panel-ltr.alpha158_fund.json, its booster NEVER loaded) on
           rows date <= gate_fit_end AND 60-session label endpoint <
           validation_start (endpoint map on the corpus's own
           calendar); momentum leg = the frozen v0 recipe
           (momentum-v0-fd65161a20b29314) trained at the latest weekly
           cutoff (last trading day <= a Saturday, corpus calendar) <=
           validation_start, with the module's golden checks (content
           sha recomputes, frozen params fingerprint, composite golden
           reproduction <1e-9, names floor) — failure drops the leg
           for the fold and records a degradation flag.
           (iii) VALIDATION (strictly OOS): blend z+z (ddof=0, NaN
           propagates — blend_scorer semantics), top-5 per entry day
           held 5 sessions, entries capped so every exit lands on/
           before train_end; pnl_pct = raw 5d close return − SPY
           (data/ohlcv/<T>/1d.parquet); entry_regime from
           build_regime_series (the WF gate's own constructor,
           imported from scripts/analyze_manifest_sanity_placebo.py
           and called the run_wf_gate.py:2701 way); stamps via
           scripts/trade_monotonicity.py evaluate_trade_monotonicity
           VERBATIM defaults (min_n 30, min_spearman 0.02, positive
           spread), frozen per fold per regime.
           (iv) FULL-TRAIN models (panel <= train_end with per-row
           purge vs test start; momentum cutoff <= train_end) score
           the TEST fold days only; emitted as
           fold,date,ticker,recipe_score,regime.

           Committed real-run artifacts (doc/design/frozen/):
           2026-08-10-qp-evidence-scores.csv,
           2026-08-10-qp-evidence-stamps.json,
           2026-08-10-qp-evidence-manifest.json (every input sha,
           per-fold boundaries, OOS validation day counts, degradation
           flags, params fingerprints, the orch#956 expected_schedule
           {fold -> corpus test dates}, and both output shas).

WHY/DIR:   orch#955 §7 binds the runner; the model-training half
           belongs in renquant-model (the orch#953 P0 boundary, the
           model#220 relocation precedent). Publishing hash-pinned
           prediction/stamp artifacts makes the orchestrator handoff
           auditable by sha256 instead of by trust.

BOUNDARIES (recorded per fold; validation = 252 sessions, 247 entry
           days each — the last 5 entry days are dropped so exits stay
           <= train_end):

           fold gate_fit_end validation_start train_end  test (days)
           1    2017-12-28   2017-12-29       2018-12-31 2019-04-01..2019-12-31 (191)
           2    2018-12-31   2019-01-02       2019-12-31 2020-04-01..2020-12-31 (191)
           3    2020-01-02   2020-01-03       2020-12-31 2021-04-01..2021-12-31 (191)
           4    2020-12-31   2021-01-04       2021-12-31 2022-04-01..2022-12-31 (189)
           5    2021-12-30   2021-12-31       2022-12-30 2023-04-01..2023-12-31 (188)
           6    2022-12-28   2022-12-29       2023-12-29 2024-04-01..2024-12-31 (191)
           7    2023-12-29   2024-01-02       2024-12-31 2025-04-01..2025-12-31 (190)
           8    2024-12-27   2024-12-30       2025-12-31 2026-04-01..2026-05-07 (26)

           Test-day counts reproduce the freeze §5 table exactly
           (191/191/191/189/188/191/190/26 = 1357) and are asserted in
           code. Momentum: NO degradation on any fold (all 16 cutoff
           artifacts cleared every golden check; n_scored 264-292 vs
           floor 50). Regime coverage: 0 UNKNOWN days anywhere.

EVIDENCE:  artifact:      doc/design/frozen/2026-08-10-qp-evidence-
                          scores.csv — 387,968 rows [VERIFIED — wc -l
                          387,969 incl. header], sha256 b9676666c4c7…
                          [VERIFIED — shasum recomputed independently
                          of the manifest, 2026-08-09; equals the
                          manifest's outputs.scores_csv.sha256].
                          Stamps 2026-08-10-qp-evidence-stamps.json
                          sha256 0533ad12383c… [VERIFIED — same
                          method]. Inputs pinned in the manifest:
                          corpus 870f68ebad5d… [VERIFIED — runtime
                          assert vs the harness pin], harness
                          7ca9e48f3be9…, prod artifact 6461b827ab23…,
                          trade_monotonicity f9752d7ab238…, regime
                          constructor bde58d14218a…, 293 OHLCV read
                          digests; panel_trainer git revision
                          5bd9c16bfd4e [VERIFIED — recorded at run
                          time]. 1235 validation trades per fold, all
                          with finite pnl [VERIFIED — manifest per-fold
                          counters].
           prod or exp:   experiment. All inputs read-only (frozen
                          corpus, prod artifact JSON, OHLCV, strategy
                          config); no production path written; run
                          executed in an isolated worktree; outputs
                          land only under this repo's
                          doc/design/frozen/.
           existing data: the frozen v2 harness (CUTS + endpoint-map
                          purge convention, model#213), the production
                          panel trainer module (PANEL_LTR_PARAMS), the
                          packaged frozen momentum v0 recipe
                          (model#164/#177), the WF gate's own regime
                          constructor and trade-monotonicity module —
                          nothing re-derived, nothing re-leveled; the
                          only new machinery is the nested split
                          orchestration the freeze itself specifies.
           best-known?:   yes — every constant is the freeze's or a
                          production module's own (params fingerprint
                          momentum-v0-fd65161a… matches the packaged
                          params_v0() [VERIFIED — asserted in code +
                          test]); the one resolved ambiguity (an arm
                          serves ONE momentum artifact, its latest
                          admissible weekly cutoff) is recorded in the
                          manifest with its equivalence argument:
                          every scored day >= the arm's bound, so the
                          latest admissible cutoff IS the live-cadence
                          ledger tail for all of them.
           scope:         one new script, one new test file, three
                          committed run artifacts, this progress doc.
                          No src/ package changes, no orchestrator
                          changes (PR B consumes these artifacts by
                          sha), no live surface touched, no gate or
                          config moved. NO labels/joining/statistic/
                          verdict here — fwd_5d_excess is never read.

TESTS:     tests/test_qp_evidence_scorer.py — 7 passed in 2.85s
           [VERIFIED — pytest, 2026-08-09]: (a) planted monotone
           world -> per-regime passed=True stamps and anti-monotone ->
           passed=False, through the VERBATIM production evaluator;
           (b) two full nested runs byte-identical (scores CSV +
           stamps); (c) validation-day leak into test scores fails
           loudly, plus the orch#956 contract guards (schedule
           coverage, one regime per (fold, date), (fold, date, ticker)
           sort); (d) manifest sha integrity incl. corruption
           detection; (e) momentum golden checks on a REAL
           train_momentum_artifact over synthetic readers + tamper
           detection; (f) dropped-leg degradation flag with z(panel)-
           alone fallback; (g) the frozen fingerprint literal. Full
           suite: 1572 passed, 1 skipped in 66.81s [VERIFIED — make
           test in the worktree with sibling-repo PYTHONPATH and
           ../RenQuant/.venv python, 2026-08-09].

RUN:       ~39 min wall under caffeinate (dominated by the 2032-date
           production regime series; the 16 XGB trainings + scoring
           took ~95s) [VERIFIED — run log timestamps]. Frozen stamps
           summary (per-regime eligible/passed, gate authority
           unchanged): folds 6 and 7 pass in all active regimes;
           folds 1-5 and 8 each fail in at least one active regime
           (details in the stamps JSON). No interpretation here — PR B
           applies the stamps unchanged and computes the §5 statistic.

NEXT:      merge this PR -> orchestrator PR B (join-only runner)
           consumes the three artifacts by sha256, applies the frozen
           stamps to the test-day selections, and publishes the §6
           verdict (PASS | FAIL | POWER_INSUFFICIENT) with the frozen
           §5 inference parameters.
