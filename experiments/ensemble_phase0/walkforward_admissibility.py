"""Walkforward-manifest admissibility for walkforward-SIM expert scores (GOAL-4).

Why this exists (distinct from the live-DB ``created_at`` admissibility)
-----------------------------------------------------------------------
The Stage-0 ledger's live-DB path admits a prediction date only when a
pipeline run's ``created_at`` (the wall-clock time the score was persisted)
is at-or-before that date's own session-close cutoff — correct for the LIVE
forward DB, where ``created_at`` ~= ``run_date``.

It is WRONG for a walkforward-SIM DB. A walkforward backtest is executed once,
in a single batch, long after the historical dates it scores: in
``data/sim_runs.db`` all 1089 sim runs carry ``created_at=2026-05-11`` while
their ``run_date`` spans 2024-01..2026-03. A ``created_at <= cutoff`` test would
reject EVERY sim date as look-ahead, discarding a fully point-in-time-clean
558-date history.

The sim's point-in-time cleanliness does not come from ``created_at`` — it comes
from the MODEL VINTAGE. The sim scores each bar via
``WalkForwardModelLoader.model_as_of(D)`` (RenQuant
``backtesting/renquant_104/kernel/walk_forward/loader.py``), which selects the
latest retrain fold whose feature cutoff (``effective_train_cutoff_date`` if the
fold declares one, else ``cutoff_date``) plus ``lookahead_days`` BUSINESS days
(``pandas.tseries.offsets.BDay``) is strictly before ``D``, and asserts no
leakage (``entry_as_of`` checks). So a sim score for date ``D`` was produced by
a model trained only on data at-or-before its feature cutoff.

This module reproduces that fold selection from the walkforward MANIFEST so an
extraction harness can admit sim dates by their real vintage (not ``created_at``)
and stamp a truthful ``training_cutoff`` (the fold's ``cutoff_date``) instead of
the live path's ``"MISSING"``.

Codex review (2026-07-21, renquant-model PR #64) on the first cut of this
module found two P0 gaps, both fixed here:

1. **Date-semantics drift.** The first cut selected folds using
   ``cutoff_date + datetime.timedelta(lookahead_days)`` — calendar days, and it
   never looked at ``effective_train_cutoff_date``. The real loader uses
   ``effective_train_cutoff_date or cutoff_date`` plus
   ``pandas.tseries.offsets.BDay(lookahead_days)`` (business days), which
   disagrees with calendar-day arithmetic whenever a weekend falls inside the
   lookahead window, and disagrees whenever a fold pre-embargoes labels via
   ``effective_train_cutoff_date``. Fixed by DELETING the local date-arithmetic
   reimplementation and importing the canonical selector from
   ``renquant_common.walk_forward_fold_selection`` — the SAME module a
   follow-up to the real loader would import from, so there is exactly one
   implementation instead of two that can silently drift apart. This trades
   away the original "pure stdlib, no cross-repo import" design goal (kept for
   portability) for correctness, per the review: a portable module that
   reimplements the wrong contract is worse than a dependent module that
   reimplements the right one.

2. **No provenance verification.** Fold-coverage alone only proves SOME
   eligible fold existed for a date — it never checked that the extracted sim
   record was actually produced by that fold's artifact (a wrong-vintage score
   could still be silently admitted). Fixed by requiring the caller to supply
   :class:`ObservedFoldProvenance` — what the sim-DB record itself claims
   produced it — and rejecting (not silently admitting) any record where that
   claim is missing or does not match the fold this module independently
   selected. See :class:`ObservedFoldProvenance` for exactly which sim-DB
   field this must be sourced from and the honest caveats about it.

Leakage note: admitting by fold-coverage is NOT a blind "trust the sim". The sim
already enforced the as-of contract at scoring time; this check independently
confirms, from the manifest, that a legitimate as-of fold existed for the date —
a date with no such fold (before walkforward coverage) is rejected, and a date
whose observed provenance does not match the selected fold is rejected too.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Union

import pandas as pd

from renquant_common.walk_forward_fold_selection import (
    safe_last_label_date,
    select_latest_eligible_fold,
)


@dataclass(frozen=True)
class WalkforwardFold:
    """One retrain fold from a walkforward manifest's ``retrains`` list."""

    cutoff_date: str  # last training date, ISO YYYY-MM-DD
    lookahead_days: int = 0  # label-horizon embargo, in BUSINESS days
    artifact_uri: str = ""
    # Present when the artifact was trained with labels already pre-embargoed
    # before ``cutoff_date`` — the real loader (RetrainEntry) then uses this,
    # not ``cutoff_date``, as the feature-row cutoff. Mirrors
    # ``kernel.walk_forward.loader.RetrainEntry.effective_train_cutoff_date``.
    effective_train_cutoff_date: "str | None" = None
    # Content digest of the fold's artifact file, when the manifest stamps
    # one (schema v2, ``scripts/stamp_wf_manifest_digests.py``). Used for
    # provenance verification — see :class:`ObservedFoldProvenance`.
    artifact_sha256: "str | None" = None

    @property
    def usable_from(self) -> date:
        """First date this fold may score.

        Delegates to the canonical ``renquant_common`` contract (BUSINESS-day
        lookahead, ``effective_train_cutoff_date``-aware) so this stays a
        faithful mirror of ``WalkForwardModelLoader.entry_as_of`` rather than
        a second, independently-evolving implementation. Returns a plain
        ``datetime.date`` (the manifest / prediction dates this module works
        with are calendar dates, not timestamps).
        """
        return safe_last_label_date(
            self.cutoff_date, self.lookahead_days, self.effective_train_cutoff_date,
        ).date()


