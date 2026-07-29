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
| T9 | acting on a striking by-product | this registers the test; nothing from Stage 0 (model#86) or model#87 is treated as a result — see the CORRECTION below |
| **T10 (new)** | **confusing "the score is stale" with "the signal is long-horizon"** — a stale score can look long-horizon because the score barely changes | an explicit **turnover-matched control**: the same test on a deliberately smoothed version of the prod XGB score (60-day rolling mean), which manufactures persistence WITHOUT changing the underlying signal. If smoothing alone reproduces the long-horizon profile, the effect is persistence, not horizon. |

## CORRECTION (visible, per long-term-agreements.md entry 10)

An earlier version of §1 stated an "IC rises with label lag" table tagged
`[VERIFIED — goal6-stage0/results.json, wf-eval/diagnostics.log]`, and §2
stated PatchTST "is CLOSED at 60d (model#87)". Neither claim has a real
source: GOAL-6 Stage 0 (model#86) has not run an approved/executed result
`[VERIFIED — model#86 review thread, 5 unresolved CHANGES_REQUESTED
findings as of 2026-07-29]`, and model#87 is a frozen prereg with its
results commit dropped after the corpus it depended on was found not to
exist `[VERIFIED — model#87 branch history]`. Retracted, not restated.
This prereg is now a pure pre-run design: the motivating observation is
the operator's question, not a verified measurement, and establishing
whether IC actually rises with label lag is part of what THIS run
measures — not a premise it is handed.

## 1. The motivating question (unverified — this run is what answers it)

Operator question, off a persistence finding that has not itself been
confirmed: does the panel's cross-sectional signal live at a longer label
horizon than the 60d we currently train and trade? No prior IC-vs-lag
table is asserted as evidence here; §2's frozen source contract is what
this run must execute against to answer it.

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
  is open (model#85's 43-fold signal-existence evaluation has not run) and
  this prereg neither closes nor un-closes it.
- **Source contract (frozen, mandatory before the run):** each subject's
  score panel must be named by an explicit, checked-in artifact path and
  git commit/run-id at execution time; a results doc citing a path that
  does not exist in the repo at a resolvable commit is not a valid basis
  for any verdict under this prereg, full stop.
- **Horizon grid (frozen):** 20, 60, 100, 120, 160 trading days. For each,
  the label is the realised excess return over exactly that window,
  constructed from the same OHLCV source as the existing labels.
- **Statistics:** per-date rank IC and top-decile spread, block-level, with
  the block length set to the arm's OWN horizon.
- **Nulls, per arm:** within-date permutation (20 seeds) and the
  **turnover-matched control** of T10.
- **Multiplicity (frozen):** `h*` is chosen as the argmax over 5 horizons
  (§3), which is a 5-way selection, not a single test. The reported
  decision t at `h*` must clear `t* ≥ 2.0` against a Bonferroni-corrected
  per-horizon threshold of α/5 (two-sided), i.e. the same `t* ≥ 2.0` bar
  restated after correction — not a post-hoc single-horizon comparison.
  All 5 per-horizon t-values are reported in the results doc regardless of
  which wins, so the selection is auditable.
- **Cost realism (required, not optional, frozen source):** cost per
  round-trip is `renquant_common.cost_model.round_trip_cost_bps(spec)`
  using the production `CostModelSpec` — not a new estimate. For each arm:
  `bets_per_year = 252 / horizon_trading_days`;
  `annualised_cost = round_trip_cost_bps/1e4 * bets_per_year`;
  `net_edge = (REAL block-level mean return at h) − annualised_cost`.
  Pass threshold: an arm can only be eligible for RELOCATE if
  `net_edge > 0` at its own `h*` — a positive-t arm that fails this still
  cannot RELOCATE. This is evaluated in the results doc, not asserted here.

## 3. Decision rule (frozen)

Let `h*` be the horizon maximising (REAL − permutation) block-level t for
the PROD XGB, with `t*` its value.

- **RELOCATE (open a shadow at h\*)** — `t* ≥ 2.0` (Bonferroni-corrected
  per §2) AND `h* ≠ 60` AND the turnover-matched control at `h*` is
  materially weaker than REAL (its t below half of `t*`) AND the clf
  subject agrees in direction AND `net_edge > 0` at `h*` per §2's cost
  arithmetic.
  Consequence: a shadow lane trained and scored at `h*`, entering through the
  standard gate chain. NOT a production switch.
- **STAY (60d is correct)** — `h* = 60`, or `t* < 2.0`, or the turnover
  control reproduces the effect, or `net_edge ≤ 0` at `h*`.
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
