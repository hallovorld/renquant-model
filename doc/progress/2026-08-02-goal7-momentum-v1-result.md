# GOAL-7 v1 verdict: UNRESOLVED-METHOD at the calibration gate — published verbatim

STATUS: complete (the single §7 shot is consumed and sealed; docs-only PR).
WHAT: doc/research/2026-08-02-goal7-momentum-v1-result.md + the sealed
result.json/EXECUTION_CLAIM.json committed byte-verbatim. The frozen
calibration family (AR(1) + Amendment-2 bootstrap_max adequacy) REFUSED the
realized IC series: max ACF deviation 0.4047 vs threshold 0.1645 (B=500,
alpha=0.05), no collapse to MA per the reviewed rule. No H1/H2 comparison
happened; nothing licensed, nothing killed.
WHY/DIR: honest-negative discipline — the refusal machinery the A4 bundle
validated fired on our own study; publishing the measured 40-lag ACF
(rho_1=0.9269, oscillatory decay) is what makes a v2 designable against
MEASURED dependence.
EVIDENCE:
  artifact:      data/2026-08-02-goal7-momentum-v1-result/result.json
                 (sha256 46118a12..., byte-identical to the sealed store copy
                 at ~/renquant-data-store/goal7-momentum-prereg-run/)
  prod or exp:   exp — research verdict record; no serving surface
  existing data: n_dates 2378, thin-skipped 221, rho_1 0.9269, max_abs_dev
                 0.4047 vs bootstrap_threshold 0.1645, overlap_ma bar 2.463
                 (published, unused) `[VERIFIED — result.json, this commit]`
  best-known?:   yes — the one licensed invocation's sealed output; a rerun is
                 mechanically refused (exit 4) and would be method-shopping
  scope:         docs-only; the claim/result stay sealed 0444 in the store;
                 v2 (if pursued) is a NEW prereg through the same door
NEXT: operator reads the verdict; if the line continues, a v2 prereg with a
dependence-adequate null (gap-block geometry or real-series bootstrap per the
standing block-length rule) — direction sketched in the research doc, NOT
preregistered here. AC6: N/A — research docs.
