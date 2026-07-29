# PREREG (FROZEN) — is the panel's signal at a LONGER horizon than we trade?

Frozen: 2026-07-28, before the run. Author: claude · Reviewer: codex.
Origin: operator question — "用旧 patchtst 替代新 patchtst 来预测？这很诡异！
是不是哪里不对？如果真有 alpha 的话有可能 streamline 吗？"

## 0. Known-trap checklist

| # | past failure | avoided how |
|---|---|---|
| T1 | a placebo sitting on the signal's own peak | nulls here are within-date permutation and a **horizon-matched** shuffle; no lag-shift null anywhere |
| T2 | naive t on overlapping labels | block-level inference with the block length set to EACH arm's own label horizon (a 120d arm blocks at 120d, not 60d) — the longer arm is penalised correctly, never flattered |
| T6 | post-hoc horizon picking | the horizon grid is enumerated here before the run: 20, 60, 100, 120, 160 trading days |
| T9 | acting on a striking by-product | this registers the test; nothing from Stage 0 (model#86) or model#87 is treated as a result — see §1 |
| **T10 (new)** | **confusing "the score is stale" with "the signal is long-horizon"** — a stale score can look long-horizon because the score barely changes | an explicit **turnover-matched control**: the same test on a deliberately smoothed version of the prod XGB score (60-day rolling mean), which manufactures persistence WITHOUT changing the underlying signal. If smoothing alone reproduces the long-horizon profile, the effect is persistence, not horizon. |

## 1. The motivating question (unverified — this run is what answers it)

Operator question, off a persistence finding that has not itself been
confirmed: does the panel's cross-sectional signal live at a longer label
horizon than the 60d we currently train and trade?

No prior IC-vs-lag table is asserted as evidence here. GOAL-6 Stage 0
(model#86) carries open CHANGES_REQUESTED findings on its own PR and has
not reached an approved, merged result; model#87's closure verdict was
retracted and has no confirmatory run merged either. Citing
`goal6-stage0/results.json` or a "PatchTST CLOSED at 60d" claim as
`[VERIFIED]` premises here would misstate their PROCESS status — separate
from whether the underlying scratch computation behind either is itself
correct (it may be — that is not settled by this doc and is not this
prereg's question to answer). §2's frozen source contract is what THIS run
must execute against to answer the operator's question; establishing
whether IC actually rises with label lag is part of what it measures, not
a premise it is handed.

Two competing explanations, and the design must separate them:
- **H-A (horizon relocation):** the information genuinely concerns returns
  3–6 months out. Actionable — retrain and trade at that horizon.
- **H-B (persistence artefact):** slow-moving scores plus overlapping labels
  manufacture the profile. Not actionable; the "signal" is an autocorrelation
  shadow.

## 2. Design (frozen)

- **Subjects:** prod XGB corpus (primary — it is the model that trades) and
  the certified clf corpus, both on the 142-name intersection. PatchTST is
  included as a descriptive third subject only; its own capability question
  is open (model#85's evaluation and model#87's closure are both
  unresolved) and this prereg neither closes nor un-closes it.
- **Source contract (frozen, mandatory before the run):** each subject's
  score panel must be named by an explicit artifact path resolvable at
  execution time — a checked-in path + git commit/run-id, or, for
  scratch-computed inputs, an explicit scratch path + file hash recorded in
  the results doc. A results doc citing a path that cannot be resolved at
  execution time is not a valid basis for any verdict under this prereg,
  full stop.
- **Horizon grid (frozen):** 20, 60, 100, 120, 160 trading days. For each,
  the label is the realised excess return over exactly that window,
  constructed from the same OHLCV source as the existing labels.
- **Statistics (frozen estimator + SE):** per-date rank IC and top-decile-
  minus-bottom-decile spread return. Block-level inference: non-overlapping
  blocks of length `h` (the arm's own horizon) trading days, block
  boundaries at `t = 0, h, 2h, ...` counted from the corpus's first
  eligible date for that horizon; the block statistic is the mean of the
  per-date statistic (IC, or spread return) within the block; the
  estimator is `mean(block_stats)` over `N_h = floor(T_h / h)` blocks
  (`T_h` = number of eligible trading days at horizon `h`);
  `SE = std(block_stats, ddof=1) / sqrt(N_h)`; degrees of freedom
  `df = N_h − 1`. `t = mean(block_stats) / SE`, Student's-t with that `df`
  — never a fixed critical value.
- **Nulls, per arm (frozen):** (i) within-date permutation of the score
  across the cross-section (20 seeds, same eligible universe/date as REAL);
  (ii) the T10 turnover-matched control — the PROD XGB score smoothed by a
  **causal** 60-trading-day rolling mean per ticker (`min_periods=60`, no
  look-ahead), then cross-sectionally re-ranked per date (matching REAL's
  rank-IC construction) before computing IC/spread — restricted to the SAME
  eligible dates and SAME 142-name universe as REAL at that horizon.
- **Multiplicity (frozen):** `h*` is chosen as the argmax over 5 horizons
  (§3), a 5-way selection, not a single test. Base two-sided significance
  level `α = 0.05`; Bonferroni-corrected per-horizon level
  `α_adj = α / 5 = 0.01`. The decision critical value is
  `t_crit(df) = scipy.stats.t.ppf(1 − α_adj / 2, df)`, evaluated at the
  winning horizon's OWN block-level `df` from the Statistics bullet above —
  **not** a fixed `2.0`. All 5 per-horizon `t`, `df`, and `t_crit` values
  are reported in the results doc regardless of which wins, so the
  selection is auditable.
- **Cost realism (required, not optional, frozen source):** cost per
  round-trip is `renquant_common.cost_model.round_trip_cost_bps(spec)`
  using the production `CostModelSpec` — not a new estimate. For each arm:
  `bets_per_year = 252 / horizon_trading_days`;
  `annualised_cost = round_trip_cost_bps/1e4 * bets_per_year`;
  `net_edge = REAL_block_mean_spread_return(h) − annualised_cost`, where
  `REAL_block_mean_spread_return(h)` is the top-decile-minus-bottom-decile
  spread's block-level estimator from the Statistics bullet — the only
  registered statistic that is itself a return (rank IC is a correlation
  and is never netted against cost). Pass threshold: an arm can only be
  eligible for RELOCATE if `net_edge > 0` at its own `h*` — a positive-`t`
  arm that fails this still cannot RELOCATE. This is evaluated in the
  results doc, not asserted here.

## 3. Decision rule (frozen)

Let `h*` be the horizon maximising (REAL − permutation) block-level t for
the PROD XGB, with `t*` its value.

- **RELOCATE (open a shadow at h\*)** — `t* ≥ t_crit(df at h*)`
  (Bonferroni-corrected per §2, not a fixed `2.0`) AND `h* ≠ 60` AND the
  turnover-matched control at `h*` is materially weaker than REAL (its t
  below half of `t*`) AND the clf subject agrees in direction AND
  `net_edge > 0` at `h*` per §2's cost arithmetic.
  Consequence: a shadow lane trained and scored at `h*`, entering through the
  standard gate chain. NOT a production switch.
- **STAY (60d is correct)** — `h* = 60`, or `t* < t_crit(df at h*)`, or the
  turnover control reproduces the effect, or `net_edge ≤ 0` at `h*`.
- **INCONCLUSIVE** — anything else, including a broken arm or a source
  artifact that fails the §2 source contract.

Ties and ambiguity resolve to STAY: the burden of proof is on moving, not on
keeping. No post-hoc horizon outside the frozen grid may be adopted.

## 4. Why this matters beyond one model

If RELOCATE holds, every gate, label, and turnover assumption in the stack is
mis-specified in the same direction, and the fix is a recipe change rather
than a new architecture. If STAY holds, the long-lag profile is an
autocorrelation shadow and the programme keeps its current horizon with one
fewer open question. Both outcomes are useful; neither is a promotion.
