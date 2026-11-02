"""Source-preserving synthetic Patient World Model projection regressions.

Only independently authored fictional patient reports. No clinical inference.
"""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler
from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.world_model import synthetic_world_model

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def fictional_report(case, document, specimen, marker, state, date="2026-04-04"):
    rows = [
        "OI-SYNTHETIC-REPORT/1",
        "Patient: " + case,
        "Document: " + document,
        "Type: pathology",
        "Event-Date: " + date,
        "Issued-At: " + date,
    ]
    if specimen is not None:
        rows.append("Specimen: " + specimen)
    rows.append(f"Finding: {marker}|{state}|Fictional authored observation.")
    return ("\n".join(rows) + "\n").encode()


class SyntheticWorldModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "world.sqlite"
        self.store = CaseStore(self.path)
        self.addCleanup(self.store.close)
        for case in ("CASE-ALPHA", "CASE-BETA"):
            self.store.add_case(case, "Independently invented " + case)

    def test_current_observations_are_exactly_source_anchored_and_time_qualified(self):
        record = self.store.import_report(
            "CASE-ALPHA", (FIXTURES / "alpha-pathology-original.txt").read_bytes()
        )
        model = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        self.assertEqual(model["contract"], "oi.synthetic-world-model/1")
        self.assertEqual(model["case_id"], "CASE-ALPHA")
        self.assertEqual(model["authority"], "source_report_only_unreviewed")
        self.assertEqual(model["clinical_interpretation"], "not_generated")
        self.assertTrue(model["synthetic"])
        self.assertEqual(model["summary"]["current_sources"], 1)
        self.assertEqual(model["summary"]["current_observations"], 3)
        for observation in model["observations"]:
            self.assertEqual(observation["source_version_id"], record["source_id"])
            self.assertTrue(observation["document_id"])
            self.assertEqual(len(observation["source_sha256"]), 64)
            self.assertGreater(observation["source_line"], 0)
            self.assertEqual(observation["event_date"], "2026-05-03")
            self.assertEqual(observation["issued_at"], "2026-05-05")
            self.assertIn("+00:00", observation["received_at"])
            self.assertEqual(observation["review_state"], "not_established")
            self.assertIsNone(observation["clinical_meaning"])
        self.assertEqual(model["conflicts"], [])
        self.assertEqual({x["reported_state"] for x in model["observations"]},
                         {"reported", "not-reported", "indeterminate"})

    def test_negative_is_not_missing_and_amendment_keeps_history(self):
        previous = self.store.import_report(
            "CASE-ALPHA", (FIXTURES / "alpha-pathology-original.txt").read_bytes()
        )
        before = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        self.assertIn("not-reported", {x["reported_state"] for x in before["unresolved"]})
        amended = self.store.import_report(
            "CASE-ALPHA", (FIXTURES / "alpha-pathology-amended.txt").read_bytes()
        )
        after = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        self.assertEqual(after["summary"]["current_sources"], 1)
        self.assertEqual(after["summary"]["superseded_sources"], 1)
        self.assertEqual({x["source_version_id"] for x in after["observations"]},
                         {amended["source_id"]})
        self.assertIn("negative", {x["reported_state"] for x in after["observations"]})
        self.assertNotIn("not-reported", {x["reported_state"] for x in after["observations"]})
        self.assertEqual(after["history"][0]["source_version_id"], previous["source_id"])
        self.assertEqual(after["current_sources"][0]["supersedes_source_id"],
                         previous["source_id"])
        self.assertEqual({x["source_version_id"] for x in before["observations"]},
                         {previous["source_id"]})

    def test_opposing_same_specimen_same_date_is_unresolved_not_decided(self):
        self.store.import_report("CASE-ALPHA", fictional_report(
            "CASE-ALPHA", "SRC-ONE", "SPECIMEN-ONE", "marker-z", "reported"))
        self.store.import_report("CASE-ALPHA", fictional_report(
            "CASE-ALPHA", "SRC-TWO", "SPECIMEN-ONE", "marker-z", "negative"))
        model = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        self.assertEqual(len(model["conflicts"]), 1)
        conflict = model["conflicts"][0]
        self.assertEqual(conflict["status"], "unresolved_source_disagreement")
        self.assertEqual(conflict["specimen_id"], "SPECIMEN-ONE")
        self.assertEqual(conflict["reported_states"], ["negative", "reported"])
        self.assertEqual(len(conflict["observation_refs"]), 2)
        self.assertEqual(len(model["observations"]), 2)

    def test_different_or_unknown_specimen_does_not_create_false_conflict(self):
        self.store.import_report("CASE-ALPHA", fictional_report(
            "CASE-ALPHA", "SRC-ONE", "SPECIMEN-ONE", "marker-z", "reported"))
        self.store.import_report("CASE-ALPHA", fictional_report(
            "CASE-ALPHA", "SRC-TWO", "SPECIMEN-TWO", "marker-z", "negative"))
        self.store.import_report("CASE-ALPHA", fictional_report(
            "CASE-ALPHA", "SRC-THREE", None, "marker-z", "negative"))
        self.store.import_report("CASE-ALPHA", fictional_report(
            "CASE-ALPHA", "SRC-FOUR", None, "marker-z", "reported"))
        result = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(len(result["observations"]), 4)

    def test_other_patient_and_global_evidence_are_not_projected(self):
        self.store.import_report("CASE-BETA",
            (FIXTURES / "beta-pathology.txt").read_bytes())
        self.store.import_report("CASE-ALPHA",
            (FIXTURES / "alpha-pathology-original.txt").read_bytes())
        alpha = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        beta = synthetic_world_model(self.store.state("CASE-BETA"), "CASE-BETA")
        self.assertEqual(alpha["case_id"], "CASE-ALPHA")
        self.assertEqual(beta["case_id"], "CASE-BETA")
        self.assertTrue(all(item["document_id"] != "PATH-BETA"
                            for item in alpha["observations"]))
        self.assertTrue(all(item["document_id"] != "PATH-ALPHA"
                            for item in beta["observations"]))
        self.assertNotIn("evidence", alpha)
        self.assertNotIn("broker_links", alpha)
        self.assertNotIn("clinical_note_text", alpha)

    def test_read_only_and_stale_review_states(self):
        source = self.store.import_report("CASE-ALPHA",
            (FIXTURES / "alpha-pathology-original.txt").read_bytes())
        question_id = self.store.add_question("CASE-ALPHA", "What is uncertain?")
        snapshot = self.store.create_snapshot("CASE-ALPHA", question_id,
            "Fictional investigator summary only", [source["source_id"]])
        before_state = self.store.state("CASE-ALPHA")
        first = synthetic_world_model(before_state, "CASE-ALPHA")
        second = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        self.assertEqual(first, second)
        self.assertEqual(self.store.state("CASE-ALPHA")["events"],
                         before_state["events"])
        self.assertIn(snapshot, first["review_needed"]["draft_snapshot_ids"])
        self.store.import_report("CASE-ALPHA",
            (FIXTURES / "alpha-pathology-amended.txt").read_bytes())
        after = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        self.assertIn(snapshot, after["review_needed"]["stale_snapshot_ids"])
        self.assertNotIn(snapshot, after["review_needed"]["draft_snapshot_ids"])
        self.assertIn(question_id, after["review_needed"]["open_question_ids"])

    def test_malformed_or_cross_case_snapshot_fails_closed(self):
        self.store.import_report("CASE-ALPHA",
            (FIXTURES / "alpha-pathology-original.txt").read_bytes())
        state = self.store.state("CASE-ALPHA")
        copied = dict(state)
        copied["assertions"] = [dict(state["assertions"][0], source_version_id=99999)]
        with self.assertRaises(InvalidInput):
            synthetic_world_model(copied, "CASE-ALPHA")
        with self.assertRaises(InvalidInput):
            synthetic_world_model(dict(state, case={"case_id": "wrong-case"}), "CASE-ALPHA")

    def test_http_endpoint_is_explicitly_synthetic_and_case_scoped(self):
        self.store.import_report("CASE-ALPHA",
            (FIXTURES / "alpha-pathology-original.txt").read_bytes())
        self.store.import_report("CASE-BETA",
            (FIXTURES / "beta-pathology.txt").read_bytes())
        self.store.close()
        handler = type("SyntheticWorldHandler", (Handler,),
                       {"db_path": str(self.path), "allow_crossref_live": False,
                        "log_message": lambda self, *args: None})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for case in ("CASE-ALPHA", "CASE-BETA"):
                req = Request(f"http://127.0.0.1:{server.server_port}/api/cases/{case}/world-model")
                with urlopen(req, timeout=8) as response:
                    self.assertEqual(response.status, 200)
                    data = json.loads(response.read())
                    self.assertEqual(data["case_id"], case)
                    self.assertTrue(data["synthetic"])
                    self.assertEqual(data["clinical_interpretation"], "not_generated")
            try:
                urlopen(Request(f"http://127.0.0.1:{server.server_port}/api/cases/CASE-NOPE/world-model"), timeout=8)
            except HTTPError as error:
                self.assertEqual(error.code, 422)
            else:
                self.fail("unknown case must not be projected")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
