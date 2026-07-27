# GOAL-4 Phase A — walk-forward-sim -> Phase A inputs converter (XGB expert)   (PR #65)

STATUS:    in-progress
WHAT:      `experiments/ensemble_phase0/build_phase_a_inputs.py` — a
           scorer-agnostic CLI converter from a walk-forward sim to the
           Phase-A score-dir + shared `returns.csv`. **[rework 3, this
           update — codex's blocking review implemented]** The converter
           now consumes the `wf_sim_provenance.v1` JSONL ledger
           (renquant-pipeline
           `doc/design/2026-07-27-wf-sim-provenance-contract.md`, "design
           #215", persistence merged as pipeline#216; umbrella #531 wires
           the sim emit to `data/wf_provenance/<sim_run_id>.jsonl`) as the
           ONLY source of fold/artifact identity, via the new REQUIRED
           `--provenance-ledger` input. Per prediction date, design §2.5
           is implemented exactly:
           (i) the complete `fold_resolved` + `score_committed` pair is
           required, with matching `(sim_run_id, prediction_date)` keys
           and a matching `artifact_digest` echo; orphans (either kind
           alone), non-identical duplicates, `persisted: false`,
           `pit_violation: true`, `is_real_content_digest: false`, and a
           null `input_watermark` are each rejected with a
           machine-readable `{reason_code, detail}` record persisted in
           the build manifest (content-identical duplicates modulo the
           audit clock are accepted as idempotent re-emits, mirroring the
           sink's `_AUDIT_ONLY_KEYS` identity);
           (ii) the score rows are read AT the recorded
           `score_observation_key` (`(run_id, date, run_type)`) from the
           sim DB and the canonical `score_payload_digest` is recomputed
           over exactly what was read back — equality with the committed
           digest plus an `n_rows` match is required. **[round-2 P1-1,
           this update]** The digest is a FIXED versioned vendored copy
           ONLY (KEEP IN SYNC note pinned to pipeline origin/main
           `ac98b502`, identity stamped as `PAYLOAD_DIGEST_IMPL` in the
           build manifest) — renquant-model does not import
           renquant_pipeline, not even guarded (architecture boundary);
           the previous dynamic-import preference is REMOVED. The stored
           test vectors (computed once from the pinned producer revision)
           are the explicit producer/consumer compatibility contract;
           (iii) `select_pit_fold` + `resolve_artifact_digest` are DEMOTED
           to independent cross-checks: any disagreement with the ledger
           identity (including an artifact that cannot be re-hashed) is a
           HARD `CrossCheckMismatchError` quarantining the date and
           aborting before any output is written — never a fallback.
           Output stamping uses LEDGER facts verbatim: `training_cutoff` =
           `fold_resolved.cutoff_date`, `model_content_sha256` =
           `fold_resolved.artifact_digest`, `score_timestamp` =
           `score_committed.score_timestamp` (the SIMULATED decision
           instant, §2.2), `as_of_date`/`data_watermark` =
           `score_committed.input_watermark`. Nothing identity- or
           time-shaped is recomputed at extraction time. Sim-DB dates with
           no ledger record are rejected `no_provenance_record`. Every
           record still carries `classification: EXPLORATORY_ONLY` — the
           containment stays until real rerun evidence exists.
           **[round-2 P1-2, this update]** model#66's per-expert output
           isolation is FOLDED IN: the admissibility ledger + its calendar
           evidence are written under `output_dir/<expert_name>/` (the
           dir already holding that expert's score files + `universe.txt`)
           instead of the shared root, so a second expert built into the
           same `output_dir` cannot clobber the first expert's evidence;
           `BuildManifest` records the isolated `ledger_path`; the shared
           forward-returns CSV stays at the root by design
           (expert-independent label data). #66 becomes superseded once
           this PR lands.
           `tests/test_build_phase_a_inputs.py` — 30 tests: ledger fixtures
           (valid pair; orphaned resolved; orphaned committed; duplicate
           committed non-identical [rejected] / byte-identical +
           audit-clock-only [accepted]; duplicate fold_resolved conflict;
           pit_violation; persisted:false; non-real content digest;
           artifact-echo mismatch; null input_watermark; mixed
           sim_run_ids; wrong schema_version), DB read-back verification
           (pass; digest mismatch; n_rows mismatch), verbatim-stamping
           unit test, cross-check quarantine (identity disagreement;
           unresolvable artifact), vendored-digest STORED producer
           vectors, BDay replay semantics (kept from model#64),
           end-to-end synthetic sim DB + ledger ADMITTED by the canonical
           validator, the two-expert no-clobber isolation regression
           (adapted from #66 to the ledger-backed evidence schema), and
           the fail-closed empty case.
WHY/DIR:   Codex's blocking review on this PR: post-hoc reconstruction of
           which fold/artifact scored which date is inadmissible;
           provenance must be persisted at generation time and the
           converter must consume those persisted facts, with
           reconstruction only as a cross-check. The persistence half has
           now LANDED (pipeline#216 implementing design #215; umbrella
           #531 wires the sim emit), so this update re-bases the converter
           on the merged contract. Stated plainly: the converter now
           REQUIRES a generation-time ledger, and the historical
           558-record sim history has NO ledger — it is therefore
           permanently inadmissible through this path. That is the point
           of the redesign, not a regression: admissible Phase-A evidence
           arrives only from the post-#531 PRE-registered reruns (seeds +
           disposition rule frozen before launch, design #215 §3.5).
EVIDENCE:  artifact:      experiments/ensemble_phase0/build_phase_a_inputs.py
                          (converter) + tests/test_build_phase_a_inputs.py
           prod or exp:   experiment (`experiments/ensemble_phase0/`,
                          output explicitly `EXPLORATORY_ONLY`, never fed
                          into a champion/L1 promotion decision)
           existing data: n/a — no model/data performance number is
                          claimed; the prior real-data conversion run
                          (149 dates / 116 admitted) is SUPERSEDED and
                          void: that sim predates the provenance sink, so
                          its output is inadmissible through the reworked
                          converter by construction
           best-known?:   n/a
           scope:         "experiment tooling + unit tests, not a
                          performance claim; correctness is proven by the
                          test suite + the canonical validator's admission
                          verdict on synthetic fixtures — no real-data
                          admission claim can exist until a post-#531
                          rerun emits a ledger"
           `python -m pytest tests/test_build_phase_a_inputs.py
           tests/test_phase_a_runner.py tests/test_admissibility_ledger.py`
           -> 312 passed, 0 skipped (the round-2 P1 pass removed the
           conditional imported-equivalence test — the digest contract is
           now import-free by design — and added the #66-derived
           isolation regression); full repo suite 888 passed, 2 skipped.
           Codex's baseline on the pre-rework head was 293 on the same
           three files — no regression, +19 net new tests. [VERIFIED]
NEXT:      - SANCTIONED FOLLOW-UP (separate PR, NOT this one; codex
             round-2 P1-1): canonicalize the score-payload digest into
             renquant-common (same pattern as
             `walk_forward_fold_selection`) so pipeline#216's emit side
             and this converter both consume ONE implementation instead
             of producer + pinned vendored copy.
           - umbrella #531 (sim emit wiring) merges; then the XGB
             multi-seed rerun runs under a frozen prereg doc (seeds +
             disposition rule BEFORE launch) producing the first
             admissible ledger-backed corpus; PatchTST rerun remains
             compute-gated (no-Modal rule stands).
           - #66 is superseded by this PR (its isolation fix is folded in
             per codex round-2 P1-2); it closes once this PR lands.
           - The `EXPLORATORY_ONLY` classification stays on every record
             this converter emits until that rerun evidence exists and is
             re-reviewed.
