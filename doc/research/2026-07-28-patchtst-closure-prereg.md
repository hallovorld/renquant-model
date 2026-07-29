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

## 1. The claim under test

**H0 (the claim to be falsified):** today's PatchTST score carries fresh
cross-sectional information beyond the persistence of its own 60-trading-day-old
score.

Stage 0 measured `REAL − persistence` for PatchTST as **negative in all six
cells** (−0.79 … −2.31 block-level t) while the prod XGB was **positive in
all six** (+0.34 … +1.59) `[VERIFIED — goal6-stage0/results.json]`. If that
holds up, PatchTST's walk-forward edge is stale-score inertia and it is not
an alpha source, regardless of its IC point estimate.

## 2. Confirmatory design

- **Subjects:** the 43-fold PatchTST corpus and, as a positive control, the
  prod XGB corpus. A design that cannot show the control passing is not
  evidence about the treatment. **The PatchTST corpus is NOT YET
  GENERATED** — the frozen dispatch plan is model#82 / renquant-backtesting
  #81-#82 ($16.8 projected / $20 hard cap, execute-time enforced); a 1-fold
  smoke test under this exact recipe has passed feasibility, the remaining
  42 folds have not been dispatched. This confirmatory run cannot execute
  until that corpus exists and is independently verifiable (on-disk fold
  count + provenance, not a document's say-so).
- **Statistic:** `REAL − persistence` on per-date rank IC and on the
  top-decile spread, block-level t across folds, at 60d.
- **Persistence lags:** 20d, 40d, 60d, 80d. A genuine fresh-information
  signal should beat its own stale self at EVERY lag; a persistence artefact
  should fail at the lags near the score's autocorrelation plateau. Reporting
  all four prevents a single-lag artefact from deciding.
- **Second control:** the same test on a deliberately signal-free score
  (within-date permuted PatchTST scores), which must show no systematic sign.

## 3. Decision rule (frozen)

Let `p` = the number of the four persistence lags at which PatchTST's
`REAL − persistence` IC difference is **negative with block-level t ≤ −1.0**,
and let the prod-XGB control be positive at ≥ 3 of 4 lags (control valid).

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
