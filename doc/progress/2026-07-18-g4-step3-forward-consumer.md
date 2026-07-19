# G4 v4 §5 step 3 — PIT input-parity re-homed as a model-only comparator; forward consumer moved to the umbrella

STATUS: revised after codex CHANGES_REQUESTED (blocking architecture
defect: model → orchestrator reverse cross-repo edge). Phase 0 stays
BLOCKED; no capital deployment, no schedule change, no scheduled job.
Author: hallovorld. Reviewer: haorensjtu-dev.

## Crux finding (report this first)

The first cut of this PR added a **model → orchestrator reverse cross-repo
edge**: `experiments/ensemble_phase0/{backfill_scores,pit_parity_ledger}.py`
imported `renquant_orchestrator.g4_shadow_job.G4EvidenceStore` /
`g4_admission.admit_g4_session`, the CI checked out renquant-orchestrator,
and pytest's `pythonpath` added `../renquant-orchestrator/src`.
`renquant-orchestrator` ALREADY depends on `renquant-model`, so this
reverses the boundary contract and makes the model test environment depend
on an (at the time) unmerged orchestrator API. Codex blocked it; this
revision removes the edge entirely.

The underlying data-hygiene finding is unchanged and correct: under v4 §4
the terminal/inferential series comprises ONLY sessions admitted FORWARD
after the activation commit ("No backfill of pilot, pre-freeze, or
inter-stage sessions into the terminal series under any circumstance"), so
the old close-anchored `runs.alpaca.db` as-of scan (`select_asof_runs` /
`RunSelection` / the DB path) stays RETIRED IN FULL. What changed is
*where* the forward consumer lives.

## Repo-boundary split (the fix)

Per RFC §5 and the codex review, the work splits cleanly along the
boundary:

- **renquant-model keeps the portable, model-only PIT input-parity
  comparator** — `pit_parity_ledger.py`. It defines what "the two frozen
  arms consumed identical PIT inputs" MEANS (a model-domain concept) and
  operates on PLAIN decision-record mappings with a declared data contract
  (see the module docstring). It imports NO orchestrator type, never reads
  the store, never runs admission.
- **The umbrella (`RenQuant`) owns the pinned integration harness** that
  resolves the canonical store, runs admission/registration eligibility,
  applies the forward-only enrollment rule, and feeds the loaded record
  pairs into the model comparator. Design note (part B, spec only):
  `doc/design/2026-07-18-g4-step3-umbrella-forward-consumer.md` in this
  branch's scratch + posted on this PR — NOT implemented here.

## What changed in this repo

- `experiments/ensemble_phase0/backfill_scores.py` — **DELETED** (with its
  test). It was a pure orchestrator-integration consumer: its entire body
  took a `G4EvidenceStore`, called `admit_g4_session`, and layered a
  post-activation gate. There is no model-domain remainder to keep — the
  forward-only enrollment/series-assembly logic is specified for the
  umbrella harness in the part-B design note.
- `experiments/ensemble_phase0/pit_parity_ledger.py` — **rewritten as a
  model-only comparator.** `compare_input_parity(records, *, session_date,
  expected_arms=PARITY_ARMS, contract_integrity=None)` takes plain
  decision-record mappings and returns a `ParityVerdict`. Verdict-bearing
  dimensions are INPUTS only (`input_manifest` digest-equality = v4 §3
  "same manifested information set", `declared_watermark`, frozen
  `calendar_id`/`price_source_id`, `schedule_target`, `schema_version`);
  scorer/artifact digests differ by design ⇒ informational. The
  contract-integrity/watermark gate (`validate_session_records` + the
  byte-level `recompute_watermark_from_store` hook) is NOT run here — it is
  the umbrella's job, and its result is passed in as a plain
  `ContractIntegrity(ok, reason_codes)`. Only stdlib + the
  `renquant_pipeline.decision_schedule` arm-name constants are imported
  (pipeline is a lower-level contract, not the reverse edge).
- `.github/workflows/ci.yml` — the `renquant-orchestrator` checkout step is
  removed; the model CI no longer touches the orchestrator.
- `pyproject.toml` — `../renquant-orchestrator/src` removed from the pytest
  `pythonpath`.
- `tests/test_pit_parity_ledger.py` — rewritten against plain-dict fixtures
  (no orchestrator, no store); includes a guard test asserting the module
  source never references `renquant_orchestrator` again.

## Declared data contract (model ↔ umbrella interface)

`compare_input_parity` consumes, for one decision session:
- `records`: iterable of plain decision-record mappings (the fields the
  canonical job persists: `arm`, `input_manifest`, `declared_input_watermark`,
  `calendar_id`, `price_source_id`, `orders_scheduled_for`, `schema_version`,
  `job_id`, and informational `artifact_digests`/`config_digest`/
  `run_bundle_timestamp`). Failure/unreadable records are skipped.
- `contract_integrity` (optional): the umbrella's `validate_session_records`
  outcome as `ContractIntegrity(ok, reason_codes)`.

Returns a JSON-serialisable `ParityVerdict`. No orchestrator/store/
pipeline-runtime type crosses this boundary.

## Fail-closed shape (no capital-path gate introduced)

Research tooling only; Phase 0 is BLOCKED and the canonical shadow job is
not scheduled. The comparator writes nothing but a report under a
caller-chosen output dir; it never writes a production path or a store.

## Tests

`tests/test_pit_parity_ledger.py`: retirement + no-orchestrator-import
guards; canonical pair = parity; scorer-artifact difference stays parity;
contract-not-evaluated still reports input parity (honest about the
umbrella's gate); contract failure ⇒ not_parity; input-manifest divergence,
watermark/frozen-id/schema/schedule mismatch, missing arm, missing session,
and failure/unreadable skipping all fail closed; ledger build + write with
and without a contract map. `backfill_scores` and its test are gone.

The exact-pinned 4-repo umbrella integration run (v4 §6(a)) is the part-B
umbrella item — NOT run here.
