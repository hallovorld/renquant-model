# Signal Artifact Contract → Self-Describing Envelope

**Date:** 2026-07-12
**Branch:** feat/signal-artifact-contract
**Status:** revised after Codex CHANGES_REQUESTED review (2026-07-13T00:15:21Z, commit 0ec2adb)

## Why this revision

The original implementation (`SignalArtifactContract` + `load_signal_contract()` /
`verify_signal_contract()`) established byte-equality on a file, not trusted
provenance. `producer_run_id`, `schema_version`, and `universe_hash` were
**caller-supplied arguments**, not extracted from the artifact. Any caller
could hash arbitrary bytes and attach arbitrary provenance to them — the
function proved "this digest matches these bytes right now" (tamper
detection after the fact), not "this artifact was genuinely produced by the
real model-scoring pipeline." Codex's review identified this precisely, plus
four related gaps (missing fields for authorization, a verify-then-read
race, no timestamp/path validation, and overclaiming "unblocks #501").

## What changed

The artifact is now a **self-describing, versioned JSON envelope**: every
provenance field is embedded in the artifact's own bytes, so hashing the
bytes and extracting the declared provenance from those same bytes are the
same operation. A caller can no longer supply provenance separately from
content.

- **Renamed `SignalArtifactContract` → `SignalEnvelope`.** The shape changed
  enough (parsed timestamps, session date, signal payload, self-consistency
  digest) that keeping the old name would have been misleading — the old
  class was a caller-asserted contract; the new one is a fully-parsed,
  self-validating payload. `signal_contract.py` keeps its filename since
  Codex's review and the module's purpose (the signal *contract*) are
  unchanged, only its implementation.
- **New envelope schema** (single JSON file, `schema_version: 1`):
  `producer_run_id`, `universe_hash`, `model_content_sha256`,
  `calibrator_content_sha256`, `data_watermark` (tz-aware ISO-8601),
  `decision_timestamp` (tz-aware ISO-8601), `session_date` (ISO-8601 date),
  `signals` (payload, e.g. `{"scores": {...}}`), and a
  `signal_snapshot_digest` computed by the producer over all of the above.
  One JSON file was chosen over a manifest+payload pair — it avoids the
  "manifest digest only covers the manifest" trap by construction, since
  there is only one set of bytes to hash.
- **One function, one read:** `load_and_verify_signal_envelope(path, *,
  allowed_roots=None) -> SignalEnvelope` replaces the old
  construct/re-verify pair. It opens the file once, reads all bytes,
  computes the SHA-256 content digest from those bytes, parses the same
  bytes as JSON, and extracts every provenance field from the parsed
  content — there is no `producer_run_id=...` / `universe_hash=...` etc.
  parameter for a caller to pass (`tests/test_signal_contract.py::
  test_loader_signature_has_no_provenance_args` asserts the signature is
  exactly `{path, allowed_roots}`). The returned `SignalEnvelope` is frozen
  and its `signals` payload is a recursively-frozen mapping
  (`MappingProxyType`/tuples), so there's no verify-then-read race: nothing
  is re-read from disk after validation, and the object a caller acts on is
  exactly what was hashed and parsed.
- **Self-consistency digest:** `signal_snapshot_digest` is computed by the
  producer (`compute_signal_snapshot_digest` / `build_signal_envelope`) over
  the canonical JSON of every other field, and the loader recomputes it from
  the parsed fields, rejecting the file if they disagree. This catches
  hand-edited/partially-tampered envelopes (e.g. someone bumps
  `universe_hash` without touching `signals`) that a raw whole-file hash
  alone would not distinguish from a legitimately different artifact.
- **Path/root allowlist:** `allowed_roots: Sequence[str | Path] | None` —
  when provided, the resolved path must fall under one of the resolved
  roots, checked via `Path.resolve()` + parent-chain membership (not string
  prefix matching, which is bypassable by a sibling directory whose name
  happens to string-prefix the allowed root, e.g. `trusted-evil/` vs
  `trusted/`). `allowed_roots=None` keeps unrestricted behavior, documented
  in the docstring as unsafe for any real trust boundary.
- **Producer-side helpers added:** `build_signal_envelope(...)` and
  `compute_signal_snapshot_digest(...)` let a producer serialize a
  self-consistent envelope directly, addressing Codex's point that "the
  model should publish the signal artifact contract" rather than only
  offering a read-side verifier.
- **Exception hierarchy:** `SignalEnvelopeError(ValueError)` base, with
  `MalformedSignalEnvelopeError`, `SignalEnvelopeSchemaVersionError`,
  `SignalEnvelopeProvenanceError`, `SignalEnvelopePathPolicyError`
  subclasses, plus builtin `FileNotFoundError` for a missing file. All
  validation fails closed.
- **Placeholder blocklist:** mirrors the convention already established in
  orchestrator's `crypto_session.py` (`_is_valid_fingerprint` /
  `_PLACEHOLDER_FINGERPRINT_VALUES`, found on branch
  `feat/crypto-session-scheduler-v2`) — exact-match, case-insensitive,
  against `{missing, unknown, todo, tbd, n/a, na, none, null, nil, fixme,
  changeme, placeholder, xxx, <unset>, unset}` — applied to
  `producer_run_id` and `universe_hash`.

