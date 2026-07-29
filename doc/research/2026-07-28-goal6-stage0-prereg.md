# PREREG (FROZEN) — GOAL-6 Stage 0: re-baseline the ruler

Frozen: 2026-07-28, before any Stage-0 run.
Design: orchestrator `doc/research/2026-07-28-goal6-model-capability-design.md` §5 Stage 0.
Author: claude · Adversarial reviewer: codex.
Cost: zero new data, zero cloud, CPU only (the existing XGB 43-fold corpus,
`walkforward_manifest_gbdt_prod_recipe_v2`, scores at ~15s/fold).

## 0. Known-trap checklist (mandatory section; each item names a real past failure)

| # | past failure | how THIS design avoids it |
|---|---|---|
| T1 | 2026-07-28: chose a `shift+120d` placebo that turned out to sit on the **peak** of the score's own predictive profile (IC lag-100d = +0.078, t=3.21), making `real − placebo` structurally negative and the decision statistic uninformative | no lag-shift null is used as a decision statistic. Nulls are §3: label permutation within date, and a **persistence-matched** control. The lag profile is measured as a RESULT, never used to define the null |
| T2 | 2026-07-28: reported naive per-date t (+5.39) on overlapping 60-day labels whose block-adjusted t was +0.70 | every t in this study is fold/block-level; naive t may be reported for comparability but is never a decision input, and each table states its `n_eff` |
| T3 | 2026-07-27→28: an invocation was frozen without an end-to-end smoke on the exact environment, and the batch was VOID | a 2-fold smoke on the exact command runs BEFORE the full sweep; the sweep is only launched if the smoke's outputs parse |
| T4 | 2026-07-28: machine slept 5h mid-run, freezing a batch at 12/43 | any run >15 min is launched under `caffeinate -i -w <pid>` |
| T5 | recurring: absolute IC quoted without its matched null | every reported effect is a REAL − NULL difference with its own dispersion; absolute values appear only in descriptive tables that say so |
| T6 | recurring: post-hoc subgroup search rescuing a dead result | the hypothesis set below is closed. Regime/sector/date splits are descriptive-only and may not change any verdict |
| T7 | 2026-06→07: production inputs mutated by an experiment | read-only: no write outside the scratch dir; no file under `RenQuant/data/` or any live artifact/state is opened for writing |
| T8 | recurring: model/panel internals implemented in the orchestrator | this study lives in **renquant-model**; the orchestrator holds only the design + registry |

## 1. Question

Given the same already-trained models and the same panel, **which
measurement choice — statistic and horizon — has the most power to detect
the edge that is actually there?** This is a measurement study. No model is
trained, promoted, or killed by it.

## 2. Subjects and data

- **Models, Stage 0 executable scope (already trained, unchanged):**
  (a) production panel-LTR XGB ranker; (b) the certified top-decile
  classifier (the blend leg). Both score against the existing corpus
  `data/exp/oos_pick_table_recipe_v2.parquet` (508 dates, 2024-02-02 →
  2026-02-11, 43-fold `walkforward_manifest_gbdt_prod_recipe_v2`) — an
  artifact that exists on disk today, read-only, not recomputed.
- **PatchTST is OUT OF SCOPE for this Stage-0 run.** An earlier draft of
  this prereg claimed model#85's "43-fold corpus scores already computed
  (`scores.parquet`, 88,750 rows)" as a reusable input; that specific
  claim does not hold — model#85 is still a queued, unmerged prereg and
  no `scores.parquet` for this corpus is committed anywhere in this
  repo's history. That is a narrower claim than "the corpus does not
  exist": model#91 (queued, unmerged) now carries a content-addressed
  index of a 43-fold PatchTST corpus (root digest
  `b8aa2d99...`, Modal dispatch app ids `ap-RIc3qj4D3yFfU9z7tAx4Rd` /
  `ap-HHid4LhAAD0heLm7Mlk4aW`) — so the correct status is **not yet
  pinned to a stable, reviewable source contract that this Stage-0 design
  can cite**, not nonexistence. Stage 0 does not run against an input
  without a stated immutable path and fingerprint. PatchTST is added to
  Stage 0 as a follow-up amendment once model#85 (or model#91's index)
  is merged and this design cites its exact artifact path and row/date
  fingerprint — not before.
- **Panel:** the existing `transformer_v4_wl200_clean.parquet`
  (142 tickers, 2016-01-04 → 2026-04-28), read-only.
