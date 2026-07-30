# PREREG (FROZEN): measure the decision we trade, not the one we don't

**Frozen:** 2026-07-29, before applying the rule below to any subject other
than the screen named in §3.
**Status at freeze:** no confirmatory result exists. This document contains no
outcome.

---

## 0. How to audit every number in this document

```
python3 tools/traded_estimand_calibration.py \
    --subject         clf \
    --corpus          <scratch>/clf-wf/clf_wf_scores.parquet \
    --screen-corpus   <scratch>/clf-wf/clf_wf_scores.parquet \
    --patchtst-corpus <scratch>/wf-eval/scores.parquet \
    --panel /Users/renhao/git/github/RenQuant/data/transformer_v4_wl200_clean.parquet \
    --require-pinned
```

The script pins each input by sha256 and **aborts** on a mismatch, so a
different corpus cannot reproduce different numbers under this document's
name. Its sections A-E map 1:1 onto §2, §3, §6, §5, §5 below.

| input | sha256 | supplies |
|---|---|---|
| `clf-wf/clf_wf_scores.parquet` | `1da3fcfab06af1e597ac0eb83dff4741ed3dd027de8b8a6b4d58979f5bc4efe4` | §2 units, §3 screen, §5 false-flag, §6 null |
| `wf-eval/scores.parquet` | `6eb209e2491b26b18b7b687c7683f27f8e5cbe56592186bfbac68381e2606d18` | §5 shift120 ban |
| `data/transformer_v4_wl200_clean.parquet` | `3982ca545d4c109b4809b887f2f9bbfc1a9363f7889b6a2ba08504e2668f0676` | §5 label panel (production file, opened READ-ONLY) |

Both corpora live in the quarantined scratch namespace, as their own preregs
require; the panel is a production data file and is read, never written.

---

## 1. The claim being registered

Every gate in this programme has been read off **full cross-section IC** — the
rank correlation between score and forward return across *all* names. The
system does not trade all names. It trades the **top decile**.

Registered hypothesis: the traded estimand carries resolvable signal where IC
does not, because IC spends its power on the ~90% of the cross-section we never
act on.

This is registered as a *measurement-design* claim, not a claim that any
particular model has edge.

## 2. The estimand, fixed now

For each score date `d` with at least 20 scored names:

```
k        = round(0.10 * n_names(d))            # at least 1
spread(d) = mean(fwd_60d_excess | top-k by score)
          - mean(fwd_60d_excess | remaining n-k)
```

Aggregated over dates by the estimator in §4.

**Units.** `fwd_60d_excess` is **cross-sectionally standardised** — measured on
the clf corpus: `mean = -0.0000`, `sd = 0.9982` `[VERIFIED — calibration §A, clf corpus sha256 1da3fcfa…5bc4efe4]`. A
spread of `0.30` therefore means **0.30 standard deviations of the forward
return distribution, NOT 30% return.** Converting to money requires the raw
return dispersion this label has standardised away, and is explicitly OUT OF
SCOPE here. No P&L claim may be made from this document's statistic.

**Why decile and not another cut.** Top-10% is the cut the live buy path
already uses. Registering the cut we trade rather than the cut that maximises
the statistic is the entire point; any other `k` would need its own
registration.

## 3. What is a SCREEN and what may be CONFIRMATORY

**SCREEN (already observed — cannot confirm anything).** The clf walk-forward
corpus (625 score dates, 43 folds, 292 tickers) was run on this estimand
*before* this document was written: spread `+0.368 sd`, block `t = +3.03`,
resolving on all three views, with 5/5 label-shuffle placebos null (max
`|t| = 0.84`) `[VERIFIED — calibration §B, clf corpus sha256 1da3fcfa…5bc4efe4]`.

That result is **why this prereg exists**. It is a screen. It cannot also be
its own confirmation, and quoting it as evidence for the registered hypothesis
would be the exact HARKing failure that retracted two PatchTST verdicts.

**CONFIRMATORY subjects — unseen on this estimand at freeze time:**

| subject | corpus | seen on this estimand? |
|---|---|---|
| PatchTST WF | 43-fold, 625 dates, 142 names | **no** |
| prod XGB | its own WF corpus | **no** |
| clf, forward dates | dates accruing after 2026-03-31 | **no (do not exist yet)** |

The first two may be run once this document is merged. The third is the only
one that is independent for the clf subject itself, and it accrues at ~21
dates/month, so it will not be decidable for months. That limitation is
recorded here rather than worked around.

## 4. Estimator, fixed now

`renquant_model_common.lag_alignment.dependence_aware_mean`, with
`block_length = 60` (the label horizon in trading days, so overlapping labels
sit inside one block), `n_boot >= 2000`.

**A subject RESOLVES only when all three views agree in sign:** the block
`t`, the moving-block bootstrap CI, and leave-one-block-out. Two of three is
not a result. No other estimator may be substituted after seeing an outcome.

