# Multi-Panel Ensemble Architecture: Literature Survey and Hypothesis

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
regime, or turnover constraints. Whether multi-panel architectures beat the
frozen champion (current XGB panel), a simple risk-abstention baseline, and a
soft equal-weight mixture must be determined by staged OOS experiments with
preregistered protocols, not by the survey below.

Candidate architecture: **Hierarchical MoE with Regime-Conditional Gating** —
three prediction levels (per-ticker, sector-panel, cross-sectional panel) whose
outputs are combined by a gating function conditioned on HMM regime state and
sector membership. Each phase advances only if the prior phase demonstrates OOS
improvement over the required baselines.

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
experts in the same group) suggests a cross-reference path. However: MIGA
operates on CSI300/500/1000 (300–1000 stocks), not 104; the style grouping is
learned, not GICS-imposed; and the results are on Chinese A-shares, a different
microstructure. Whether the architecture's advantage transfers to our universe
is an empirical question.

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
independent.

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
Whether the routing layer adds value over simple equal-weighting is the central
empirical question.

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
conditional model serving). The strategy-level gate ≈ HMM regime detection →
demote the primary in failing regimes. The position cap ≈ per-stock uncertainty
from ensemble disagreement between panel and per-ticker models. Whether our
HMM confidence signal is informative enough to drive a useful regime gate is
unestablished.

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
justify sector-specialized models is an empirical question, not an architectural
given.

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

**Level 2 — Sector Panel Models:**
- NEW: sector-grouped panel models (5–7 sector groups)
- Grouping by GICS sector with minimum group size = 10 stocks (merge small
  sectors)
- Training: shared feature encoder (alpha158 base) + sector-specific prediction
  heads
- Cross-sector regularization via PPFM penalty

**Level 3 — Large Cross-Sectional Panel:**
- Existing XGB and PatchTST panel scorers
- Sees all 104 stocks simultaneously

### 4.2 Regime-Conditional Gating

The gating function outputs weights w = (w₁, w₂, w₃) for the three levels,
conditioned on:
- HMM regime state (one-hot: BULL_CALM, BULL_VOLATILE, BEAR)
- Regime confidence (HMM posterior probability)
- Rolling volatility and correlation features
- Sector membership of the target stock

**Regime-specific behavior (hypothesized, to be tested):**

| Regime | Large Panel | Sector Panel | Per-Ticker | Rationale (hypothesis) |
|---|---|---|---|---|
| BULL_CALM | High | High | Low | Cross-sectional patterns stable; sector rotation active |
| BULL_VOLATILE | Medium | Low | High | Dispersion high; idiosyncratic signals dominate |
| BEAR | High (defensive) | Medium | Low | Flight-to-quality is cross-sectional |

### 4.3 Position-Level Uncertainty

After the gated ensemble produces μ̂ for each stock:
- Compute ensemble disagreement = std(Level1_score, Level2_score, Level3_score)
- If disagreement > threshold → reduce position weight or exclude from buy list
- If all three levels agree → high-conviction position

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

Proposed grouping (merge to ~7 groups):
1. Tech + Communication Services (~25 stocks)
2. Healthcare (~15 stocks)
3. Financials (~15 stocks)
4. Consumer Discretionary (~12 stocks)
5. Industrials (~15 stocks)
6. Consumer Staples (~8 stocks)
7. Energy + Materials + Utilities + Real Estate (~14 stocks)

### 5.2 Model architecture for sector panels

Given our XGB-primary stack, sector panels should also be tree-based (not neural)
to maintain interpretability and infrastructure compatibility.

**Concern:** XGB on 10–20 stocks × ~250 trading days × 5 years = 12,500–25,000
samples per sector. Adequate for a shallow tree (max_depth=4–6) but not deep.

### 5.3 WF gate integration

Every new model (sector panels, gating function) must pass the existing
walk-forward gate independently before serving. The ensemble output must ALSO
pass the gate — a passing component + failing ensemble = no deploy.

---

## 6. Required baselines and experiment protocol

The literature survey establishes plausibility, not efficacy for our system. Each
phase must demonstrate OOS improvement over these baselines before advancing:

### 6.1 Required baselines (all phases)

1. **Frozen champion:** Current XGB panel scorer, unchanged, with no ensemble
   or gating. This is the bar.
2. **Risk-abstention baseline:** Frozen champion + a simple regime-based
   abstention rule (e.g., reduce/halt buys when HMM posterior confidence < 0.5
   or in BEAR regime). Tests whether regime-conditioning adds value even without
   additional models.
3. **Soft equal-weight mixture:** Simple 1/N average of all available model
   scores (no gating, no routing). Tests whether gating complexity adds value
   over naive combination.

A candidate architecture advances only if it beats ALL THREE baselines OOS on
the primary metric (IC, or a cost-adjusted return metric if post-Phase-2).

### 6.2 Experiment protocol requirements

Each phase's experiment must preregister:

