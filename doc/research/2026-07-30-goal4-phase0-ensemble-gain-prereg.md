# PREREG — GOAL-4 Phase 0: does combining the existing scorers gain anything?

**FROZEN. No run has been executed against this document.** Nothing live changes on
any outcome. This document neither kills GOAL-4 nor authorises building an ensemble;
it registers the cheap screen that decides which of those is next.

## §0 Why this exists: GOAL-4 has never had an acceptance criterion

GOAL-4 has had **zero work** for weeks, and the reason is not neglect — it is that
no one ever wrote down what would count as passing. A goal without measurable
acceptance criteria cannot be worked on, only talked about.

Its record also has to be stated accurately, because it is easy to get wrong in both
directions. #569 claimed a KILL; independent re-verification returned **WEAKENED**
because the PatchTST checkpoint had been **mistraced**; #569 was then **reverted via
#570** on separate repo-placement grounds
`[VERIFIED — prior work, memory goal-4-multi-model-ensemble]`. So GOAL-4 is
**neither killed nor delivered — it is undefined.** This screen defines it.

## §1 The premise, in a form that can fail

An ensemble is worth building only if combining the members produces more signal
than the best member alone. Note carefully what this does **not** require: it does
**not** require any member to be individually significant. That distinction is the
whole reason this screen is worth running rather than skipping.

The tempting shortcut — "every member is individually insignificant, therefore the
ensemble is null" — is **wrong**, and registering why prevents it being used later.
Two members each carrying a small TRUE edge, each individually underpowered, can
combine into a detectable one; variance reduction is exactly the mechanism an
ensemble is supposed to exploit. Individual insignificance under low power does not
establish zero edge. **So the combination is tested directly, not inferred from the
members.**

What IS fatal is redundancy: members that rank the cross-section the same way cannot
diversify. That is measured (§5) but not gated, because redundancy is continuous and
its effect is already captured by the primary statistic.

