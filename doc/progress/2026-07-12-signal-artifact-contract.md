# Signal Artifact Contract → Producer-Authored Envelope

**Date:** 2026-07-12
**Branch:** feat/signal-artifact-contract
**Status:** revised twice after Codex CHANGES_REQUESTED review
(2026-07-13T00:15:21Z, commit 0ec2adb)

## History on this PR

1. **`0ec2adb`** — original implementation. `SignalArtifactContract` +
   `load_signal_contract()` / `verify_signal_contract()`. Codex flagged that
   `producer_run_id`, `schema_version`, and `universe_hash` were
   **caller-supplied arguments**, not extracted from the artifact — any
   caller could hash arbitrary bytes and attach arbitrary provenance to
   them. This established byte-equality (tamper detection after the fact),
   not trusted provenance.
2. **`e7716ff`** — a concurrent session's fix (pushed to this same branch
   while this revision was independently in progress; reconciled here
   rather than overwritten — see "Reconciling a concurrent push" below).
   Replaced the API with `load_and_verify_signal_artifact(artifact_path) ->
   (SignalArtifactContract, bytes)`: the artifact is now a JSON manifest,
   every provenance field is extracted from the parsed manifest (not caller
   args), the file is read exactly once and both the contract and the raw
   bytes are returned (closing the verify-then-read race), all digest
   fields are validated as 64-char lowercase hex, and both timestamps must
   be timezone-aware. 68 tests.
3. **This commit** — a small follow-up on top of `e7716ff`, after
   independently re-verifying its diff against each of Codex's 5 points
   (see "Independent verification" below) and finding three genuine,
   empirically-confirmed remaining gaps. Fixes only those three; everything
   `e7716ff` got right is left as-is.

## Independent verification of `e7716ff`

Checked out `e7716ff` fresh in an isolated worktree and ran its own test
suite (`68 passed`), then read the actual source (not just the commit
message) and wrote small proof-of-concept scripts exercising the real
checked-out code for each of Codex's 5 points:

1. **Provenance extracted from the artifact, not caller args.** CONFIRMED —
   `load_and_verify_signal_artifact(artifact_path: str)` takes only the
   path; every provenance field (`producer_run_id`, `schema_version`,
   `universe_hash`, digests, timestamps, `session_date`) is read from the
   parsed JSON manifest.
2. **Fields needed to authorize a D-session signal.** CONFIRMED present:
   `model_content_digest`, `calibrator_content_digest`, `data_watermark`,
   `decision_timestamp`, `session_date`, `signal_snapshot_digest`. (Gap
   found in how `signal_snapshot_digest` is *checked* — see below.)
3. **Verify-then-read race.** CONFIRMED fixed — one `read_bytes()` call;
   contract and payload both derive from that one read; own tests
   (`test_replacement_after_verify_uses_stale_payload`,
   `test_mutation_after_load_does_not_affect_payload`) demonstrate this, and
   the function body has only the one read call.
4. **Timestamp timezone-awareness, digest formats, path policy.**
   PARTIALLY confirmed: naive timestamps are genuinely rejected; all four
   digest fields are genuinely format-checked as 64-char lowercase hex.
   **Gap:** "path policy" was only a negative `..`-traversal string check —
   there was no positive allowlist mechanism, so a caller could still point
   at any absolute path outside any trust boundary.
5. **Honesty about unblocking #501.** **Gap:** neither the progress doc nor
   the PR body were updated by `e7716ff` — both still described the old,
   no-longer-existing `load_signal_contract()`/`verify_signal_contract()`
   API and still flatly claimed "Unblocks #501" without the caveat Codex
   asked for. Fixed in this revision (see below).

### Three gaps found and empirically demonstrated (not just read from source)

Ran proof-of-concept scripts against the actual checked-out `e7716ff` code:

- **No `allowed_roots` mechanism.** `load_and_verify_signal_artifact` had no
  parameter to restrict loading to a trusted directory. Demonstrated:
  loading a manifest from an arbitrary temp directory outside any
  configured trust boundary succeeded unconditionally — the only guard was
  rejecting literal `..` path segments, which does not stop an absolute
  path to anywhere else on the filesystem.
- **`signal_snapshot_digest` was format-checked but never recomputed /
  verified for self-consistency.** Demonstrated: loaded a manifest with an
  arbitrary, format-valid digest (`"c" * 64`, unrelated to any other
  field); then changed `universe_hash` to a tampered value while leaving
  that same stale digest in place — both loaded successfully with no
  error. The field carried no real integrity guarantee.
- **`signals` (the actual scored payload) was never type/content-validated
  and was not exposed on the returned contract.** Demonstrated: manifests
  with `"signals": "just a string"` or `"signals": null` loaded
  successfully; `hasattr(contract, "signals")` is `False` — a consumer
  must independently re-parse the raw `payload` bytes and know to reach
  into `["signals"]` themselves.

## What this commit adds (only the three gaps above)

