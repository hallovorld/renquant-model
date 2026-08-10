# xgb_rev_60d prereg — the reversal twin, all choices frozen pre-run

STATUS:    design only; no harness code, no runs, no label-derived
           numbers.

WHAT:      doc/design/2026-08-10-xgb-rev-60d-prereg.md — one new frozen
           element (a 60-column reversal feature list: 12 alpha158
           windowed families — MA/RESI/RSQR/STD/IMXD/CORR/CORD/VMA/
           VSTD/WVMA/VSUMP/VSUMN — × windows 5/10/20/30/60, disjoint
           from the momentum twin's 70, features_sha256 pinned in-doc).
           Everything else inherited verbatim from the momentum v2
           prereg (model#213): the 8 embargoed folds with 91-calendar-
           day gaps, the per-row purge rule, PARAMS + seeds (42,43,44),
           the four PASS/KILL legs (NaN fold counts non-positive), the
           corpus sha pin, artifact_kind + null-until-countersigned
           verdict machine-surface rules, and an explicit no-sweeps /
           deviations-void-the-run freeze clause. The positive-control
           planted signal is frozen in the doc (0.35*RESI20 +
           0.25*CORR60) so the follow-up harness has no freedom.

WHY/DIR:   The momentum twin's machinery (embargoed folds, purge,
           committed verifier) is a durable asset; the cheapest honest
           next hypothesis is its reversal complement — deviation-from-
           anchor + liquidity-provision conditioning (Jegadeesh 1990;
           Nagel 2012; Campbell–Grossman–Wang 1993). Expectation set IN
           THE DOC: at a 60-session label the reversal prior is weak and
           KILL is the expected outcome; no gate moves because of it.

EVIDENCE:  artifact:      all 60 columns + label present, zero overlap
                          with the momentum 70 [VERIFIED — read from the
                          parquet schema via pyarrow.parquet.read_schema,
                          2026-08-09; 178-column schema]; feature-list
                          sha [DERIVED — sha256(json.dumps(FEATS)),
                          the momentum harness convention]; corpus pin
                          [VERIFIED — inherited unchanged from the
                          merged mom v2 prereg, same corpus file].
           prod or exp:   experiment design; corpus read-only, schema
                          read only (no data loaded).
           existing data: the merged mom v2 prereg + frozen harness as
                          the structural template; no reversal numbers
                          exist anywhere.
           best-known?:   yes — the feature selection RULE is stated in
                          the doc (disjoint families, exact-difference
                          columns excluded, K-bar/level/fundamental
                          columns excluded) so the table is derivable,
                          not curated.
           scope:         one design doc + this progress doc; no harness
                          code, no runs, no label-derived numbers; the
                          harness lands as a separate follow-up PR bound
                          to the frozen text after this PR merges.
TESTS:     none run (design doc only — nothing executable on this
           branch). The follow-up harness PR carries the committed
           harness + fail-closed verifier + both control JSONs
           (positive PASS / null KILL, hard exit codes) before any real
           run, per §3 and §5 of the doc.

NEXT:      merge this PR → follow-up harness PR bound to the frozen
           text (feature sha, fold table, params, pin) → controls
           committed → ONE real execution → result JSON checked by the
           committed verifier, verdict null until countersigned.
