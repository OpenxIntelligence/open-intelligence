"""Care coordination dimension (slice D6): appointments — times and changes.

D6 acceptance: design settled before code; CRUD + change history work on
synthetic data; role gates enforced (patient sees own case only); suite
green with zero new failures.

Fixtures are independently authored synthetic appointments recorded
through the store's own methods. No live model call is made here:
appointments are deterministic records over the ledger — a scheduled
date is a recorded plan, never a booking, and the platform sends
nothing and books nothing.
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
    FICTIONAL_ACTOR_HEADER,
    FICTIONAL_ACTOR_PURPOSE,
    GRANT_DENIAL_MESSAGE,
    ROLE_DENIAL_MESSAGE,
    Handler,
    seed,
)
from open_intelligence.appointments import (
    AppointmentInputError,
    appointments_view,
    check_reason,
    check_scheduled_date,
    check_time,
    check_title,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "open_intelligence"

PATIENT = "FICTIONAL-PATIENT-A"
AUDITOR = "FICTIONAL-AUDITOR-A"
UNKNOWN_ACTOR = "FICTIONAL-NOBODY"
PASSWORD = "fictional-demo-password"
PURPOSE = FICTIONAL_ACTOR_PURPOSE
ACTOR = "Fictional recorder"
REASON = "Planned at intake, one day after the fictional report"


def create_appointment(store, case_id="CASE-ALPHA", **overrides):
    """One synthetic appointment through the store's own method."""
    values = {
        "title": "Follow-up visit",
        "scheduled_date": "2026-11-20",
        "scheduled_time": "09:30",
        "purpose": "Review the fictional report",
        "location": "Room 4",
        "actor_label": ACTOR,
        "reason": REASON,
    }
    values.update(overrides)
    return store.create_appointment(case_id, values.pop("title"), **values)


