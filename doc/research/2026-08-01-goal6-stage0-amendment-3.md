# GOAL-6 Stage 0 — Amendment 3 (visible, PRE-RUN): label vintage and block geometry

**Amends exactly three clauses of the frozen Stage-0 prereg
(`2026-07-28-goal6-stage0-prereg.md`). Filed before any execution; Stage 0 has not
run. Amendments 1 and 2 (the H2(c) band suspension) are untouched and compatible:
this amendment shares no clause with either. Both defects were found by measurement, not taste, and both follow the momentum
chain's precedent: a frozen rule that measurement shows defective gets a visible
amendment, never a runner-level reinterpretation.**

## Defect 1: the design is silent on label VINTAGE, and the two candidate sources disagree

§2 freezes "Labels: `fwd_20d_excess` and `fwd_60d_excess`, both already present" —
present on the PANEL. The corpus (`data/exp/oos_pick_table_recipe_v2.parquet`, frozen
2026-07-03) carries its own `fwd_60d_excess` and NO 20d column, so the 20d arm must
read the panel regardless. Measured `[实测 2026-08-01, model#160 thread]`: corpus vs
today's panel on all 147,066 (date,name) pairs — **58.5% differ beyond 1e-9**
(byte-equal 41.5%, corr 0.999579, max |Δ| = 1.87 on INTC; all 292 tickers affected in
every period). The corpus labels are a stale vintage of the same estimand: silently
mixing them with panel labels would put two label vintages inside one paired test —
the exact shape of the fund-freshness clip bug. Also measured today: the two candidate
panels (`transformer_v4_wl200_clean`, `alpha158_291_fundamental_dataset`) agree
**byte-for-byte** on `fwd_60d_excess` over their full 354,258-row intersection
(max |Δ| = 0.0), so "the panel" is well-defined for labels.

**Amended rule:** ALL decision-statistic labels — both horizons, both model arms, and
every null — are read from ONE panel file in ONE pass at execution:
`data/transformer_v4_wl200_clean.parquet` (the file §2 already names), whose sha256 is
recorded in the run output at read time. The corpus supplies ONLY
`score`/`decile_rank`/`regime`. The corpus's own `fwd_60d_excess` is demoted to a
DIAGNOSTIC (its divergence from the panel label may be reported as a data-vintage
observation; it decides nothing).

## Defect 2: §4's block construction is the L = h geometry the program's own erratum rules unsupported

§4 freezes `block length = ceil(h / rebalance spacing) = h` with non-overlapping
h-day blocks. The 2026-07-30 erratum (`doc/research/2026-07-30-erratum-block-length-
equals-horizon.md`) measured exactly this scheme: adjacent h-blocks of dates still
share label windows (boundary crossing ≈ 1.0), and the realized size at nominal 0.05
was **0.2162 / 0.1034** on the two measured designs; the repaired scheme (a GAP ≥ h
between consecutive blocks) measured **0.047–0.051**. The Stage-0 prereg was frozen
2026-07-28, two days BEFORE the erratum — it inherited the defect, and yesterday's
independent audit flagged the same geometry riding the corrected-eval bundle.

**Amended rule:** block-level decision statistics use gap-separated blocks — length
`h` trading days with a GAP of `h` trading days between consecutive blocks (so no two
blocks share any label window); `n_eff` is the gapped block count and every table
states it. The no-gap L = h numbers may be published as diagnostics only, clearly
labelled. The already-frozen `SE_HAC` estimator (Newey-West, Bartlett, lag = h_min−1)
is untouched.

## Defect 3: arm (b) has no scores in the corpus §2 points both arms at

§2 freezes "Both score against the existing corpus
`data/exp/oos_pick_table_recipe_v2.parquet`" — measured `[实测 2026-08-01]`: that
table's manifest records its `score` column as the XGB prod recipe's output ONLY;
the certified top-decile classifier has no scores there. As frozen, arm (b) is
unexecutable. The classifier's out-of-sample scores DO exist, committed in this repo:

**Amended rule:** arm (b)'s scoring table is
`doc/research/data/2026-07-29-clf-wf-closure-bundle/artifacts/clf-wf/clf_wf_scores.parquet`
(committed; sha256 `1da3fcfab06af1e597ac0eb83dff4741ed3dd027de8b8a6b4d58979f5bc4efe4`), score column **`cal`**
(the calibrated output the blend leg serves; `raw` may be reported as a diagnostic),
restricted to the 508-date Stage-0 window — coverage measured: **508/508 dates ×
292/292 names per date** (the file spans 625 OOS dates; the intersection is complete).
Its own `fwd_60d_excess` column is demoted to a diagnostic exactly as Defect 1 demotes
the XGB corpus's — all decision labels come from the single panel read.

## Not amended

Everything else: the 3×2 statistic/horizon grid, both nulls (within-date permutation;
persistence-matched control with its frozen alignment rules), the paired contrast with
Holm-Bonferroni, H2's hard numeric gate, the T1–T8 trap checklist, XGB-only scope with
PatchTST out of scope, and the separate-results-PR rule (§6).

## Not claimed

That either defect changed any published number — Stage 0 has never run, which is why
these are amendments and not errata. That the corpus's stale labels are WRONG — they
were correct at build time; the panel has since been recomputed from revised prices
(attribution to a specific data change is NOT established). That gap-separated blocks
are optimal — they are the erratum's measured-safe repair, chosen over per-study
bootstrap calibration to keep this amendment surgical.
