"""A control arm must be shown to be null before it can certify anything.

The failure this exists for, measured 2026-07-29 on the 43-fold PatchTST
walk-forward corpus. The evaluation ran three arms — `real`, a `shift120`
label-displacement placebo, and a 5-seed label `shuffle` — and read the real
arm against them:

    arm                 mean IC        t        p
    real               +0.0343     +1.38    0.178      <- not significant
    shift120 (placebo) +0.0715     +2.90    0.006      <- SIGNIFICANT
    shuffle  (null)    +0.0013     +0.90    0.375      <- correctly null

(common 524-score-date sample, 37 folds, so this is not the sample-drift
artefact that retracted an earlier verdict — it survives that correction
unchanged.)

The placebo scored HIGHER than the real arm and was the only arm to clear
significance. A control in that state cannot support any verdict, in either
direction: it does not represent the no-signal world, so "the real arm beats
the control" and "the real arm fails to beat the control" are both
uninterpretable. Two published verdicts on this corpus had already been
retracted, one of them for a control that passed 37.5% of the time on
signal-free input — the same defect, measured less sharply.

The rule this module enforces is deliberately narrow and mechanical:

    Before a control arm may gate a verdict, it must be checked for
    significance on its own. A control that is itself significant VOIDS the
    comparison rather than losing it.

That is a different question from "did the treatment beat the control", and
it must be asked first. It is easy to skip because a control is usually
*assumed* null by construction — `shift120` was assumed null because
displacing a label by 120 trading days "obviously" destroys alignment. It did
not: a score carrying slow-moving cross-sectional structure still correlates
with a return window six months out.

Scope: this decides only whether a control is fit to serve as a null. It does
not compute the treatment effect, choose an estimand, or rank models. Pair it
with :mod:`renquant_model_common.lag_alignment` — that module makes arms share
a sample, this one makes the control mean something once they do.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

__all__ = [
    "ControlCalibrationError",
    "ControlVerdict",
    "assess_control",
    "gate_comparison",
]


class ControlCalibrationError(ValueError):
    """Raised when a control cannot be assessed at all."""


def _t_statistic(values: Sequence[float]) -> tuple[float, int]:
    """One-sample t against 0, and the n used.

    Returns ``inf``/``-inf`` for a unanimous non-zero constant sample and
    ``0.0`` for an all-zero one: unanimity is not infinite evidence when the
    thing everyone agrees on is "no effect".
    """
    n = len(values)
    if n < 2:
        raise ControlCalibrationError(
            f"a control needs at least 2 observations to be assessed, got {n}"
        )
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    if var <= 1e-30:
        if abs(mean) <= 1e-30:
            return 0.0, n
        return (math.inf if mean > 0 else -math.inf), n
    return mean / math.sqrt(var / n), n


#: Two-sided |t| beyond which a control is treated as NOT null. Deliberately
#: LOWER than a discovery threshold: the cost of wrongly trusting a broken
#: control (an uninterpretable verdict, published) is much higher than the
#: cost of wrongly rejecting a usable one (collect a better control). The
#: 2026-07-29 placebo sat at |t| = 2.90.
DEFAULT_MAX_ABS_T = 2.0

#: A control with very few observations cannot demonstrate it is null — it can
#: only fail to demonstrate it is not. Below this it is UNPROVEN, not clean.
DEFAULT_MIN_OBS = 8


@dataclass(frozen=True)
class ControlVerdict:
    """Whether a control arm is fit to serve as a null."""

    name: str
    mean: float
    t_stat: float
    n_obs: int
    status: str          # "CLEAN" | "NOT_NULL" | "UNPROVEN"
    reason: str

    @property
    def usable(self) -> bool:
        """True only for CLEAN. UNPROVEN is not usable — it is unknown."""
        return self.status == "CLEAN"

    def describe(self) -> str:
        return (
            f"control '{self.name}': {self.status} — mean={self.mean:+.4f}, "
            f"t={self.t_stat:+.2f}, n={self.n_obs}. {self.reason}"
        )


def assess_control(
    values: Iterable[float],
    *,
    name: str = "control",
    max_abs_t: float = DEFAULT_MAX_ABS_T,
    min_obs: int = DEFAULT_MIN_OBS,
) -> ControlVerdict:
    """Decide whether ``values`` behave like a no-signal arm.

    ``values`` are the control arm's per-unit statistics on the SAME units the
    treatment is measured over (per-fold means, per-block means — whatever the
    prereg registered). Passing per-date values when the treatment is
    aggregated per fold will understate dependence and overstate |t|; align
    the units first (see :mod:`~renquant_model_common.lag_alignment`).
    """
    vals = [float(v) for v in values]
    if not vals:
        raise ControlCalibrationError(f"control '{name}' has no observations")
    t_stat, n = _t_statistic(vals)
    mean = sum(vals) / n

    if abs(t_stat) > max_abs_t:
        return ControlVerdict(
            name, mean, t_stat, n, "NOT_NULL",
            f"|t| = {abs(t_stat):.2f} exceeds {max_abs_t}, so this arm carries "
            f"signal of its own and cannot represent the no-signal world. Any "
            f"comparison against it is VOID, not merely negative.",
        )
    if n < min_obs:
        return ControlVerdict(
            name, mean, t_stat, n, "UNPROVEN",
            f"only {n} observation(s) (< {min_obs}); this arm has not failed "
            f"the null check, it is unable to take it. Absence of a "
            f"significant control is not evidence of a clean one.",
        )
    return ControlVerdict(
        name, mean, t_stat, n, "CLEAN",
        f"|t| = {abs(t_stat):.2f} within {max_abs_t} on {n} observations — "
        f"consistent with a no-signal arm.",
    )


def gate_comparison(
    controls: dict[str, Iterable[float]],
    *,
    max_abs_t: float = DEFAULT_MAX_ABS_T,
    min_obs: int = DEFAULT_MIN_OBS,
) -> tuple[bool, list[ControlVerdict]]:
    """Gate a whole comparison on EVERY control being clean.

    Returns ``(may_proceed, verdicts)``. ``may_proceed`` is True only when
    every control is CLEAN — one broken control voids the comparison even if
    the others are fine, because the reader cannot tell which arm the
    treatment was actually being read against.

    Raises rather than returning True when no controls are supplied: a
    comparison with no control is not a comparison that passed its control
    check, and silently treating it as one is how unvalidated arms reach a
    verdict.
    """
    if not controls:
        raise ControlCalibrationError(
            "no control arms supplied — a comparison with no control cannot "
            "pass a control check; register at least one null arm"
        )
    verdicts = [
        assess_control(vals, name=name, max_abs_t=max_abs_t, min_obs=min_obs)
        for name, vals in controls.items()
    ]
    return all(v.usable for v in verdicts), verdicts
