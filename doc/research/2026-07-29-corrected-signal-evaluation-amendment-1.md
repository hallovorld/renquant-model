# AMENDMENT 1 to the corrected signal-evaluation prereg (model#90)

Written 2026-07-29. **Scope: provenance only.** The block-length defect from
the same review was fixed IN PLACE in the parent by the co-reviewer
(`f947a1d`, "block_length floor for Q2"), and this amendment deliberately does
**not** restate that rule — one rule written twice in two places, in two
wordings, is how a document starts contradicting itself.

## What this amendment adds — and what it does NOT repair

The review's second finding was that numbers cited from a session-scratch
path cannot be audited by another reviewer and vanish with the session. The
co-reviewer resolved it by **deleting** those numbers. That is safe but
lossy: the measurements were real and they are the reason the parent's design
looks the way it does.

So the artifacts are now **retained and output-content-addressed** — a
forensic trace of what one session's outputs contained, NOT a provenance
repair for confirmatory inputs/results (see Honest limitation below; this is
stated up front here, not just at the end, because the framing below could
otherwise read as overclaiming it). Using the reviewed tool from model#91
(MERGED 2026-07-29T08:38:58Z):

- location `/Users/renhao/renquant_bundles/corrected-eval-20260729/`
  (alongside the other frozen bundles, outside any session scratch);
- root digest
  `901f0addd19b7381775f9dd593e046b862863b8bb04bb0de7260eb405423810a`
  over **61 files**, produced by regenerating the index with `tools/
  corpus_index.py` from model#93's branch (`fix/corpus-index-self-
  reference`, APPROVED but NOT YET MERGED as of this writing) —
  `[VERIFIED — tools/corpus_index.py verify using that branch's code, this
  session: "VERIFY OK: 61 files, 6969817 bytes"]`. **This digest is NOT yet
  reproducible with `tools/corpus_index.py` as currently merged on `main`**:
  the merged tool does not self-exclude an `INDEX.json` written inside its
  own indexed root, and running `verify` with it against this exact bundle
  fails with `root digest mismatch` + `present in corpus but not in index:
  INDEX.json` `[VERIFIED — ran the merged tool directly against this
  bundle, this session, reproduced that exact failure]`. Reproduction
  requires model#93 to merge first.
- verifiable, once model#93 merges, by `python tools/corpus_index.py verify
  --root <path> --index <index>`, which exits non-zero on any digest,
  missing-file or extra-file mismatch.

  CORRECTION (per long-term-agreements.md entry 10): this line originally
  cited root `f6b6ef6d…` over 44 files — that snapshot mutated (more
  outputs were appended to the bundle after the digest was taken), retracted
  on model#92's own thread and re-verified here against the current,
  freshly-sealed state. Any further writes into the bundle invalidate the
  digest above too and require re-verification before being cited again.

**Rule going forward for this prereg's line of work:** a number may be quoted
only if it is (a) reproducible from committed code, or (b) tied to a
content-addressed artifact root whose verification is actually reproducible
with the currently-merged tooling. Numbers meeting neither are removed, not
re-asserted. The measurements below currently satisfy a weaker version of
(b) — content-addressed, but not yet reproducibly verifiable pending
model#93 — and that gap is stated here rather than papered over.

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
