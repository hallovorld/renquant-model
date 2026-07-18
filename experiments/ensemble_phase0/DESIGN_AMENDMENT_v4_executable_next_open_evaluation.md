# Amendment v4: executable next-open evaluation and evidence integrity

Date: 2026-07-17
Status: RFC amendment to the base design, v2, and v3. v3 is retained as a
record of the rejected design. Supersession boundary (r2, explicit):
this amendment REPLACES v3 §B (decision schedule), §C (evaluation
design), and §E where in tension — specifically §E1's shared
`select_asof_runs` helper is SUBSUMED by the pipeline-owned public
schedule/validation API (§5 here); no private cross-repo as-of helper
survives anywhere. v3 §A (findings/motivation) and §D (feasibility
posture) stand as historical record; v3 §F's non-changes are restated by
§5-§6 here. v3 §B's "the 16 structurally-excluded sessions become
evaluable" expectation is REVOKED for inference (§4 data hygiene).
Phase 0 remains BLOCKED. No capital deployment or schedule change is
authorized.

## 1. Why v3 is not sufficient

v3 correctly rejected close-anchored qualification for a post-close process,
but it introduced three new gaps:

1. "last committed before next open" selects an output by mutable commit order,
   not by a verified information set.
2. A daily portfolio-difference label is not an executable return definition
   without holdings, fills, cash, costs, missing-leg behavior, and price-source
   rules.
3. Importing G1's `LB90 > 0` machinery would again permit an economically
   trivial effect to advance the ensemble.

The experiment is a prospective paired operational comparison, not randomized
causal evidence. Its result applies only to the frozen L1/champion pair and
the declared execution process.

## 2. One canonical next-open observation

For decision session T, a qualifying record for each arm must have all of:

- immutable `decision_session=T`, declared input watermark no later than the
  official close of T, and a complete input/artifact/universe manifest;
- a run-bundle timestamp in `(close(T), open(T+1))`, but timestamp is evidence
  only, never the information-set proof;
- a frozen, versioned calendar and price-source identifier;
- a declared order set scheduled for the first regular-session open of T+1;
- a deterministic job identity for `{arm, T, artifact digests, config digest}`.

There is exactly one canonical job identity per arm/session. Retried jobs must
have byte-identical decision and input digests. Divergent duplicates, a
watermark violation, or a missing arm make the session an integrity failure;
they cannot be resolved by selecting the latest commit.

**Failure budgets (r2 — two separately pre-registered budgets, replacing
the self-contradictory single rule).** Two session-count budgets are
frozen at the pilot-registration commit, before any collection:

- `B_idio` — idiosyncratic single-arm failures (job crash, missing arm,
  divergent retry, asymmetric valuation/fill/price failure per §3).
  Proposed: ceil(5% of the phase's planned sessions), per phase (pilot
  and terminal each).
