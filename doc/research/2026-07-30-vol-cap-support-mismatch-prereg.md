# PREREG (FROZEN): does the pre-scoring volatility cap remove the names where the model has edge?

**Frozen:** 2026-07-30, **before any arm was computed.** This revision contains
**NO result.** The git history of this branch is the evidence.

**Status:** a CHEAP, BOUNDED test. §7 states plainly that it can only **kill**
the concern or **justify escalation** — it can never confirm it. Registering
that asymmetry up front is the point of the document.

---

## 1. The measured mismatch this tests

Three quantities, all `[VERIFIED-prior — renquant-model#103 / orchestrator#615]`:

| | |
|---|---:|
| `STD60` average marginal effect on the live scorer (400 z-space baselines) | **+0.2301** — the largest of any feature |
| `spearman(STD60, annualised 60d vol)` across 144 watchlist names | **+0.821** |
| the 60% annualised-vol gate, which runs **BEFORE** scoring, drops | **35** names, median `STD60` **0.1586** |
| it keeps | **109** names, median `STD60` **0.0513** → **3.09×** |

So the model's single strongest input is **truncated at serve time at roughly
the 60th percentile of the support it was trained on** — the artifact's own
`panel_shape` is 292 uncapped tickers. Training and serving see different
supports of the model's dominant feature, and a name the gate drops has no score
row at all, so this is invisible from the score DB.

**The question that decides whether this matters:** is the model's edge
**concentrated in the names the gate removes**? If it is, the gate is destroying
signal before it can be used. If it is not, the mismatch is cosmetic and this
lane should be closed cheaply rather than escalated.

## 2. Corpus, pinned — and its reuse disclosed

| input | sha256 |
|---|---|
| `RenQuant/data/alpha158_291_fundamental_dataset.parquet` | `7defdacf97f8eb057a9a56a2eb7bc6eb48bc33adb9fd00a2a6c36943be87daa5` |
| `backtesting/renquant_104/artifacts/prod/panel-ltr.alpha158_fund.json` | pinned at run time and printed |

Both are **production files opened READ-ONLY**; the runner pins the panel and
**aborts** on mismatch.

**Disclosure:** this panel was already consumed by two factor screens
(`2026-07-29-vol-conditioned-momentum-reversion-screen.md`,
`2026-07-29-momentum-family-screen.md`). Those asked whether a *factor* carries
signal. This asks where the *deployed model's own score* has its edge, which is
a different estimand on the same rows — but reuse is reuse, and it is recorded
here rather than left for a reviewer to notice.

## 3. THE BINDING LIMITATION, stated before any number exists

**The artifact was TRAINED on this panel** (`panel_shape = {rows: 721335,
tickers: 292, dates: 2570}`). Every measurement below is therefore
**IN-SAMPLE**, and:

- **No absolute edge number may be read from this document.** An in-sample IC or
  spread is an overfit measurement and means nothing about live performance.
- **Only the CONTRAST between the kept and dropped groups may be read**, and
  only because the training panel was **uncapped**, so the fit was not
  deliberately steered toward either group.
- **Even the contrast is confounded**, and this is not something the design can
  remove: in-sample fit quality may itself differ between high-vol and low-vol
  names (a noisier group can be easier or harder to memorise). So a large
  contrast **cannot** distinguish "real edge concentration" from "differential
  overfit". A clean separation needs out-of-sample scores for the dropped names,
  and those do not exist — the serving path never scores them.

That is why §7 registers this as a one-way test.

## 4. Score reconstruction, and the check that must pass first

The scorer is reconstructed from the artifact alone: standardise each of the 172
`feature_cols` with the artifact's own `feature_means` / `feature_stds`, then
predict with `booster_raw_json`.

**Gate on the reconstruction, evaluated BEFORE any arm:** the standardised
feature matrix must have per-column mean ≈ 0 and sd ≈ 1 on this panel. If it
does not, the stored moments do not belong to this panel and **the run aborts**
— every downstream number would be computed on a mis-standardised input. The
tolerance is registered now: `|mean| ≤ 0.15` and `sd ∈ [0.8, 1.25]` for at least
**90%** of the 172 columns.

