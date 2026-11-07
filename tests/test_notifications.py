"""Care coordination dimension (slice D7): notifications — changes and due items.

D7 acceptance: a due task, a re-review trigger, and a staleness event
each produce exactly one visible notification to the right role;
clearing is explicit; suite green with zero new failures.

Fixtures are independently authored synthetic records built through
the store's own methods (follow-through tasks, appointments,
amendments that stale a snapshot and open a re-review task). No live
model call is made here: notifications are deterministic derivations
of the ledger, computed at read time — nothing is sent anywhere, and
clearing acknowledges the alert only, never the underlying work.
"""

import ast
import json
import tempfile
import threading
import unittest
from datetime import date, timedelta
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
from open_intelligence.followthrough import followthrough_view
from open_intelligence.notifications import (
    NotificationInputError,
    check_notification_key,
    notifications_view,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "open_intelligence"
SAMPLE = ROOT / "examples" / "synthetic"

PATIENT = "FICTIONAL-PATIENT-A"
AUDITOR = "FICTIONAL-AUDITOR-A"
UNKNOWN_ACTOR = "FICTIONAL-NOBODY"
PASSWORD = "fictional-d7-test-password"
PURPOSE = FICTIONAL_ACTOR_PURPOSE
ACTOR = "Fictional recorder"
REASON = "Planned at intake, one day after the fictional report"
TODAY = "2026-06-02"


def report(name: str) -> bytes:
    return (SAMPLE / name).read_bytes()


def keys_of(result: dict) -> list[str]:
    return [entry["key"] for entry in result["notifications"]]


def kinds_of(result: dict) -> list[str]:
    return [entry["kind"] for entry in result["notifications"]]


class NotificationStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "notifications.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")
        self.store.add_case("CASE-BETA", "Fictional case Beta")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _task(self, case_id="CASE-ALPHA", title="Fictional record check",
              **overrides):
        return self.store.create_followthrough_task(
            case_id, title, actor_label=ACTOR, reason=REASON, **overrides)

    def _appointment(self, case_id="CASE-ALPHA", title="Fictional visit",
                     scheduled_date="2026-05-20", **overrides):
        return self.store.create_appointment(
            case_id, title, scheduled_date=scheduled_date,
            actor_label=ACTOR, reason=REASON, **overrides)

    def _stale_setup(self, case_id="CASE-ALPHA"):
        """One open question, one draft, one anchored task — then amend.

        The amendment supersedes the original source version, marks
        the draft stale, opens one re-review task, and flags the
        anchored follow-through task for re-check.
        """
        original = self.store.import_report(
            case_id, report("alpha-pathology-original.txt"))
        question_id = self.store.add_question(
            case_id, "What does the fictional Alpha source report about Marker A?")
        snapshot_id = self.store.create_snapshot(
            case_id, question_id,
            "A human-authored fictional draft awaiting demo review.",
            [original["source_id"]])
        anchored = self._task(
            case_id, title="Anchored fictional check",
            source_version_id=original["source_id"])
        amended = self.store.import_report(
            case_id, report("alpha-pathology-amended.txt"))
        self.assertEqual(amended["invalidated_snapshots"], [snapshot_id])
        return {"question_id": question_id, "snapshot_id": snapshot_id,
                "task_id": anchored,
                "source_id": original["source_id"]}

    def test_empty_case_shows_honest_empty_state(self):
        result = notifications_view(self.store, "CASE-BETA", "clinician", TODAY)
        self.assertEqual(result["case_id"], "CASE-BETA")
        self.assertEqual(result["notifications"], [])
        self.assertEqual(result["counts"], {
            "followthrough-overdue": 0, "followthrough-due-soon": 0,
            "appointment-due": 0, "followthrough-recheck": 0,
            "rereview-open": 0, "snapshot-stale": 0})
        self.assertIn("Nothing is sent", result["disclaimer"])
        self.assertTrue(result["synthetic"])

    def test_overdue_task_notifies_patient_and_team_exactly_once(self):
        task_id = self._task(due_date="2026-05-01")
        for role in ("clinician", "operator", "patient"):
            result = notifications_view(self.store, "CASE-ALPHA", role, TODAY)
            self.assertEqual(kinds_of(result), ["followthrough-overdue"])
            self.assertEqual(keys_of(result),
                             [f"followthrough-overdue:{task_id}:2026-05-01"])
        # The view is derived: reading twice never duplicates a trigger.
        again = notifications_view(self.store, "CASE-ALPHA", "clinician", TODAY)
        self.assertEqual(keys_of(again), keys_of(
            notifications_view(self.store, "CASE-ALPHA", "clinician", TODAY)))

    def test_due_soon_task_notifies_as_due_soon_not_overdue(self):
        task_id = self._task(due_date="2026-06-05")
        result = notifications_view(self.store, "CASE-ALPHA", "clinician", TODAY)
        self.assertEqual(keys_of(result),
                         [f"followthrough-due-soon:{task_id}:2026-06-05"])

    def test_task_moves_from_due_soon_to_overdue_exactly_once(self):
        task_id = self._task(due_date="2026-06-05")
        soon = notifications_view(self.store, "CASE-ALPHA", "clinician", "2026-06-02")
        self.assertEqual(keys_of(soon),
                         [f"followthrough-due-soon:{task_id}:2026-06-05"])
        late = notifications_view(self.store, "CASE-ALPHA", "clinician", "2026-06-10")
        self.assertEqual(keys_of(late),
                         [f"followthrough-overdue:{task_id}:2026-06-05"])

    def test_completed_deferred_undated_and_future_tasks_notify_nothing(self):
        finished = self._task(title="Finished fictional check", due_date="2026-05-01")
        self.store.update_followthrough_task(
            "CASE-ALPHA", finished, "assigned", actor_label=ACTOR,
            reason="Assigning the finished fictional task.",
            owner_label="Fictional owner")
        self.store.update_followthrough_task(
            "CASE-ALPHA", finished, "acknowledged", actor_label=ACTOR,
            reason="Acknowledging the finished fictional task.")
        self.store.update_followthrough_task(
            "CASE-ALPHA", finished, "completed", actor_label=ACTOR,
            reason="Completing the finished fictional task.")
        deferred = self._task(title="Deferred fictional check", due_date="2026-05-01")
        self.store.update_followthrough_task(
            "CASE-ALPHA", deferred, "deferred", actor_label=ACTOR,
            reason="Deferring the fictional task with a recorded reason.")
        self._task(title="Undated fictional check")
        self._task(title="Future fictional check", due_date="2026-06-20")
        result = notifications_view(self.store, "CASE-ALPHA", "clinician", TODAY)
        self.assertEqual(result["notifications"], [])

    def test_amendment_yields_recheck_rereview_and_stale_exactly_once_each(self):
        fixture = self._stale_setup()
        team = notifications_view(self.store, "CASE-ALPHA", "clinician", TODAY)
        kinds = kinds_of(team)
        self.assertEqual(kinds.count("followthrough-recheck"), 1)
        self.assertEqual(kinds.count("rereview-open"), 1)
        self.assertEqual(kinds.count("snapshot-stale"), 1)
        self.assertEqual(len(kinds), 3)
        recheck = next(n for n in team["notifications"]
                       if n["kind"] == "followthrough-recheck")
        self.assertEqual(recheck["record_id"], fixture["task_id"])
        self.assertIn(str(fixture["source_id"]), recheck["key"])
        stale = next(n for n in team["notifications"]
                     if n["kind"] == "snapshot-stale")
        self.assertEqual(stale["record_id"], fixture["snapshot_id"])
        # Review work is team-only: the patient sees none of the three.
        patient = notifications_view(self.store, "CASE-ALPHA", "patient", TODAY)
        self.assertEqual(patient["notifications"], [])

    def test_past_due_appointment_notifies_and_future_or_terminal_do_not(self):
        past = self._appointment(scheduled_date="2026-05-20")
        self._appointment(title="Future fictional visit",
                          scheduled_date="2026-07-01")
        cancelled = self._appointment(title="Cancelled fictional visit",
                                      scheduled_date="2026-05-21")
        self.store.change_appointment(
            "CASE-ALPHA", cancelled, "cancel", actor_label=ACTOR,
            reason="The fictional visit is no longer needed.")
        for role in ("clinician", "patient"):
            result = notifications_view(self.store, "CASE-ALPHA", role, TODAY)
            self.assertEqual(keys_of(result),
                             [f"appointment-due:{past}:2026-05-20"])

    def test_patient_sees_due_kinds_only(self):
        self._task(due_date="2026-05-01")
        self._appointment(scheduled_date="2026-05-20")
        self._stale_setup()
        patient = notifications_view(self.store, "CASE-ALPHA", "patient", TODAY)
        self.assertEqual(set(kinds_of(patient)), {
            "followthrough-overdue", "appointment-due"})
        team = notifications_view(self.store, "CASE-ALPHA", "clinician", TODAY)
        self.assertEqual(len(team["notifications"]), 5)

    def test_auditor_sees_nothing(self):
        self._task(due_date="2026-05-01")
        self._stale_setup()
        result = notifications_view(self.store, "CASE-ALPHA", "auditor", TODAY)
        self.assertEqual(result["notifications"], [])

    def test_clearing_removes_for_that_role_only(self):
        task_id = self._task(due_date="2026-05-01")
        key = f"followthrough-overdue:{task_id}:2026-05-01"
        cleared = self.store.clear_notification(
            "CASE-ALPHA", key, "clinician", "FICTIONAL-CLINICIAN-A")
        self.assertEqual(cleared["notification_key"], key)
        self.assertFalse(cleared["already_cleared"])
        self.assertEqual(
            keys_of(notifications_view(
                self.store, "CASE-ALPHA", "clinician", TODAY)), [])
        # The same key stays visible to the patient until they clear it.
        self.assertEqual(
            keys_of(notifications_view(
                self.store, "CASE-ALPHA", "patient", TODAY)), [key])
        self.assertEqual(len(self.store.list_notification_clears("CASE-ALPHA")), 1)
        # Clearing touches nothing underneath: the task is still overdue.
        view = followthrough_view(self.store, "CASE-ALPHA", TODAY)
        self.assertEqual(view["overdue_task_ids"], [task_id])

    def test_clearing_is_idempotent(self):
        task_id = self._task(due_date="2026-05-01")
        key = f"followthrough-overdue:{task_id}:2026-05-01"
        first = self.store.clear_notification(
            "CASE-ALPHA", key, "clinician", "FICTIONAL-CLINICIAN-A")
        second = self.store.clear_notification(
            "CASE-ALPHA", key, "clinician", "FICTIONAL-CLINICIAN-A")
        self.assertFalse(first["already_cleared"])
        self.assertTrue(second["already_cleared"])
        self.assertEqual(len(self.store.list_notification_clears("CASE-ALPHA")), 1)

    def test_clearing_unknown_or_invisible_keys_is_rejected(self):
        self._task(due_date="2026-05-01")
        fixture = self._stale_setup()
        team = notifications_view(self.store, "CASE-ALPHA", "clinician", TODAY)
        stale_key = next(n["key"] for n in team["notifications"]
                         if n["kind"] == "snapshot-stale")
        with self.assertRaises(InvalidInput):
            self.store.clear_notification(
                "CASE-ALPHA", "not-a-key", "clinician", "FICTIONAL-CLINICIAN-A")
        with self.assertRaises(InvalidInput):
            self.store.clear_notification(
                "CASE-ALPHA", "followthrough-overdue:999:2026-05-01",
                "clinician", "FICTIONAL-CLINICIAN-A")
        # A team-only key cannot be cleared by a patient, even guessed.
        with self.assertRaises(InvalidInput):
            self.store.clear_notification(
                "CASE-ALPHA", stale_key, "patient", PATIENT)
        with self.assertRaises(InvalidInput):
            self.store.clear_notification(
                "CASE-ALPHA", stale_key, "auditor", AUDITOR)

    def test_rescheduled_appointment_is_a_new_notification_after_clear(self):
        appointment_id = self._appointment(scheduled_date="2026-05-20")
        old_key = f"appointment-due:{appointment_id}:2026-05-20"
        self.store.clear_notification(
            "CASE-ALPHA", old_key, "clinician", "FICTIONAL-CLINICIAN-A")
        self.store.change_appointment(
            "CASE-ALPHA", appointment_id, "reschedule", actor_label=ACTOR,
            reason="Moving the fictional visit one day later.",
            scheduled_date="2026-05-21")
        result = notifications_view(self.store, "CASE-ALPHA", "clinician", TODAY)
        self.assertEqual(keys_of(result),
                         [f"appointment-due:{appointment_id}:2026-05-21"])

    def test_key_validation(self):
        for good in ("followthrough-overdue:3:2026-05-01",
                     "followthrough-due-soon:3:2026-06-05",
                     "appointment-due:3:2026-05-20",
                     "followthrough-recheck:3:12",
                     "rereview-open:3",
                     "snapshot-stale:3"):
            self.assertEqual(check_notification_key(good), good)
        for bad in (None, 12, "", "followthrough-overdue:3",
                    "followthrough-overdue:0:2026-05-01",
                    "followthrough-overdue:x:2026-05-01",
                    "followthrough-overdue:3:21/05/2026",
                    "followthrough-overdue:3:2026-13-01",
                    "snapshot-stale:3:extra", "unknown-kind:3",
                    "rereview-open:3:2026-05-01"):
            with self.assertRaises(NotificationInputError, msg=bad):
                check_notification_key(bad)

    def test_unknown_case_role_and_today_raise(self):
        with self.assertRaises(InvalidInput):
            notifications_view(self.store, "CASE-NOPE", "clinician", TODAY)
        with self.assertRaises(NotificationInputError):
            notifications_view(self.store, "CASE-ALPHA", "nobody", TODAY)
        with self.assertRaises(NotificationInputError):
            notifications_view(self.store, "CASE-ALPHA", "clinician", "02/06/2026")
        with self.assertRaises(InvalidInput):
            self.store.clear_notification(
                "CASE-NOPE", "followthrough-overdue:1:2026-05-01",
                "clinician", "FICTIONAL-CLINICIAN-A")

    def test_view_is_read_only_and_adds_no_rows(self):
        self._task(due_date="2026-05-01")
        before = self.store.list_notification_clears("CASE-ALPHA")
        first = notifications_view(self.store, "CASE-ALPHA", "clinician", TODAY)
        second = notifications_view(self.store, "CASE-ALPHA", "clinician", TODAY)
        self.assertEqual(first, second)
        self.assertEqual(self.store.list_notification_clears("CASE-ALPHA"), before)

    def test_ordering_is_recorded_date_then_kind(self):
        self._task(title="Later fictional check", due_date="2026-06-05")
        self._task(title="Earlier fictional check", due_date="2026-05-01")
        self._stale_setup()
        result = notifications_view(self.store, "CASE-ALPHA", "clinician", TODAY)
        kinds = kinds_of(result)
        self.assertEqual(kinds[0], "followthrough-overdue")
        self.assertEqual(kinds[1], "followthrough-due-soon")
        # Undated review work sorts after every dated notification.
        self.assertEqual(kinds[-2:], ["rereview-open", "snapshot-stale"])


