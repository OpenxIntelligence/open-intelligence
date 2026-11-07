"""Care coordination dimension (slice D8): referrals — request, status, outcome.

D8 acceptance: design settled before code; referral lifecycle works on
synthetic data with status history; the second-opinion review/audit
treatment is followed (pinned materials, separate outcome record,
review state reopened by amendments); role gates enforced (patient
sees own case only); suite green with zero new failures.

Fixtures are independently authored synthetic referrals recorded
through the store's own methods. No live model call is made here:
referrals are deterministic records over the ledger — a referral
records a request, never sends anything, books nothing, or contacts
anyone.
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
from open_intelligence.referrals import (
    ReferralInputError,
    check_actor_label,
    check_change_reason,
    check_outcome_kind,
    check_outcome_text,
    check_reason,
    check_review_scope,
    check_specialty,
    referrals_view,
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
OUTCOME_REASON = "Outcome recorded after the fictional review"
OUTCOME_TEXT = "The fictional team took the referral on for review"
REVIEW_SCOPE = "Demo-only acknowledgment of this fictional referral."
REVIEWER = "Synthetic reviewer (unverified)"


def report(name):
    return (SAMPLE / name).read_bytes()


def create_referral(store, case_id="CASE-ALPHA", question_id=None, **overrides):
    """One synthetic referral through the store's own method."""
    values = {
        "specialty_label": "cardiology",
        "reason_text": REASON,
        "source_version_ids": None,  # caller supplies the pinned material
        "actor_label": ACTOR,
    }
    values.update(overrides)
    return store.create_referral(
        case_id, question_id, values["specialty_label"], values["reason_text"],
        values["source_version_ids"], actor_label=values["actor_label"])