- **Labels:** `fwd_20d_excess` and `fwd_60d_excess`, both already present.
  Note they are cross-sectionally standardised (σ ≈ 1.005), so spreads are
  in cross-sectional σ units, not percentage points — every table must say so.

## 3. Statistics and nulls (frozen)

**Statistics (3):** per-date rank IC · top-decile minus bottom-decile spread
· top-decile hit rate (fraction of top-decile names with positive excess).

**Horizons (2):** 20d, 60d. Additionally, the **IC-vs-horizon profile**
(lags 0…160d in 20d steps) is computed as a descriptive result for each
model — this is the T1 finding promoted to a first-class measurement.

**Nulls (2, both computed for every statistic × horizon):**
1. **Within-date permutation**, 20 seeds — destroys cross-sectional ordering,
   preserves everything else. Verified clean in prior work (−0.0008).
2. **Persistence-matched control** — for each (date `t`, ticker) cell with a
   REAL score, the persistence-arm score is that SAME ticker's own score at
   `t − 60 trading days` (from the model's own scoring table, never
   resampled or imputed), evaluated against the SAME label at date `t` as
   the REAL arm. **Score alignment:** the `t-60` score must be an actual
   prior scoring date present in the corpus for that ticker.
   **Unavailable-score handling:** if a ticker has no score 60 trading days
   before `t` (first 60 trading days of its coverage in the corpus, or a
   gap), that (date, ticker) cell is DROPPED from the persistence arm ONLY
   — never imputed or forward-filled — while the REAL arm and the
   permutation-null arm for that date keep full coverage, unaffected. Every
   persistence-arm table reports its own coverage against the REAL arm's
   coverage (e.g. "18,240 / 20,100 cells, 90.7%"). **Block-level variance:**
   computed independently on the persistence arm's own eligible-date
   subset, using the same block-length rule as below
   (`ceil(label_horizon / rebalance spacing)`) applied to THAT subset —
   never borrowed from the permutation arm's SE, since the two arms can
   have different eligible-date counts. This isolates "does today's score
   add information beyond the persistence of an old score", which the T1
   finding showed is the actual confound (cross-sectional rank
   autocorrelation 0.59 at 1d, 0.30 at 60d).

**Inference:** all effects reported as REAL − NULL with fold/block-level
dispersion; block length = ceil(label_horizon / rebalance spacing). Every
table states `n_eff`.

**Rebalance spacing and block construction (frozen):** rebalance spacing is
1 trading day (this project's live-runner cadence generates a signal every
trading day). For horizon `h` (20 or 60 trading days), block length =
`ceil(h / 1) = h` trading days: blocks are non-overlapping windows of `h`
trading days with boundaries at `t = 0, h, 2h, ...` counted from the
corpus's first eligible date for that horizon; the block statistic is the
mean of the per-date statistic (IC, decile spread, hit rate, or a REAL −
NULL difference) within the block; `n_eff = N = floor(T / h)` blocks
(`T` = eligible trading days); block-level `SE = std(block_stats, ddof=1) /
sqrt(N)`; degrees of freedom `df = N − 1`. Every "block-level t" in this
document is `mean(block_stats) / SE` with that `df`.

**`SE_HAC` (frozen, used only for §5 H2's effect-size veto (c)):**
Newey-West HAC on the per-date (not per-block) effect-size series, Bartlett
kernel, lag `L = h_min − 1` trading days where `h_min = min(20, 60) = 19` —
the exact MA(h−1)-order dependence induced by daily rebalancing of an
h-day-overlapping forward return (Hansen-Hodrick / Newey-West rule for
overlapping-window statistics):
`SE_HAC = sqrt( (1/n) * (γ₀ + 2 * Σ_{k=1}^{L} (1 − k/(L+1)) * γ_k) )`,
where `γ_k` is the sample autocovariance at lag `k` of the per-date effect
series and `n` is that arm's own eligible-date count.

## 4. Hypotheses (closed set)

- **H1 (statistic):** the tail statistics (decile spread, hit rate) have
  higher power than full-cross-section IC on the same data.
  *Decision use:* if supported, the Stage-2 primary statistic is whichever
  tail statistic clears §5's bar with the larger own-t (tie breaks to
  spread); if refuted, Stage 2 keeps IC and the GOAL-6 §3 option A is
  withdrawn.
