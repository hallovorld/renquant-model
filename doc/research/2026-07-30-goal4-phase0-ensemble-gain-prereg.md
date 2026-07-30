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

## §2.5 SEALED SOURCE MANIFEST — an abort gate, not a bookkeeping step

A served checkpoint digest identifies the *model*. It cannot reproduce the
*panels*, so on its own it does not make this screen reproducible. Before any
statistic is computed, a manifest is generated, committed and sealed, covering:

| artifact | what is recorded |
|---|---|
| each member's historical score panel | path relative to a NAMED corpus root, sha256, row count, min/max score date, ticker count |
| the forward-return / label corpus | same five, plus the label column name and horizon |
| each member's served artifact | sha256, `trained_date`, feature-contract digest, config fingerprint (§2 abort gate) |
| the feature/config revision each panel was produced under | revision identifier and its digest |
| the included-member set | the exact list, after exclusions, with the reason for each exclusion |
| manifest root | one sha256 over the sorted per-artifact digests, so a single number pins the whole input set |

**Fail-closed, and the failure mode is named.** The harness recomputes every digest
before construction and **refuses** on the first mismatch, naming the file. A
*missing* manifest is also a refusal, not a bootstrap path — the same defect was
just found live on the sibling momentum line, where `verify_or_abort()` printed a
note and returned when the manifest was absent
`[VERIFIED — prior work, renquant-model#110 codex review 2026-07-30]`. An absent
manifest only ever occurs when something has already gone wrong (wrong working
directory, partial checkout, renamed artifact), which is exactly when the check
matters. A malformed manifest is likewise a refusal and is distinguished from an
absent one, because the remedies differ.

**Sealed means sealed.** The manifest is generated once and no artifact is appended
afterwards. Appending one silently voids every prior citation of the root digest —
that has already happened on this programme, where docs cited a root over 44 files
while the bundle had grown to 61 `[VERIFIED — prior work, 2026-07-29 PatchTST
closure retraction]`. If an artifact must be added, the manifest is regenerated and
every citation restated together.

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

**5.1 Positive control — a synthetic member with a KNOWN edge, constructed in
closed form.** "IC approximately +0.05" would leave a calibration knob inside the
control, so the construction is specified exactly and is **non-iterative**: nothing
is tuned against a realised IC, and a future run can be checked against this text.

For each admissible date `t`, over that date's ticker cross-section of size `n`:

1. `u = normal_scores(rank(r_{t→t+h}))` — ranks of the realised forward return
   mapped through `Φ⁻¹((i − 0.5)/n)`, ties broken by **ascending ticker symbol**
   (deterministic, no random tie-breaking).
2. `e = normal_scores(rank(v))` where `v` is drawn from
   `numpy.random.default_rng(SEED_BASE + int(t.strftime("%Y%m%d")))`, `SEED_BASE =
   20260730`. The seed is a pure function of the date, so the control is
   bit-reproducible and independent of iteration order.
3. `synthetic_t = α·u + sqrt(1 − α²)·e`.

**`α` is fixed by a closed form, not searched.** For bivariate-normal scores with
Pearson correlation `ρ`, the population Spearman correlation is
`ρ_s = (6/π)·arcsin(ρ/2)`. Inverting for a target `ρ_s = 0.05`:

> `α = 2·sin(π · 0.05 / 6) = 0.0523538966`
> `[DERIVED — 2*math.sin(math.pi*0.05/6); check (6/math.pi)*math.asin(α/2) = 0.0500000000]`

So the **population** Spearman IC of the synthetic member against the realised
return is exactly `+0.05` by construction. Because `u` is built from the realised
return, the synthetic member is a deliberate oracle-with-noise; it exists only to
prove the harness can see an inserted gain and never enters any treatment arm.

**Construction sanity, asserted not tuned:** the realised mean per-date Spearman IC
of the synthetic member must satisfy `|mean − 0.05| ≤ 0.01`. If it does not, the
**construction is broken and the screen VOIDs** — the value of `α` is not adjusted
to bring it into range. That distinction is the whole point of registering a closed
form: the assertion can only fail the run, never re-calibrate it.