@dataclass(frozen=True)
class ObservedFoldProvenance:
    """What a sim-DB record itself claims produced its score, for verification
    against the fold this module independently selects.

    Per Codex review (PR #64): fold-coverage alone proves a legitimate vintage
    EXISTED for a date, not that the extracted record actually used it. A
    caller extracting from RenQuant's ``data/sim_runs.db`` must build this from
    the run's own persisted provenance, not invent one:

      * ``pipeline_runs.run_bundle_json`` is a JSON blob written verbatim from
        ``kernel.artifact_contract.build_run_bundle()``. Its
        ``training_cutoff`` key is populated either from the JSON panel
        artifact's own ``trained_date`` field, or — for non-JSON checkpoints
        (e.g. the PatchTST ``.pt`` family) — from the ACTIVE scorer's runtime
        metadata (``effective_train_cutoff_date`` if present, else
        ``trained_date``). Its ``model_content_sha256`` key is the content
        fingerprint of that same artifact
        (``renquant_common.model_fingerprint.model_content_sha256``).

    HONEST CAVEAT: neither key is guaranteed to be byte-identical to the
    manifest fold's ``cutoff_date`` — ``trained_date`` is the wall-clock day
    training finished, a distinct field from ``cutoff_date`` (the last
    in-sample label date) in the walkforward manifest schema, though the two
    are close in practice for a well-formed fold. Callers comparing
    ``training_cutoff`` against the selected fold should compare it against
    whichever of the fold's own ``cutoff_date`` / ``effective_train_cutoff_date``
    the extraction harness's manifest also carries a matching field for; this
    module cannot paper over an ambiguity it cannot resolve on its own, so it
    fails a record closed (see :func:`walkforward_admissibility`) whenever the
    match cannot be established, rather than guessing.

    A record with no ``ObservedFoldProvenance`` at all (``None``) means
    provenance was never checked — REJECTED unconditionally, never silently
    admitted on fold-coverage alone.
    """

    training_cutoff: "str | None" = None
    artifact_sha256: "str | None" = None


@dataclass(frozen=True)
class WalkforwardAdmission:
    """Result of admitting one prediction date against the manifest folds."""

    admitted: bool
    prediction_date: str
    training_cutoff: str  # the selected fold's cutoff_date, or "" if rejected
    feature_data_cutoff: str  # the prediction date itself (inference as-of)
    fold_artifact_uri: str = ""
    rejection_reasons: tuple[str, ...] = ()


def load_walkforward_folds(manifest_path: Union[str, Path]) -> list[WalkforwardFold]:
    """Parse a walkforward manifest into folds, sorted by ``usable_from``.

    Accepts the ``retrains`` schema (renquant-104 GBDT/PatchTST manifests) and
    the ``folds`` alias. Entries missing ``cutoff_date`` or the lookahead field
    are skipped (a partial manifest must not silently admit uncovered dates).
    ``effective_train_cutoff_date`` and ``artifact_sha256`` are optional and
    parsed when present (schema v2 manifests stamp both; older manifests
    stamp neither and fall back to ``cutoff_date``-only selection and
    unverifiable-digest provenance).
    """
    data = json.loads(Path(manifest_path).read_text())
    entries = data.get("retrains")
    if entries is None:
        entries = data.get("folds", [])
    folds: list[WalkforwardFold] = []
    for entry in entries:
        cutoff = entry.get("cutoff_date")
        lookahead = entry.get("lookahead_days", entry.get("lookahead"))
        if cutoff is None or lookahead is None:
            continue
        effective = entry.get("effective_train_cutoff_date")
        folds.append(
            WalkforwardFold(
                cutoff_date=str(cutoff),
                lookahead_days=int(lookahead),
                artifact_uri=str(entry.get("artifact_uri", "")),
                effective_train_cutoff_date=(
                    str(effective) if effective not in (None, "") else None
                ),
                artifact_sha256=(
                    str(entry["artifact_sha256"])
                    if entry.get("artifact_sha256")
                    else None
                ),
            )
        )
    return sorted(folds, key=lambda f: (f.usable_from, f.cutoff_date))


