import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import (
    FICTIONAL_ACTOR_PURPOSE,
    Handler,
    seed,
)
from session_auth import signin_demo
from open_intelligence.store import CaseStore

ROOT = Path(__file__).resolve().parents[1]

STAGES = ("intake", "sources", "questions", "review", "report", "followthrough")

# Descriptive-only wording: the journey shell must never carry clinical-action
# language. Checked as substrings against the lowercased journey section.
FORBIDDEN_WORDING = ("recommend", "prescrib", "authoriz", "order", "direct")


def journey_section() -> str:
    html = (ROOT / "web" / "index.html").read_text()
    start = html.index('<section class="panel panel-journey" id="journey"')
    end = html.index("</section>", start)
    return html[start:end]


class JourneyShellUiContractTests(unittest.TestCase):
    def test_nav_and_panel_link_six_existing_stages(self):
        html = (ROOT / "web" / "index.html").read_text()

        self.assertIn('<a href="#journey">Guided journey</a>', html)
        self.assertIn('id="journey-heading"', html)
        self.assertIn("FICTIONAL DEMO DATA", journey_section())
        for number, name in enumerate(
            ("INTAKE", "SOURCES", "QUESTIONS", "REVIEW", "REPORT", "FOLLOW-THROUGH"),
            start=1,
        ):
            self.assertIn(f"STEP {number} OF 6 · {name}", journey_section())
        for href in (
            'href="#import"',
            'href="#sources"',
            'href="#investigations"',
            'href="#changes-since-review"',
            'href="#investigation-history-heading"',
            'href="#options"',
        ):
            self.assertIn(href, journey_section())
        for stage in STAGES:
            self.assertIn(f'id="journey-{stage}-pill"', journey_section())
            self.assertIn(f'id="journey-{stage}-status"', journey_section())

    def test_each_step_states_what_it_is_and_is_not(self):
        section = journey_section()

        self.assertEqual(section.count("This step is"), 6)
        self.assertEqual(section.count("It is not"), 6)

    def test_journey_copy_is_descriptive_only(self):
        lowered = journey_section().lower()

        for wording in FORBIDDEN_WORDING:
            self.assertNotIn(wording, lowered)

    def test_loader_renders_from_existing_state_with_text_only_updates(self):
        javascript = (ROOT / "web" / "app.js").read_text()

        self.assertIn("function renderJourney()", javascript)
        self.assertIn("renderJourney();", javascript)
        # IDs are built at runtime: journeyStep(prefix) sets el(prefix +
        # '-pill') and el(prefix + '-status'), so assert the call sites
        # and the construction, not literal IDs that never appear.
        self.assertIn("el(prefix + '-pill')", javascript)
        self.assertIn("el(prefix + '-status')", javascript)
        for stage in STAGES:
            self.assertIn(f"journeyStep('journey-{stage}'", javascript)
        for key in (
            "active.sources",
            "active.assertions",
            "active.questions",
            "active.snapshots",
            "active.options",
            "active.quarantines",
        ):
            self.assertIn(key, javascript)
        self.assertIn("textContent", javascript)
        self.assertNotIn("innerHTML", javascript)

    def test_cross_stage_links_are_pure_anchors_to_existing_targets(self):
        javascript = (ROOT / "web" / "app.js").read_text()
        html = (ROOT / "web" / "index.html").read_text()

        for label in (
            "Open saved drafts",
            "Back to question Q",
            "Continue to discussion items",
            "View investigation #",
        ):
            self.assertIn(label, javascript)
        for href in (
            "#investigation-history-heading",
            "#question-pane-heading",
            "#options",
        ):
            self.assertIn(href, javascript)
        for target in (
            'id="question-pane-heading"',
            'id="investigation-history-heading"',
            'id="options"',
        ):
            self.assertIn(target, html)

    def test_styles_cover_journey_shell(self):
        css = (ROOT / "web" / "style.css").read_text()

        self.assertIn(".panel-journey", css)
        self.assertIn(".journey-grid", css)
        self.assertIn(".journey-step", css)


class JourneyShellHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "journey-shell-http.sqlite")
        seed(cls.path)
        store = CaseStore(cls.path)
        try:
            for case_id in ("CASE-ALPHA", "CASE-BETA"):
                store.create_grant("FICTIONAL-NAVIGATOR-A", case_id,
                                   FICTIONAL_ACTOR_PURPOSE, "2020-01-01", "2999-12-31")
        finally:
            store.close()
        bound_handler = type(
            "BoundJourneyShellHandlerForTest", (Handler,), {"db_path": cls.path}
        )
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()
        cls._cookie = signin_demo(cls.port, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request_json(self, path: str):
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                      headers={"Cookie": self._cookie})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def request_text(self, path: str):
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                      headers={"Cookie": self._cookie})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as error:
            return error.code, error.read().decode("utf-8")

    def test_existing_state_route_carries_everything_the_shell_reads(self):
        status, state = self.request_json("/api/cases/CASE-ALPHA/state")

        self.assertEqual(status, 200)
        for key in (
            "sources",
            "assertions",
            "questions",
            "snapshots",
            "options",
            "quarantines",
        ):
            self.assertIn(key, state)
        current = [s for s in state["sources"] if s["state"] == "current"]
        self.assertEqual(len(current), 2)
        self.assertEqual(len(state["assertions"]), 5)
        self.assertEqual(state["questions"], [])
        self.assertEqual(state["snapshots"], [])
        self.assertEqual(state["options"], [])
        self.assertEqual(state["quarantines"], [])

    def test_portal_serves_journey_panel(self):
        status, body = self.request_text("/")

        self.assertEqual(status, 200)
        self.assertIn('id="journey"', body)
        self.assertIn('<a href="#journey">Guided journey</a>', body)

    def test_unknown_case_keeps_existing_boundary(self):
        status, error = self.request_json("/api/cases/CASE-NOPE/state")

        self.assertEqual(status, 422)
        self.assertEqual(error["error"], "Unknown case")


class DraftFilterUiContractTests(unittest.TestCase):
    def test_filter_control_present_and_text_only(self):
        javascript = (ROOT / "web" / "app.js").read_text()

        self.assertIn("draftQuestionFilter", javascript)
        self.assertIn("draftFilterCaseId", javascript)
        self.assertIn("Showing drafts for Q", javascript)
        self.assertIn("Show all drafts", javascript)
        self.assertIn("textContent", javascript)
        self.assertNotIn("innerHTML", javascript)

    def test_filter_state_resets_on_case_switch(self):
        javascript = (ROOT / "web" / "app.js").read_text()

        self.assertIn("if (!sameCase)", javascript)
        self.assertIn("draftQuestionFilter = null", javascript)
        self.assertIn("draftFilterCaseId = null", javascript)
        self.assertIn("draftFilterCaseId !== caseId", javascript)
        self.assertIn("draftFilterCaseId === caseId", javascript)
        self.assertIn("draftQuestionFilter = question.id", javascript)
        self.assertIn("draftFilterCaseId = caseId", javascript)

    def test_filter_copy_is_descriptive_only(self):
        for snippet in (
            "Showing drafts for Q",
            "Show all drafts",
            "No drafts for this question yet in this fictional case.",
        ):
            lowered = snippet.lower()
            for wording in FORBIDDEN_WORDING:
                self.assertNotIn(wording, lowered)

    def test_filter_is_client_side_only(self):
        javascript = (ROOT / "web" / "app.js").read_text()

        self.assertIn("active.snapshots", javascript)
        self.assertIn(
            "Number(snapshot.question_id) !== Number(draftQuestionFilter)",
            javascript,
        )
        self.assertNotIn("/drafts/filter", javascript)


class DraftFilterHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "draft-filter-http.sqlite")
        seed(cls.path)
        store = CaseStore(cls.path)
        try:
            for case_id in ("CASE-ALPHA", "CASE-BETA"):
                store.create_grant("FICTIONAL-NAVIGATOR-A", case_id,
                                   FICTIONAL_ACTOR_PURPOSE, "2020-01-01", "2999-12-31")
        finally:
            store.close()
        bound_handler = type(
            "BoundDraftFilterHandlerForTest", (Handler,), {"db_path": cls.path}
        )
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()
        cls._cookie = signin_demo(cls.port, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request_json(self, path: str):
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                      headers={"Cookie": self._cookie})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def request_text(self, path: str):
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                      headers={"Cookie": self._cookie})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as error:
            return error.code, error.read().decode("utf-8")

    def test_state_still_returns_unfiltered_lists(self):
        status, state = self.request_json("/api/cases/CASE-ALPHA/state")

        self.assertEqual(status, 200)
        self.assertIn("snapshots", state)
        self.assertIn("questions", state)
        self.assertIn("sources", state)

    def test_portal_still_serves_draft_anchor_targets(self):
        status, body = self.request_text("/")

        self.assertEqual(status, 200)
        self.assertIn('id="snapshot-list"', body)
        self.assertIn('id="question-list"', body)
        self.assertIn('id="investigation-history-heading"', body)


if __name__ == "__main__":
    unittest.main()