This is the only validation available: there are no stored scores for these
dates to compare against, because the panel ends 2026-05-01 and the score DB
holds no features (renquant-pipeline#226).

## 5. Arms, fixed now

Volatility is measured exactly as the live gate measures it — annualised stdev
of daily close-to-close returns over 60 trading days, in percent — and the
threshold is the live `60.0`.

| id | arm |
|---|---|
| V_full | every name on each date |
| V_kept | names with `ann_vol ≤ 60%` — what serving actually scores |
| V_drop | names with `ann_vol > 60%` — what the gate removes before scoring |

`V_full` exists so that a kept-vs-dropped difference can be read against the
pooled level rather than in isolation.

## 6. Estimands, estimator, controls — identical to the two prior screens

E1 full cross-section Spearman IC per date; E2 top-decile spread with
`k = round(0.10·n)`, `k ≥ 1`; dates with `n < 20` **scored names in that arm**
dropped. Estimator `dependence_aware_mean`, `block_length = 60`,
`n_boot = 2000`; an arm RESOLVES only when block `t`, bootstrap CI and
leave-one-block-out agree. Five within-date label shuffles per arm per estimand;
a control above the arm's own `|t|` **VOIDS** it.

Deliberately unchanged from the factor screens so the numbers are comparable and
so no estimator choice can be attributed to this question's answer.

**Multiplicity.** 3 arms × 2 estimands = **6 new tests**. Joint with the 18
already registered ⇒ **24 tests** ⇒ Bonferroni α=0.05 two-sided ⇒
**`|t| ≥ 3.06`**. This supersedes the prior `2.99` **upward**. Tightening after
freezing is conservative and permitted; loosening is not.

**A known defect in the control rule, carried forward not silently repeated:**
an arm whose own `|t|` is near zero is mechanically labelled VOID, because any
control noise out-scores it. That was disclosed in the momentum screen and is
NOT amended retroactively here; the runner prints the arm's own `|t|` next to the
control max so a reader can tell a VOID-because-null from a VOID-because-dirty.

## 7. Decision rule — a ONE-WAY test, registered as such

1. **Reconstruction gate (§4) fails ⇒ ABORT.** No arm is reported.
2. **CLOSE THE LANE** if `V_drop`'s E2 spread is **not materially above**
   `V_kept`'s — concretely, if `V_drop_E2 ≤ V_kept_E2`, or if `V_drop`'s controls
   VOID it. Then the pre-scoring cap is not removing the model's edge, the
   support mismatch is cosmetic, and no retrain, no gate move, and no further
   work on this lane is justified. **This is the cheap kill, and it is the
   outcome I expect to be most useful.**
3. **ESCALATE — and only escalate** if `V_drop_E2` exceeds `V_kept_E2` with
   clean controls and `|t| ≥ 3.06`. The licensed next step is then an
   out-of-sample design (walk-forward scores for the dropped names), **not** a
   config change, **not** moving the vol cap, and **not** a retrain. Because of
   §3's confound, this document can never license touching the live path.
4. No verdict may be revised by changing the vol threshold, `k`, the block
   length, or the date range. Any such change is a new screen needing a new
   registration.

## 8. What a positive would NOT license

Not a config change. Not moving or removing the 60% vol cap — that cap is a risk
control with its own rationale, and "the model scores high-vol names well
in-sample" is not an argument for holding them. Not a sizing change. Not a P&L
claim: the label is per-date z-scored, so every number is in standard
deviations.

---

**Nothing in this revision is a result.**

---

# RESULT: ABORTED at AC-0. The gate caught MY bug, not a production bug.

`[VERIFIED — this session]` Runner output: `doc/research/data/2026-07-30-m1-abort.log`.

## The registered gate fired

Only **1 of 172** standardised columns (0.6%) landed within `|mean| ≤ 0.15` and
`sd ∈ [0.8, 1.25]`, against the registered floor of **90%**. Per §7.1 the run
aborted and **no arm was reported**. Worst offenders: `book_to_price`
(mean `+1.4e17`), `earnings_yield` (`+2.8e16`), `VWAP0` (`−106.15`),
`HIGH0` (`−72.42`), `LOW0` (`−71.56`).

## Why it fired — the honest answer is that the runner was wrong

I read the code rather than inferring from the numbers, and the design is
deliberate and documented:

- `RenQuant/scripts/train_production_model.py:240` logs, verbatim:
  *"Loading R1K + 5-fund panel (**already normalized**: alpha158=zscore,
  fund=robust-zscore)"*
- `build_normalization()` at `:358`, verbatim: *"Build the **inference**
  normalization chain stored in the artifact. For each feature, (mean, std) such
  that **(raw − mean) / std = normalized value**"*, sourced from
  `data/alpha158_qlib_dataset.stats.json`.

So the on-disk training panel is **already in the model's input space**, and the
artifact's `feature_means` / `feature_stds` exist so the **serving** path can map
freshly-computed RAW features into that space. My runner applied them to the
already-normalised panel — **a double standardisation.** The measured signature
matches exactly: `VWAP0` stored `mu = 1.0` (a vwap/close ratio) versus panel mean
`−0.0065, sd 0.966`; `STD60` stored `mu = 0.0576` versus a freshly computed raw
`std(close,60)/close` of 0.047–0.055 on five names.

**There is no train/serve standardisation bug.** I was one report away from
claiming one, and AC-0 is the only reason I did not. That is what the gate was
for, and it is the most useful thing this document produced.

## M1's question remains OPEN, and needs a different instrument

The vol-cap support question is neither answered nor refuted. Answering it needs
the model's score on this panel, which requires feeding the **already-normalised**
columns to the booster directly, with no second standardisation — a one-line
change to the runner. That is a **new registration**, not a re-run of this one:
§7.4 forbids revising a verdict by changing the procedure, and this document's
verdict is ABORT.

## What the abort DID establish — a real, function-level defect

`[VERIFIED — this session]`

| | |
|---|---|
| `feature_raw_clip_low` / `_high` set for | **158 of 172** columns |
| set for the 14 fundamental columns | **none — all `None`** |
| `stats.json` clip entries | **158** |
| `STD60` (Alpha158) raw clip | `[0.00843, 0.59738]` — bounded |
| `book_to_price` panel values | mean **+3.96e16**, max **+1.68e19** |
| rows with `|book_to_price| > 1e6` | **11,006 = 1.52%** |
| rows with `|earnings_yield| > 1e6` | **10,338 = 1.42%** |
| `book_to_price` share of model gain | **2.0%** |

Generator: `RenQuant/scripts/fetch_sec_fundamentals.py:318`,
`result["book_to_price"] = _safe_ratio(eq, mktcap)` — `StockholdersEquity /
market_cap`, with no denominator floor and no output winsorisation. The same file
at `:308` already carries a comment about previously *"poisoned earnings_yield /
book_to_price for ~45 tickers"*, so this failure mode is known and was only
partly addressed.

**Impact, bounded honestly:** XGBoost splits are rank-based, so 1e19 values do
not corrupt the training arithmetic. What they do is make those 1.5% of rows fall
on the same side of **every** `book_to_price` split, which turns a feature
carrying 2.0% of gain into a garbage-row indicator for that slice. Not
catastrophic, and not nothing. **No claim is made here about the effect on any
score**, because that would need the score reconstruction this document just
failed to perform.