**The control's requirement:** combine the synthetic member equal-weight with the
benchmark and require the harness to detect a gain at `|t| ≥ T_crit`. **If the
harness cannot detect a gain that was inserted on purpose, the screen is VOID** and
its negative result means nothing about ensembles.

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

---

# AMENDMENT 1 — the positive control was unsatisfiable by construction

Registered 2026-07-30, **before any re-run**. The screen executed under this prereg
(model#118) VOIDed on §5.1, and the frozen text worked exactly as intended: it forbade
adjusting `α` and forced a VOID rather than a tuned pass. **The defect is in the design I
wrote, not in the execution.**

## A1.1 The diagnosis, and a correction to my own first account of it

§5.1 fixed `α = 2·sin(π·0.05/6) = 0.0523538966` from the identity
`ρ_s = (6/π)·arcsin(ρ/2)`. **That identity is asymptotic.** At finite cross-section width
it does not deliver a realised Spearman IC of 0.05, so the `|mean − 0.05| ≤ 0.01`
assertion I also registered was unreachable — the control could not pass however correct
the implementation.

My first account of this said the real-panel shortfall exceeded clean simulation, implying
a further undiagnosed component. **That was wrong, and it was wrong for a familiar
reason: I compared against the wrong width.** The panel's universe is 145 tickers, but its
mean admissible rows per date is **115.4** (`364736 / 3161`)
`[VERIFIED — tr_matrix_metadata.json n_rows / n_dates]`. Simulating at the *realised*
width, 2000 draws, seed 20260730 `[VERIFIED — scipy Monte Carlo, this session]`:

| n | mean realised Spearman | s.e. | 3·s.e. band |
|---:|---:|---:|---|
| 115 | **0.04232** | 0.00207 | **[0.03610, 0.04855]** |
| 141 | 0.04028 | 0.00196 | [0.03440, 0.04616] |

model#118 measured **0.03681** on the real panel, which falls **inside** the n=115 band.
So there is **no evidence of any component beyond finite-sample bias at the panel's actual
width**, and the fix below is sufficient rather than merely necessary. Retracting the
"further component" claim explicitly rather than letting it stand.

## A1.2 The replacement, registered

`α` is no longer taken from a closed form. It is **calibrated on the panel's own
geometry**, before the treatment arm is computed:

1. **Calibrate on the object, not on a model of it.** Draw the synthetic member using the
   panel's *actual* per-date admissible ticker sets and its actual rank structure — not a
   synthetic iid cross-section of nominal width. The 145-vs-115 error above is precisely
   what calibrating against an idealisation costs.
2. **Bisection**, not search-with-judgement: find `α ∈ (0, 1)` such that the mean realised
   per-date Spearman IC of the synthetic member against the realised forward return equals
   **0.05**, using **2000** draws at seed **20260730**, bisection tolerance `1e-4` on `α`,
   maximum 40 iterations.
3. **The acceptance band is DERIVED, not asserted:** `±3 ×` the standard error of the
   calibration's mean, reported alongside `α`. At 2000 draws that is roughly `±0.006`
   `[DERIVED — 3 × 0.00207 from the table above]` — tighter than the `±0.01` I originally
   asserted, and it is a measured property of the calibration rather than a number I chose.
4. **If no `α` in `(0, 1)` reaches 0.05 within the derived band, the screen VOIDs.** `α`
   is still **never** hand-adjusted after seeing a result; the prohibition in §5.1 stands
   unchanged and now applies to the calibrated value.
5. The calibrated `α`, the achieved mean IC, its standard error, the draw count, the
   iteration count and the realised per-date width distribution all appear in the report.

## A1.3 What this amendment does NOT change

Everything else in the frozen text: the §2 identity abort gate, the §2.5 sealed source
manifest, the equal-weight unfitted combination, the §4 paired estimand and block
estimator, `T_crit = max(P95_null, t_{0.975, n_blocks−1})`, the null control and its 10%
validity ceiling, the non-tautology check, the descriptive-only redundancy table, and the
four §6 outcomes with their licences.

**A re-run executes the whole frozen sequence from §2, not just the control.** The screen
VOIDed at §5.1 before the treatment arm was computed, so no arm of this study has a
result, and picking up mid-sequence would mean running a treatment whose identity and
manifest gates were established in a different session.

## A1.4 The generalisation worth carrying

Two designs of mine failed the same way within hours: a **1.96** critical value frozen for
a `t` over single-digit blocks, and an **asymptotic** `ρ_s`–`ρ` identity frozen as an exact
finite-sample target. Both are large-sample quantities applied at small `n`, and both were
caught by review or by a control rather than by me. The registered practice that follows:
**any constant derived from an asymptotic argument must be re-derived at the realised
sample geometry before it is frozen, and its tolerance derived from that same
computation.**

## A1.5 CORRECTION to this amendment, before it merged

An independent re-verification of model#118 (model#120) refutes A1.2's sufficiency
claim, and it does so decisively. **A1.2 as written would VOID again.**

**The control is structurally incapable of firing, not merely mis-calibrated.** Sweeping
`α` to the value whose *realised* IC hits 0.05 exactly still fails
`[VERIFIED — prior work, model#120 α-sweep]`:

| `α` | realised member IC | control `t` | detected at `T_crit = 2.3646`? |
|---|---:|---:|---|
| 0.0523539 (frozen) | +0.03681 | +0.0984 | no |
| **0.0660000 (perfectly calibrated)** | **+0.04990** | **+0.5294** | **no — short by 4.47×** |
| 0.2000000 | +0.17936 | +4.6015 | yes |

**Mechanism.** Equal-weight rank-averaging a 0.05-IC member into a benchmark whose own IC
is **+0.07312** yields **+0.0030** of gain — **4.1% of the benchmark's own IC**
`[DERIVED — 0.0030 / 0.07312]` — and that is invisible at `n_blocks = 8`. So §5.1
registered a control **weaker than the incumbent**, and §3's equal weighting dilutes what
remains. Fixing `α` fixes the wrong term.

### A1.6 The registered consequence is a POWER finding, not a control patch

The control's failure is a measurement of the whole screen, not of the control:
**the minimum member IC this design can detect is somewhere between 0.05 and 0.18**, an
order of magnitude above any plausible ensemble member on this panel, where the production
recipe's `genuine_ic` above the placebo floor is **+0.00079**
`[VERIFIED — prior work, renquant-backtesting#83]`.

Registered, replacing A1.2's step 3:

1. the synthetic member's target is **derived, not chosen**: solve for the member IC at
   which the expected gain through the *registered* combination rule clears `T_crit` at
   the *realised* `n_blocks`, and report that value as the screen's **minimum detectable
   gain (MDG)**;
2. **the MDG is reported whatever the outcome**, in the headline, alongside the main arm;
3. **pre-committed:** if the MDG exceeds the largest gain an ensemble of these members
   could plausibly produce, the screen reports **UNRESOLVED (underpowered)** and **may not
   report NO-GAIN**. A null from a screen that cannot see the effect is not evidence of
   absence, and §6's NO-GAIN outcome is hereby unavailable unless the MDG is met.

**This retroactively constrains how model#118's main arm may be cited.** Its
`t = −1.0025` was never adjudicated (the VOID sits upstream), and under this clause it
could not have supported NO-GAIN even if it had been: **the screen cannot detect a
realistic ensemble gain at 8 blocks.** Anyone citing that number as evidence against
ensembling is citing an underpowered null.

### A1.7 Also carried from model#120, unresolved

- `MIN_NAMES = 20` exists in the run code and **not** in the frozen text. Inert on this
  panel (minimum cross-section 98, result identical with and without it) but unregistered;
  it is registered here explicitly.
- §5.2's "within-date permutations of the member scores" **does not say whether the
  benchmark is permuted**. #118 permuted all members jointly (`P95_null` 1.9131), #120
  permuted only candidates (1.5418). Both bind on the Student-t leg so the verdict is
  robust, but the ambiguity is real: **the benchmark is NOT permuted** is registered now.
- §2 was operationalised at **recipe identity**, not single-checkpoint identity, because
  all three scorers are walk-forward retrained and no single checkpoint can score a
  multi-year history without lookahead. That is an interpretation of the frozen text and
  is registered as the intended reading.
- `certified_clf`'s identity trail is **weaker** than the other two (recipe-script hash and
  hyperparameters; no per-fold digest, against 43/43 for XGB and PatchTST). Disclosed, not
  resolved.

