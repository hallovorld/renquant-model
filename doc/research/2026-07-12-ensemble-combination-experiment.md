# Ensemble Combination Experiment Design

**Date:** 2026-07-12
**Status:** DESIGN — evidence protocol revised after independent review. Do not
implement, promote, or infer expected profitability from this document.
**Owner:** Model (research design, WF runner implementation, and the fitted
ensemble specification — this repo owns the experiment, not just the base
scorers). Orchestrator invokes a versioned run of this repo's WF runner and
retains the immutable run bundle (scheduling/provenance only, no research
logic). Pipeline consumes a selected, immutable ensemble specification at
inference time (no research logic, no fitting).
**Scope:** How to combine existing and new models into a single trading signal.
This document decides the combination METHOD, not the models themselves.

---

## 0. Binding reconsideration: no profitability claim

This is a **research protocol**, not evidence that an ensemble has positive
expected return, positive incremental alpha, or a right to replace the frozen
champion. Forecast-combination theory supplies a conditional prediction-error
argument; it does not establish a trading result for this 104-stock universe,
this target horizon, this portfolio mapping, or this cost model.

For a combined score to improve the live decision, all of the following must
be true at the same time:

1. Each admitted expert must supply point-in-time out-of-sample forecasts with
   correct as-of lineage and no material data-quality asymmetry.
2. The experts must contain complementary information or errors. Averaging two
   highly correlated, similarly biased scores normally just averages the same
   mistake; it does not create breadth.
3. Any forecast-level improvement must survive the actual score-to-position
   mapping, liquidity limits, turnover, fees, slippage, borrow assumptions, and
   risk constraints. A higher IC can leave the trade list unchanged, or can
   make a small gross gain that is consumed by incremental turnover.
4. The result must survive a final chronological confirmation window that was
   not used to select experts, normalize scores, choose a method, tune a
   parameter, choose a test, or set a deployment threshold.

The correct economic estimand is therefore not "does the ensemble have a
positive backtest?" It is the incremental, post-cost outcome relative to the
frozen champion under the same executable policy:

```
Delta_net = NetOutcome(ensemble, fixed_policy) -
            NetOutcome(champion, fixed_policy)
```

The null is `Delta_net <= 0`. No section below may be read as reversing that
burden of proof. If the evidence is inconclusive, the mandated action is to
retain the champion and publish the negative or inconclusive result.

### 0.1 Theory supports a conditional hypothesis, not an expected-return prior

For unbiased forecasts with stable error covariance `Sigma`, a
covariance-aware linear combination can reduce **forecast MSE** relative to an
individual forecast. That result depends on covariance estimation, calibration,
and stability. It does not optimize a discontinuous top-N portfolio after
costs, and it fails when the covariance estimate is noisy or changes across
regimes. Equal weighting is useful precisely because it avoids estimating those
weights; it is a robust benchmark, not an alpha theorem.

The literature therefore justifies testing a small, pre-registered set of
combination rules. It does not justify assuming that a second scorer creates
alpha, that a lower forecast loss converts to net return, or that a learned or
regime-conditioned rule is appropriate at the available effective sample size.

### 0.2 This section controls the earlier ladder

If this reconsideration conflicts with a statement elsewhere in this document,
this section and Section 4.5 control. In particular, L4 is **not an executable
current-stage candidate**: the available regime history is insufficient to
support state-specific weight selection without a separate feasibility and
power analysis. Its retained discussion is research background only.

---

## 1. Problem statement

We have (or will have) multiple models that each score the same 104-stock
universe:

| Model | Status | Type |
|---|---|---|
| XGB panel scorer | Primary (live) | Cross-sectional panel |
| PatchTST panel scorer | Shadow (demoted) | Cross-sectional panel |
| Per-ticker tournament | Frozen since April (timeout) | Per-ticker |
| Sector panel models | Not built | Sector-grouped panel |

The question is not "which ensemble should we deploy?" It is: **is there
enough independently generated, point-in-time evidence to justify testing a
small set of combinations, and can any of them improve the frozen champion's
post-cost outcome?**

The operator's initial vision was **hard routing** — for each ticker, pick the
one model with the best backtest and only listen to that model. This document
explains why that approach is statistically fragile, presents the
literature-backed alternative (soft combination), and defines the experiment
plan to validate it.

---

## 2. Why hard routing is not the default

### 2.1 The operator's proposed approach

> "每个 ticker 都有一个对应的最适合的模型。A 的 ticker 模型一直很好，今天
> ticker 说买 A 那我们就买 A。半导体模型认为 mu 该买，且 mu 最好的模型是
> 半导体，那就买 MU。"

This is **hard routing**: for each ticker, select the single best-performing
model based on backtest data, and route that ticker's decisions exclusively
through that model.

### 2.2 Why it doesn't work (literature evidence)

Hard routing is a high-variance choice in a small sample. The core problem is
that selecting the "best" model on backtest data can select noise rather than
signal. This does not prove that every routing rule fails; it means routing is
not an admissible default without stronger, separately pre-registered evidence
than this program can currently provide.

**Winner's curse (selection bias):** With K models and N tickers, you run K×N
comparisons. For each ticker, the model with the highest backtest IC is
disproportionately likely to have benefited from favorable noise rather than
genuine predictive superiority. With 5 models × 104 tickers = 520 comparisons,
the false discovery rate is severe.

Numerical example: suppose 5 models all have true IC = 0.03 for ticker AAPL,
but backtest noise produces observed ICs of {0.00, 0.02, 0.03, 0.04, 0.08}.
Hard routing selects the 0.08 model. Out of sample, it reverts to 0.03 — the
same as every other model. The "selection" captured noise, not edge.

**Non-stationarity:** The best model for a ticker changes over time. AAPL may
be best predicted by a sector panel during semiconductor cycle phases (2024)
and by the overall panel during macro-driven phases (2025). Hard routing to one
model based on historical performance cannot adapt to this.

**Insufficient statistical power:** To reliably distinguish model A from model
B for a single ticker requires far more out-of-sample data than we have.
5 years × 250 days = 1,250 observations per ticker. Distinguishing IC = 0.04
from IC = 0.03 at 95% confidence requires ~2,500+ observations (power
analysis; the difference is 0.01 in a noisy signal). We cannot reliably select
per-ticker.

### 2.3 Literature consensus

The forecast combination literature (50+ years, hundreds of studies)
consistently finds:

> "Combination dominates selection in virtually all contexts."
> — Timmermann (2006), "Forecast Combinations"

> "Equal weights are surprisingly hard to beat out of sample."
> — Genre et al. (2013), Forecast Combination 50-Year Review

Key papers:

