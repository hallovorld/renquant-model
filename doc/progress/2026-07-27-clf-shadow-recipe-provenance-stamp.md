# 2026-07-27 — shadow clf trainer: round-8 recipe-provenance stamp

STATUS:    delivered
WHAT:      scripts/train_topdecile_clf_shadow.py now stamps the round-8
           recipe-provenance contract fields TOP-LEVEL, alongside the #83
           cutoff stamp: `provenance_schema_version="v1"`,
           `recipe_id="walkforward_only_v1"`,
           `required_axis_fields=["effective_train_cutoff_date"]` — vendored
           constants with a KEEP-IN-SYNC note pointing at the canonical
           contract (umbrella/pipeline `panel_scorer.py`
           `PROVENANCE_SCHEMA_VERSION` / `RECIPE_REQUIRED_AXES` /
           `stamp_provenance_schema`); this repo must NOT import
           renquant_pipeline. Values also printed in the run summary.
WHY/DIR:   tonight's e2e probe marked both shadows' top_picks NOT ACTIONABLE:
           "artifact does not stamp provenance_schema_version/recipe_id
           (fail-closed, required-recipe-schema, round 8)". The round-8
           admission gate requires the artifact's OWN stamp (never inferred
           from present cutoff fields) and re-verifies the claimed recipe
           against the actually-present axis fields. This trainer's confirmed
           provenance axes are EXACTLY {effective_train_cutoff_date} (#83) ⇒
           `walkforward_only_v1`. Stamping is possible since renquant-common
           0.15.1 (PR #36, merged 20442b6) classified the three keys
           OPERATIONAL — hash-preserving, so `config_fingerprint` cannot
           move. Stamped BEFORE `stamp_contract()` so the total-classification
           hasher validates the keys at train time; on an OLDER
           renquant-common the build fails closed (UnclassifiedKeyError)
           instead of emitting an unfingerprintable or inadmissible artifact.
EVIDENCE:
  artifact:      tests/gbdt/test_train_topdecile_clf_shadow.py — 13 passed
                 (3 new, `skipif` renquant-common < 0.15.1: stamp
                 values+top-level placement replaying main()'s sequence;
                 fingerprint stability WITH the new common — fp identical
                 with/without the full provenance stamp; round-8 recipe
                 resolution — vendored `resolve_recipe_id` taxonomy resolves
                 the trainer's axis set to its stamped recipe_id and the
                 admission re-verification block is satisfied). Full suite:
                 894 passed, 2 skipped (run against merged common 0.15.1).
  prod or exp:   code-only PR; no production write. Regenerated artifact
                 (same flags/data/seed) at a scratch `shadow/` path verified
                 against the PINNED pipeline runtime under BOTH commons
                 (current pinned common AND merged 0.15.1): (a) PanelScorer
                 .load surfaces all three stamp fields +
                 effective_train_cutoff_date=2026-04-28 in scorer.metadata;
                 (b) config_fingerprint UNCHANGED at
                 sha256:1d8f167fed18cd8cb1e0760251fdd5398724e630462d92b41561d2e19973e41b
                 (model_content_sha256 of the new payload == payload minus
                 stamp == deployed); (c) booster_raw_json byte-identical to
                 the DEPLOYED artifact (which is the #83 round-1 regen,
                 sha 6101a9fe...) with exactly-equal smoke predictions
                 (max_abs_diff 0.0); (d) new file sha256
                 1e644354e0981f470d13161a771a0c668ab918124531f9955c037688d607ddf8
                 (abbrev 1e644354e0981f47); top-level diff vs deployed =
                 exactly the three stamp keys; (e) BONUS acceptance — the
                 umbrella copy's own `resolve_recipe_id` plus a replication
                 of shadow_scoring's round-8 admission block on the new
                 artifact's scorer.metadata resolves `walkforward_only_v1`
                 (schema_version_ok / recipe_recognized / recipe_satisfied
                 all True). Deployment is the coordinator's step.
  existing data: same panel as #83 (unchanged, max labeled date 2026-04-28,
                 725,115 rows) — same-data/seed retrain reproduces the
                 deployed booster bit-for-bit.
  best-known?:   canonical taxonomy vendored verbatim from the round-8
                 contract source (umbrella panel_scorer.py, mirrored in
                 renquant-pipeline); renquant-common 0.15.1 is the reviewed
                 classification enabling top-level stamping.
  scope:         trainer + tests + this doc. No live artifact/config/pin
                 touched. NOTE for the deploy batch: the RUNTIME common pin
                 must advance to >= 0.15.1 (20442b6) with the artifact swap
                 so the pinned verifier carries the classification.
NEXT:      coordinator deploy batch: swap the regenerated artifact into the
           live shadow slot + advance the runtime renquant-common pin +
           receipt + probe rerun — next shadow session's top_picks should
           then be admissible under recipe `walkforward_only_v1` instead of
           refused for a missing recipe schema.
