"""The errata is a separate document, and the prereg it corrects is UNTOUCHED.

Codex on model#141 rejected the first version of this: it inserted HTML pointer
comments into the registered lines while the PR claimed the document was
byte-identical. That is an edit, and the substring tests I had written could not have
detected it -- a substring surviving says nothing about the bytes around it.

So immutability is now established the only way it can be: by pinning the blob. These
tests fail if the prereg changes by one byte, whatever the change is and wherever it
lands.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PREREG = ROOT / "doc/research/2026-07-30-momentum-total-return-prereg.md"
ERRATA = ROOT / "doc/research/2026-07-31-tr-prereg-data-claim-errata.md"

# The revision this errata is written against, and its content digest.
PREREG_BLOB = "c0e03c95f8087c9d3572148d79891b7adf7043b0"
PREREG_SHA256 = "bad1ade550cf102597d57bcc7558a3518cdae9ffac631e5c196a8ae7157f8f3d"
PREREG_BYTES = 63_323
FREEZE_COMMIT = "048975f4e030d3a90bd8ee1c97466f00f4810b52"


def test_the_prereg_is_byte_for_byte_the_revision_this_errata_pins():
    """The claim "the registered document is unchanged", made checkable.

    A substring assertion cannot establish this; only the digest can. If someone
    appends a section, inserts a pointer comment, or fixes a typo, this fails -- which
    is the point, because on a frozen document all three are the same act.
    """
    raw = PREREG.read_bytes()
    assert len(raw) == PREREG_BYTES
    assert hashlib.sha256(raw).hexdigest() == PREREG_SHA256


def test_the_pinned_digest_is_gits_own_object_id_not_a_number_i_invented():
    """Recompute git's blob id from the bytes, independently of git.

    The pin above is only trustworthy if it names the same object the repository
    names. ``blob <len>\\0<content>`` hashed with sha1 IS git's object id, so this
    ties the errata's pin to the revision graph without shelling out.
    """
    raw = PREREG.read_bytes()
    oid = hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()
    assert oid == PREREG_BLOB


def test_this_branch_does_not_modify_the_prereg_at_all():
    """The strongest form: git itself reports no diff against the base.

    Skipped rather than passed when git or the base ref is unavailable -- an
    environment gap is not evidence of a clean tree, and a check that silently returns
    OK without looking is the fail-open default this programme keeps re-learning.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "diff", "--name-only", "origin/main", "--",
             str(PREREG.relative_to(ROOT))],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
        pytest.skip(f"git unavailable: {type(exc).__name__}: {exc}")
    if out.returncode != 0:  # pragma: no cover
        pytest.skip(f"git diff rc={out.returncode}: {out.stderr.strip()[:200]}")
    assert out.stdout.strip() == "", f"prereg modified: {out.stdout!r}"


def test_the_registered_claim_is_still_there_unedited():
    """Necessary but NOT sufficient -- kept because it names what is being corrected.

    Left in deliberately alongside the digest test, and labelled: this is the check
    that gave false confidence the first time round. It documents the target; the
    digest above is what enforces immutability.
    """
    doc = PREREG.read_text(encoding="utf-8")
    assert "D1 is a statement about the DATA, not about momentum." in doc
    assert "The dividend confound is REFUTED as the explanation of the aborted run's" in doc


def test_the_prereg_carries_no_pointer_back_to_this_errata():
    """Proof the first approach was fully reverted, not merely re-worded.

    A pointer comment inside the frozen file is exactly what codex rejected. Its
    absence is the observable difference between "separate document" and "annotated
    original".
    """
    doc = PREREG.read_text(encoding="utf-8")
    assert "ERRATA-2026-07-31" not in doc
    assert "ERRATA-2026-08-01" not in doc


def _errata_prose() -> str:
    """Whitespace-normalised errata text.

    Every assertion below is against PROSE, and prose wraps. A phrase moving across a
    line break must not decide whether a claim is enforced -- the first run of these
    tests failed on exactly that (`never rested on\\nthe data claim`), as did a test on
    model#140 the same evening. Normalise once, here, rather than per assertion.
    """
    return " ".join(ERRATA.read_text(encoding="utf-8").split())


def test_the_errata_pins_the_revision_it_corrects():
    e = _errata_prose()
    assert PREREG_BLOB in e
    assert PREREG_SHA256 in e
    assert FREEZE_COMMIT in e


def test_the_errata_cites_stable_headings_and_those_headings_exist():
    """Line numbers move when a document is appended to; headings do not.

    Each heading the errata cites must actually be present in the pinned prereg --
    otherwise the errata points at nothing, which is how a correction quietly stops
    applying to the thing it corrects.
    """
    doc = PREREG.read_text(encoding="utf-8")
    for heading in [
        "## 5c. Registered DATA diagnostic D1 — no verdict attached",
        "## Bottom line",
        "## 3. D1 — the dividend confound is REFUTED (a statement about the DATA)",
    ]:
        assert heading in doc, heading


def test_the_verdict_is_explicitly_UNAFFECTED():
    """The narrowing must not be allowed to grow into the §6 verdict."""
    e = _errata_prose()
    assert "UNRESOLVED / TILT-NOT-EXCLUDED" in e
    assert "never rested on the data claim" in e


def test_the_errata_records_its_own_two_corrections():
    """Both the wrong date and the wrong form are on the record, not rewritten away."""
    e = _errata_prose()
    assert "2026-08-01" in e          # the date it was first given
    assert "06:39 PDT" in e           # what the clock actually read
    assert "byte-identical" in e      # the false claim it made
