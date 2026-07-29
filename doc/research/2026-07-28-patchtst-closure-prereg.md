# PREREG (FROZEN) — PatchTST closure decision

Frozen: 2026-07-28, before the confirmatory run AND before its subject corpus
has been generated (see CORRECTION below).
Author: claude · Adversarial reviewer: codex.
Prior evidence: model#86 Stage 0 (persistence measurement — itself currently
under active codex review with 5 unresolved design findings, not yet
approved). This prereg exists because Stage 0's finding LOOKS decisive and a
decisive-looking finding must not be acted on post-hoc — it needs its own
rule, frozen first.
CORRECTION (visible, per long-term-agreements.md entry 10, not a silent
overwrite): a prior version of this line also cited "model#85 (43-fold,
verdict UNDERPOWERED)" as prior evidence. model#85 has not run — see its own
corrected doc. That reference is dropped rather than restated; this prereg's
own test does not depend on model#85's outcome either way.

## 0. Known-trap checklist

| # | past failure | avoided how |
|---|---|---|
| T1 | a placebo that sat on the signal's own peak (shift-120 vs a lag profile peaking at 100d) | no lag-shift null anywhere in this design |
| T2 | naive per-date t on overlapping labels (+5.39 vs block-adjusted +0.70) | block-level inference only; `n_eff` printed per row |
| T6 | post-hoc subgroup rescue | closed hypothesis; regime/sector splits descriptive only |
| **T9 (new)** | **acting on a striking result found under a DIFFERENT prereg** — Stage 0's persistence finding was a by-product of a measurement study, not a registered kill test | this document registers the kill rule BEFORE the confirmatory run, on data/seeds not used to generate the finding where possible |
| T5 | absolute effects without matched nulls | every arm reports REAL − NULL |
| **T11 (new)** | **sample-composition mismatch between REAL and PERSIST windows** — `corpus[lag:N]` vs `corpus[0:N-lag)` pairs on label date but draws from different score-date windows, asymmetrically dropping the weakest-IC recent dates from PERSIST only | §2 freezes a common-score-date-set requirement: both arms computed on the shared date subset at each lag, never the raw offset slices |

## 1. The claim under test

**H0 (the claim to be falsified):** today's PatchTST score carries fresh
cross-sectional information beyond the persistence of its own 60-trading-day-old
score.

**CORRECTION (visible, per long-term-agreements.md entry 10, not a silent
overwrite):** this section previously cited "Stage 0 measured `REAL −
persistence` for PatchTST as negative in all six cells (−0.79 … −2.31
block-level t) while the prod XGB was positive in all six (+0.34 … +1.59)"
tagged `[VERIFIED — goal6-stage0/results.json]`. That citation is false:
`goal6-stage0/results.json` cannot exist as a verified artifact because
model#86 (GOAL-6 Stage 0) has not run an approved/executed result — its own
progress doc STATUS reads "no run yet". The specific six-cell numbers are
dropped rather than restated. What motivates this prereg is only the
qualitative shape of model#86's *as-yet-unapproved* design measurement
(PatchTST trending negative on a persistence contrast, prod XGB trending
positive) — not a verified quantity, and not a premise this prereg's own
test depends on either way (T9 exists precisely so this prereg does not
inherit an unregistered measurement as if it were a result).

## 2. Confirmatory design

- **Subjects:** the 43-fold PatchTST corpus and, as a positive control, the
  prod XGB corpus. A design that cannot show the control passing is not
  evidence about the treatment. **The PatchTST corpus's existence is
  contested, not settled**: one audit found no on-disk fold count or
  Modal-run provenance reachable from this repo's git history; a later
  audit reported 43/43 fold dirs, checkpoints, and calibrators plus Modal
  dispatch provenance in a quarantined scratch namespace outside git (see
  model#87's 2026-07-29T06:05 PR comment). This prereg does not resolve
  that dispute. Whoever runs the confirmatory test must independently
  re-verify the corpus at its actual claimed location and provenance
  fingerprint before treating it as real — a document's say-so, in either
  direction, is not sufficient.
- **Statistic:** `REAL − persistence` on per-date rank IC and on the
  top-decile spread, block-level t across folds, at 60d.
- **Persistence lags:** 20d, 40d, 60d, 80d. A genuine fresh-information
  signal should beat its own stale self at EVERY lag; a persistence artefact
  should fail at the lags near the score's autocorrelation plateau. Reporting
  all four prevents a single-lag artefact from deciding.
- **Second control:** the same test on a deliberately signal-free score
  (within-date permuted PatchTST scores), which must show no systematic sign.
- **T11 (new known trap — sample-composition mismatch, frozen fix
  required):** an adversarial audit of an actually-executed confirmatory
  run under this exact design found that reading the REAL arm as
  `corpus[lag:N]` and the PERSIST arm as `corpus[0:N-lag)` pairs the two
  arms on label date but draws them from **different score-date windows**
  — the REAL arm always includes the most recent `lag` dates that PERSIST
  necessarily excludes, and those recent dates carried the weakest (near-
  zero or negative) IC in the motivating profile. Recomputed on a common
  score-date set, a prior run's `p=4/4` CLOSE-direction result for PatchTST
  fell to `0/4`, and the prod-XGB positive control fell to `1/4` (control
  invalid). **Before this confirmatory test is executed for real, the
  harness MUST compute REAL and PERSIST on the same common score-date
  subset at each lag** (drop the non-overlapping tail dates from both
  arms, not just one) — otherwise `p` in §3 is not measuring what it
  claims to.

## 3. Decision rule (frozen)

Let `p` = the number of the four persistence lags at which PatchTST's
`REAL − persistence` IC difference is **negative with block-level t ≤ −1.0**,
computed per the T11 common-score-date-set requirement (§2) — `p` computed
from the raw, non-matched `corpus[lag:N]`/`corpus[0:N-lag)` slices does not
satisfy this decision rule and any verdict built on it is void — and let
the prod-XGB control be positive at ≥ 3 of 4 lags (control valid).

- **CLOSE (PatchTST retired as an alpha source)** — control valid AND
  `p ≥ 3`. The corpus is retained as a PIT artefact; the shadow lane's
  PatchTST leg is deprecated through the standard chain; no re-pitch without
  a NEW registration naming what changed in the recipe.
- **KEEP OPEN** — control valid AND `p ≤ 1`. Stage 0's finding does not
  replicate; PatchTST's status reverts to whatever model#85's own frozen
  evaluation (not yet run) determines.
- **INCONCLUSIVE** — anything else, or an invalid control. No closure, no
  further compute without a new prereg.

Ties, ambiguity, or a broken run resolve to INCONCLUSIVE. A CLOSE verdict
does **not** authorise any live change by itself; it authorises opening the
deprecation PR that the standard chain then reviews.

## 4. Discipline

Read-only over the quarantined corpus; no production surface touched; every
number provenance-tagged (LONG rule #10); negative and inconclusive outcomes
reported with equal prominence; this document is frozen and any change is a
timestamped amendment written before the affected run.