## Codex's 5 points — how each is addressed

1. **"Caller-supplied provenance, not extracted/verified."** Fixed:
   `load_and_verify_signal_envelope(path, *, allowed_roots=None)` takes no
   provenance arguments at all; every field is parsed and validated from the
   artifact's own JSON bytes. Verified structurally by
   `test_loader_signature_has_no_provenance_args`.
2. **"Missing fields for authorizing a D-session signal."** Fixed: the
   envelope schema now carries `model_content_sha256`,
   `calibrator_content_sha256`, `data_watermark`, `decision_timestamp`,
   `session_date`, and the `signals` payload, plus a
   `signal_snapshot_digest` covering all of them — not just a raw file
   digest.
3. **"verify-then-read race (separate open from consumption)."** Fixed:
   single read (`resolved.read_bytes()`), one digest computation, one JSON
   parse, and an immutable returned payload — no code path re-opens or
   re-reads the path afterward. Tested via
   `test_reload_after_mutation_returns_different_result` (two independent
   loads after a file rewrite return different results — no caching bypass)
   and `test_tamper_after_load_is_not_silently_trusted` (mutating the file
   after a load doesn't affect the already-returned object; a fresh load
   fails closed).
4. **"Validate created_utc timezone-awareness / digest formats / path
   policy."** Fixed: `data_watermark` and `decision_timestamp` must be
   timezone-aware ISO-8601 (naive timestamps rejected with
   `SignalEnvelopeProvenanceError`); `model_content_sha256`,
   `calibrator_content_sha256`, and `signal_snapshot_digest` must each be
   64-char lowercase hex; `allowed_roots` provides the path-policy
   allowlist described above (`created_utc` itself was dropped from the
   schema — `data_watermark` and `decision_timestamp` are the two
   timestamps that actually matter for authorization, and `session_date` is
   the third).
5. **"Don't claim this unblocks #501 outright."** This module now proves:
   (a) the returned payload's provenance genuinely came from the artifact's
   own bytes (closing the "caller supplies independent provenance" gap),
   and (b) a `schema_version` contract exists for downstream consumers to
   rely on. It does **not** prove who was authorized to write the file in
   the first place — that is a process/access-control concern for whatever
   writes into the configured `allowed_roots`, outside this module's scope.
   `#501`'s consumer (orchestrator's crypto session scheduler) still has to
   derive its **own** expected signal identity — e.g. compare the
   envelope's `session_date` / `data_watermark` against what the scheduler
   independently expects for the current tick, and compare
   `model_content_sha256` / `calibrator_content_sha256` against the
   model/calibrator it actually has pinned — rather than accepting the
   envelope's self-reported identity as authoritative on its own. That
   comparison logic is out of scope for this module and belongs in the
   orchestrator repo (independently, orchestrator's
   `feat/crypto-session-scheduler-v2` branch already has its own
   `SignalSnapshot`/`SignalArtifactRef`/`validate_signal_contract` — it does
   not yet import from `renquant_model_common`; wiring that up, if desired,
   is orchestrator-side work, not part of this PR).

## Explicitly out of scope (by design)

- Schema migration system: a single `CURRENT_SIGNAL_ENVELOPE_SCHEMA_VERSION
  = 1` constant with hard equality (reject anything else) is used; a
  version-negotiation/migration system is deferred until a real second
  version is needed (noted as a comment in the module).
- Anything that belongs in orchestrator or execution (session gating,
  kill-switches, the scheduler's own expected-identity derivation) — stays
  in the orchestrator repo.
- Proving *who* is allowed to produce a genuine envelope — that's a
  process/access-control question for the deployment layout, not something
  a data-format module can enforce.

## Tests

`tests/test_signal_contract.py` — 65 tests, all passing (Python 3.10.20,
`RenQuant/.venv`), covering: valid round-trip, producer-helper digest
parity, str-path acceptance, no-provenance-argument-surface (structural),
reload-after-mutation divergence, tamper-after-load non-effect on the
already-returned object, allowed_roots accept/reject (including a
traversal-lookalike-prefix sibling-directory case), unrestricted-by-default
behavior, missing file, empty file, malformed JSON, non-object JSON root,
each of the 10 required fields missing individually, schema_version
mismatch (value and type), placeholder producer_run_id/universe_hash
(several placeholder strings each), invalid digest formats for both content
hashes, naive/malformed timestamps, the causal `data_watermark` >
`decision_timestamp` violation (plus an equal-is-allowed case), a
`Z`-suffix timestamp equivalence case, non-dict/empty `signals`, tampered
`signals`/`universe_hash` after the digest was computed (self-consistency
catch), malformed `signal_snapshot_digest` format, frozen-dataclass
immutability, and immutable `signals` mapping.

```
============================== 65 passed in 0.06s ==============================
```

Full repo suite (`python -m pytest -q`, RenQuant `.venv` which has
`torch`): **426 passed, 2 skipped**, no regressions. (The task brief noted
`tests/patchtst`/`tests/gbdt` have pre-existing environment-dependent
collection failures elsewhere; they collect and pass cleanly under this
venv, so no such failures were observed in this run.)