| Paper | Year | Finding |
|---|---|---|
| Smith & Wallis | 2009 | Selection amplifies estimation error; combination averages it out. The mathematical explanation for why simple averaging beats sophisticated selection. |
| Timmermann | 2006 | Systematic review: combination > selection across macroeconomic forecasting, financial returns, volatility, density forecasts. |
| Claeskens, Magnus, Vitale & Zenber | 2016 | Model selection's OOS performance is systematically lower than model averaging because selection variance is underestimated. |
| Gu, Kelly & Xiu | 2020 | 30,000 US equities: ensemble average of tree + neural network models outperforms any single best model. IR 0.4–0.6 vs 0.35. The foundational empirical asset pricing paper. |
| Forecast Combinations 50-Year Review | 2022 | arXiv:2205.04216. Equal weights "surprisingly hard to beat" across 50 years of evidence, especially in small-sample / non-stationary settings — exactly our regime. |
| MoE Comprehensive Survey | 2025 | arXiv:2503.07137. Documents MoE failure modes: expert collapse (>99% representation similarity), load imbalance, gating overfitting. |

### 2.4 Hard routing vs soft combination — side by side

| Dimension | Hard routing (select one) | Soft combination (weighted average) |
|---|---|---|
| Error handling | One model wrong → fully exposed | One model wrong → diluted by others |
| Noise sensitivity | Selects the noisiest backtest winner | Averages out noise across models |
| Adaptability | Locked to historical winner | Weights can shift (L2+) |
| OOS degradation | Can be severe from selection error | Not guaranteed; depends on calibration and error diversity |
| Statistical requirement | High (must distinguish per ticker) | Still material: requires stable, complementary point-in-time forecasts |
| Literature support | Weak prior for this small-sample use | A reason to test, not direct evidence of trading profitability |

---

## 3. Design: staged soft combination

### 3.0 Stage 0 - admissibility and complementarity gate

No L1-L3 comparison may start until every proposed expert passes an
**admissibility ledger** for every historical prediction date. The ledger must
record model/content fingerprint, training cutoff, feature/data cutoff, score
timestamp, universe coverage, missingness, score orientation, and realized
label availability. A model with only a retrospective score file is not an
admitted expert.

Before fitting weights, the development period must also report, without using
the final confirmation window:

- cross-sectional score correlation and rank correlation by date;
- residual/error correlation at the actual prediction horizon;
- disagreement coverage: the fraction of dates and names for which the expert
  would alter the champion's rank or executable decision;
- incremental gross contribution under a fixed policy before and after costs;
- coverage and missingness parity versus the champion.

There is no universal correlation cutoff that proves complementarity. Instead,
the gate is falsifiable: if an expert has near-duplicate scores/errors, fails
as-of/coverage parity, or produces no economically material decision change,
it is excluded and the result is recorded as "no admissible incremental
expert." Do not fit an ensemble merely because two model classes have different
names.

### 3.1 Maturity ladder

The experiment follows a strict ladder. Each level is tested against the
previous level. Advancing requires statistically significant OOS improvement
measured on held-out data never seen during any model training, weight
selection, or hyperparameter tuning.

```
L1:     Equal-weight average (2 experts: XGB + PatchTST)
         ↓ beats frozen champion?
L2:     Inverse-variance weighted (2 experts)
         ↓ beats L1?
L1-3E:  Equal-weight average, SAME-SET CONTROL (3 experts: XGB + PatchTST +
        per-ticker) — computed the moment a 3rd expert becomes available,
        BEFORE L3 is evaluated (see §3.1bis)
         ↓
L3:     Linear stacking (meta-model, 3 experts)
         ↓ beats L2 AND beats L1-3E?
L4:     DEFERRED - research background only; not executable at current
        effective regime sample size
STOP (no learned gating, no attention, no neural routing)
```

The following are explicitly excluded from the **current executable** program:

| Excluded | Why |
|---|---|
| L5: Sector panels | 104 stocks / 7 groups = 8–25 per group; insufficient sample for per-sector models. Revisit only if universe expands to 300+. |
| L6: Learned MoE gating | ~15 regime transitions in 5 years = insufficient training data for a gating network; documented expert collapse risk. |
| L7: Hierarchical MoE + attention | Zero production evidence at any scale. |
| L4: Regime-conditional weights | Deferred until a separate pre-registered feasibility/power study demonstrates enough non-overlapping state-specific labels. |

### 3.1bis Same-set controls (isolating combination method from expert-set changes)

The expert set is not held constant across the ladder: L1/L2 use only two
experts (XGB + PatchTST), while L3/L4 add a third (the per-ticker tournament,
once unfrozen — see §5.1). This is a confound. If L3 (3-expert linear
stacking) beats L2 (2-expert inverse-variance), that gain could be caused
entirely by **the added expert** — a genuinely useful third scorer would
improve almost any reasonable combination rule, including a naive one — and
not by anything about the **stacking method itself**. The ladder must not
interpret a two-model L2 result as evidence about a three-model L3, and it
must not credit the combination method for a gain that the expert-set change
alone would have produced.

To isolate the combination method's own contribution, **every level that
introduces a new expert must be compared against both**:

(a) the immediately preceding level (as already planned in §3.1), **and**
(b) a same-expert-set equal-weight control — i.e., before evaluating L3, first
    compute L1-style equal-weight averaging over the **same 3-expert set**,
    on identical prediction timestamps, universe, portfolio construction,
    costs, and outer folds.

Call this new, explicitly named control **L1-3E** (equal-weight on the
3-expert set). L1-3E's primary purpose in this design is as a control: it is
computed to give L3 (and, transitively, L4) a same-set baseline to beat,
isolating the combination method's own contribution from the expert-set
change. That control role does not preclude L1-3E from reaching production:
if no higher rung (L3, or L4) beats L1-3E at the 3-expert set, L1-3E — being
the best validated combination method at the current 3-expert set — is a
legitimate deployment candidate, exactly like any other ladder rung (see
§3.4, §5.3). L1-3E is not a permanent, independently-advancing rung the way
L1/L2/L3/L4 are (it only exists once a 3rd expert is available, and it is
computed specifically to be compared against L3), but whenever it wins that
comparison it can and does deploy — the same way L1 or L2 deploy when they
win theirs.

**L3's advance criterion (revised, see also §3.4)**: L3 (stacking, 3 experts)
must beat **both** L2 (its predecessor, 2 experts) **and** L1-3E (the same-set
control, 3 experts). If L3 beats L2 but not L1-3E, the correct inference is
that the gain is attributable to the added expert, not to the stacking
method — L3 **as a combination method is not validated**, even though the
expert addition itself may still be a valid, separately reportable finding
(e.g., it would support unfreezing the per-ticker tournament and feeding it
into L1/L2, not necessarily support building L3/L4).

### 3.2 Level 1 — Equal-weight average

**What:** For each ticker on each date, compute:

```
μ_ensemble = (1/K) × Σ μ_k
```

where μ_k is the score from model k. All available models contribute equally.

**Models included:** Start with XGB panel + PatchTST panel (the two we have
today). Add per-ticker tournament scores when unfrozen (Phase 1 prerequisite:
timeout fix 600→3600s, already verified to produce 0→114 candidates).

