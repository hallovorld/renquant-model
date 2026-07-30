# Run artifacts — 2026-07-30 momentum on a dividend-adjusted total-return series

Produced by the run of `tools/momentum_total_return_run.py` against the frozen
prereg `doc/research/2026-07-30-momentum-total-return-prereg.md`. The prereg and
runner were committed in `048975f` BEFORE these files existed; the results were
appended afterwards. That git order is the evidence that nothing was selected
after seeing a number.

| file | what it is |
|---|---|
| `run.log` | full stdout of the frozen run, including the shuffle self-check, both input pin verifications, the primary, the 40-shuffle control calibration, §5b, D1 and the descriptive screen panel |
| `results.json` | machine-readable form of the same, incl. every placebo `|t|` and all 40 false-flag replications |
| `robustness.json` | post-run diagnostics (`tools/momentum_total_return_robustness.py`): the look-ahead proof, leave-one-block-out, the decile profile, and the NaN-name exclusion |
| `total_return_validation.json` | Part-1 validation report from `tools/build_total_return_series.py` (ex-div-day gap before/after, negative control, return identity, per-ticker adjustment factors) |
| `dividend_column_semantics.json` | the empirical `dividend`-column semantics from `tools/dividend_column_semantics.py` |
| `tr_matrix_metadata.json` | build metadata + sha256 of the pinned factor matrix |

The two large pinned inputs (`total_return_close.parquet` 4.0 MB,
`momentum_factor_matrix_tr.parquet` 76 MB) are NOT committed. They are
reproducible from the umbrella OHLCV corpus by running, in order,
`tools/build_total_return_series.py` then `tools/build_tr_factor_matrix.py`,
and their sha256 pins are recorded in the prereg §3 and re-verified by the
runner, which aborts on mismatch.

**Verdict recorded here is `UNRESOLVED / TILT-NOT-EXCLUDED`. Nothing is
licensed** — no model, no shadow deployment, no capital action.
