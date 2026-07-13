# Signal Artifact Contract

**Date:** 2026-07-12
**Branch:** feat/signal-artifact-contract
**Unblocks:** orchestrator PR #501 (crypto session scheduler)

Added `renquant_model_common.signal_contract` -- a frozen, content-addressable
contract for signal artifacts. The orchestrator session scheduler consumes this
to verify signal integrity before acting on model outputs.

- `SignalArtifactContract` (frozen dataclass) with SHA-256 content digest
- `load_signal_contract()` computes digest from artifact bytes
- `verify_signal_contract()` re-reads and re-hashes to detect tampering
- `__post_init__` validates all fields (non-empty strings, hex format, version >= 1)
- 16 tests covering happy path, tamper detection, error paths, validation, immutability