**Why start here:** Equal-weight is the strongest baseline in the forecast
combination literature. Stopping here if L1 fails to beat the frozen champion
is a **pre-committed resource-conservation stopping rule** — a deliberate
cost/effort decision — **not a proven statistical implication**. It is not
true in general that "if equal-weight loses, no fancier method will win":
heterogeneous, correlated forecast errors can in principle let a constrained
combiner (e.g. a covariance-aware minimum-variance weighting, or a
regularized stacking model) beat equal-weight even in cases where equal-weight
itself fails to beat the champion, because equal weighting is optimal only
under the special case of equal error variance and zero cross-correlation.
Stopping at an L1 failure remains an acceptable, **explicitly labeled cost
decision** — we are choosing not to spend the additional 5+ days of L2-L4
effort chasing a smaller and statistically harder-to-confirm edge — not a
claimed statistical necessity. If the operator wants the program to continue
past an L1 failure, that is a valid choice; this document's default is to
stop for cost reasons, not because it is provably hopeless.

**Implementation:** A scoring combination script that reads existing model
outputs (XGB panel scores + PatchTST panel scores from the daily inference
pipeline) and computes the simple average. No new model training. Estimated
effort: 1–2 days.

**Evaluation:** Nested walk-forward (§4) comparing ensemble vs frozen champion
(XGB alone) on IC, RankIC, net-of-cost simulated return, and Sharpe ratio.

### 3.3 Level 2 — Inverse-variance weighted

**What:** Weight each model by the inverse of its recent forecast error
variance, operating on the **causally-normalized scores** defined in §4.1bis
(not on raw model outputs):

```
w_k = (1 / σ²_k) / Σ (1 / σ²_j)
μ_ensemble = Σ w_k × μ_k
```

where σ²_k is model k's rolling forecast error variance over the trailing
window, and μ_k is the causally-normalized score from §4.1bis.

**Why this needs more care than the naive formula suggests:** Inverse-variance
weighting of **raw** forecast errors is not scale-invariant — different
models' raw errors can be on entirely different scales, which the causal
normalization in §4.1bis resolves by construction (this is why L2 is defined
to consume normalized, not raw, scores). Separately, the naive diagonal
formula above **ignores correlated residuals across models**: treating each
model's error variance independently (a diagonal, zero-cross-correlation
covariance matrix) is a special case that needs justification, not an
assumption baked in silently. Concretely, L2 must do all of the following:

(a) **Operate on normalized scores.** L2 consumes the causally-normalized,
    consistently-oriented scores from §4.1bis, never raw model outputs.

(b) **Justify or drop the independence assumption.** Either (i) test and
    report residual cross-correlation between models on **inner-fold data
    only**, and proceed with the diagonal (independent-variance) formula
    above only if that correlation is below a pre-registered threshold (e.g.
    |ρ| < 0.3, chosen before looking at outer-fold results), or (ii) if
    correlation exceeds the threshold, use a proper covariance-aware
    minimum-variance combination that accounts for the full error covariance
    matrix, not just its diagonal.

(c) **Shrink the covariance/variance estimate.** A raw sample covariance
    matrix is unstable at this scale (2-3 models, ~60-day trailing windows).
    Apply shrinkage toward a diagonal matrix (if using the covariance-aware
    variant) or toward equal weights (if using the diagonal variant), with the
    shrinkage intensity either fixed a priori or selected via **inner-fold**
    validation only — never via the same data used to compute the final
    deployed weights.

(d) **Fix the rolling-window update timing in advance.** The variance/
    covariance estimate used at each outer-test date must use only data
    strictly before that date (causal, no lookahead). The window length is
    fixed in advance at 60 trading days (matching this document's original
    proposal) and is not tuned per outer fold — tuning the window length per
    fold would itself be an undisclosed selection step.

**Implementation:** Same combination script, plus a rolling variance/
covariance computation on each model's residuals per (a)-(d) above. Estimated
effort: 1–1.5 days incremental on top of L1 (revised up from the original
0.5-day estimate to account for the covariance/shrinkage work).

**Evaluation:** Same nested WF as L1, additionally comparing L2 vs L1.

**Advance criterion:** L2 must beat L1 (equal-weight) OOS. If it doesn't, the
literature predicts this is likely — equal-weight is hard to beat — and we
deploy L1 instead. (This is the same pre-committed cost-stopping framing as
§3.2 — not a claim that a better-specified L2 could never win.)

### 3.4 Level 3 — Linear stacking

**What:** Train a linear regression meta-model:

```
μ_ensemble = β₀ + β₁·μ_XGB + β₂·μ_PatchTST + β₃·μ_ticker + ε
```

The meta-model learns the optimal linear combination of base model scores.
Critically: **linear only** — no trees, no neural networks, no interaction
terms. This is deliberate. A linear meta-model has minimal capacity to overfit
to the inner-fold data, which is the dominant risk at this sample size.

**Why linear, not nonlinear:** at our scale (104 stocks, 5 years, 3–5 base
models), a nonlinear meta-model has more capacity than the signal supports —
overfitting risk grows with meta-model flexibility while the effective inner-
fold sample size stays fixed, so a linear meta-model is the conservative
choice on overfitting-risk grounds alone. (An earlier version of this
document additionally cited QuantBench 2025, arXiv:2504.18600, as evidence
that "production quant systems deliberately use linear regression as
meta-model." QuantBench is a benchmark-platform paper; it does not make or
support that specific claim about industry practice, so the citation has been
removed. The linear-only choice here rests entirely on the overfitting-risk
argument above, which stands on its own without an appeal-to-authority
citation.)

**Implementation:** Requires the nested walk-forward harness (§4) — the
meta-model's coefficients must be fit on inner folds only, never touching
outer-fold test data. Estimated effort: 2–3 days (most of which is the harness,
reusable for L4).

**Evaluation:** Same nested WF, additionally comparing L3 vs L2 **and L3 vs
L1-3E** — the same-set equal-weight control defined in §3.1bis. Both
comparisons use identical prediction timestamps, universe, portfolio
construction, costs, and outer folds as L3 itself.

**Advance criterion (revised — see §3.1bis):** L3 must beat **both** L2 (its
predecessor) **and** L1-3E (the same-set, 3-expert equal-weight control) OOS.
If L3 beats L2 but not L1-3E, the gain is attributed to the newly added
per-ticker expert, not to the stacking method — L3 does not advance as a
combination method, and the ladder deploys L1-3E (equal-weight on the
3-expert set) instead of L2, pending a separate decision on whether the
expert addition itself is deployed. If L3 fails to beat L2 as well, deploy L2
(or L1).

### 3.5 Level 4 — Deferred research background, not a current candidate

**Status: DEFERRED.** The material in this section records why L4 was
considered and why its original grid was unsafe. It is not an implementation
plan, an experiment authorization, or a deployment branch for the current
104-stock/available-history setting. Reinstatement requires a separate design
PR with a state-specific effective-sample calculation, a fixed candidate set,
and an untouched confirmation period. Until then, a result of "L3 is best
among admissible current candidates" is final; no L4 test is run.

**What:** A fixed weight table indexed by HMM regime state:

```python
REGIME_WEIGHTS = {
    "BULL_CALM":     {"xgb": 0.45, "patchtst": 0.35, "ticker": 0.20},
    "BULL_VOLATILE": {"xgb": 0.30, "patchtst": 0.20, "ticker": 0.50},
    "BEAR":          {"xgb": 0.50, "patchtst": 0.35, "ticker": 0.15},
}
```

