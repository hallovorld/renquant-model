# GOAL-4: the ensemble premise, re-evaluated on doubly-derived evidence

**Status: assessment, not a prereg. Nothing here runs anything or changes any surface.**
Every load-bearing number below has an independent second derivation (operator's
double-audit directive, 2026-08-01); the audit verdicts are cited inline.

## The premise, decomposed

"A multi-model ensemble is worth building" requires three preconditions. They now have
different, measured answers:

### P1 — members must differ enough to combine: **HOLDS** `[早前实测, 审计 UPHELD]`

Twelve same-recipe prod-lineage boosters disagree on **35.7%** of the real top decile
(median pairwise overlap 0.6429, reproduced independently to three decimals), worst
pair-date replacing **67%** (overlap exactly 1/3), against high whole-list agreement
(Spearman ~0.854). Consensus structure exists: 66.9% of top-decile slots held by ≥7/12
majorities, 25.9% unanimous. Diversity is a precondition, not evidence an ensemble
works — but the precondition is met with room.

### P2 — the admitting gate must distinguish members: **FAILS** `[本次实测, 审计 UPHELD]`

15 of 15 distinct stamped artifacts carry `candidate_artifact_used = false` (byte-grep
control: 138 `false`, 0 `true`); 13 of 15 share one recipe fingerprint. The gate that
admits capital is recipe-hashed and never scores the candidate's own booster — so it
cannot tell apart the very members whose 35.7% disagreement is P1. **Any ensemble built
today would be admitted by a gate blind to which member (or blend) it is serving.**
Related decay of the evidence chain: the prod artifact's WF manifest and its override
rollback both point at deleted `/tmp` paths (orch#726).

### P3 — a valid evaluation instrument for "does combining help": **PROPOSED, NOT YET USABLE**

The prior combiner evidence is E55: NGB-on **lost** a 27-month A/B by −3.78 APY pts /
−0.14 Sharpe, and its written reactivation gate (`pure_alpha ≥ +0.04`) names a quantity
with **zero producers** on any main; the whole `panel_ltr.ngboost` node is wired to
nothing (three fields, three dead ends — orch#725/#729). Meanwhile the inference machinery an honest re-test would need has been PROPOSED this
session — the #162 null-construction protocol (an approved DISCUSSION draft: no frozen
constants, no executable implementation) and the #164 freeze candidate (under review,
validity unresolved). **Neither is a usable instrument today.** An ensemble contrast can
be evaluated validly only after a consumer preregistration freezes the protocol's
constants for that contrast AND a runner implementing it exists — the same two steps the
momentum lane is itself still completing.

## The re-evaluated conclusion

**The binding constraint on GOAL-4 is P2, not P1.** Member diversity is real and
measured; what is missing is a gate that can see members. Sequencing that follows:

1. **First (renquant-backtesting boundary):** candidate-artifact scoring in the WF gate —
   the `candidate_artifact_used=false` fix. Until it lands, an ensemble cannot even be
   *admitted* as itself, and Phase-0 outcomes could not alter what serves.
2. **Second (this repo):** draft, review and FREEZE an ensemble-contrast
   preregistration instantiating #162 (paired blend-vs-best-single contrast, worst-case
   calibrated bar), plus its runner — the two artifacts without which no valid
   evaluation exists. This step also replaces the unfalsifiable `pure_alpha` gate with
   produced quantities (orch#729). **Nothing in this assessment authorizes running it**;
   it authorizes drafting it, after step 1's gate fix has an owner.
3. **Not before either:** any new combiner training. E55's loss stands as the prior;
   `[早前实测]` and nothing here revisits it.

## Not claimed

That an ensemble would help — P1 is compatible with twelve models sharing one blind
spot, and no forward-return statistic is computed here. That P2's fix is small; it is
gate-owning-repo work with its own review trail. That the consensus core (25.9%
unanimous slots) is investable signal; it is structure, measured label-free.
