"""Care coordination dimension (slice D9): care-team collaboration —
shared updates and handoffs.

D9 acceptance: design settled before code; a clinician and a patient
account see the same case with role-appropriate views (the patient
sees the same shared record; the role boundary is write access, not
visibility); handoffs are recorded and auditable (append-only status
history, second-opinion review/audit treatment, amendment-driven
reopening); suite green with zero new failures.

Fixtures are independently authored synthetic care-team records
recorded through the store's own methods. No live model call is made
here: updates and handoffs are deterministic records over the
ledger — a shared update or a handoff sends nothing, books nothing,
or contacts anyone.
"""

import ast
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.__main__ import (
    DEMO_ACTOR,
    FICTIONAL_ACTOR_PURPOSE,
    GRANT_DENIAL_MESSAGE,
    ROLE_DENIAL_MESSAGE,
    Handler,
    seed,
)
from open_intelligence.team_collaboration import (
    TeamCollaborationInputError,
    care_team_view,
    check_author_label,
    check_author_role,
    check_change_reason,
    check_close_note,
    check_handoff_reason,
    check_review_scope,
    check_update_text,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "open_intelligence"
SAMPLE = ROOT / "examples" / "synthetic"

PATIENT = "FICTIONAL-PATIENT-A"
AUDITOR = "FICTIONAL-AUDITOR-A"
UNKNOWN_ACTOR = "FICTIONAL-NOBODY"
PASSWORD = "fictional-demo-password"
PURPOSE = FICTIONAL_ACTOR_PURPOSE
ACTOR = "Fictional recorder"
REASON = "The fictional record needs another team's input"
ACK_REASON = "Receipt confirmed by the fictional team"
CLOSE_REASON = "The receiving side recorded the handoff as taken up"
UPDATE_TEXT = "The fictional team noted the shared record for the patient"
REVIEW_SCOPE = "Demo-only acknowledgment of this fictional record."
REVIEWER = "Synthetic reviewer (unverified)"


def report(name):
    return (SAMPLE / name).read_bytes()


def create_update(store, case_id="CASE-ALPHA", **overrides):
    """One synthetic shared update through the store's own method."""
    values = {
        "update_text": UPDATE_TEXT,
        "author_label": ACTOR,
        "author_role": "clinician",
    }
    values.update(overrides)
    return store.create_team_update(
        case_id, values["update_text"],
        author_label=values["author_label"], author_role=values["author_role"])


def create_handoff(store, case_id="CASE-ALPHA", question_id=None, **overrides):
    """One synthetic handoff through the store's own method."""
    values = {
        "from_actor": "Fictional sender",
        "to_actor": "Fictional receiver",
        "reason_text": REASON,
        "source_version_ids": None,  # caller supplies the pinned material
        "actor_label": ACTOR,
    }
    values.update(overrides)
    return store.create_handoff(
        case_id, question_id, values["from_actor"], values["to_actor"],
        values["reason_text"], values["source_version_ids"],
        actor_label=values["actor_label"])


class TeamCollaborationValidationTests(unittest.TestCase):
    def test_update_handoff_and_review_rules(self):
        self.assertEqual(check_update_text("  " + UPDATE_TEXT + "  "), UPDATE_TEXT)
        self.assertEqual(check_author_label("  " + ACTOR + "  "), ACTOR)
        self.assertEqual(check_author_role("operator"), "operator")
        self.assertEqual(check_author_role("clinician"), "clinician")
        self.assertEqual(check_handoff_reason("  " + REASON + "  "), REASON)
        self.assertEqual(check_change_reason("  " + ACK_REASON + "  "), ACK_REASON)
        self.assertEqual(check_close_note("  " + CLOSE_REASON + "  "), CLOSE_REASON)
        self.assertEqual(check_review_scope("  " + REVIEW_SCOPE + "  "), REVIEW_SCOPE)
        for bad in (None, "", "   ", "x" * 1001):
            with self.subTest(bad=bad):
                with self.assertRaises(TeamCollaborationInputError):
                    check_update_text(bad)
        with self.assertRaises(TeamCollaborationInputError):
            check_update_text("too short")
        with self.assertRaises(TeamCollaborationInputError):
            check_handoff_reason("too short")
        with self.assertRaises(TeamCollaborationInputError):
            check_change_reason("too short")
        with self.assertRaises(TeamCollaborationInputError):
            check_close_note("too short")
        with self.assertRaises(TeamCollaborationInputError):
            check_review_scope("too short")
        with self.assertRaises(TeamCollaborationInputError):
            check_author_label("x")
        for bad in (None, "", "patient", "auditor", "OPERATOR"):
            with self.subTest(bad=bad):
                with self.assertRaises(TeamCollaborationInputError):
                    check_author_role(bad)

    def test_clinical_language_is_rejected_in_care_team_text(self):
        # The guard is the follow-through guard, reused — one canonical
        # rule, not a fork. Every author-controlled field carries it.
        for field, value in (
                ("update", "You should start treatment"),
                ("update", "Best drug for this case"),
                ("author", "Recommend treatment now"),
                ("reason", "Prescribe the fictional dose"),
                ("reason", "Eligible patients clinic"),
                ("change_reason", "Start treatment as soon as possible"),
                ("close_note", "Diagnose the fictional marker"),
                ("review_scope", "Order the treatment without waiting"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(TeamCollaborationInputError):
                    if field == "update":
                        check_update_text(value)
                    elif field == "author":
                        check_author_label(value)
                    elif field == "reason":
                        check_handoff_reason(value)
                    elif field == "change_reason":
                        check_change_reason(value)
                    elif field == "close_note":
                        check_close_note(value)
                    else:
                        check_review_scope(value)
        # Plain planning language passes.
        self.assertEqual(check_update_text(UPDATE_TEXT), UPDATE_TEXT)
        self.assertEqual(check_handoff_reason(REASON), REASON)


class TeamUpdateStoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.dir.name) / "t.db")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.store.close()
        self.dir.cleanup()

    def test_create_lists_update_with_pending_review_state(self):
        update_id = create_update(self.store)
        listed = self.store.list_team_updates("CASE-ALPHA")
        self.assertEqual(len(listed["updates"]), 1)
        item = listed["updates"][0]
        self.assertEqual(item["update_id"], update_id)
        current = item["current"]
        self.assertEqual(current["update_text"], UPDATE_TEXT)
        self.assertEqual(current["author_label"], ACTOR)
        self.assertEqual(current["author_role"], "clinician")
        self.assertEqual(current["review_state"], "pending")
        self.assertEqual(item["review_events"], [])
        self.assertIn("Fictional care-team records only", listed["disclaimer"])
        self.assertTrue(listed["synthetic"])

    def test_create_validates_text_role_and_case(self):
        with self.assertRaises(InvalidInput):
            create_update(self.store, update_text="too short")
        with self.assertRaises(InvalidInput):
            create_update(self.store, author_role="patient")
        with self.assertRaises(InvalidInput):
            create_update(self.store, case_id="CASE-NOPE")

    def test_review_acknowledges_and_refuses_repeats(self):
        update_id = create_update(self.store)
        result = self.store.review_team_update(
            "CASE-ALPHA", update_id, REVIEWER, REVIEW_SCOPE)
        self.assertEqual(result["result"], "acknowledged_in_demo")
        item = self.store.list_team_updates("CASE-ALPHA")["updates"][0]
        self.assertEqual(item["current"]["review_state"], "reviewed_in_demo")
        self.assertEqual(len(item["review_events"]), 1)
        self.assertEqual(item["review_events"][0]["action"], "acknowledge")
        self.assertEqual(item["review_events"][0]["reviewer_label"], REVIEWER)
        with self.assertRaises(InvalidInput):
            self.store.review_team_update(
                "CASE-ALPHA", update_id, REVIEWER, REVIEW_SCOPE)

    def test_updates_are_case_scoped(self):
        update_id = create_update(self.store)
        self.assertEqual(self.store.list_team_updates("CASE-BETA")["updates"], [])
        with self.assertRaises(InvalidInput):
            self.store.review_team_update(
                "CASE-BETA", update_id, REVIEWER, REVIEW_SCOPE)


class HandoffStoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.dir.name) / "t.db")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")
        self.path = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.img = self.store.import_report(
            "CASE-ALPHA", report("alpha-imaging.txt"))
        self.beta = self.store.import_report(
            "CASE-BETA", report("beta-pathology.txt"))
        self.q = self.store.add_question(
            "CASE-ALPHA", "What does the fictional record state about marker A?")
        self.q_beta = self.store.add_question(
            "CASE-BETA", "What does the fictional record state about marker A?")

    def tearDown(self):
        self.store.close()
        self.dir.cleanup()

    def _handoff(self, materials=None, question=None):
        return create_handoff(
            self.store, question_id=question or self.q,
            source_version_ids=[self.path["source_id"]] if materials is None else materials)

    def _view_handoff(self, handoff_id):
        for entry in self.store.list_handoffs("CASE-ALPHA")["handoffs"]:
            if entry["handoff_id"] == handoff_id:
                return entry
        self.fail(f"handoff {handoff_id} not in view")

    def test_create_lists_open_with_created_event_and_materials(self):
        handoff_id = self._handoff()
        listed = self.store.list_handoffs("CASE-ALPHA")
        self.assertEqual(len(listed["handoffs"]), 1)
        item = listed["handoffs"][0]
        self.assertEqual(item["handoff_id"], handoff_id)
        current = item["current"]
        self.assertEqual(current["from_actor"], "Fictional sender")
        self.assertEqual(current["to_actor"], "Fictional receiver")
        self.assertEqual(current["reason_text"], REASON)
        self.assertEqual(current["status"], "open")
        self.assertEqual(current["review_state"], "pending")
        self.assertEqual(item["question"],
                         "What does the fictional record state about marker A?")
        self.assertEqual(len(item["materials"]), 1)
        self.assertEqual(item["materials"][0]["id"], self.path["source_id"])
        self.assertEqual(item["materials"][0]["state"], "current")
        self.assertEqual(len(item["history"]), 1)
        created = item["history"][0]
        self.assertEqual(created["change_kind"], "created")
        self.assertIsNone(created["previous_status"])
        self.assertEqual(created["new_status"], "open")
        self.assertEqual(created["actor_label"], ACTOR)
        self.assertEqual(item["review_events"], [])
        self.assertIn("Fictional care-team records only", listed["disclaimer"])
        self.assertTrue(listed["synthetic"])

    def test_create_validates_question_materials_and_case(self):
        with self.assertRaises(InvalidInput):
            self._handoff(question=999999)
        with self.assertRaises(InvalidInput):
            self._handoff(question=self.q_beta)
        with self.assertRaises(InvalidInput):
            self._handoff(materials=[])
        with self.assertRaises(InvalidInput):
            self._handoff(materials=[self.path["source_id"], self.path["source_id"]])
        with self.assertRaises(InvalidInput):
            self._handoff(materials=[self.beta["source_id"]])
        with self.assertRaises(InvalidInput):
            create_handoff(self.store, case_id="CASE-NOPE", question_id=self.q,
                           source_version_ids=[self.path["source_id"]])

    def test_acknowledge_moves_open_to_acknowledged(self):
        handoff_id = self._handoff()
        outcome = self.store.acknowledge_handoff(
            "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=ACK_REASON)
        self.assertEqual(outcome["result"], "acknowledged")
        self.assertEqual(outcome["change_kind"], "acknowledged")
        self.assertEqual(outcome["previous_status"], "open")
        item = self._view_handoff(handoff_id)
        self.assertEqual(item["current"]["status"], "acknowledged")
        self.assertEqual(len(item["history"]), 2)
        event = item["history"][1]
        self.assertEqual(event["change_kind"], "acknowledged")
        self.assertEqual(event["previous_status"], "open")
        self.assertEqual(event["new_status"], "acknowledged")
        self.assertEqual(event["reason"], ACK_REASON)

    def test_acknowledge_rules(self):
        handoff_id = self._handoff()
        with self.assertRaises(InvalidInput):
            self.store.acknowledge_handoff(
                "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason="short")
        with self.assertRaises(InvalidInput):
            self.store.acknowledge_handoff(
                "CASE-ALPHA", 999, actor_label=ACTOR, reason=ACK_REASON)
        self.store.acknowledge_handoff(
            "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=ACK_REASON)
        with self.assertRaises(InvalidInput):
            self.store.acknowledge_handoff(
                "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=ACK_REASON)

    def test_close_requires_acknowledged_and_is_terminal(self):
        handoff_id = self._handoff()
        with self.assertRaises(InvalidInput):
            self.store.close_handoff(
                "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=CLOSE_REASON)
        self.store.acknowledge_handoff(
            "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=ACK_REASON)
        outcome = self.store.close_handoff(
            "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=CLOSE_REASON)
        self.assertEqual(outcome["result"], "closed")
        self.assertEqual(outcome["change_kind"], "closed")
        self.assertEqual(outcome["previous_status"], "acknowledged")
        item = self._view_handoff(handoff_id)
        self.assertEqual(item["current"]["status"], "closed")
        self.assertEqual(len(item["history"]), 3)
        self.assertEqual(item["history"][2]["change_kind"], "closed")
        self.assertEqual(item["history"][2]["reason"], CLOSE_REASON)
        # Terminal: no further transition of any kind.
        for call in (
                lambda: self.store.acknowledge_handoff(
                    "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=ACK_REASON),
                lambda: self.store.close_handoff(
                    "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=CLOSE_REASON),
        ):
            with self.subTest(call=call):
                with self.assertRaises(InvalidInput):
                    call()

    def test_review_acknowledges_and_refuses_repeats(self):
        handoff_id = self._handoff()
        result = self.store.review_handoff(
            "CASE-ALPHA", handoff_id, REVIEWER, REVIEW_SCOPE)
        self.assertEqual(result["result"], "acknowledged_in_demo")
        item = self._view_handoff(handoff_id)
        self.assertEqual(item["current"]["review_state"], "reviewed_in_demo")
        self.assertEqual(len(item["review_events"]), 1)
        self.assertEqual(item["review_events"][0]["action"], "acknowledge")
        self.assertEqual(item["review_events"][0]["reviewer_label"], REVIEWER)
        with self.assertRaises(InvalidInput):
            self.store.review_handoff(
                "CASE-ALPHA", handoff_id, REVIEWER, REVIEW_SCOPE)

    def test_amendment_reopens_handoff_for_review(self):
        handoff_id = self._handoff()
        self.store.acknowledge_handoff(
            "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=ACK_REASON)
        self.store.close_handoff(
            "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=CLOSE_REASON)
        result = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-amended.txt"))
        self.assertEqual(result["invalidated_handoffs"], [handoff_id])
        item = self._view_handoff(handoff_id)
        self.assertEqual(item["current"]["review_state"], "needs_review")
        # The status and history stay visible; only review is refused.
        self.assertEqual(item["current"]["status"], "closed")
        with self.assertRaises(InvalidInput):
            self.store.review_handoff(
                "CASE-ALPHA", handoff_id, REVIEWER, REVIEW_SCOPE)

    def test_history_is_append_only(self):
        handoff_id = self._handoff()
        self.store.acknowledge_handoff(
            "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=ACK_REASON)
        before = self._view_handoff(handoff_id)["history"]
        self.store.close_handoff(
            "CASE-ALPHA", handoff_id, actor_label=ACTOR, reason=CLOSE_REASON)
        after = self._view_handoff(handoff_id)["history"]
        self.assertEqual(len(after), 3)
        self.assertEqual(after[:2], before)
        self.assertEqual(after[2]["change_kind"], "closed")

    def test_handoffs_are_case_scoped(self):
        handoff_id = self._handoff()
        self.assertEqual(self.store.list_handoffs("CASE-BETA")["handoffs"], [])
        for call in (
                lambda: self.store.acknowledge_handoff(
                    "CASE-BETA", handoff_id, actor_label=ACTOR, reason=ACK_REASON),
                lambda: self.store.close_handoff(
                    "CASE-BETA", handoff_id, actor_label=ACTOR, reason=CLOSE_REASON),
                lambda: self.store.review_handoff(
                    "CASE-BETA", handoff_id, REVIEWER, REVIEW_SCOPE),
        ):
            with self.subTest(call=call):
                with self.assertRaises(InvalidInput):
                    call()


class CareTeamViewTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.dir.name) / "t.db")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.path = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.q = self.store.add_question(
            "CASE-ALPHA", "What does the fictional record state about marker A?")

    def tearDown(self):
        self.store.close()
        self.dir.cleanup()

    def test_view_counts_updates_and_handoff_statuses(self):
        first_update = create_update(self.store)
        second_update = create_update(
            self.store, update_text="A second fictional note for the team")
        first = create_handoff(
            self.store, question_id=self.q, source_version_ids=[self.path["source_id"]])
        second = create_handoff(
            self.store, question_id=self.q, source_version_ids=[self.path["source_id"]],
            from_actor="Fictional sender two")
        third = create_handoff(
            self.store, question_id=self.q, source_version_ids=[self.path["source_id"]],
            from_actor="Fictional sender three")
        self.store.acknowledge_handoff(
            "CASE-ALPHA", second, actor_label=ACTOR, reason=ACK_REASON)
        self.store.acknowledge_handoff(
            "CASE-ALPHA", third, actor_label=ACTOR, reason=ACK_REASON)
        self.store.close_handoff(
            "CASE-ALPHA", third, actor_label=ACTOR, reason=CLOSE_REASON)
        view = care_team_view(self.store, "CASE-ALPHA")
        self.assertEqual(view["counts"], {
            "updates": 2, "open": 1, "acknowledged": 1, "closed": 1})
        self.assertEqual(view["case_id"], "CASE-ALPHA")
        self.assertTrue(view["synthetic"])
        self.assertEqual(
            [item["update_id"] for item in view["updates"]],
            [first_update, second_update])
        self.assertEqual(
            [item["handoff_id"] for item in view["handoffs"]],
            [first, second, third])


class CareTeamHttpTests(unittest.TestCase):
    """The care-team routes, served live like test_http.py."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        cls.store = CaseStore(cls.path)
        cls.store.set_account_password(DEMO_ACTOR, PASSWORD)
        cls.store.create_account(PATIENT, "Fictional patient", "patient", PASSWORD,
                                 own_case_id="CASE-ALPHA")
        cls.store.create_account(AUDITOR, "Fictional auditor", "auditor", PASSWORD)
        cls.store.create_grant(PATIENT, "CASE-ALPHA", PURPOSE, "2020-01-01", "2999-12-31")
        cls.q = cls.store.add_question(
            "CASE-ALPHA", "What does the fictional record state about marker A?")
        bound = type("BoundHandlerForTest", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.store.close()
        cls.tmp.cleanup()

    def raw(self, path, data=None, headers=None):
        values = dict(headers or {})
        if data is not None:
            values["Content-Type"] = "application/json"
            values["Origin"] = f"http://127.0.0.1:{self.port}"
        req = Request(f"http://127.0.0.1:{self.port}{path}",
                      data=None if data is None else json.dumps(data).encode(),
                      headers=values)
        try:
            with urlopen(req, timeout=5) as response:
                return (response.status, response.headers.get("Set-Cookie"),
                        json.loads(response.read()))
        except HTTPError as err:
            return err.code, err.headers.get("Set-Cookie"), json.loads(err.read())

    def signin(self, account_id):
        status, cookie, body = self.raw(
            "/api/auth/sign-in", {"account_id": account_id, "password": PASSWORD})
        self.assertEqual(status, 200, body)
        return cookie.split(";", 1)[0]

    def request(self, path, data=None, cookie=None):
        headers = {}
        if cookie is not None:
            headers["Cookie"] = cookie
        status, _, body = self.raw(path, data, headers)
        return status, body

    def header_request(self, path, data=None, actor=DEMO_ACTOR):
        # Slice 2 (W1): the header path is gone; sign in as the actor
        # instead. All call sites use the default demo clinician.
        return self.request(path, data, cookie=self.signin(actor))

    def _seeded_question_and_source(self):
        state = self.store.state("CASE-ALPHA")
        source_id = state["sources"][0]["id"]
        return self.q, source_id

    def test_list_route_returns_care_team_and_empty_state(self):
        status, data = self.header_request("/api/cases/CASE-BETA/care-team")
        self.assertEqual(status, 200)
        self.assertEqual(data["case_id"], "CASE-BETA")
        self.assertEqual(data["updates"], [])
        self.assertEqual(data["handoffs"], [])
        self.assertEqual(data["counts"], {
            "updates": 0, "open": 0, "acknowledged": 0, "closed": 0})
        self.assertIn("Fictional care-team records only", data["disclaimer"])

    def test_update_and_handoff_round_trip(self):
        # The HTTP class shares one seeded server, so earlier tests may
        # already have posted records: assert relative to the list seen
        # at the start of this test, not absolute counts.
        question_id, source_id = self._seeded_question_and_source()
        _status, before = self.header_request("/api/cases/CASE-ALPHA/care-team")
        self.assertEqual(_status, 200)
        status, body = self.header_request("/api/cases/CASE-ALPHA/care-team/updates", {
            "update_text": UPDATE_TEXT, "author_label": ACTOR})
        self.assertEqual(status, 201, body)
        update_id = body["update_id"]
        status, body = self.header_request(
            f"/api/cases/CASE-ALPHA/care-team/updates/{update_id}/review", {
                "reviewer_label": REVIEWER, "scope": REVIEW_SCOPE})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["result"], "acknowledged_in_demo")
        status, body = self.header_request("/api/cases/CASE-ALPHA/care-team/handoffs", {
            "question_id": question_id, "from_actor": "Fictional sender",
            "to_actor": "Fictional receiver", "reason_text": REASON,
            "source_version_ids": [source_id], "actor_label": ACTOR})
        self.assertEqual(status, 201, body)
        handoff_id = body["handoff_id"]
        # A close before acknowledgment is a 422 and writes nothing.
        status, body = self.header_request(
            f"/api/cases/CASE-ALPHA/care-team/handoffs/{handoff_id}/close", {
                "actor_label": ACTOR, "reason": CLOSE_REASON})
        self.assertEqual(status, 422)
        status, body = self.header_request(
            f"/api/cases/CASE-ALPHA/care-team/handoffs/{handoff_id}/acknowledge", {
                "actor_label": ACTOR, "reason": ACK_REASON})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["result"], "acknowledged")
        status, body = self.header_request(
            f"/api/cases/CASE-ALPHA/care-team/handoffs/{handoff_id}/close", {
                "actor_label": ACTOR, "reason": CLOSE_REASON})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["result"], "closed")
        status, body = self.header_request(
            f"/api/cases/CASE-ALPHA/care-team/handoffs/{handoff_id}/review", {
                "reviewer_label": REVIEWER, "scope": REVIEW_SCOPE})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["result"], "acknowledged_in_demo")
        status, data = self.header_request("/api/cases/CASE-ALPHA/care-team")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["updates"]), len(before["updates"]) + 1)
        self.assertEqual(data["updates"][-1]["current"]["review_state"], "reviewed_in_demo")
        self.assertEqual(data["updates"][-1]["current"]["author_role"], "clinician")
        self.assertEqual(len(data["handoffs"]), len(before["handoffs"]) + 1)
        current = data["handoffs"][-1]["current"]
        self.assertEqual(current["status"], "closed")
        self.assertEqual(current["review_state"], "reviewed_in_demo")
        self.assertEqual(len(data["handoffs"][-1]["history"]), 3)
        # A bad update is a 422 and writes nothing.
        status, body = self.header_request("/api/cases/CASE-ALPHA/care-team/updates", {
            "update_text": "too short", "author_label": ACTOR})
        self.assertEqual(status, 422)
        status, data = self.header_request("/api/cases/CASE-ALPHA/care-team")
        self.assertEqual(len(data["updates"]), len(before["updates"]) + 1)

    def test_patient_sees_the_same_shared_record_as_the_clinician(self):
        # D9 acceptance: a clinician and a patient account see the same
        # case with role-appropriate views — the same shared record,
        # with the role boundary at write access, not visibility.
        question_id, source_id = self._seeded_question_and_source()
        self.header_request("/api/cases/CASE-ALPHA/care-team/updates", {
            "update_text": UPDATE_TEXT, "author_label": ACTOR})
        self.header_request("/api/cases/CASE-ALPHA/care-team/handoffs", {
            "question_id": question_id, "from_actor": "Fictional sender",
            "to_actor": "Fictional receiver", "reason_text": REASON,
            "source_version_ids": [source_id], "actor_label": ACTOR})
        _status, clinician = self.header_request("/api/cases/CASE-ALPHA/care-team")
        patient = self.signin(PATIENT)
        status, data = self.request("/api/cases/CASE-ALPHA/care-team", cookie=patient)
        self.assertEqual(status, 200)
        self.assertEqual(data["updates"], clinician["updates"])
        self.assertEqual(data["handoffs"], clinician["handoffs"])
        self.assertEqual(data["counts"], clinician["counts"])

    def test_routes_require_a_grant(self):
        question_id, source_id = self._seeded_question_and_source()
        for path, data in (
                ("/api/cases/CASE-ALPHA/care-team", None),
                ("/api/cases/CASE-ALPHA/care-team/updates", {
                    "update_text": UPDATE_TEXT, "author_label": ACTOR}),
                ("/api/cases/CASE-ALPHA/care-team/handoffs", {
                    "question_id": question_id, "from_actor": "Fictional sender",
                    "to_actor": "Fictional receiver", "reason_text": REASON,
                    "source_version_ids": [source_id], "actor_label": ACTOR}),
        ):
            with self.subTest(path=path, data=data is not None):
                status, body = self.request(path, data)
                self.assertEqual(status, 403)
                self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})

    def test_role_gates_patient_reads_own_case_only_and_never_writes(self):
        patient = self.signin(PATIENT)
        status, data = self.request("/api/cases/CASE-ALPHA/care-team", cookie=patient)
        self.assertEqual(status, 200)
        status, body = self.request("/api/cases/CASE-BETA/care-team", cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        # Patient writes are denied by role even on their own case.
        question_id, source_id = self._seeded_question_and_source()
        status, body = self.request("/api/cases/CASE-ALPHA/care-team/updates", {
            "update_text": UPDATE_TEXT, "author_label": ACTOR}, cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": ROLE_DENIAL_MESSAGE})
        status, body = self.request("/api/cases/CASE-ALPHA/care-team/handoffs", {
            "question_id": question_id, "from_actor": "Fictional sender",
            "to_actor": "Fictional receiver", "reason_text": REASON,
            "source_version_ids": [source_id], "actor_label": ACTOR}, cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": ROLE_DENIAL_MESSAGE})
        # Auditor holds no case grants: the grant gate denies case routes.
        auditor = self.signin(AUDITOR)
        status, body = self.request("/api/cases/CASE-ALPHA/care-team", cookie=auditor)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        # Unauthenticated case routes are denied.
        status, body = self.request("/api/cases/CASE-ALPHA/care-team")
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})


class NoModelCallTests(unittest.TestCase):
    def test_module_has_no_model_call_and_no_dimension_import(self):
        # D9 is deterministic code over the ledger: it never calls a
        # model and never imports another dimension module. The
        # follow-through import is the same care-coordination
        # dimension's pre-existing text guard, not a dimension module.
        dimension_modules = {
            "extraction", "specimen_chain", "terminology", "fhir_exchange",
            "dicom", "longitudinal", "lab_series", "imaging", "molecular",
            "therapy", "patient_analytics",
            "literature", "trials", "hypothesis",
            "appointments", "notifications", "referrals",
        }
        tree = ast.parse((SRC / "team_collaboration.py").read_text())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
        self.assertFalse({"investigation", "skeptic", "__main__"} & imports)
        imported = {name.split(".")[-1] for name in imports}
        self.assertFalse(dimension_modules & imported)


if __name__ == "__main__":
    unittest.main()