The weight values above are illustrative. The actual values are selected on
inner-fold data (§4.2) from a small, pre-specified candidate list per regime
— not a fine 0.05-increment grid — for the reasons given below.

**Inner-fold search space vs. outer hypothesis multiplicity (corrected —
Codex 3rd-round review, 2026-07-12).** With 3 experts and weights constrained
to 0.05 increments summing to 1.0, the number of distinct weight-simplex
points **per regime** is C(22,2) = 231 — not "~200" as an earlier version of
this document stated. If the three regimes' weight tables were selected
**jointly** as a single combinatorial search (rather than fit independently
per regime), that is 231³ ≈ 12.3 million joint three-regime weight-table
combinations, not "~200 × 3 ≈ 600."

These numbers describe the **size of L4's inner-fold search space** — this is
ordinary nested-CV hyperparameter/model selection, exactly analogous to
grid-searching any ML hyperparameter inside a single outer-fold's training
data. It does **not**, by itself, inflate the outer hypothesis count (§4.4),
because the search never touches outer-test data: every candidate is scored
only against inner-fold data, and only the single winning candidate per
outer-train window is ever carried forward to touch an outer-test window. A
prior revision of this document stated that this multiplicity "must be folded
into the same family-wise error accounting as the rest of the ladder
(§4.2/§4.4)." **That was a methodological error, corrected in this
revision:** conflating the size of an inner-fold selection space with the
outer hypothesis count both misstates what is being tested (a literal
12.3-million-way correction is neither meaningful nor intended) and would
make inference over the ladder needlessly impossible. §4.4's outer hypothesis
family is unaffected by the size of L4's inner grid — see §4.4 for the
corrected accounting.

To make this rigorous rather than merely asserted: **the entire L4 selection
algorithm — the candidate grid (redefined below), the causal HMM
specification, the occupancy rule (below), and the shrinkage rule — must be
fully specified and FROZEN before any outer-fold evaluation begins.** Within
each outer-train window, this frozen algorithm runs exactly once, entirely on
that window's inner-fold data (per §4.1's nested split), and produces a
single fitted L4 weight specification for that fold — exactly like fitting a
single model's hyperparameters via inner-CV and then evaluating only the one
resulting model once, on the outer holdout. The corollary: if, after seeing
outer-fold results, a different L4 algorithm *variant* is tried (a different
occupancy threshold, a different shrinkage scheme, a different candidate
grid, etc.), that new variant constitutes a **new outer hypothesis** — it
must either (a) be added to the pre-registered outer family (§4.4) with its
own correction budget from the start, or (b) be evaluated only on a
completely fresh, previously-untouched holdout split, since the original
outer-test data is "spent" the moment it informs a decision to try a new
variant.

The occupancy floor, shrinkage, and equal-weight fallback below remain
necessary safeguards — but their purpose is to control **inner-fold
overfitting/selection risk** (preventing the inner search from fitting noise
even though it never touches outer data), not to satisfy an outer-multiplicity
correction; this purpose distinction is stated explicitly wherever these
mechanisms recur (§4.2, §4.4).

**The proposed 60-trading-day floor does not support this fitting problem —
redefined in effective non-overlapping blocks, with a pre-registered
feasibility gate.** An earlier version of this document proposed a **60
trading day** floor before a regime's own weight-table entry could be
grid-searched. That is wrong: with `fwd_60d` labels, 60 raw trading days is
approximately **one overlapping label-horizon's worth of data** — as this
document's own §4.1 already establishes for the broader non-IID problem — not
60 independent observations. It cannot identify 231 per-state weight
candidates, a shrinkage intensity, and a causal HMM configuration
simultaneously. This is corrected as follows:

- **Occupancy eligibility, redefined in effective non-overlapping blocks.**
  Using the same non-overlapping-block concept already defined in §4.1 (block
  length ≥ the label horizon [60 trading days] plus the existing embargo
  gap), count how many such genuinely non-overlapping blocks fall within a
  given regime state's occupied days inside the inner-train window. A
  regime's own weight-table entry may be attempted only if that count meets a
  pre-registered minimum of **4 non-overlapping blocks** (chosen as roughly
  the smallest count that allows both a handful of training blocks and a
  held-out inner-inner validation block for the shrinkage step below — this
  is a judgment call, flagged explicitly, not a derived optimum). **Stated
  openly, not engineered to pass:** given this document's own "~15 regime
  transitions in 5 years" observation, most individual regime spells will be
  well under one full non-overlapping block's length, so most regimes in a
  typical 5-year sample will likely fail to clear even this small block-count
  minimum — this is an expected, disclosed consequence of the fitting
  problem's actual effective sample size, not a bar to be tuned until
  something passes.
- **A much smaller, coarser, explicitly enumerated candidate set — not a fine
  grid.** Given the effective sample size above, the fine 0.05-increment /
  231-point grid is replaced with a small, pre-specified candidate list per
  regime: **4 candidates** — the equal-weight vector (1/3, 1/3, 1/3), and one
  directional tilt toward each of the 3 experts (a {0.5, 0.3, 0.2} vector,
  rotated so each expert in turn is the one receiving 0.5). Four is
  deliberately close to the minimum needed to ask a meaningful question at
  all ("does tilting toward any one expert help, versus equal weight, in this
  regime") while adding as few free selection choices as the effective sample
  can support — this is not a de-tuned version of the original 231-point
  grid, it is a different, much smaller design chosen because the effective
  sample cannot support fine-grained search.
- **Regularization/shrinkage toward equal weights** (retained from the prior
  revision; purpose reframed above). Every fitted per-regime table must still
  be shrunk toward equal weights: the final per-regime weight is
  `shrinkage_intensity × grid_optimal + (1 - shrinkage_intensity) ×
  equal_weight`, with `shrinkage_intensity` chosen via **inner-inner**
  validation (a validation split within the inner-train window, held out from
  the grid search itself) — never via the same grid search that picked the
  raw optimum.
- **Equal-weight fallback** (retained). If a regime does not clear the
  occupancy minimum, or the shrinkage-adjusted table does not beat equal
  weight on a held-out inner-validation split, that regime uses L1 (or
  L1-3E, if the 3-expert set is in use) equal-weight instead of a custom
  per-regime table.
- **Causal regime classification** (retained from the prior revision). The
  HMM regime state used to index the weight table must be fit using only data
  available strictly before each prediction date within the outer-train
  window — no full-sample or smoothed HMM fit that uses future information to
  label past regimes (this restates/tightens the existing §4.2 causal-HMM
  control, applied explicitly to L4's own fitting, not just to regime
  *labels* used elsewhere).

**Pre-registered power/feasibility gate — checked before any inner-fold grid
search for L4 is attempted.** If a regime's state-specific effective
non-overlapping-block sample does not clear the pre-registered minimum above,
**L4 must be declared infeasible for this dataset** for that regime — a
valid, honest negative/inconclusive finding, not something to silently paper
over via regularization or a lower occupancy bar. If no regime clears the
minimum, the entire L4 rung is declared infeasible for this dataset, and the
ladder stops at L3 (or whichever level won) without ever running L4's inner
grid search for any regime. **This is the central evidence threshold for
rejecting learned MoE** (per PR #45's Phase 4 contingency, already rejected
for insufficient regime-transition data) — the static L4 alternative must be
held to the **same** evidentiary standard, not a lower one just because it is
the mechanically "simpler" of the two.

**Why static, not learned:** ~3 regime transitions per year × 5 years = ~15
training points for regime-conditional behavior. A learned gating network
would have far more parameters than training points. A fixed table selected
from the small candidate set on inner folds, subject to the
occupancy/shrinkage/fallback safeguards and the feasibility gate above (or
declared infeasible where that gate is not cleared), is the most that this
data can support.

**Literature support (narrowly qualified — see also §8):** RegimeFolio is a
**2025** preprint (arXiv:2510.14986; an earlier version of this document
incorrectly dated it 2024), and it uses a **VIX-based regime classifier with
dynamic mean-variance allocation** — not an HMM classifier with a static
per-regime weight table, as an earlier version of this document implied.
RegimeFolio therefore does **not** directly validate this design's specific
L4 mechanism (HMM classifier + static weight table); it is cited here only as
support for **regime-conditional ensembling as a general concept** — that
conditioning combination weights on a market-regime signal is a viable,
literature-supported idea. RegimeFolio's own specific mechanism (VIX
classifier + dynamic mean-variance) differs from this design's mechanism
(HMM classifier + static per-regime weight table), so this design's L4 choice
must stand on the occupancy/shrinkage/fallback safeguards and the feasibility
gate above, not on this citation.