class NotificationHttpTests(unittest.TestCase):
    """The notification routes, served live like test_http.py."""

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

    def test_empty_case_returns_empty_notifications(self):
        # CASE-BETA is seeded but never written by this class, so its
        # list stays the empty state.
        status, data = self.header_request("/api/cases/CASE-BETA/notifications")
        self.assertEqual(status, 200)
        self.assertEqual(data["case_id"], "CASE-BETA")
        self.assertEqual(data["notifications"], [])
        self.assertEqual(data["counts"], {
            "followthrough-overdue": 0, "followthrough-due-soon": 0,
            "appointment-due": 0, "followthrough-recheck": 0,
            "rereview-open": 0, "snapshot-stale": 0})
        self.assertIn("Nothing is sent", data["disclaimer"])

    def test_overdue_task_round_trip_and_clear(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        status, body = self.header_request(
            "/api/cases/CASE-ALPHA/followthrough-tasks", {
                "title": "Fictional record check", "due_date": yesterday,
                "actor_label": ACTOR, "reason": REASON})
        self.assertEqual(status, 201, body)
        task_id = body["task_id"]
        status, data = self.header_request("/api/cases/CASE-ALPHA/notifications")
        self.assertEqual(status, 200)
        key = f"followthrough-overdue:{task_id}:{yesterday}"
        self.assertIn(key, keys_of(data))
        status, body = self.header_request(
            "/api/cases/CASE-ALPHA/notifications/clear",
            {"notification_key": key})
        self.assertEqual(status, 200, body)
        self.assertFalse(body["already_cleared"])
        status, data = self.header_request("/api/cases/CASE-ALPHA/notifications")
        self.assertNotIn(key, keys_of(data))
        # Clearing touched nothing underneath: the task is still overdue.
        status, view = self.header_request("/api/cases/CASE-ALPHA/followthrough")
        self.assertEqual(status, 200)
        self.assertIn(task_id, view["overdue_task_ids"])

    def test_patient_clears_own_due_notification_but_not_team_kinds(self):
        # A stale draft + open re-review task, built on the shared store
        # (same SQLite file the server reads).
        original = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))
        question_id = self.store.add_question(
            "CASE-ALPHA", "What does the fictional Alpha source report?")
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id,
            "A human-authored fictional draft awaiting demo review.",
            [original["source_id"]])
        self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-amended.txt"))
        patient = self.signin(PATIENT)
        status, data = self.request(
            "/api/cases/CASE-ALPHA/notifications", cookie=patient)
        self.assertEqual(status, 200)
        # The patient sees no review-work notification at all.
        self.assertNotIn("rereview-open", kinds_of(data))
        self.assertNotIn("snapshot-stale", kinds_of(data))
        # ...and cannot clear a team-only key, even guessed.
        status, body = self.request(
            "/api/cases/CASE-ALPHA/notifications/clear",
            {"notification_key": f"snapshot-stale:{snapshot_id}"},
            cookie=patient)
        self.assertEqual(status, 422, body)
        # The patient CAN clear their own due notification (D7 carve-out).
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        task_id = self.store.create_followthrough_task(
            "CASE-ALPHA", "Fictional record check", due_date=yesterday,
            actor_label=ACTOR, reason=REASON)
        key = f"followthrough-overdue:{task_id}:{yesterday}"
        status, data = self.request(
            "/api/cases/CASE-ALPHA/notifications", cookie=patient)
        self.assertIn(key, keys_of(data))
        status, body = self.request(
            "/api/cases/CASE-ALPHA/notifications/clear",
            {"notification_key": key}, cookie=patient)
        self.assertEqual(status, 200, body)
        status, data = self.request(
            "/api/cases/CASE-ALPHA/notifications", cookie=patient)
        self.assertNotIn(key, keys_of(data))
        # The carve-out is route-specific: patient writes elsewhere
        # are still denied by role.
        status, body = self.request("/api/cases/CASE-ALPHA/appointments", {
            "title": "Patient-created visit", "scheduled_date": "2026-11-20",
            "actor_label": ACTOR}, cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": ROLE_DENIAL_MESSAGE})
        # And on another case entirely, even the clear route is denied.
        status, body = self.request("/api/cases/CASE-BETA/notifications/clear",
                                    {"notification_key": key}, cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})

    def test_routes_require_a_grant_and_role(self):
        for path, data in (
                ("/api/cases/CASE-ALPHA/notifications", None),
                ("/api/cases/CASE-ALPHA/notifications/clear",
                 {"notification_key": "followthrough-overdue:1:2026-05-01"}),
        ):
            with self.subTest(path=path, data=data is not None):
                status, body = self.request(path, data)
                self.assertEqual(status, 403)
                self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        auditor = self.signin(AUDITOR)
        status, body = self.request(
            "/api/cases/CASE-ALPHA/notifications", cookie=auditor)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        status, body = self.request("/api/cases/CASE-ALPHA/notifications")
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})

    def test_clear_rejects_unknown_and_inactive_keys(self):
        status, body = self.header_request(
            "/api/cases/CASE-ALPHA/notifications/clear",
            {"notification_key": "not-a-key"})
        self.assertEqual(status, 422)
        status, body = self.header_request(
            "/api/cases/CASE-ALPHA/notifications/clear",
            {"notification_key": "followthrough-overdue:999999:2026-05-01"})
        self.assertEqual(status, 422)

    def test_unknown_case_uses_existing_case_boundary(self):
        status, body = self.header_request("/api/cases/CASE-NOPE/notifications")
        self.assertEqual(status, 422)


class NoModelCallTests(unittest.TestCase):
    def test_module_has_no_model_call_and_no_dimension_import(self):
        # D7 is deterministic code over the ledger: it never calls a
        # model and never imports another dimension module. The
        # follow-through import is the same care-coordination
        # dimension's pre-existing view, not a dimension module.
        dimension_modules = {
            "extraction", "specimen_chain", "terminology", "fhir_exchange",
            "dicom", "longitudinal", "lab_series", "imaging", "molecular",
            "therapy", "patient_analytics",
            "literature", "trials", "hypothesis",
            "appointments", "notifications",
        }
        tree = ast.parse((SRC / "notifications.py").read_text())
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
