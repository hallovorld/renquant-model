# Progress: content-addressed index for the PatchTST 43-fold corpus

STATUS:   delivered. Resolves the cross-repo factual contradiction blocking orch#590
          (HIGH) — two repositories were carrying opposite existence claims about the
          same input.

WHAT:     Adds `doc/research/evidence/2026-07-29-patchtst-43fold-corpus-index.json`
          (schema `artifact_corpus_index.v1`): per-file sha256 and byte size for every
          file in every fold, the top-level manifest and provenance sidecar, a root
          digest over the sorted `path:sha256` list, the Modal block, the dispatch app
          ids, the budget contract, and `failed_folds`. Both repos cite this file
          instead of asserting existence or non-existence in prose.

WHY/DIR:  One repo's memory record asserted the corpus "does not exist"; the other
          asserted a directly inspected 43-fold corpus. Both were reasoning from
          different evidence: the corpus is quarantined in session scratch BY the
          governing prereg — it must not enter any repo or the umbrella tree — so
          "absent from git" is the designed outcome and proves nothing either way. A
          content-addressed index is the reconciliation: it is inspectable, citable,
          and falsifiable by recomputation.

EVIDENCE: `[VERIFIED — hashed 2026-07-29 by direct file reads]` root digest
          `b8aa2d998c51fcd19c06afa3e63753f2ad5522cd2651d9f30bf60e038b291aa5`;
          43 fold dirs / 43 `*_model.pt` / 43 `*calibration.json`; cutoffs
          2023-10-02 … 2026-03-02; Modal `app_name: renquant-wf-patchtst` with dispatch
          app ids `ap-RIc3qj4D3yFfU9z7tAx4Rd` and `ap-HHid4LhAAD0heLm7Mlk4aW`;
          `budget_contract {max_total_usd: 25.0, pre_spend_usd: 1.45,
          rate_usd_per_hour: 0.59, timeout_seconds: 2900}`; `failed_folds: []`;
          `n_folds_promotable: 0` (quarantined by design, calibrators fitted
          separately). The provenance's `code_git_heads` pin all seven sibling repos at
          states that independently matched this machine's checkouts hours after the
          run. No model/IC claim is made here, so the §4(b) triad does not apply.

NEXT:     Cite this index from the model-side evidence trail and from the orchestrator
          MID record, replacing both the existence and the non-existence assertions.
          Honest limitation stated in the index itself: it proves WHAT is on disk and
          its digests, not that the bytes were produced by the run they claim — the
          Modal app ids and the git-head correspondence are corroboration, not proof.
