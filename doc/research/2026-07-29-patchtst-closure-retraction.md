# PatchTST closure re-run — **CLOSE RETRACTED. Status: INCONCLUSIVE.**

Date: 2026-07-29. I commissioned an adversarial review against my own CLOSE.
It broke the claim on six counts, five of them mine. The claim is withdrawn
in full.

## Why it does not stand

1. **The "different estimands" defence is void — and choosing it was HARKing.**
   The frozen prereg is not ambiguous. §2 T11 requires the harness to
   "compute REAL and PERSIST on the same common **score-date** subset at each
   lag", and §3 states that a `p` computed from `corpus[lag:N]` /
   `corpus[0:N−lag)` slices "does not satisfy this decision rule and any
   verdict built on it is void". My re-run's arms are exactly those slices
   (score positions `[L,544]` vs `[0,544−L]`). I argued the rule meant the
   label-common estimand **after** seeing that only it produced CLOSE. That
   is HARKing, and no amount of correct arithmetic downstream repairs it.

2. **~70% of the effect is the era offset the first retraction was about.**
   Decomposing `d = ERA + SIGNAL`: L=60 era term −0.0305 of −0.0425 (**72%**);
   L=80 −0.0322 of −0.0476 (**68%**). Lag-0 IC by score-date quartile
   +0.0493 / +0.0032 / +0.0672 / +0.0043 — episodic, so an offset window
   biases hard.

3. **"Both arms share every row" was half-true, stated as whole.** True of
   LABEL rows, false of SCORE eras. And "one common sample for every lag" is
   plainly wrong: per-lag samples are 525 / 505 / 485 / 465 dates with
   different start dates.

4. **The control cannot fail.** It is a bare sign count: a within-date-permuted
   (signal-free) prod XGB passes "≥3 of 4 positive" **37.5%** of the time, and
   zero-skill AR scores 50–55%. It also has essentially no era gradient, so it
   is structurally incapable of failing the way the treatment fails.

5. **Wrong estimator.** §2 freezes a fold-level t; I used 60-date blocks.
   Under the frozen estimator p = **3/4** (L=20 misses).

6. **My own standard rejects it.** model#90's three-view rule applied to my
   own table resolves **2 of 4** lags — below the ≥3 bar → INCONCLUSIVE.

`p` ranges over **{0, 2, 3, 3, 4}** across defensible handling choices. A
verdict that moves with the handling choice is not a verdict.

## A false [VERIFIED] tag — mine, and the rule was mine too

Docs on this line cited root digest `f6b6ef6d…` over **44 files**. The bundle
hashes to `901f0add…` over **61 files**
`[VERIFIED — tools/corpus_index.py generate, 2026-07-29]`, because I added
`wf-eval/` and `clf-wf/` to it afterwards and never regenerated the index.
The tag did not verify at the moment I wrote it.

Lesson, now explicit: **a digest citation is only valid against a frozen
bundle.** Appending a single file silently voids every prior citation of that
root. Bundles cited in evidence must be sealed, or re-indexed and re-cited
together.

## What this retraction does NOT establish

PatchTST is **not exonerated**. On the registered common-score-date basis the
point estimates stay negative at every lag (−0.0021 / −0.0064 / −0.0487 /
−0.0613) — merely unresolvable. "KEEP OPEN" is no better supported than
CLOSE. The honest disposition is **INCONCLUSIVE**, which is what the original
audit said. A further attempt needs a NEW prereg naming the estimand up front
and a bias-corrected estimator.

One angle did close in the claim's favour, against the reviewer's own brief:
low score autocorrelation does **not** mechanically manufacture this result
(zero-skill AR at matched ρ closes 5.0% of the time; genuine-skill-with-low-
autocorrelation closes 0/20). That mechanism is ruled out.

## The process lesson

I published a CLOSE, it was retracted, I produced a second CLOSE that reversed
the retraction's basis, and I withheld it pending adversarial review. The
review destroyed it. **Withholding the verdict was the only thing that worked**
— had I published on the strength of my own reasoning, this would have been
the second retraction on the same question in one day.
