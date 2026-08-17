# G-I MoE impl step 1 — three simple-sort factor emitters (design orch#984 §4–5)

STATUS:    delivered. Library code + synthetic-frame tests ONLY — nothing
           scheduled, nothing served, nothing run against production data.

WHAT:      New package `src/renquant_model_factors/` — the three
           momentum-grade simple-sort candidates from the APPROVED G-I MoE
           design (orch#984 §4), as clones of the momentum emitter PATTERN,
           not of its code:

           * `machine.py` — ONE shared assembly: (injected readers, factor
             def, frozen params) → per-ticker RAW scores → a momentum-shaped
             artifact (kind / params / config_fingerprint / MEASURED
             effective cutoff / read digests / content_sha256). Imported,
             never copied: `content_sha256_of` / `verify_artifact_content_sha`
             from `renquant_model_momentum.train`; the chained ledger from
             `renquant_model_momentum.ledger` (re-exported — NO ledger code
             in this package). The one re-stated helper is `_jsonable`
             (underscore-private upstream; no semantic divergence, noted in
             its docstring), and `factor_config_fingerprint` diverges from
             the momentum producer's recipe ONLY in the prefix
             (`factor_<name>-` vs `momentum-` — same canonical-JSON digest),
             because stamping `momentum-` on a factor artifact would be the
             version-mislabel class at the fingerprint level.
           * `high52w.py` + `_frozen_params_high52w_v0.py` — 52-week-high
             proximity (George–Hwang): score = close_t / max(close over the
             trailing 252 trading-day observations), min_obs=200, kind
             `factor_high52w_v0`.
           * `lowbeta.py` + `_frozen_params_lowbeta_v0.py` — betting-against-
             beta (Frazzini–Pedersen): score = −beta_hat, OLS slope of daily
             close-to-close returns on the INJECTED SPY series over the
             trailing 252 paired returns, min_obs=200, kind
             `factor_lowbeta_v0`.
           * `quality_gp.py` + `_frozen_params_quality_gp_v0.py` — gross
             profitability (Novy-Marx), kind `factor_quality_gp_v0`. Field
             availability was ENUMERATED FIRST (the step-1 spec's
             precondition): the exact ratio gross_profit / total_assets
             already exists on the data surface as column
             `gross_profitability`, computed upstream by
             `renquant_base_data.sec_fundamentals.compute_derived_features`
             (SEC `GrossProfit`, falling back to the accounting identity
             Revenue − CostOfRevenue only when the subtotal is untagged,
             over SEC `Assets`), and served by
             `renquant_base_data.loaders.fundamentals` (FACTOR_COLS) and the
             alpha158 fund panel (FUND_COLS). The emitter consumes THAT
             column verbatim — no proxy, no recomputation; `source_column`
             is part of the frozen recipe. Staleness ceiling 400 calendar
             days (annual cadence + filing lag), fail-closed.

           Frozen params modules are PREREG CONTENT, frozen in this build PR
           before any scoring run (orch#984 §5b candidate-manifest freeze:
           the exact formula/variant must be committed before any corpus
           score). Scores are RAW by contract — measured against the real
           consumer: `BlendPanelScorer.score` z-scores each component
           cross-sectionally at serve time (ddof=0), which is how the
           momentum ledger is consumed today.

           Tests: `tests/test_factor_emitters.py` (hand-computable synthetic
           frames: high52w spike ⇒ 0.8 exactly; lowbeta 2×/−0.5× SPY ⇒
           −2.0/+0.5 exactly; quality_gp upstream value 0.42 verbatim;
           min_obs/staleness fail-closed; missing-series vs NaN-score
           distinction; fingerprint stability; content-sha tamper; ledger
           append + chain-verify + history-rewrite refusal + one-kind-per-
           file lane discipline) and `tests/test_factor_frozen_params.py`
           (frozen literals pinned; the high52w/lowbeta clocks held EQUAL to
           momentum v0's frozen module; wheel-self-sufficiency; domain
           validators fail-closed).

WHY/DIR:   orch#984 §5 step 1: every MoE candidate walks momentum's exact
           qualification path, starting with a standalone hash-chained
           emitter. Cloning the PATTERN while importing the machinery keeps
           one chain implementation, one sha discipline, and one artifact
           shape for every ledger lane the scorer-identity monitor watches.

BUILD CFG: no pyproject change needed — packages are auto-discovered via
           `[tool.setuptools.packages.find] where = ["src"]`, which is
           exactly how `renquant_model_momentum` is declared.

EVIDENCE:
  artifact:       src/renquant_model_factors/ (7 modules),
                  tests/test_factor_emitters.py,
                  tests/test_factor_frozen_params.py
  prod or exp:    neither — library code + synthetic-frame unit tests; no
                  production path read or written, no emitter run against
                  real data, no scheduling
  existing data:  none consumed. The quality_gp field audit is read-only
                  code inspection of renquant-base-data
                  (sec_fundamentals.py, loaders/fundamentals.py,
                  alpha158_fund_panel.py) — no frame was loaded
  best-known?:    yes for the pattern (momentum's emitter is the validated
                  GOAL-7 path this clones); the frozen v0 constants adopt
                  momentum v0's clock by design and are held equal by test;
                  quality_gp consumes the repo's ONE existing Novy-Marx
                  surface rather than inventing a second
  scope:          implements design orch#984 §4–5 impl step 1 ONLY: the
                  three simple-sort emitters as library code. NO scheduling,
                  NO production runs, NO IC screening in this PR — the cheap
                  IC screen is impl step 2 with its own frozen spec, and any
                  deploy is operator-gated. `tail_q90_20d` (the fourth §4
                  candidate) is a panel-pipeline recipe, not a simple-sort
                  emitter, and is out of scope here.

VERIFICATION:
  full suite from the worktree (PYTHONPATH pointed at the sibling
  `renquant-*/src` checkouts, since the worktree is not a sibling):
    pre-existing: 1568 passed, 9 skipped (same skips as before this change
                  — none of the new tests skip)
    new:          33 passed
    total:        1601 passed, 9 skipped, 0 failed

NEXT:      (1) impl step 2 — the cheap IC screen, ONLY AFTER the §5b batch
               manifest freeze (the screen views corpus scores).
           (2) weekly emitter scheduling — operator-gated, its own PR.

---

## Review fix (2026-08-17, Codex MED on lowbeta pairing)

FINDING:   `lowbeta.py` computed `pct_change` on the ticker and SPY series
           SEPARATELY, then joined the returns — an interior ticker-date
           gap paired a multi-session ticker return with the one-session
           SPY return at the endpoint, silently changing the beta
           estimator and violating the frozen paired-daily-return
           contract.

FIX:       Inner-join the two PRICE series first, compute returns on the
           aligned frame, and keep a pair only when its two dates are
           ADJACENT in the market calendar (the market series' index) —
           the gap-spanning pair is dropped, exactly the frozen v0 "a gap
           yields a dropped pair, never forward-filled" contract (so no
           new params version: this corrects the implementation to the
           preregistered construction, not the construction itself). A
           NaN close now behaves identically to a missing row.

EVIDENCE:
  discriminates: old-style pairing on the new gap fixture gives
                 beta 1.994646 vs the exact 2.0 the construction implies
                 (|Δ| = 5.35e-03, tolerance 1e-9)
                 [VERIFIED — one-off recomputation of the old join on the
                 test fixture, this session]
  new tests:     `test_lowbeta_interior_date_gap_never_mispairs` (AUDIT
                 REGRESSION GUARD) + `test_lowbeta_nan_close_drops_the_
                 pair_not_the_contract`
  focused suite: tests/test_factor_emitters.py +
                 tests/test_factor_frozen_params.py — 35 passed, 0 failed
                 [VERIFIED — pytest -q, this session]
