# Standalone momentum pipeline — train / test / trade architecture

**Status:** PROPOSAL for review. Operator directive 2026-08-02: *"模型有了，
但是要有自己的训练，测试，交易 pipeline"* — the momentum model graduates from
one-shot studies to a standing vertical: its own training pipeline, its own
recurring evaluation, and its own (shadow) trading lane. This document fixes
the architecture, repo ownership, contracts, and build order. It changes no
behavior by itself.

## Why this shape (what the two sealed studies taught)

v1/v2 (model#189/#193) established honestly that HISTORY cannot answer the
fine-grained monthly question at our standards: ~2,378 daily observations
collapse to ~59 independent ones under the h=20 overlap, and the frozen 0.04
target is underpowered there (positive-control detection 0.559 vs the 0.80
floor `[VERIFIED — model#193]`). The remedies are structural, and they are
exactly a pipeline, not another study:
1. **Forward evidence** — a shadow lane accumulates NEW independent
   observations at ~1/day instead of re-squeezing the same past.
2. **Recurring honest evaluation** — the validated v2 machinery becomes a
   standing test harness run at every retrain, logging evidence instead of
   issuing one irrevocable verdict.
3. **Gate-compatible artifacts** — training emits artifacts that carry the
   #94 admissibility fields from day one, so IF promotion is ever proposed,
   the lineage-capable WF gate can certify it without retrofits.

## The three pipelines

### 1. TRAIN (renquant-model — owner of training internals)

- New package `renquant_model_momentum` promoting the existing pieces
  (`renquant_model_common.momentum_features` F1–F5 + composite;
  `renquant_model_common.total_return`) behind ONE artifact-producing entry:
  `train_momentum_artifact(asof, universe, params) -> artifact`.
- "Training" for this construction = the rolling estimation itself (252d
  window / 21d skip residual OLS per name; the frozen v1 constants are the
  v0 params `[VERIFIED — model#164 §2]`) + per-date cross-sectional z stats.
  No fitted hyper-parameters in v0; the params block is versioned so a
  future weighted composite is a NEW params version, never a silent change.
- **Artifact contract (gate-compatible from day one):** self-carried
  `cutoff_date`, `effective_train_cutoff_date`, `cutoff_embargo_days`,
  params + universe + input digests (panel/OHLCV per-file shas), content
  sha256 — mirroring the gbdt window artifacts the lineage gate already
  admits (backtesting#95/#99). TYPE discipline per the stringified-norm_kind
  lesson: every list stays a list.
- Cadence: weekly, aligned with the WF world; each run appends to a
  momentum artifact ledger (append-only, digest-chained like the Job B
  extension manifest).
- Inputs: the LIVE ohlcv/panel surfaces read with per-file digest RECORDING
  (not pinning — this is production training, not a frozen study; the digest
  record is what makes any later dispute answerable). No writes outside the
  artifact store.

### 2. TEST (renquant-model — the recurring harness)

- The v2 gap-block machine (model#192's `goal7_momentum_v2_run.py` internals)
  refactored into a REUSABLE evaluator `evaluate_momentum_artifact(artifact,
  eval_window) -> report`: same block geometry, same degenerate-sd and ρ₁
  valves, same positive/negative controls with published per-rep counts —
  but parameterized over the evaluation window and RECURRING.
- Run at every retrain over the trailing OOS window; the report is APPENDED
  to an evaluation ledger (`momentum_eval_ledger.jsonl`, additive). No gate,
  no verdict wording: the ledger rows carry the raw gates' outputs
  (power-adequacy, controls, block-t) and the standing interpretation rule:
  **capital promotion is NOT on this path** — promotion, if ever proposed,
  goes through the WF lineage gate with these artifacts.
- The h=60 question (the marginally-viable one, `[推导 — the #190 design-time
  arithmetic]`) rides here as a second evaluation horizon in the SAME ledger
  once fwd_60d labels are wired — evidence accumulation, not a one-shot.

### 3. TRADE — shadow only (strategy-104 config + existing shadow infra)

- A `shadow_models` entry in strategy-104 (the slot vacated by the retired
  hf_patchtst lane) pointing at the momentum artifact; the pipeline's shadow
  scoring path serves it daily alongside the primary — read-only, zero
  capital.
- The EXISTING GOAL-1 machinery watches it for free: shadow sentinel
  (multi-lane), shadow_lane_preflight, the blend-readout-style forward
  ledger (picks overlap, realized labels at maturity). This is deliberate:
  the momentum lane inherits every silent-death guard built this month.
- **Standing rule restated:** shadow here is DATA COLLECTION. No verdict is
  claimed by deployment; live-capital promotion requires the standard gates
  (WF lineage + freshness + operator sign-off) — unchanged.

## Build order (each slice its own reviewed PR)

1. This design (review → merge).
2. TRAIN: package + artifact contract + weekly job code + tests (golden:
   artifact reproduces the v1 runner's scores on a fixed date to <1e-9 —
   the constructions must be THE SAME code, imported not copied).
3. TEST: the reusable evaluator + ledger + tests (the v2 runner's synthetic
   fixtures port over).
4. TRADE: s104 shadow_models config PR + shadow-lane registration tests.
5. Machine landing (launchd job for the weekly retrain + run-checkout/pin
   sync) — ONE operator grant with reverts, per the containment protocol.
   Until granted, everything above is merged-but-dark by design.

## Not claimed / boundaries

- No alpha claim anywhere in this document; the pipeline exists to MEASURE.
- Repo boundaries honored: training internals in renquant-model; the shadow
  serving config in strategy-104; no broker code (shadow only); the
  orchestrator only schedules.
- The v1/v2 sealed results stay untouched; the estimand they closed stays
  closed. The recurring harness asks the SAME question only as accumulating
  evidence, never as a re-adjudication of the sealed shots.
