# AMENDMENT 1 to the corrected signal-evaluation prereg (model#90)

Written 2026-07-29. **Scope: provenance only.** The block-length defect from
the same review was fixed IN PLACE in the parent by the co-reviewer
(`f947a1d`, "block_length floor for Q2"), and this amendment deliberately does
**not** restate that rule — one rule written twice in two places, in two
wordings, is how a document starts contradicting itself.

## What this amendment adds

The review's second finding was that numbers cited from a session-scratch
path cannot be audited by another reviewer and vanish with the session. The
co-reviewer resolved it by **deleting** those numbers. That is safe but
lossy: the measurements were real and they are the reason the parent's design
looks the way it does.

So the artifacts are now **retained and content-addressed** instead, using the
reviewed tool from model#91 (MERGED 2026-07-29T08:38:58Z):

- location `/Users/renhao/renquant_bundles/corrected-eval-20260729/`
  (alongside the other frozen bundles, outside any session scratch);
- root digest
  `f6b6ef6d5055600df190da9d56c32453e31b71c54ff5beeda88e12caac0df38a`
  over **44 files** `[VERIFIED — tools/corpus_index.py generate, 2026-07-29]`;
- verifiable by `python tools/corpus_index.py verify --root <path> --index <index>`,
  which exits non-zero on any digest, missing-file or extra-file mismatch.

**Rule going forward for this prereg's line of work:** a number may be quoted
only if it is (a) reproducible from committed code, or (b) tied to a
content-addressed artifact root. Numbers meeting neither are removed, not
re-asserted — which is what the parent now does, and this amendment simply
moves specific measurements from category (neither) into category (b).

## What this amendment does NOT change

No subject, statistic, null, horizon, hypothesis, decision rule or block-length
rule. The parent, as amended in place, remains the single source for all of
those.

## Honest limitation

Content addressing proves WHAT the artifacts contain and makes any claim about
them falsifiable by recomputation. It does not prove the artifacts were
produced by the analysis they claim to come from — for that, the reviewable
evidence is the committed harness code plus the parent's frozen design, not a
digest.
