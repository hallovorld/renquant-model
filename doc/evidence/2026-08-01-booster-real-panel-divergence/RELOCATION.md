# Relocated evidence — same-recipe booster divergence (UNREPRODUCED HISTORICAL MEASUREMENT)

STATUS: **an unreproduced historical measurement with partial surviving
provenance** — NOT a description of production/runtime behavior, and not
currently re-runnable from this archive alone. Its stated role is a
non-performance, preregistration-input record for the GOAL-4/GOAL-8
ensemble premise; nothing here licenses production inference.

RELOCATED 2026-08-04 from `renquant-orchestrator` branch
`goal4/booster-divergence-on-the-real-panel` (PR orch#712, CLOSED
out-of-scope). The closure ruling, verbatim:

> `renquant-orchestrator` owns pinned-subrepo orchestration, and this PR
> hosts model-artifact evaluation. […] What must move, and where:
> 同-recipe boosters 在真实面板上的分歧度量 → `renquant-model`, with the
> source/provenance and the stated non-performance claims carried across.
> If orchestration ever needs the result, it consumes a versioned summary
> artifact, not the evaluator.

## Provenance manifest (the auditability anchor for the byte-verbatim claim)

Source commit OID (both the PR branch and its `o712-wt` twin resolve to
the same commit): `6be4e61dde08ca1f64ffbf44f0934b642fc1e8fc`.

sha256 of every relocated file:

```
0886674bc0582083d31d031363a0cb17416ae1ac96e014aeeacd91093b676fce  CLAIMS-original-progress-doc.md
b5bfffd29286c0d6ceb23e0781f9666559990e4f32c3780cab94eabbf02a6c36  divergence.json
a46ddbb7ecac9a60436f634eb537744bdee2b666292a6d9dfce2627ac314fc93  run.log
8447532275a6d94bc0eae3dfdfd63dcfc9985a3afee7b1deb338574c6069d35a  booster_real_panel_divergence.py
ccd242b493f0fe30b87fd0306268b906811b9a396df2a78a6f467a37ec2207f7  test_booster_real_panel_divergence.py
```

## Why UNREPRODUCED (the honest inventory)

- Inputs are identified by artifact NAMES, one recipe fingerprint
  (`sha256:f8fb2259b…`), and SHORTENED booster keys — no immutable panel
  identity and no full per-artifact content identities are preserved, so
  the exact input set cannot be re-certified from this archive.
- The corpus records `source_space=panel` as a measurement choice, while
  the live serving path uses `raw` — the measurement therefore does not
  even claim to mirror the runtime transform.
- The evaluator is a MACHINE-LOCAL runner (operator machine's live
  artifact tree + panel); preserved as provenance, deliberately not in
  this repo's CI, and not sufficient for replay elsewhere.

## What the historical record claims (summarized; the byte-preserved
`CLAIMS-original-progress-doc.md` is the authored source)

12 distinct boosters under one config fingerprint, scored on the then-live
alpha158 panel's last 20 sessions (2026-04-07 → 2026-05-04): median
top-decile disagreement **35.7%** (median pairwise Spearman 0.854; worst
pair/date 67% replaced). Within its own framing it corrected orch#698's
~60% synthetic figure. Under THIS archive's label, both numbers are
historical measurements of their respective setups — neither is a
statement about current production behavior.
