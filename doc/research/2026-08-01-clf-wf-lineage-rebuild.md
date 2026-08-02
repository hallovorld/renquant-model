# clf WF corpus rebuilt WITH per-fold artifact persistence + lineage manifest (GOAL-6 Job A, model#180)

## What this delivers `[本次实测 2026-08-01]`

The renquant-backtesting#94 Stage-1b on-ramp: the certified clf recipe now has a
**gate-consumable lineage** —

- **43/43 fold artifacts persisted** (17 MB total), each self-carrying the #94
  admissibility fields: feature contract (`feature_cols/means/stds`), `cutoff_date`,
  `cutoff_embargo_days: 60`, `effective_train_cutoff_date`, OOS window, seed, and the
  booster bytes — mirroring what the gbdt window artifacts already carry.
- **Lineage manifest** per the merged #94 identity model:
  `lineage_root_sha = e9eefe813785ca719e0b7e1fc40ae96488dee42102a9e98eb6e3954db601606b`
  (`sha256(recipe_src_sha256 + LF + LF-joined ordered fold shas + LF)`), recomputed
  from the on-disk artifacts at verification time — **MATCH**.
- The rebuilt score corpus (178,191 rows / 43 folds / 625 OOS dates / 292 names —
  counts IDENTICAL to the frozen original) with its own provenance manifest.

## Vintage honesty (stated, not hidden)

The rebuild read TODAY's panel (`55811f63…`, recorded at read time in the manifest);
the frozen 07-29 bundle was built on `7c0c6447…`, which no longer exists on the live
path. Consequences, measured: the rebuilt corpus's byte sha differs from the original
(`46f447fd…` vs `1da3fcfa…`), **87.5% of the 178,191 `cal` values are byte-identical**,
max |Δ| = 0.062, mean 4.9e-4 — consistent with the 58.5% label-vintage drift measured
on model#160's thread. **Neither corpus replaces the other**: the 07-29 bundle stays
the frozen historical record; this bundle is the current-vintage lineage the gate lane
consumes, self-pinned to its own input digest.

## Tool provenance

`tools/wf_clf_corpus_rebuild_persist.py` is the committed closure-bundle driver copied
with exactly two additions (per-fold persistence; the lineage manifest) — the recipe
and corpus arithmetic are byte-unchanged, and the diff against the original driver is
reviewable in this PR. Wall time 216.3 s (original: 217.7 s). One serialization fix
during development (mu/sd are arrays, zipped with feat_cols) — caught by the 2-fold
smoke before the full run.

## What this unblocks

renquant-backtesting#94 Stage 1b: the clf recipe can now enter the candidate-scoring
gate's shadow stage on equal terms with gbdt (whose 43/43 window artifacts were
measured already on disk). Next: the gate lane implementation consumes both lineages.
