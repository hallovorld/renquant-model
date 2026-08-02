# GOAL-7 residual momentum v2 — the single execution's verdict: UNRESOLVED-METHOD (control gate)

**The one licensed v2 invocation ran 2026-08-02 and terminated at §3.1(d):
positive-control clear-rate 0.5590 against the frozen 0.80 floor (negative
control 0.0250, inside its 0.10 ceiling). H1/H2 were never evaluated; nothing
is licensed and nothing is killed. The shot is consumed and sealed (result
sha256 `9414edab…`), committed byte-verbatim in
`doc/research/data/2026-08-02-goal7-momentum-v2-result/` (force-added past the `data/`
ignore rule as this repo's results bundles are).**

## The refusal, in numbers `[VERIFIED — result.json]`

- 2,378 scored dates → 59-block gap partition; realized_block_sd (ddof=1)
  **0.14496**; bar t_{0.975,58} = 2.00172.
- Positive control (Normal(0.04, 0.14496), n=59/rep, PCG64 20260801+r,
  1,000 reps): clear-rate **0.5590** — the machine detects a TRUE 0.04 only
  ~56% of the time at this block variance. Frozen floor 0.80 → refuse.
- Negative control: 0.0250 ≤ 0.10 — the false-positive side is healthy.
- Cross-check the refusal is arithmetic, not accident: SE = 0.14496/√59 =
  0.01887; noncentrality for μ=0.04 is 2.12 vs bar 2.00 → theoretical power
  ≈ 0.55 `[DERIVED — one-sided t power at df 58]`. The measured 0.559 is the
  same number. The machine is honest and the gate did exactly its job.
- Notable: the MDE ceiling would have PASSED (bar×SE = 0.0378 < 0.06) — the
  positive control caught what the 0.06 ceiling was too loose to catch.
  Published but unused: placebo_mean_abs 0.0484.

## What two sealed refusals now say together

v1 (model#189): the dependence structure defeats AR(1) calibration. v2 (this
document): after switching to the dependence-avoiding geometry, the SAME
panel's block variance leaves the frozen 0.04 target underpowered at the
frozen 0.80 detection floor. Two different honest machines, two refusals,
zero peeks at H1 — the conclusion is about the QUESTION, not the candidate:
**T = 2,378 dates of this panel cannot answer "mean IC ≥ 0.04 at h=20" with
honest inference at these standards.** A third null family on the same
estimand would be method-shopping and is not proposed.

## Options forward (operator decision material, no recommendation ranking)

1. **Different candidate, same door** — the dossier §2 v-next directions
   (vol-conditioned momentum-reversion; factor-momentum residualization) are
   different constructions whose block variance may differ; each enters as a
   fresh prereg.
2. **Different question** — e.g., a longer measurement horizon (h=60 halves
   the block count but may raise per-block signal) or a different estimand
   (top-decile spread, the Stage-0 finding that tails move when ranks do
   not). Any such change is a NEW prereg with its own power arithmetic
   computed BEFORE freezing (the v2 lesson: run the §3 positive-control
   arithmetic against plausible sd at design time).
3. **Stop the standalone-momentum line** and bank the two sealed negatives —
   the operator's dossier preserves everything for a future re-entry.

## Chain provenance

Prereg model#191 (frozen c280d32d) · runner model#192 (implemented the frozen
text with an EMPTY delta; three declared readings reviewer-confirmed) ·
inputs by digest from the v1 chain (store 294/294, manifest base-data#60) ·
executed once, sealed, rerun refused.
