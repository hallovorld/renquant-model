# PREREG v2 — PatchTST closure: is its WF edge its own stale score?

**FROZEN. No run has been executed against this document.** Nothing live changes
on any outcome; see §8 for what a KILL does and does not license.

This supersedes the closure prereg merged as model#87, whose verdict was
**RETRACTED IN FULL** on 2026-07-29
`[VERIFIED — prior work, doc/research/2026-07-29-patchtst-closure-retraction.md]`.
That retraction ends with the instruction this document exists to obey: *"A further
attempt needs a NEW prereg naming the estimand up front and a bias-corrected
estimator."* model#87 **may not be reused as-is** and is not a fallback if
anything here proves inconvenient.

---

## §0 ABORT GATES — evaluated before any statistic is computed

Each gate below is fail-closed. If any cannot be satisfied, the study does not run
and the disposition is **VOID (identity)**, not UNRESOLVED. A VOID study licenses
nothing and may not be re-analysed into a verdict.

**§0.1 Artifact identity, established by execution.** The subject is *the PatchTST
checkpoint the live shadow path actually serves* — not a checkpoint found by
reading code or by name. This is not a formality: a prior PatchTST kill claim
(orchestrator #569) was independently re-verified to **WEAKENED** specifically
because the checkpoint had been **mistraced**
`[VERIFIED — prior work, memory goal-4-multi-model-ensemble; #569 later reverted via #570]`.

Required, in order:
1. Obtain the served artifact's identity from **serving output or its emitted
   metadata**, not from a config path or a filename.
2. Record `sha256` of the checkpoint file, its `trained_date`, its declared
   feature contract, and the config fingerprint under which it is served.
3. Assert the fingerprint recorded in step 2 equals the fingerprint of the file
   the study loads. **Not "the paths look the same" — the digests.**
4. If serving emits no artifact identity at all, that is itself the finding: the
   study VOIDs and the deliverable becomes an identity-plumbing issue, because a
   scorer whose served artifact cannot be identified cannot be adjudicated at all.

**§0.2 Sealed evidence bundle.** Every digest cited in the result must be computed
against a bundle that is **sealed before the run**. The retraction records why:
docs on this line cited a root digest over 44 files while the bundle had grown to
61, because files were appended after the citation
`[VERIFIED — prior work, 2026-07-29 retraction §"A false [VERIFIED] tag"]`.
Appending one file silently voids every prior citation of that root. The bundle
index is generated once, its root recorded here at run time, and **no file is
added afterwards**; if one must be, the index is regenerated and every citation
re-stated together.

**§0.3 Estimator implementation self-checks, run before the treatment.** Each must
pass or the study VOIDs:
- the within-date pairing is asserted to operate on a date-sorted frame, and the
  assertion is proven to **reject** an unsorted frame. A permutation helper that
  silently leaks across dates on a ticker-major frame has already aborted one study
  on this programme `[VERIFIED — prior work, model#105 abort]`;
- the block partition is asserted to contain **no undersized block** (§3);
- any multiple-comparison correction used is asserted to implement the step-down
  stop, tested against a hand-computed case. A house `holm()` lacking that stop,
  biased toward passing, shipped as recently as 2026-07-30
  `[VERIFIED — prior work, model#110 §"holm bug"]`.

---

## §1 THE ESTIMAND — named up front, one choice, with the reason stated now

The retraction's first and largest count was that I chose between two candidate
estimands **after** seeing which produced a CLOSE, and called it a
"different-estimands defence." That is HARKing and no downstream arithmetic
repairs it `[VERIFIED — prior work, retraction count 1]`. So the choice is made
here, before any number exists, and it is stated in a form that cannot be
reinterpreted.

**Registered estimand.** For an evaluation date `t` and the forward excess return
`r_{t→t+h}` (h = 60 trading days, the label the model is trained against), let

- `IC_fresh(t)` = cross-sectional Spearman IC between `score_t` and `r_{t→t+h}`
- `IC_stale(t)` = cross-sectional Spearman IC between `score_{t−L}` and the **same**
  `r_{t→t+h}`, over the **same tickers**, on the **same rows**

and define the per-date paired difference

> **`d(t) = IC_fresh(t) − IC_stale(t)`**

The estimand is `E[d(t)]` over admissible evaluation dates. **A positive `E[d]`
means today's score adds information about today's forward return beyond what an
L-day-old score already carried. A negative `E[d]` means the fresh score is worse
than the model's own stale output.**

**Why this is the bias-corrected estimator the retraction asked for.** The 72% era
term arose because the two arms were taken from *different date slices*
(`[L, N]` against `[0, N−L]`), so they were evaluated in different eras and the
model's skill is episodic — lag-0 IC by score-date quartile ran
`+0.0493 / +0.0032 / +0.0672 / +0.0043`
`[VERIFIED — prior work, retraction count 2]`. Here **both arms are evaluated on
the identical set of `(date, ticker, forward-return)` rows.** The evaluation era is
common by construction, so no era offset can enter the difference. This is a
structural fix, not a covariate adjustment.

**The limitation this does NOT remove, stated now so it cannot be presented later
as a discovery.** The stale arm's *score* is produced in era `t−L` while the fresh
arm's is produced in era `t`. Because skill is episodic, `d(t)` therefore compares
a score from one episode against a score from another. That does not bias `E[d]` —
the aggregation is over a common date set with no per-arm slicing — but it does
mean the estimand is **"fresh beats own-stale on identical evaluation rows"** and
NOT "freshness is valuable holding skill regime constant." The §6.5 era view
exists to characterise this, not to rescue a verdict.

**Admissible dates.** `t` is admissible iff (a) `score_t` exists, (b) `score_{t−L}`
exists, (c) `r_{t→t+h}` is **complete** — the forward window ends on or before the
corpus's last date. (c) is not optional bookkeeping: 9.6% of score dates in
sha256-pinned corpora on this programme have a 60-trading-day forward window ending
past the corpus's own last date `[VERIFIED — prior work, memory
asserted-instead-of-measured]`. Both arms use exactly this set; no arm gets a row
the other does not.

**Primary lag, registered on theory.** **L = 60 trading days = h.** The reason is
data-independent and stated before any lag is computed: a score is trained to
predict the next 60 trading days, so a score already 60 trading days old has by
construction exhausted its own horizon. If the model carries fresh information, it
must beat a score whose horizon has fully elapsed. **L = 60 is the only gate.**
L = 20 / 40 / 80 are computed and reported as **DESCRIPTIVE ONLY and may not enter
any decision**, explicitly including any count of how many lags share a sign — the
4-lag sign count is exactly the statistic the retraction killed (§4.2).

Today's momentum study is the reason this clause is emphatic: its selected horizon
turned out to be the argmax of `|t|` across the claim band, which git order proved
was not post-hoc but which remains a coincidence worth designing away
`[VERIFIED — prior work, model#110 ERRATUM/§h=120 note]`.

---

## §2 SUBJECTS, AND WHAT EACH IS FOR

| arm | role | may it fail? |
|---|---|---|
| PatchTST, the §0.1-identified served checkpoint | **treatment** | yes — that is the question |
| production XGB, unpermuted | **positive control** | must PASS or study VOIDs |
| production XGB, within-date permuted scores | **null control** | must FAIL at the registered rate or study VOIDs |
| PatchTST, within-date permuted scores | **null control, matched** | must FAIL |

Prior measurements on a corrected common-sample harness, carried here as context
and **not** as this study's evidence: PatchTST `d = −0.0556 (t = −2.31)`, prod XGB
`+0.0290 (t = +1.23)`, certified clf `+0.0096 (t = +1.31)`, and PatchTST's lag-60
rank autocorrelation 0.30 against XGB 0.70 / clf 0.79
`[VERIFIED — prior work, model#90 corrected-eval/verdict.log]`.

Note what that XGB control number implies and do not paper over it: the positive
control's own margin was **0.23 of a t** on `n_eff = 8`, and leave-one-block-out
spanned `[+0.67, +1.94]` `[VERIFIED — prior work, model#90]`. §7 pre-commits what
happens when the control is that thin.

---

## §3 ESTIMATOR — frozen, including the arithmetic that has bitten twice

The retraction's count 5 was using a different estimator than the one frozen
`[VERIFIED — prior work, retraction count 5]`. There is therefore exactly one
estimator here and no alternative is admissible.

1. Compute `d(t)` per admissible evaluation date (§1).
2. Sort admissible dates ascending. Let `N_eval` = their count.
3. Partition into **non-overlapping contiguous blocks of 60 trading days**.
   `n_blocks = floor(N_eval / 60)`. **Any remainder is DROPPED.**
4. Block statistic = mean of `d(t)` within the block. Test statistic = one-sample
   `t` over the `n_blocks` block means, two-sided.

**Step 3 is written this way because of a defect committed today.** The momentum
study formed 10 blocks where the correct count was 9, and equal-weighted a final
block holding 5 days, inflating its headline `t` by 15.6%
`[VERIFIED — prior work, model#110 ERRATUM]`. Two rules follow and are frozen:
`N_eval` **excludes** dates with an incomplete forward window before blocking (not
after), and an undersized trailing block is **discarded, never equal-weighted**.
§0.3 asserts both.

**Reported alongside, mandatory:** `N_eval`, `n_blocks`, the count of dropped
remainder days, and the per-arm row counts. A result without these is incomplete.

---

## §4 CONTROLS — and the proof that they can fail

### 4.1 Positive control
Prod XGB, unpermuted, same harness, same dates. **Must produce `t > 0` with
`|t| ≥ 1.96`.** A design in which the control cannot be shown to pass is not
evidence about the treatment.

### 4.2 Null control, with a MEASURED false-pass rate
The retraction's count 4: the old control was a bare sign count that a signal-free
within-date-permuted prod XGB passed **37.5%** of the time, with zero-skill AR
scores at 50–55%; it was structurally incapable of failing the way the treatment
fails `[VERIFIED — prior work, retraction count 4]`.

Registered fix, in two parts:

- the **statistic** is no longer a sign count over lags. It is a single block-level
  `t` at L = 60 (§1, §3), so lag sign-counting cannot occur;
- the false-pass rate is **measured, not assumed**. Run **40** independent
  within-date permutations of each subject's scores through the identical harness
  and record the fraction reaching `|t| ≥ 1.96`. **Registered ceiling: 10%.** If
  the observed rate exceeds 10%, the harness is **VOID** and no verdict is drawn
  from it — the treatment's own number is not reported as a finding.
- report `mean|t|`, `p95|t|` and `max|t|` of the permutation distribution, and the
  treatment's `|t|` **as a quantile of it**.

### 4.3 The null control must not be a tautology
A negative control that is algebraically forced to agree tests plumbing, not
arithmetic. Today's dividend work shipped exactly that: 34 non-payers matched
bit-for-bit, but their `dividend` column is exactly `0.0` on every row, so the
adjustment factor is identically 1.0 and the two series are equal *whatever the
algorithm does* `[VERIFIED — prior work, model#110 negative-control correction]`.

So before use, the permutation control must be shown to **change the statistic**:
assert `IC_fresh` on permuted scores differs from `IC_fresh` on real scores by more
than floating-point tolerance on at least 95% of dates. A permutation that leaves
the statistic unchanged is a broken permutation, not a passing control.

---

## §5 DECISION RULE — frozen, four outcomes, no fifth

Evaluated **only** at L = 60, **only** with the §3 estimator, **only** if §0 and
§4 gates hold.

| outcome | condition |
|---|---|
| **KILL** | `t ≤ −1.96` **and** every §6 robustness gate holds |
| **RETAIN-INFORMATIVE** | `t ≥ +1.96` |
| **UNRESOLVED** | `|t| < 1.96` |
| **VOID** | any §0 abort gate, or positive control fails, or measured null-control false-pass rate > 10%, or §4.3 tautology check fails |

**A KILL requires the robustness gates; a RETAIN does not.** That asymmetry is
deliberate and is registered with its reason: this study can only *remove* a
scorer, and removing one that is genuinely informative is the costlier error, so
the destructive verdict carries the heavier burden. It is not a licence to soften
the bar in the other direction — `|t| < 1.96` is UNRESOLVED and stays UNRESOLVED.

**UNRESOLVED is a statement about power, never about PatchTST.** The retraction
already records that on the registered basis the point estimates stay negative at
every lag (`−0.0021 / −0.0064 / −0.0487 / −0.0613`) yet resolve nothing, and that
"KEEP OPEN" was no better supported than CLOSE
`[VERIFIED — prior work, retraction §"What this retraction does NOT establish"]`.
A third UNRESOLVED on this question is a finding about the corpus's power and must
be reported as such, not narrated toward a conclusion.

---

## §6 ROBUSTNESS GATES — required for KILL only, all must hold

These exist because today's momentum study cleared every gate its frozen design
contained and then died on two dimensions the design had **omitted**: name and
robust location. Dropping 5 of 145 names took `t` from +3.258 to +1.871; a median
spread instead of a mean gave +1.964; winsorizing the label to ±1 gave +1.990
`[VERIFIED — prior work, model#110 robustness table]`. A design whose gates are
all in one dimension is not robust, it is narrow.

- **6.1 Name dimension.** Leave-one-ticker-out over all tickers: sign of `d`
  preserved in **≥ 95%** of refits and `|t| ≥ 1.96` in **≥ 90%**.
- **6.2 Robust location.** Replace the per-block mean with the per-block **median**
  of `d(t)`: sign preserved, `|t| ≥ 1.96`.
- **6.3 Outlier insensitivity.** Winsorize the label cross-section to ±1 SD: sign
  preserved, `|t| ≥ 1.96`.
- **6.4 Block dimension.** Leave-one-block-out: sign preserved in **all**
  `n_blocks` refits.
- **6.5 Era.** Split admissible dates into chronological halves: sign preserved in
  both. This characterises the episodic-skill limitation named in §1; a failure
  here means the effect is era-local and KILL is not licensed.
- **6.6 Mechanism sanity.** Report `d` alongside PatchTST's lag-L score
  autocorrelation. Already ruled out as a mechanical artifact — zero-skill AR at
  matched ρ closes 5.0% of the time and genuine-skill-with-low-autocorrelation
  closed 0/20 `[VERIFIED — prior work, retraction §"One angle did close"]` — so
  this is reported, not gated. Recording it prevents that finding being
  re-litigated.

---

## §7 POWER, STATED BEFORE THE RUN

`n_blocks` is expected to be **single-digit** on this corpus; model#90's comparable
harness had `n_eff = 8` `[VERIFIED — prior work, model#90]`. At `n_blocks = 8` a
two-sided 1.96 bar needs `|d| / se(d) ≥ 1.96` on 7 degrees of freedom, which is a
**thin** basis for a destructive verdict, and the positive control's own margin on
that harness was 0.23 of a t.

Pre-committed consequences, so no discretion exists at reporting time:

1. If `n_blocks < 6`, the study reports **UNRESOLVED (underpowered)** regardless of
   the point estimate, and the deliverable becomes what would raise `n_blocks`.
2. If the positive control passes with `|t| < 2.5`, the treatment's verdict is
   reported **with the control's own thinness in the same sentence**, and a KILL
   additionally requires §6.4 leave-one-block-out to hold with **`|t| ≥ 1.96` in
   every refit**, not merely sign preservation.
3. The exact `n_blocks`, `N_eval` and dropped-remainder count appear in the
   headline, not in an appendix.

---

## §8 WHAT EACH OUTCOME LICENSES — and one thing that is not contingent at all

**A KILL licenses:** removing PatchTST from the shadow-feed candidate set, and
closing the GOAL-4 sub-question of whether it contributes independent information.

**A KILL does NOT license:** any edit to a deployed config, artifact or state file;
any launchd change; any pin advance. Those are live run surfaces and remain under
the CONTAINMENT PROTOCOL — a tracked task with an owner and an explicit expiry or
restore condition, a durable record with literal revert steps, and the reviewed
surface updated in the same batch.

**Not contingent on this study, and stated here so the study cannot become its
excuse:** the fallback-config hazard is a **safety defect that must be fixed
regardless of the verdict**. A fallback path can make a 623-day-stale PatchTST the
*primary* scorer, and because its scores are intrinsically all-negative that
produces a **sell-only** book `[VERIFIED — prior work, RenQuant#546; memory
patchtst-scores-intrinsically-negative]`. A sell-only day has already starved the
live book once `[VERIFIED — prior work, memory incident-20260716-book-drained-to-cash]`.
Fixing that does not require knowing whether PatchTST has edge — a stale scorer
must not become primary either way. If this study returns UNRESOLVED a third time,
**#546 still gets fixed.**

---

## §9 DELIVERABLE SHAPE, FROZEN

The run emits, in this order: §0 gate results; `N_eval` / `n_blocks` / dropped
days; the §4 control table with the measured false-pass rate; the L=60 treatment
statistic; the §6 gate table (KILL only); the descriptive L=20/40/80 rows under a
heading stating they may not enter the decision; then the §5 verdict verbatim.

**Publication discipline.** The verdict is **withheld pending adversarial review**
before it is published. This is the one thing that has actually worked on this
question: a CLOSE was published and retracted, a second CLOSE was withheld, and the
commissioned review destroyed it — had it been published on the strength of my own
reasoning it would have been the second retraction in one day
`[VERIFIED — prior work, retraction §"The process lesson"]`.

The review is commissioned **before** the results commit, and both the review and
its disposition are appended **verbatim** to this line's documents before merge.
