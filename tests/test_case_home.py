"""Unified case-home composition tests (Engineering-core).

The home endpoint composes existing builders citation-for-citation: mission,
timeline, and changes outputs are embedded verbatim, and every derived
section names its source builder. These tests verify software contracts
only, not clinical correctness. Fictional fixtures only.
"""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.changes import changes_since_review
from open_intelligence.home import BUILDERS, build_case_home
from open_intelligence.investigation import ValidatedInvestigation
from open_intelligence.mission import build_patient_mission
from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.timeline import case_timeline

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"
TRIAL = (SAMPLE / "discovery-trial-001.txt").read_bytes()

FULL_PERMS = {
    "metadata": {"store": "allowed", "display": "allowed"},
    "full_text": {"store": "allowed", "display": "allowed"},
}

AMENDED_IMAGING = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-ALPHA
Document: IMG-ALPHA
Type: imaging
Event-Date: 2026-05-17
Issued-At: 2026-05-20
Amends: IMG-ALPHA@1
Finding: lesion-size|reported|A fictional reference lesion was measured as 31 mm on the current scan.
Finding: comparison|reported|Prior images arrived; comparison remains a fictional demonstration note.
"""


def report(name: str) -> bytes:
    return (SAMPLE / name).read_bytes()


def validated_investigation(citations) -> ValidatedInvestigation:
    return ValidatedInvestigation(
        status="completed",
        claims=[{
            "text": "The fictional sources describe a finding.",
            "kind": "hypothesis",
            "support": "context",
            "citations": citations,
            "uncertainty": "moderate",
            "limits": "Synthetic only.",
        }],
        abstentions=[], dropped=[],
        model="recorded-test", mode="replay")


class CaseHomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "home.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def latest_event(self, case_id: str):
        return self.store.db.execute(
            "SELECT id,occurred_at FROM events WHERE case_id=? ORDER BY id DESC LIMIT 1",
            (case_id,)).fetchone()

    def test_cover_marks_fictional_scope_builders_and_position(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        home = build_case_home(self.store, "CASE-ALPHA")
        latest = self.latest_event("CASE-ALPHA")

        self.assertTrue(home["cover"]["fictional"])
        self.assertIn("FICTIONAL", home["cover"]["marking"])
        self.assertNotIn("Sid", repr(home))
        self.assertEqual(home["cover"]["scope"], "synthetic_workflow_only")
        self.assertEqual(home["cover"]["case_id"], "CASE-ALPHA")
        self.assertEqual(home["cover"]["label"], "Fictional Alpha")
        self.assertEqual(home["cover"]["generated_from"], dict(BUILDERS))
        self.assertEqual(home["cover"]["report_position"],
                         {"event_id": latest["id"], "occurred_at": latest["occurred_at"]})
        # Report position pins to the ledger, not to wall-clock generation.
        self.assertEqual(home["cover"]["timeline_as_of"]["event_id"], latest["id"])
        self.assertTrue(home["limitations"])
        self.assertTrue(all(isinstance(item, str) for item in home["limitations"]))

    def test_embeds_mission_timeline_changes_verbatim(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        state = self.store.state("CASE-ALPHA")

        home = build_case_home(self.store, "CASE-ALPHA")

        self.assertEqual(home["mission"], build_patient_mission(state))
        self.assertEqual(home["timeline"], case_timeline(self.store, "CASE-ALPHA"))
        self.assertEqual(home["changes"], changes_since_review(self.store, "CASE-ALPHA"))
        self.assertEqual(home["cover"]["changes_anchor"], home["changes"]["anchor"])
        self.assertEqual(home["cover"]["timeline_as_of"], home["timeline"]["as_of"])

    def test_citations_survive_composition_citation_for_citation(self):
        original = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))
        home = build_case_home(self.store, "CASE-ALPHA")

        marker = next(item for item in home["mission"]["what_we_know"]
                      if item["finding_key"] == "marker-a")
        self.assertEqual(marker["source_version_id"], original["source_id"])
        self.assertEqual(marker["source_line"], 9)
        self.assertEqual(marker["state"], "not-reported")
        entry = next(item for item in home["timeline"]["entries"]
                     if item["document_id"] == "PATH-ALPHA")
        self.assertEqual(entry["source_id"], original["source_id"])
        self.assertEqual(entry["coverage"], "known")

    def test_attention_and_stage_reference_mission_without_rederiving(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        home = build_case_home(self.store, "CASE-ALPHA")

        self.assertEqual(home["attention"]["source"], "mission")
        self.assertEqual(home["attention"]["builder"], BUILDERS["mission"])
        self.assertEqual(home["attention"]["next_actions"], home["mission"]["next_actions"])
        self.assertEqual(home["attention"]["material_changes"],
                         home["mission"]["material_changes"])
        self.assertTrue(home["attention"]["next_actions"])
        self.assertEqual(home["stage"]["source"], "mission")
        self.assertEqual(home["stage"]["workflow_status"], home["mission"]["workflow_status"])
        self.assertIn("no clinical staging", home["stage"]["note"].lower())

    def test_goals_are_reported_absent_never_inferred(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        home = build_case_home(self.store, "CASE-ALPHA")

        self.assertEqual(home["goals"]["available"], False)
        self.assertIn("no goals", home["goals"]["reason"].lower())
        self.assertIn("none are inferred", home["goals"]["reason"].lower())
        self.assertNotIn("goals_list", home["goals"])
        self.assertNotIn("goal", json.dumps(home["review_state"]).lower())

    def test_follow_ups_list_owned_tasks_with_option_citation(self):
        original = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))
        question = self.store.add_question(
            "CASE-ALPHA", "What does the fictional pathology source report?")
        snapshot = self.store.create_snapshot(
            "CASE-ALPHA", question,
            "The fictional source reports histology and marker states.",
            [original["source_id"]])
        option = self.store.create_option(
            "CASE-ALPHA", snapshot, "Fictional discussion item",
            "A fictional description of a discussion item for testing.", "unknown")
        task = self.store.add_preparation_task(
            "CASE-ALPHA", option, "Gather fictional scheduling notes",
            "Fictional coordinator", 3)
        self.store.set_preparation_task_status("CASE-ALPHA", task, "in_progress")

        home = build_case_home(self.store, "CASE-ALPHA")

        self.assertEqual(home["follow_ups"]["source"], BUILDERS["options"])
        self.assertEqual(home["follow_ups"]["preparation_tasks"], [{
            "task_id": task,
            "option_id": option,
            "option_label": "Fictional discussion item",
            "label": "Gather fictional scheduling notes",
            "owner_label": "Fictional coordinator",
            "status": "in_progress",
            "lead_time_days": 3,
            "created_at": home["follow_ups"]["preparation_tasks"][0]["created_at"],
        }])
        beta = build_case_home(self.store, "CASE-BETA")
        self.assertEqual(beta["follow_ups"]["preparation_tasks"], [])

    def test_review_state_reports_exact_snapshot_option_and_investigation_states(self):
        original = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))
        imaging = self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        question = self.store.add_question(
            "CASE-ALPHA", "What does the fictional pathology source report?")
        stale_snapshot = self.store.create_snapshot(
            "CASE-ALPHA", question,
            "The original fictional source reports marker states.",
            [original["source_id"]])
        self.store.acknowledge_demo_review(
            "CASE-ALPHA", stale_snapshot, "Synthetic reviewer")
        fresh_investigation = self.store.save_investigation(
            "CASE-ALPHA", question, "evidence-summary",
            validated_investigation([{"type": "source", "id": original["source_id"]}]),
            "replay")
        amendment = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-amended.txt"))
        draft_snapshot = self.store.create_snapshot(
            "CASE-ALPHA", question,
            "The amended fictional source reports marker states.",
            [amendment["source_id"]])
        option = self.store.create_option(
            "CASE-ALPHA", draft_snapshot, "Fictional discussion item",
            "A fictional description of a discussion item for testing.", "unknown")
        self.store.add_option_dependency(
            "CASE-ALPHA", option, "source",
            source_version_id=imaging["source_id"])
        self.store.import_report("CASE-ALPHA", AMENDED_IMAGING)

        home = build_case_home(self.store, "CASE-ALPHA")
        review = home["review_state"]

        snapshots = {item["snapshot_id"]: item for item in review["snapshots"]}
        self.assertEqual(snapshots[stale_snapshot]["state"], "stale")
        self.assertEqual(snapshots[draft_snapshot]["state"], "draft")
        self.assertEqual(snapshots[stale_snapshot]["reviewer_label"], "Synthetic reviewer")
        self.assertEqual(snapshots[draft_snapshot]["source_ids"], [amendment["source_id"]])
        options = {item["option_id"]: item for item in review["options"]}
        self.assertEqual(options[option]["review_state"], "needs_review")
        self.assertEqual(options[option]["snapshot_state"], "draft")
        investigations = {item["investigation_id"]: item
                          for item in review["investigations"]}
        self.assertTrue(investigations[fresh_investigation]["stale"])
        self.assertEqual(investigations[fresh_investigation]["review_state"], "pending")
        self.assertEqual(investigations[fresh_investigation]["kind"], "hypothesis")

    def test_review_state_reports_discovery_link_validity(self):
        rights_id = self.store.register_rights_source(
            "EXT-HOME", "Fictional Archive", "v1", "2026-01-15", FULL_PERMS,
            attribution="Fictional archive, demo only")["rights_source_id"]
        discovery_id = self.store.import_discovery(
            TRIAL, rights_source_id=rights_id)["discovery_id"]
        question = self.store.add_question(
            "CASE-ALPHA", "What fictional sources relate to this question?")
        link = self.store.link_discovery(
            "CASE-ALPHA", question, discovery_id, "limited",
            "No applicability judgement made yet for this listing.")

        valid = build_case_home(self.store, "CASE-ALPHA")["review_state"]["discovery_links"]
        self.assertEqual([(item["link_id"], item["state"]) for item in valid],
                         [(link, "valid")])

        self.store.revoke_rights_source(
            rights_id, "Rights withdrawn by the fictional archive.")
        revoked = build_case_home(self.store, "CASE-ALPHA")["review_state"]["discovery_links"]
        self.assertEqual(
            [(item["link_id"], item["state"], item["invalidated_cause"])
             for item in revoked],
            [(link, "invalid", "revocation")])

    def test_case_isolation_holds_across_every_section(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-BETA", report("beta-pathology.txt"))
        self.store.add_question("CASE-ALPHA", "What does the Alpha pathology source report?")

        beta = build_case_home(self.store, "CASE-BETA")
        rendered = repr(beta)

        self.assertNotIn("Marker A was not tested in this specimen.", rendered)
        self.assertNotIn("Alpha pathology", rendered)
        self.assertIn("Marker A testing was not assessed for this sample.", rendered)
        for item in beta["mission"]["what_we_know"]:
            self.assertIn(item["source_version_id"],
                          {source["id"] for source in self.store.state("CASE-BETA")["sources"]})

    def test_unknown_case_rejected(self):
        with self.assertRaisesRegex(InvalidInput, "Unknown case"):
            build_case_home(self.store, "CASE-NOBODY")

    def test_composition_is_read_only(self):
        original = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))
        question = self.store.add_question(
            "CASE-ALPHA", "What does the fictional pathology source report?")
        self.store.create_snapshot(
            "CASE-ALPHA", question,
            "The fictional source reports histology and marker states.",
            [original["source_id"]])

        before = "\n".join(self.store.db.iterdump())
        first = build_case_home(self.store, "CASE-ALPHA")
        middle = "\n".join(self.store.db.iterdump())
        second = build_case_home(self.store, "CASE-ALPHA")
        after = "\n".join(self.store.db.iterdump())

        self.assertEqual(before, middle)
        self.assertEqual(middle, after)
        self.assertEqual(first, second)
        json.dumps(first)  # the HTTP route must be able to serialize this


class CaseHomeHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound_handler = type("BoundHandlerForHome", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path):
        request = Request(f"http://127.0.0.1:{self.port}{path}")
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_home_route_composes_sections(self):
        status, data = self.request("/api/cases/CASE-ALPHA/home")
        self.assertEqual(status, 200)
        for section in ("cover", "mission", "timeline", "changes", "attention",
                        "goals", "follow_ups", "review_state", "stage", "limitations"):
            self.assertIn(section, data)
        self.assertTrue(data["cover"]["fictional"])
        self.assertEqual(data["cover"]["case_id"], "CASE-ALPHA")
        self.assertEqual(data["stage"]["workflow_status"],
                         data["mission"]["workflow_status"])
        self.assertEqual(data["goals"]["available"], False)

    def test_home_route_rejects_unknown_case(self):
        status, data = self.request("/api/cases/CASE-NOBODY/home")
        self.assertEqual(status, 422)
        self.assertIn("Unknown case", data["error"])


if __name__ == "__main__":
    unittest.main()
