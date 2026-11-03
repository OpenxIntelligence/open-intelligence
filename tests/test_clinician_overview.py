"""Clinician overview slice: store projection, HTTP route, UI contract.

Each assertion is falsifiable: it fails when the clinician-overview
feature is absent (missing module, route, panel, or renderer) and when
the projection invents, omits, leaks, or directs care.
"""

import json
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore
from open_intelligence.__main__ import FICTIONAL_ACTOR_HEADER, Handler, seed
from open_intelligence.clinician_overview import build_clinician_overview

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"

DISCLAIMER_LITERAL = "Summary of the recorded case file only \u2014 not a clinical recommendation, not a treatment decision."


def report(name: str) -> bytes:
    return (SAMPLE / name).read_bytes()


def stripped_text(overview: dict) -> str:
    """Overview JSON without the required negated disclaimer sentence."""
    return json.dumps(overview, ensure_ascii=False).replace(DISCLAIMER_LITERAL, "")


def assert_no_directive(testcase: unittest.TestCase, overview: dict) -> None:
    """Fail when projection output carries directive clinical wording."""
    lowered = stripped_text(overview).lower()
    testcase.assertNotIn("authoriz", lowered, "overview must not emit authorize wording")
    testcase.assertNotIn("prescrib", lowered, "overview must not emit prescribe wording")
    testcase.assertNotIn("recommend", lowered, "overview must not emit recommend wording outside the disclaimer")
    testcase.assertIsNone(
        re.search(r"\border\w*\b", lowered),
        "overview must not emit order wording",
    )
    testcase.assertIsNone(
        re.search(r"direct\w*\W+care", lowered),
        "overview must not emit direct-care wording",
    )


BENIGN_QUESTION = "What does the current fictional source list for Marker A?"
BENIGN_SUMMARY = "Reported observations:\nMarker A was not tested in the current fictional source."
BENIGN_OPTION_LABEL = "Fictional discussion item"
BENIGN_OPTION_DESC = "A fictional item under discussion with its uncertainty noted."
BENIGN_TASK_LABEL = "Fictional preparation step"
BENIGN_TASK_OWNER = "Synthetic holder"


class ClinicianOverviewProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "clinician-overview.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def overview(self, case_id: str) -> dict:
        return build_clinician_overview(self.store.state(case_id))

    def test_empty_case_shows_six_sections_without_inventing_content(self):
        overview = self.overview("CASE-ALPHA")

        for section in ("current_sources", "open_questions", "pending_reviews",
                        "follow_up_tasks", "goals", "journey_stage"):
            self.assertIn(section, overview)
        self.assertEqual(overview["case"]["case_id"], "CASE-ALPHA")
        self.assertEqual(overview["case"]["scope"], "synthetic_only")
        self.assertEqual(overview["disclaimer"], DISCLAIMER_LITERAL)
        self.assertEqual(overview["current_sources"], [])
        self.assertEqual(overview["open_questions"], [])
        self.assertEqual(overview["pending_reviews"], [])
        self.assertEqual(overview["follow_up_tasks"], [])
        self.assertEqual(overview["goals"]["count"], 0)
        self.assertEqual(overview["goals"]["items"], [])
        self.assertIn("No goals are recorded", overview["goals"]["note"])
        self.assertIn("CASE-ALPHA", overview["goals"]["citation"])
        self.assertEqual(overview["journey_stage"]["stage"], "awaiting_sources")
        self.assertEqual(overview["journey_stage"]["label"], "Awaiting sources")
        self.assertIn("CASE-ALPHA", overview["journey_stage"]["citation"])

    def test_seeded_case_shows_all_six_sections_with_citations(self):
        first = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        second = self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        question_id = self.store.add_question("CASE-ALPHA", BENIGN_QUESTION)
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id, BENIGN_SUMMARY,
            [first["source_id"], second["source_id"]],
        )
        option_id = self.store.create_option(
            "CASE-ALPHA", snapshot_id, BENIGN_OPTION_LABEL, BENIGN_OPTION_DESC, "unknown",
        )
        task_id = self.store.add_preparation_task(
            "CASE-ALPHA", option_id, BENIGN_TASK_LABEL, BENIGN_TASK_OWNER,
        )

        overview = self.overview("CASE-ALPHA")

        self.assertEqual(len(overview["current_sources"]), 2)
        by_doc = {item["document_id"]: item for item in overview["current_sources"]}
        self.assertEqual(set(by_doc), {"PATH-ALPHA", "IMG-ALPHA"})
        self.assertEqual(by_doc["PATH-ALPHA"]["version"], 1)
        self.assertEqual(by_doc["IMG-ALPHA"]["version"], 1)
        for item in overview["current_sources"]:
            self.assertIsInstance(item["source_version_id"], int)
            self.assertIn(item["document_id"], item["citation"])
            self.assertIn(str(item["version"]), item["citation"])
            self.assertIn(str(item["source_version_id"]), item["citation"])
        self.assertEqual(len(overview["open_questions"]), 1)
        self.assertEqual(overview["open_questions"][0]["question_id"], question_id)
        self.assertIn(str(question_id), overview["open_questions"][0]["citation"])
        kinds = {item["kind"] for item in overview["pending_reviews"]}
        self.assertIn("snapshot_draft", kinds)
        draft = next(item for item in overview["pending_reviews"] if item["kind"] == "snapshot_draft")
        self.assertEqual(draft["snapshot_id"], snapshot_id)
        self.assertIn(str(snapshot_id), draft["citation"])
        self.assertEqual(len(overview["follow_up_tasks"]), 1)
        task = overview["follow_up_tasks"][0]
        self.assertEqual(task["task_id"], task_id)
        self.assertEqual(task["option_id"], option_id)
        self.assertIn(str(task_id), task["citation"])
        self.assertIn(str(option_id), task["citation"])
        self.assertEqual(overview["goals"]["count"], 0)
        self.assertIn("CASE-ALPHA", overview["goals"]["citation"])
        self.assertEqual(overview["journey_stage"]["stage"], "review_required")
        self.assertIn("CASE-ALPHA", overview["journey_stage"]["citation"])

    def test_pending_reviews_match_review_queue_exactly(self):
        original = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        imaging = self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        question_id = self.store.add_question("CASE-ALPHA", BENIGN_QUESTION)
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id, BENIGN_SUMMARY, [original["source_id"]],
        )
        self.store.acknowledge_demo_review("CASE-ALPHA", snapshot_id, "Synthetic reviewer")
        option_id = self.store.create_option(
            "CASE-ALPHA", snapshot_id, BENIGN_OPTION_LABEL, BENIGN_OPTION_DESC, "unknown",
        )
        self.store.add_option_dependency(
            "CASE-ALPHA", option_id, "source",
            source_version_id=original["source_id"],
        )
        imaging_question = self.store.add_question("CASE-ALPHA", BENIGN_QUESTION + " (imaging)")
        imaging_snapshot = self.store.create_snapshot(
            "CASE-ALPHA", imaging_question, BENIGN_SUMMARY, [imaging["source_id"]],
        )

        amendment = self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))
        self.assertEqual(amendment["invalidated_snapshots"], [snapshot_id])
        quarantine = self.store.import_report("CASE-ALPHA", report("wrong-patient.txt"))
        self.assertEqual(quarantine["result"], "quarantined")

        state = self.store.state("CASE-ALPHA")
        open_ids = {q["id"] for q in state["questions"] if q["state"] == "open"}
        expected_drafts = {s["id"] for s in state["snapshots"] if s["state"] == "draft"}
        expected_stale = {s["id"] for s in state["snapshots"]
                          if s["state"] == "stale" and s["question_id"] in open_ids}
        expected_options = {o["id"] for o in state["options"] if o["review_state"] == "needs_review"}
        expected_quarantine = {q["id"] for q in state["quarantines"]}

        overview = self.overview("CASE-ALPHA")
        got_drafts = {item["snapshot_id"] for item in overview["pending_reviews"]
                      if item["kind"] == "snapshot_draft"}
        got_stale = {item["snapshot_id"] for item in overview["pending_reviews"]
                     if item["kind"] == "snapshot_stale"}
        got_options = {item["option_id"] for item in overview["pending_reviews"]
                       if item["kind"] == "option_needs_review"}
        got_quarantine = {item["quarantine_id"] for item in overview["pending_reviews"]
                          if item["kind"] == "quarantined_delivery"}

        self.assertEqual(got_drafts, expected_drafts)
        self.assertEqual(got_stale, expected_stale)
        self.assertEqual(got_options, expected_options)
        self.assertEqual(got_quarantine, expected_quarantine)
        self.assertIn(snapshot_id, got_stale)
        self.assertIn(option_id, got_options)
        self.assertIn(imaging_snapshot, got_drafts)
        self.assertIn(quarantine["quarantine_id"], got_quarantine)

        # A replacement that addresses the question retires the historical
        # stale snapshot from pending without deleting history.
        replacement = self.store.create_snapshot(
            "CASE-ALPHA", question_id, BENIGN_SUMMARY + " Amended source inspected.",
            [amendment["source_id"]],
        )
        self.store.acknowledge_demo_review("CASE-ALPHA", replacement, "Synthetic reviewer")
        retired = self.overview("CASE-ALPHA")
        retired_stale = {item["snapshot_id"] for item in retired["pending_reviews"]
                         if item["kind"] == "snapshot_stale"}
        self.assertNotIn(snapshot_id, retired_stale)
        history_ids = {s["id"] for s in self.store.state("CASE-ALPHA")["snapshots"]}
        self.assertIn(snapshot_id, history_ids)

    def test_follow_up_tasks_match_preparation_state_exactly(self):
        first = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        question_id = self.store.add_question("CASE-ALPHA", BENIGN_QUESTION)
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id, BENIGN_SUMMARY, [first["source_id"]],
        )
        option_id = self.store.create_option(
            "CASE-ALPHA", snapshot_id, BENIGN_OPTION_LABEL, BENIGN_OPTION_DESC, "unknown",
        )
        active = self.store.add_preparation_task(
            "CASE-ALPHA", option_id, BENIGN_TASK_LABEL, BENIGN_TASK_OWNER,
        )
        progressing = self.store.add_preparation_task(
            "CASE-ALPHA", option_id, "Fictional records check", BENIGN_TASK_OWNER,
        )
        blocked = self.store.add_preparation_task(
            "CASE-ALPHA", option_id, "Fictional waiting step", BENIGN_TASK_OWNER,
        )
        done = self.store.add_preparation_task(
            "CASE-ALPHA", option_id, "Fictional filed copy", BENIGN_TASK_OWNER,
        )
        cancelled = self.store.add_preparation_task(
            "CASE-ALPHA", option_id, "Fictional withdrawn step", BENIGN_TASK_OWNER,
        )
        self.store.set_preparation_task_status("CASE-ALPHA", progressing, "in_progress")
        self.store.set_preparation_task_status("CASE-ALPHA", blocked, "blocked")
        self.store.set_preparation_task_status("CASE-ALPHA", done, "done")
        self.store.set_preparation_task_status("CASE-ALPHA", cancelled, "cancelled")

        overview = self.overview("CASE-ALPHA")
        got_ids = {item["task_id"] for item in overview["follow_up_tasks"]}
        self.assertEqual(got_ids, {active, progressing, blocked})
        for item in overview["follow_up_tasks"]:
            self.assertEqual(item["option_id"], option_id)
            self.assertIn(str(item["task_id"]), item["citation"])

        # Finishing a task removes it from the projection with no second copy.
        self.store.set_preparation_task_status("CASE-ALPHA", active, "done")
        again = self.overview("CASE-ALPHA")
        self.assertEqual({item["task_id"] for item in again["follow_up_tasks"]},
                         {progressing, blocked})

    def test_goals_count_is_zero_without_invented_goals(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))

        overview = self.overview("CASE-ALPHA")

        self.assertEqual(overview["goals"], {
            "count": 0,
            "items": [],
            "note": "No goals are recorded in the current synthetic ledger for this case.",
            "citation": "case CASE-ALPHA",
        })

    def test_journey_stage_follows_record_without_directing_care(self):
        overview = self.overview("CASE-ALPHA")
        self.assertEqual(overview["journey_stage"]["stage"], "awaiting_sources")

        first = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        overview = self.overview("CASE-ALPHA")
        self.assertEqual(overview["journey_stage"]["stage"], "ready_to_define_question")

        question_id = self.store.add_question("CASE-ALPHA", BENIGN_QUESTION)
        overview = self.overview("CASE-ALPHA")
        self.assertEqual(overview["journey_stage"]["stage"], "investigation_in_progress")

        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id, BENIGN_SUMMARY, [first["source_id"]],
        )
        overview = self.overview("CASE-ALPHA")
        self.assertEqual(overview["journey_stage"]["stage"], "review_required")
        self.assertTrue(overview["pending_reviews"])

        self.store.acknowledge_demo_review("CASE-ALPHA", snapshot_id, "Synthetic reviewer")
        overview = self.overview("CASE-ALPHA")
        self.assertEqual(overview["journey_stage"]["stage"], "reviewed_in_demo")

        self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))
        overview = self.overview("CASE-ALPHA")
        self.assertEqual(overview["journey_stage"]["stage"], "review_required")

    def test_quarantine_history_alone_never_blocks_reviewed_stage(self):
        first = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        question_id = self.store.add_question("CASE-ALPHA", BENIGN_QUESTION)
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id, BENIGN_SUMMARY, [first["source_id"]],
        )
        self.store.acknowledge_demo_review("CASE-ALPHA", snapshot_id, "Synthetic reviewer")
        quarantine = self.store.import_report("CASE-ALPHA", report("wrong-patient.txt"))
        self.assertEqual(quarantine["result"], "quarantined")
        overview = self.overview("CASE-ALPHA")
        # CR-01: quarantine history is listed, never a stage gate.
        self.assertEqual(overview["journey_stage"]["stage"], "reviewed_in_demo")
        got_quarantine = {item["quarantine_id"] for item in overview["pending_reviews"]
                          if item["kind"] == "quarantined_delivery"}
        self.assertIn(quarantine["quarantine_id"], got_quarantine)

    def test_case_isolation_holds(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-BETA", report("beta-pathology.txt"))
        alpha_question = "Alpha-only fictional marker inquiry ZULU- distinct text"
        question_id = self.store.add_question("CASE-ALPHA", alpha_question)
        first = next(s for s in self.store.state("CASE-ALPHA")["sources"] if s["state"] == "current")
        snapshot_id = self.store.create_snapshot("CASE-ALPHA", question_id, BENIGN_SUMMARY, [first["id"]])
        option_id = self.store.create_option(
            "CASE-ALPHA", snapshot_id, "Alpha-only fictional discussion ZULU", BENIGN_OPTION_DESC, "unknown",
        )
        self.store.add_preparation_task(
            "CASE-ALPHA", option_id, "Alpha-only fictional step ZULU", BENIGN_TASK_OWNER,
        )

        beta = self.overview("CASE-BETA")
        rendered = repr(beta)

        self.assertEqual(beta["case"]["case_id"], "CASE-BETA")
        self.assertNotIn("ZULU", rendered)
        self.assertNotIn(alpha_question, rendered)
        self.assertNotIn("PATH-ALPHA", rendered)
        self.assertIn("PATH-BETA", rendered)
        beta_source_ids = {s["id"] for s in self.store.state("CASE-BETA")["sources"]}
        for item in beta["current_sources"]:
            self.assertIn(item["source_version_id"], beta_source_ids)

    def test_view_wide_scan_finds_no_directive_wording(self):
        first = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        second = self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        question_id = self.store.add_question("CASE-ALPHA", BENIGN_QUESTION)
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id, BENIGN_SUMMARY, [first["source_id"], second["source_id"]],
        )
        option_id = self.store.create_option(
            "CASE-ALPHA", snapshot_id, BENIGN_OPTION_LABEL, BENIGN_OPTION_DESC, "unknown",
        )
        self.store.add_preparation_task(
            "CASE-ALPHA", option_id, BENIGN_TASK_LABEL, BENIGN_TASK_OWNER,
        )

        assert_no_directive(self, self.overview("CASE-ALPHA"))
        assert_no_directive(self, self.overview("CASE-BETA"))

        # Negative control: the scan itself must catch directive wording,
        # so a passing scan is evidence rather than a vacuous check.
        for planted in ("authorize this step", "prescribe this item",
                        "order this therapy", "recommend this path",
                        "direct care here"):
            with self.subTest(planted=planted):
                with self.assertRaises(AssertionError):
                    assert_no_directive(self, {"planted": planted,
                                              "disclaimer": DISCLAIMER_LITERAL})

    def test_amendment_supersedes_without_deleting_history(self):
        original = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        question_id = self.store.add_question("CASE-ALPHA", BENIGN_QUESTION)
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id, BENIGN_SUMMARY, [original["source_id"]],
        )
        amendment = self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))

        overview = self.overview("CASE-ALPHA")
        self.assertEqual(len(overview["current_sources"]), 1)
        self.assertEqual(overview["current_sources"][0]["version"], 2)
        self.assertEqual(overview["current_sources"][0]["source_version_id"], amendment["source_id"])
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(len(state["sources"]), 2)
        stale = [item for item in overview["pending_reviews"] if item["kind"] == "snapshot_stale"]
        self.assertEqual([item["snapshot_id"] for item in stale], [snapshot_id])
        for item in overview["current_sources"] + overview["open_questions"]:
            self.assertIn("citation", item)
            self.assertTrue(item["citation"])
        for item in overview["pending_reviews"]:
            self.assertIn("review_state", item)


class ClinicianOverviewHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "clinician-overview-http.sqlite")
        seed(cls.path)
        bound_handler = type(
            "BoundClinicianOverviewHandlerForTest", (Handler,), {"db_path": cls.path}
        )
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

    def request(self, path: str):
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                          headers={FICTIONAL_ACTOR_HEADER: "FICTIONAL-NAVIGATOR-A"})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_seeded_case_exposes_read_only_clinician_overview(self):
        status, overview = self.request("/api/cases/CASE-ALPHA/clinician-overview")

        self.assertEqual(status, 200)
        for section in ("current_sources", "open_questions", "pending_reviews",
                        "follow_up_tasks", "goals", "journey_stage"):
            self.assertIn(section, overview)
        self.assertEqual(overview["case"]["case_id"], "CASE-ALPHA")
        self.assertEqual(overview["disclaimer"], DISCLAIMER_LITERAL)
        self.assertEqual(len(overview["current_sources"]), 2)
        self.assertEqual(overview["journey_stage"]["stage"], "ready_to_define_question")
        for item in overview["current_sources"]:
            self.assertIn("citation", item)
            self.assertIn(str(item["version"]), item["citation"])
        assert_no_directive(self, overview)

    def test_unknown_case_returns_existing_422_boundary(self):
        status, error = self.request("/api/cases/CASE-UNKNOWN/clinician-overview")

        self.assertEqual(status, 422)
        self.assertEqual(error["error"], "Unknown case")