- **H2 (horizon):** the 20d label yields a higher power ratio (effect / SE)
  than 60d, at equal or lower effect size.
  *Decision use:* if supported, 20d becomes the **measurement** horizon for
  Stage 1–2 diagnostics. A trading-horizon change is explicitly out of scope
  and would need its own economics prereg.
- **H3 (horizon mis-specification):** at least one model's IC-vs-horizon
  profile peaks materially beyond its training horizon.
  *Decision use:* descriptive only in Stage 0. If supported, it opens a
  separate prereg — it does not modify H1/H2 verdicts.

## 5. Decision rule (frozen)

**Paired contrast, not two separate point estimates.** Every comparison
between two arms (two statistics for H1; two horizons for H2) is computed
as a PAIRED difference on the SAME within-date-permutation draws (the same
20 seeds, same dates, per §3): for seed `s`, `Δ_A(s) = REAL_A − PERM_A(s)`
and `Δ_B(s) = REAL_B − PERM_B(s)`; the paired contrast statistic
`t_pair(A,B)` is the block-level t of the per-seed difference series
`Δ_A(s) − Δ_B(s)`, s = 1..20, using the same block-length rule as §3
(`block length = ceil(label_horizon / rebalance spacing)`). This tests
whether A's edge over its own null reliably exceeds B's edge over its own
null — not whether two independently-computed t's happen to differ.

**H1 — three statistics, closed multiplicity family.** The C(3,2) = 3
pairwise contrasts (spread-vs-IC, hit-vs-IC, spread-vs-hit) use Holm-
Bonferroni correction across the 3 tests, family-wise α = 0.10 (the
codebase's existing convention for multi-statistic interaction tests).
**SUPPORTED** — BOTH `t_pair(spread, IC)` and `t_pair(hit, IC)` are
Holm-significant in favour of the tail statistic, AND each tail statistic's
own REAL − permutation t ≥ 2.0. **REFUTED** — neither tail statistic clears
both conditions. **INCONCLUSIVE** — exactly one clears, or a
Holm-significant contrast favours IC over a tail statistic. If SUPPORTED,
the Stage-2 primary statistic is whichever tail statistic has the larger
own-t (tie breaks to spread, the statistic already used for live sizing).

**H2 — one paired contrast, horizon.** Run on the primary statistic H1
selects (IC if H1 REFUTED/INCONCLUSIVE; the winning tail statistic if H1
SUPPORTED). **SUPPORTED** requires ALL THREE, none waivable: (a)
`t_pair(20d, 60d) ≥ 2.0` in favour of 20d; (b) 20d's own REAL − permutation
t ≥ 2.0; (c) `d_20d ≤ d_60d` — 20d's REAL − permutation effect size (native
units of the selected statistic) does not exceed 60d's, enforcing "equal or
lower effect size" as a hard numeric gate rather than narrative: if 20d's
apparent power edge comes from a LARGER raw effect rather than more
independent blocks, that is a different phenomenon than "the same edge
measured with more power," and H2 cannot be SUPPORTED on it. **REFUTED** —
(a) or (b) fails, or (c) fails by more than one `SE_HAC` of the smaller
sample (a clear violation, not a rounding tie). **INCONCLUSIVE** —
anything else, including a marginal/near-tie violation of (c).

**Veto (all hypotheses).** The persistence-matched null is reported for
every arm using its own eligible-date coverage and block-level SE (§3) and
is a veto: if an arm's REAL − persistence difference is not positive at
t ≥ 1.0, that arm cannot be declared SUPPORTED regardless of its
permutation-null result, because its apparent edge is stale-score
persistence rather than fresh information.

Ties, ambiguity, a broken run, or any INCONCLUSIVE verdict resolve to
Stage 2 proceeding with the CURRENT production choices (IC, 60d) rather
than an unvalidated switch.

## 6. Deliverable

One results document, opened as a SEPARATE PR after this prereg is approved
(never bundled with the prereg itself), containing: the 3 × 2 statistic ×
horizon table per in-scope model (XGB ranker, top-decile classifier — see
§2 on PatchTST's exclusion) with both nulls and block-level inference; the
IC-vs-horizon profiles; the H1/H2/H3 verdicts under §5, including the Holm
correction detail for H1; and an explicit recommendation for the Stage-2
primary statistic and measurement horizon. Negative and inconclusive
outcomes are reported with the same prominence as positive ones.