Carried as prior work, not measured for this document, and load-bearing on what to
expect: the production recipe's `genuine_ic` above the placebo floor is **+0.00079**
`[VERIFIED — prior work, renquant-backtesting#83]`; the prod XGB's traded estimand is
reproduced by a **single sort on STD20** (+0.2836 against the model's +0.2534) and
collapses to **−0.0554** when orthogonalised to STD60
`[VERIFIED — prior work, traded-estimand study, memory panel-signal-identity-capacity]`;
PatchTST's margin over its own 60-day-stale score is **−0.0556 (t = −2.31)**, which
does **not** clear the correctly calibrated bar of 2.3646 at `n_eff = 8`
`[VERIFIED — prior work, model#90]` `[DERIVED — scipy.stats.t.ppf(0.975, 7)]`; the
certified clf reads **+0.0096 (t = +1.31)** `[VERIFIED — prior work, model#90]`; and
the tail statistic has led IC on **4 of 4** independent subjects while clearing no
preregistered bar on any `[VERIFIED — prior work, memory panel-signal-identity-capacity]`.

## §2 Members, and the benchmark registered a priori

| member | role |
|---|---|
| production XGB | **the benchmark.** Registered as the comparison arm *because it is the deployed scorer*, not because it scores best |
| certified top-decile clf | candidate member |
| PatchTST | candidate member, **subject to the artifact-identity abort gate** below |

**Registering the benchmark a priori removes the selection bias that would otherwise
sink this screen.** "Does the ensemble beat the best member?" is biased when *best*
is read off the same data — the winner's margin is inflated by selection. Naming the
production scorer in advance removes the choice entirely. If the ensemble cannot beat
the incumbent, it is not worth deploying whatever it does to the others.

**Abort gate, inherited verbatim from the PatchTST closure prereg (§0.1 there):** each
member's served artifact identity must be established from **serving output or emitted
metadata**, and the digest of the file the study loads must equal it. A prior PatchTST
claim died precisely on a mistraced checkpoint. If identity cannot be established for
a member, that member is **excluded and the exclusion is reported** — the screen may
still run on the remainder, but a two-member screen is reported as a two-member screen.

## §3 Combination rule: equal weight, unfitted

The combination is the **per-date equal-weight average of members' cross-sectional
ranks**. No fitted weights.

This is registered, not a shortcut. Fitting weights on the same panel the screen is
evaluated on is the overfit trap that would make any positive result uninterpretable,
and this programme has enough experience of an in-sample winner not surviving contact
with a holdout. Weight fitting is a **Phase-1** question and only becomes admissible
if Phase 0 shows an unfitted equal-weight combination already gains. An equal-weight
combination is also the weakest reasonable version of the hypothesis, which is the
right thing to test first: if the easiest form of the idea shows nothing, the elaborate
forms do not deserve the compute.

## §4 Estimand, estimator and critical value

**Paired on identical rows.** For each evaluation date `t` with complete forward
excess return `r_{t→t+h}` (h = 60 trading days):

> **`g(t) = IC_ensemble(t) − IC_benchmark(t)`**

both ICs being cross-sectional Spearman against the **same** `r_{t→t+h}`, over the
**same tickers**, on the **same rows**. The estimand is `E[g(t)]`. Pairing on
identical evaluation rows is what keeps the episodic-skill era structure out of the
difference — the same structural fix that the PatchTST closure prereg adopted after
an era offset was found carrying ~70% of a retracted effect
`[VERIFIED — prior work, 2026-07-29 closure retraction, count 2]`.

**Admissible dates** are those where every included member has a score AND
`r_{t→t+h}` is complete — the forward window ends on or before the corpus's last
date. All arms use exactly this set; no arm gets a row another does not.

**Estimator, frozen.** Non-overlapping contiguous blocks of 60 trading days over the
admissible dates; `n_blocks = floor(N_eval / 60)`; **the remainder is dropped, never
equal-weighted** — a study today formed 10 blocks where 9 was correct and
equal-weighted a 5-day trailing block, inflating its headline `t` by 15.6%
`[VERIFIED — prior work, model#110 ERRATUM]`. Statistic = one-sample two-sided `t`
over block means of `g(t)`.

**Critical value, one symbol used everywhere:**

> `T_crit = max( P95_null , t_{0.975, n_blocks−1} )`

`P95_null` is the 95th percentile of `|t|` from **200** within-date permutations of
the *member* scores through the identical harness. The Student-t leg uses the
**realised** `n_blocks` after the remainder drop, not an expected value. Reference
`[DERIVED — scipy.stats.t.ppf(0.975, n−1)]`: `n=8 → 2.3646`, `n=9 → 2.3060`,
`n=10 → 2.2622`. The larger of the two is taken, which is conservative for the
build-something verdict. Frozen at 1.96 this screen would have used a bar roughly
**17% too low** at `n=8`; that error was caught in review on PR #113 before any run
and is not repeated here.

**Mandatory in the report:** `N_eval`, `n_blocks`, dropped remainder days, `P95_null`,
`t_{0.975, n_blocks−1}`, which leg bound `T_crit`, and `|t|` as a quantile of the null.

## §5 CONTROLS — including one that proves the harness can detect a gain

**5.1 Positive control — a synthetic member with a KNOWN edge.** Construct a synthetic
score whose per-date rank correlation with the realised `r_{t→t+h}` is calibrated to
**IC ≈ +0.05**, combine it equal-weight with the benchmark, and require the harness to
detect a gain at `|t| ≥ T_crit`. **If the harness cannot detect a gain that was
inserted on purpose, the screen is VOID** and its negative result means nothing about
ensembles.

This control is the reason the screen is worth running at all. A design that returns
"no gain" without ever demonstrating it *could* have said otherwise is not evidence —
it is the same failure as a null control that cannot fail, which sank a design on this
programme eleven days' work ago `[VERIFIED — prior work, 2026-07-29 closure
retraction, count 4]`.

**5.2 Null control.** Members replaced by within-date permutations of their own scores.
The combination must NOT gain. Report the false-pass rate over the 200 permutations of
§4 against a **10%** validity ceiling; above it the harness is VOID.

**5.3 Non-tautology check.** Assert the permutation actually changes the statistic on
≥95% of dates. A control that is algebraically forced to agree tests plumbing, not
arithmetic — a negative control shipped today was exactly that, matching bit-for-bit
because its adjustment factor was identically 1.0
`[VERIFIED — prior work, model#110 negative-control correction]`.

**5.4 Redundancy, descriptive only.** Per-date pairwise Spearman between members'
scores; report mean, p5 and p95. **This may not enter the decision.** It is recorded
because it changes how a future Phase 1 would be designed, and because a high value
explains a null primary result without being permitted to substitute for one.

## §6 DECISION RULE — frozen, four outcomes

| outcome | condition |
|---|---|
| **GO-PHASE-1** | `t ≥ +T_crit`, positive control detected, null control clean |
| **NO-GAIN** | `t ≤ −T_crit` — the combination is actively worse than the incumbent |
| **UNRESOLVED** | `|t| < T_crit` |
| **VOID** | positive control undetected, or null false-pass rate > 10%, or §5.3 fails, or fewer than 2 members survive the identity gate |

**What GO-PHASE-1 licenses:** writing a Phase-1 design covering weight fitting with
out-of-sample validation. **It does not license** any deployment, any config or
artifact edit, any launchd change, or any pin advance — those are live run surfaces
under the CONTAINMENT PROTOCOL.

**What UNRESOLVED licenses:** nothing, and it is the most likely outcome given §1's
prior numbers. If `n_blocks < 6` the screen reports **UNRESOLVED (underpowered)**
regardless of the point estimate, and the deliverable becomes what would raise
`n_blocks`. A third consecutive UNRESOLVED across this programme's lines is a finding
about the corpus's power and is reported as such, not narrated toward a conclusion.

**What NO-GAIN licenses:** closing GOAL-4's ensemble hypothesis in its current form,
with the redundancy table (§5.4) as the explanation. It does **not** license claiming
any individual member is null — that is a different estimand and this screen does not
measure it.

## §7 Publication discipline

The verdict is **withheld pending adversarial review** and is not published on the
strength of my own reasoning. That is the only thing that has worked on this
programme's contested questions: a CLOSE published on this very family of models was
retracted, a second was withheld, and the commissioned review destroyed it
`[VERIFIED — prior work, 2026-07-29 closure retraction, §"The process lesson"]`.
