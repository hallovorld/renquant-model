# GOAL-6 Stage 0 — Amendment 5 (visible, PRE-RUN): the H1 evaluation horizon, frozen at 20d with a cross-horizon confirmation guard

**Amends nothing but the H1 horizon and its hand-off to Stage 2. Filed on the codex
round-3 review of the runner (model#174): the H1 horizon determines the primary
statistic handed to H2, so it is an inferential decision, not an implementation
default. Option (a) of the review's three, plus a guard that closes the circularity
option (a) alone would leave.**

## The frozen choice: H1 is evaluated at 20d

Rationale, from the honest gap-block geometry Amendment 3 fixed `[推导 from frozen
arithmetic; thresholds 本次实测]`: on the full 508-date window the gapped block counts
are **13 (20d)** vs **4 (60d)**. A Holm-corrected 3-contrast family at family α = 0.10
needs its smallest p ≤ 0.0333, i.e. **|t| ≥ 2.403 at df = 12** but **|t| ≥ 3.740 at
df = 3**. At 60d the family is structurally near-unresolvable — freezing H1 there
would predetermine REFUTED/INCONCLUSIVE by geometry, not by data. 20d is the only
horizon whose block count can resolve the statistic question at all.

## The guard: a 20d-selected statistic does not silently steer a 60d regime

H1's selection is conditioned on the 20d horizon; H2 then tests that horizon
separately. The uncovered corner is H1 = SUPPORTED (a tail statistic wins at 20d)
while H2 ≠ SUPPORTED (Stage 2's measurement horizon stays 60d). Frozen resolution:

* In that corner, the H1-selected tail statistic carries into Stage 2 **only if**, at
  60d, BOTH (i) its own REAL − permutation gap-block t ≥ 2.0 and (ii) its 60d
  persistence veto passes (t ≥ 1.0, positive) — the same bars every other decision
  uses, applied at the horizon Stage 2 will actually measure at.
* Otherwise Stage 2 keeps **IC** (the incumbent statistic), exactly as the prereg's
  tie rule already prescribes for every ambiguous outcome.

No new thresholds are invented: the clause reuses the frozen own-t bar (2.0), the
frozen veto bar (1.0, positive), and the Amendment-3 block geometry at 60d.

## Not amended

Every H1/H2 threshold, the Holm family, both nulls, the §5 veto (as wired per review
round 2), Amendments 1–4.

## Not claimed

That 20d selection is unconditionally optimal — it is the only RESOLVABLE choice under
the honest geometry, and its conditioning on the challenger horizon is exactly what
the confirmation guard exists to contain. That the guard adds power — it only prevents
an unvalidated cross-horizon transfer.
