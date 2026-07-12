# Multi-Panel Ensemble Architecture: Literature Survey and Falsifiable Hypotheses

**Date:** 2026-07-12
**Origin:** Operator request — "我们可以搞多个板块的panel模型+大panel+ticker，
多搞出来一些，然后互相参考，我相信学术界和工业界有类似的架构！"
**Status:** Research memo — literature survey + falsifiable hypotheses.
Not an implementation RFC; no code or behavioral change.
**Scope:** Academic/industry survey + candidate architecture for RenQuant-104

---

## 1. Bottom line

The operator's vision — sector panels + large cross-sectional panel + per-ticker
models, cross-referencing and regime-conditional — has plausible academic support
from five papers (2022–2025) and is conceptually consistent with scaled
industrial practice (WorldQuant/Two Sigma). However, **plausibility in published
literature does not establish transferability** to our 104-stock universe, cost
regime, or turnover constraints. Those papers were validated on CSI300/500/1000
(300–1000 A-shares), Russell 3000, or a 4-month live window on non-overlapping
strategies — none of them is this universe, this label, or this cost regime.

Whether multi-panel architectures beat the frozen champion (current XGB panel),
a simple risk-abstention baseline, and a soft equal-weight mixture is an open
empirical question to be settled by staged, out-of-sample experiments against
three pre-registered, falsifiable hypotheses (§6) — not by the survey below.
The literature review's job is to establish that the architecture is worth the
cost of running those experiments, nothing more.

Candidate architecture: **Hierarchical MoE with Regime-Conditional Gating** —
three prediction levels (per-ticker, sector-panel, cross-sectional panel) whose
outputs are combined by a gating function conditioned on HMM regime state and
sector membership. Each phase advances only if the prior phase demonstrates a
validated OOS edge under the criteria in §6; the program is explicitly allowed
to end early with a negative result (§7).

---

## 2. Academic foundations

### 2.1 MIGA — Mixture-of-Experts with Group Aggregation (2024)

**Source:** Li et al., "MIGA: Mixture-of-Experts with Group Aggregation for
Stock Market Prediction," [arXiv:2410.02241](https://arxiv.org/abs/2410.02241)
(Oct 2024).

**Architecture:**
- 63 experts organized into 7 groups of 9 experts each
- Router encodes cross-sectional stock features → Top-K (K=8) expert selection
  via softmax
- **Group Aggregation:** within each group, expert outputs are concatenated and
  processed through multi-head self-attention — experts within the same group
  share information and collaborate
- Style-based routing: stocks with similar characteristics (momentum/value/size)
  route to the same expert cluster

**Training:**
- Expert loss = IC (information coefficient) instead of MSE — directly
  optimizes ranking quality
- Router loss = load-balancing term to prevent expert collapse
- Combined: L = α·L_Router + β·L_Expert (α=2e-3, β=1)

**Results (CSI300 long-only):**
- IC=0.052, ICIR=0.265, RankIC=0.079, RankICIR=0.365
- 24% excess annual return (AR), IR=1.80
- +33% AR improvement over prior SOTA (ModernTCN: 18%)

**Plausibility for our system:** MIGA's "style groups" are structurally
analogous to sector panels. The group aggregation mechanism (attention between
experts in the same group) suggests a cross-reference path (§4.4). However:
MIGA operates on CSI300/500/1000 (300–1000 stocks), not 104; the style grouping
is learned, not GICS-imposed; and the results are on Chinese A-shares, a
different microstructure. Whether the architecture's advantage transfers to
our universe is an empirical question, not implied by these results.

### 2.2 PPFM — Projection-Penalized Factor Model (2025)