**Sample rule.** Where two arms are compared, they must be evaluated on a
COMMON score-date set, constructed with `lag_alignment.align_lags` /
`align_lag_pairs`. Any comparison built from `corpus[lag:N]` versus
`corpus[0:N-lag)` slices is void on sight — that defect has already retracted
one verdict on this programme.

## 5. Controls, and the measured cost of the control rule

Five label-shuffle arms (seeds 0-4): permute `fwd_60d_excess` **within each
date**, preserving the per-date cross-sectional distribution, then recompute
§2 unchanged.

Each control is assessed with
`renquant_model_common.control_calibration.assess_control` fed **fold means**
(not per-date values, not block means — the unit is registered because it
changes the answer). A control that is itself significant does not lose the
comparison, it **VOIDS** it.

Measured false-flag rate of that bar on 30 genuinely clean nulls
`[VERIFIED — re-run post-#96-merge on 85be1a3; calibration §D, clf corpus
sha256 1da3fcfa…5bc4efe4, seeds 5000-5029]`:
fold means 1/30 = 3%, block means 2/30 = 7%.

`control_calibration.assess_control` — which §D depends on — **merged to
`main` as `0c82f6a`** (`renquant-model#96`). This branch is rebased onto that
`main` commit, and §D was re-run on that rebased tree (`85be1a3`): the import
resolves through the canonical `renquant_model_common.control_calibration`
path with **no PYTHONPATH override and no stacked branch**, and the pinned
sha256 check passed on all three inputs. The dependency is discharged: the
earlier "not yet verified relative to `main`" / "unmergeable until #96 lands"
qualifiers no longer apply and have been removed.


### §5 AMENDMENT 1 (2026-07-29, before any confirmatory run)

The false-flag rate of the `|t| > 2.0` bar is **not a constant of the rule**.
It depends on the corpus geometry, and the first revision registered only one
end of the range:

| corpus | names x folds | per-arm false-flag | ALL-clean void rate |
|---|---|---:|---:|
| clf walk-forward | 292 x 43 | 3% (1/30) `[VERIFIED — calibration §D]` | 14% `[DERIVED — 1-0.97^5]` |
| synthetic signal-free panel | 60 x 44 | **8.0% (12/150)** `[VERIFIED — runner tests]` | **34%** `[DERIVED — 1-0.92^5]` |

So the same frozen rule discards between **14% and 34%** of valid work
depending on panel shape. On clean synthetic arms the `|t|` distribution runs
median 0.69, p90 1.85, **max 3.71** `[VERIFIED]`.

**Registered consequence.** Before a subject is run, its corpus's own per-arm
false-flag rate MUST be measured on 30 clean shuffles and reported alongside
the verdict. A VOID is then interpretable — a reader can tell "this control is
genuinely carrying signal" from "this panel's geometry makes the bar strict".
An unreported VOID is not a result.

**The threshold is NOT changed.** Loosening a bar after discovering it is
strict is moving the goalpost, and no re-run allowance is granted either: a
"re-run with fresh seeds on a VOID" rule is a garden of forking paths. The
cost stays, it is now stated at its true width, and it is paid knowingly.

A mechanism I hypothesised and DISCARDED rather than registered: that 60-day
overlapping labels make fold means autocorrelated, breaking the plain
one-sample `t`. Measured lag-1 autocorrelation of null fold means: mean
`+0.001`, median `+0.040`, `|ac| > 0.2` in 3/20 arms `[VERIFIED]`. The
independence assumption holds; the bar is simply not calibrated to this
statistic's tails.


### §5 AMENDMENT 2 (2026-07-29, before any confirmatory run)

Amendment 1 required every confirmatory subject to measure its OWN 30-shuffle
false-flag rate. The calibration tool could not do that: it ran section D only
on the already-consumed clf corpus, so PatchTST and prod XGB had **no execution
path for a prerequisite this document calls mandatory**. A registered protocol
that is not executable for the subjects it names is not registered.

`tools/traded_estimand_calibration.py` is now `--subject`/`--corpus`
parameterised. Running it on the PatchTST subject for the first time produced
two subject-specific facts that Amendment 1 predicted would exist and the
single-corpus version could not have seen:

| quantity | clf subject | **patchtst subject** |
|---|---:|---:|
| label mean | −0.0000 | **+0.1356** |
| label sd | 0.9982 | 1.0895 |
| false-flag, fold means (registered unit) | 1/30 = 3% | **0/30 = 0%** |
| ALL-clean survival over 5 controls | 84% | **100%** |
| null CI half-width | 0.0124 sd | **0.0184 sd** |

`[VERIFIED — calibration §A/§C/§D, subject=patchtst, corpus sha256
6eb209e2…e2606d18 joined to panel sha256 3982ca54…668f0676]`

**Two consequences, both registered here:**

**(a) The void-rate budget is subject-specific and the range is wider than
Amendment 1 stated.** Measured 0% (patchtst) to 3% per arm (clf) to 8%
(synthetic), i.e. an ALL-clean void rate of 0%–34%. Carrying clf's 16% forward
to PatchTST would have attached a materially wrong budget to its verdict.

