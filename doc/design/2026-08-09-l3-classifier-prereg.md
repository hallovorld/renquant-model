# L3 meta-label classifier — preregistration (every choice frozen before training)

The third layer's experiment contract, at the standard of orch#910 §10 and
the L2 records: model class, features, splits, metrics, thresholds and kill
conditions are fixed HERE, before any training run exists to steer them.

**Ownership (relocated from orch#929 per its review):** the classifier
preregistration is model-factory research and lives in THIS repo; the
orchestrator owns the dataset export only. The orchestrator-side doc is
reduced to the dataset-contract pointer
(`renquant-orchestrator/doc/design/2026-08-09-l3-classifier-prereg.md`).

Number provenance (LONG row 10): every corpus figure in this document tagged
`[VERIFIED — …]` was re-measured in the relocation session by read-only
reads (runs DB opened `mode=ro`; dataset figures from a rebuild of the
orch#928 module with CSV + manifest written under /tmp; regime-calendar
count from the committed posterior CSV) and matches the canonical
post-correction record in
`renquant-orchestrator/doc/progress/2026-08-09-l3-candidate-dataset.md`.
Frozen design constants — numbers this document *chooses* rather than
measures — are tagged `[ASSUMED — frozen here]`.

## 0 · Dataset contract (consumed, not owned)

Producer: `renquant-orchestrator/src/renquant_orchestrator/l3_candidate_dataset.py`
(merged orch#928), schema `l3_candidate_dataset.v1`. One row per
(run_date, ticker) from each date's widest candidate run; label = market
forward return at the score date (`fwd_20d` primary, `fwd_60d` carried);
acted-ness (`selected`, `blocked_by`) and provenance (`run_type`) are
columns, never filter defaults. Canonical manifest `[VERIFIED — manifest,
re-measured in relocation session]`: 7,167 rows / 523 dates / 1,275
candidates without a forward row excluded-and-counted / selected 135 / base
win rate 0.6307 / live 2,189 vs sim 4,978.

**REGIME GATE (orch#930):** the merged #928 join takes the run_date's
latest `live_state_snapshots` row — NOT causal (a later same-day snapshot
postdates the scoring; codex P0 on orch#929). orch#930 replaces it with the
join by RUN IDENTITY: the same run's snapshot, whose regime that run
computed before scoring, with `regime_source = same_run_snapshot | absent`
and `regime_snapshot_created_at` carried per row. Regime-based features in
this prereg are therefore **gated on orch#930 being merged** — the
deterministic rule is in §2.

## 1 · Hypothesis under test

A small classifier on ENTRY-TIME features can identify conditions under which
the panel's candidates win (fwd_20d > 0) at a rate materially above the
act-always baseline — the AFML meta-labeling shape: precision via selection
on an existing signal, not a new signal. `[knowledge anchor — López de
Prado, AFML; the repo's win-rate memory names this the honest lever]`

## 2 · Frozen experiment

| element | frozen choice | rationale |
|---|---|---|
| model class | **logistic regression, L2, C=1.0** `[ASSUMED — frozen here; scikit-learn default]` | smallest class expressing monotone effects; 7,167 rows `[VERIFIED — manifest]` / 6–11 features (per the regime gate) `[DERIVED — count of the frozen feature lists]` affords nothing exotic |
| secondary (descriptive only) | depth-2 GBDT, 100 trees, lr 0.1 `[ASSUMED — frozen here; conventional defaults]` | nonlinearity probe; carries NO decision weight |
| features — base (unconditional) | panel_score, mu, sigma, expected_return, rank_score, n_candidates_that_date — 6 features `[DERIVED — count of this list]` | entry-time only; EXCLUDED: selected/blocked_by (post-decision), kelly_target_pct (function of mu/sigma), sector (cardinality vs live sample) |
| features — regime block (**GATED on orch#930**) | regime one-hot over {bull_calm, bull_volatile, bear, choppy, absent} + regime_confidence (0 when absent) — 5 additional features. **Admitted ONLY if orch#930 (run-identity causal join) is merged when the training run starts; otherwise the run executes on the 6 base features and the block is EXCLUDED.** The gate resolves once, at run start, from merged state — no mid-run choice; admitting the block later is a NEW dated prereg. `[ASSUMED — frozen here]` | under the merged #928 date-join the field is non-causal and may not be frozen (codex P0). Under #930's join regime is honestly live-only — 2,184 of 2,189 live rows carry it, all 4,978 sim rows are `absent` `[VERIFIED — read-only rebuild on the orch#930 head, relocation session]` — so `absent` is encoded as its own recorded category, never imputed, and the run_type-split reporting below is the guard |
| label | win = fwd_20d > 0 | the dataset's declared primary horizon |
| split | expanding walk-forward, quarterly steps, **20-trading-day embargo** `[DERIVED — equals the fwd_20d label horizon]` at every boundary | the label overlap horizon; no random splits, ever |
| training rows | ALL rows (sim + live), **declared**: sim features come from historical model versions — run_type is reported as a metric split, never silently pooled | the alternative (live-only, 2,189 rows `[VERIFIED — manifest]`) is a prereg VARIANT run alongside, not a post-hoc choice |
| decision thresholds | τ ∈ {0.5, 0.6} `[ASSUMED — frozen here]`, both frozen | two, not a grid |
| primary metric | **expectancy uplift**: mean(fwd_20d \| P≥τ) − mean(fwd_20d \| all), per fold | the decision quantity, not AUC |
| secondary metrics | AUC, calibration slope/intercept | descriptive |
| placebo | labels shuffled WITHIN date, 200 seeds `[ASSUMED — frozen here]` | kills cross-sectional leakage stories |
| external test | the 64 `trade_evaluations` rows `[VERIFIED — sqlite ro count, relocation session]`, evaluated **once**, after all folds, never tuned against | the only forward-labeled honest set |

## 3 · PASS / KILL (deterministic)

PASS requires ALL (every threshold in this list `[ASSUMED — frozen here]`;
the 64 is `[VERIFIED — sqlite ro count, relocation session]`):
1. fold-consistent positive primary-metric uplift at τ=0.5 (median across
   folds > 0 AND ≥ ⅔ of folds > 0);
2. uplift exceeds the within-date-shuffle placebo's 95th percentile;
3. the once-only external test does not contradict (uplift ≥ 0 on the 64
   rows; with n=64 this is a sign check, stated as such);
4. calibration slope in [0.5, 2.0] on pooled folds (a wildly miscalibrated
   P is not a usable gate).

Any leg fails ⇒ KILL for this feature set and model class; the record states
"the panel's entry quality is not predictable from these entry-time features
at this history" — a completed outcome. **No feature additions, no threshold
moves, no model upgrades inside this prereg.** A new attempt is a new dated
prereg. The regime gate (§2) is not a threshold move: it is a frozen
either/or resolved by external merge state before the run begins.

## 4 · What PASS earns — and does not

PASS earns a SHADOW lane only: the classifier logs act/skip/half verdicts
beside the live run daily (the L1 shadow pattern; same grant class — its own
operator-granted batch). It does NOT earn order impact; that promotion needs
the shadow record plus an operator grant, and remains subject to the
promotion guards (§10-pattern) like every other layer.

## 5 · Failure modes anticipated (so they cannot be discovered as surprises)

* **Sim-feature drift**: 69% of rows `[DERIVED — 4,978 sim / 7,167 total,
  manifest]` carry features from historical model versions; run_type-split
  metrics are mandatory in the report, and a PASS driven only by sim rows
  with live rows flat is reported as NOT transferable.
* **Regime collinearity** (only if the §2 regime block is admitted):
  bull_calm dominates the calendar (1,240 of 2,388 posterior days
  `[VERIFIED — argmax count over committed renquant-orchestrator/
  doc/research/data/2026-08-08-regime-posteriors.csv, relocation session]`);
  regime coefficients may be unidentified — reported, not patched. And since
  regime is live-only under the causal join, the `absent` category is
  collinear with run_type=sim by construction — reported alongside the
  run_type split, never "fixed" by imputation.
* **Base-rate drift**: the 0.6307 base win rate `[VERIFIED — manifest]` is a
  bull-period artifact; the uplift metric is relative per fold, which is the
  defense, and the placebo is within-date, which preserves each date's base
  rate exactly.

## 6 · What this prereg does not cover

Position sizing from P (half-size bands), cost interactions, and any use of
the classifier on SELL decisions are all out of scope — each would be its
own dated prereg on this dataset or a successor.