- **`compute_signal_snapshot_digest(...)`** — single source of truth for the
  canonical digest formula (`schema_version`, `producer_run_id`,
  `universe_hash`, both content digests, both timestamps normalized to UTC
  ISO-8601, `session_date`, `signals`, all as sorted-key JSON, SHA-256
  hex). Exported so producers can call the *same* formula rather than
  hand-rolling their own and risking drift — this repo's own institutional
  history (`model_content_sha256` triple-hand-copied-implementation
  incident) is exactly the failure mode a shared formula avoids.
- **Self-consistency check in the loader.** After parsing all fields
  (including `signals`), `load_and_verify_signal_artifact` recomputes the
  expected digest via `compute_signal_snapshot_digest` and rejects the
  artifact (`ValueError: signal_snapshot_digest mismatch...`) if the
  manifest's declared value disagrees. A single hand-edited field can no
  longer hide behind an untouched, stale-but-well-formatted digest.
- **`signals` type validation.** Must be a non-empty JSON object, or the
  load fails closed (`ValueError`). (Kept minimal: still returned only via
  the raw `payload` bytes, matching `e7716ff`'s existing return shape —
  restructuring the return type to also expose a typed `signals` field was
  judged out of scope for a small follow-up; noted as a residual ergonomic
  gap below, not a safety gap.)
- **`allowed_roots: Sequence[str | Path] | None = None` parameter** on
  `load_and_verify_signal_artifact`. When given, the resolved absolute path
  must fall under one of the resolved roots, checked via `Path.resolve()` +
  parent-chain membership (`root in resolved.parents`) — not string-prefix
  matching, which a sibling directory like `trusted-evil/` next to
  `trusted/` would bypass. `None` (default) preserves `e7716ff`'s existing
  unrestricted behavior, documented in the docstring as unsafe for any real
  trust boundary.
- **Test fixture fix required by the above:** `_make_manifest()` in the
  test file now computes a real, self-consistent
  `signal_snapshot_digest` via `compute_signal_snapshot_digest` by default
  (previously every test manifest used a fixed placeholder like `"a" * 64`
  unrelated to its own fields — harmless before the self-consistency check
  existed, but would fail every test once it did). Explicitly passing
  `signal_snapshot_digest=...` still overrides verbatim, for tests that
  deliberately exercise mismatch scenarios.
- **12 new tests** (68 → 80): `TestSignalsPayloadValidation` (not-a-dict,
  null, list, empty-dict rejected), `TestAllowedRootsPolicy` (unrestricted
  default, accept under root, reject outside root, reject a
  traversal-lookalike sibling-prefix directory, multiple roots any-match),
  and rewritten `TestMismatchedSnapshotMetadata` (two different
  self-consistent manifests have different digests; a tampered field with
  a stale digest is rejected; a tampered `signals` payload with a stale
  digest is rejected; valid self-consistent round-trip). Two pre-existing
  tests whose premise the new check invalidated were fixed rather than
  deleted: `test_load_roundtrip`'s digest assertion now compares against
  the manifest's own computed value instead of a hardcoded placeholder,
  and `test_signal_snapshot_digest` was repurposed to check a genuinely
  self-consistent (not arbitrary) digest extracts correctly.

## Reconciling a concurrent push

While this revision was in progress in an isolated worktree, a separate
session pushed `e7716ff` to this same branch, attempting the identical
fix in parallel. Per the coordinator's instruction, this was NOT silently
overwritten: the diff was independently read and its claims verified by
running its own tests and writing proof-of-concept scripts against the
actual checked-out code (not trusting the commit message). Genuine gaps
were found (above) and this commit fixes only those, fast-forwarded on
top of `e7716ff` — nothing from that commit was reverted or reimplemented.

## Codex's 5 points — final status

1. **Caller-supplied provenance, not extracted/verified.** Fixed by
   `e7716ff`: no argument surface for a caller to supply
   `producer_run_id`/`universe_hash`/`schema_version`/etc — everything
   comes from the parsed manifest. (Note, applies equally to `e7716ff` and
   to this follow-up: `SignalArtifactContract` remains a public dataclass
   that *can* still be constructed directly with arbitrary fields, bypassing
   the loader. This is inherent to using a plain dataclass and is
   documented as "construct only via the loader" rather than mechanically
   enforced — a residual, shared characteristic, not something this
   follow-up changes.)
2. **Missing fields for authorizing a D-session signal.** Fixed by
   `e7716ff` (fields present) + this commit (`signal_snapshot_digest` now
   actually verified, not just format-checked; `signals` now
   type-validated).
3. **Verify-then-read race.** Fixed by `e7716ff` — single read, contract +
   raw bytes both derived from it, no re-open.
4. **Timestamp timezone-awareness / digest formats / path policy.** Fixed
   by `e7716ff` (timezones, digest formats) + this commit (`allowed_roots`
   allowlist, closing the gap where only `..`-traversal was blocked).
