"""Contract tests for the issue 116 asset timeline projection.

Covers the pure projection in src/open_intelligence/asset_timeline.py
only, against the real CaseStore on main. It does not claim the
projection is wired to the timeline route or the world model: on main
at 2451983, case_timeline has no assets section, and wiring this
projection is a separate, later step.
"""

import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore
from open_intelligence.asset_timeline import asset_projection

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"


class TestAssetTimeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "test.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.path = self.store.import_report(
            "CASE-ALPHA", (SAMPLE / "alpha-pathology-original.txt").read_bytes()
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def block(self, asset_id="BLOCK-ALPHA"):
        return self.store.add_biological_asset(
            "CASE-ALPHA", asset_id, "ffpe_block", "EPISODE-A", "2026-05-03",
            self.path["source_id"], specimen_state="recorded",
            specimen_id="BIOPSY-ALPHA",
        )

    def test_current_asset_projection(self):
        self.block()
        result = asset_projection(self.store, "CASE-ALPHA")
        self.assertEqual(result["counts"], {"total": 1, "current": 1, "stale": 0, "orphan": 0})
        entry = result["assets"][0]
        self.assertEqual(entry["asset_id"], "BLOCK-ALPHA")
        self.assertEqual(entry["kind"], "ffpe_block")
        self.assertEqual(entry["freshness"], "current")
        self.assertFalse(entry["orphan"])

    def test_genomics_pointer_with_parent(self):
        block = self.block()
        genomics = self.store.add_biological_asset(
            "CASE-ALPHA", "GENOMICS-ALPHA", "genomics_data_pointer", "EPISODE-A",
            "2026-05-04", self.path["source_id"], specimen_state="recorded",
            specimen_id="BIOPSY-ALPHA", parent_asset_id=block,
            pointer_label="Fictional genomics pointer",
        )
        result = asset_projection(self.store, "CASE-ALPHA")
        entry = [a for a in result["assets"] if a["asset_id"] == "GENOMICS-ALPHA"][0]
        self.assertEqual(entry["parent_kind"], "ffpe_block")
        self.assertEqual(entry["freshness"], "current")

    def test_amendment_marks_asset_stale_not_deleted(self):
        self.block()
        self.store.import_report(
            "CASE-ALPHA", (SAMPLE / "alpha-pathology-amended.txt").read_bytes()
        )
        result = asset_projection(self.store, "CASE-ALPHA")
        self.assertEqual(result["counts"]["stale"], 1)
        self.assertEqual(result["assets"][0]["freshness"], "stale")
        self.assertEqual(result["assets"][0]["anchor_state"], "superseded")

    def test_empty_case_projection(self):
        self.store.add_case("CASE-EMPTY", "Fictional Empty")
        result = asset_projection(self.store, "CASE-EMPTY")
        self.assertEqual(result["counts"]["total"], 0)
        self.assertEqual(result["assets"], [])

    def test_unknown_case_denied(self):
        with self.assertRaises(Exception):
            asset_projection(self.store, "CASE-NOPE")


if __name__ == "__main__":
    unittest.main()
