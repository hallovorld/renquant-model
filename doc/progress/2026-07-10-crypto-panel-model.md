# Crypto XGB panel model slice (crypto RFC D-C3 model-side / D-C8b / D-C9 core)

Date: 2026-07-10
PR: feat(crypto): XGB panel training pipeline + fee-aware net-of-cost WF gate

## What

Model-factory slice of the merged crypto trading RFC (renquant-orchestrator
`doc/design/2026-07-10-crypto-trading-rfc.md` §4, gap M1): a new
`renquant_model_crypto` package — additive, family-gated, zero changes to
any equity family file.

1. **Crypto panel training pipeline** (`panel_data.py`, `training.py`):
   - Consumes the D-C2 crypto bar store
     (`{data_dir}/crypto_ohlcv/{SLUG}/1d.parquet`, UTC daily bars).
   - alpha158 price/volume feature transform SOFT-CONSUMED from base-data
     (canonical: `crypto_bars.build_crypto_features_for_pair`, base-data#41;
     fallback: the identical `alpha158_qlib_panel.build_features_for_ticker`
     call on base-data main — verified asset-agnostic). Which path served is
     stamped in provenance.
   - **FROZEN primary label (§4.3)**: `fwd_20d_raw` — raw forward return
     over exactly 20 CALENDAR days on the UTC-day axis, exact-match target
     bar (missing bar ⇒ NaN, never a nearest-bar substitute). BTC-excess is
     NOT implemented as a label (pre-registered diagnostic only).
   - Training reuses the EXISTING `renquant_model_gbdt` engine verbatim
     (`ModelTrainingJob`: purged WF CV → rank:pairwise booster → version:3
     artifact, `kind="panel_ltr_xgboost"` so the existing scorer entry point
     serves it). Normalization is train-fit `panel_raw_z` (per-fold re-fit
     via the CV's injected builder — no leakage). Cutoff embargo in CALENDAR
     days (not BDay).
   - Fingerprint stamps ride the unified
     `renquant_common.model_fingerprint` via the SAME `StampFingerprintTask`
     the equity family uses — no new impl (M6 lesson). All crypto stamps
     nest under the artifact's `metadata` key (OPERATIONAL in the v1
     classification tables): **no new top-level key, no classification-table
     change, no schema bump**. `stamp()`/`verify()` round-trip pinned.

