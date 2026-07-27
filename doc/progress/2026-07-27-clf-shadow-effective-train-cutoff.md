# 2026-07-27 — shadow clf trainer: stamp top-level effective_train_cutoff_date

STATUS:    delivered
WHAT:      scripts/train_topdecile_clf_shadow.py now stamps a TOP-LEVEL
           `effective_train_cutoff_date` on the shadow artifact — the honest
           training-data cutoff, computed FROM THE DATA as the max panel date
           actually trained on AFTER the fwd_60d label dropna (new helper
           `effective_train_cutoff()`; also printed in the run summary).
WHY/DIR:   the first live shadow session (2026-07-27) wrote a DEGRADED health
           record for `topdecile_clf_blend_leg` with reasons
           `['missing_train_cutoff']`: the runtime health check
           (renquant-pipeline `shadow_scoring.py`, ~line 453) reads
           `scorer.metadata.get("effective_train_cutoff_date")`, and the
           deployed artifact does not carry the field anywhere. Placement is
           the whole fix: the runtime `PanelScorer.load` builds
           `scorer.metadata` from TOP-LEVEL payload keys (via
           `stamp_artifact_metadata`), so the field must be a top-level key —
           a metadata-nested copy would surface only through a DEPRECATED
           flatten shim. Top-level is fingerprint-SAFE here (unlike the
           shadow_role/blend_spec/classifier_label_spec lesson in the 07-26
           doc): `effective_train_cutoff_date` is ALREADY classified
           OPERATIONAL in renquant-common's fingerprint tables
           (model_fingerprint.py OPERATIONAL_KEYS, "training-window
           provenance"), so `model_content_sha256` / `config_fingerprint` are
           unchanged by it. Stamped BEFORE `stamp_contract()` so the hasher's
           total-classification check validates the key at train time.
EVIDENCE:
  artifact:      tests/gbdt/test_train_topdecile_clf_shadow.py — 10 passed
                 (3 new: honest-cutoff = max LABELED date on a synthetic
                 panel with a NaN-label tail, not the raw panel max, and
                 refuse on all-NaN; main()'s stamping sequence puts the key
                 at the artifact TOP level, not nested under metadata;
                 fingerprint stability — config_fingerprint identical with
                 and without the stamped key). Full suite: 891 passed,
                 2 skipped.
  prod or exp:   code-only PR; no production write. A regenerated artifact
                 (same flags/data/seed as the deployed 07-26 run, written to
                 a scratch `shadow/` path) was verified OUT-OF-REPO against
                 the PINNED runtime: PanelScorer.load surfaces
                 effective_train_cutoff_date=2026-04-28 in scorer.metadata;
                 config_fingerprint UNCHANGED at
                 sha256:1d8f167fed18cd8cb1e0760251fdd5398724e630462d92b41561d2e19973e41b;
                 booster_raw_json byte-identical to the deployed artifact and
                 smoke predictions (rng 104, 32 rows) exactly equal
                 (max_abs_diff 0.0); the only top-level key diff vs deployed
                 is the added field. Deployment of the regenerated artifact
                 is the coordinator's step, not this PR's.
  existing data: panel alpha158_291_fundamental_dataset.parquet (unchanged
                 since the 07-26 train run, mtime 07-26 10:02); max labeled
                 date after fwd_60d_excess dropna = 2026-04-28 (725,115 rows,
                 2,594 dates — matches the deployed artifact's panel_shape).
  best-known?:   top-level placement cross-checked three ways: the runtime
                 loader's metadata construction, renquant-common's key
                 classification (OPERATIONAL ⇒ hash-excluded), and an
                 empirical model_content_sha256 on a copy of the DEPLOYED
                 artifact with the key added (fingerprint identical).
  scope:         trainer + tests only; authorizes no deployment, touches no
                 live artifact/config/pin. The live shadow artifact swap
                 (scratch-verified bytes above) is a separate coordinator
                 action.
NEXT:      coordinator deploys the regenerated artifact into the live shadow
           slot (fingerprint-stable, prediction-identical ⇒ drop-in); next
           shadow session's health record should then carry
           effective_train_cutoff_date=2026-04-28 instead of
           missing_train_cutoff.
