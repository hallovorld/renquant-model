# Momentum artifacts stamp the identity the admission check reads

STATUS:    Implemented. 6 new tests, full suite 1539 passed.

WHAT:      `renquant_model_momentum.train` gains `params_config_fingerprint()`
           and stamps `config_fingerprint` as a TOP-LEVEL artifact key.

WHY/DIR:   s104#95 asked to backfill `expected_config_fingerprint` into two fast
           lane configs. Reading the consumer shows that cannot work:

             model_admission.py:196-199
               actual = artifact.get("config_fingerprint") ...
               if not actual: return _reject("missing_config_fingerprint")
               expected = cfg.get("expected_config_fingerprint") ...

           The identity is read from the ARTIFACT; the lane config only supplies
           the value it is compared against, and is never reached when the
           artifact carries none. Measured on the live fast artifact: 22
           top-level keys, `config_fingerprint` absent. So both fast blend legs
           were rejected one step earlier than the issue assumed.

           Form is `momentum-<params_version>-<sha256(canonical params)[:16]>`,
           byte-for-byte `renquant_pipeline.momentum_identity.params_fingerprint`
           — the module that exists so the umbrella's stdlib-only pinned-path CI
           can validate the same string. This repo does NOT import it at runtime
           (`renquant-model` does not depend on `renquant-pipeline`); the copies
           are pinned equal by a test instead.

EVIDENCE:  artifact:      `tests/test_momentum_config_fingerprint.py` (6 cases)
           prod-or-exp:   producer only; emits no orders and changes no config
           existing-data: `pytest tests/ -q` -> 1539 passed, 0 failed
                          `[VERIFIED — 2026-08-07]`
           best-known?:   yes. The alternative considered and rejected was
                          importing the consumer copy, which would add a
                          model -> pipeline runtime dependency in the wrong
                          direction.
           scope:         `params_version` is read from INSIDE `params`, where
                          the ledger (`ledger.py:159`) and `artifact_kind_for`
                          also read it. I first reported that key as absent by
                          checking the top level — the test
                          `test_params_version_comes_from_inside_params_not_top_level`
                          pins the depth so the same mistake fails loudly.

           Reverse check: shortening the digest slice to [:15] turns the
           consumer-equality test and the form test red; the other four stay
           green. The equality test RAN (not skipped) — verified with `-rs`.

NEXT:      1. Existing artifacts are not retro-stamped. `artifacts/momentum_fast/
              2026-08-06/momentum_residual_v0.json` still lacks the key, so the
              fast legs stay rejected until a re-emit. That is a rerun, not a
              hand-edit of a published artifact.
           2. Only then does a config-side `expected_config_fingerprint` have
              anything to compare against. s104#95 should be re-scoped to
              "re-emit, then pin", not "backfill".
           3. NOT DONE: the panel producer still stamps no binding data cutoff
              (`run_model_freshness_monitor.sh` reports `prod-panel UNKNOWN,
              fail-closed`), which is what orch#745's deferred 28-day ceiling
              waits on. The momentum producer already stamps `cutoff_date` and
              `effective_train_cutoff_date` — a working example in the same fleet.
