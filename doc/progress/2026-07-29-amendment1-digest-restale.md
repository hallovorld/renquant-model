# Progress: fix a stale digest citation on the already-merged amendment-1 doc

STATUS:   delivered. One-line factual correction to an already-merged doc.

WHAT:     Updates `doc/research/2026-07-29-corrected-signal-evaluation-amendment-1.md`:
          the retained-bundle citation (root digest + file count) pointed at a
          snapshot that had since mutated. Re-verified and updated to the
          current state.

WHY/DIR:  Found while fixing the same stale-digest issue on model#92 (a still-
          open PR touching sibling docs about the same bundle). This file
          isn't part of #92's diff — it merged earlier as part of model#90 —
          so the same class of fix needs its own PR here.

EVIDENCE: artifact:      `doc/research/2026-07-29-corrected-signal-evaluation-amendment-1.md`
          (this PR) `[VERIFIED — this PR's diff]`.
           prod or exp:   docs-only correction; no production artifact touched.
           existing data: re-verified directly this session, not trusted from
          any prior claim: regenerated the bundle's index with
          `tools/corpus_index.py` (model#93's self-exclusion fix, so an
          `INDEX.json` written into the bundle root doesn't corrupt its own
          digest) and ran `verify` — `VERIFY OK: 61 files, 6969817 bytes,
          root_digest 901f0addd19b7381775f9dd593e046b862863b8bb04bb0de7260e
          b405423810a` `[VERIFIED — tools/corpus_index.py verify, this
          session]`. This matches the digest independently cited on
          model#92's `patchtst-closure-retraction.md` as the bundle's
          mutated state, confirming both records now agree.
           best-known?:   n/a — a provenance citation fix, not a model/
          statistic claim.
           scope:         "single-line factual correction; no statistic, lag
          grid, subject list, decision rule, or block-length rule changed."

NEXT:     None. If the bundle receives further writes, this digest (and
          model#92's matching one) will need re-verification again before
          being cited — flagged explicitly in both docs now.
