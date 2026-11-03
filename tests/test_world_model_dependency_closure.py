"""Dependency-closure checks for amendment staleness (issue 116, WS-04).

Fictional data only: the repo's team-authored CASE-ALPHA synthetic reports.
Test-only; exercises CaseStore + synthetic_world_model from PR 147 unchanged.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path

from open_intelligence.store import CaseStore
from open_intelligence.world_model import synthetic_world_model

SYNTHETIC = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


class WorldModelDependencyClosureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "closure.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional closure case")
        self.path_raw = (SYNTHETIC / "alpha-pathology-original.txt").read_bytes()
        self.path_v1 = self.store.import_report("CASE-ALPHA", self.path_raw)["source_id"]
        self.img_v1 = self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-imaging.txt").read_bytes())["source_id"]
        q1 = self.store.add_question("CASE-ALPHA", "Which fictional source lines need review?")
        q2 = self.store.add_question("CASE-ALPHA", "Which other fictional lines need review?")
        q3 = self.store.add_question("CASE-ALPHA", "Which combined fictional lines need review?")
        self.snap_path = self.store.create_snapshot(
            "CASE-ALPHA", q1, "Fictional note citing the pathology source only.", [self.path_v1])
        self.snap_img = self.store.create_snapshot(
            "CASE-ALPHA", q2, "Fictional note citing the imaging source only.", [self.img_v1])
        self.snap_both = self.store.create_snapshot(
            "CASE-ALPHA", q3, "Fictional note citing both sources.", [self.path_v1, self.img_v1])

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def amend(self):
        return self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())

    def snapshot_states(self):
        return {s["id"]: s["state"] for s in self.store.state("CASE-ALPHA")["snapshots"]}

    def test_amending_one_document_stales_only_its_dependents(self):
        result = self.amend()
        self.assertEqual(result["result"], "imported")
        self.assertEqual(result["version"], 2)
        self.assertEqual(sorted(result["invalidated_snapshots"]),
                         sorted([self.snap_path, self.snap_both]))
        states = self.snapshot_states()
        self.assertEqual(states[self.snap_path], "stale")
        self.assertEqual(states[self.snap_both], "stale")
        self.assertNotEqual(states[self.snap_img], "stale")
        model = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        self.assertEqual(model["review_needed"]["stale_snapshot_ids"],
                         sorted([self.snap_path, self.snap_both]))
        img_versions = {o["document_version"] for o in model["observations"]
                        if o["document_id"] == "IMG-ALPHA"}
        self.assertEqual(img_versions, {1})

    def test_original_version_bytes_and_hash_are_preserved(self):
        self.amend()
        row = self.store.db.execute(
            "SELECT raw,sha256,version,state FROM source_versions WHERE id=?",
            (self.path_v1,)).fetchone()
        self.assertEqual(bytes(row["raw"]), self.path_raw)
        self.assertEqual(row["sha256"], hashlib.sha256(self.path_raw).hexdigest())
        self.assertEqual(row["version"], 1)
        self.assertEqual(row["state"], "superseded")
        versions = {(s["document_id"], s["version"], s["state"])
                    for s in self.store.state("CASE-ALPHA")["sources"]}
        self.assertIn(("PATH-ALPHA", 2, "current"), versions)
        model = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        self.assertIn(("PATH-ALPHA", 1),
                      {(h["document_id"], h["version"]) for h in model["history"]})


if __name__ == "__main__":
    unittest.main()
