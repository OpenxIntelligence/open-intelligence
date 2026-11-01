import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore
from open_intelligence.mission import build_patient_mission

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"


def report(name: str) -> bytes:
    return (SAMPLE / name).read_bytes()


class PatientMissionProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "mission.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def mission(self, case_id: str) -> dict:
        return build_patient_mission(self.store.state(case_id))

    def test_empty_case_waits_for_sources_without_inventing_state(self):
        mission = self.mission("CASE-ALPHA")

        self.assertEqual(mission["case"], {
            "case_id": "CASE-ALPHA",
            "label": "Fictional Alpha",
            "scope": "synthetic_workflow_only",
        })
        self.assertEqual(mission["workflow_status"], "awaiting_sources")
        self.assertEqual(mission["where_am_i"], {
            "current_source_documents": 0,
            "reported_statements": 0,
            "open_questions": 0,
            "stale_investigations": 0,
            "quarantined_deliveries": 0,
            "latest_source_event_date": None,
        })
        self.assertEqual(mission["what_we_know"], [])
        self.assertEqual(mission["what_remains_unresolved"]["source_findings"], [])
        self.assertEqual(mission["next_actions"][0]["kind"], "gather_source")
        self.assertIn("not a diagnosis or treatment recommendation", mission["guardrails"][0])

    def test_seeded_case_preserves_source_states_and_exact_anchors(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))

        mission = self.mission("CASE-ALPHA")

        self.assertEqual(mission["workflow_status"], "ready_to_define_question")
        self.assertEqual(mission["where_am_i"]["current_source_documents"], 2)
        self.assertEqual(mission["where_am_i"]["reported_statements"], 5)
        self.assertEqual(mission["where_am_i"]["latest_source_event_date"], "2026-05-17")
        by_key = {item["finding_key"]: item for item in mission["what_we_know"]}
        self.assertEqual(by_key["marker-a"]["state"], "not-reported")
        self.assertEqual(by_key["marker-a"]["statement"], "Marker A was not tested in this specimen.")
        self.assertIsInstance(by_key["marker-a"]["source_version_id"], int)
        self.assertEqual(by_key["marker-a"]["source_line"], 9)
        unresolved = {item["finding_key"] for item in mission["what_remains_unresolved"]["source_findings"]}
        self.assertEqual(unresolved, {"marker-a", "margin", "comparison"})
        self.assertEqual(mission["next_actions"][0]["kind"], "define_question")

    def test_projection_never_leaks_another_case(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-BETA", report("beta-pathology.txt"))
        self.store.add_question("CASE-ALPHA", "What does the Alpha pathology source report?")

        beta = self.mission("CASE-BETA")
        rendered = repr(beta)

        self.assertEqual(beta["case"]["case_id"], "CASE-BETA")
        self.assertNotIn("Marker A", rendered)
        self.assertNotIn("Alpha pathology", rendered)
        self.assertTrue(all(item["source_version_id"] in {
            source["id"] for source in self.store.state("CASE-BETA")["sources"]
        } for item in beta["what_we_know"]))

    def test_malformed_event_details_are_ignored_without_misleading_change(self):
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO events (case_id,kind,details,occurred_at) VALUES (?,?,?,?)",
                ("CASE-ALPHA", "source_imported", "{not-json", "2026-10-31T12:00:00+00:00"),
            )

        mission = self.mission("CASE-ALPHA")

        self.assertEqual(mission["material_changes"], [])
        self.assertEqual(mission["workflow_status"], "awaiting_sources")

    def test_amendment_surfaces_only_dependent_review_work(self):
        original = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        imaging = self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        pathology_question = self.store.add_question(
            "CASE-ALPHA", "What was reported about Marker A?"
        )
        imaging_question = self.store.add_question(
            "CASE-ALPHA", "What did the imaging comparison report?"
        )
        stale_snapshot = self.store.create_snapshot(
            "CASE-ALPHA", pathology_question,
            "The original source reports that Marker A was not tested.",
            [original["source_id"]],
        )
        current_snapshot = self.store.create_snapshot(
            "CASE-ALPHA", imaging_question,
            "The imaging source reports that prior images were unavailable.",
            [imaging["source_id"]],
        )
        self.store.acknowledge_demo_review(
            "CASE-ALPHA", stale_snapshot, "Synthetic reviewer"
        )

        amendment = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-amended.txt")
        )
        mission = self.mission("CASE-ALPHA")

        self.assertEqual(amendment["invalidated_snapshots"], [stale_snapshot])
        self.assertEqual(mission["workflow_status"], "review_required")
        self.assertEqual(
            mission["what_remains_unresolved"]["stale_investigation_ids"],
            [stale_snapshot],
        )
        self.assertNotIn(
            current_snapshot,
            mission["what_remains_unresolved"]["stale_investigation_ids"],
        )
        self.assertTrue(any(
            item["kind"] == "source_amended"
            and "PATH-ALPHA@2" in item["summary"]
            and str(stale_snapshot) in item["summary"]
            for item in mission["material_changes"]
        ))
        self.assertTrue(any(
            action["kind"] == "reconcile_stale_investigation"
            for action in mission["next_actions"]
        ))
        marker = next(
            item for item in mission["what_we_know"]
            if item["finding_key"] == "marker-a"
        )
        self.assertEqual(marker["state"], "negative")
        self.assertIn("performed", marker["statement"])


if __name__ == "__main__":
    unittest.main()
