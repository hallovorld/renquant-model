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

---

## AMENDMENT 2 (2026-07-30, review findings) — provenance correction

**This heading originally read "... BEFORE any arm was computed", matching
Amendment 1's framing. That claim is false as a statement about git history:
this section's commit (`ea40e20`) landed AFTER the Stage A execution
(`6c992fd`) already existed on this shared-worktree branch — a concurrent
process committed `6c992fd` before this section was drafted, unnoticed until
after `ea40e20` was pushed. "The git order is the evidence" is this
document's own standard, so the claim is corrected rather than left standing:
the two fixes below were motivated by review findings on the pre-result
design, not by having read `6c992fd`'s numbers, but they were *committed*
after a result existed. `STAGE A RESULT` below states, independently, why
that execution is VOID regardless of this section's provenance.**

Two review defects, closed without having read any Stage A number.

### 2a. `B_v1_lag`'s +60d stamp does not isolate value/source ALONE

§3 claimed `B_v1_lag − B_v2` isolates "the value/source contribution alone"
because both arms are "conservatively stamped". That does not hold: 60d is
registered in §3 as the 10-K **p95**, so **by construction ~5% of 10-Ks alone**
file later than the re-stamp — before counting any other lag-prone tail — and
§7 separately measures **10.2% of quarterly and 11.7% of annual facts** with a
first-publication lag **> 90d** on the fuller v2 sample. For that residual,
`B_v1_lag` still carries the value from before it was truly available: smaller
contamination than `B_v1`, but not zero. `B_v1_lag − B_v2` was therefore an
**upper bound** on the value/source effect, not a pure isolate, as `renquant-base-data`
review of the companion fallback-constant PR (**#57**) independently confirmed
about the same 60d/p95 construction.

**Resolution: stop estimating a conservative constant, and reuse the ground
truth that already exists.** `B_v2`'s own availability stamp is real `filed`
per fact, independently verified in §1 at **0 PIT violations**. `B_v1_lag` is
REDEFINED as: v1's **values**, joined on `(ticker, fiscal_period_end)` to
**v2's real `filed` date for that same fact** — not an estimated constant.
Where a v1 fact has no matching v2 `filed` stamp, that `(ticker,
fiscal_period_end)` row is DROPPED from `B_v1_lag`, never defaulted to +60d;
the runner must print the dropped-row count so a silent shrink cannot pass
unnoticed. `LAG_DAYS = 60` is retired from the design; nothing in this study
depends on it any longer.

This makes the two arms' availability discipline **literally identical, not
approximately conservative**, so:
- `B_v1 − B_v1_lag` still isolates the look-ahead contribution alone — values
  held identical, only the stamp SOURCE changes (v1's own defective tiers vs
  v2's independently-verified real filed date).
- `B_v1_lag − B_v2` now isolates the value/source contribution alone with the
  stamp held EXACTLY fixed, superseding §3's "conservatively stamped... 60d
  is the measured 10-K p95" language.

This also removes this design's only remaining dependency on base-data's
filing-lag-fallback policy (base-data **#51/#53/#57**): `B_v1_lag` no longer
derives its stamp from any estimated lag, so nothing here is gated on that
policy landing.

### 2b. The Stage B gate statistic was descriptive but decision-driving

§4 called the `B_v1_lag − B_v2` pairwise contrast "descriptive... NOT counted
as new tests" while §5/Amendment 1 used that SAME contrast, at the SAME
family-derived threshold, to gate whether Stage B runs. A statistic that
decides something is confirmatory, not descriptive, regardless of whether it
is a deterministic function of already-counted arms — the derived quantity has
its own null distribution and its own chance of a false positive, which the
family-wise correction must cover. Separately, two estimands (E1 Spearman IC,
E2 top-decile spread) were both eligible to report this contrast with no
stated primary and no rule for when they disagree.

**Resolution.**

1. **Primary gate estimand: E1** (full cross-section Spearman IC). No new
   preference is invented — E1 is simply assigned priority among the two
   estimands §4 already registered as co-equal, because it uses the full
   cross-section rather than a top-decile subset.
2. **The gate contrast is now counted.** `B_v1_lag − B_v2`, per feature
   (`roe`, `gross_profitability`, `asset_growth`), per estimand (E1 AND E2 —
   E2 is counted too because it participates in the corroboration rule below,
   so it is not merely descriptive either) = **6 new tests**. Joint family
   with the 43 already registered (Amendment 1) = **49** ⇒ Bonferroni α=0.05
   two-sided, standard closed form `z = Φ⁻¹(1 − 0.05/(2·49))` = 3.2848,
   rounded UP (the conservative direction) to **`|t| ≥ 3.29`**. This
   supersedes `3.24` **upward**. (`B_v1 − B_v1_lag` is unaffected: it only
   checks §3's registered-expectation direction, never gates a decision, and
   stays descriptive/uncounted.)
3. **Exact gate rule, replacing §5 and Amendment 1's gate language.** For a
   given feature, the gate is **OPEN** only if ALL of:
   - the primary contrast (`B_v1_lag − B_v2`, estimand E1) RESOLVES (block
     `t`, bootstrap CI, leave-one-block-out agree in sign) at `|t| ≥ 3.29`;
   - both contributing arms' placebos are clean on E1 for that feature;
   - E2's point estimate on the same feature does not disagree in SIGN with
     E1's. E2 need not itself resolve at the bar — it is corroboration, not
     an independent gate — but an opposite sign is a live disagreement, not
     noise.

   If the first two hold but E2 disagrees in sign, the feature is marked
   **PRIMARY-ONLY, NOT CORROBORATED** and does **not** open the gate; the
   disagreement itself is reported as a finding, not discarded. Stage B runs
   if **at least one** feature reaches OPEN — the OR-across-features
   structure is unchanged from §5/Amendment 1; only what counts as OPEN
   changed.

**Why this direction, not a blend or a p-value adjustment shortcut.** Naming
E1 primary and requiring E2 sign-corroboration costs more than either (a)
leaving both estimands eligible to gate (cheaper to claim, but exactly the
ambiguity flagged) or (b) dropping E2 from the gate path entirely (simpler,
but throws away a real disagreement signal). Counting the gate contrast in
the family costs a stricter bar (3.24 → 3.29) rather than a cheaper one.

**Nothing in this amendment is a result.**

---

### 2c. "Clean placebos" was never defined numerically

SS4, SS5, Amendment 1 and the gate rule all require **clean placebos**, and
SS5's outcome table makes `any arm's placebos dirty` a **VOID** — a decision.
But the frozen text never states what `clean` means as a number. The Stage-A
execution below then applied `max |t| <= 2.0` at RESULT time to void
`B_v2 | asset_growth`, and that bar appears nowhere in SS1-SS7 or Amendment 1
(the only earlier `2.0` in this document is the unrelated "`book_to_price`
carries 2.0% of its gain"). An undefined gate term filled in after seeing the
arms is an unregistered decision rule, and it decided a VOID that fed the
Stage-B gate check. Whether 2.0 is a sensible number is irrelevant to that.

**Resolution — registered here, BEFORE the re-execution Amendment 2a forces.**
A control arm is CLEAN for a (feature, estimand) cell iff

    max |t| over the registered placebo seeds  <  2.0

where `t` is the same block-`t` statistic, on the same aggregation unit and the
same common support as the real arms. `>= 2.0` is DIRTY and VOIDs that cell.

The bar is deliberately fixed at the conventional two-sided ~5% z-value and is
deliberately **NOT** family-corrected. A control bar must be EASY to fail,
because its job is to catch contamination; Bonferroni-widening it would make a
broken control harder to detect, which is backwards. Same asymmetry
`control_calibration` registers (renquant-model#96): wrongly trusting a broken
control costs a published-then-retracted verdict, wrongly rejecting a usable one
costs one more control run.

Recorded plainly: this rule is registered NOW and governs only the
re-execution. It does **not** retroactively legitimise the Stage-A numbers
below, which applied it before it existed.

---

# STAGE A RESULT — **SUPERSEDED AND VOID. DO NOT CITE.**

> Amendment 2 invalidated this execution on its own terms, and Amendment 2c
> adds a third reason. Retained for audit only.
>
> 1. **It used the RETIRED `B_v1_lag`.** These arms were computed with the
>    +60d synthetic constant. Amendment 2a retired that constant entirely and
>    redefined `B_v1_lag` to use v2's real per-fact `filed` date. The arms below
>    do not implement the current design.
> 2. **It cites a superseded bar.** The verdict below reads against
>    `|t| >= 3.24`; Amendment 2b counted the gate contrast into the family and
>    raised the bar to `|t| >= 3.29`.
> 3. **It applied an unregistered placebo rule.** The `max |t| <= 2.0` bar used
>    to void `B_v2 | asset_growth` did not exist in the frozen text when these
>    arms ran (Amendment 2c).
>
> **The Stage-B gate is therefore UNDETERMINED — not closed.** No capability
> claim in either direction is licensed by this execution. What does NOT depend
> on these numbers and still stands: v2 remains the preferred input on
> **correctness** grounds, which SS5 registered in advance.

`[VOID — computed under the retired +60d `B_v1_lag`, against a superseded
threshold, using an unregistered placebo rule; retained for audit, not
inference]`

**§4 pre-flight PASSED before any arm ran:** the shuffle is a true within-date
permutation on a deliberately *interleaved* frame, and the self-check was itself
shown to **reject** an unsorted frame — so it certifies something rather than
passing vacuously. That gate exists because the immediately preceding study was
ABORTED for exactly this defect.

**Common support (§2):** v1 qualifying tickers 592, v2 515, **intersection 507**;
**3,158** common dates; per-arm per-date observations **n = 2,597**. Label
`sd = 0.9984` ⇒ units are SD of the cross-section, **not return**.

## ~~SS6 verdict: STAGE B GATE CLOSED~~ — WITHDRAWN. The gate is UNDETERMINED.

`[VOID]` No feature showed a resolvable source difference as executed. Largest
was `asset_growth` at `|t| = 1.37`, read against the then-current bar of
**3.24** (now **3.29** per Amendment 2b). This does not close the gate: the
contrast was computed on the retired +60d `B_v1_lag`, so an unresolvable
difference there is equally consistent with "no source difference" and with
"the residual contamination masked it".

| feature | look-ahead `B_v1 − B_v1_lag` | value/source `B_v1_lag − B_v2` |
|---|---:|---:|
| `roe` | **+0.0002** (t=+0.22) | +0.0324 (t=+1.18) |
| `gross_profitability` | **−0.0188** (t=−2.08) | −0.0166 (t=−0.27) |
| `asset_growth` | **+0.0005** (t=−0.11) | +0.0323 (t=+1.37) |

Arm levels, for context (all below the bar):

| arm | roe | gross_profitability | asset_growth |
|---|---:|---:|---:|
| `B_v1` | +0.0376 (t=+1.33) | −0.0603 (t=−1.50) | +0.1308 (t=+2.33) |
| `B_v1_lag` | +0.0373 (t=+1.30) | −0.0415 (t=−1.00) | +0.1303 (t=+2.34) |
| `B_v2` | +0.0049 (t=+0.35) | −0.0249 (t=−0.69) | +0.0981 (t=+1.84) **PLACEBO-DIRTY** (ctl 2.29) |

`B_v2 | asset_growth` is **VOID** per §4 — its placebo max `|t| = 2.29` exceeds the
2.0 bar. The Stage-B gate check required *both* contributing arms clean, so that
feature could not have opened the gate regardless of its contrast.

## The registered expectation did NOT materialise, and that is the finding

§3 registered, before any number: *"if look-ahead helps in-sample, `B_v1` should
score better than `B_v1_lag`"*. Measured:

- `roe`: better by **+0.0002** — three orders of magnitude below the arm level.
- `asset_growth`: better by **+0.0005**, with `t = −0.11`, i.e. the per-date
  differences are noise around zero.
- `gross_profitability`: **worse by −0.0188** (`t = −2.08`) — the *contaminated*
  arm lost.

So the contamination bought essentially nothing predictively. **That does not make
it acceptable.** §6 registered the asymmetry in advance and it binds here: 19% of
filing events asserting a value was knowable before it was filed is a correctness
defect, and correctness is not decided by a predictive horse race. What this run
establishes is the *size* of the defect's predictive footprint — small — which is
worth knowing precisely because it removes the temptation to argue either way from
performance.

The `gross_profitability` sign deserves one sentence of restraint: at `|t| = 2.08`
against a 3.24 bar, "contamination made it worse" is **not** a claim. It is a
counterweight to any story in which look-ahead reliably inflates results, and
nothing more.

## What Stage A did NOT establish

- **Nothing about the two features the production scorer leans on most.**
  `earnings_yield` and `book_to_price` were excluded from every arm (§2), and
  `book_to_price` alone carries 2.0% of that scorer's gain. The split-factor
  repair has to land before they can be compared at all.
- **Nothing about model capability.** Stage A compares feature content on a common
  support; a retrain was neither run nor licensed.
- **No signal claim for any of the three features.** The best arm level is
  `asset_growth` at `t = +2.33`, below the bar — and its positive sign runs
  *against* the classical asset-growth anomaly, which is a reason for more
  caution, not less.
- **Nothing out-of-sample.** All in-sample on overlapping history.

## Consequence for the lane

The expensive stage is closed by measurement rather than by opinion, which is what
the gate was for. **v2 remains the preferred input on correctness grounds alone.**
The remaining blockers on making it usable are unchanged and are not
model-capability questions: the split-adjustment mismatch on share counts, and
v2's own unverified provenance (`data/edgar_pit/` gitignored, no refresh job,
harvester never code-reviewed — base-data #51/#53, both OPEN).
