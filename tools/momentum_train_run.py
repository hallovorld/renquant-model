#!/usr/bin/env python3
"""Momentum TRAIN CLI — wires REAL readers into the pure core. (GOAL-7 slice 2)

READ-ONLY over the live surfaces (RenQuant data/ ohlcv + panel + sectors) with
per-file digest RECORDING (not pinning — design §1); writes ONLY under
--out-root. NO launchd/schedule wiring lives here or anywhere in this slice:
machine landing is slice 5 and is operator-gated (design build order).

``--params-version`` (model#199 build item 2) selects which FROZEN param set
to train — v0 (252/21, the slow lane) or v1_fast (63/5, the fast shadow
lane). One construction, two clocks; each lane publishes into its OWN
--out-root (own ledger, own dated dirs) under the SHARED dated-artifact
basename (see ARTIFACT_BASENAME). Default v0: existing invocations are
unchanged.

Exit codes: 0 ok (incl. --dry-run, and RECONCILED — see below); 2 usage;
3 surfaces missing / refused; 4 artifact for this cutoff already exists AND
is already ledgered (append-only: never overwritten; a disagreeing re-run is
a dispute to investigate); 5 the ledger refused the append (the finalized
artifact remains on disk — it is never re-trained — and a retry reconciles
by appending its ledger row once the cause clears).

TWO-FILE PROTOCOL (codex review round 3, PR #196): the artifact is finalized
(staging write + atomic rename) BEFORE the ledger append is attempted, so a
crash/failure can only ever leave a valid, content-sha-verified artifact with
no ledger row — never an append-only ledger row pointing at a missing
artifact. On startup, an artifact that exists but has no matching ledger row
is RECONCILED (its ledger row is appended) rather than rejected or retrained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from renquant_model_common.total_return import total_return_close  # noqa: E402
from renquant_model_momentum import (LedgerIntegrityError,  # noqa: E402
                                     append_to_artifact_ledger,
                                     load_and_verify_ledger, params_v0,
                                     params_v1_fast, train_momentum_artifact,
                                     verify_artifact_content_sha)

RQ = Path("/Users/renhao/git/github/RenQuant")
PANEL_PATH = RQ / "data/alpha158_291_fundamental_dataset.parquet"
SECTORS_PATH = RQ / "data/ticker_sectors.json"
OHLCV_ROOT = RQ / "data/ohlcv"
#: Where the scorer-identity monitor reads promotion receipts (orchestrator
#: scorer_identity_monitor.SHADOW_RECEIPT_SUBDIR). The dir name says patchtst
#: for historical reasons — renaming it is a monitor+ops-manifest change and
#: deliberately NOT bundled with receipt emission.
RECEIPTS_DIR = RQ / "logs" / "promote_shadow_patchtst"
#: Env override for the receipt output dir, resolved by ``resolve_receipts_dir``.
#: UNSET in production → ``RECEIPTS_DIR`` (the monitor's real read path) is used
#: verbatim, so the weekly job is byte-for-byte unchanged. Tests set it (or pass
#: ``--receipts-dir``) so a test run's receipts land in a tmp dir and never
#: under the operator's live receipt path.
RECEIPTS_DIR_ENV = "MOMENTUM_RECEIPTS_DIR"
MARKET = "SPY"
DEFAULT_OUT_ROOT = Path.home() / "renquant-data-store" / "momentum-train"
#: Dated-artifact basename — SHARED by every params_version (model#199 item 2).
#: This is a serving-PATH convention, not an identity claim: the pipeline's
#: momentum_residual loader hardcodes exactly this basename
#: (renquant-pipeline momentum_residual_scorer.MOMENTUM_DATED_ARTIFACT_BASENAME)
#: when following a verified ledger tail to `<ledger dir>/<cutoff>/<basename>`,
#: so a lane that wrote a version-derived basename would publish artifacts the
#: current loader can never serve (dated_artifact_missing on every daily run).
#: Identity lives in the artifact's kind / params_version / content_sha256 and
#: in the ledger row's cross-checked copies of them — never in the filename.
#: Follow-up (noted in the #199-item-2 PR): teach the pipeline loader to derive
#: the basename from the ledger row, then version this name.
ARTIFACT_BASENAME = "momentum_residual_v0.json"
LEDGER_BASENAME = "momentum_artifact_ledger.jsonl"

#: The frozen param sets this CLI can train, keyed by their params_version.
#: Each lane gets its OWN --out-root (its own ledger + dated dirs): the ledger
#: dedup key is (cutoff_date, params_version) but the dated-artifact path is
#: version-agnostic (shared basename above), so two lanes sharing one out-root
#: would collide on the same `<cutoff>/<basename>` file — and the serving
#: loader follows a single ledger tail, which a mixed ledger would alternate.
PARAMS_BY_VERSION = {"v0": params_v0, "v1_fast": params_v1_fast}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class LiveReaders:
    """MomentumReaders over the live surfaces, digest-recording every read."""

    def __init__(self, ohlcv_root: Path = OHLCV_ROOT,
                 sectors_path: Path = SECTORS_PATH) -> None:
        self._ohlcv_root = ohlcv_root
        self._sectors_path = sectors_path
        self._digests: dict[str, str] = {}
        self._frames: dict[str, pd.DataFrame | None] = {}
        self._sectors: dict[str, str | None] | None = None

    def record_digest(self, name: str, path: Path) -> None:
        self._digests[name] = _sha(path)

    def _frame(self, ticker: str) -> pd.DataFrame | None:
        if ticker not in self._frames:
            f = self._ohlcv_root / ticker / "1d.parquet"
            if not f.is_file():
                self._frames[ticker] = None
            else:
                self.record_digest(f"ohlcv/{ticker}/1d.parquet", f)
                self._frames[ticker] = pd.read_parquet(f)
        return self._frames[ticker]

    def _tr_returns_of(self, ticker: str) -> pd.Series | None:
        raw = self._frame(ticker)
        if raw is None:
            return None
        tr = total_return_close(
            raw["close"],
            raw["dividend"] if "dividend" in raw.columns
            else pd.Series(0.0, index=raw.index))
        return tr.pct_change()

    # -- MomentumReaders protocol -------------------------------------------
    def tr_returns(self, ticker: str) -> pd.Series | None:
        return self._tr_returns_of(ticker)

    def volume(self, ticker: str) -> pd.Series | None:
        raw = self._frame(ticker)
        return None if raw is None else raw["volume"]

    def market_tr_returns(self) -> pd.Series:
        r = self._tr_returns_of(MARKET)
        if r is None:
            raise FileNotFoundError(
                f"market series {MARKET} absent under {self._ohlcv_root}")
        return r

    def sector_of(self) -> dict[str, str | None]:
        if self._sectors is None:
            self.record_digest("ticker_sectors.json", self._sectors_path)
            raw = json.loads(self._sectors_path.read_text())
            self._sectors = {t: v.get("sector") for t, v in raw.items()}
        return self._sectors

    def read_digests(self) -> dict[str, str]:
        return dict(self._digests)


def resolve_universe(asof: pd.Timestamp) -> tuple[list[str], str]:
    """Tickers present on the latest panel date <= asof (live panel read)."""
    panel = pd.read_parquet(PANEL_PATH, columns=["ticker", "date"])
    panel["date"] = pd.to_datetime(panel["date"])
    eligible = panel[panel["date"] <= asof]
    if eligible.empty:
        raise ValueError(f"panel has no dates <= {asof.date()}")
    day = eligible["date"].max()
    universe = sorted(eligible.loc[eligible["date"] == day, "ticker"].unique())
    return universe, str(pd.Timestamp(day).date())


def _sha256_of_file(path: Path) -> str | None:
    """sha256 of the file's bytes, or None if it does not exist yet (genesis)."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def emit_ledger_append_receipt(receipts_dir: Path, ledger_path: Path,
                               digest_before: str | None,
                               artifact: Mapping[str, Any],
                               row: Mapping[str, Any]) -> Path:
    """Persist the WRITER-side evidence for one ledger append (orch#909 contract).

    The scorer-identity monitor keys a ledger lane by the LEDGER FILE's byte
    digest as stamped in run bundles — NOT the artifact's content sha — so
    identity_before/identity_after carry the ledger file digest straddling the
    append. Full 64-hex (the monitor compares prefix-aware). identity_before is
    OMITTED at genesis: the monitor's ``_side_matches`` treats "the lane was
    absent" and "the receipt names nothing" as the same claim.

    Filename carries the ledger dir stem so two ledgers appended in the same
    second cannot collide; the monitor's date parse falls through to the
    payload's ``promoted_at``, which is part of its contract.
    """
    digest_after = _sha256_of_file(ledger_path)
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "schema": "shadow_promotion_receipt.v1",
        "kind": "ledger_append",
        "promoted_at": now.isoformat(),
        "lane": str(ledger_path),
        "identity_after": {"expected_content_sha256": f"sha256:{digest_after}"},
        "append": {
            "cutoff_date": artifact.get("cutoff_date"),
            "params_version": artifact.get("params", {}).get("params_version"),
            "artifact_content_sha256": artifact.get("content_sha256"),
            "row_index": row.get("row_index"),
            "row_sha": row.get("row_sha"),
        },
    }
    if digest_before is not None:
        payload["identity_before"] = {
            "expected_content_sha256": f"sha256:{digest_before}"}
    receipts_dir.mkdir(parents=True, exist_ok=True)
    name = f"{now.strftime('%Y-%m-%dT%H%M%S')}Z__{ledger_path.parent.name}.json"
    out = receipts_dir / name
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    return out