- **Primary metric:** IC (Phases 1–2), cost-adjusted simulated return (Phases 3–4)
- **Nested walk-forward protocol:** Same 3-cut WF used for current gate, with
  per-sector adjustments for smaller sample sizes. No information from the
  test period may leak into training (feature selection, hyperparameter tuning,
  architecture decisions, or sector grouping)
- **Leakage controls:** Sector grouping must be fixed before training begins
  (no data-driven sector assignment using test-period information). Label
  construction must respect the same embargo gap as the primary model
- **Sample/support requirements:** Minimum stocks per sector group and minimum
  WF cut length. If a sector group has fewer than N stocks (proposed: N=8),
  it must use PPFM regularization or merge with an adjacent sector
- **Calibration:** Ensemble scores must be calibrated to a common scale before
  combination (z-scoring within the training window). Raw score magnitudes
  from different model families are not comparable
- **Multiple-comparison treatment:** If multiple sector groupings, gating
  functions, or hyperparameter settings are tried, report the full set of
  results with a family-wise error rate correction (e.g., Bonferroni or
  step-down). The cherry-picked best result is not evidence
- **Promotion criteria:** Preregistered IC improvement threshold and
  consistency requirement (e.g., improvement must be positive in ≥2 of 3 WF
  cuts, not just on average)

### 6.3 Phase-specific decision rules

- **Phase 1 (per-ticker unfreeze):** If per-ticker IC ≤ panel IC in all
  sector-regime cells → skip Level 1, focus on Level 2
- **Phase 2 (sector panels):** If no sector group's panel beats the frozen
  champion OOS → halt. Sector panels are not free — they add model risk,
  maintenance burden, and WF gate surface area
- **Phase 3 (cross-reference + uncertainty):** If ensemble disagreement does
  not predict next-period model error → uncertainty cap adds noise, not value
- **Phase 4 (learned gating):** CONTINGENT — only if Phases 1–3 demonstrate
  that multiple model outputs contain complementary information worth routing.
  With ~3 regime transitions per year on 5y data (~15 training points for
  regime weights), overfitting the gating network is the default outcome.
  Phase 4 is a hypothesis, not a planned implementation target

---

## 7. Staging plan

### Phase 1: Unfreeze per-ticker + baseline measurement (prerequisite)
- Fix the per-ticker tournament timeout (600→3600s, already identified)
- Retrain per-ticker models on current data
- Measure: per-ticker IC vs panel IC by sector and regime
- Decision rule: see §6.3

### Phase 2: Sector panels with fixed gating
- Train sector-grouped XGB panels (7 groups per §5.1)
- Measure: sector panel IC vs large panel IC, by sector
- Implement fixed regime-conditional weights (no learned gating)
- Walk-forward gate each sector panel independently
- Compare against all three baselines (§6.1) OOS
- Decision rule: see §6.3

### Phase 3: Cross-reference and uncertainty
- Implement group aggregation within sector groups
- Add position-level uncertainty cap (ensemble disagreement)
- Validate: does cross-reference improve IC? Does uncertainty cap reduce
  drawdowns?
- Compare against baselines with cost-adjusted return metric

### Phase 4: Learned gating (CONTINGENT)
- ONLY if Phases 1–3 demonstrate complementary information
- Train gating network on historical component ICs × regime states
- Must beat soft equal-weight mixture to justify complexity
- Risk: overfitting to few regime transitions is the expected failure mode

---

## 8. Open questions for operator

1. **Sector grouping:** The proposed 7 groups (§5.1) — acceptable? Or prefer
   GICS Level 1 (11 sectors) with PPFM regularization for small groups?

2. **Model architecture:** Sector panels as XGB (infrastructure-compatible) or
   explore neural (LSTM/Transformer) for sectors where sequence modeling matters?

3. **Priority vs. existing work:** This is a multi-phase research program. Where
   does it sit relative to G1 (cash drag), G2 (crypto), and the two-arm
   experiment?

4. **Per-ticker tournament:** Phase 1 requires unfreezing the per-ticker
   tournament (fix timeout + retrain). Is this authorized given the model repo's
   current state?

---

## Sources

- [MIGA: Mixture-of-Experts with Group Aggregation (2024)](https://arxiv.org/abs/2410.02241)
- [Adaptive Multi-task Learning for Multi-sector Portfolio Optimization (2025)](https://arxiv.org/abs/2507.16433)
- [AlphaMix: Routing Uncertainty-Aware Trading Experts (2022)](https://arxiv.org/abs/2207.07578)
- [AlphaCrafter: Multi-Agent Cross-Sectional Trading (2025)](https://arxiv.org/abs/2605.05580)
- [When Alpha Breaks: Two-Level Uncertainty for Safe Deployment (2025)](https://arxiv.org/abs/2603.13252)
- [Multi-Layer Hybrid MTL Structure (2025)](https://arxiv.org/abs/2501.09760)
- [WorldQuant signal architecture](https://youngandcalculated.substack.com/p/how-quant-hedge-funds-actually-build)
