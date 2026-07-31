# GOAL-4's second member is scoring live from a checkpoint its own health record calls `fault`

**Bottom line `[本次实测 2026-07-31]`.** The shadow PatchTST scorer's own health records —
four consecutive live runs, 2026-07-27 through 07-29 — all report **`status: fault`**,
with reason `stale_623d_limit_28d`. And on every one of them it **scored every
candidate anyway**.

| run_date | status | reason | n_candidates | n_scored | skip_reason |
|---|---|---|---:|---:|---|
| 2026-07-27 | **fault** | `stale_621d_limit_28d` | 80 | **80** | `None` |
| 2026-07-28 | **fault** | `stale_622d_limit_28d` | 77 | **77** | `None` |
| 2026-07-28 | **fault** | `stale_622d_limit_28d` | 78 | **78** | `None` |
| 2026-07-29 | **fault** | `stale_623d_limit_28d` | 78 | **78** | `None` |

`effective_train_cutoff_date: 2024-11-13` on all four; `content_sha256` identical
(`sha256:07046963994dbb8d…`).

## What is and is not claimed

**The detection works.** The record computes the staleness correctly, names the policy
it violates (`limit_28d` — the *"NO model >28 days"* freshness rule), and marks `fault`.
Nothing here is a failure of measurement.

> **The fault is advisory.** `skip_reason` is `None` and `n_scored == n_candidates` on
> every run. A record that says *fault* while the thing keeps producing the output
> downstream reads is the shape this programme keeps paying for — here in its mildest
> and most defensible form, because a shadow lane arguably *should* keep producing so it
> can be measured.

**Not claimed:** that this is a bug. Whether a fault should stop scoring depends on
whether any consumer treats shadow scores as usable, and I have not established that.

**What IS claimed, and it is enough:** if PatchTST is to be an ensemble member, the
scores it would contribute **today** come from a checkpoint **623 days past a 28-day
limit** whose own health record says `fault`. That is a fact about GOAL-4's member #2
that belongs beside its `−0.0556 (t = −2.31)`, and it was in the evidence bundle without
being in any document.

## Where it was, and why it had no home

It sits in `doc/research/data/2026-07-30-patchtst-closure-v2/` —
`shadow_scorer_health_hf_patchtst.jsonl` and `identity_evidence.json`, produced by the
closure-v2 run. The closure progress doc contains **zero** mentions of `fault` or `623`
`[本次实测]`, and **correctly so**: it confined itself to the frozen prereg's questions
and must not add unregistered claims. So these facts were measured, written to disk, and
never surfaced. This document is their home.

## The other number in the same bundle

`trained_date: 2026-05-22` against `effective_train_cutoff_date: 2024-11-13` — a **556-day
gap between when the checkpoint was trained and the newest data it saw**. A 60-day
embargo does not explain a gap that size. **Flagged, not explained** — I have not
established what produced it, and a plausible-sounding reason is not a measurement.

Tests: 4, pinned to the frozen health records.
