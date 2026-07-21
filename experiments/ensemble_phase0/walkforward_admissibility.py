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
``WalkForwardModelLoader.model_as_of(D)`` (renquant-backtesting
``kernel/walk_forward/loader.py``), which selects the latest retrain fold whose
``cutoff_date + lookahead_days`` is strictly before ``D`` and asserts no leakage
(``entry_as_of`` checks). So a sim score for date ``D`` was produced by a model
trained only on data at-or-before ``cutoff_date <= D - lookahead_days``.

This module reproduces that fold selection from the walkforward MANIFEST so an
extraction harness can admit sim dates by their real vintage (not ``created_at``)
and stamp a truthful ``training_cutoff`` (the fold's ``cutoff_date``) instead of
the live path's ``"MISSING"``. It is pure logic over (manifest folds, date): it
does not read any DB and imports nothing outside the stdlib, so it stays
model-owned and portable (no reverse cross-repo edge).

Leakage note: admitting by fold-coverage is NOT a blind "trust the sim". The sim
already enforced the as-of contract at scoring time; this check independently
confirms, from the manifest, that a legitimate as-of fold existed for the date —
a date with no such fold (before walkforward coverage) is rejected.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Union


@dataclass(frozen=True)
class WalkforwardFold:
    """One retrain fold from a walkforward manifest's ``retrains`` list."""

    cutoff_date: str  # last training date, ISO YYYY-MM-DD
    lookahead_days: int  # label-horizon embargo before the fold is usable
    artifact_uri: str = ""

    @property
    def usable_from(self) -> date:
        """First date this fold may score: ``cutoff_date + lookahead_days``.

        The fold trains on data through ``cutoff_date``; its labels need
        ``lookahead_days`` to realise, so ``model_as_of`` only reaches for it
        once the prediction date is strictly past this point.
        """
        return date.fromisoformat(self.cutoff_date) + timedelta(days=self.lookahead_days)


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
        folds.append(
            WalkforwardFold(
                cutoff_date=str(cutoff),
                lookahead_days=int(lookahead),
                artifact_uri=str(entry.get("artifact_uri", "")),
            )
        )
    return sorted(folds, key=lambda f: (f.usable_from, f.cutoff_date))


def select_walkforward_fold(
    folds: list[WalkforwardFold], prediction_date: str
) -> WalkforwardFold | None:
    """The fold ``model_as_of(prediction_date)`` would use, or ``None``.

    Mirrors ``WalkForwardModelLoader.model_as_of``: among folds usable strictly
    before ``prediction_date`` (``cutoff_date + lookahead_days < prediction_date``),
    pick the one with the latest ``cutoff_date``. ``None`` means the date is
    before any fold's coverage — the sim could not have scored it with a valid
    vintage, so it is inadmissible.
    """
    d = date.fromisoformat(prediction_date)
    usable = [f for f in folds if f.usable_from < d]
    if not usable:
        return None
    return max(usable, key=lambda f: date.fromisoformat(f.cutoff_date))


def walkforward_admissibility(
    folds: list[WalkforwardFold], prediction_date: str
) -> WalkforwardAdmission:
    """Admit ``prediction_date`` iff a valid as-of fold covers it.

    On admission, ``training_cutoff`` is the selected fold's ``cutoff_date``
    (truthful vintage provenance) and ``feature_data_cutoff`` is the prediction
    date itself (inference reads features as of the decision date).
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
    return WalkforwardAdmission(
        admitted=True,
        prediction_date=prediction_date,
        training_cutoff=fold.cutoff_date,
        feature_data_cutoff=prediction_date,
        fold_artifact_uri=fold.artifact_uri,
    )