def resolve_receipts_dir(cli_arg: str | None = None) -> Path:
    """Where ledger-append receipts are written.

    Injection precedence: explicit ``--receipts-dir`` > ``$MOMENTUM_RECEIPTS_DIR``
    > ``RECEIPTS_DIR`` (the production default — the exact path the
    orchestrator's scorer-identity monitor reads). With NOTHING injected the
    result is ``RECEIPTS_DIR`` unchanged, so the real weekly job is
    behaviour-invariant; the seam exists so a test run redirects every receipt
    write into a tmp dir instead of the operator's live receipt path."""
    if cli_arg:
        return Path(cli_arg).expanduser()
    env = os.environ.get(RECEIPTS_DIR_ENV)
    if env:
        return Path(env).expanduser()
    return RECEIPTS_DIR


def _emit_receipt_or_warn(receipts_dir: Path, ledger_path: Path,
                          digest_before: str | None,
                          artifact: Mapping[str, Any],
                          row: Mapping[str, Any]) -> None:
    """A failed receipt write must not fail a run whose append already
    SUCCEEDED — the monitor going CRITICAL on the unexplained boundary is the
    designed detection for a missing receipt, so this is fail-closed at the
    system level, never silent."""
    try:
        emit_ledger_append_receipt(receipts_dir, ledger_path, digest_before,
                                   artifact, row)
    except OSError as exc:
        print(json.dumps({
            "status": "WARN-RECEIPT-NOT-WRITTEN",
            "why": str(exc),
            "consequence": ("the scorer-identity monitor will report this "
                            "append as an unexplained boundary — that alarm "
                            "is the designed backstop, do not silence it"),
        }, indent=2))