**Future-only implementation note:** a future L4 proposal would need its own
research-runner design, feasibility/power calculation, and fresh confirmation
window. It has no current evaluation or advance criterion and cannot be used
to choose a deployed combination in this program.

---

## 4. Experiment protocol

### 4.1 Nested walk-forward

The standard single-model WF split (train → embargo → test) is insufficient
when a combination layer sits on top of base models. The combination layer's
weight selection is a **second fitting step** that can leak outer-fold
information if naively cross-validated.

```
Outer fold (never touched during any fitting):
  ├── Outer-train window
  │     ├── Inner-train: base model training + combination weight fitting
  │     ├── Inner-embargo: gap (same convention as existing WF gate)
  │     └── Inner-test: combination weight validation / selection
  ├── Outer-embargo: gap
  └── Outer-test: FINAL evaluation (H1 comparison only)
```

**Critical discipline:** The combination weights (L2 variance window, L3
coefficients, L4 regime-weight table) are fit/selected using ONLY inner-fold
data. The outer-test window is touched exactly once, for the final comparison.
No iteration, no "let me try different weights and see which works on the
outer fold."

**Per-window IC observations are not IID — this breaks a plain paired
t-test.** `fwd_60d` labels overlap heavily across adjacent prediction dates:
a prediction made on day *t* and one made on day *t+5* share roughly 55 of
their 60 label days. Successive per-window ICs within a fold are therefore
**strongly dependent**, not independent draws. A plain paired t-test on
per-window IC differences (as an earlier version of this document proposed)
assumes IID observations and will understate the true standard error,
inflating apparent significance. This must be addressed by one of the
following, decided **before** running any outer-fold evaluation:

(a) **Non-overlapping outer blocks (primary planned approach).** Define outer
    evaluation blocks with a minimum block length ≥ the label horizon (60
    trading days) **plus** the existing embargo gap, so that blocks used as
    independent units in the paired test do not share overlapping `fwd_60d`
    windows with each other. This is the primary planned approach. **Openly
    stated tradeoff:** this can reduce the effective number of independent
    outer observations substantially relative to a naive per-window count —
    e.g. 5 years of daily windows produces far fewer independent ~60+
    trading-day blocks than daily windows would suggest. This reduction in
    power is a real cost of doing the test validly and is disclosed here, not
    discovered after the fact.

(b) **Dependence-robust inference (fallback, used if (a) leaves too few
    blocks for meaningful power).** Use a moving-block or stationary
    bootstrap on the per-window IC differences (block length tied to the
    label-horizon autocorrelation, e.g. ≥60 trading days), or a
    Newey-West/HAC-adjusted standard error for the paired-difference test
    statistic, in place of the naive paired t-test's standard error.

(a) is the primary planned approach; (b) is the fallback if (a)'s block count
is too small for meaningful power. **This choice must be pre-registered
before running any outer-fold evaluation** — it is not to be chosen post-hoc
based on which procedure happens to produce a significant result for a given
level comparison.

### 4.1bis Defining the combined observable

Before any combination method (L1-L4) can be run, the following must be fixed
and documented — none of L1-L4 is well-defined without these:

- **Common, causal score normalization and orientation.** All base-model
  scores must be put on a common scale via a causal (no-lookahead)
  normalization — e.g. a cross-sectional z-score computed using only
  information available as of the prediction timestamp — and a consistent
  score **orientation** across models (all models' higher score = more
  bullish; a model that natively outputs "more bearish = higher" must be
  sign-flipped before combination, not silently combined as-is).
- **Exact as-of-timestamp discipline.** All base-model scores combined for a
  given date must all be generated using data available as of that same
  cutoff. No mixing models whose effective as-of times differ (e.g. one
  model's score computed from data as of market close and another's from a
  stale intraday snapshot) — that would silently reintroduce a lookahead or
  staleness asymmetry between experts.
- **Missing/stale-expert fallback policy (must be pick-one, not left open).**
  If one base model's score is missing or stale for a given ticker/date, this
  design specifies: **exclude that model from the combination for that
  specific observation, and re-normalize the remaining models' weights to sum
  to 1** (rather than dropping the whole observation). Dropping the whole
  observation would silently shrink the evaluation universe/date coverage in
  a way that could differ systematically across levels (e.g. if the newer
  per-ticker expert has more missingness than XGB/PatchTST, whole-observation
  dropping would bias L3/L4 toward an easier, more-liquid/more-complete
  subset than L1/L2 are evaluated on). Weight re-normalization keeps the
  evaluated universe identical across levels.
- **Immutable fingerprints for every base-model score snapshot** feeding a
  combination run. This repo already has a single canonical fingerprint
  implementation for exactly this kind of problem —
  `renquant_common.model_fingerprint.model_content_sha256` — adopted after a
  prior incident where independently hand-copied fingerprint implementations
  hashed different field sets and silently diverged. Every base-model score
  snapshot (and the resulting ensemble weights/spec) consumed by a
  combination run must be stamped with this canonical fingerprint, not a
  new ad hoc hash, so that a combination run's inputs are reproducible and
  auditable exactly like a single-model run's inputs already are.

L2 (§3.3) is specified to consume the causally-normalized, consistently-
oriented scores defined here, not raw model outputs — this is what resolves
L2's scale-invariance problem (§3.3(a)).

### 4.2 Leakage controls

