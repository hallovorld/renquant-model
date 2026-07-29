# Corrected signal evaluation — RESULTS (frozen prereg model#90)

Executed 2026-07-29 on the corrected primitive (model#89); every comparison
pinned to `align_lags(...)` common samples. No deviation from the frozen
design. Wall time 18.2 s. Artifacts: `scratchpad/corrected-eval/`.

## Control check first

The prod XGB is the design's positive control. `d = REAL − persistence` on IC:
**t = +1.229 ≥ 1.0 → FRESH-INFORMATIVE. Control PASSES**, so the other
verdicts are admissible.

Stated plainly: it passes by 0.23 of a t on `n_eff = 8`, and leave-one-block-out
moves it to **[+0.67, +1.94]** — it falls below the bar if any of 3 of the 8
blocks is removed. The sensitivity is real but thin.

## Q1 — does each subject beat its own persistence?

142-name intersection, panel labels, block = 60 score dates, both arms
restricted to the same score dates (T12). `[VERIFIED — corrected-eval/verdict.log]`

| subject | stat | REAL mean (t) | d vs permutation (t) | **d vs persistence (t)** | n_eff | n_dates |
|---|---|---|---|---|---|---|
| prod XGB | IC | +0.0849 (+1.48) | +0.0858 (+1.48) | **+0.0290 (+1.23)** | 8 | 448 |
| prod XGB | spread | +0.4711 (+2.40) | +0.4728 (+2.39) | +0.1166 (+0.97) | 8 | 448 |
| certified clf | IC | +0.0980 (+1.52) | +0.0974 (+1.51) | **+0.0096 (+1.31)** | 10 | 565 |
| certified clf | spread | +0.4563 (+1.92) | +0.4530 (+1.90) | +0.0374 (+0.44) | 10 | 565 |
| PatchTST | IC | +0.0212 (+0.57) | +0.0209 (+0.56) | **−0.0556 (−2.31)** | 10 | 565 |
| PatchTST | spread | +0.2370 (+1.65) | +0.2334 (+1.63) | −0.1286 (−1.28) | 10 | 565 |

**Verdicts:** prod XGB **FRESH-INFORMATIVE** (+1.23) · certified clf
**FRESH-INFORMATIVE** (+1.31) · PatchTST **PERSISTENCE-DRIVEN** (−2.31,
sign-stable under leave-one-block-out at [−2.94, −1.88]).

### Reading the PatchTST result honestly

The mechanical label is PERSISTENCE-DRIVEN, but the mechanism is **not** a
sticky score: PatchTST's lag-60 cross-sectional rank autocorrelation is
**+0.30** against +0.70 (XGB) and +0.79 (clf) `[VERIFIED — robustness.log]`,
so its control arm is close to an independent draw. What the number says is
that PatchTST's **60-trading-day-old score predicts the forward 60d better
(+0.077) than its current score (+0.021)** — its fresh output is worse than
its own stale output. That is a defect in the model, not an artefact of
persistence.

## Q2 — is the lag profile real once the sample is fixed? **PROFILE-WITHDRAWN**

Common-sample IC by lag `[VERIFIED — corrected-eval/results.json]`:

| lag | prod XGB (n=400) | clf (n=484) | PatchTST (n=484) |
|---|---|---|---|
| 0 | **+0.1056** | **+0.1097** | +0.0499 |
| 20 / 40 / 60 | +0.0876 / +0.0658 / +0.0559 | +0.0791 / +0.0476 / +0.0389 | +0.0382 / +0.0329 / +0.0408 |
| 80 / 100 / 120 / 160 | +0.0420 / +0.0386 / +0.0561 / +0.0929 | +0.0180 / +0.0414 / +0.0939 / +0.0916 | +0.0363 / +0.0564 / +0.0874 / +0.0416 |

Best paired lag>0 vs lag-0 t: XGB **−0.13**, clf **−0.13**, PatchTST +0.51 —
**every** paired t is negative for XGB and clf. The size of the original
error, measured: on each lag's own maximal sample XGB reads +0.069 (lag 0) →
+0.097 (lag 120); on the common sample the same profile reads **+0.106 →
+0.056**. The entire apparent rise was sample drift. The parked horizon
prereg (model#88) stays parked.

## Q3 — which statistic carries more power? **INCONCLUSIVE**

The tail spread leads IC for **every** subject (XGB +2.39 vs +1.48; clf +1.90
vs +1.51; PatchTST +1.63 vs +0.56), but no subject clears both frozen bars
(lead ≥ 1.0 AND winner's own t ≥ 2.0). Production keeps IC. This is now the
third independent dataset pointing the same way and it still does not clear a
preregistered bar — a consistent direction is not a licence to switch.

## Disclosures (not in the frozen prereg)

1. `PERSIST_LAG = 60` trading days and `MIN_NAMES = 20` are inherited verbatim
   from model#86 §3.2; the frozen text says "the persistence-matched control"
   without restating them.
2. Comparative tables take labels from the panel uniformly. The clf corpus's
   carried label matches the panel bitwise (max abs diff 0.0); **the XGB pick
   table's does not** — corr 0.9993, 40% exactly equal, max abs diff 1.87,
   concentrated in 2026-02 and in extreme movers (INTC, AMD, MRVL): a vintage
   difference (pick table 2026-07-03 vs panel 2026-07-25). Own-universe rows
   use each subject's carried label; XGB there reads IC +0.0553 with
   `d_vs_persist` t = +1.16 — same verdict.
3. The trailing partial block is kept (dropping it would be an unregistered
   threshold).
4. §3 says "block-level t over folds" while §2 sets block length = label
   horizon; §2's blocks are primary, fold-level t recorded as secondary.
5. Descriptive additions: the maximal-sample lag diagnostic, the
   score-autocorrelation table, leave-one-block-out stability, and a harness
   self-test (oracle+noise → IC +0.398 t=+57.9; pure noise → +0.0004 t=+0.13).

## What this changes

- **First correctly-computed evidence that the two models we rely on add fresh
  information.** Both the trading model and the certified blend leg clear
  their own persistence control.
- **PatchTST's negative is now correctly derived**, and for a sharper reason
  than the retracted verdict claimed. Formal closure still needs its own
  registered kill rule; model#87 is retracted and may not be reused as-is.
- **The horizon story is dead**, cleanly, on a fixed sample.
- **The tail statistic keeps winning and keeps not clearing the bar** — which
  is a power problem, and power is exactly what GOAL-6 Stage 1 (breadth)
  exists to buy.