class ReferralValidationTests(unittest.TestCase):
    def test_specialty_reason_outcome_and_actor_rules(self):
        self.assertEqual(check_specialty("  cardiology  "), "cardiology")
        self.assertEqual(check_reason("  " + REASON + "  "), REASON)
        self.assertEqual(check_outcome_text("  " + OUTCOME_TEXT + "  "), OUTCOME_TEXT)
        self.assertEqual(check_actor_label("  " + ACTOR + "  "), ACTOR)
        self.assertEqual(check_change_reason("  " + ACK_REASON + "  "), ACK_REASON)
        self.assertEqual(check_review_scope("  " + REVIEW_SCOPE + "  "), REVIEW_SCOPE)
        self.assertEqual(check_outcome_kind("accepted"), "accepted")
        self.assertEqual(check_outcome_kind("declined"), "declined")
        self.assertEqual(check_outcome_kind("completed"), "completed")
        for bad in (None, "", "   ", "x" * 121):
            with self.subTest(bad=bad):
                with self.assertRaises(ReferralInputError):
                    check_specialty(bad)
        with self.assertRaises(ReferralInputError):
            check_reason("too short")
        with self.assertRaises(ReferralInputError):
            check_reason(None)
        with self.assertRaises(ReferralInputError):
            check_outcome_text("too short")
        with self.assertRaises(ReferralInputError):
            check_change_reason("too short")
        with self.assertRaises(ReferralInputError):
            check_review_scope("too short")
        with self.assertRaises(ReferralInputError):
            check_actor_label("x")
        for bad in (None, "", "seen", "referred", "ACCEPTED"):
            with self.subTest(bad=bad):
                with self.assertRaises(ReferralInputError):
                    check_outcome_kind(bad)

    def test_clinical_language_is_rejected_in_referral_text(self):
        # The guard is the follow-through guard, reused — one canonical
        # rule, not a fork. Every author-controlled field carries it.
        for field, value in (
                ("specialty", "You should start treatment"),
                ("specialty", "Best drug for this case"),
                ("reason", "Prescribe the fictional dose"),
                ("reason", "Eligible patients clinic"),
                ("outcome", "Diagnose the fictional marker"),
                ("actor", "Recommend treatment now"),
                ("change_reason", "Start treatment as soon as possible"),
                ("review_scope", "Order the treatment without waiting"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ReferralInputError):
                    if field == "specialty":
                        check_specialty(value)
                    elif field == "reason":
                        check_reason(value)
                    elif field == "outcome":
                        check_outcome_text(value)
                    elif field == "actor":
                        check_actor_label(value)
                    elif field == "change_reason":
                        check_change_reason(value)
                    else:
                        check_review_scope(value)
        # Plain planning language passes.
        self.assertEqual(check_specialty("cardiology"), "cardiology")
        self.assertEqual(check_reason(REASON), REASON)


class ReferralStoreTests(unittest.TestCase):
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

    def _referral(self, materials=None, question=None):
        return create_referral(
            self.store, question_id=question or self.q,
            source_version_ids=[self.path["source_id"]] if materials is None else materials)

    def _view_referral(self, referral_id):
        for entry in self.store.list_referrals("CASE-ALPHA")["referrals"]:
            if entry["referral_id"] == referral_id:
                return entry
        self.fail(f"referral {referral_id} not in view")

    def test_create_lists_requested_with_created_event_and_materials(self):
        referral_id = self._referral()
        listed = self.store.list_referrals("CASE-ALPHA")
        self.assertEqual(len(listed["referrals"]), 1)
        item = listed["referrals"][0]
        self.assertEqual(item["referral_id"], referral_id)
        current = item["current"]
        self.assertEqual(current["specialty_label"], "cardiology")
        self.assertEqual(current["reason_text"], REASON)
        self.assertEqual(current["status"], "requested")
        self.assertEqual(current["review_state"], "pending")
        self.assertEqual(item["question"],
                         "What does the fictional record state about marker A?")
        self.assertEqual(len(item["materials"]), 1)
        self.assertEqual(item["materials"][0]["id"], self.path["source_id"])
        self.assertEqual(item["materials"][0]["state"], "current")
        self.assertIsNone(item["outcome"])
        self.assertEqual(len(item["history"]), 1)
        created = item["history"][0]
        self.assertEqual(created["change_kind"], "created")
        self.assertIsNone(created["previous_status"])
        self.assertEqual(created["new_status"], "requested")
        self.assertEqual(created["actor_label"], ACTOR)
        self.assertEqual(item["review_events"], [])
        self.assertIn("Fictional referrals only", listed["disclaimer"])
        self.assertTrue(listed["synthetic"])

    def test_create_validates_question_materials_and_case(self):
        with self.assertRaises(InvalidInput):
            self._referral(question=999999)
        with self.assertRaises(InvalidInput):
            self._referral(question=self.q_beta)
        with self.assertRaises(InvalidInput):
            self._referral(materials=[])
        with self.assertRaises(InvalidInput):
            self._referral(materials=[self.path["source_id"], self.path["source_id"]])
        with self.assertRaises(InvalidInput):
            self._referral(materials=[self.beta["source_id"]])
        with self.assertRaises(InvalidInput):
            create_referral(self.store, case_id="CASE-NOPE", question_id=self.q,
                            source_version_ids=[self.path["source_id"]])

    def test_acknowledge_moves_requested_to_acknowledged(self):
        referral_id = self._referral()
        outcome = self.store.acknowledge_referral(
            "CASE-ALPHA", referral_id, actor_label=ACTOR, reason=ACK_REASON)
        self.assertEqual(outcome["result"], "acknowledged")
        self.assertEqual(outcome["change_kind"], "acknowledged")
        self.assertEqual(outcome["previous_status"], "requested")
        item = self._view_referral(referral_id)
        self.assertEqual(item["current"]["status"], "acknowledged")
        self.assertEqual(len(item["history"]), 2)
        event = item["history"][1]
        self.assertEqual(event["change_kind"], "acknowledged")
        self.assertEqual(event["previous_status"], "requested")
        self.assertEqual(event["new_status"], "acknowledged")
        self.assertEqual(event["reason"], ACK_REASON)

    def test_acknowledge_rules(self):
        referral_id = self._referral()
        with self.assertRaises(InvalidInput):
            self.store.acknowledge_referral(
                "CASE-ALPHA", referral_id, actor_label=ACTOR, reason="short")
        with self.assertRaises(InvalidInput):
            self.store.acknowledge_referral(
                "CASE-ALPHA", 999, actor_label=ACTOR, reason=ACK_REASON)
        self.store.acknowledge_referral(
            "CASE-ALPHA", referral_id, actor_label=ACTOR, reason=ACK_REASON)
        with self.assertRaises(InvalidInput):
            self.store.acknowledge_referral(
                "CASE-ALPHA", referral_id, actor_label=ACTOR, reason=ACK_REASON)

    def test_outcome_requires_acknowledged_and_is_terminal(self):
        referral_id = self._referral()
        with self.assertRaises(InvalidInput):
            self.store.record_referral_outcome(
                "CASE-ALPHA", referral_id, "accepted", OUTCOME_TEXT,
                self.path["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON)
        self.store.acknowledge_referral(
            "CASE-ALPHA", referral_id, actor_label=ACTOR, reason=ACK_REASON)
        outcome_id = self.store.record_referral_outcome(
            "CASE-ALPHA", referral_id, "accepted", OUTCOME_TEXT,
            self.path["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON)
        self.assertEqual(outcome_id, 1)
        item = self._view_referral(referral_id)
        self.assertEqual(item["current"]["status"], "outcome_recorded")
        self.assertEqual(item["outcome"]["outcome_kind"], "accepted")
        self.assertEqual(item["outcome"]["outcome_text"], OUTCOME_TEXT)
        self.assertEqual(item["outcome"]["anchor"]["document_id"], "PATH-ALPHA")
        self.assertEqual(item["outcome"]["anchor"]["state"], "current")
        self.assertEqual(len(item["history"]), 3)
        self.assertEqual(item["history"][2]["change_kind"], "outcome_recorded")
        # A second outcome is refused; the recorded outcome stays.
        with self.assertRaises(InvalidInput):
            self.store.record_referral_outcome(
                "CASE-ALPHA", referral_id, "completed", OUTCOME_TEXT,
                self.path["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON)
        # Terminal: no further transition of any kind.
        for call in (
                lambda: self.store.acknowledge_referral(
                    "CASE-ALPHA", referral_id, actor_label=ACTOR, reason=ACK_REASON),
                lambda: self.store.record_referral_outcome(
                    "CASE-ALPHA", referral_id, "completed", OUTCOME_TEXT,
                    self.path["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON),
        ):
            with self.subTest(call=call):
                with self.assertRaises(InvalidInput):
                    call()

    def test_outcome_validates_kind_anchor_and_reason(self):
        referral_id = self._referral()
        self.store.acknowledge_referral(
            "CASE-ALPHA", referral_id, actor_label=ACTOR, reason=ACK_REASON)
        with self.assertRaises(InvalidInput):
            self.store.record_referral_outcome(
                "CASE-ALPHA", referral_id, "seen", OUTCOME_TEXT,
                self.path["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON)
        with self.assertRaises(InvalidInput):
            self.store.record_referral_outcome(
                "CASE-ALPHA", referral_id, "accepted", "too short",
                self.path["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON)
        with self.assertRaises(InvalidInput):
            self.store.record_referral_outcome(
                "CASE-ALPHA", referral_id, "accepted", OUTCOME_TEXT,
                self.beta["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON)
        with self.assertRaises(InvalidInput):
            self.store.record_referral_outcome(
                "CASE-ALPHA", referral_id, "accepted", OUTCOME_TEXT,
                self.path["source_id"], actor_label=ACTOR, reason="short")
        # Nothing was written by the refused outcomes.
        item = self._view_referral(referral_id)
        self.assertEqual(item["current"]["status"], "acknowledged")
        self.assertIsNone(item["outcome"])
        self.assertEqual(len(item["history"]), 2)

    def test_outcome_kinds_record(self):
        for kind in ("accepted", "declined", "completed"):
            with self.subTest(kind=kind):
                referral_id = self._referral()
                self.store.acknowledge_referral(
                    "CASE-ALPHA", referral_id, actor_label=ACTOR, reason=ACK_REASON)
                self.store.record_referral_outcome(
                    "CASE-ALPHA", referral_id, kind, OUTCOME_TEXT,
                    self.path["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON)
                self.assertEqual(
                    self._view_referral(referral_id)["outcome"]["outcome_kind"], kind)

    def test_review_acknowledges_and_refuses_repeats(self):
        referral_id = self._referral()
        result = self.store.review_referral(
            "CASE-ALPHA", referral_id, REVIEWER, REVIEW_SCOPE)
        self.assertEqual(result["result"], "acknowledged_in_demo")
        item = self._view_referral(referral_id)
        self.assertEqual(item["current"]["review_state"], "reviewed_in_demo")
        self.assertEqual(len(item["review_events"]), 1)
        self.assertEqual(item["review_events"][0]["action"], "acknowledge")
        self.assertEqual(item["review_events"][0]["reviewer_label"], REVIEWER)
        with self.assertRaises(InvalidInput):
            self.store.review_referral(
                "CASE-ALPHA", referral_id, REVIEWER, REVIEW_SCOPE)

    def test_amendment_reopens_referral_for_review(self):
        referral_id = self._referral()
        self.store.acknowledge_referral(
            "CASE-ALPHA", referral_id, actor_label=ACTOR, reason=ACK_REASON)
        self.store.record_referral_outcome(
            "CASE-ALPHA", referral_id, "accepted", OUTCOME_TEXT,
            self.path["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON)
        result = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-amended.txt"))
        self.assertEqual(result["invalidated_referrals"], [referral_id])
        item = self._view_referral(referral_id)
        self.assertEqual(item["current"]["review_state"], "needs_review")
        # The status and outcome stay visible; only review is refused.
        self.assertEqual(item["current"]["status"], "outcome_recorded")
        self.assertEqual(item["outcome"]["outcome_kind"], "accepted")
        with self.assertRaises(InvalidInput):
            self.store.review_referral(
                "CASE-ALPHA", referral_id, REVIEWER, REVIEW_SCOPE)

    def test_history_is_append_only(self):
        referral_id = self._referral()
        self.store.acknowledge_referral(
            "CASE-ALPHA", referral_id, actor_label=ACTOR, reason=ACK_REASON)
        before = self._view_referral(referral_id)["history"]
        self.store.record_referral_outcome(
            "CASE-ALPHA", referral_id, "declined", OUTCOME_TEXT,
            self.path["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON)
        after = self._view_referral(referral_id)["history"]
        self.assertEqual(len(after), 3)
        self.assertEqual(after[:2], before)
        self.assertEqual(after[2]["change_kind"], "outcome_recorded")

    def test_referrals_are_case_scoped(self):
        referral_id = self._referral()
        self.assertEqual(self.store.list_referrals("CASE-BETA")["referrals"], [])
        for call in (
                lambda: self.store.acknowledge_referral(
                    "CASE-BETA", referral_id, actor_label=ACTOR, reason=ACK_REASON),
                lambda: self.store.record_referral_outcome(
                    "CASE-BETA", referral_id, "accepted", OUTCOME_TEXT,
                    self.path["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON),
                lambda: self.store.review_referral(
                    "CASE-BETA", referral_id, REVIEWER, REVIEW_SCOPE),
        ):
            with self.subTest(call=call):
                with self.assertRaises(InvalidInput):
                    call()


class ReferralsViewTests(unittest.TestCase):
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

    def test_view_counts_statuses(self):
        first = create_referral(
            self.store, question_id=self.q, source_version_ids=[self.path["source_id"]])
        second = create_referral(
            self.store, question_id=self.q, source_version_ids=[self.path["source_id"]],
            specialty_label="neurology")
        third = create_referral(
            self.store, question_id=self.q, source_version_ids=[self.path["source_id"]],
            specialty_label="radiology")
        self.store.acknowledge_referral(
            "CASE-ALPHA", second, actor_label=ACTOR, reason=ACK_REASON)
        self.store.acknowledge_referral(
            "CASE-ALPHA", third, actor_label=ACTOR, reason=ACK_REASON)
        self.store.record_referral_outcome(
            "CASE-ALPHA", third, "completed", OUTCOME_TEXT,
            self.path["source_id"], actor_label=ACTOR, reason=OUTCOME_REASON)
        view = referrals_view(self.store, "CASE-ALPHA")
        self.assertEqual(view["counts"], {
            "requested": 1, "acknowledged": 1, "outcome_recorded": 1})
        self.assertEqual(view["case_id"], "CASE-ALPHA")
        self.assertTrue(view["synthetic"])
        self.assertEqual(
            [item["referral_id"] for item in view["referrals"]],
            [first, second, third])


class ReferralsHttpTests(unittest.TestCase):
    """The referral routes, served live like test_http.py."""

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

    def test_list_route_returns_referrals_and_empty_state(self):
        status, data = self.header_request("/api/cases/CASE-BETA/referrals")
        self.assertEqual(status, 200)
        self.assertEqual(data["case_id"], "CASE-BETA")
        self.assertEqual(data["referrals"], [])
        self.assertEqual(data["counts"], {
            "requested": 0, "acknowledged": 0, "outcome_recorded": 0})
        self.assertIn("Fictional referrals only", data["disclaimer"])

    def test_create_acknowledge_outcome_review_round_trip(self):
        question_id, source_id = self._seeded_question_and_source()
        status, body = self.header_request("/api/cases/CASE-ALPHA/referrals", {
            "question_id": question_id, "specialty_label": "cardiology",
            "reason_text": REASON, "source_version_ids": [source_id],
            "actor_label": ACTOR})
        self.assertEqual(status, 201, body)
        referral_id = body["referral_id"]
        # An outcome before acknowledgment is a 422 and writes nothing.
        status, body = self.header_request(
            f"/api/cases/CASE-ALPHA/referrals/{referral_id}/outcome", {
                "outcome_kind": "accepted", "outcome_text": OUTCOME_TEXT,
                "anchor_source_version_id": source_id,
                "actor_label": ACTOR, "reason": OUTCOME_REASON})
        self.assertEqual(status, 422)
        status, body = self.header_request(
            f"/api/cases/CASE-ALPHA/referrals/{referral_id}/acknowledge", {
                "actor_label": ACTOR, "reason": ACK_REASON})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["result"], "acknowledged")
        status, body = self.header_request(
            f"/api/cases/CASE-ALPHA/referrals/{referral_id}/outcome", {
                "outcome_kind": "accepted", "outcome_text": OUTCOME_TEXT,
                "anchor_source_version_id": source_id,
                "actor_label": ACTOR, "reason": OUTCOME_REASON})
        self.assertEqual(status, 201, body)
        outcome_id = body["outcome_id"]
        self.assertEqual(outcome_id, 1)
        status, body = self.header_request(
            f"/api/cases/CASE-ALPHA/referrals/{referral_id}/review", {
                "reviewer_label": REVIEWER, "scope": REVIEW_SCOPE})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["result"], "acknowledged_in_demo")
        status, data = self.header_request("/api/cases/CASE-ALPHA/referrals")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["referrals"]), 1)
        current = data["referrals"][0]["current"]
        self.assertEqual(current["status"], "outcome_recorded")
        self.assertEqual(current["review_state"], "reviewed_in_demo")
        self.assertEqual(data["referrals"][0]["outcome"]["outcome_kind"], "accepted")
        self.assertEqual(len(data["referrals"][0]["history"]), 3)
        # A bad create is a 422 and writes nothing.
        status, body = self.header_request("/api/cases/CASE-ALPHA/referrals", {
            "question_id": question_id, "specialty_label": "cardiology",
            "reason_text": "too short", "source_version_ids": [source_id],
            "actor_label": ACTOR})
        self.assertEqual(status, 422)
        status, data = self.header_request("/api/cases/CASE-ALPHA/referrals")
        self.assertEqual(len(data["referrals"]), 1)

    def test_routes_require_a_grant(self):
        question_id, source_id = self._seeded_question_and_source()
        for path, data in (
                ("/api/cases/CASE-ALPHA/referrals", None),
                ("/api/cases/CASE-ALPHA/referrals", {
                    "question_id": question_id, "specialty_label": "cardiology",
                    "reason_text": REASON, "source_version_ids": [source_id],
                    "actor_label": ACTOR}),
        ):
            with self.subTest(path=path, data=data is not None):
                status, body = self.request(path, data)
                self.assertEqual(status, 403)
                self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})

    def test_role_gates_patient_reads_own_case_only_and_never_writes(self):
        patient = self.signin(PATIENT)
        status, data = self.request("/api/cases/CASE-ALPHA/referrals", cookie=patient)
        self.assertEqual(status, 200)
        status, body = self.request("/api/cases/CASE-BETA/referrals", cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        # Patient writes are denied by role even on their own case.
        question_id, source_id = self._seeded_question_and_source()
        status, body = self.request("/api/cases/CASE-ALPHA/referrals", {
            "question_id": question_id, "specialty_label": "cardiology",
            "reason_text": REASON, "source_version_ids": [source_id],
            "actor_label": ACTOR}, cookie=patient)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": ROLE_DENIAL_MESSAGE})
        # Auditor holds no case grants: the grant gate denies case routes.
        auditor = self.signin(AUDITOR)
        status, body = self.request("/api/cases/CASE-ALPHA/referrals", cookie=auditor)
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        # Unauthenticated case routes are denied.
        status, body = self.request("/api/cases/CASE-ALPHA/referrals")
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})


class NoModelCallTests(unittest.TestCase):
    def test_module_has_no_model_call_and_no_dimension_import(self):
        # D8 is deterministic code over the ledger: it never calls a
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
        tree = ast.parse((SRC / "referrals.py").read_text())
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
