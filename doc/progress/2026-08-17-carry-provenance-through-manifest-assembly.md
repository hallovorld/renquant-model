# Carry provenance through manifest assembly — the 2026-08-15 cutover

STATUS:    delivered, with a NAMED GAP left open on purpose (see the DESIGN
           QUESTION below). Restores this repo's suite, which is red on every
           push since 2026-08-15. No behaviour change for any trainer that
           declares no provenance — those are rejected before and after; what
           changes is that a trainer that DOES declare one is no longer stripped.

WHAT:      Two src carries + five test fixtures.

           src (the real defect):
           * `renquant_model_gbdt/pipelines.py` — `_RUNTIME_ARTIFACT_FIELDS`
             gains `"provenance"`. `BuildArtifactManifestTask` rebuilds the
             manifest from this enumerated allow-list, so a `provenance` key set
             by the trainer was silently dropped.
           * `renquant_model_patchtst/pipelines.py` — the manifest there is a
             fixed dict with no pass-through at all; carry `provenance` from
             `ctx.checkpoint_artifact` when present.

           tests (accurate declarations for synthetic doubles):
           * 5 fixtures gain `"provenance": {"kind": "none"}`.
           * `test_training_pipeline_uses_common_task_job_pattern` gains an
             explicit assertion that the trainer's determination SURVIVES
             assembly, so the allow-list entry has a test of its own rather than
             being covered only incidentally.

WHY/DIR:   `renquant-artifacts` sets `PROVENANCE_REQUIRED_AFTER = date(2026,8,15)`
           and `provenance_required()` returns True unconditionally on/after that
           date (one-way, no env override). Omission no longer counts as a
           lineage determination, so `validate_artifact_manifest` rejects any
           manifest without one.

           The interesting half is not the fixtures. It is that the assembly
           layer **silently drops** a field the layer below it is now required to
           carry: a trainer that correctly declared its lineage would have the
           declaration stripped one layer down and then be rejected for not
           having one. That is an enumerated allow-list quietly changing the
           meaning of its own default. This PR only stops the stripping.

DESIGN QUESTION (deliberately NOT answered here):
           **No trainer in this repo declares any provenance at all** — measured:
           zero occurrences of `"provenance"` and zero of
           `provenance_reference` anywhere in `src/` before this change. So once
           a real retrain reaches manifest assembly, it is rejected, and the
           pass-through fixed here is necessary but NOT sufficient.

           Choosing what a real trained model declares is a governance decision,
           not a mechanical one: `kind="experiment"` requires an
           `_experiment_classification.json` marker plus a registry index;
           `kind="canonical"` requires `run_intent_path`, `run_intent_digest`,
           `artifact_digest == manifest.fingerprint`, prod registry bindings and
           a resolvable publication record; `kind="none"` is admissible only
           while `promotion_status != "prod"`, i.e. it forecloses promotion.
           Picking one decides whether retrained models can reach prod at all,
           so it belongs to whoever owns the promotion guard — I am surfacing it,
           not choosing it.

           NOT currently the binding constraint on live retrains: the 2026-08-17
           gated WF promote chain fails EARLIER, at the orch#799 blend-vs-xgb
           reference rule (`conditional_retrain_104/2026-08-17.log`, "Gated WF
           promote chain FAILED (anomaly_vix_5pct)"; zero provenance hits in that
           log). This defect is latent behind that one and surfaces the moment it
           clears.

EVIDENCE:
  artifact:       src/renquant_model_gbdt/pipelines.py,
                  src/renquant_model_patchtst/pipelines.py, 5 test fixtures
  prod or exp:    prod code path (model artifact assembly), but no live
                  behaviour change today — see "NOT currently the binding
                  constraint" above
  existing data:  main's last green CI is 2026-08-12, BEFORE the cutover date —
                  main CI has not run since, so "last green" is not evidence of
                  health. Measured locally on a clean origin/main sibling
                  worktree instead.
  best-known?:    yes. The allow-list entry is proven load-bearing by deleting
                  it and re-running: the new assertion fails (1 failed) and
                  passes with it (4 passed). Validator behaviour measured
                  directly, not inferred:
                    kind=none      + prod       -> REJECT
                    kind=none      + candidate  -> PASS
                    kind=canonical + prod       -> REJECT (missing
                                                   publication_record_digest,
                                                   registry bindings)
                    kind=canonical + candidate  -> PASS
  scope:          this repo. The same cutover independently breaks
                  renquant-pipeline (28 tests), renquant-backtesting (2, PR #113)
                  and renquant-orchestrator; each is filed in its own repo.
                  renquant-orchestrator additionally DEPENDS on this PR: its
                  `contract_fixture` sets provenance, and its CI checks out
                  renquant-model at main with no ref, so its fixture cannot go
                  green until this lands.

VERIFICATION:
  Run from a SIBLING worktree — `[tool.pytest.ini_options] pythonpath` uses
  `../renquant-*/src`, so a worktree outside `git/github/` fails with unrelated
  ModuleNotFoundErrors that have nothing to do with the change under test.

  pre-fix  (clean origin/main): tests/gbdt + tests/patchtst   4 failed
  post-fix:                     tests/gbdt + tests/patchtst   314 passed
  allow-list entry removed:     1 failed  (proves it load-bearing)

NEXT:      (1) land this; renquant-orchestrator's fixture PR then goes green.
           (2) the DESIGN QUESTION above needs an owner before the orch#799
               blend-vs-xgb blocker clears, or the first successful retrain
               after that will be rejected at manifest validation.