class AppointmentValidationTests(unittest.TestCase):
    def test_title_date_time_and_reason_rules(self):
        self.assertEqual(check_title("  Follow-up visit  "), "Follow-up visit")
        self.assertEqual(check_scheduled_date("2026-11-20"), "2026-11-20")
        self.assertEqual(check_time("09:30"), "09:30")
        self.assertIsNone(check_time(None))
        self.assertEqual(check_reason("short note", required=False), "short note")
        self.assertEqual(check_reason(None, required=False), "")
        for bad_date in (None, "", "20/11/2026", "2026-13-01", "2026-11-20T09:30"):
            with self.subTest(bad_date=bad_date):
                with self.assertRaises(AppointmentInputError):
                    check_scheduled_date(bad_date)
        for bad_time in ("", "9:30", "24:00", "09:60", "09:30:00", 930):
            with self.subTest(bad_time=bad_time):
                with self.assertRaises(AppointmentInputError):
                    check_time(bad_time)
        for bad_title in (None, "", "   ", "x" * 121):
            with self.subTest(bad_title=bad_title):
                with self.assertRaises(AppointmentInputError):
                    check_title(bad_title)
        with self.assertRaises(AppointmentInputError):
            check_reason("too short", required=True)
        with self.assertRaises(AppointmentInputError):
            check_reason(None, required=True)

    def test_clinical_language_is_rejected_in_appointment_text(self):
        # The guard is the follow-through guard, reused — one canonical
        # rule, not a fork. Every author-controlled field carries it.
        for field, value in (
                ("title", "You should start treatment"),
                ("title", "Best drug for this case"),
                ("purpose", "Prescribe the fictional dose"),
                ("location", "Eligible patients clinic"),
                ("reason", "Diagnose the fictional marker"),
                ("actor", "Recommend treatment now"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(AppointmentInputError):
                    if field == "title":
                        check_title(value)
                    elif field == "purpose":
                        from open_intelligence.appointments import check_purpose
                        check_purpose(value)
                    elif field == "location":
                        from open_intelligence.appointments import check_location
                        check_location(value)
                    elif field == "reason":
                        check_reason(value, required=True)
                    else:
                        from open_intelligence.appointments import check_actor_label
                        check_actor_label(value)
        # Plain planning language passes.
        self.assertEqual(check_title("Review the fictional report"), "Review the fictional report")


class AppointmentStoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.dir.name) / "t.db")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.dir.cleanup()

    def test_create_lists_scheduled_with_created_event(self):
        appointment_id = create_appointment(self.store)
        listed = self.store.list_appointments("CASE-ALPHA")
        self.assertEqual(len(listed["appointments"]), 1)
        item = listed["appointments"][0]
        self.assertEqual(item["appointment_id"], appointment_id)
        current = item["current"]
        self.assertEqual(current["title"], "Follow-up visit")
        self.assertEqual(current["scheduled_date"], "2026-11-20")
        self.assertEqual(current["scheduled_time"], "09:30")
        self.assertEqual(current["purpose"], "Review the fictional report")
        self.assertEqual(current["location"], "Room 4")
        self.assertEqual(current["status"], "scheduled")
        self.assertEqual(len(item["history"]), 1)
        created = item["history"][0]
        self.assertEqual(created["change_kind"], "created")
        self.assertIsNone(created["previous_date"])
        self.assertEqual(created["new_date"], "2026-11-20")
        self.assertEqual(created["new_time"], "09:30")
        self.assertIsNone(created["previous_status"])
        self.assertEqual(created["new_status"], "scheduled")
        self.assertEqual(created["actor_label"], ACTOR)
        self.assertEqual(created["reason"], REASON)
        self.assertIn("Fictional appointments only", listed["disclaimer"])
        self.assertTrue(listed["synthetic"])

    def test_create_without_time_or_location(self):
        appointment_id = create_appointment(
            self.store, scheduled_time=None, purpose=None, location=None, reason=None)
        current = self.store.list_appointments("CASE-ALPHA")["appointments"][0]["current"]
        self.assertEqual(current["scheduled_time"], None)
        self.assertEqual(current["purpose"], "")
        self.assertEqual(current["location"], "")
        self.assertEqual(appointment_id, 1)

    def test_reschedule_keeps_status_and_records_previous_and_new(self):
        appointment_id = create_appointment(self.store)
        outcome = self.store.change_appointment(
            "CASE-ALPHA", appointment_id, "reschedule",
            scheduled_date="2026-11-21", scheduled_time="10:00",
            actor_label=ACTOR, reason="Room 4 is booked that day, moving one day")
        self.assertEqual(outcome["result"], "scheduled")
        self.assertEqual(outcome["change_kind"], "rescheduled")
        self.assertEqual(outcome["previous_status"], "scheduled")
        item = self.store.list_appointments("CASE-ALPHA")["appointments"][0]
        self.assertEqual(item["current"]["status"], "scheduled")
        self.assertEqual(item["current"]["scheduled_date"], "2026-11-21")
        self.assertEqual(item["current"]["scheduled_time"], "10:00")
        self.assertEqual(len(item["history"]), 2)
        event = item["history"][1]
        self.assertEqual(event["change_kind"], "rescheduled")
        self.assertEqual(event["previous_date"], "2026-11-20")
        self.assertEqual(event["new_date"], "2026-11-21")
        self.assertEqual(event["previous_time"], "09:30")
        self.assertEqual(event["new_time"], "10:00")

    def test_reschedule_without_a_new_time_keeps_the_current_time(self):
        appointment_id = create_appointment(self.store)
        self.store.change_appointment(
            "CASE-ALPHA", appointment_id, "reschedule",
            scheduled_date="2026-11-21",
            actor_label=ACTOR, reason="Moving one day, same morning time")
        item = self.store.list_appointments("CASE-ALPHA")["appointments"][0]
        self.assertEqual(item["current"]["scheduled_date"], "2026-11-21")
        self.assertEqual(item["current"]["scheduled_time"], "09:30")
        self.assertEqual(item["history"][1]["new_time"], "09:30")

    def test_reschedule_rules(self):
        appointment_id = create_appointment(self.store)
        # A reschedule needs a new date.
        with self.assertRaises(InvalidInput):
            self.store.change_appointment(
                "CASE-ALPHA", appointment_id, "reschedule",
                scheduled_time="10:00",
                actor_label=ACTOR, reason="New time only, no new date given")
        # A reschedule that changes neither date nor time is a no-op.
        with self.assertRaises(InvalidInput):
            self.store.change_appointment(
                "CASE-ALPHA", appointment_id, "reschedule",
                scheduled_date="2026-11-20", scheduled_time="09:30",
                actor_label=ACTOR, reason="Same date and time as before")
        # A bad new date is rejected before any write.
        with self.assertRaises(InvalidInput):
            self.store.change_appointment(
                "CASE-ALPHA", appointment_id, "reschedule",
                scheduled_date="21/11/2026",
                actor_label=ACTOR, reason="Bad date format in the request")
        self.assertEqual(
            len(self.store.list_appointments("CASE-ALPHA")["appointments"][0]["history"]), 1)

    def test_cancel_and_complete_are_terminal_history(self):
        cancelled = create_appointment(self.store, title="Cancelled visit")
        outcome = self.store.change_appointment(
            "CASE-ALPHA", cancelled, "cancel",
            actor_label=ACTOR, reason="Patient asked to cancel the fictional visit")
        self.assertEqual(outcome["result"], "cancelled")
        self.assertEqual(outcome["change_kind"], "cancelled")
        completed = create_appointment(self.store, title="Completed visit")
        outcome = self.store.change_appointment(
            "CASE-ALPHA", completed, "complete",
            actor_label=ACTOR, reason="Visit happened as planned that day")
        self.assertEqual(outcome["result"], "completed")
        for appointment_id in (cancelled, completed):
            with self.subTest(appointment_id=appointment_id):
                with self.assertRaises(InvalidInput):
                    self.store.change_appointment(
                        "CASE-ALPHA", appointment_id, "reschedule",
                        scheduled_date="2026-12-01",
                        actor_label=ACTOR, reason="Trying to reopen a closed record")
                with self.assertRaises(InvalidInput):
                    self.store.change_appointment(
                        "CASE-ALPHA", appointment_id, "cancel",
                        actor_label=ACTOR, reason="Trying to cancel it again now")

    def test_cancel_or_complete_carries_no_new_date_or_time(self):
        appointment_id = create_appointment(self.store)
        for action in ("cancel", "complete"):
            with self.subTest(action=action):
                with self.assertRaises(InvalidInput):
                    self.store.change_appointment(
                        "CASE-ALPHA", appointment_id, action,
                        scheduled_date="2026-11-21",
                        actor_label=ACTOR, reason="A date rides on a close-out")
                with self.assertRaises(InvalidInput):
                    self.store.change_appointment(
                        "CASE-ALPHA", appointment_id, action,
                        scheduled_time="10:00",
                        actor_label=ACTOR, reason="A time rides on a close-out")

    def test_invalid_action_id_and_reason_are_rejected(self):
        appointment_id = create_appointment(self.store)
        with self.assertRaises(InvalidInput):
            self.store.change_appointment(
                "CASE-ALPHA", appointment_id, "postpone",
                scheduled_date="2026-11-21",
                actor_label=ACTOR, reason="Not one of the three actions")
        with self.assertRaises(InvalidInput):
            self.store.change_appointment(
                "CASE-ALPHA", 999, "cancel",
                actor_label=ACTOR, reason="No such appointment in this case")
        with self.assertRaises(InvalidInput):
            self.store.change_appointment(
                "CASE-ALPHA", appointment_id, "cancel",
                actor_label=ACTOR, reason="short")
        with self.assertRaises(InvalidInput):
            self.store.create_appointment(
                "CASE-NOPE", "Missing case", scheduled_date="2026-11-20",
                actor_label=ACTOR)

    def test_history_is_append_only(self):
        appointment_id = create_appointment(self.store)
        self.store.change_appointment(
            "CASE-ALPHA", appointment_id, "reschedule",
            scheduled_date="2026-11-21",
            actor_label=ACTOR, reason="Moving one day, same morning time")
        before = self.store.list_appointments("CASE-ALPHA")["appointments"][0]["history"]
        self.store.change_appointment(
            "CASE-ALPHA", appointment_id, "cancel",
            actor_label=ACTOR, reason="Patient asked to cancel the fictional visit")
        after = self.store.list_appointments("CASE-ALPHA")["appointments"][0]["history"]
        self.assertEqual(len(after), 3)
        self.assertEqual(after[:2], before)
        self.assertEqual(after[2]["change_kind"], "cancelled")

    def test_appointments_are_case_scoped(self):
        appointment_id = create_appointment(self.store, case_id="CASE-ALPHA")
        self.assertEqual(self.store.list_appointments("CASE-BETA")["appointments"], [])
        with self.assertRaises(InvalidInput):
            self.store.change_appointment(
                "CASE-BETA", appointment_id, "cancel",
                actor_label=ACTOR, reason="Wrong case for this appointment")

    def test_creating_an_appointment_touches_no_other_ledger(self):
        before = self.store.list_appointments("CASE-ALPHA")
        create_appointment(self.store)
        after = self.store.list_appointments("CASE-ALPHA")
        self.assertEqual(len(before["appointments"]) + 1, len(after["appointments"]))
        self.assertEqual(self.store.list_appointments("CASE-BETA")["appointments"], [])


class AppointmentsViewTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.dir.name) / "t.db")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")

    def tearDown(self):
        self.dir.cleanup()

    def test_view_sorts_by_date_and_counts_statuses(self):
        create_appointment(self.store, title="Later visit", scheduled_date="2026-12-05")
        create_appointment(self.store, title="Earlier visit", scheduled_date="2026-11-10")
        cancelled = create_appointment(
            self.store, title="Cancelled visit", scheduled_date="2026-11-15")
        self.store.change_appointment(
            "CASE-ALPHA", cancelled, "cancel",
            actor_label=ACTOR, reason="Patient asked to cancel the fictional visit")
        view = appointments_view(self.store, "CASE-ALPHA")
        titles = [item["current"]["title"] for item in view["appointments"]]
        self.assertEqual(titles, ["Earlier visit", "Cancelled visit", "Later visit"])
        self.assertEqual(view["counts"], {
            "scheduled": 2, "cancelled": 1, "completed": 0, "past_due_date": 0})
        self.assertEqual(view["case_id"], "CASE-ALPHA")
        self.assertTrue(view["synthetic"])

    def test_view_flags_past_due_dates_only_when_today_is_supplied(self):
        create_appointment(self.store, title="Past visit", scheduled_date="2026-11-10")
        create_appointment(self.store, title="Future visit", scheduled_date="2026-11-20")
        without_today = appointments_view(self.store, "CASE-ALPHA")
        self.assertEqual([i["days_until"] for i in without_today["appointments"]],
                         [None, None])
        with_today = appointments_view(self.store, "CASE-ALPHA", today="2026-11-15")
        self.assertEqual([i["days_until"] for i in with_today["appointments"]], [-5, 5])
        self.assertEqual([i["past_due_date"] for i in with_today["appointments"]],
                         [True, False])
        self.assertEqual(with_today["counts"]["past_due_date"], 1)
        # Flagging a past due date changes nothing stored.
        self.assertEqual(
            self.store.list_appointments("CASE-ALPHA")["appointments"][0]["current"]["status"],
            "scheduled")
        with self.assertRaises(AppointmentInputError):
            appointments_view(self.store, "CASE-ALPHA", today="15/11/2026")


