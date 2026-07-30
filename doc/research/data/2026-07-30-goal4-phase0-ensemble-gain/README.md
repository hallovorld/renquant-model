# GOAL-4 Phase-0 ensemble-gain screen — execution artifacts

Executes `doc/research/2026-07-30-goal4-phase0-ensemble-gain-prereg.md`
(renquant-model#114) literally. Code: `tools/goal4_phase0_manifest.py` (§2.5
seal) + `tools/goal4_phase0_run.py` (§3–§6). This directory: `manifest.json`
(sealed, §2.5), `results.json`, `run.log`, three per-date CSVs.

**Verdict: VOID.** See `results.json.void_reasons`. Withheld pending
adversarial review per §7 — see the results doc under `doc/research/` for
the appended review.

## §2 identity — construction note (read this before the numbers)

Production scorers on this programme are walk-forward retrained on a
rolling schedule (model-freshness governance: no model >28 days old); a
single served checkpoint can only validly score dates inside its own
post-training-cutoff window without lookahead, so no single checkpoint can
generate a multi-year historical panel. §2's "served artifact identity
established from serving output or emitted metadata" is therefore
operationalised at the RECIPE level — this is the SAME construction
model#90 (cited approvingly by this prereg's own §1) used, not a new
relaxation invented for this run:

- **prod_XGB**: served artifact = `artifacts/prod/panel-ltr.alpha158_fund.json`
  (confirmed wired via `strategy_config.json` → `gbdt/panel_ltr.artifact_path`),
  `config_fingerprint=sha256:f8fb2259b2bf1537`. ALL 43 folds of the
  historical WF panel's underlying artifacts carry this exact
  `config_fingerprint` — verified directly, not asserted (43/43 match).
- **PatchTST**: served artifact = `artifacts/patchtst_shadow/pt07_strict_trainfit_embargo60_20260522/seed_44/hf_patchtst_all_seed44_model.pt`
  (confirmed wired via `strategy_config.json` → `ranking.panel_scoring.artifact_path`),
  file sha256 independently recomputed and matched against its own emitted
  `.metadata.json.artifact_sha256`, `config_fingerprint=sha256:f8fb2259b2bf1537`
  (same recipe fingerprint as prod_XGB — same watchlist/config family).
  ALL 43 folds of the historical WF panel: file sha256 == fold metadata's
  emitted `artifact_sha256` (43/43) AND fold `config_fingerprint` ==
  served identity (43/43) — both independently verified.
- **certified_clf**: served artifact = `artifacts/shadow/panel-clf.top-decile.fwd60.json`,
  `config_fingerprint=sha256:1d8f167f…e41b`; content sha256 independently
  recomputed as `1e644354e0981f47…`, matching the value independently
  stamped in `doc/progress/2026-07-28-umbrella-blend-scorer-kind.md` (a
  different PR, different session) — corroborating evidence, not
  self-citation. **Weaker evidence trail than the other two members**: the
  WF corpus driver never persisted a per-fold `config_fingerprint`, so
  identity for the historical panel rests on a byte-exact match of the
  RECIPE SOURCE SCRIPT (`scripts/train_topdecile_clf_shadow.py`,
  sha256 `04cba8a42429…` — identical between what built the WF panel and
  current `renquant-model` main) plus exact hyperparameter/label/
  lookahead/feature-count agreement, not a per-fold digest. Disclosed as
  the primary attack surface for adversarial review; not treated as
  grounds for exclusion, since identity IS established from emitted
  metadata, just at coarser granularity.

No member was excluded (3/3 survive the identity gate as operationalised
above).

## Label corpus selection — a real, verified discrepancy

