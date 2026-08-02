# GOAL-6 Stage 0 — RESULTS: H1 REFUTED, H2 REFUTED, both arms; Stage 1–2 keep (IC, 60d)

**Single §7 invocation of the merged runner (model#174) on the amended frozen design
(prereg + Amendments 1–5), 2026-08-01. Verbatim output:
`doc/research/data/2026-08-01-goal6-stage0-results/stage0_output.json`. All numbers
below `[本次实测]` from that file. This is a NEGATIVE result reported with the same
prominence a positive one would get; the tie rule's outcome — keep the incumbent
measurement choices — is the design working, not a failure.**

## Verdicts

| arm | H1 (tail stats beat IC?) | H2 (20d beats 60d?) | Stage-2 hand-off |
|---|---|---|---|
| prod XGB ranker | **REFUTED** | **REFUTED** | **IC @ 60d** (incumbent) |
| certified clf (`cal`) | **REFUTED** | **REFUTED** | **IC @ 60d** (incumbent) |

## Why, in numbers (508 dates; gapped blocks: n_eff 13 @20d, 4 @60d)

**H1 (evaluated at 20d per Amendment 5).** Neither tail statistic clears BOTH frozen
conditions. XGB: `t_pair(spread,IC) = 2.26` vs the Holm-first bar **2.403** (df=12) —
close but short; own-t spread 1.87 / hit 1.45, both under the 2.0 bar. clf: contrasts
1.57/0.31, own-t 1.29/0.73 — nowhere near. REFUTED on the rule's own arithmetic.

**H2 (IC, 20d vs 60d).** (a) fails both arms (t_pair not ≥ 2.0 in favour of 20d);
(b) fails (20d own-t 0.92/0.51 < 2.0). Notably (c) HOLDS both arms — the 20d effect is
SMALLER (XGB d20 +0.0430 vs d60 +0.0542) — the power hypothesis had it backwards here.

**Persistence controls (never reached — H1/H2 are REFUTED on their own conditions,
independently of any veto):** REAL − persistence block t ranged **0.41 – 1.86**.
Naming the cells the vetoes WOULD have examined: for H1's would-be tail winners at
20d — clf spread **1.12** (clears the 1.0 bar), clf hit **0.96** (fails), xgb spread
**0.41** (fails), xgb hit **1.02** (clears); for H2's would-be IC cells — clf
**1.86 / 1.16** (both clear), xgb **0.61 / 0.84** (both fail). So the vetoes were a
mixed bag, and the honest statement is narrower than 'nothing clears': every xgb
spread/IC cell sits at or below 0.84, no cell anywhere exceeds 1.86 (vs the 2.0
own-t bar), and the stale-score-inertia reading rests on those LOW cells — the
verdicts themselves never consulted any of this. Coverage: 448/508 persistence
dates, 100% cell coverage within them.

## Diagnostics (no α budget; stated for the record)

- At 60d the tail Δblock t's look large (XGB spread 2.87, hit 3.08) but sit on
  **df = 3** (Student 97.5% = 3.18; the Holm-family bar there would be 3.74) — the
  honest gap geometry says these resolve nothing, which is exactly why Amendment 5
  put H1 at 20d.
- Raw means for scale: XGB 60d IC +0.0538 (permutation null −0.0004); clf 60d IC
  +0.0296. Across-seed MC noise floor sd ≈ 0.058–0.086 per statistic.
- The corpus-vs-panel label-vintage drift (Amendment 3's Defect 1) decided nothing:
  all labels came from the committed frozen table `b1981eef…`.

## Decision consequence (per the frozen decision-use clauses)

- **Stage-2 primary statistic: IC. Measurement horizon: 60d.** GOAL-6 §3 option A
  (tail-statistic switch) is withdrawn by H1's REFUTED.
- No trading-horizon claim was ever in scope; none is made.
- H3 lag profiles are in the JSON as descriptive output; nothing decides on them.

## Provenance

Preflight (in the JSON): prereg + all five amendments present; labels table
`b1981eef…`; clf table `1da3fcfa…`; XGB corpus canonical content `ba964b40…` verified
on the loaded frame; corpus path recorded. Runner = merged model#174; seeds
20260801+0..19; single invocation, exit 0.