class AppointmentsHttpTests(unittest.TestCase):
    """The appointment routes, served live like test_http.py."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        cls.store = CaseStore(cls.path)
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

    def request(self, path, data=None, cookie=None, actor=None):
        headers = {}
        if cookie is not None:
            headers["Cookie"] = cookie
        if actor is not None:
            headers[FICTIONAL_ACTOR_HEADER] = actor
        status, _, body = self.raw(path, data, headers)
        return status, body

    def header_request(self, path, data=None, actor=DEMO_ACTOR):
        return self.request(path, data, actor=actor)

    def test_list_route_returns_appointments_and_empty_state(self):
        # CASE-BETA is seeded but never written by this class, so its
        # list stays the empty state even though other tests create
        # appointments on CASE-ALPHA (shared server, alphabetical order).
        status, data = self.header_request("/api/cases/CASE-BETA/appointments")
        self.assertEqual(status, 200)
        self.assertEqual(data["case_id"], "CASE-BETA")
        self.assertEqual(data["appointments"], [])
        self.assertEqual(data["counts"], {
            "scheduled": 0, "cancelled": 0, "completed": 0, "past_due_date": 0})
        self.assertIn("Fictional appointments only", data["disclaimer"])

    def test_create_and_change_routes_round_trip(self):
        status, body = self.header_request("/api/cases/CASE-ALPHA/appointments", {
            "title": "Follow-up visit", "purpose": "Review the fictional report",
            "scheduled_date": "2026-11-20", "scheduled_time": "09:30",
            "location": "Room 4", "actor_label": ACTOR, "reason": REASON})
        self.assertEqual(status, 201, body)
        appointment_id = body["appointment_id"]
        status, data = self.header_request("/api/cases/CASE-ALPHA/appointments")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["appointments"]), 1)
        self.assertEqual(data["appointments"][0]["current"]["title"], "Follow-up visit")
        status, body = self.header_request(
            f"/api/cases/CASE-ALPHA/appointments/{appointment_id}/change", {
                "action": "reschedule", "scheduled_date": "2026-11-21",
                "actor_label": ACTOR,
                "reason": "Room 4 is booked that day, moving one day"})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["result"], "scheduled")
        self.assertEqual(body["change_kind"], "rescheduled")
        status, data = self.header_request("/api/cases/CASE-ALPHA/appointments")
        current = data["appointments"][0]["current"]
        self.assertEqual(current["scheduled_date"], "2026-11-21")
        self.assertEqual(current["scheduled_time"], "09:30")
        self.assertEqual(len(data["appointments"][0]["history"]), 2)
        # A bad create is a 422 and writes nothing.
        status, body = self.header_request("/api/cases/CASE-ALPHA/appointments", {
            "title": "Bad date visit", "scheduled_date": "21/11/2026",
            "actor_label": ACTOR})
        self.assertEqual(status, 422)
        status, data = self.header_request("/api/cases/CASE-ALPHA/appointments")
        self.assertEqual(len(data["appointments"]), 1)

    def test_routes_require_a_grant(self):
        for path, data in (
                ("/api/cases/CASE-ALPHA/appointments", None),
                ("/api/cases/CASE-ALPHA/appointments", {
                    "title": "No grant visit", "scheduled_date": "2026-11-20",
                    "actor_label": ACTOR}),
        ):
            with self.subTest(path=path, data=data is not None):
                status, body = self.request(path, data, actor=UNKNOWN_ACTOR)
                self.assertEqual(status, 403)
                self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})

    def test_role_gates_patient_reads_own_case_only_and_never_writes(self):
        patient = self.signin(PATIENT)
        status, data = self.request("/api/cases/CASE-ALPHA/appointments", cookie=patient)
        self.assertEqual(status, 200)
        status, body = self.request("/api/cases/CASE-BETA/appointments", cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        # Patient writes are denied by role even on their own case.
        status, body = self.request("/api/cases/CASE-ALPHA/appointments", {
            "title": "Patient-created visit", "scheduled_date": "2026-11-20",
            "actor_label": ACTOR}, cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": ROLE_DENIAL_MESSAGE})
        # Auditor holds no case grants: the grant gate denies case routes.
        auditor = self.signin(AUDITOR)
        status, body = self.request("/api/cases/CASE-ALPHA/appointments", cookie=auditor)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        # Unauthenticated case routes are denied.
        status, body = self.request("/api/cases/CASE-ALPHA/appointments")
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})


class NoModelCallTests(unittest.TestCase):
    def test_module_has_no_model_call_and_no_dimension_import(self):
        # D6 is deterministic code over the ledger: it never calls a
        # model and never imports another dimension module. The
        # follow-through import is the same care-coordination
        # dimension's pre-existing text guard, not a dimension module.
        dimension_modules = {
            "extraction", "specimen_chain", "terminology", "fhir_exchange",
            "dicom", "longitudinal", "lab_series", "imaging", "molecular",
            "therapy", "patient_analytics",
            "literature", "trials", "hypothesis",
            "appointments",
        }
        tree = ast.parse((SRC / "appointments.py").read_text())
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