def select_walkforward_fold(
    folds: list[WalkforwardFold], prediction_date: str
) -> WalkforwardFold | None:
    """The fold ``model_as_of(prediction_date)`` would use, or ``None``.

    Delegates to ``renquant_common.walk_forward_fold_selection
    .select_latest_eligible_fold`` — the canonical mirror of
    ``WalkForwardModelLoader.entry_as_of``'s selection rule (latest
    ``cutoff_date`` among folds whose business-day, effective-cutoff-aware
    safe-label-date is strictly before ``prediction_date``). ``None`` means
    the date is before any fold's coverage — the sim could not have scored it
    with a valid vintage, so it is inadmissible.
    """
    return select_latest_eligible_fold(folds, prediction_date)


def _dates_match(a: "str | None", b: "str | None") -> bool:
    """Compare two date-like strings for equality, tolerant of format/time
    component differences (e.g. ``"2024-01-02"`` vs
    ``"2024-01-02T00:00:00"``). Either side missing is never a match."""
    if not a or not b:
        return False
    try:
        return pd.Timestamp(a) == pd.Timestamp(b)
    except (ValueError, TypeError):
        return False


def walkforward_admissibility(
    folds: list[WalkforwardFold],
    prediction_date: str,
    observed: "ObservedFoldProvenance | None" = None,
) -> WalkforwardAdmission:
    """Admit ``prediction_date`` iff a valid as-of fold covers it AND the
    record's own observed provenance matches that fold.

    On admission, ``training_cutoff`` is the selected fold's ``cutoff_date``
    (truthful vintage provenance) and ``feature_data_cutoff`` is the prediction
    date itself (inference reads features as of the decision date).

    ``observed`` is the sim-DB record's own claim of what produced it (see
    :class:`ObservedFoldProvenance`). Per Codex review (PR #64): fold coverage
    alone is not sufficient to admit a record — a date having SOME eligible
    fold does not prove the record we are looking at was actually scored by
    it. ``observed=None`` (the default omission) rejects unconditionally
    rather than silently trusting coverage; passing a real
    ``ObservedFoldProvenance`` and having it verify against the selected fold
    is required to admit.
    """
    fold = select_walkforward_fold(folds, prediction_date)
    if fold is None:
        return WalkforwardAdmission(
            admitted=False,
            prediction_date=prediction_date,
            training_cutoff="",
            feature_data_cutoff=prediction_date,
            rejection_reasons=("before_walkforward_coverage",),
        )

    reasons: list[str] = []
    expected_cutoff = fold.effective_train_cutoff_date or fold.cutoff_date

    if observed is None:
        reasons.append("missing_observed_provenance")
    else:
        if not observed.training_cutoff:
            reasons.append("missing_observed_training_cutoff")
        elif not _dates_match(observed.training_cutoff, expected_cutoff):
            reasons.append(
                f"observed_training_cutoff={observed.training_cutoff!r} does not "
                f"match selected fold cutoff={expected_cutoff!r} "
                f"(fold_artifact={fold.artifact_uri!r}) — wrong-vintage score"
            )
        if fold.artifact_sha256:
            if not observed.artifact_sha256:
                reasons.append(
                    "missing_observed_artifact_sha256 (selected fold manifest "
                    "stamps artifact_sha256; cannot verify without one to "
                    "compare)"
                )
            elif observed.artifact_sha256 != fold.artifact_sha256:
                reasons.append(
                    f"observed_artifact_sha256={observed.artifact_sha256!r} != "
                    f"selected fold artifact_sha256={fold.artifact_sha256!r}"
                )

    if reasons:
        return WalkforwardAdmission(
            admitted=False,
            prediction_date=prediction_date,
            training_cutoff="",
            feature_data_cutoff=prediction_date,
            fold_artifact_uri=fold.artifact_uri,
            rejection_reasons=tuple(reasons),
        )

    return WalkforwardAdmission(
        admitted=True,
        prediction_date=prediction_date,
        training_cutoff=fold.cutoff_date,
        feature_data_cutoff=prediction_date,
        fold_artifact_uri=fold.artifact_uri,
    )
