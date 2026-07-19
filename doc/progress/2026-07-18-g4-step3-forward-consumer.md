# G4 v4 §5 step 3 — score backfill + PIT parity re-homed onto the merged contracts

STATUS: delivered (tooling + tests). Phase 0 stays BLOCKED; no capital
deployment, no schedule change, no scheduled job. Author: hallovorld.
Reviewer: haorensjtu-dev.

## Crux finding (report this first)

Under the merged v4 amendment's §4 data hygiene, **the score "backfill"
has NO inferential role left.** The terminal/inferential series comprises
ONLY sessions admitted AFTER the activation commit, produced by the
canonical shadow job (orchestrator step 2) running FORWARD ("No backfill
of pilot, pre-freeze, or inter-stage sessions into the terminal series
under any circumstance"). The old `backfill_scores.py` did exactly the
prohibited thing: it scanned the close-anchored `runs.alpaca.db` history
and manufactured a candidate series from PRE-FREEZE sessions (whose 15–20
accrued shadow sessions are additionally disqualified by prior analytical
exposure, model#58/#59). Its private close-anchored as-of helper
`select_asof_runs` is precisely what v4 §5 subsumes into the
pipeline-owned decision-schedule API ("no private cross-repo as-of helper
survives anywhere").

**Decision: the tool becomes a read-only FORWARD CONSUMER of the canonical
G4 evidence store + a fail-closed series assembler.** The `runs.alpaca.db`
scan, `select_asof_runs`, `RunSelection`, `--score-column`, per-date
candidate-evidence JSON, and local ledger build are RETIRED IN FULL —
there is no database code path at all, so a legacy row is *structurally*
incapable of feeding the inferential series. Diagnostic coverage of the
burned pre-freeze sessions is out of scope (v4 §4 already disqualifies
them; model#58/#59 already produced the descriptive read; re-reading them
would only re-manufacture the burned exposure).

## What changed

- `experiments/ensemble_phase0/backfill_scores.py` — rewritten as the G4
  forward series consumer. CONSUMES step-1 `renquant_pipeline.
  decision_schedule` (`validate_arm_record` / `validate_session_records` /
  `SessionWindow` / `job_identity`, pipeline#209) and step-2
  `renquant_orchestrator.g4_shadow_job.G4EvidenceStore` +
  `g4_admission.admit_g4_session` (orch#551). `admit_g4_session(...,
  persist=False)` gives the authoritative read-only verdict (nothing is
  written to the store — admission EXECUTION stays the orchestrator's per
  §5). Enrollment into the inferential series requires ALL THREE gates:
  1. **canonical-store provenance** — a missing/forged/tampered/divergent
     record or a watermark after close makes admission `admissible=False`
     ⇒ `REFUSED`;
  2. **registration binding** — the step-2 `series_eligible` flag (True
     only when the frozen calendar-id + price-source-id are supplied and
     match); this tool READS it, never mints it;
  3. **post-activation data hygiene** — the model-side gate this tool
     adds: `decision_session` strictly AFTER the frozen `activation_session`
     (v4 §4). A pre-freeze / pre-activation or unregistered session is
     demoted to `DIAGNOSTIC_ONLY` (discussable, never enrolled).
  `INFERENTIAL_SERIES_CANDIDATE` is reachable ONLY through all three; a
  closing structural invariant (`SeriesIntegrityError`) re-checks the
  enrolled set fail-closed.
- `experiments/ensemble_phase0/pit_parity_ledger.py` — rewritten. Parity
  is now between the two frozen arms (l1 / champion) of ONE canonical
  store, not prod-vs-shadow `runs.alpaca.db` bundles selected by commit
  order. Verdict-bearing dimensions are INPUTS only (`input_manifest`
  digest-equality = v4 §3 "same manifested information set",
  `declared_watermark`, frozen `calendar_id`/`price_source_id`,
  `schedule_target`, `schema_version`), gated by
  `validate_session_records` with the BYTE-LEVEL watermark hook
  (`recompute_watermark_from_store`). Scorer/artifact digests differ by
  design ⇒ informational, never verdict-bearing. The old `decision_skew`
  dimension is GONE: both arms are produced in one canonical job run from
  one input set, so cross-arm commit skew is not an input-parity signal.
  `select_asof_runs` import + `RunSelection` + both DB scans retired.
- `tests/test_backfill_scores.py`, `tests/test_pit_parity_ledger.py` —
  rewritten as the v4 §6 adversarial acceptance set (below), using
  synthetic canonical-store fixtures built by the real step-2 job
  (`run_g4_shadow_session`) — no invented historical data.
- `pyproject.toml` — pytest `pythonpath` gains `../renquant-orchestrator/src`
  so the (research-only) ensemble consumer can import the step-2 store +
  admission ledger. Both step-2 modules are import-light (stdlib + a lazy
  `renquant_common.market_calendar`); nothing in the model factory itself
  depends on the orchestrator.

## Fail-closed shape (no capital-path gate introduced)

This is research tooling; Phase 0 is BLOCKED and the canonical shadow job
is not scheduled, so a forward run today enrolls ZERO sessions — the
correct fail-closed state (no activation commit + no forward canonical
sessions exist yet). The tool never writes a production path or the store;
it reads the store and writes a report under a caller-chosen output dir.

## Tests (v4 §6 acceptance)

`tests/test_backfill_scores.py` (all green): retirement of the as-of
helper + DB path (attribute + import checks); forward canonical
registration-bound post-activation session ENROLLED with series_eligible;
pre-activation / equal-to-activation / no-activation-registered session
REFUSED from the series (diagnostic-only); unregistered (no frozen ids) not
series_eligible; forged non-canonical record REFUSED; missing session
REFUSED; job-identity determinism (record job_id == recomputed identity;
stable re-evaluation); no leakage (an input event-time AFTER close ⇒
`watermark_after_close` ⇒ REFUSED; a pre-close input is clean); series
assembly enrolls only candidates + the structural-invariant guard;
report/CLI plumbing (the real-NYSE CLI path is `importorskip`-guarded and
runs in CI).

`tests/test_pit_parity_ledger.py` (all green): retirement checks;
canonical pair = parity; scorer-artifact difference stays parity;
input-manifest divergence, missing arm, missing session, frozen-id
mismatch, and watermark-after-close all fail closed; ledger build + write.

Locally: 28 passed, 1 skipped (the pandas-gated real-NYSE CLI test) under
a minimal py3.10 venv exercising the two files against merged-main
pipeline#209 + orch#551 checkouts. NOTE: the exact-pinned 4-repo umbrella
integration run (v4 §6(a)) is a later umbrella-stage item — NOT run here.

## v4 ambiguity noted for the reviewer

§5 says the model backfill "consumes that contract" (singular = the
pipeline public API) while step 2 assigns the evidence store + admission
execution to the orchestrator. This step therefore imports BOTH the
pipeline contract and the orchestrator's store/admission reader (a
backwards model→orchestrator edge, confined to `experiments/`, not the
factory). The alternative — re-implementing the store reader + admission
rule inside the model repo — would itself be a "private cross-repo helper"
of the kind v4 forbids, so reuse of the owner's read-only surface
(`persist=False`) was chosen. Flagging for confirmation.
