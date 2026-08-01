# GOAL-7: a standalone RESIDUAL momentum model — design FOR DISCUSSION

**Status: FOR DISCUSSION, not frozen. Nothing runs until a successor of this document is
frozen after review.** This addresses the reopen condition on model#124/#128/#135 —
*"specify the inferential method and calibration without converting N/h into degrees of
freedom"* — in §3, before proposing any run.

## 1. Why THIS candidate — the map of prior NON-SUPPORTIVE results

The operator's goal is a standalone momentum model deployed to shadow. The local evidence
so far is unfavourable and must steer the candidate, not be argued with:

| already measured | verdict | source |
|---|---|---|
| mom_12_1, mom_6_1, reversal, MA200, 52wk-high on the 104 universe | **non-supportive** (bars predate the overlapping-label inference corrections) | `[早前实测]` canonical price-trend study (closed) |
| dividend-adjusted TR series construction | **validated** — ex-div gap −66.6bp → −4.8bp (t=−1.55), fixed-effects −3.2bp; negative control bitwise 0.0 on 34 non-payers | `[早前实测]` model#110-era, VERIFIED in the frozen TR prereg |
| raw momentum re-scored on the corrected TR series | point estimates worse at all 4 horizons; study verdict **UNRESOLVED** | `[早前实测]` frozen TR study, verdict UNRESOLVED |
| h=120 evaluation | infeasible PRE-BURN at every floor | `[早前实测]` model#148 |

So no prior expression of raw price or raw TR momentum has support here — and, per the
review of this document, that is the full width of the claim: the canonical bars predate
the overlapping-label inference corrections, and the TR study's own verdict is
**UNRESOLVED**. "Non-supportive or unresolved" is what the record says; "dead" is wider
than the record and is withdrawn. The one classic variant with
literature support that none of the closed studies tested is **residual momentum**
(Blitz–Huij–Martens 2011): momentum computed on *idiosyncratic* returns — the component
orthogonal to the market — standardized by idiosyncratic volatility. The economic reason
it can differ on exactly this universe: the 104 book is high-beta-tech-tilted, so raw
momentum rankings are dominated by the market/beta component (which also drives momentum
crashes); residualizing removes the part that the closed studies effectively measured and
keeps the part they did not.

**Stated up front: the local prior is unfavourable, and KILL is an acceptable, reportable
outcome.** This design exists to produce a verdict, not to produce a lane.

## 2. The model — exact and buildable, zero fitted parameters

For each name `i` on each date `t`:

1. Inputs: dividend-adjusted TR daily returns (the validated `build_total_return_series`
   construction), and SPY TR returns as the market.
2. Rolling OLS of `r_i` on `r_SPY` over `t−273 … t−21` (252 trading days of formation,
   21-day skip to avoid 1-month reversal; require ≥200 valid observations, else the name
   is unscored that day and COUNTED as unscored — no silent drop).
3. Residuals `e`; score `s_i(t) = Σe / (σ_e · √N)` — the t-statistic form, which is the
   idio-vol standardization of the reference design.
4. Cross-sectional z-score per date. That z is the lane's output.

All three constants (252 / 21 / 200) are literature values **proposed here and frozen
only by the successor preregistration** — chosen before any outcome is computed, but
after prior research, which is what "proposed" acknowledges. There is no training, no calibrator (calibrator rules are HARD), no
recipe hash to collide with the WF gate's admission problem — and the decisive property:

**Because nothing is fitted, no training window consumes history** — that is the full
claim. Deterministic formulas avoid parameter fitting; they do not make the evaluation
out-of-sample, because the family and the full-history protocol are themselves selected
after prior research. Nothing here is OOS until the successor preregistration freezes the
design; what the no-fitting property buys is the DATE COUNT, not epistemic innocence. The evaluation can use the panel's full ~2,594-date
history instead of the ~500-date corpora that made every recent small-effect test
underpowered (model#157: gap-separated blocks = 4–5 on those series).

## 2b. The feature FAMILY — five mechanisms, one composite, zero fitted parameters

Momentum is not one phenomenon. The literature decomposes it into distinct economic
mechanisms, and the non-supportive record (§1) concerns only one *expression* of one of them —
raw price trend, and even that under since-corrected inference. The family below assigns **one feature per mechanism**, chooses
expressions none of the closed studies tested, and keeps every constant a
literature value — proposed, per §2 — so the zero-parameter-fitting property survives; what that property
does and does not buy is governed by §2's pre-freeze caveat, not restated here.

| id | mechanism | feature (exact) | reference |
|---|---|---|---|
| **F1** | underreaction to firm-specific news | residual momentum t-stat: OLS of daily TR on SPY-TR over `t−273…t−21` (≥200 obs), `F1 = mean(ε)/σ(ε)·√N` | Blitz–Huij–Martens 2011 |
| **F2** | gradual diffusion / information discreteness | frog-in-the-pan: `F2 = sign(r_form) · (frac_pos_days − frac_neg_days)` over the same window — smooth trends continue, jumpy ones revert | Da–Gurun–Warachka 2014 |
| **F3** | industry-level momentum | equal-weight sector formation TR over `t−273…t−21`, assigned to each member: `F3_i = r_sector(i)` | Moskowitz–Grinblatt 1999 |
| **F4** | volume confirmation | signed-volume agreement: `F4 = (Σ vol·1[r>0] − Σ vol·1[r<0]) / Σ vol` over the formation window | Lee–Swaminathan 2000 lineage |
| **F5** | crash asymmetry | downside-beta penalty: `F5 = −(β⁻ − β⁺)`, betas vs SPY conditional on SPY down/up days, same window | Ang–Chen–Xing 2006; Daniel–Moskowitz 2016 |

**Composite (the only decision-bearing signal):** per date, cross-sectional z each
available feature, then `S = mean(z(F1)…z(F5))` with **equal weights, proposed here (frozen only at the successor prereg)**. A
name missing a feature contributes the available subset (require ≥3 of 5, else unscored
and counted); coverage per feature per date is reported. No fitted weights anywhere —
equal-weighting is the deliberately dumb, deliberately unfittable combiner.

**Excluded, with reasons stated now:** 52-week-high nearness (non-supportive locally —
canonical study `[早前实测]`, same inference caveat); calendar seasonality (underpowered at n=292 names);
MAX/lottery effect (largely overlaps F2's discreteness); **fundamental momentum is
DIAGNOSTIC-ONLY** — a fundmom retrain was already rejected (`[早前实测]` #177-era), so it
may be reported alongside but never enters `S`.

**Tier B (exploratory, clearly fenced):** a small walk-forward-fitted combiner
(logistic or shallow XGB on F1…F5, expanding window, embargo ≥ h) may be computed as a
*diagnostic upper bound* on what learned weights could add. It is **never a decision
input** at this stage: it forfeits the zero-fit power advantage, and it would inherit the
WF-gate recipe-hash admission problem (orch#735) that this lane exists to avoid.

### Known limitations, declared before any number exists

* **Sector map PIT**: F3 needs a GICS-style map; if only a current-date map exists, its
  application to history is `[假设]` (reclassification is rare but real) and the frozen
  version must name the map's vintage and fingerprint it.
* **Universe PIT**: the panel universe is today's 292 names — survivorship-tilted, like
  every study on this panel. Absolute ICs are inflated by it; the design therefore reads
  only *differences and bars on the same universe*, never absolute levels as truth.
* **Label**: `fwd_20d_excess` is price-return-based (dividends omitted inside the
  window) and per-date z-scored — Spearman IC is invariant to the z-scoring, and the
  dividend omission is a small anti-payer tilt recorded as a limitation (PR #161 AC4
  comment).

## 3. Evaluation protocol — the part the closed PRs demand

* **Estimand E1 (primary):** mean per-date cross-sectional Spearman IC of the score vs
  `fwd_20d_excess`, over all eligible panel dates. `h = 20` is declared from theory
  (T18): ~1-month continuation is the momentum literature's horizon, it is the
  smallest-overlap label available on the panel, and h=120 is pre-burn infeasible
  `[早前实测 model#148]`. `h = 60` is computed as a **descriptive secondary only**.
* **Primary test:** Newey–West HAC t on the per-date IC series, Bartlett kernel,
  `L = h − 1 = 19`, via `renquant_common.metrics.hac_se.hac_t_stat(lag=19)` — the
  implementation measured to reproduce the frozen `SE_HAC` formula to six decimals on an
  iid and a genuine MA(19) overlapping series `[本次实测 model#159]`. **No `N/h` anywhere;
  no gap-block Student bars** (model#157).
* **Validation of the test, required before any verdict is read (the "validated HAC"
  condition from the #156 review):**
  1. positive control — the identical procedure on the committed pure-noise per-date
     series must NOT reject at α;
  2. size probe — seeded synthetic AR(1) series at ρ₁ ∈ {0.90, 0.95, 0.975} with n equal
     to the observed eligible-date count; empirical size must be ≤ 1.5× nominal, else the
     study reports **UNRESOLVED-METHOD** and no substantive verdict exists.
* **Placebo (centring only, never width, never a decision input):** within-date label
  permutation, 5 draws — model#153 measured that permutation destroys the dependence
  (real ρ₁ 0.82–0.975 vs permuted ≈0), so its spread must not be used as a null width.
* **Decision structure (two hypotheses, one decision signal):**
  * **H1 (primary, 1 test):** mean per-date IC of the composite `S` against a bar and a
    test level that are **BOTH UNRESOLVED until freeze** (Open Question 4). The numbers
    +0.04 and t ≥ 2.0 appear in this document only as **illustrative magnitudes** for the
    power arithmetic — they are not a candidate bar, and per review nothing in a
    discussion draft may be called one. Outcomes: RETAIN-to-shadow / KILL /
    UNRESOLVED-METHOD / UNRESOLVED-POWER. The composite is the ONLY decision-bearing
    statistic, so the decision faces no family-wise erosion.
  * **H2 (parsimony test, 1 test):** `ΔIC = IC(S) − IC(F1)` as a paired per-date
    difference series, HAC on the differences. Corrected per review: F1 may replace `S`
    only if **F1 itself independently satisfies the frozen H1 criterion** — a composite
    passing while its core does not licenses deploying the COMPOSITE, never an
    instrument that has not cleared the primary bar. So: H1(S) ✓ ∧ H2 no-added-value ∧
    H1(F1) ✓ → deploy F1; H1(S) ✓ ∧ H1(F1) ✗ → deploy S regardless of H2.
  * **Per-feature diagnostics (5 tests, Bonferroni α/5):** each feature's own IC,
    reported to attribute where the composite's behaviour comes from — diagnostics,
    never decision inputs. The feature-by-feature rank-correlation matrix is reported so
    redundancy is visible rather than argued.

### 3a′. Independent double audit of the probe numbers — UPHELD `[本次实测 2026-08-01]`

Per the operator's double-audit directive, the probe's numbers were re-derived by an
independent agent that was **forbidden to read the probe's code or results**, via two
routes: (i) its own numpy Monte Carlo from the SE_HAC formula alone (own seed 20260801,
2,500 reps; MA cells tightened at 10,000 reps, second seed) and (ii) an **analytic
closed form** — for the rolling-20 overlap process the Bartlett estimator captures only
**66.75%** of the true long-run variance at L=19 (**88.92%** at L=59), implying inflation
1.224 and a noise-free size floor of 0.109, with estimation noise pushing above it.
Every claimed cell agreed within ~1.5 combined MC SEs (their MA(19)/L=19 at 10k reps:
**0.1184** vs claimed 0.117; their direct check `P(|t| ≥ 2.23) = 0.0471 ± 0.0021`).
**Verdict: UPHELD.** The audit's own scope note stands: it validates the numbers for
these generators, and says nothing about whether the generators model the real series —
which is exactly why the method status above remains UNRESOLVED-METHOD.

### 3a. The size probe has ALREADY RUN — and it fails the test as drafted `[本次实测 2026-08-01]`

The probe this section requires was run ahead of the freeze (H0-only synthetic series,
fixed seed — no real data, no alternative touched; `tools/goal7_hac_size_probe.py`,
results committed under `doc/research/data/2026-08-01-goal7-hac-size-probe/`). n = 2,150,
2,500 reps/cell, nominal α = 0.05 at |t| ≥ 1.96:

| H0 generator | L=19 | L=39 | L=59 | L=119 | calibrated 5% bar t\* (L=59) |
|---|---|---|---|---|---|
| iid control | **0.050** | 0.053 | 0.056 | 0.066 | 2.02 |
| **overlap MA(19)** — the designed-for shape | **0.117** | 0.082 | **0.078** | 0.080 | **2.23** |
| AR(1) ρ=0.90 | 0.142 | 0.097 | 0.090 | 0.084 | 2.27 |
| AR(1) ρ=0.95 | 0.226 | 0.147 | 0.121 | 0.100 | 2.54 |
| AR(1) ρ=0.975 | 0.357 | 0.234 | 0.181 | 0.139 | 3.10 |

Three facts this settles:

1. **The test as drafted above FAILS its own rule.** At `L = h−1 = 19`, even the pure
   label-overlap shape rejects at **0.117 — 2.3× nominal**, far past the ≤0.075 line. The
   iid row (0.050 exactly) proves the instrument is fine; the failure is the Bartlett
   triangle down-weighting precisely the lags that carry the dependence.
2. **No bandwidth in the grid rescues the nominal bar** — the overlap shape plateaus at
   ~0.078–0.082 for L ≥ 39. Widening L alone is not the fix.
3. **A calibrated bar is a candidate direction, not a validation.** At L = 59 the seeded
   5% critical value is t\* = 2.23 for the overlap shape (2.54 / 3.10 for AR(1)
   ρ = 0.95 / 0.975). Per review: these generators can **falsify** a procedure (and did),
   but they cannot **validate** size for the real series' actual, unknown, non-AR
   dependence. **The method therefore remains UNRESOLVED-METHOD** until a null calibrated
   against the real series — its construction and acceptance criteria separately frozen —
   supports it. The table above is the machinery such a calibration would use, nothing
   more.

**Direction for the successor prereg (explicitly NOT adopted here):** HAC at L = 59
against a bar calibrated by a **separately frozen** null-construction protocol that is
matched to the real IC series (measured ACF → generator family → seeded critical value),
with its own acceptance criteria and its own positive control. Until that protocol exists
and is frozen, the honest status of the primary test is **UNRESOLVED-METHOD**. A block bootstrap of the real series is a candidate secondary check; the only thing
stated here is a **construction count**: at h = 20 over ~2,150 dates, gap-separated
blocks number ≈ **54** `[推导]` versus the 4–5 of the h=60 corpora (model#157). Per
review, the count establishes neither feasibility nor validity — a gap removes direct
label overlap, not persistence — so whether such a bootstrap is usable is itself part of
the UNRESOLVED method question.

**Order-of-magnitude power arithmetic `[推导, illustrative only]`:** IF a calibration in
the neighbourhood of t\* ≈ 2.2 were validated for the real series — which it has NOT
been — then MDE ≈ 2.23 × 0.0183 ≈ **0.041**, i.e. the illustrative bar and the MDE
nearly coincide and power at a true IC of +0.04 would be ~50%. These figures exist to
size the undertaking, not to support any bar: while the method is UNRESOLVED, no claim of
valid test size is made for any constant here.

## 4. Path to shadow — so a RETAIN cannot be inert scaffolding

RETAIN triggers the four mechanical preconditions of `shadow_lane_preflight` (orch#699):
declared in the runner config's `shadow_models` (a strategy-104 config change, operator
authorization required), artifact resolves under a declared `--base`, sentinel watches the
lane name, artifact loads. Integration dependency **D1, named not hidden**: the pipeline's
`ApplyShadowScoringTask` currently loads xgb/torch artifact kinds; a deterministic
formula lane needs a `kind` the loader accepts — that is a renquant-pipeline change and is
NOT designed here. Ledger note: the new lane must log both the scored set and the
candidate set identities, so it cannot reproduce the `coverage_frac > 1` ambiguity of
orch#727 (n_scored and n_candidates drawn from different name sets).

## 5. Acceptance criteria (goal must have ACs)

* **AC1** — a frozen successor of this document exists before any IC is computed.
* **AC2** — the run executes exactly as frozen; verdict ∈ {RETAIN-to-shadow, KILL,
  UNRESOLVED-METHOD, UNRESOLVED-POWER}; a negative verdict is reported with the same
  prominence as a positive one.
* **AC3** — if RETAIN: lane live in shadow with all four preflight conditions green, the
  sentinel watching it, and a forward ledger accruing (session count reported weekly).
* **AC4** — the feasibility measurements (formation coverage, TR coverage of the 292
  universe, label convention, eligible-date counts) are attached to the frozen version as
  measured inputs, not assumptions.

## Open questions for review (deliberately not resolved here)

1. Formation coverage: what fraction of panel names have 273d of OHLCV history, per era —
   being measured now, lands with the freeze (AC4).
2. Whether the panel's `fwd_20d_excess` shares the excess convention of the corpora used
   elsewhere — same name, different files, and this programme has been bitten by exactly
   that. The constructor must be quoted in the frozen version.
3. Whether the TR construction covers the 292-name panel universe or only the 145-name
   watchlist it was validated on. If only 145, the design runs on the covered subset and
   says so, or extends coverage first.
4. α and the exact bar constants.
5. Sector map: source, vintage, coverage of the 292 — being measured; F3 drops from the
   composite (family becomes 4-of-4-minimum-3) if no defensible map exists.
6. Volume data quality across the 292 (F4 needs it) — being measured.

## Not claimed

That residual momentum has edge here — the run decides, and the local prior is against.
That D1 is small. That the MDE arithmetic holds beyond its stated assumptions. That
passing the bar licenses anything beyond SHADOW — capital admission remains the WF gate's
problem, which is separately compromised (orch#726/#735) and not this document's to fix.