## A1.8 The plausibility bound, PINNED — it was an adjustable threshold

Codex on #119: A1.6's *"the largest gain these members could plausibly produce"* has **no
source, no quantity and no rule**, so *"the UNRESOLVED versus NO-GAIN disposition remains
adjustable after observing the screen."* Correct — that is the exact defect the amendment
was written to remove, reintroduced one clause later. Pinned now, before any re-run.

### The rule

> **`P` = the mean per-date IC gain obtained by combining the benchmark with a second
> member that is (a) exactly as strong as the incumbent and (b) at the LOWEST pairwise
> redundancy observed among the three real members.**

Both inputs are already-measured quantities from the executed screen, cited rather than
chosen: benchmark IC **+0.07312** and the lowest observed pairwise score correlation
**0.404** (PatchTST↔XGB; the others are 0.517 and 0.768)
`[VERIFIED — prior work, model#118 §5.4 and its benchmark arm]`.

`P` is an **upper bound by construction**: no real member on this panel is simultaneously
as strong as the incumbent *and* less redundant than the least-redundant observed pair.
Being generous is deliberate — if even this bound sits below the screen's sensitivity, the
screen cannot see anything real, and that conclusion is then robust to the choice.

### The computed values

Monte Carlo on the panel's own geometry (`n = 115` names/date, 400 draws, seed 20260730),
with `α` calibrated empirically at that width per A1.2 rather than from the asymptotic
identity `[VERIFIED — scipy Monte Carlo, this session]`:

| quantity | value |
|---|---|
| `α` calibrated at n=115 for IC 0.07312 | 0.08799 |
| **`P` (plausibility bound)** | **+0.01897** (s.e. 0.00267) |
| block-mean s.e. of the gain statistic | 0.03036 `[DERIVED — 0.0030 / 0.0988 from #118]` |
| **`MDG` = `T_crit` × s.e.** | **+0.07180** `[DERIVED — 2.3646 × 0.03036]` |
| **`MDG / P`** | **3.78×** |

The s.e. is derived from #118's own control arm — a gain of **+0.0030** produced
`|t| = 0.0988` over 8 blocks — and it is a property of the noise, not of the gain, so the
extrapolation to `T_crit` is linear in the mean. Stated as an assumption rather than
hidden: this holds while adding signal does not materially change the dispersion.

### The deterministic comparison

> **If `MDG > P`, the screen reports UNRESOLVED (underpowered) and NO-GAIN is
> UNAVAILABLE. If `MDG ≤ P`, NO-GAIN becomes available.**

On the geometry as it stands, `MDG = 0.07180 > P = 0.01897`, so **the registered outcome
is UNRESOLVED (underpowered) and NO-GAIN is closed** — decided **before** the re-run, from
quantities that exist independently of it. Both numbers are recomputed at the realised
`n_blocks` and reported in the headline whatever happens; only the realised geometry can
move them, and the rule that consumes them cannot.

**This means a re-run cannot conclude against ensembling on this panel.** It can VOID, or
return UNRESOLVED. That is the honest state of the evidence and it is now fixed in advance
rather than available for selection afterwards.
