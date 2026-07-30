# PREREG (FROZEN): v1 vs v2 fundamentals — and the look-ahead is an ARM, not noise

**Frozen:** 2026-07-30, before any arm was computed. **No result in this
revision.** The git order is the evidence.

**Main line.** This is the `v1-vs-v2 PIT model-level A/B` lane. It is registered
in **two stages**, and the expensive stage is **gated** on the cheap one, because
a model-level difference between a contaminated panel and a clean one is
uninterpretable until the feature-level difference is decomposed.

---

## 1. Why a naive two-arm A/B would be void on arrival

v1 (the shipped `sec_fundamentals_daily`) and v2 (an as-filed PIT build) differ in
**at least three ways simultaneously** `[VERIFIED-prior — this session's audits]`:

| axis | v1 | v2 |
|---|---|---|
| availability stamp | fiscal-period-end **+ fixed 45d** on **90.37%** of rows; the `sec_filed` tier fires on **0.00%** | real `min(filed)` per fact, **0 PIT violations** |
| look-ahead | **77.6% of 10-K filings** exceed 45d, median **+10d**; 10-Ks are 24.6% of filings ⇒ **~19% of filing events contaminated** | none by construction |
| usable universe | 830 names | **515** names with all validated features ≥250 non-null days |
| features | 5 | **3** PIT-defensible; `earnings_yield` / `book_to_price` **blocked** on a split-adjustment mismatch (as-filed share counts are not retroactively split-adjusted while OHLCV closes are — AAPL **3.98×**, NVDA **9.97×**, TSLA **3.02×** share jumps) |

So a two-arm "v1 model vs v2 model" comparison would attribute to *data quality* a
difference that is partly **look-ahead removal**, partly **different values**,
partly **a different sample**, and partly **two fewer features**. Any sign it
produced would be uninterpretable. That is the failure this design exists to
avoid, and it is registered before any number.

## 2. Common support, fixed now

Every arm is evaluated on the **identical (ticker, date) rows and the identical
three features**:

```
tickers  = v1 ∩ v2, restricted to names with >=250 non-null days on all three
features = roe, gross_profitability, asset_growth      # the PIT-defensible three
dates    = dates present in BOTH panels
label    = fwd_60d_excess, per-date cross-sectionally z-scored
```

`earnings_yield` and `book_to_price` are **excluded from every arm** — including
v1's, where they exist — because including them in one arm and not the other is
the confound this section removes. Excluding a feature v1 has is a **cost to v1's
arm**, and it is paid deliberately.

Units are standard deviations of the per-date cross-section. **No P&L claim is
possible from this document.**

## 3. Arms — three, and the third is the whole point

| id | arm | isolates |
|---|---|---|
| **B_v1** | v1 values, v1 availability stamps (as shipped) | the status quo |
| **B_v1_lag** | **v1 values**, availability re-stamped to fiscal-period-end **+60d** | — |
| **B_v2** | v2 as-filed values, real `filed` availability | — |

The decomposition this buys:

- `B_v1 − B_v1_lag` = **the look-ahead contribution alone**, since the values are
  identical and only the availability discipline changes.
- `B_v1_lag − B_v2` = **the value/source contribution alone**, since both are
  conservatively stamped and only the underlying numbers differ.

Without `B_v1_lag` those two effects are algebraically inseparable. 60d is the
measured 10-K p95, i.e. the smallest lag that is conservative for both forms.

**A registered expectation, stated so it cannot be claimed as a discovery later:**
if look-ahead helps in-sample, `B_v1` should score **better** than `B_v1_lag`. A
v1 arm that looks best is therefore **not evidence that v1 is better** — it is the
expected signature of contamination, and §7 encodes that reading in advance.

## 4. Estimands and estimator — unchanged from the four prior registrations

E1 full cross-section Spearman IC per date; E2 top-decile spread,
`k = round(0.10·n)`, `k ≥ 1`; dates with `n < 20` dropped.
`dependence_aware_mean`, `block_length = 60`, `n_boot = 2000`; an arm RESOLVES
only when block `t`, bootstrap CI and leave-one-block-out agree in sign.
Five within-date label shuffles per arm per estimand.

**Two defects from the immediately preceding study are corrected here as binding
requirements, not as suggestions:**

1. **The frame MUST be sorted by date before any shuffle**, and the shuffle MUST
   be verified to preserve each date's label multiset. The momentum screen
   (`2026-07-30-momentum-horizon-prereg.md`) was **ABORTED — INVALID CONTROL**
   because its frame was ticker-major and the shuffle leaked labels across dates.
   The runner asserts both properties and **aborts** if either fails.
2. **No arm may be selected on `t`.** With `block_length` fixed at 60 this study
   has no horizon axis, so the trap cannot recur here — but the rule is carried
   forward explicitly so it is not re-learned.

**Multiplicity.** Stage A adds 3 arms × 2 estimands = **6 tests**. Joint family
with the 25 already registered = **31** ⇒ Bonferroni α=0.05 two-sided ⇒
**`|t| ≥ 3.16`**. This supersedes the prior `3.06` **upward**. Tightening after
freezing is permitted; loosening is not.

