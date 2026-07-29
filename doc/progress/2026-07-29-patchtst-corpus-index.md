# Progress: verifiable content-addressed reference for the PatchTST corpus

STATUS:   delivered. Round-2 rework after codex HIGH: v1 was an inventory, not a
          reference — a reader could only trust an asserted hash.

WHAT:     (1) `tools/corpus_index.py` — a self-contained generator/verifier with a
          stable CLI (`generate --root --out`, `verify --root --index`, exit 1 on any
          mismatch); (2) the digest construction written into the artifact itself
          (line format, sort, join, hash, symlink and directory handling) so it is
          reproducible without reading the implementation; (3) the corpus RETAINED at
          a durable path outside session scratch; (4) the regenerated index.

WHY/DIR:  codex, correctly: "a reader can only trust an asserted hash; they cannot
          reproduce or fetch the identified bytes once the session disappears." All
          three defects are addressed rather than argued with — the location was
          ephemeral, the digest existed only in prose, and nothing could recompute it.

EVIDENCE: corpus retained at `/Users/renhao/renquant_bundles/patchtst-wf-corpus-b4e47e2c`
          (14 MB, alongside the existing frozen bundles) `[VERIFIED — rsync + du]`.
          The regenerated index over the RETAINED copy reproduces the root digest
          computed earlier over the scratch original, byte for byte:
          `b8aa2d998c51fcd19c06afa3e63753f2ad5522cd2651d9f30bf60e038b291aa5`
          `[VERIFIED — tools/corpus_index.py generate + verify, 133 files,
          14,808,677 bytes, VERIFY OK]`. That agreement is independent evidence on two
          counts: the copy preserved bytes exactly, and the formalised construction is
          equivalent to the prose one it replaces. Verifier suite 7/7
          `[VERIFIED — pytest tests/test_corpus_index.py]`, pinning what an asserted
          hash cannot catch: one flipped byte, a missing file, an extra file, mtime
          changes NOT altering the digest while content changes do, and symlinks
          rejected rather than silently followed.

          Scope, stated so it is not overclaimed: this proves WHAT bytes exist and that
          any future claim about them is falsifiable by recomputation. It does not
          prove those bytes came from the run they claim — the Modal app ids and the
          per-repo git heads in the provenance remain corroboration, not proof.

NEXT:     With a verifiable reference in place, #590 / #85 / #87 can cite it to settle
          the existence question. They still may not cite the numbers computed with
          the defective harness — that is a separate blocker resolved by model#89/#90.
