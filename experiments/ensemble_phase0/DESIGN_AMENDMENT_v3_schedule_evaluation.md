# Amendment v3: decision schedule + evaluation design (ensemble combination experiment)

Date: 2026-07-17
Status: RFC amendment to `2026-07-12-ensemble-combination-experiment.md`
(base) and `DESIGN_AMENDMENT_v2_block_rebalance.md` (v2). Registered as a
NEW experiment version — v2 was never activated (Phase 0 verdict: BLOCKED
on evidence, model#58/#59), so this is a pre-activation re-registration,
not a mid-flight change. Drafted personally per design-review policy.

## A. Two findings force the re-registration

1. **Evidence volume (model#58/#59):** v2's evaluation unit — ≥8
   non-overlapping 70-session blocks tied to the 60d label — needs ~560
   admissible sessions per expert. Forward accumulation makes Phase A a
   2027+ event. The block design is not tunable inside v2 (shrinking it
   changes the estimand and reintroduces label overlap).
2. **Decision-schedule mismatch (model#60, PIT parity backfill):** v2
   inherited a close-anchored as-of contract (a session-T run qualifies
   only if committed before T's close). The REAL process on BOTH arms is:
   post-close batch decision on T's completed data, orders queued for
   T+1's open. Under the frozen contract, 16/20 shadow sessions are
   excluded as "look-ahead", and the prod runs that DO qualify are
   pre-close sell-only intraday runs — not the buy-decision runs. The
   contract mis-describes the process it is meant to protect.

## B. The re-registered decision schedule (next-open convention)

For session T:

- **Information set:** all data with watermark ≤ T's session close.
- **Decision instant:** the post-close batch run, committed in
  (T close, T+1 open). Both arms' qualifying run for T is their LAST such
  run (deterministic; duplicates resolved by latest-committed, logged).
- **Execution instant:** T+1 open (matching the venue reality: whole-share
  orders queued overnight).
- **Scored return interval:** open(T+1) → open(T+2) for the daily series
  (below). No close-to-close double use; the signal's information set
  (≤ close T) strictly precedes the first executable price (open T+1).

The PIT input-parity ledger (model#60) is schedule-agnostic and reruns
against this convention unchanged; §5.1 admission then evaluates real
coverage (expected: the 16 structurally-excluded sessions become
evaluable).

## C. The re-registered evaluation design (portfolio-difference series)

v2 evaluated 60d-label-aligned block outcomes. v3 separates concerns:

- The 60d label remains a TRAINING/scoring artifact contract (unchanged;
  it is the experts' internal business).
- The EXPERIMENT is evaluated on what capital experiences: the daily
  paired difference series
  `d_t = r_t(L1 portfolio) − r_t(champion portfolio)`, both computed
  under the identical §B schedule, identical universe/calendar inputs
  (parity-ledger-admitted sessions only), identical cost model
  (net-of-fee, the frozen execution-cost parameters from the base doc).
- **Inference = the G1 v4 machinery, verbatim** (methodology
  unification): one-sided MBB test of H0: μ_d ≤ 0 at α = 0.10; MBB block
  length from fitted autocorrelation (paired daily portfolio differences
  have no mechanical 60d overlap — the 70-session block constraint
  disappears with the estimand, which is the point); MDE set at the
  economically material threshold (pre-registered: 2 bps/session, ≈5%/yr
  on the sleeve) with power ≥ 0.80 demonstrated in a pre-activation
  simulation on the FITTED null (≥40 parity-admitted paired sessions
  before the fit — the G1 v4 §4.7 pattern, including the honest
  "infeasible at measured noise" outcome).
- **Selection control:** exactly ONE comparison is registered (L1
  equal-weight vs frozen champion). L2+ ladder steps are separate future
  registrations with family-wise control if run concurrently.

## D. Feasibility posture (honest)

L1 and the champion hold overlapping books, so σ(d_t) is plausibly small
— but v3 does NOT assume feasibility: like G1 v4, the fitted-null power
check is a HARD activation prerequisite, and "infeasible at measured
noise" is a recorded legitimate outcome. No 560-session wall; no
pretending 20 sessions suffice either. The pre-activation simulation
decides with measured numbers.

## E. Implementation items unlocked by this design (post-approval only)

1. as-of contract v2 (next-open) in the shared selection helper
   (`select_asof_runs`) — consumed by backfill, export, and the parity
   ledger; single implementation, versioned constant.
2. `backfill_scores.py` multi-DB (shadow) source support (task #60).
3. Parity-ledger rerun + coverage report under §B.
4. Daily d_t computation job (both books marked under one price source)
   feeding the §C series; telemetry counter n_admitted_paired_sessions.

## F. What v3 does NOT change

Expert artifact contracts, provenance chain (#202/#482/#484), the
admissibility ledger's fail-closed posture, the L1→L4 ladder scope
exclusions, and Phase 0's champion-unchanged verdict all stand. No
capital, no activation, no schedule deployment is authorized by this
document.
