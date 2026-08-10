# qp evidence scorer — nested per-fold gate-fit/validation/test replay (PR A)

STATUS:    executed; scores + stamps + manifest committed on this
           branch. The artifacts are the r2 RERUN under the per-date
           weekly momentum cadence — the initial run is VOIDED as a
           preregistration deviation (see CORRECTIONS). Model-side half of the MERGED qp re-enable evidence
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
           (momentum-v0-fd65161a20b29314) REPLAYED AT HISTORICAL WEEKLY
           CUTOFFS (last trading day <= each Saturday, corpus
           calendar): every validation entry day is served by its OWN
           latest weekly cutoff <= that day — the live publish cadence
           per date, never one segment-fixed artifact (review m221-r2).
           The module's golden checks (content sha recomputes, frozen
           params fingerprint, composite golden reproduction <1e-9,
           names floor) run at EVERY cutoff — a failing cutoff drops
           the leg for exactly the dates it serves (z(panel)-alone
           fallback, freeze §4) and is recorded per cutoff.
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
           purge vs test start; momentum served per TEST day at its own
           latest weekly cutoff <= that day, same per-cutoff golden
           checks) score the TEST fold days only; emitted as
           fold,date,ticker,recipe_score,regime. Each fold's
           date->cutoff schedules and per-cutoff golden-check records
           are in the manifest (folds[].validation.momentum /
           folds[].test.momentum).

           Committed real-run artifacts (doc/design/frozen/), schemas
           AS COMMITTED — the exact shapes the orchestrator's join-only
           consumer reads directly (orch#956, adapted to these
           committed artifacts at f24caf5b; no earlier draft contract
           survives):

           * 2026-08-10-qp-evidence-scores.csv — columns
             fold,date,ticker,recipe_score,regime; rows sorted by
             (fold, date, ticker); exactly one regime value per
             (fold, date); recipe_score empty where a healthy leg
             could not score the name (NaN propagation).
           * 2026-08-10-qp-evidence-stamps.json — TOP-LEVEL
             "fold_<n>" objects (n = 1..8), each carrying
             boundaries {train_start, train_end, validation_start,
             gate_fit_end, test_start, test_end}, passed, reason, and
             regimes {REGIME: {eligible, passed, n, spearman,
             top_bottom_return_spread}}.
           * 2026-08-10-qp-evidence-manifest.json —
             outputs.scores_csv.{path, sha256, n_rows} and
             outputs.stamps_json.{path, sha256}; inputs.* with every
             input sha (incl. inputs.frozen_corpus.sha256 and the 293
             OHLCV read digests); TOP-LEVEL expected_schedule keyed
             "1".."8" -> the fold's corpus test dates; per-fold
             boundaries / OOS validation day counts / momentum
             degradation flags under folds[]; params fingerprints
             under panel_trainer and momentum.

