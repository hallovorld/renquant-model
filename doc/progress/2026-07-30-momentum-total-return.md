# Dividend-adjusted total-return series + a re-registered momentum study   (PR #110)

STATUS:   delivered as `UNRESOLVED / TILT-NOT-EXCLUDED` — nothing licensed, no
          model, no shadow deployment, no capital action. Part 1 (the data
          fix) is VALIDATED. Part 2 (the momentum study built on it) cleared
          every bar the frozen design *contains* but failed the paired
          baseline gate, so the frozen rule maps it to UNRESOLVED.

          Three commits before review: `048975f` (prereg FREEZE, zero result
          files), `d256d8f` (results appended, 3-line diff to the frozen
          §§0–9), `4166e4c` (§7 adversarial review response — 1 CRITICAL + 4
          MAJOR corrections, verdict unchanged). Two codex CHANGES_REQUESTED
          reviews followed; this round (below) fixes both.

          THIS ROUND (codex review round 2, 2 findings, both fixed here):
          [BLOCKER] this progress doc was a narrative report instead of the
          required C5 STATUS:/WHAT:/WHY-DIR:/EVIDENCE:/NEXT: shape — fixed by
          this rewrite. [MED] provenance tags used `[VERIFIED-now]` /
          `[VERIFIED-prior]` / bare `[ASSUMED]` instead of LONG #10's
          `[VERIFIED — <command/file>]` / `[VERIFIED — prior work, <ref>]` /
          `[ASSUMED — <why>]` shapes — fixed across this doc and the prereg.

          Also fixed this round, from codex review round 1's still-open
          BLOCKER (the adversarial-review BLOCKER in that same round was
          already closed by `4166e4c` before round 1 finished posting — see
          RAW-INPUT MANIFEST below): `tr_matrix_metadata.json` recorded only
          an ephemeral `/private/tmp/...` scratch path as its derived-file's
          "source", with no committed record of the 145 raw OHLCV inputs
          that fed it — so a future rebuild against an edited umbrella corpus
          had no way to tell a real data change from a builder bug.

