# Progress: fix a stale digest citation on the already-merged amendment-1 doc

STATUS:   delivered, with a dependency and a scope caveat both now stated
          explicitly (per codex BLOCKER x2). The cited digest is real and
          verified, but only with model#93's NOT-YET-MERGED tool fix; it is
          NOT reproducible with `tools/corpus_index.py` as currently merged
          on `main`. Separately, this remains an output-only forensic trace,
          not a repair of input/code provenance — the doc's own framing was
          tightened so it doesn't read as claiming more than that.

WHAT:     Updates `doc/research/2026-07-29-corrected-signal-evaluation-amendment-1.md`:
          the retained-bundle citation (root digest + file count) pointed at a
          snapshot that had since mutated. Re-verified and updated to the
          current state, with the model#93 dependency and the output-only
          scope stated up front rather than only in the trailing "Honest
          limitation" section.

WHY/DIR:  Found while fixing the same stale-digest issue on model#92 (a still-
          open PR touching sibling docs about the same bundle). This file
          isn't part of #92's diff — it merged earlier as part of model#90 —
          so the same class of fix needs its own PR here.

EVIDENCE: artifact:      `doc/research/2026-07-29-corrected-signal-evaluation-amendment-1.md`
          (this PR) `[VERIFIED — this PR's diff]`.
           prod or exp:   docs-only correction; no production artifact touched.
           existing data: re-verified twice this session, not trusted from any
          prior claim. (1) With model#93's branch code (`fix/corpus-index-
          self-reference`, APPROVED not yet merged): `VERIFY OK: 61 files,
          6969817 bytes, root_digest 901f0add…` `[VERIFIED — tools/
          corpus_index.py verify using that branch, this session]`. (2) With
          the currently-MERGED `tools/corpus_index.py` on `main`: FAILS —
          `root digest mismatch` + `present in corpus but not in index:
          INDEX.json` `[VERIFIED — ran the merged tool directly against the
          bundle, this session, reproduced codex's exact finding]`. Both are
          true simultaneously; the doc now says so instead of implying
          current-tool reproducibility.
           best-known?:   n/a — a provenance citation fix, not a model/
          statistic claim.
           scope:         "single-line factual correction plus a scope/
          dependency caveat; no statistic, lag grid, subject list, decision
          rule, or block-length rule changed. Content-addressing an output
          tree does not prove those outputs came from the claimed analysis —
          restated prominently, not just in the trailing caveat section."

NEXT:     Model#93 merging resolves ONLY the tool-verification dependency
          (the merged `corpus_index.py` would then reproduce `VERIFY OK`
          without needing that branch's code) — re-run `verify` with the
          merged tool at that point and drop the "not yet reproducible"
          caveat if it passes. It does NOT resolve the output-only
          provenance limitation (Honest limitation section): the bundle
          remains an appendable directory, not an immutable snapshot, so the
          "does not prove the artifacts were produced by the claimed
          analysis" caveat stays regardless of #93's merge status. If the
          bundle receives further writes before #93 merges, the digest
          invalidates again immediately.