- `B_shared` — documented shared venue/calendar outages, including the
  §3 common price-source failure (both arms equally affected).
  Proposed: ceil(10% of the phase's planned sessions), per phase.

Every failed session is INADMISSIBLE to the d_t series, recorded with
its cause class and evidence, and counted against exactly one budget
(asymmetric → `B_idio`; symmetric/shared → `B_shared`). While both
cumulative counts stay within budget the experiment continues; EXCEEDING
either budget is a terminal `NO-GO (integrity — <budget> exhausted)`.
Both consequences are integrity verdicts, not performance verdicts.
Admissibility and budget accounting are decided from the failure records
alone, BEFORE any return series is unblinded — a session is never
dropped, added, or reclassified after returns are observed.

**Watermark verification (r2, mechanism).** The declared input watermark
is not self-certifying: the pipeline-owned validation API recomputes the
maximum event-time over the manifested inputs (resolved by digest) and
an admission REQUIRES declared == recomputed; any mismatch is an
admission failure counted against `B_idio` for that arm. The §6(b)
late-watermark adversarial test exercises exactly this recomputation.

The PIT parity ledger is **not** schedule-agnostic: it must be rerun against
these exact watermark, universe-membership, artifact-selection, and execution
fields. Its report is an input to admission, not a substitute for it.

## 3. Executable paired return definition

Each admitted arm starts with the same declared notional at the T+1 open.
For arm a, its one-session net return is:

`r_a,T = (marked_value_a at open(T+2) - starting_notional) / starting_notional`.

Marked value includes filled holdings, residual cash, dividends/financing if
applicable, and all declared execution costs. Costs use the frozen model and
realized fills when available; a bar proxy is labelled a proxy and cannot be
used to authorize capital. Every observation persists order/fill IDs, weights,
turnover, unfilled quantities, price timestamps/source digest, cost components,
and a cash reconciliation. `d_T = r_L1,T - r_champion,T` is computed only
from those immutable records. A common price-source failure invalidates both
arms and is counted; an asymmetric valuation/fill failure follows §2.

The champion is a single frozen artifact/configuration digest, selected before
pilot collection. L1 is the single frozen equal-weight combination. L2-L4 are
out of scope; no ladder choice, hyperparameter search, or alternate benchmark
may be added to this family without a new registration and predeclared
multiple-testing treatment.

## 4. Calibration, power, and terminal rule

**Two-stage start (r2).** (1) A PILOT-REGISTRATION commit freezes the
schedule, universe, artifact IDs, cost model, terminal rule, MEE,
planning effect, block rule, both failure budgets (§2), the terminal
sample-size rule, and the burned-sessions manifest below; it authorizes
ONLY blinded pilot collection. (2) The ACTIVATION commit — computed from
the sealed pilot — freezes T and the §4 simulation outputs and starts
the terminal series. Neither series can run unregistered.

At least 40 parity-admitted paired sessions are a separately manifested,
arm-label-blinded calibration pilot. They cannot enter the terminal series or
any performance claim.

**Data-hygiene exclusions (r2 — pre-freeze sessions are burned):**

- The pilot admits ONLY sessions generated under the frozen §2 contract
  AFTER the pilot-registration commit (prospective-only manifest). The
  15–20 accrued shadow sessions are DOUBLY inadmissible: they were
  generated under the old close-anchored contract, and their coverage
  and admission behavior have already been analyzed (model#58/#59) —
  prior analytical exposure disqualifies them from any inferential
  series. v3 §B's expectation that "the 16 structurally-excluded
  sessions become evaluable" is REVOKED for inference: they may be
  discussed descriptively, never enrolled.
- The TERMINAL series comprises ONLY sessions admitted after the
  activation commit (post-activation-only clause). No backfill of pilot,
  pre-freeze, or inter-stage sessions into the terminal series under any
  circumstance.
- The pilot-registration commit carries a burned-sessions manifest
  enumerating every pre-freeze session and the analyses that touched it
  (model#58/#59); the activation commit discloses this exposure. The
  manifest, not prose, is the auditable object.

**Blinding mechanism (r2, explicit).** The sizing analysis receives a
DEMEANED, arm-label-blinded d_t series (per-series mean removed before
delivery, one global random orientation applied), so neither the sign
nor the magnitude of the mean can leak; it may estimate dispersion and
dependence only. The unblinding key is sealed until the pilot report and
activation commit are both immutable. Pilot means, signs, arm PnL, and
provisional tests stay sealed.

`MEE = 2 bps/session` is only valid after a written sleeve-level economic
rationale covering expected turnover, costs, capital, and opportunity cost.
The planning effect must be predeclared strictly above MEE; absent a justified
value, the study is infeasible rather than tuned from pilot outcomes.

**Block rule and simulation DGP (r2, stated now).** The MBB block-length
RULE is `b = ceil(1.75 × max_holding_days)` capped at 40 sessions, fixed
at pilot registration; the NUMERIC b is computed from pilot-observed
holding/overlap structure, frozen at activation, and used VERBATIM in
the terminal analysis. The activation simulation's DGP dependence
structure is taken from the blinded pilot estimates — so if the frozen b
undershoots true dependence, the defect surfaces as simulated
type-I > 0.10 and REFUSES activation, rather than silently inflating
terminal type-I. Pilot sizing uses a conservative upper confidence limit
for long-run variance, never the point estimate. The simulation must
show type-I no greater than 0.10 under `mu=MEE` (Monte Carlo point
estimate governs; 95% simulation CI reported), power at least 0.80 at
the planning effect, and a fixed terminal T within the declared maximum.

**Proxy-priced sessions (r2, admission rule).** Both arms are shadow;
costs always come from the frozen cost model applied to the declared
order set. The realized-vs-proxy distinction is the PRICE SOURCE (trade
prints vs bar proxy). Bar-proxy-priced sessions ARE admissible, flagged
per session and counted; the terminal deployment-evidence statement must
report the realized/proxy split, and a proxy fraction above a cap frozen
at pilot registration (proposed: 20% of terminal sessions) downgrades
any GO to `EVIDENCE INCOMPLETE (proxy-priced)` — not deployment
eligible. A mixed series is never silently treated as uniform.

At terminal T, report statistical efficacy (`LB90 > 0`) separately from the
deployment-evidence criterion (`LB90 > MEE`). Only the latter is an ensemble
advancement candidate, and it remains subject to independent operator review,
artifact provenance, capacity, and all existing risk/WF gates. No interim
efficacy look or post-pilot change is allowed.

## 5. Ownership and implementation sequence

This model repository owns the research registration, frozen expert/champion
identities, and evaluation schema. It must not create a private cross-repo
as-of helper. `renquant-pipeline` owns a public, versioned decision-schedule
and record-validation API; `renquant-common` owns only shared canonical
serialization/digest primitives; `renquant-orchestrator` owns the daily job,
fill/price collection, admission ledger execution, and persisted run bundle.
The model/backfill code consumes that public contract. The umbrella pins the
tested assembly and proves integration; it is not an alternative runtime.

Implementation order after independent design approval:

1. Specify and test the public pipeline schedule/validation contract with
   fixture vectors in common.
2. Implement the orchestrator's canonical job, immutable decision/fill records,
   and run-bundle fields; prove duplicate/watermark/fill failure behavior.
3. Update model score backfill and PIT ledger to consume that contract; rerun
   parity coverage with exact-pinned data and artifacts.
4. Implement the blinded pilot and terminal evaluation only after steps 1-3
   materialize in one pinned umbrella integration run.

## 6. Acceptance

Before any Phase A activation, provide: (a) an exact-pinned integration run
covering all four owner repositories; (b) adversarial tests for late watermark,
divergent retry, missing arm, partial fill, asymmetric price source, and pilot
row leakage; (c) an economic MEE/planning-effect memo with turnover/cost
sensitivity; and (d) an independent review of the frozen pilot manifest.