CORRECTIONS (r2, 2026-08-10 — recorded, not silently overwritten):
           the INITIAL run of this scorer served ONE momentum artifact
           per arm (gate-fit: latest weekly cutoff <= validation_start;
           full-train: <= train_end) under an equivalence argument
           ("every scored day >= the bound"). Review m221-r2 correctly
           identified this as a PREREGISTRATION DEVIATION from freeze
           §4's historical weekly cutoffs: a segment-fixed map is not
           the ledger tail for later days — later weekly cutoffs see
           newer market data and can change rankings. That run
           (scores sha b9676666c4c7…, stamps sha 0533ad12383c…
           [VERIFIED — prior work, this doc's r1 EVIDENCE block]) is
           VOIDED as confirmatory evidence; its stamps admitted folds
           6 AND 7, which the corrected cadence does NOT reproduce
           (fold 7 fails under per-date serving — the deviation was
           material, not cosmetic). The committed artifacts are now
           the r2 rerun's, produced by the corrected per-date rule
           with identical frozen inputs (all five input shas
           re-verified unchanged before the rerun).

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
           code. Momentum: 425 unique weekly-cutoff artifacts computed
           (per-date serving, memoised across folds; per-fold sums 414
           validation + 288 test) — NO degradation at any cutoff
           [VERIFIED — manifest n_unique_cutoffs_computed +
           momentum_degraded_folds []]. Regime coverage: 0 UNKNOWN
           days anywhere.

EVIDENCE:  artifact:      doc/design/frozen/2026-08-10-qp-evidence-
                          scores.csv — 387,968 rows [VERIFIED — run
                          summary + manifest n_rows, r2 rerun
                          2026-08-09], sha256 b7c8158eb621… [VERIFIED —
                          recomputed by the committed-artifact contract
                          test, which reads the manifest pin and
                          re-hashes the file]. Stamps
                          2026-08-10-qp-evidence-stamps.json sha256
                          f57da264eef5… [VERIFIED — same method].
                          Inputs pinned in the manifest:
                          corpus 870f68ebad5d… [VERIFIED — runtime
                          assert vs the harness pin], harness
                          7ca9e48f3be9…, prod artifact 6461b827ab23…,
                          trade_monotonicity f9752d7ab238…, regime
                          constructor bde58d14218a…, 293 OHLCV read
                          digests; panel_trainer git revision
                          0b0d6102e820 [VERIFIED — recorded at run
                          time, r2 rerun]. 1235 validation trades per
                          fold, all with finite pnl [VERIFIED —
                          manifest per-fold counters, r2].
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
                          test]). The r1 "one artifact per arm"
                          equivalence argument is RETRACTED (see
                          CORRECTIONS): the momentum leg is now served
                          per date at the live weekly cadence, the
                          rule the freeze §4 text states.
           scope:         one new script, one new test file, three
                          committed run artifacts, this progress doc.
                          No src/ package changes, no orchestrator
                          changes from this PR (orch#956 consumes the
                          committed schemas directly), no live surface
                          touched, no gate or config moved. NO labels/joining/statistic/
                          verdict here — fwd_5d_excess is never read.

TESTS:     tests/test_qp_evidence_scorer.py — 11 passed in 3.50s
           [VERIFIED — pytest, 2026-08-09 r2]: (a) planted monotone
           world -> per-regime passed=True stamps and anti-monotone ->
           passed=False, through the VERBATIM production evaluator;
           (b) two full nested runs byte-identical (scores CSV +
           stamps); (c) validation-day leak into test scores fails
           loudly, plus the orch#956 contract guards (schedule
           coverage, one regime per (fold, date), (fold, date, ticker)
           sort); (d) manifest sha integrity incl. corruption
           detection; (e) momentum golden checks on a REAL
           train_momentum_artifact over synthetic readers + tamper
           detection; (f) per-cutoff dropped-leg degradation with
           z(panel)-alone fallback, recorded per affected date; (g)
           the frozen fingerprint literal; (h) per-date weekly-cadence
           serving — each scored day maps to its OWN latest weekly
           cutoff <= that day, run_fold requests exactly the scheduled
           cutoffs (memoised), and a later date is provably scored by
           the later cutoff's changed map (review m221-r2); (i) the
           COMMITTED artifacts match the orch#956 consumer contract —
           nested manifest sha pins re-hashed over the committed
           files, top-level fold_<n> stamps, frozen CSV header
           (review m221-r1's cross-PR regression pin). Full suite:
           1576 passed, 1 skipped in 70.54s [VERIFIED — pytest tests/
           in the worktree with ../RenQuant/.venv python, 2026-08-09
           r2].

RUN:       r2 rerun ~4 min wall under caffeinate (the r1 run's 2032-
           date regime series and OHLCV reads were already cached;
           425 weekly momentum artifacts + 16 XGB trainings)
           [VERIFIED — run log timestamps 23:31:40..23:35:31 PDT
           2026-08-09]. Frozen stamps summary (per-regime eligible/
           passed, gate authority unchanged): ONLY fold 6 passes in
           all active regimes; folds 1-5, 7 and 8 each fail in at
           least one active regime (details in the stamps JSON) —
           fold 7's r1 pass does NOT survive the corrected per-date
           cadence. No interpretation here — PR B applies the stamps
           unchanged and computes the §5 statistic.

NEXT:      merge this PR -> orch#956 (the join-only runner, ALREADY
           adapted to the committed schemas above at f24caf5b)
           consumes the three artifacts by sha256, applies the frozen
           stamps to the test-day selections, and publishes the §6
           verdict (PASS | FAIL | POWER_INSUFFICIENT) with the frozen
           §5 inference parameters.
