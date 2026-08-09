"""AUDIT REGRESSION GUARD for the model#208 prereg-v2 feasibility record.

Pins the review-r2 contract on the committed artifacts in
``doc/design/frozen/``:

* the committed CSV/manifest reproduce every frozen availability and
  complete-case count (drift in the committed record FAILS);
* the frozen external-eligible id list matches its pinned hash, count, and
  insufficient-data floors;
* the whole derivation is availability-only — permuting or negating every
  outcome value in the dataset leaves the report bit-identical (the
  contamination guarantee of the amendment);
* the external funnel join rule is exercised synthetically (unmatched vs
  feature-incomplete vs eligible), and injected frozen-constant drift is
  detected by ``verify``.

No test touches the runs DB — the DB-side recompute is covered by running
the module CLI with ``--db`` (evidence in the PR), while CI stays hermetic.
"""
import copy
import importlib.util
import random
from pathlib import Path

_MOD = (Path(__file__).resolve().parents[1] / "doc" / "design" / "frozen"
        / "l3_prereg_v2_feasibility.py")
_spec = importlib.util.spec_from_file_location("l3_prereg_v2_feasibility",
                                               _MOD)
feas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(feas)


class TestFrozenArtifactsRegressionGuard:
    def test_committed_csv_and_manifest_match_pinned_hashes(self):
        assert feas.sha256_file(feas.CSV_PATH) == feas.FROZEN["csv_sha256"]
        assert (feas.sha256_file(feas.MANIFEST_PATH)
                == feas.FROZEN["manifest_sha256"])

    def test_committed_record_verifies_clean_without_db(self):
        report, drifts = feas.verify()
        assert drifts == []
        assert report["external_recomputed"].startswith("SKIPPED")

    def test_committed_csv_reproduces_frozen_counts(self):
        rows = feas.load_rows(feas.CSV_PATH)
        assert feas.availability(rows) == feas.FROZEN["availability"]
        assert (feas.subset_stats(rows, feas.V1_FEATURES)
                == feas.FROZEN["subsets"]["s6_v1"])
        assert (feas.subset_stats(rows, feas.S5_FEATURES)
                == feas.FROZEN["subsets"]["s5_keep_sigma"])
        assert (feas.subset_stats(rows, feas.V2_FEATURES)
                == feas.FROZEN["subsets"]["s4_v2"])

    def test_external_ids_file_frozen_and_above_floors(self):
        ids = feas.read_frozen_external_ids(feas.EXTERNAL_IDS_PATH)
        ext = feas.FROZEN["external"]
        assert len(ids) == ext["n_eligible"] == 34
        assert len(ids) >= ext["min_rows"]
        assert len({tuple(i.split("|")[:3]) for i in ids}) \
            >= ext["min_distinct_trades"]

    def test_injected_frozen_drift_is_detected(self):
        frozen = copy.deepcopy(feas.FROZEN)
        frozen["subsets"]["s4_v2"]["n_rows"] += 1
        _, drifts = feas.verify(frozen=frozen)
        assert any("s4_v2" in d for d in drifts)


class TestAvailabilityOnlyInvariant:
    def test_report_invariant_to_outcome_values(self):
        rows = feas.load_rows(feas.CSV_PATH)
        mutated = [dict(r) for r in rows]
        rng = random.Random(0)
        for r in mutated:
            # flip signs and scramble magnitudes; keep non-emptiness intact
            r["fwd_20d"] = str(-float(r["fwd_20d"]) * rng.uniform(1, 9))
            if r.get("fwd_60d") not in ("", "None"):
                r["fwd_60d"] = str(float(r["fwd_60d"]) + rng.uniform(-1, 1))
            r["win"] = str(rng.randint(0, 1))
        for feats in (feas.V1_FEATURES, feas.S5_FEATURES, feas.V2_FEATURES):
            assert (feas.subset_stats(mutated, feats)
                    == feas.subset_stats(rows, feats))
        assert feas.availability(mutated) == feas.availability(rows)


class TestExternalFunnelJoinRule:
    DATASET = [
        {"run_date": "2026-05-08", "ticker": "AAA", "run_type": "live",
         "panel_score": "0.5", "mu": "0.1", "rank_score": "0.9",
         "n_candidates_that_date": "3", "fwd_20d": "0.02"},
        {"run_date": "2026-05-08", "ticker": "BBB", "run_type": "live",
         "panel_score": "0.4", "mu": "", "rank_score": "0.8",
         "n_candidates_that_date": "3", "fwd_20d": "0.01"},
    ]
    TE = [
        ("r1", "AAA", "buy", 1, "2026-05-08"),    # eligible
        ("r1", "AAA", "buy", 5, "2026-05-08"),    # eligible
        ("r1", "BBB", "buy", 1, "2026-05-08"),    # mu missing -> incomplete
        ("r2", "CCC", "sell", 1, "2026-05-08"),   # not a candidate row
        ("r3", "AAA", "sell", 1, "2026-05-09"),   # no dataset row that date
    ]

    def test_funnel_counts_and_determinism(self):
        funnel = feas.external_funnel(self.TE, self.DATASET)
        assert funnel["n_te_rows"] == 5
        assert funnel["n_eligible"] == 2
        assert funnel["n_feature_incomplete"] == 1
        assert funnel["n_unmatched"] == 2
        assert funnel["n_distinct_trades"] == 1
        assert funnel["by_action"] == {"buy": 2}
        assert funnel["ids"] == ["r1|AAA|buy|1", "r1|AAA|buy|5"]
        again = feas.external_funnel(self.TE, self.DATASET)
        assert again["ids_sha256"] == funnel["ids_sha256"]