**(b) §2's unit statement does NOT hold uniformly.** §2 records the label as
cross-sectionally standardised with mean −0.0000. That is true of the clf
corpus. On the PatchTST corpus the joined label has **mean +0.1356** — because
its 142 tickers are a subset of the 292-ticker panel over which the
standardisation was performed, so restricting to the subset leaves a non-zero
mean. A top-decile spread on that subject is measured against a SHIFTED
distribution.

Registered consequence: each subject's label mean and sd MUST be reported with
its verdict, and a spread may not be compared ACROSS subjects without stating
both. This does not invalidate a within-subject verdict — the spread is a
difference of two means drawn from the same distribution, so a common shift
cancels — but it does forbid the cross-subject comparison a reader would
otherwise make by default.

**Verification mode.** The tool now distinguishes FULL from PARTIAL: FULL
requires `--require-pinned` and every supplied input present in the PINNED
table, and aborts otherwise. A run that omits sections prints PARTIAL and says
so. A missing required input aborts rather than silently reducing coverage, and
an unimportable `control_calibration` now ABORTS instead of printing SKIPPED —
a calibration that omits a mandatory section must not be reported as one.

**A shift/displacement placebo may NOT be used.** Measured on the **PatchTST**
corpus — NOT the clf one; the two are different subjects and conflating them
was an error in this document's first revision — the `shift120`
label-displacement arm scores fold-mean IC `+0.0715` at `t = +2.90` (37 folds)
against the real arm's `+0.0278` at `t = +1.22` (43 folds)
`[VERIFIED — calibration §E, corpus sha256 6eb209e2…e2606d18 joined to panel
sha256 3982ca54…668f0676]`. A control more significant than the arm it is
meant to null is not a control. Displacing a label does not destroy alignment
when the score carries slow-moving cross-sectional structure.

## 6. Power, stated honestly

Under a pure null the estimator is tight: median CI half-width `0.0124 sd`
across 12 clean shuffles `[VERIFIED — calibration §C, seeds 1000-1011]`. That is **not** the MDE,
because a real effect brings its own per-date dispersion: the screen's real
arm carried half-width `0.2176 sd` at an effect of `0.3680 sd`
`[VERIFIED — calibration §B]`.

So: an effect whose per-date series is as disperse as the screen's needs to be
of order **`0.22 sd` or larger** to resolve at 11 blocks `[DERIVED]`. A subject
returning a smaller point estimate is expected to come back UNRESOLVED, and
that outcome carries no information about the model — only about the sample.
It must be reported as UNRESOLVED, never as a negative.

## 7. Decision rule, frozen

For each confirmatory subject, in this order:

1. **Controls first.** If `gate_comparison` over the five shuffle arms returns
   `may_proceed = False`, the subject is **VOID**. Stop. Do not look at the
   real arm.
2. **Real arm.** Compute §2 under §4.
3. **Verdict:**
   - **RESOLVED-POSITIVE** — all three views positive AND bootstrap CI low
     bound `> 0` AND the largest control `|t|` is below the real arm's `|t|`.
   - **RESOLVED-NEGATIVE** — all three views negative and CI high bound `< 0`.
   - **UNRESOLVED** — anything else. This is the default and the most likely
     outcome; it is a statement about power, not about the model.
4. No verdict may be revised by changing `k`, the block length, the estimator,
   or the date range. Any such change makes the run a new screen requiring a
   new registration.

## 8. What a RESOLVED-POSITIVE would and would not license

Would: promoting the traded estimand to the gate statistic in place of IC, for
that subject.

Would **not**: any capital action, any sizing change, any claim of expected
return. The statistic is in standardised units (§2) and carries no cost model,
no turnover model, and no capacity model. Money is a separate, later question.

## 9. Trap checklist

| # | trap | how this document closes it |
|---|---|---|
| T1 | HARKing the estimand | §2 fixed before any confirmatory subject; §3 names the screen as a screen |
| T2 | Estimator swapped after seeing the answer | §4 fixed, substitution forbidden |
| T3 | Arms on drifting samples | §4 common-sample rule; slice comparisons void on sight |
| T4 | Control that cannot fail | §5 shift placebo banned with the measurement that banned it |
| T5 | Control bar that voids valid work silently | §5 Amendment 1: rate measured per corpus (3%-8%), void cost registered as a RANGE (14%-34%), and each subject must report its own rate with the verdict |
| T6 | Unit confusion | §2 records `sd = 0.9982`; P&L claims forbidden |
| T7 | Reading UNRESOLVED as a negative | §6 and §3 rule it out explicitly |
| T8 | Reusing a consumed corpus | §3 lists which corpora are consumed and which are not |
| T9 | Multiplicity across subjects | three subjects registered; each reported separately, no best-of |
| T10 | Verdict published before adversarial review | §10 |

## 10. Publication rule

No verdict from this prereg is published until it has survived a commissioned
adversarial review whose brief is to REFUTE it. Withholding a verdict pending
attack is the only thing that prevented a third retraction on this programme.

---

**Nothing in this document is a result.** The confirmatory runs begin after it
merges.