**Pairwise differences** (`B_v1 − B_v1_lag`, `B_v1_lag − B_v2`) are computed on the
common date set as a **paired per-date series**, then aggregated by the same
estimator. They are reported as **two additional descriptive contrasts**, and are
**NOT** counted as new tests, because they are deterministic functions of arms
already counted. No significance claim is made from them — only sign and
magnitude, which is what the decomposition needs.

## 5. Stage B is GATED, and the gate is the point

**Stage B — the model-level retrain A/B — runs ONLY IF Stage A returns a
resolvable difference on `B_v1_lag − B_v2` at `|t| ≥ 3.16` with clean placebos.**

Rationale, registered: a retrain per arm is the expensive step, and if the two
panels' features carry indistinguishable predictive content on a common support,
then a model-level difference could only come from noise, from the sample, or from
the two excluded features — none of which is the question. Spending a retrain to
discover that would be building a validation cathedral before there is anything to
validate.

If Stage B runs, its design must be registered **separately and afterwards**,
because the retrain recipe (features, folds, embargo) is not fixed by this
document. **This document licenses no retrain by itself.**

## 6. What each Stage A outcome licenses

| outcome | verdict | licensed |
|---|---|---|
| any arm's placebos dirty | **VOID** for that arm | nothing |
| `\|B_v1 − B_v1_lag\|` resolvable and `B_v1` better | **CONTAMINATION CONFIRMED** | quantify it in the record; it is **not** an argument for v1 |
| `B_v1_lag − B_v2` unresolvable | **NO MEASURABLE SOURCE DIFFERENCE** | **Stage B is NOT run.** v2 is still preferred on correctness grounds — a clean panel does not need to win a horse race to be the right input — but no capability claim is made |
| `B_v1_lag − B_v2` resolvable at `\|t\| ≥ 3.16` | **SOURCE DIFFERENCE MEASURED** | register Stage B separately |

**Note the asymmetry, registered deliberately:** v2 being no better than v1 does
**not** license keeping v1. Look-ahead is a correctness defect, and correctness is
not decided by predictive horse race. This study can tell us how much the
contamination was worth; it cannot license shipping it.

## 7. Limits registered in advance

- **Everything here is in-sample on overlapping history.** No claim about live
  performance.
- **`earnings_yield` and `book_to_price` are excluded from all arms**, so this
  study says nothing about the two features the production scorer actually leans
  on most among the fundamentals (`book_to_price` carries 2.0% of its gain). A
  full answer needs the split-factor repair first.
- **v2's provenance is itself unverified**: `data/edgar_pit/` is gitignored, has no
  refresh job, was produced by ad-hoc heredocs in one session, and its harvester
  was never code-reviewed (base-data **#51/#53**, both OPEN). Its own progress doc
  marks the artifact **UNVERIFIED**. So "v2 is PIT" is a claim about the
  *construction rule*, verified as 0 violations against its own stamps — not a
  claim that the underlying facts are complete. Measured: **10.2% of quarterly and
  11.7% of annual facts** have a first-publication lag > 90d, which makes
  availability **late (conservative), not look-ahead**, and 6 of 829 tickers look
  systematically under-harvested.
- **No cost, turnover or capacity model.** No P&L.
- The **515-name** common universe is not the 830-name universe and not the live
  145-name watchlist. Only **100** of those names have OHLCV reaching 2026-07, so
  this is a research comparison, not a serving-path statement.

---

**Nothing in this revision is a result.**

---

## AMENDMENT 1 (2026-07-30, BEFORE any arm was computed)

**A hole in the frozen design, found while implementing the runner and closed
before any number exists.**

§4 counted "3 arms × 2 estimands = 6 tests". That arithmetic silently assumes
**one score per arm** — but §2 fixes **three features**, and the document never
said how three features become one score. Any combination rule chosen after
seeing results would be a HARK, and even choosing one now carries a trap: the
asset-growth anomaly is classically **negatively** signed while profitability is
positively signed, so an equal-weight blend with no sign alignment would partly
cancel by construction — and registering a sign per feature is itself a choice
that could be tuned.

**Registered resolution: no combination rule. The estimand is PER FEATURE.**

- Arms become `(arm, feature)` pairs: 3 arms × **3 features** × 2 estimands =
  **18 tests**.
- Joint family with the 25 already registered = **43** ⇒ Bonferroni α=0.05
  two-sided ⇒ **`|t| ≥ 3.24`**. This supersedes `3.16` **upward**.
- The two decomposition contrasts of §3 are computed **per feature** and remain
  **descriptive, not counted** — they are deterministic functions of arms already
  counted.

**Why this direction.** Inventing a blend would have kept the bar at 3.16 and made
the result cheaper to claim. Per-feature costs a stricter bar and more work, and it
buys two things worth more than that: no unregistered rule enters the chain, and a
per-feature contrast is *interpretable* — "the look-ahead was worth X on `roe`" is
a statement; "the look-ahead was worth X on an equal-weight blend of three
features with unaligned signs" is not.

§6's decision table applies unchanged, read per feature. Stage B's gate now
requires a resolvable `B_v1_lag − B_v2` contrast on **at least one** feature at
`|t| ≥ 3.24` with clean placebos on both contributing arms.

**Nothing in this amendment is a result.**