2. **Fee-aware WF gate (D-C8b)** (`fee_gate.py`):
   - Soft-consumes the generic cost primitive `renquant_common.cost_model`
     (companion PR, D-C8a) with a frozen byte-identical local fallback
     (`_cost_model_fallback.py`, parity-tested) — merge order free, no pin
     bump (the pipeline#183 / base-data#41 pattern). Resolution recorded in
     the gate's provenance stamp.
   - Crypto taker default 25 bps [GUESS: Stage-0 battery verifies from fill
     receipts — stamped `GUESS_stage0_verifies` in every artifact].
   - `net_of_cost_wf_evaluation`: fold construction identical to the gross
     CV; per fold trains a booster, replays a top-k equal-weight strategy
     (weight drift tracked; realized turnover; costs on trade days via the
     shared primitive; held-name bar gaps fail closed) and runs BTC
     buy-and-hold + the pre-registered naive 20cd BTC-timing rule on the
     same window. `net = gross − cost_model(...)`; gross-pass/net-fail is a
     FAIL.
   - **§4.3/§4.4 "beat buy-and-hold BTC net of fees" bar = computed
     DIAGNOSTIC, not an enable path**: stamped
     `diagnostic_only: true, enable_path: false,
     owner_of_enablement: stage_2_5...`; ties do NOT pass (superiority
     framing per §6.1). Nothing in this repo flips a sleeve on.

3. **Survivor-bias honesty (§4.6)**: training universe = STATIC
   current-pairs list (caller-pinned, never discovered); every artifact
   stamps `survivorship_claim: exploratory_survivor_only_panel`,
   `evidence_tier: tier1_exploratory_survivor_only` + the explicit tier
   note (tier-1 may inform model/feature choices, may NOT justify
   full-universe promotion; tier 2 = prospective Stage 1/2/2.5), and
   `pit_upgrade: stage0_item_pending`.

## Boundaries

Model repo owns training/eval/promotion internals only: no live-execution
logic, no broker code, no `kernel.*` imports (hermetic subprocess boundary
test). Feature OPERATORS stay in base-data (consumed, with D-C2's own call
as the fallback); the shared cost math stays in renquant-common (D-C8a).

## Tests (54 new in `tests/crypto/`)

- Feature/label determinism: double-assembly frame+hash equality; label
  hand-checks (`close[D+20]/close[D]−1` exact; gap ⇒ NaN; last-20d NaN).
- Fee-gate arithmetic: fully hand-computed 4-day rotation replay (gross
  0.21 / net 0.20148875 / cost 0.0075), drift-aware turnover (1/3 after a
  double), buy-and-hold + timing-rule hand math, tie-does-not-pass,
  gross-pass/net-fail = FAIL.
- Fingerprint stamps: canonical `model_content_sha256` equality,
  `stamp()`/`verify()` round-trip, operational-stamp invariance vs
  predictive-key sensitivity, persisted-reload equality.
- Equity-family byte-identity: equity artifact fingerprint bit-identical
  before/after importing the crypto package; frozen engine constants
  pinned; equity context defaults unaffected.
- Soft-consume: fallback↔common behavior-grid parity (skips cleanly in a
  fallback-only env).

## Verification

- Fallback path (sibling renquant-common on main, no `cost_model`):
  **316 passed, 1 skipped** (the parity test) — baseline before this PR:
  263 passed.
- Consume path (pythonpath pointed at the companion common branch
  `feat/net-cost-primitives`): **317 passed, 0 skipped** — parity test
  green against the real canonical.
- Equity families: zero files modified (`git diff --stat` shows additive
  package + tests + this doc only).

## Cross-repo

Companion PR (renquant-common): feat(cost) `renquant_common.cost_model`
(D-C8a). Merge order free by soft-consume; common SHOULD merge first.

## Out of scope (per RFC lanes)

Crypto-native feature families beyond the alpha158 price/volume subset
(D-C3 base-data side), PIT universe reconstruction (Stage-0), model card +
artifact publication + production training config (D-C9 completion),
Stage-0 fee calibration, any orchestrator/pipeline/execution wiring
(D-C4..D-C7, D-C11..D-C13).

---

## r2 (same day) — Codex review fixes

1. **Lookahead (blocking finding)**: the r1 replay decided AND filled at the
   same bar's close — a fill priced inside the decision's information set.
   Frozen feasible convention now: a decision from bar D fills at the close
   of bar `D + execution_delay_bars` (default 1, the next observable daily
   mark; 0 rejected everywhere); the delay period's return accrues to the
   PRE-fill book; turnover costs are charged on the fill bar; decisions
   whose fill bar falls beyond the window EXPIRE unexecuted (counted). The
   pre-registered BTC-timing baseline takes the SAME delay (it conditions on
   the decision bar's close); buy-and-hold takes none (it conditions on
   nothing — and being fully invested from bar 0 vs the strategy's bar-1+
   start is conservative AGAINST the strategy). Every result stamps an
   `execution_convention` block. **Regression tests (Codex-required)**:
   perturbing a decision bar's close leaves the replay's accounting
   bit-identical, for both the strategy replay and the timing rule
   (`tests/crypto/test_fee_gate.py::TestExecutionDelay`,
   `TestBtcBaselines::test_timing_rule_regression_...`). All replay hand
   math recomputed for the delayed-fill timeline.
2. **Cost-model soft fallback REMOVED; measured-spec-gated net verdicts**:
   `_cost_model_fallback.py` deleted; `renquant_common.cost_model` is a HARD
   import (pyproject pin `renquant-common>=0.12.0`; informative fail-closed
   ImportError below it — verified directly against common main). The gate
   emits a NET verdict ONLY with a caller-supplied spec + a validated
   MEASURED attestation (`{source: stage0_battery|live_canary, measured_at,
   evidence_ref}`); the 25 bps default stays a [GUESS] research constant the
   gate structurally cannot turn into a net number. Without attestation:
   labeled `grade: gross_only_diagnostic`,
   `net_verdict_status: withheld_unmeasured_cost_spec`, promotion verdict
   withheld. Spec-without-attestation and malformed attestations are hard
   errors (never silent downgrades). Every emitted spec stamps its canonical
   identity: `cost_spec` dict + `cost_spec_sha256`
   (`cost_model_content_sha256`, cross-repo golden-pinned) + schema version
   + attestation.
3. **Exploratory boundary hardened**: gate results (and the artifact stamp)
   now carry `decision_grade: false` + explicit reasons (tier-1
   survivor-only panel; unmeasured/partially-measured cost spec; no
   prospective Stage 1/2/2.5 evidence), per-fold `n_val_dates`,
   `val_start/val_end`, decision/fill/expiry counts, per-fold daily
   return mean/std, and cross-fold total-return dispersion.

### r2 verification

- Consume path (sibling common on the companion branch, 0.12.0):
  **334 passed, 0 skipped** (71 crypto tests).
- Pre-D-C8a env (sibling common on main): **263 passed + 4 skipped** — the
  four crypto test modules skip with the explicit hard-dependency reason;
  equity suite byte-identical to the pre-PR baseline (263). Fail-closed
  import verified directly.
- Merge order is now HARD: common#28 (0.12.0) must merge and siblings sync
  before the crypto family is usable; the equity families are unaffected
  either way.
