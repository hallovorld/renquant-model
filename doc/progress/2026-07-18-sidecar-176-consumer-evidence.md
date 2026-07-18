# Progress: AC-1 sidecar 176-column consumer evidence (calibrator loaders)

Date: 2026-07-18
Scope: test-only companion to the renquant-base-data RFC
`doc/design/2026-07-18-rawlabel-sidecar-sentiment-reconciliation.md` (AC-1)
and its evidence appendix (the base-data PR carries the full inventory).

## What this PR adds

- `tests/test_sidecar_176_consumer_evidence.py` — executable proof that both
  model-repo sidecar readers are SAFE at the migrated 176-column contract:
  - `renquant_model_patchtst.fit_calibrator._load_panel_with_raw_label`
    (fit_calibrator.py:166 reads `columns=["ticker", "date", er_label_col]`)
  - `renquant_model_gbdt.fit_calibrator_alpha158_fund._load_expected_return_labels`
    (fit_calibrator_alpha158_fund.py:154, same column-pruned read)
  Both merge only keys + `fwd_60d_excess_raw` from a fixture carrying the
  builder's exact 176-column schema; no sentiment column is consumed.
- `tests/data/rawlabel_sidecar_columns_176.json` — embedded export of
  base-data `RAWLABEL_SIDECAR_COLUMNS` (main `b72dd92`); drift guard =
  base-data `tests/test_rawlabel_sidecar_schema_export.py`.

## What this PR does NOT do

No behavior change, no migration, no served-file mutation.
