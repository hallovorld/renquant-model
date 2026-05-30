"""D6 rename regression guard — train_one → train_single_run.

The function previously named ``train_one`` was renamed to ``train_single_run``
to match the broader naming convention (training.py wraps it as a single-run
adapter; the old name was misleading because there's no ``train_many`` peer).

A back-compat alias ``train_one = train_single_run`` preserves importability
for external callers. This test pins the alias contract so:
  * The rename can't be undone silently.
  * The alias can't be removed silently while external callers still depend on it.
"""
from __future__ import annotations

from renquant_model_patchtst import hf_trainer


def test_train_single_run_is_the_canonical_name() -> None:
    """The lifted name is the function definition."""
    assert callable(hf_trainer.train_single_run)
    assert hf_trainer.train_single_run.__name__ == "train_single_run"


def test_train_one_is_an_alias_of_train_single_run() -> None:
    """Back-compat: external callers using train_one still resolve."""
    assert hf_trainer.train_one is hf_trainer.train_single_run


def test_both_names_are_in_module_namespace() -> None:
    names = vars(hf_trainer)
    assert "train_single_run" in names
    assert "train_one" in names
