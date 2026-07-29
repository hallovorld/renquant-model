"""The two properties that actually stop a retraction.

Two verdicts on this programme were published and retracted because a prose
procedure was followed loosely. These tests pin the two places where loose
following does the damage:

  1. the rule must REFUSE to run before it is frozen (merged), because an
     estimand still editable by the person about to read the answer is not
     preregistered;
  2. a VOID must never COMPUTE the real arm — not merely decline to print it.
     A void a reader can see through is advisory, and an advisory void is how
     an estimand gets chosen after the fact.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import traded_estimand_run as R  # noqa: E402


def _corpus(*, signal: float, n_dates: int = 660, n_names: int = 60,
            seed: int = 0) -> pd.DataFrame:
    """A panel whose top decile out-performs by `signal` label sd."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-01", periods=n_dates)
    rows = []
    for i, d in enumerate(dates):
        score = rng.normal(size=n_names)
        y = signal * (score > np.quantile(score, 0.9)) + rng.normal(size=n_names)
        rows += [(i // 15, d, f"T{j:03d}", score[j], y[j]) for j in range(n_names)]
    return pd.DataFrame(rows, columns=["fold_idx", "date", "ticker", "raw",
                                       R.LABEL])


# --- property 1: refuse before frozen -------------------------------------

def test_refuses_when_the_prereg_is_not_on_origin_main(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "prereg_is_frozen", lambda repo=".": (False, "not merged"))
    corpus = tmp_path / "c.parquet"
    _corpus(signal=1.0).to_parquet(corpus)
    with pytest.raises(R.PreregNotFrozen, match="REFUSING TO RUN"):
        R.main(["--subject", "x", "--corpus", str(corpus)])


def test_rehearsal_is_allowed_but_stamped(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(R, "prereg_is_frozen", lambda repo=".": (False, "not merged"))
    corpus = tmp_path / "c.parquet"
    _corpus(signal=1.0).to_parquet(corpus)
    R.main(["--subject", "x", "--corpus", str(corpus),
            "--i-am-not-preregistering"])
    out = capsys.readouterr().out
    assert "REHEARSAL — NOT A VERDICT" in out
    # every substantive line carries the stamp, so a pasted excerpt cannot lose it
    body = [ln for ln in out.splitlines() if "subject=" in ln or "real arm" in ln]
    assert body and all("REHEARSAL" in ln for ln in body)


def test_the_flag_forces_rehearsal_even_when_the_prereg_IS_frozen(tmp_path, monkeypatch, capsys):
    """The regression codex caught.

    `rehearsal = not frozen` meant that once the prereg was frozen the explicit
    flag silently stopped stamping, so a rehearsal on a FROZEN prereg produced
    output indistinguishable from a real verdict — precisely the direction the
    stamp exists to prevent. The flag must FORCE rehearsal, not merely permit
    running unfrozen.
    """
    monkeypatch.setattr(R, "prereg_is_frozen", lambda repo=".": (True, "frozen"))
    corpus = tmp_path / "c.parquet"
    _corpus(signal=1.0).to_parquet(corpus)
    R.main(["--subject", "x", "--corpus", str(corpus),
            "--i-am-not-preregistering"])
    out = capsys.readouterr().out
    assert "REHEARSAL — NOT A VERDICT" in out
    body = [ln for ln in out.splitlines() if "subject=" in ln or "real arm" in ln]
    assert body and all("REHEARSAL" in ln for ln in body)


def test_a_frozen_run_without_the_flag_is_NOT_stamped(tmp_path, monkeypatch, capsys):
    """The counterpart: a genuine verdict must not carry a rehearsal stamp."""
    monkeypatch.setattr(R, "prereg_is_frozen", lambda repo=".": (True, "frozen"))
    corpus = tmp_path / "c.parquet"
    _corpus(signal=1.0).to_parquet(corpus)
    R.main(["--subject", "x", "--corpus", str(corpus)])
    assert "REHEARSAL" not in capsys.readouterr().out


def test_frozen_check_reads_the_REMOTE_not_the_worktree(tmp_path):
    """A local edit by the person about to read the answer is the thing this
    guards against, so a working-tree copy must not satisfy it."""
    (tmp_path / "doc" / "research").mkdir(parents=True)
    (tmp_path / "doc" / "research" / Path(R.PREREG_DOC).name).write_text("x")
    frozen, note = R.prereg_is_frozen(str(tmp_path))
    assert frozen is False
    assert "origin/main" in note


def _git_repo_with_frozen_prereg(tmp_path: Path, *, frozen_text: str,
                                  local_text: str) -> Path:
    """A repo where `origin/main` carries the prereg at `frozen_text`, then
    the local worktree copy is overwritten (uncommitted) to `local_text`."""
    doc_dir = tmp_path / "doc" / "research"
    doc_dir.mkdir(parents=True)
    doc_path = doc_dir / Path(R.PREREG_DOC).name
    doc_path.write_text(frozen_text)
    run = lambda *args: subprocess.run(  # noqa: E731
        ["git", "-C", str(tmp_path), *args], check=True,
        capture_output=True, text=True)
    run("init", "-q")
    run("config", "user.email", "t@t.example")
    run("config", "user.name", "t")
    run("add", "-A")
    run("commit", "-q", "-m", "frozen")
    head = run("rev-parse", "HEAD").stdout.strip()
    run("update-ref", "refs/remotes/origin/main", head)
    doc_path.write_text(local_text)  # diverge the worktree, uncommitted
    return tmp_path


def test_frozen_check_rejects_a_local_edit_after_the_prereg_has_merged(tmp_path):
    """Reproduces the reported gap: once the prereg lands on origin/main, an
    unmerged local edit to the same path must not satisfy the freeze gate."""
    repo = _git_repo_with_frozen_prereg(
        tmp_path, frozen_text="registered §7 rule\n",
        local_text="registered §7 rule, quietly loosened\n")
    frozen, note = R.prereg_is_frozen(str(repo))
    assert frozen is False
    assert "does not match" in note


def test_frozen_check_passes_when_local_copy_matches_origin_main_exactly(tmp_path):
    repo = _git_repo_with_frozen_prereg(
        tmp_path, frozen_text="registered §7 rule\n",
        local_text="registered §7 rule\n")
    frozen, note = R.prereg_is_frozen(str(repo))
    assert frozen is True


# --- property 2: a VOID never computes the real arm ------------------------

def test_void_does_not_compute_the_real_arm(monkeypatch):
    monkeypatch.setattr(R, "gate_comparison",
                        lambda controls: (False, [
                            type("V", (), {"name": "shuffle_seed0",
                                           "usable": False, "t_stat": 3.1,
                                           "describe": lambda self: "bad"})()]))

    def explode(*a, **k):  # the real arm's estimator
        raise AssertionError("the real arm was computed on a VOID run")
    monkeypatch.setattr(R, "dependence_aware_mean", explode)

    out = R.run_subject(_corpus(signal=1.0), subject="x",
                        corpus_sha256="d", rehearsal=False)
    assert out.verdict == R.VOID
    assert out.real is None
    assert "NOT COMPUTED" in out.describe()


def test_void_reason_names_the_offending_control(monkeypatch):
    monkeypatch.setattr(R, "gate_comparison",
                        lambda controls: (False, [
                            type("V", (), {"name": "shuffle_seed3",
                                           "usable": False, "t_stat": 3.1,
                                           "describe": lambda self: "bad"})()]))
    monkeypatch.setattr(R, "dependence_aware_mean",
                        lambda *a, **k: pytest.fail("must not run"))
    out = R.run_subject(_corpus(signal=1.0), subject="x",
                        corpus_sha256="d", rehearsal=False)
    assert "shuffle_seed3" in out.reason


# --- the verdict ladder ----------------------------------------------------

def _seed_whose_controls_pass(signal: float) -> pd.DataFrame:
    """Controls VOID a sizeable fraction of runs by construction (see
    test_the_registered_control_rule_voids_valid_experiments). The verdict
    ladder must be exercised on a run that got past them."""
    for seed in range(20):
        c = _corpus(signal=signal, seed=seed).dropna(subset=["raw", R.LABEL])
        fold_of = c.drop_duplicates("date").set_index("date")["fold_idx"]
        ok, _ = R.gate_comparison(R.control_arms(c, fold_of))
        if ok:
            return c
    raise AssertionError("no seed in 0..19 cleared the controls")


def test_a_strong_signal_resolves_positive():
    out = R.run_subject(_seed_whose_controls_pass(1.2), subject="x",
                        corpus_sha256="d", rehearsal=False)
    assert out.verdict == R.RESOLVED_POSITIVE
    assert out.real["mean"] > 0 and out.real["ci_low"] > 0


def test_pure_noise_is_UNRESOLVED_never_negative():
    """§6: a null result is a statement about power, not about the model."""
    out = R.run_subject(_seed_whose_controls_pass(0.0), subject="x",
                        corpus_sha256="d", rehearsal=False)
    assert out.verdict == R.UNRESOLVED
    assert "POWER" in out.reason and "not be reported as a negative" in out.reason


def test_the_registered_control_rule_voids_valid_experiments():
    """Pins a finding that surfaced on this runner's FIRST synthetic run.

    Measured on 150 control arms over 30 signal-free synthetic corpora: the
    registered |t| > 2.0 bar flags 8.0% of genuinely clean arms, so ALL-clean
    over 5 arms voids ~34% of valid experiments. The prereg registered 14%,
    measured on the clf corpus (3% per arm).

    The same frozen rule therefore discards between 14% and 34% of valid work
    depending on panel shape. That range is the finding; this test fails if a
    future change quietly makes the bar permissive instead of amending §5.
    """
    flagged = total = 0
    for seed in range(6):
        c = _corpus(signal=0.0, seed=seed).dropna(subset=["raw", R.LABEL])
        fold_of = c.drop_duplicates("date").set_index("date")["fold_idx"]
        for name, vals in R.control_arms(c, fold_of).items():
            total += 1
            if not R.gate_comparison({name: vals})[0]:
                flagged += 1
    assert total == 30
    assert flagged > 0, (
        "no clean arm was flagged in 30 draws; if the bar has been loosened, "
        "amend prereg §5 explicitly rather than changing the threshold")


def test_registered_constants_match_the_prereg():
    """These are constants, not flags: §7.4 makes changing one a new screen."""
    assert (R.TOP_FRACTION, R.BLOCK_TDAYS, R.N_CONTROL_SEEDS) == (0.10, 60, 5)
    doc = (Path(__file__).resolve().parent.parent / R.PREREG_DOC).read_text()
    assert "0.10 * n_names" in doc and "block_length = 60" in doc


def test_the_corpus_digest_is_recorded():
    out = R.run_subject(_corpus(signal=1.2), subject="x",
                        corpus_sha256="abc123", rehearsal=False)
    assert "abc123" in out.describe()


# --- the estimand's two arms must be exact complements --------------------
#
# The runner selected top-k with nlargest and the bottom arm independently
# with nsmallest(n-k). On tied scores those sets overlap, so the bottom arm
# was not "the remaining names" and the statistic was not the registered
# estimand — for the real arm AND every control arm, since both route
# through spread_per_date().


def _tied(n: int, y, *, date="2026-01-02", tickers=None):
    return pd.DataFrame({
        "date": [date] * n,
        "ticker": tickers if tickers is not None else [f"T{i:03d}" for i in range(n)],
        "raw": [1.0] * n,                      # fully degenerate: all tied
        R.LABEL: list(y),
    })


def test_all_ties_does_not_put_a_row_in_both_arms():
    """The exact case the old nlargest/nsmallest form got wrong."""
    n = 40
    y = list(np.arange(float(n)))
    out = R.spread_per_date(_tied(n, y), R.LABEL)
    k = max(1, int(round(n * R.TOP_FRACTION)))
    expected = np.mean(y[:k]) - np.mean(y[k:])
    assert len(out) == 1
    assert out.iloc[0] == pytest.approx(expected)
    # the old form scored -16.0 here where the registered estimand is -20.0
    df = pd.DataFrame({"raw": [1.0] * n, "y": y})
    old = df.nlargest(k, "raw")["y"].mean() - df.nsmallest(n - k, "raw")["y"].mean()
    assert out.iloc[0] != pytest.approx(old), "regression: old overlapping form"


def test_boundary_ties_still_partition_cleanly():
    n, y = 30, list(np.arange(30.0))
    k = max(1, int(round(n * R.TOP_FRACTION)))
    f = _tied(n, y)
    f["raw"] = [9.0] * (k + 4) + [1.0] * (n - k - 4)   # tie block straddles k
    out = R.spread_per_date(f, R.LABEL)
    assert out.iloc[0] == pytest.approx(np.mean(y[:k]) - np.mean(y[k:]))


def test_tie_policy_is_row_order_independent():
    """A merely-stable sort would give order-dependent answers here."""
    n = 40
    y = list(np.arange(float(n)))
    tick = [f"T{i:03d}" for i in range(n)]
    a = R.spread_per_date(_tied(n, y, tickers=tick), R.LABEL)
    idx = np.random.default_rng(0).permutation(n)
    b = R.spread_per_date(
        _tied(n, [y[i] for i in idx], tickers=[tick[i] for i in idx]), R.LABEL)
    assert a.iloc[0] == pytest.approx(b.iloc[0])


def test_the_twin_implementation_has_not_drifted():
    """One estimand, one implementation. `traded_estimand_calibration.py`
    carries the same function; if either grows a different tie policy the two
    tools stop measuring the same thing (the twin-implementation class this
    repo family has hit before)."""
    src = Path(R.__file__).resolve().parent / "traded_estimand_calibration.py"
    if not src.exists():
        pytest.skip("traded_estimand_calibration.py not present on this head")
    text = src.read_text()
    # Match the buggy CALL, not the word — the fixed version's docstring
    # legitimately names `nsmallest(n-k)` while explaining what it replaced.
    assert "nsmallest(len(g) - k" not in text, \
        "twin regressed to the independently-selected overlapping arms"
    assert 'kind="mergesort"' in text and "iloc[:k]" in text, \
        "twin lost the single-sort position split"