| Leakage vector | Control |
|---|---|
| Base model sees outer-test data | Standard WF embargo (existing convention) |
| Combination weights see outer-test data | Nested inner/outer split (§4.1) |
| Weight selection grid-searched on outer data | Grid search on inner-test ONLY |
| Regime labels leak future | HMM regime state is computed using data strictly before the prediction date (online/causal HMM, no smoothing); same causality requirement applies to L4's own regime-conditional fitting (§3.5) |
| Per-window IC observations are not IID (`fwd_60d` overlap) | Non-overlapping outer blocks ≥ label horizon + embargo, or dependence-robust bootstrap/HAC inference (§4.1) — NOT a plain paired t-test |
| Expert-set change confounded with combination method (L2→L3 adds a 3rd expert) | Same-set equal-weight control L1-3E (§3.1bis); L3 must beat both L2 and L1-3E |
| Base-model score scale/orientation/staleness inconsistency | Causal normalization, consistent orientation, exact as-of discipline, missing-expert fallback, immutable fingerprints (§4.1bis) |
| Multiple comparisons across the full ladder, INCLUDING the data-adaptive level-by-level winner-selection step itself | See the full enumerated hypothesis family and correction procedure in §4.4 — this is materially larger than "3 comparisons." L4's inner grid (231-per-regime / 231³-joint, §3.5) is a separate, inner-fold-only selection problem and is NOT part of this outer accounting — see §4.4 for why. |
| L4's inner-fold candidate search treated as if it were outer hypothesis multiplicity | L4's selection algorithm (grid, causal HMM spec, occupancy rule, shrinkage rule) is frozen before outer evaluation and runs once per outer fold entirely on inner-fold data (§3.5); only the resulting single fitted spec per fold is ever compared against outer-test data (item 6 of §4.4's family) |
| L4 state-occupancy floor understates the fitting problem (60 raw days ≈ 1 overlapping label-horizon, not 60 independent observations) | Occupancy redefined in effective non-overlapping blocks (§4.1's block concept), small pre-specified candidate set, pre-registered feasibility gate — L4 declared infeasible for a regime (or the whole rung) if the gate is not cleared, held to the same evidentiary standard as rejected learned MoE (§3.5) |

### 4.3 Evaluation metrics

All metrics computed on outer-test windows only:

| Metric | Definition | Purpose |
|---|---|---|
| IC | Pearson correlation between predicted μ and realized fwd_60d return | Ranking accuracy |
| RankIC | Spearman rank correlation | Robust ranking accuracy |
| ICIR | IC / std(IC) across outer windows | Stability of ranking accuracy |
| Net return | Simulated portfolio return after transaction costs (existing sim infrastructure), under a FIXED score-to-portfolio mapping (§4.4) | Economic value |
| Sharpe ratio | Annualized net return / annualized volatility, same fixed mapping | Risk-adjusted return |
| Turnover | Monthly portfolio turnover rate, held fixed across compared levels (§4.4) | Cost of implementation |

### 4.4 Advance criteria (pre-registered)

**The complete hypothesis family (not "3 comparisons").** An earlier version
of this document stated the multiple-comparisons count as 3 (L1 vs champion,
best-L vs L1, best-L vs champion). That undercounts the ladder as actually
specified. The full, enumerated family is:

1. L1 vs frozen champion
2. L2 vs L1
3. L1-3E vs L2 (the same-set control comparison introduced in §3.1bis)
4. L3 vs L2
5. L3 vs L1-3E
6. Final declared candidate vs frozen champion

Beyond these six pairwise tests, **the ladder's own level-by-level winner
selection is itself a data-adaptive selection step** — choosing, after the
fact, "whichever level won" and reporting its comparison as if it were the
only test conducted inflates the effective family further, the same way
picking the best of several backtested models does (§2.2's winner's-curse
logic applies here too, one level up the stack).

**Historical note on L4's inner-fold grid (corrected — Codex
3rd-round review, 2026-07-12).** A prior revision of this document stated
that L4's 231-per-regime / 231³-joint candidate weight tables (§3.5) "must
also be folded into this same accounting, not treated as a separate,
uncounted search." **That was a methodological error, now corrected.** The
231/231³ figure describes the size of L4's inner-fold hyperparameter-
selection space — ordinary nested-CV model selection, per §3.5 — not an
additional set of outer hypotheses: the inner grid search never touches
outer-test data. Conflating the two
both misstates what is being tested and would make inference over this
ladder needlessly impossible (a literal 12.3-million-way correction is
neither meaningful nor intended). The outer family subject to correction is
exactly the six current items enumerated above. L4 is deferred by Section 0.2
and Section 4.5, so no L4 candidate is in the current outer family.

**Correction procedure — one of the following must be pre-registered before
running any outer-fold evaluation:**

(i) **Family-wise error correction (Holm-Bonferroni step-down).**
    Holm-Bonferroni step-down is preferred over flat Bonferroni because it is
    less conservative while remaining valid. Apply it across the **full**
    enumerated family above (the six current items),
    including a term for the level-selection step (e.g. by including the
    "final declared-winner vs champion" comparison in the family, which is
    where the selection step's effect ultimately surfaces). **OR:**

(ii) **Hierarchical/sequential gatekeeping (closed testing).** Since the
     ladder already stops at the first level that fails to beat its
     comparison(s), each gate may instead use a **fixed, pre-registered
     per-gate alpha** (e.g. α = 0.05 at every gate — not shrinking or
     relaxing at later gates). Under a hierarchical gatekeeping design, this
     controls the family-wise error rate for the **sequence** of gates,
     **provided each later test is only conducted after the earlier one
     passes** (a closed testing procedure). This precondition is stated
     explicitly here, not merely assumed: if a later gate were tested
     regardless of an earlier gate's outcome, the family-wise error guarantee
     would not hold.

State which of (i)/(ii) is used before running any outer-fold evaluation —
this is not to be chosen post-hoc based on which framework happens to pass a
given level.

**Per-comparison test.** For each pairwise comparison in the family above:

- **H0:** The candidate level's mean IC ≤ the comparison level's mean IC
  (one-sided).
- **H1:** The candidate level's mean IC > the comparison level's mean IC.
- **Test:** the dependence-robust procedure from §4.1 (non-overlapping
  outer blocks, or moving-block/stationary bootstrap / HAC-adjusted paired
  test) — never a plain paired t-test on per-window IC.
- **Minimum effect size:** ΔIC ≥ 0.005 (below this, the improvement is not
  economically meaningful given our transaction cost regime). This threshold
  is **necessary but not sufficient** — see the costed decision-level
  requirement below.

**Costed, decision-level outcome — required co-primary pass condition.**
ΔIC alone is not an economic effect size without a fixed score-to-portfolio
mapping, turnover treatment, and risk constraint. In addition to the
ΔIC≥0.005 / statistical-significance test above, every level comparison also
requires a costed, decision-level outcome:

- Net-of-transaction-cost realized Sharpe ratio and/or return, computed under
  a **fixed** score-to-portfolio mapping — the same position-sizing/top-N
  selection convention already used elsewhere in this codebase for the
  frozen champion. This mapping is **not re-optimized per level**: every
  level in the ladder is passed through the identical portfolio-construction
  convention, so that a change in decision-level outcome can be attributed to
  the combination method, not to a different, level-specific portfolio
  construction.
- Turnover and a concentration/risk constraint are held **fixed** (not
  re-optimized per level) across all levels being compared, for the same
  reason.

A level advances only if it clears **both** the statistical test (per the
chosen (i)/(ii) correction, ΔIC ≥ 0.005) **and** the costed, decision-level
condition above. A level that only clears the IC-based test but shows no
costed, decision-level improvement under the fixed mapping does not advance —
ΔIC alone is not sufficient economic evidence.

A level that clears both conditions relative to every required comparison in
its row of the hypothesis-family table above advances only to the confirmation
stage in Section 4.5. It does not deploy directly from walk-forward results.

### 4.5 Binding evidence protocol: discovery is not confirmation

The earlier ladder is a candidate-generation mechanism. This section replaces
any reading of walk-forward success as deployment evidence.

#### A. Freeze the research universe before results

Before the first discovery run, create an immutable experiment manifest that
lists every considered expert, expert set, score normalization, missing-score
rule, covariance/window rule, portfolio mapping, rebalance cadence, cost
assumption, risk constraint, test, and stopping rule. The manifest must also
record rejected candidates and failed runs. A variation not in the manifest is
an exploratory follow-up, not confirmation evidence.

The forecast horizon and trade cadence must be coherent. A 60-trading-day
label does not license daily independent re-optimization: the experiment must
declare the holding/rebalance schedule and purge/embargo implied by the actual
label interval. The same schedule is used for champion and candidate.

#### B. Use three chronological evidence stages

1. **Discovery:** nested, purged walk-forward may compare the small
   pre-registered L1/L2/L3 set and select at most one candidate. Its purpose
   is rejection and candidate selection, not a live claim.
2. **Confirmation:** a final chronological holdout, embargoed from discovery,
   remains unread until the full candidate specification and portfolio mapping
   are frozen. Evaluate exactly one selected candidate against the champion.
   No re-ranking experts, choosing a new cost model, changing the test, or
   adding a regime variant is permitted after this window is opened.
3. **Operational shadow:** only a confirmed candidate may run DARK through the
   model -> pipeline -> orchestrator path. The run must create fingerprints,
   decision traces, portfolio deltas, and an immutable run bundle. It changes
   no live orders. A separate reviewed authorization is required before any
   production behavior can change.

If the confirmation holdout has already been inspected for any ensemble
decision, it is spent. Reserve a later chronological window or report that
there is no independent confirmation evidence.

#### C. Define a trading pass before observing confirmation data

IC and RankIC are diagnostics; neither is a primary economic pass condition.
The confirmation report must include block-bootstrap or other dependence-aware
uncertainty for all of the following, under identical executable constraints:

- incremental net return and risk-adjusted return versus champion;
- incremental turnover, estimated costs, and net return per unit of turnover;
- concentration, drawdown, gross/net exposure, and liquidity-cap compliance;
- trade-list overlap and action delta, so a claimed gain cannot come from a
  silent change in coverage or an unexamined handful of names;
- base-cost and pre-registered adverse-cost scenarios, including at least a
  2x cost stress and a reduced-liquidity/participation stress.

A candidate passes only when the pre-registered, dependence-aware lower
confidence bound for its incremental **net** outcome is positive in the base
case, it does not fail the adverse-cost scenario, and no fixed risk or
operational constraint is breached. The exact confidence level, bootstrap
scheme, minimum economically material net effect, and risk tolerances must be
in the manifest before discovery. A positive point estimate, a Sharpe ratio
without selection adjustment, or DeltaIC >= 0.005 alone is not a pass.

Because selection has occurred across experts and combination rules, the
discovery report must additionally report a data-snooping adjustment over the
recorded candidate universe, such as a White Reality Check / SPA-style
bootstrap or a deflated-Sharpe analysis with the effective number of trials.
That adjustment is a diagnostic on research credibility; it does not convert
an already-inspected holdout into independent confirmation.

#### D. Explicit non-results

The protocol has three successful scientific outcomes: (1) no admissible
incremental expert, (2) no candidate survives confirmation, or (3) one
candidate earns a DARK operational trial. Outcomes (1) and (2) are valuable
because they prevent a false production promotion. There is no requirement to
advance the ladder or use the third expert merely because it is available.

---

## 5. What we need before running experiments

### 5.1 Prerequisites

| Prerequisite | Status | Blocking? |
|---|---|---|
| Stage 0 point-in-time forecast/admissibility ledger | Not built | Blocks every ensemble comparison |
| Immutable experiment manifest and unread final confirmation window | Not built | Blocks every ensemble comparison |
| XGB panel scorer producing daily scores | Live (primary) | No |
| PatchTST point-in-time score ledger with parity evidence | Unknown | Blocks its admission as an expert |
| Per-ticker tournament unfrozen and point-in-time ledgered | Blocked on timeout fix | Blocks L1-3E/L3 |
| Nested WF + purging harness | Not built | Blocks discovery |
| Execution-calibrated cost/liquidity scenarios | Unknown | Blocks confirmation |

### 5.2 Experiment phases

| Phase | Scope | Prerequisites | Est. effort | Deliverable |
|---|---|---|---|---|
| **Phase 0** | Build the admissibility ledger, cost scenarios, manifest, and unread confirmation split | Point-in-time scores and artifacts | Not estimated until data audit | Signed research manifest or a documented block |
| **Phase A** | Discovery only: compare the smallest admitted L1/L2 set; L3 only after its third expert passes Stage 0 | Phase 0 + purged nested WF | Not estimated until Phase 0 | One selected candidate or a negative result, with all trials logged |
| **Phase B** | One-candidate chronological confirmation under the frozen executable policy | Phase A selection + untouched holdout | Not estimated | Confirmed, rejected, or inconclusive result |
| **Phase C** | DARK operational shadow and run-bundle parity | Phase B pass | Not estimated | Evidence for a separate production-authorization PR |

### 5.3 Go/no-go decision tree

```
Phase 0: ledger, manifest, costs, and unread confirmation window
  ├── any prerequisite fails -> report BLOCKED; champion unchanged
  └── all pass -> Phase A: discovery on the recorded candidate universe
                    ├── no candidate survives -> report NEGATIVE; champion unchanged
                    └── one candidate selected -> Phase B: one-time chronological confirmation
                                                 ├── fails/inconclusive -> report result; champion unchanged
                                                 └── passes -> Phase C: DARK operational shadow
                                                               ├── parity/operability fails -> champion unchanged
                                                               └── passes -> separate authorization review;
                                                                            no automatic production promotion
```

All comparisons above are subject to the manifest, selection-adjustment,
confirmation, and operational-shadow requirements in §4.5 -- not IC alone.

At every node, the decision is binary and pre-registered. No "let's try one
more thing" after a negative result.

---

## 6. What this design explicitly does NOT include

| Excluded | Rationale |
|---|---|
| Sector panel models | Insufficient sample (8–25 stocks per group). Revisit if universe grows to 300+. |
| Learned gating network | ~15 regime transitions in training data; documented expert collapse risk. |
| Attention-based cross-reference | Zero production evidence. |
| Hard routing (per-ticker model selection) | Not a current candidate: the available effective sample cannot support its per-ticker selection burden. This is not a universal impossibility claim. |
| Nonlinear meta-model | Overfitting risk at our scale (104 stocks, 3-5 base models) — see §3.4 for the full argument. (An earlier version of this row also cited QuantBench 2025 as evidence that production systems deliberately use linear meta-models; that citation has been removed — QuantBench is a benchmark-platform paper and does not support that claim. The exclusion rests on the overfitting-risk argument alone.) |

These exclusions are **not permanent** — they are scoped to this experiment
program. If the universe expands, if more data accumulates, or if a specific
paper demonstrates transferability to our setting, any of these can be
reopened with a new design doc and its own pre-registered hypothesis.

---

## 7. Relationship to prior design (model PR #45)

The multi-panel ensemble architecture memo (model PR #45, merged) proposed a
more ambitious 4-phase program including sector panels, cross-reference
attention, and learned gating. This document **supersedes the combination
method** in that design:

| PR #45 proposed | This document |
|---|---|
| Sector panels (Phase 2) | Excluded — insufficient sample at 104 stocks |
| Fixed regime weights (Phase 2) | Deferred from the current program; current effective regime evidence is insufficient for state-specific fitting |
| Cross-reference attention (Phase 3) | Excluded — zero production evidence |
| Learned gating (Phase 4, contingent) | Excluded — insufficient regime transitions for training |

The model-building vision (per-ticker experts, multiple panel scorers) from
PR #45 remains valid — the change is in how their outputs are combined.
PR #45's experiment protocol (nested WF, leakage controls, pre-registered
metrics) is adopted here with minor refinements.

---

## 8. References

### Primary (combination method)

| Ref | Paper | Year | Key finding |
|---|---|---|---|
| [T06] | Timmermann, "Forecast Combinations" | 2006 | Broad review supporting combination as a hypothesis class; not proof of net trading benefit in this system |
| [SW09] | Smith & Wallis, "A Simple Explanation of the Forecast Combination Puzzle" | 2009 | Selection amplifies estimation error; combination averages it out |
| [FC22] | Wang et al., "Forecast Combinations: An Over 50-Year Review" | 2022 | arXiv:2205.04216. Equal weights surprisingly hard to beat OOS. **Plausibility, not transferability**: this review supports *testing* equal-weight and more complex combinations as a well-established empirical prior across many domains — it does not itself prove that the specific proposed L1-L4 ladder will outperform in this trading pipeline's specific 104-stock universe, turnover, and cost regime. Matches the "plausibility, not transferability" framing used for the literature review in the companion multi-panel design (model PR #45, §1). |
| [GKX20] | Gu, Kelly & Xiu, "Empirical Asset Pricing via Machine Learning" | 2020 | RFS. Ensemble average > any single best model on 30k equities |
| [C16] | Claeskens et al., "The Forecast Combination Puzzle" | 2016 | Model selection OOS systematically worse than model averaging |

### Research-integrity and confirmation references

| Ref | Paper | Year | How it constrains this protocol |
|---|---|---|---|
| [WRC00] | White, "A Reality Check for Data Snooping" | 2000 | Tests a selected rule against a benchmark while accounting for a recorded universe of alternatives; motivates the discovery-universe ledger and bootstrap diagnostic in Section 4.5. |
| [DSR14] | Bailey & Lopez de Prado, "The Deflated Sharpe Ratio" | 2014 | Adjusts Sharpe-ratio interpretation for selection bias, non-normality, and multiple trials; diagnostic evidence, not a substitute for an untouched confirmation holdout. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551 |
| [CPCV18] | Lopez de Prado, "Advances in Financial Machine Learning", Ch. 12 | 2018 | Motivates purging and embargoing labels with overlapping information; this protocol still retains chronological confirmation because CPCV-like resampling cannot create an unread historical future. |
| [SB14] | Pesaran & Pick, "Forecast Combinations under Structural Break Uncertainty" | 2014 | Shows the bias-variance tradeoff around break uncertainty; supports treating regime adaptation as a conditional hypothesis rather than a default upgrade. https://doi.org/10.1016/j.ijforecast.2013.06.003 |
| [HFC23] | Athey et al., "Hedging Forecast Combinations" | 2023 | States that covariance-aware combination depends on estimated forecast-error moments, reinforcing that MSE-optimal weights are not automatic trading-optimal weights. https://arxiv.org/abs/2308.15384 |

### Supporting (architecture and failure modes)

| Ref | Paper | Year | Key finding |
|---|---|---|---|
| [RF25] | RegimeFolio, "Regime Aware Sectoral Portfolio Optimization" | 2025 (corrected — an earlier version of this document said 2024) | arXiv:2510.14986. Uses a **VIX-based regime classifier with dynamic mean-variance allocation** (corrected — an earlier version of this document said "HMM classifier, static weights," which is not what this paper does), Sharpe 1.17, 34 US large-caps. Cited here only as support for regime-conditional ensembling as a *general concept*; it does not validate this design's specific HMM-classifier + static-weight-table L4 mechanism (§3.5). |
| [QB25] | QuantBench, "Benchmarking AI for Quant Investment" | 2025 | arXiv:2504.18600. A benchmark-platform paper — it does **not** claim or support that production systems deliberately use linear regression as a meta-model (corrected — an earlier version of this document made that claim citing this paper; the claim has been removed from §3.4, whose linear-only choice now rests solely on the overfitting-risk argument). |
| [MoE25] | MoE Comprehensive Survey | 2025 | arXiv:2503.07137. Expert collapse, representational collapse, load imbalance |
| [AF24] | AlphaForge, "Mine and Dynamically Combine Formulaic Alphas" | 2024 | AAAI 2025. Dynamic temporal weighting > fixed weights |
| [CFA25] | CFA Institute, "Ensemble Learning in Investment" | 2025 | Industry-standard recognition of ensemble ML in practice |

### Open-source references

| Framework | Repo | Relevance |
|---|---|---|
| MarketRegimeNet | github.com/lu8848/MarketRegimeNet | Closest runnable analog: 4-model regime-aware ensemble + WF + Alpha158 |
| Qlib | github.com/microsoft/qlib | Production-grade quant ML infra; DoubleEnsemble, Alpha158 |
| RD-Agent | github.com/microsoft/rd-agent | Automated factor+model co-optimization (NeurIPS 2025) |

### Papers from prior design (model PR #45, combination method superseded)

| Ref | Paper | Year | Status in this design |
|---|---|---|---|
| MIGA | arXiv:2410.02241 | 2024 | Excluded (learned MoE, CSI300 only, no code) |
| AlphaMix | arXiv:2207.07578 | 2022 | Excluded (two-stage MoE, no official code) |
| PPFM | arXiv:2507.16433 | 2025 | Excluded (cross-sector transfer, insufficient sample at 104) |
| AlphaCrafter | arXiv:2605.05580 | 2025 | Excluded (LLM-agent-based, different paradigm) |
| Two-Level Uncertainty | arXiv:2603.13252 | 2025 | Position-level uncertainty cap concept retained as optional future add-on if L1–L4 demonstrates ensemble disagreement is informative |
