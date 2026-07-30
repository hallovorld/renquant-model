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
| `raw_input_manifest.json` | canonical pin on the RAW layer (see below) |

The two large pinned inputs (`total_return_close.parquet` 4.0 MB,
`momentum_factor_matrix_tr.parquet` 76 MB) are NOT committed. They are
reproducible from the umbrella OHLCV corpus by running, in order,
`tools/build_total_return_series.py` then `tools/build_tr_factor_matrix.py`,
and their sha256 pins are recorded in the prereg §3 and re-verified by the
runner, which aborts on mismatch.

**Raw-layer reproducibility (added in response to codex review1 BLOCKER1).**
A pin on the two DERIVED parquets above only proves that file didn't change;
it says nothing about the 145-ticker `data/ohlcv/<T>/1d.parquet` raw corpus or
the watchlist config that produced them, so a future rebuild against an
edited umbrella corpus could not tell a real data change from a builder bug.
`raw_input_manifest.json` closes that gap: `tools/raw_input_manifest.py`
content-addresses every raw ticker file (reusing `tools/corpus_index.py`,
the same canonical digest construction used elsewhere in this repo) plus the
watchlist config's own sha256, into one committed pin —
`corpus_fingerprint_sha256=48728e24bf2a043aec5529ece14199412372010ff6396bb83fd25ef26f53ad62`,
`config_sha256=f52d096e0a491008a051fb1fc9c0114a9bb98f22788f3b36b4b531274cb31710`
`[VERIFIED — python tools/raw_input_manifest.py generate --out doc/research/data/2026-07-30-momentum-total-return/raw_input_manifest.json, this session]`.
Both `build_total_return_series.py` and `build_tr_factor_matrix.py` now call
`raw_input_manifest.verify_or_abort()` before touching any raw file and ABORT
on a mismatch; re-running both against this pin reproduced
`total_return_close.parquet` sha256 `8c23496ee351757ec1f953597f9705168542f67cc16f209385091bb60d741ac9`
and `momentum_factor_matrix_tr.parquet` sha256
`85c27fc1d5a56a4c585c03db22dc8be0123badfc83ef23e46cdd358c704eb35a` — bit-identical
to the pins already recorded in the prereg §3, confirming the raw corpus has
not moved since the original run
`[VERIFIED — re-ran both builders this session, diffed sha256 against prereg §3]`.

**Verdict recorded here is `UNRESOLVED / TILT-NOT-EXCLUDED`. Nothing is
licensed** — no model, no shadow deployment, no capital action.