5. **Don't overclaim "unblocks #501."** This module proves: (a) the
   returned contract's provenance genuinely came from the artifact's own
   bytes, (b) `signal_snapshot_digest` is now a real, verified
   self-consistency check over the other fields (not decorative), and (c)
   a scheduler can restrict which directories it will ever load from via
   `allowed_roots`. It does **not** prove *who* was authorized to write a
   genuine artifact into those directories in the first place — that is a
   process/access-control concern for whatever writes into the configured
   `allowed_roots`, outside this module's scope. `#501`'s consumer
   (orchestrator's crypto session scheduler) still has to derive its own
   expected signal identity — e.g. compare the loaded contract's
   `session_date` / `data_watermark` against what the scheduler
   independently expects for the current tick, and compare
   `model_content_digest` / `calibrator_content_digest` against the
   model/calibrator it actually has pinned — rather than treating the
   artifact's self-reported provenance as authoritative on its own. That
   comparison logic is out of scope for this module and belongs in the
   orchestrator repo. (Independently: orchestrator's
   `feat/crypto-session-scheduler-v2` branch already has its own
   `SignalSnapshot` / `SignalArtifactRef` / `validate_signal_contract` and
   does not yet import from `renquant_model_common` — wiring that up, if
   desired, is orchestrator-side work, not part of this PR.)

## Explicitly out of scope / residual, honestly noted

- `signals` is validated for type but still only reachable via the raw
  `payload` bytes returned alongside the contract (not a typed field on
  `SignalArtifactContract` itself) — a consumer must
  `json.loads(payload)["signals"]`. This is an ergonomic gap, not a safety
  one (no re-read from disk is involved), and was left as-is to keep this
  a small, targeted follow-up rather than a return-shape redesign.
- No producer-side envelope-*builder* convenience function beyond
  `compute_signal_snapshot_digest` (which is sufficient for a producer to
  construct a compliant manifest, just requires assembling the dict by
  hand).
- Schema migration system: a single equality check against
  `schema_version == 1` (via the existing `>= 1` + digest-formula
  agreement) is deemed sufficient for now; a real migration system is
  future work if/when a second version is actually needed.
- Anything that belongs in orchestrator or execution (the scheduler's own
  expected-identity derivation, kill-switches, session gating) stays in
  the orchestrator repo.
- Proving *who* is allowed to write a genuine artifact — a
  process/access-control question for the deployment layout, outside what
  a data-format module can enforce.

## Tests

`tests/test_signal_contract.py` — **80 passed** (Python 3.10.20,
`RenQuant/.venv`):

```
============================== 80 passed in 0.07s ==============================
```

Full repo suite (`python -m pytest -q`, same venv, which has `torch` so
`tests/patchtst`/`tests/gbdt` collect and run too): **441 passed, 2
skipped**, no regressions.

## Revision note (round 5, 2026-07-13) — 3 bugs found in a concurrent fix for the same Codex findings

A concurrent session pushed 5dc9bb6 addressing Codex's 3 round-4 findings
(unknown schema version, causal timing invariant, non-finite JSON) —
independently verified against the real code (not just the commit
message) and found 3 genuine remaining gaps:

1. **Timezone bug**: `session_date != decision_timestamp.date()` compares
   against `decision_timestamp`'s date in WHATEVER offset it happens to
   carry, not necessarily UTC. Proved empirically: a `decision_timestamp`
   of `2026-07-12T23:30:00-05:00` (US Eastern) is
   `2026-07-13T04:30:00+00:00` in UTC — local date `07-12`, UTC date
   `07-13` — and the buggy comparison accepted `session_date="2026-07-12"`
   despite the crypto RFC's UTC-calendar-day session convention
   (`renquant_orchestrator.crypto_session.SessionWindow`) meaning it
   should have been rejected. Fixed to
   `decision_timestamp.astimezone(timezone.utc).date()`.
2. **Incomplete signal-value validation**: the finiteness check only fired
   for `isinstance(value, float)` — a string, `None`, or `bool` value
   never matches that check (bool is an `int` subclass, not `float`) and
   passed straight through untouched despite Codex's ask to "validate
   signal values/keys against the declared signal schema." Replaced with a
   comprehensive check: keys must be non-empty strings, values must be
   finite, non-bool `(int, float)`.
3. **`__post_init__` not updated**: the `SUPPORTED_SCHEMA_VERSIONS` check
   (and the causal-timing/session-date invariants) were only added to
   `load_and_verify_signal_artifact` — a direct
   `SignalArtifactContract(schema_version=2, ...)` construction bypassing
   the loader could still smuggle an unsupported version through the old
   `>= 1` check alone. Added the same 3 checks (schema version, timing
   invariant, session-date binding) to `__post_init__`, with the correct
   UTC-aware comparison from the start this time.

`_make_contract`'s test fixture had the same class of bug as an earlier
round: it hardcoded `session_date=date(2026, 7, 12)` alongside
`decision_timestamp=_NOW` (the real wall-clock time when tests run) — a
mismatch whenever the suite runs on any day other than exactly that one.
Fixed to derive `session_date=_NOW.astimezone(timezone.utc).date()`
dynamically.

10 new tests: UTC-vs-local-offset session_date rejection/acceptance (at
both load and direct-construction), string/None/bool signal-value
rejection, empty-string signal-key rejection, int-signal-value acceptance
(a valid finite type, distinct from bool), and unsupported/bool
schema_version rejection at direct construction.

`tests/test_signal_contract.py`: **100 passed** (was 90; +10 net).