**Source:** Fan, Wu, Yang, "Adaptive Multi-task Learning for Multi-sector
Portfolio Optimization,"
[arXiv:2507.16433](https://arxiv.org/abs/2507.16433) (Jul 2025).

**Architecture:**
- Each sector m has its own factor model: R_m = B_m · F_m + ε
- Cross-sector transfer via projection penalty:
  L = Σ(prediction errors) + (λ/T) · Σ‖P^(m) − P^(m')‖²_F
  where P = projection matrix of the factor space
- λ controls information sharing intensity: λ=0 → independent sectors;
  λ→∞ → identical factors (pooled)
- Algorithm converges within ~10 iterations

**Key insight:** The penalty is data-adaptive. Sectors that share similar latent
factors (e.g. tech and semiconductors) naturally transfer more information.
Heterogeneous sectors (e.g. utilities vs biotech) remain approximately
independent. This is the theoretical basis for letting an undersized sector
group borrow strength from related sectors rather than being trained (or
excluded) in isolation — see §6.4's sample/support requirement.

**Results:** Superior aggregated Sharpe ratios on Russell 3000 multi-sector
portfolios vs both independent and pooled approaches.

**Plausibility for our system:** PPFM addresses the small-sector sample size
problem — a sector with 5–15 stocks can borrow strength from related sectors
via adaptive regularization. The Russell 3000 context is closer to US equities
than CSI. However, our 104-stock universe is much smaller than Russell 3000;
whether the cross-sector transfer adds value at this scale is unknown.

### 2.3 AlphaMix — Uncertainty-Aware Trading Experts (2022)

**Source:** Cong et al., "Quantitative Stock Investment by Routing
Uncertainty-Aware Trading Experts: A Multi-Task Learning Approach,"
[arXiv:2207.07578](https://arxiv.org/abs/2207.07578) (Jul 2022).

**Architecture:**
- **Stage 1:** Train multiple independent trading experts with individual
  uncertainty-aware loss functions. Each expert specializes on a subset of
  market conditions.
- **Stage 2:** Train neural routers that dynamically deploy experts on an
  as-needed basis — the router acts as a portfolio manager selecting which
  expert(s) to trust for each stock at each time step.

**Key insight:** Two-stage training prevents expert collapse — experts trained
independently first develop genuine specialization, then the router learns to
select among them.

**Plausibility for our system:** Our current system already has independently
trained models (XGB panel, PatchTST panel, per-ticker tournament). AlphaMix's
architecture suggests treating these as pre-trained experts and learning a
routing layer on top could be viable, rather than retraining everything jointly.
Whether the routing layer adds value over simple equal-weighting (H3, §6.1) is
the central empirical question.

### 2.4 AlphaCrafter — Multi-Agent Cross-Sectional Trading (2025)

**Source:** "AlphaCrafter: A Full-Stack Multi-Agent Framework for Cross-Sectional
Quantitative Trading,"
[arXiv:2605.05580](https://arxiv.org/abs/2605.05580) (May 2025).

**Architecture (three agents):**
1. **Miner:** Continuously expands factor library, validates via IC and stability
2. **Screener:** Assesses market regime → constructs regime-conditioned factor
   ensembles with dynamic weights and directional biases
3. **Trader:** Translates ensemble into executable strategy under risk constraints

**Regime-aware ensemble:**
- Evaluates trend direction, volatility, correlation structure
- Ranks factors by regime-conditional suitability scores
- Assigns directional weights (w_f, d_f) based on regime compatibility
- "Dynamically reweights information sources without retraining"

**Results:** 18.27% AR / 1.53 Sharpe (CSI300), maintained positive returns in
live trading (2026.01–04) — most baselines went negative live despite positive
backtests.

**Plausibility for our system:** The Screener's regime-conditional reweighting
is structurally similar to what our HMM regime state could drive. However:
AlphaCrafter uses LLM-based agents (GPT/Claude/Gemini), not traditional ML
scorers; and its live trading period (4 months) is short. Whether regime-
conditional reweighting works with our HMM and XGB/PatchTST stack is untested.

### 2.5 Two-Level Uncertainty for Safe Deployment (2025)

**Source:** "When Alpha Breaks: Two-Level Uncertainty for Safe Deployment of
Cross-Sectional Stock Rankers,"
[arXiv:2603.13252](https://arxiv.org/abs/2603.13252) (Mar 2025).

**Architecture (two levels):**
1. **Strategy-level regime gate:** Monitors distributional shift → decides
   whether the ranking model remains reliable in current conditions. If
   regime-trust < threshold → halt trading entirely.
2. **Position-level epistemic cap:** Uses ensemble disagreement to quantify
   per-stock prediction confidence → high-uncertainty predictions receive lower
   weights or are excluded.

**Key insight:** Separation of concerns — the regime gate answers "should we
trade at all?" while the position cap answers "how much should we trust this
specific recommendation?"

**Plausibility for our system:** This maps to the F4 Option A concept (regime-
conditional model serving, §8). The strategy-level gate ≈ HMM regime detection
→ demote the primary in failing regimes. The position cap ≈ per-stock
uncertainty from ensemble disagreement between panel and per-ticker models.
Whether our HMM confidence signal is informative enough to drive a useful
regime gate is unestablished, and the position cap specifically requires a
calibration check before it is trusted as a sizing input (§6.5).

### 2.6 Industry practice: WorldQuant / Two Sigma

**Architecture (public disclosures):**
- WorldQuant deploys ~4 million individual alpha signals. Each is an independent
  predictive rule. A separate portfolio construction team combines signals into
  models, multiple models into funds.
- Signals are evaluated against the entire deployed alpha population's
  correlation structure
- **Regime stability tests**: production signals must demonstrate consistent
  performance across multiple distinct market regimes
- Two Sigma: comparably large signal library built over 20 years; edge comes
  from combining weakly predictive signals whose errors are uncorrelated

**Plausibility for our system:** The architectural principle — no single model
trades in isolation; ensemble + regime conditioning — is shared. However, the
scale difference (2–3 models vs 4M signals) is extreme; whether the benefits of
ensemble architecture survive at our scale is not implied by the industrial
analogy.

---

## 3. Our current system (as-built)

| Component | Status | Strength | Weakness |
|---|---|---|---|
| XGB panel scorer | Primary (re-promoted 06-23) | Gate-passing WF stamp, tabular SOTA | Compressed mu range, no sequence modeling |
| PatchTST panel scorer | Shadow (demoted) | Distributional σ head, sequence modeling | 1 retrain, 2/3 WF cuts unexecutable |
| Per-ticker tournament | Frozen since April | Captures idiosyncratic patterns | 600s timeout → 0 candidates; stale |
| HMM regime detector | Active (3-state) | BULL_CALM/BULL_VOLATILE/BEAR | Binary-ish confidence; no per-model trust |
| Ensemble | SHELVED (06-12) | Measured IC improvement in dead windows | Never implemented; no gating |

**Observed gap:** All models see the same cross-sectional feature set with no
sector specialization. The XGB panel treats AAPL and XOM as interchangeable
feature vectors. Whether sector-specific dynamics (tech momentum clustering,
energy macro sensitivity, healthcare regulatory events) are material enough to
justify sector-specialized models is an empirical question, not an
architectural given.

---

## 4. Candidate architecture

### 4.1 Overview: Hierarchical MoE with Regime-Conditional Gating

```
                    ┌─────────────────────┐
                    │   Regime Router     │ ← HMM state + volatility
                    │   (gating network)  │
                    └──────┬──────────────┘
                           │ weights w_r(regime, sector)
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     ┌────────────┐ ┌───────────┐ ┌──────────┐
     │ Level 3    │ │ Level 2   │ │ Level 1  │
     │ Large Panel│ │ Sector    │ │ Per-Ticker│
     │ (XGB/PTST)│ │ Panels    │ │ Experts  │
     └────────────┘ └───────────┘ └──────────┘
           │              │             │
           └──────────────┼─────────────┘
                          ▼
                 ┌─────────────────┐
                 │ Position-Level  │ ← ensemble disagreement
                 │ Uncertainty Cap │
                 └────────┬────────┘
                          ▼
                    Final Score μ̂
```

**Three prediction levels:**

**Level 1 — Per-Ticker Experts:**
- Existing per-ticker tournament models (once unfrozen)
- Each ticker has its own specialized model
- Captures: idiosyncratic mean-reversion, earnings patterns, stock-specific
  momentum signatures
- Input: ticker-specific features (price history, volume, fundamentals)

**Level 2 — Sector Panel Models:**
- NEW: sector-grouped panel models (5–7 sector groups)
- Grouping by GICS sector with a minimum support threshold below which a group
  defers to Level 3 instead of getting its own model (§6.4)
- Training: shared feature encoder (alpha158 base) + sector-specific prediction
  heads (per MIGA architecture)
- Cross-sector regularization via PPFM penalty (sectors with similar factor
  spaces share more information)
- Captures: within-sector relative value, sector-specific factor loadings,
  industry momentum clustering

**Level 3 — Large Cross-Sectional Panel:**
- Existing XGB and PatchTST panel scorers
- Sees all 104 stocks simultaneously
- Captures: broad cross-sectional patterns, market-wide factor premia,
  inter-sector rotation signals

### 4.2 Regime-Conditional Gating

The gating function outputs weights w = (w₁, w₂, w₃) for the three levels,
conditioned on:
- HMM regime state (one-hot: BULL_CALM, BULL_VOLATILE, BEAR)
- Regime confidence (HMM posterior probability)
- Rolling volatility and correlation features
- Sector membership of the target stock

**Regime-specific behavior (hypothesized, to be tested — not implemented in
Phase 1/2, see §6.1's H1 definition):**

| Regime | Large Panel | Sector Panel | Per-Ticker | Rationale (hypothesis) |
|---|---|---|---|---|
| BULL_CALM | High | High | Low | Cross-sectional patterns stable; sector rotation active |
| BULL_VOLATILE | Medium | Low | High | Dispersion high; idiosyncratic signals dominate |
| BEAR | High (defensive) | Medium | Low | Flight-to-quality is cross-sectional; sector rotation |

### 4.3 Position-Level Uncertainty (per arXiv:2603.13252)

After the gated ensemble produces μ̂ for each stock:
- Compute ensemble disagreement = std(Level1_score, Level2_score, Level3_score)
- If disagreement > threshold → reduce position weight or exclude from buy list
- If all three levels agree → high-conviction position
- This would replace the current binary VetoWeakBuys with a continuous
  confidence measure — **contingent on the calibration check in §6.5 passing**;
  the mechanism is not assumed to be informative just because the referenced
  paper found it useful in a different setting.

### 4.4 Cross-Reference Mechanism (per MIGA Group Aggregation)

Within sector groups, use attention-based cross-reference:
- Sector panel scores for all stocks in a sector are concatenated
- Multi-head self-attention produces refined scores that account for
  within-sector relationships
- Example: if AAPL scores high but MSFT/GOOGL score low in the same tech group,
  the attention mechanism can flag AAPL as an outlier (potentially contrarian
  opportunity or data anomaly)

Between levels, use residual connections:
- Level 2 (sector) receives Level 3 (large panel) scores as additional input
- Level 1 (per-ticker) receives both Level 2 and Level 3 scores
- Each level's output = its own prediction + learned residual from higher levels
- This prevents lower levels from contradicting the cross-sectional picture
  without strong evidence

This mechanism is Phase 3 scope (§7) — it is described here as part of the
candidate architecture, not as something Phase 1/2 implements or that H1 tests.

---

## 5. Practical constraints and design choices

### 5.1 Sample size problem

With 104 stocks across ~11 GICS sectors, the smallest sectors (Real Estate,
Utilities, Materials) may have 3–5 stocks. Options:

| Approach | Pros | Cons |
|---|---|---|
| **A. Merge small sectors** (5–7 groups of 10–20) | Sufficient samples; simple | Loses sector granularity for merged groups |
| **B. PPFM regularization** (11 sectors, penalized) | Preserves all sectors; data-adaptive | More complex; λ tuning |
| **C. Multi-head single model** (shared encoder + sector heads) | Parameter-efficient; one training run | Sector heads may not fully specialize |
| **D. Sector embedding** (sector as a feature, not a model split) | No sample split; continuous | Not truly separate sector models |

**Recommendation:** Start with A (merged groups), graduate to C (multi-head)
after proving the concept. PPFM (B) is the eventual target for cross-sector
regularization but adds significant complexity. This recommendation is a
starting point for Phase 2 implementation, not itself validated — §6.1's H1
tests exactly this simplest variant (A) against the frozen champion.

Proposed grouping (merge to ~7 groups):
1. Tech + Communication Services (~25 stocks)
2. Healthcare (~15 stocks)
3. Financials (~15 stocks)
4. Consumer Discretionary (~12 stocks)
5. Industrials (~15 stocks)
6. Consumer Staples (~8 stocks)
7. Energy + Materials + Utilities + Real Estate (~14 stocks)

### 5.2 Model architecture for sector panels

Given our XGB-primary stack, sector panels should also be tree-based (not
neural) to maintain interpretability and infrastructure compatibility.

**Option: XGB with sector-specific training sets + shared hyperparameters**
- Train one XGB per sector group on the sector's stocks only
- Share hyperparameter search results across sectors (but allow per-sector
  tuning within bounds, subject to the inner-fold discipline in §6.2)
- Feature set: same alpha158 base, but sector panels can add sector-specific
  features (e.g., oil price for energy, yield curve for financials) — any
  such addition is itself an inner-fold hyperparameter decision, not something
  chosen by looking at outer-fold performance
- Prediction target: same fwd_60d label as the frozen champion (§6.3)
- Walk-forward validation: same nested 3-cut protocol per sector (§6.2), with
  smaller cuts due to fewer stocks

**Concern:** XGB on 10–20 stocks × ~250 trading days × 5 years = 12,500–25,000
samples per sector. This is adequate for a shallow tree (max_depth=4–6, ~50
leaves) but not for a deep model. The PPFM regularization from §2.2 helps
here — the sector model borrows statistical strength from the full-panel
model — but is a Phase 2+ exploratory refinement, not part of H1's simplest
variant (§6.1).

### 5.3 Gating implementation

**Simple gating (Phase 2, this is what H1 tests):** Fixed regime-conditional
weights, no learned gating.

```python
REGIME_WEIGHTS = {
    "BULL_CALM":     {"panel": 0.5, "sector": 0.3, "ticker": 0.2},
    "BULL_VOLATILE": {"panel": 0.3, "sector": 0.2, "ticker": 0.5},
    "BEAR":          {"panel": 0.6, "sector": 0.3, "ticker": 0.1},
}
```

Weights selected by HMM regime state, fixed before the outer-fold holdout is
touched (weight selection happens on inner folds — §6.2). Validated by
replaying historical regimes and measuring ensemble IC vs component IC on
inner-fold data only; the outer-fold comparison is reserved for the H1/H2/H3
confirmatory test.

**Learned gating (Phase 4, CONTINGENT — see §7):** A small network (2-layer
MLP, ~100 params) that maps (regime_features, sector_one_hot) → softmax
weights. Trained on historical IC data with the same nested walk-forward
discipline as the scorers (§6.2) — critically, the network's own fitting must
stay inside inner folds, since a gating network is exactly the kind of
second-stage fitting step that can silently leak outer-fold information if
naively cross-validated. Risk: overfitting the gating network to regime
history (only ~3 regime transitions per year on 5y data = ~15 training points
for regime weights). Mitigated by strong regularization + leave-one-regime-out
cross-validation, but this risk is precisely why Phase 4 is contingent on
Phases 1–3 first showing there is complementary information worth routing at
all.

### 5.4 WF gate integration

Every new model (sector panels, gating function) must pass the existing
walk-forward gate independently before serving. The ensemble output must ALSO
pass the gate — a passing component + failing ensemble = no deploy.

Sector panels have fewer stocks per WF cut → noisier gate metrics. Consider a
pooled gate (sector panels evaluated jointly) alongside per-sector gates. This
is in addition to, not a replacement for, the nested outer/inner discipline in
§6.2: passing the existing single-model WF gate is necessary but not
sufficient once a gating layer sits on top of the scorers.

---

## 6. Falsifiable hypotheses and experiment protocol

The literature in §2 establishes plausibility, not efficacy, for this system.
This section defines the actual test: three pre-registered hypotheses, in
priority order, and the protocol required to test them without the specific
leakage vectors a multi-level (scorer + gating) system introduces beyond a
single-model WF gate.

### 6.1 The three hypotheses (priority order)

- **H1 (primary, confirmatory).** The simplest viable multi-panel/MoE variant —
  Phase 1+2 only: per-ticker unfreezing + sector panels + **fixed**
  regime-conditional gating weights (§5.3's `REGIME_WEIGHTS` table, no learned
  gating) — beats the frozen champion (current XGB panel, unchanged) OOS, net
  of transaction costs, by a pre-registered, statistically significant margin.
  **This is the one confirmatory comparison this research program is
  pre-registered against.**
- **H2 (secondary, exploratory context).** The same H1 variant beats a
  risk-abstention baseline: the frozen champion, unchanged, plus only a
  confidence-based position-sizing/abstention overlay (e.g., reduce/halt buys
  when HMM posterior confidence is low or in BEAR regime) — no new sector or
  gating models at all. H2 tests whether multi-panel complexity is even
  necessary, or whether a cheap risk overlay captures most of the benefit.
- **H3 (secondary, exploratory context).** The same H1 variant beats a
  soft-mixture baseline: a simple fixed or rolling-weighted average of the
  existing champion + shadow model(s) (e.g., XGB + PatchTST), with **no**
  sector panels and **no** learned or fixed regime gating. H3 tests whether
  the *specific* hierarchical architecture (sector panels, regime
  conditioning) adds value over the cheapest possible ensemble of what
  already exists.

H2 and H3 are context for interpreting an H1 result — they are not
independently promotable. A variant that beats H2 or H3 but not H1 is not a
positive result for this program. Phases 3–4 (cross-reference attention,
learned gating, §4.4/§5.3/§7) are separate, later, contingent experiments and
must never be folded into the H1 comparison — H1 is evaluated on the Phase
1+2 variant only.

### 6.2 Nested walk-forward protocol

A gating layer is a **second fitting step** on top of the base scorers. A flat,
single-model WF split (train → embargo → test, once) protects the base
scorers but does nothing to stop the gating weights/network from implicitly
"seeing" outer-test performance during their own selection — a leakage vector
that doesn't exist in this codebase's current single-model WF gate and that
this program must guard against explicitly:

- **Outer folds:** the final held-out test windows used ONLY for the H1/H2/H3
  confirmatory comparison in §6.1. These windows are never touched during any
  model training, hyperparameter search, sector-grouping choice, or
  gating-weight/network selection, for any of the three levels or the gating
  layer.
- **Inner folds:** nested within each outer-train window. Used for sector-panel
  hyperparameter tuning (§5.2) AND all gating-weight/network selection
  (§5.3), including the fixed-weight table's own validation. Nothing about the
  gating mechanism — fixed or learned — may be chosen by looking at outer-fold
  performance.

This is new discipline beyond the existing single-model WF gate specifically
because of the gating layer; it does not replace or loosen the per-scorer WF
gate requirement in §5.4.

### 6.3 Leakage controls

The existing embargo convention in this codebase — a ~30-day gap between train
and test windows on the fwd_60d label, per the WF gate's existing embargo
discipline — is reused at every level, not reinvented:

- Per-ticker (Level 1), sector-panel (Level 2), and cross-sectional panel
  (Level 3) training all use the same embargo gap as the frozen champion.
- The embargo applies to the **gating layer's own fitting** too, not just the
  base scorers: gating-weight/network selection on inner folds respects the
  same train/embargo/test boundary as any other fit, so the gating mechanism
  cannot see label information from inside its own embargo window any more
  than a base scorer can.
- Sector grouping (§5.1) must be fixed before training begins using
  information available at the group's train-window start — no data-driven
  sector assignment using test-period information.

### 6.4 Sample/support requirements

A sector panel is **ineligible for its own independent WF gate**, and must not
be trained or served as a standalone model, until it clears a minimum support
threshold: **≥10 stocks in the group AND ≥3 years of history**, consistent
with §5.1's sample-size discussion and the PPFM small-sector reasoning in
§2.2. Below that threshold, the group **defers entirely to the Level 3
cross-sectional panel** — it is not forced into an undersized independent
model, and it is not automatically merged into an adjacent sector as a
substitute for meeting the threshold (merging per §5.1 Option A is a valid way
to *reach* the threshold, but a group that still falls short after merging
defers to Level 3 rather than shipping a WF-gate-ineligible model).

### 6.5 Calibration requirement (position-level uncertainty cap)

Before Phase 3 ships the position-level uncertainty cap (§4.3), the mechanism
must be validated, not assumed: does higher measured ensemble disagreement
correlate with higher **realized** prediction error, out of sample? This
requires an actual calibration check — e.g., bin predictions by
disagreement quantile and compare each bin's realized error (a
reliability-diagram-style comparison) — on inner-fold data. A disagreement
measure that does not track realized error is not a valid sizing input
regardless of what arXiv:2603.13252 found in its own setting (§2.5); shipping
it unvalidated would import that paper's conclusion without importing its
evidence.

Separately, and at a different stage of the pipeline: raw scores from
different model families are not on a comparable scale and must be
normalized (e.g., z-scored within the training window) before any
combination (soft mixture, H3, or gated ensemble). This is a mechanical
score-normalization step, not a substitute for the calibration check above.

### 6.6 Multiple-comparison treatment and promotion criteria

The full staging plan tests 3 hypotheses × several candidate architecture
variants (§5.1's grouping options A–D, PPFM vs no PPFM, fixed vs learned
gating). Only one of these is confirmatory:

- **H1 vs the frozen champion, using the simplest viable variant (§6.1), is
  the ONE pre-registered primary/confirmatory test.** Every other combination
  — alternative grouping options, PPFM regularization, learned gating,
  cross-reference attention (§4.4) — is exploratory. Exploratory results are
  reported as exploratory: they are never elevated to "the" result of this
  program, and a promising exploratory finding requires a fresh, independent
  confirmatory re-test before it can be promoted on its own.
- If multiple exploratory variants are compared, report the full set of
  results with a family-wise error rate correction (e.g., Bonferroni or a
  step-down procedure). A cherry-picked best-of-N result is not evidence.
- **Promotion criteria:** "beats champion" means a **statistically
  significant** — not merely directionally positive — improvement in
  net-of-transaction-cost Sharpe/IC over the frozen champion on the outer-fold
  holdout, with the improvement holding in a pre-registered majority of the
  outer WF cuts (not just on average). This is the same rigor this codebase's
  existing placebo-clean / regime-conditional WF-gate promotion discipline
  already applies to single models; this program does not get a laxer bar
  because it is an ensemble.

---

## 7. Staging plan

### Phase 1: Unfreeze per-ticker + baseline measurement (prerequisite)
- Fix the per-ticker tournament timeout (600→3600s, already identified)
- Retrain per-ticker models on current data
- Measure: per-ticker IC vs panel IC by sector and regime, on inner folds
- If per-ticker IC ≤ panel IC everywhere → skip Level 1, focus on Level 2
- **Dependency:** None. Can start immediately on model repo — see §9's open
  question on authorization.

### Phase 2: Sector panels with fixed gating (this is what H1 tests)
- Train sector-grouped XGB panels (7 groups per §5.1, subject to §6.4's
  support threshold)
- Measure: sector panel IC vs large panel IC, by sector, on inner folds
- Implement fixed regime-conditional weights (§5.3 simple gating), selected on
  inner folds only
- Run the H1/H2/H3 confirmatory comparison (§6.1) on the outer-fold holdout
- Walk-forward gate each sector panel independently (§5.4), plus the nested
  discipline in §6.2 for the gating weights
- **Dependency:** Phase 1 measurement (to know if Level 1 adds value)
- **Deliverable:** the H1 result. If H1 fails, the default outcome is to stop
  here rather than proceed to Phase 3 (see Phase 4 note below).

### Phase 3: Cross-reference and uncertainty (exploratory, contingent on H1)
- Implement MIGA-style group aggregation within sector groups (§4.4)
- Add position-level uncertainty cap (ensemble disagreement), gated on the
  calibration check in §6.5 passing first
- Replace binary VetoWeakBuys with continuous confidence measure only if the
  calibration check passes
- Validate: does cross-reference improve IC on inner folds? Does the
  calibrated uncertainty cap reduce drawdowns on the outer-fold holdout?
- **Dependency:** Phase 2 sector panels operational AND a validated H1 edge
  (§6.6) — this phase is exploratory refinement of a demonstrated H1 result,
  not a rescue plan if H1 fails.

### Phase 4: Learned gating + full regime-conditional serving (CONTINGENT)
- Train gating network on historical component ICs × regime states, with the
  nested-fold discipline in §5.3/§6.2
- Implement F4 Option A: in degraded regimes, primary panel demoted to shadow,
  gating shifts weight to sector panels or per-ticker experts
- Full regime-conditional model serving as the operator envisioned
- **Dependency:** Phase 3 validated AND sufficient regime transition history.
- **Explicitly not a committed implementation target.** Phase 4 is contingent
  on Phases 1–3 demonstrating a real, validated H1 edge under §6.6's criteria.
  It is not scheduled or resourced until that gate is cleared. **If Phases
  1–3 fail to show a validated edge, the research program concludes there —
  a valid, useful negative result — and does not automatically continue to
  Phase 4.**
- **Risk:** gating network overfitting to few regime transitions (§5.3).

---

## 8. Connection to F4 Option A (PR #479)

The operator's F4 request (regime-conditional model serving, orchestrator
#479) is structurally similar to Phase 4 of this architecture. #479's design
was too narrow in one respect — it only considered shadow-demoting the
primary panel without an alternative to demote *to* — and this multi-panel
architecture, **if it validates through the staged experiments above**, is a
potential future input to that discussion: sector panels or per-ticker
experts as the demotion target.

This research does not itself resolve or substitute for the #479 decision,
and it should not be read as doing so. #479 concerns **serving policy**, which
is a strategy/orchestrator-owned decision gated on an actual operator
sign-off, matching the reviewer's own point on #479 that policy amendments
need an actual operator decision, not research-implied justification. That
remains true regardless of what this research program finds — a positive H1
result would make the case for revisiting #479 stronger, but would not itself
authorize a serving-policy change.

---

## 9. Open questions for operator

1. **Sector grouping:** The proposed 7 groups (§5.1) — acceptable? Or prefer
   GICS Level 1 (11 sectors) with PPFM regularization for small groups?

2. **Model architecture:** Sector panels as XGB (infrastructure-compatible) or
   explore neural (LSTM/Transformer) for sectors where sequence modeling matters
   (tech momentum)?

3. **Priority vs. existing work:** This is a multi-phase research program. Where
   does it sit relative to G1 (cash drag), G2 (crypto), and the two-arm
   experiment?

4. **Per-ticker tournament:** Phase 1 requires unfreezing the per-ticker
   tournament (fix timeout + retrain). Is this authorized given the model repo's
   current state?

5. **Authorization scope for Phase 1:** Phase 1 (unfreezing the per-ticker
   tournament, retraining) is a live-tree-adjacent research action — it
   trains and evaluates models, even though it is scoped to the model repo
   and produces no production behavior change on its own. Confirm it needs
   the same ask-first authorization as other experiment-launching work in
   this codebase before starting, rather than assuming model-repo scope alone
   is sufficient authorization.

---

## Sources

- [MIGA: Mixture-of-Experts with Group Aggregation (2024)](https://arxiv.org/abs/2410.02241)
- [Adaptive Multi-task Learning for Multi-sector Portfolio Optimization (2025)](https://arxiv.org/abs/2507.16433)
- [AlphaMix: Routing Uncertainty-Aware Trading Experts (2022)](https://arxiv.org/abs/2207.07578)
- [AlphaCrafter: Multi-Agent Cross-Sectional Trading (2025)](https://arxiv.org/abs/2605.05580)
- [When Alpha Breaks: Two-Level Uncertainty for Safe Deployment (2025)](https://arxiv.org/abs/2603.13252)
- [Multi-Layer Hybrid MTL Structure (2025)](https://arxiv.org/abs/2501.09760)
- [WorldQuant signal architecture](https://youngandcalculated.substack.com/p/how-quant-hedge-funds-actually-build)
