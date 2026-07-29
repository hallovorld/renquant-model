# Corrected signal evaluation — RESULTS

Prereg: `2026-07-29-corrected-signal-evaluation-prereg.md` (model#90) as amended
in place (`block_length = max(60, L)`) and by amendment 1 (provenance).

**Every number below is tied to a content-addressed artifact root**, which is
why they can be quoted at all — an earlier draft cited a session-scratch path
and was correctly rejected as unauditable:

- artifacts `/Users/renhao/renquant_bundles/corrected-eval-20260729/`
- root digest `f6b6ef6d5055600df190da9d56c32453e31b71c54ff5beeda88e12caac0df38a`
  over 44 files, verifiable with
  `python tools/corpus_index.py verify --root <path> --index <index>` (model#91)

Inference is `renquant_model_common.dependence_aware_mean` (model#89): an
effect counts as resolved only when the block t, a moving-block bootstrap CI
and the leave-one-block-out bounds **all agree in sign**. That is strictly
stricter than a t-test on 8–12 blocks, which leans on a normal approximation
it has not earned.

## Q1 — does each subject beat its OWN persistence?

Decision statistic `d = REAL − persistence` on per-date rank IC, 142-name
intersection, both arms on the same score dates, `block_length = 60`, 1500
bootstrap resamples
`[VERIFIED — dependence_aware_mean over the artifacts above, 2026-07-29]`:

| subject | n dates | mean d | block t | bootstrap 90% CI | leave-one-block-out | three-view |
|---|---|---|---|---|---|---|
| **prod XGB** | 448 | **+0.0359** | +1.23 (8 blk) | **[+0.0218, +0.0787]** | [+0.0140, +0.0428] | **RESOLVES** |
| **certified clf** | 565 | **+0.0113** | +1.31 (10 blk) | **[+0.0049, +0.0275]** | [+0.0046, +0.0126] | **RESOLVES** |
| PatchTST | 565 | **−0.0488** | −2.31 (10 blk) | **[−0.0772, −0.0050]** | [−0.0678, −0.0431] | **RESOLVES (negative)** |

**All three verdicts survive the stricter rule.** The two models the book
relies on beat their own 60-day-old scores on every view; PatchTST loses to
its own stale self on every view.

## The contrast that makes the above meaningful

The same estimator on the RAW IC arms (levels, not differences) resolves for
only ONE subject `[VERIFIED — same artifacts]`:

| subject | mean IC | block t | bootstrap 90% CI | three-view |
|---|---|---|---|---|
| prod XGB | +0.0907 | +1.48 | [+0.0047, +0.2301] | RESOLVES |
| certified clf | +0.0830 | +1.52 | [−0.0287, +0.1749] | does NOT resolve |
| PatchTST | +0.0164 | +0.57 | [−0.0487, +0.0686] | does NOT resolve |

Note the certified clf: its raw-IC block t (+1.52) is the LARGEST of the three
and its bootstrap interval still crosses zero. Reading the t alone would have
called it the strongest subject; reading three views calls its level
unresolved while its *paired difference* resolves.

That pattern is expected rather than contradictory — pairing against the
model's own stale score removes the common market/regime noise that dominates
the level — but it is worth stating plainly: **on this data the differences
are better determined than the levels**, and any claim about "the IC of model
X" is weaker than a claim about "model X beats its own persistence".

## What is and is not established

- Established: both production-relevant models carry fresh information beyond
  score persistence, on three independent views of the uncertainty.
- Established: PatchTST's walk-forward edge is worse than its own stale score,
  robustly. Formal closure still needs its own registered kill rule — model#87
  is retracted and may not be reused.
- NOT established: the absolute cross-sectional IC of the certified clf. Its
  level does not resolve, and no claim in this programme should quote it as if
  it did.
