"""Linear baselines for cross-sectional ranking — DLinear/NLinear adaptations.

Per the merged research plan (`docs/patchtst_capability_research_proposal.md`
§"P1 Low-Cost Decision Baselines"): "DLinear/NLinear is a P1 must-try
baseline. If a simple linear model beats PatchTST under the same splits,
placebos, and per-regime gates, the PatchTST investment should pause."

This package ports the LTSF-Linear (Zeng et al. AAAI 2023) models for
RenQuant's cross-sectional ranking task. See
`docs/dlinear_source_note.md` for the source-note + deviations per the
Implementation Reference Policy.
"""

from .dlinear import (
    DLinearRanker,
    MovingAverageDecomposition,
    NLinearRanker,
)
from .trainer import build_parser, train_single_run

__all__ = [
    "DLinearRanker",
    "MovingAverageDecomposition",
    "NLinearRanker",
    "build_parser",
    "train_single_run",
]
