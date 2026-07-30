# Evidence: corpus cutoff-sanity + label-maturity audit ON THE TRADING AXIS

Replay log for the numbers quoted in `doc/progress/2026-07-30-corpus-trading-axis-audit.md`
and PR #109. Re-run this session, both corpora, same command, full raw output below —
nothing trimmed or paraphrased.

## Inputs (read-only, sha256-pinned)

| role | path | sha256 |
|---|---|---|
| clf corpus | `<scratch>/clf-wf/clf_wf_scores.parquet` | `1da3fcfab06af1e597ac0eb83dff4741ed3dd027de8b8a6b4d58979f5bc4efe4` |
| PatchTST corpus | `<scratch>/wf-eval/scores.parquet` | `6eb209e2491b26b18b7b687c7683f27f8e5cbe56592186bfbac68381e2606d18` |
| SPY trading-date axis | `RenQuant/data/ohlcv/SPY/1d.parquet` | `0987e3b638cb9659aac0d5d68e2688773ef40b5f6ec907c9176dec1b30a10f2c` |

`<scratch>` matches the placeholder in `doc/research/2026-07-29-traded-estimand-prereg.md`
(same two pinned corpora, same hashes, that doc's §2/§3/§5/§6). All three hashes were
re-computed this session with `shasum -a 256 <path>` immediately before the runs below,
confirming the inputs match the prior pins — no re-fetch, no mutation.

## Command (run once per corpus, axis and lookahead held fixed)

```
python3 tools/corpus_trading_axis_audit.py \
    --corpus <scratch>/clf-wf/clf_wf_scores.parquet \
    --axis RenQuant/data/ohlcv/SPY/1d.parquet \
    --lookahead 60
```

```
python3 tools/corpus_trading_axis_audit.py \
    --corpus <scratch>/wf-eval/scores.parquet \
    --axis RenQuant/data/ohlcv/SPY/1d.parquet \
    --lookahead 60
```

## Raw output — `clf_wf_scores.parquet`

```
corpus: clf_wf_scores.parquet
  rows=178191 dates=625 folds=43 span=2023-10-03 -> 2026-03-31
  axis: 2657 trading days from /Users/renhao/git/github/RenQuant/data/ohlcv/SPY/1d.parquet
  rows with score_date <= own cutoff: 0
  label maturity, 60 TRADING days:
    unverifiable score dates: 60/625 = 9.6%
    earliest: 2026-01-05 — its label needs data through 2026-04-01
    NOTE: unverifiable != immature. The label may be complete in the panel; the CORPUS cannot establish it. Do not describe such a corpus as label-verified.
  a BDay(60) bound on these dates would be SHORT on 99.4% of them, by mean +3.63 / max +10 calendar days

FAIL: unverifiable label fraction 9.6% > 0.0%
```
Exit code: `1`.

## Raw output — `wf-eval/scores.parquet`

```
corpus: scores.parquet
  rows=88750 dates=625 folds=43 span=2023-10-03 -> 2026-03-31
  axis: 2657 trading days from /Users/renhao/git/github/RenQuant/data/ohlcv/SPY/1d.parquet
  rows with score_date <= own cutoff: 0
  label maturity, 60 TRADING days:
    unverifiable score dates: 60/625 = 9.6%
    earliest: 2026-01-05 — its label needs data through 2026-04-01
    NOTE: unverifiable != immature. The label may be complete in the panel; the CORPUS cannot establish it. Do not describe such a corpus as label-verified.
  a BDay(60) bound on these dates would be SHORT on 99.4% of them, by mean +3.63 / max +10 calendar days

FAIL: unverifiable label fraction 9.6% > 0.0%
```
Exit code: `1`.

## Reconciliation with the progress doc / PR body

Both re-runs above reproduce, verbatim, the numbers already quoted in
`doc/progress/2026-07-30-corpus-trading-axis-audit.md` and the PR #109 body table
(`0` rows at-or-before-cutoff, `60/625 = 9.6%` unverifiable, earliest `2026-01-05`,
`99.4%` / mean `+3.63` / max `+10`). The SPY axis hash quoted in the progress doc
(`0987e3b638cb9659…1b30a10f2c`) was display-truncated there; the full 64-character
hash is recorded above.
