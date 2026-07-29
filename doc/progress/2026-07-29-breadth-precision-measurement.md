# Relocate breadth-precision measurement from orchestrator#601

STATUS:    delivered. Byte-identical relocation — no in-transit fixes needed
           (unlike the capacity-power-memo relocation, this memo's two prior
           MED review findings, reviewable derivation and per-number
           provenance, were already resolved on the source branch before the
           BLOCKER that triggered this move).

WHAT:      Relocates `doc/research/2026-07-29-breadth-does-not-buy-evaluation-precision.md`
           and `tools/breadth_precision_verify.py` from
           `hallovorld/renquant-orchestrator#601`, byte-identical. Re-ran the
           verifier here against the same sha256-pinned inputs before
           committing — `PIN OK` on both, and the emitted tables (ladder,
           fit `0.03530 + 0.9816/N`, 91% irreducible share, -2.9%/-4.4%
           deltas, survivorship probe) match the memo exactly.

WHY/DIR:   `renquant-orchestrator`'s review (round 2, BLOCKER) found this is
           model-evaluation research — it reads the clf 43-fold score
           corpus, computes per-date IC under cross-sectional subsampling,
           fits a variance model, and probes the production panel for
           survivorship — not orchestration. Per the umbrella multi-repo
           code-placement rule (model research -> `renquant-model`, never
           the orchestrator), this completes that move so
           `orchestrator#601` can be reduced to a relocation record. Same
           pattern as the capacity-power-memo relocation
           (`doc/progress/2026-07-24-capacity-power-memo.md`, this repo) and
           the factorial-HFR study before it.

EVIDENCE:
  artifact:      `tools/breadth_precision_verify.py` (committed, this PR);
                 inputs pinned `clf_wf_scores.parquet` sha256
                 `1da3fcfa…5bc4efe4` and `clf_wf_manifest.json` sha256
                 `c1cb22e2…7bd092086`; production panel
                 `data/transformer_v4_wl200_clean.parquet` (this repo's
                 `data` symlink -> `../RenQuant/data`), READ-ONLY.
  prod or exp:   EXPERIMENT/measurement + a committed verifier. No
                 production data, config, or artifact written; the panel
                 was opened for read only.
  existing data: Re-ran the verifier in this repo before committing (see
                 WHAT) rather than trusting the orchestrator-branch output
                 by recall.
  best-known?:   Yes for this corpus, independently checkable from this
                 branch. Explicitly NOT claimed: that breadth fails to
                 improve the MODEL, or that the 830-name panel should not
                 be built (memo §6).
  scope:         `renquant-model` docs + one tool. No pin advanced, no
                 training run, no live surface touched.

NEXT:      None from this relocation PR — the memo authorizes nothing; it
           supplies a measured number for GOAL-6 Stage 2 scoping. The
           orchestration-side sequencing implication is tracked in
           `orchestrator#601`'s relocation-record progress doc, which cites
           this PR as the evidence owner.