WHAT:     `tools/build_total_return_series.py` builds `TR[t] = close[t] /
          prod_{s>t}(1+dividend[s]/close[s])`, a dividend-adjusted
          total-return close series, per the empirically-established
          `dividend` column semantics (sentinel `0.0`, not `1.0`/NaN; ex-date,
          not pay-date; same split-back-adjusted axis as `close`).
          `tools/build_tr_factor_matrix.py` rebuilds the momentum/vol/beta/mdd
          factor library on that series (`_tr` suffix) paired against the
          original price-only build (`_px` suffix) in one frame.
          `tools/momentum_total_return_run.py` runs one pre-registered test:
          primary arm `mom_12_1_tr`, `h=120`, `dependence_aware_mean` block
          `t` with `block_length=h`, on holdout 2021-10-08→2026-07-29
          (Bonferroni `m=2`, programme-wide test #26).

          RAW-INPUT MANIFEST (this round): `tools/raw_input_manifest.py` —
          new — content-addresses all 145 raw `data/ohlcv/<T>/1d.parquet`
          files plus the watchlist config's own sha256 into one manifest,
          reusing `tools/corpus_index.py`'s existing canonical digest
          construction (content-addressed index, generate/verify CLI) rather
          than a second hashing implementation. Both builder scripts now call
          `raw_input_manifest.verify_or_abort()` before touching any raw
          file, and ABORT on a mismatch instead of silently building on
          inputs the committed pin no longer describes. Committed pin:
          `doc/research/data/2026-07-30-momentum-total-return/raw_input_manifest.json`.
          `tests/test_raw_input_manifest.py` (7 tests, synthetic fixture, no
          real umbrella data touched) pins: every raw file + the config is
          hashed and included; SPY is not double-counted when it is already
          in the watchlist (matches production: SPY IS one of the 145 names,
          not a 146th); generate/verify round-trips; a tampered raw file or a
          changed config fails verification; a missing raw file aborts loudly
          instead of silently skipping it; the digest is stable across
          repeated builds.

WHY/DIR:  `doc/research/2026-07-30-momentum-horizon-prereg.md` is `ABORTED —
          INVALID CONTROL`. Its erratum listed three defects a corrected
          registration would have to fix: (1) the placebo leaked labels
          across dates on an interleaved frame; (2) selecting the arm on
          block `t` was structurally biased because `block_length=h` makes
          the block count fall ~12× as the horizon rises; (3) the price
          series was not dividend-adjusted, which the aborted run itself
          named as the likely explanation for its own headline pattern (a
          monotone rise of the spread with holding horizon — exactly what an
          omitted, horizon-accumulating dividend produces). All three are
          fixed here, in git order, before the primary was computed.

          The raw-input manifest (this round) closes a fourth, review-raised
          gap: reproducibility of the STUDY, not the theory — a pin on a
          derived file proves the file didn't change, not that the inputs
          that built it are the ones a future rebuild would read.

EVIDENCE:
  artifact:       `doc/research/2026-07-30-momentum-total-return-prereg.md`
                  (frozen §§0–9 + appended RESULTS + §7 adversarial review +
                  §8 raw-input manifest, this round) and
                  `doc/research/data/2026-07-30-momentum-total-return/`
                  (`results.json`, `robustness.json`,
                  `total_return_validation.json`, `run.log`,
                  `tr_matrix_metadata.json`, `raw_input_manifest.json` —
                  this round).
  prod or exp:    EXPERIMENT. No model built, no shadow deployment, no
                  capital action, no production path written.
  existing data:  Yes, all RE-MEASURED this session, not recalled:
                    ex-div-day gap, raw → TR-adjusted: −66.6 bp (t=−20.6) →
                      −4.8 bp (t=−1.55), 92.7% removed; with ticker+date
                      fixed effects: −63.7 bp (t=−25.1) → −3.2 bp (t=−1.33)
                    return identity over 4,344 events: max error 4.44e−16
                    `_px` twin vs pinned price-only library: max|diff|
                      0.000e+00 on all 14 factors, 364,736 rows
                    primary, AS REGISTERED: E2 = +0.4310 SD, block t=+3.767
                      on 10 blocks (programme bar 3.1019)
                    primary, CORRECTED (§7 review Correction 3, block-count
                      erratum): t=+3.258 on 9 blocks — the labelled
                      statistic series is 1,085 dates not 1,205, so
                      `_blocks()`'s 10th "block" holds 5 dates, not 120
                    name-dimension robustness (§7 review CRITICAL): drop 5
                      largest name contributors (SMCI/APP/LITE/PLTR/VRT,
                      3.4% of names) → t=+1.871 (FAILS bar); median spread
                      instead of mean → t=+1.964 (FAILS bar)
                    §5b paired baseline gate: t=+1.682, Holm p=0.093 — FAILS
                      → maps to the frozen UNRESOLVED verdict
                    D1 (dividend-confound-refutation) diagnostic: paired
                      TR-minus-price delta −0.0075/−0.0088/−0.0107/−0.0103 at
                      h=20/60/120/250, all |t|≤1.74 — ≈2% of the effect and
                      negative, refuting the dividend confound as the
                      explanation of the ABORTED run's headline pattern
                    raw-input manifest (this round): corpus_fingerprint_sha256
                      `48728e24bf2a043aec5529ece14199412372010ff6396bb83fd25ef26f53ad62`,
                      config_sha256
                      `f52d096e0a491008a051fb1fc9c0114a9bb98f22788f3b36b4b531274cb31710`
                    re-running both builders against that pin THIS SESSION
                      reproduced `total_return_close.parquet` sha256
                      `8c23496ee351757ec1f953597f9705168542f67cc16f209385091bb60d741ac9`
                      and `momentum_factor_matrix_tr.parquet` sha256
                      `85c27fc1d5a56a4c585c03db22dc8be0123badfc83ef23e46cdd358c704eb35a`
                      — bit-identical to the two pins already recorded in the
                      prereg §3 when it was frozen, confirming the raw
                      OHLCV corpus has not moved since
                  `[VERIFIED — re-ran tools/build_total_return_series.py and
                  tools/build_tr_factor_matrix.py this session, diffed
                  sha256 against prereg §3 and tr_matrix_metadata.json]`.
  best-known?:    Yes for this dividend-adjustment methodology on this
                  watchlist — the first total-return series built for this
                  corpus. NOT claimed: that momentum orders the
                  cross-section (full-sample IC t=+0.589 ≈ 0, U-shaped
                  decile profile, reported post-hoc as a caveat, not
                  pre-registered).
  scope:          `renquant-model` tools + docs only. No pin advanced in any
                  other repo, no umbrella write, no live surface touched.

VALIDATION:
          `python3 -m pytest tests/test_momentum_total_return_shuffle.py
          tests/test_raw_input_manifest.py tests/test_corpus_index.py -v`
          — 31 passed, 0 failed, this session.

          `python3 tools/build_total_return_series.py` and
          `python3 tools/build_tr_factor_matrix.py` re-run this session
          end-to-end against the committed raw-input pin: both printed
          `RAW INPUT PIN OK`, both wrote derived-file sha256 values
          identical to the ones pinned in the prereg §3 (quoted above), and
          `build_total_return_series.py` reproduced `built 145 series (111
          payers / 34 non-payers)` — unchanged from the original run.

NEXT:     None — nothing is licensed by this study, so nothing downstream is
          unblocked. The prereg's §7/§8 successor list (name-dimension
          robustness gate, fixed block partition, non-contiguous shuffle
          fixture, and 6 more) are candidate items for a FUTURE
          re-registration; this PR does not authorize or schedule one.