class ClinicianOverviewUiContractTests(unittest.TestCase):
    def test_panel_contains_six_sections_and_disclaimer(self):
        html = (ROOT / "web" / "index.html").read_text()

        self.assertIn('href="#clinician-overview"', html)
        self.assertIn('id="clinician-overview"', html)
        self.assertIn("Clinician overview", html)
        self.assertIn('id="clinician-overview-stage"', html)
        self.assertIn('id="clinician-overview-disclaimer"', html)
        self.assertIn('id="clinician-overview-counts"', html)
        self.assertIn('id="clinician-overview-sources"', html)
        self.assertIn('id="clinician-overview-questions"', html)
        self.assertIn('id="clinician-overview-pending"', html)
        self.assertIn('id="clinician-overview-tasks"', html)
        self.assertIn('id="clinician-overview-goals"', html)
        self.assertIn('id="clinician-overview-journey"', html)
        self.assertIn(DISCLAIMER_LITERAL, html)
        self.assertIn("FICTIONAL", html)
        self.assertIn('<script src="/clinician-overview.js" defer></script>', html)

    def test_renderer_is_case_scoped_text_safe_and_refreshable(self):
        javascript = (ROOT / "web" / "clinician-overview.js").read_text()

        self.assertIn(
            "/api/cases/${encodeURIComponent(caseId)}/clinician-overview",
            javascript,
        )
        self.assertIn("requestSequence", javascript)
        self.assertIn("picker.value !== caseId", javascript)
        self.assertIn("MutationObserver", javascript)
        self.assertIn("textContent", javascript)
        self.assertNotIn("innerHTML", javascript)
        self.assertIn("FICTIONAL", javascript)
        self.assertIn("No current sources recorded for this fictional case.", javascript)
        self.assertIn("No open questions recorded for this fictional case.", javascript)
        self.assertIn("No items waiting for review in this fictional case.", javascript)
        self.assertIn("No follow-up tasks recorded for this fictional case.", javascript)
        self.assertIn("overview.disclaimer", javascript)

    def test_server_serves_renderer_and_route(self):
        server = (ROOT / "src" / "open_intelligence" / "__main__.py").read_text()

        self.assertIn('if path == "/clinician-overview.js":', server)
        self.assertIn('self._static("clinician-overview.js", "text/javascript; charset=utf-8")', server)
        self.assertIn("/clinician-overview", server)
        self.assertIn("build_clinician_overview", server)


if __name__ == "__main__":
    unittest.main()