def _reconcile_or_refuse(artifact_path: Path, ledger_path: Path,
                         receipts_dir: Path) -> int:
    """An artifact already exists at this cutoff's path — reconcile or refuse.

    Startup half of the two-file protocol (codex review round 3, PR #196): a
    finalized artifact with no ledger row is not a corrupt state, it is the
    ONE recoverable failure the protocol allows (a crash/refusal between
    rename and ledger append). Reconcile by appending the row for the exact
    bytes on disk — never retrain, never silently drop the artifact."""
    try:
        existing = json.loads(artifact_path.read_text(encoding="utf-8"))
        verify_artifact_content_sha(existing)
    except (json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({
            "status": "REFUSED-ARTIFACT-EXISTS",
            "artifact_path": str(artifact_path),
            "why": f"existing artifact failed content-sha verification: {exc}",
        }, indent=2))
        return 4

    params_version = existing.get("params", {}).get("params_version")
    try:
        rows = load_and_verify_ledger(ledger_path)
    except LedgerIntegrityError as exc:
        print(json.dumps({
            "status": "REFUSED-LEDGER",
            "why": str(exc),
            "cutoff_date": existing.get("cutoff_date"),
            "artifact_final_written": True,
            "retry_reconciles": False,
        }, indent=2))
        return 5

    already_ledgered = any(
        r["cutoff_date"] == existing["cutoff_date"]
        and r["params_version"] == params_version for r in rows)
    if already_ledgered:
        print(json.dumps({
            "status": "REFUSED-ARTIFACT-EXISTS",
            "artifact_path": str(artifact_path),
            "why": ("append-only store: an existing cutoff artifact is never "
                    "overwritten; a disagreeing re-run is a dispute to "
                    "investigate"),
        }, indent=2))
        return 4

    digest_before = _sha256_of_file(ledger_path)
    try:
        row = append_to_artifact_ledger(existing, ledger_path)
    except LedgerIntegrityError as exc:
        print(json.dumps({
            "status": "REFUSED-LEDGER",
            "why": str(exc),
            "cutoff_date": existing.get("cutoff_date"),
            "artifact_final_written": True,
            "retry_reconciles": True,
        }, indent=2))
        return 5
    _emit_receipt_or_warn(receipts_dir, ledger_path, digest_before, existing,
                          row)
    print(json.dumps({
        "status": "RECONCILED",
        "why": ("artifact existed with no matching ledger row — a prior run "
                "crashed or was interrupted between finalize and ledger "
                "append; appended the row for the artifact already on disk"),
        "cutoff_date": existing["cutoff_date"],
        "artifact_path": str(artifact_path),
        "content_sha256": existing["content_sha256"],
        "ledger_row_index": row["row_index"],
        "ledger_row_sha": row["row_sha"],
    }, indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--asof", required=True,
                    help="cutoff date YYYY-MM-DD (the artifact's cutoff_date)")
    ap.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT),
                    help="artifact store root (NEVER a live production path); "
                         "one out-root PER params_version — see "
                         "PARAMS_BY_VERSION")
    ap.add_argument("--params-version", default="v0",
                    choices=sorted(PARAMS_BY_VERSION),
                    help="which frozen param set to train (model#199 item 2: "
                         "v0 = the slow 252/21 lane, v1_fast = the fast 63/5 "
                         "shadow lane); default v0 keeps every existing "
                         "invocation byte-identical in behavior")
    ap.add_argument("--dry-run", action="store_true",
                    help="verify surfaces + resolve the universe + print the "
                         "plan; write NOTHING, digest NOTHING")
    ap.add_argument("--receipts-dir", default=None,
                    help="where to write ledger-append receipts; UNSET → "
                         f"${RECEIPTS_DIR_ENV} → the production monitor path "
                         "(RECEIPTS_DIR). The real weekly job leaves this unset "
                         "and is unchanged; the seam exists so tests never "
                         "write under the operator's live receipt dir")
    a = ap.parse_args(argv)
    asof = pd.Timestamp(a.asof)
    out_root = Path(a.out_root).expanduser()
    receipts_dir = resolve_receipts_dir(a.receipts_dir)
    params = PARAMS_BY_VERSION[a.params_version]()

    surfaces = {
        "panel": PANEL_PATH,
        "sectors": SECTORS_PATH,
        "ohlcv_root": OHLCV_ROOT,
        "market_series": OHLCV_ROOT / MARKET / "1d.parquet",
    }
    missing = [k for k, p in surfaces.items() if not p.exists()]
    if missing:
        print(json.dumps({
            "status": "REFUSED-SURFACES-MISSING", "missing": missing,
            "surfaces": {k: str(p) for k, p in surfaces.items()},
        }, indent=2))
        return 3

    universe, universe_date = resolve_universe(asof)
    artifact_path = out_root / str(asof.date()) / ARTIFACT_BASENAME
    ledger_path = out_root / LEDGER_BASENAME

    if a.dry_run:
        print(json.dumps({
            "dry_run": True,
            "asof": str(asof.date()),
            "surfaces": {k: str(p) for k, p in surfaces.items()},
            "universe_n": len(universe),
            "universe_date": universe_date,
            "params": params,
            "would_write": [str(artifact_path), str(ledger_path)],
            "digest_recording": ("real runs only — dry-run reads the panel's "
                                 "ticker/date columns and hashes nothing"),
        }, indent=2))
        return 0

    if artifact_path.exists():
        return _reconcile_or_refuse(artifact_path, ledger_path, receipts_dir)

    readers = LiveReaders()
    readers.record_digest("panel:alpha158_291_fundamental_dataset.parquet",
                          PANEL_PATH)
    artifact = train_momentum_artifact(asof, universe, params,
                                       readers=readers)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    # TWO-FILE PROTOCOL (codex review round 3 on #196, reversing round 1's
    # ordering, which left the OPPOSITE, more-authoritative failure: a crash
    # between ledger-append and rename could leave an append-only ledger row
    # pointing at a missing artifact — durable and unrepairable). Invariant
    # CHOSEN instead: an artifact, once it exists at its final path, is
    # ALWAYS the exact bytes that were trained (content-sha verifiable) —
    # the ledger row for it may still be missing, and that is always
    # recoverable by reconciliation (_reconcile_or_refuse above), never by
    # retraining. Order: (1) full bytes to a staging name in the same
    # directory; (2) os.rename (Path.replace) staging -> final, atomic on
    # POSIX; (3) ledger append. If (3) refuses or crashes, the finalized
    # artifact simply sits unledgered until the next invocation reconciles
    # it — never re-trained, never orphaned.
    staging_path = artifact_path.with_suffix(artifact_path.suffix + ".tmp")
    staging_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    staging_path.replace(artifact_path)
    digest_before = _sha256_of_file(ledger_path)
    try:
        row = append_to_artifact_ledger(artifact, ledger_path)
    except LedgerIntegrityError as exc:
        print(json.dumps({
            "status": "REFUSED-LEDGER",
            "why": str(exc),
            "cutoff_date": artifact["cutoff_date"],
            "artifact_final_written": True,
            "retry_reconciles": True,
        }, indent=2))
        return 5
    _emit_receipt_or_warn(receipts_dir, ledger_path, digest_before, artifact,
                          row)
    print(json.dumps({
        "status": "TRAINED",
        "cutoff_date": artifact["cutoff_date"],
        "effective_train_cutoff_date": artifact["effective_train_cutoff_date"],
        "n_names": artifact["n_names"],
        "n_scored": artifact["n_scored"],
        "names_floor_ok": artifact["names_floor_ok"],
        "content_sha256": artifact["content_sha256"],
        "artifact_path": str(artifact_path),
        "ledger_row_index": row["row_index"],
        "ledger_row_sha": row["row_sha"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