`data/alpha158_291_fundamental_dataset.parquet` (mtime 2026-07-29) was used
as the canonical `r_{t→t+h}` source for ALL THREE members, not each panel's
own bundled `fwd_60d_excess` column, because a cross-check found the
prod-XGB panel's (`data/exp/oos_pick_table_recipe_v2.parquet`, mtime
2026-07-03) bundled label diverges from it on **58.5% of the 147,066
overlapping (date,ticker) rows** (86,017/147,066 not bit-exact; mean abs
diff 0.0019, max abs diff 1.87 —
187 percentage points on realized 60-day excess return), consistent with
the XGB panel being built against a since-superseded label vintage.
The chosen corpus matches the certified-clf panel's bundled label EXACTLY
on all 88,750 overlapping rows, and matches the older, narrower
`transformer_v4_wl200_clean.parquet` watchlist panel to <1bp on
353,406/353,548 rows — i.e. it is the current, internally-consistent
vintage, and clf's own panel was already built against it (or an
indistinguishable predecessor).

## Why VOID (§5.1, both independently sufficient)

1. **Construction assertion fails.** Realised mean per-date Spearman IC of
   the synthetic positive-control member = **0.03681**, outside the
   required `[0.04, 0.06]` band (`|0.03681 − 0.05| = 0.0132 > 0.01`). Per
   §5.1 this alone means "the construction is broken and the screen
   VOIDs" — α was NOT adjusted (frozen at 0.0523538966).

   Diagnosed, not just observed: an isolated Monte-Carlo check (pure
   iid-normal `r`, no real data, 3000 trials per n) of the EXACT same
   rankit/arcsin construction shows a systematic finite-sample bias that is
   inherent to the formula, not a bug in this execution —
   `ρ_s=(6/π)arcsin(ρ/2)` is an asymptotic (n→∞) identity between the
   Pearson correlation of two continuous bivariate-normal variables and
   their population Spearman correlation; `u` and `e` here are finite
   rankit (order-statistic) transforms, not continuous draws, and the
   realized mean Spearman IC under this construction converges to 0.05
   only as n grows:

   | n | mean realised Spearman IC (3000 trials) |
   |---|---|
   | 20 | 0.0067 |
   | 50 | 0.0343 |
   | **140** | **0.0424** |
   | 500 | 0.0483 |
   | 2000 | 0.0493 |
   | 10000 | 0.0497 |

   The actual per-date cross-section here is 141.3 names on average (min
   98, median 142) — squarely in the biased regime. The idealized
   iid-normal expectation at n=140 (0.0424) is itself borderline-outside
   tolerance; the realized 0.03681 on real returns is a further, modest
   step down, plausibly from non-normal return distributions interacting
   with the same finite-n effect. This is a property of the FROZEN
   construction at realistic cross-sectional widths, not an implementation
   defect — reported plainly per instructions, not routed around.

2. **Even granting construction, the control is not detected.** Combined
   equal-weight with the benchmark, the control's own `|t| = 0.0988`, far
   below `T_crit = 2.3646` (`n_blocks=8`, student-t-bound). The benchmark
   (prod_XGB alone) has its own mean per-date IC ≈0.054 — comparable in
   magnitude to the synthetic's ≈0.037-0.05 and UNCORRELATED with it by
   construction (synthetic is built independent of any real model) — so a
   50/50 rank-average blend does not reliably beat the stronger single arm
   at only 8 blocks of statistical power. This is exactly what the control
   is FOR: it shows the harness, as specified (equal-weight combination,
   `n_blocks=8`), cannot confirm even a genuine, deliberately-inserted gain
   under current data — so the main arm's own `UNRESOLVED`-shaped result
   (`t=-1.00`, `|t|` far under `T_crit`) would have been uninformative even
   had the construction passed.

## Everything else, for the record (not decision-relevant given VOID)

- Main arm: `N_eval=508`, `n_blocks=8`, dropped=28, `t=-1.0025`,
  `T_crit=2.3646` (student-t leg; `P95_null=1.9131`). `|t|` sits at the
  0.70 quantile of the permutation null.
- §5.2 null false-pass rate: 4.0% of 200 permutations exceeded `T_crit`
  (ceiling 10%) — would have passed on its own.
- §5.3 non-tautology: permutation changed the per-date statistic on 100% of
  dates, every one of the 200 seeds — would have passed on its own.
- §5.4 redundancy (descriptive only): certified_clf vs prod_XGB mean
  pairwise Spearman 0.768 (very high — the two GBDT-family members largely
  agree); PatchTST vs prod_XGB 0.404; PatchTST vs certified_clf 0.517.
