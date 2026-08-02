# PREREG (FREEZE CANDIDATE) — residual momentum v2: the SAME candidate under a dependence-adequate null

**Frozen on merge of this PR. No IC, no score, no label statistic may be
computed for this study before that merge. One post-merge execution, one
sealed verdict, exactly as v1 — the single-shot machinery (O_EXCL claim,
predeclared sealed result, rerun refused) is REUSED with a NEW predeclared
run dir: `~/renquant-data-store/goal7-momentum-v2-prereg-run/`.**

**Backlog anchor:** model#190. **What changed vs v1 and WHY (the whole
change):** v1's single shot sealed `UNRESOLVED-METHOD` — its AR(1)+
`bootstrap_max` calibration family measured the realized IC dependence
(ρ₁ = 0.9269, oscillatory decay; 40-lag vector published in model#189) and
refused, with no MA collapse permitted. v2 replaces the DEPENDENCE-MODELING
approach with the DEPENDENCE-AVOIDING geometry already validated in Stage-0:
non-overlapping gap-blocks. Candidate, inputs, estimand, placebo discipline,
and decision-map SHAPE are unchanged from v1; every carried-over object is
pinned by digest, not by prose.

## 1. Candidate and inputs — UNCHANGED from v1, carried by digest

- Construction: exactly the merged #161 §2 + #162 protocol as implemented by
  the merged runner lineage (residual momentum vs SPY-TR: window 252, skip 21,
  min obs 200; F1–F5; composite S = equal-weight z-mean, ≥3 of 5; ETFs no F3;
  `total_return_close` from its package home
  `renquant_model_common/total_return.py`, moved verbatim in model#188).
- Inputs resolve THROUGH the base-data fingerprint manifest exactly as
  Amendment 3 froze for v1: dataset_id `momentum-prereg-inputs-20260801`,
  panel `55811f6387e67411fe11a20eb1d5d929086c5a9dc2675496f3d8592fed2c0dba`,
  sector `ec26bb1efcf8463519366478ae72c933f93c9d110d65f8af1634e2fcbb578d3b`,
  combined OHLCV
  `4d4638a9f0d69f940fb36a73c28e92883d51b686ab032aebedf559c174c2c1d0`.
  Verify-then-read, per-file sha256, mismatch/absence = UNRESOLVED-DATA,
  no live-path fallback. The 43 verified non-payers stand as frozen in v1 §2.
- Estimand: per-date cross-sectional Spearman IC of S (and of F1 alone)
  against `fwd_20d_excess`; per-date names floor **50** (below → date skipped
  as `thin`, counted and published).

## 2. Inference — the gap-block machine (REPLACES v1 §4 entirely)

1. **Blocks:** partition the scored-date axis (ascending) into consecutive
   windows of **h = 20** trading dates separated by discarded gaps of
   **h = 20** dates: block k covers dates [k·2h, k·2h + h). With T scored
   dates this yields **n_blocks = floor((T − h) / (2h)) + 1**; at v1's
   realized T = 2378 this is **59** `[DERIVED — floor(2358/40)+1; the
   realized T of THIS run governs]`. Dates skipped as thin do not shift the
   partition: the partition is over the realized scored-date sequence.
2. **Block statistic:** the mean IC within each block (blocks with fewer than
   **10** usable dates are dropped and counted; if fewer than **40** blocks
   survive, verdict = `UNRESOLVED-POWER`).
3. **Test statistic:** the one-sample t over surviving block means (df =
   n_surviving − 1). The gap ≥ h is what buys approximate independence
   between blocks — the standing block-length rule (`L = h` is the defect;
   independence needs a GAP ≥ h).
4. **Bars:** two-sided **t_{0.975, df}** read from Student-t (df-aware, the
   Stage-0/Holm discipline — no borrowed 1.96 on small n; at df = 58 this is
   2.0017 `[DERIVED — scipy.stats.t.ppf(0.975, 58); the realized df
   governs]`).
5. **Adequacy check on the machine itself (teeth, the A4 lesson):** the runner
   computes the lag-1 autocorrelation OF THE SURVIVING BLOCK MEANS. If
   |ρ₁(blocks)| ≥ **0.25**, verdict = `UNRESOLVED-METHOD` (the geometry
   failed to buy independence; published, shot consumed). This is v2's
   refusal valve, mirror of v1's bootstrap_max.
6. **No HAC, no AR/MA fitting, no bootstrap anywhere in the decision path.**

## 3. Placebo and controls — v1 discipline, v2 machine

- **Per-date placebo (unchanged):** 5 seeded within-date label permutations
  (seed **20260801**), centring only; H1 requires placebo mean |IC| < **0.01**.
- **Positive control (adapted to the machine):** a seeded synthetic block
  series with true mean 0.04 and block-sd equal to the REALIZED block-sd must
  clear the bar in ≥ **80%** of 1,000 seeded replications
  (seed 20260801) — run BEFORE the real comparison; failure =
  `UNRESOLVED-METHOD`.
- **Negative control (adapted):** the same generator with true mean 0 must
  clear in ≤ **10%**; violation = `UNRESOLVED-METHOD`.

## 4. Decision map (shape unchanged from v1)

Let t_S, t_F1 be the block-t statistics; bar = t_{0.975, df}; MDE =
bar × SE_blocks.

- `MDE > 0.06` → **UNRESOLVED-POWER**.
- H1: mean IC(S) ≥ **+0.04** AND t_S ≥ bar AND placebo clean. Fail → **KILL**.
- If H1 passes: t_Δ = block-t of (IC_S − IC_F1). |t_Δ| < bar AND F1
  independently clears (mean ≥ 0.04, t_F1 ≥ bar) → **RETAIN-F1**;
  otherwise → **RETAIN-S**.
- RETAIN licenses **shadow only** (orch#699 + D1). KILL closes the line;
  the dossier §2 v-next directions remain available as NEW preregs.

## 5. Execution contract

Single `--execute`; claim before any read; predeclared sealed result at the
NEW v2 run dir; every terminal outcome (including both UNRESOLVED forms)
consumes the shot; pre-inference identity refusals release the claim with a
ledger entry; `tr_builder_importable` preflight check retained. The runner
diff implementing §2–§4 is a SEPARATE PR gated on this document's merge, and
where it and this document disagree, THIS document governs.

## 6. Not claimed / carried risks

- Not claimed: that gap-blocks make the block means exactly independent —
  §2.5 measures and refuses if materially violated.
- Carried: n ≈ 59 is small; the MDE gate (§4) is what says so honestly.
- The v1 sealed result (model#189) is untouched evidence; this study is a new
  question to the same data, declared before looking again.
