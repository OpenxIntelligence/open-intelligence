"""Actual PG16/HTTP: canonical review disclosure stays inside source authority.

The original encoders still produce real JSON bytes before each injected effect.
Both FastAPI's typed-response fast path and the prepared JSONResponse path are
observed, so a missed encoder cannot make an authority regression pass. Fixtures
are independently fictional; only the fixture without test methods is inherited.
"""
import copy
from contextlib import contextmanager
from dataclasses import dataclass, replace
import json
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from fastapi import routing as fastapi_routing
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.app import create_app
from http_support import running_server
from test_canonical_review_flow import RETURN_REASON, create_question
from test_patients import TOKEN_A
from test_source_versions import AMENDED, SourceVersionFixture


QUEUE_CONTRACT = "oi.synthetic-question-review-return-queue/2"
PRIVATE_FAILURE = "PRIVATE-REVIEW-JSON-ENCODING"


@dataclass(frozen=True)
class ReviewOperation:
    name: str
    patient_id: str
    question_id: str
    path: str
    body: dict | None
    status: int
    duplicate: bool | None = None
    receipt_id: str | None = None


def review_request(base, operation):
    """Read actual HTTP, including an unfixed encoder's non-JSON 500 response."""
    headers = {"Authorization": "Bearer " + TOKEN_A}
    raw = None
    if operation.body is not None:
        headers["Content-Type"] = "application/json"
        raw = json.dumps(operation.body).encode()
    try:
        reply = build_opener(ProxyHandler({})).open(
            Request(base + operation.path, headers=headers, data=raw), timeout=8,
        )
    except HTTPError as error:
        reply = error
    with reply:
        raw = reply.read()
        try:
            body = json.loads(raw)
        except ValueError:
            body = raw.decode("utf-8", errors="replace")
        return reply.status, body, reply.headers


@contextmanager
def observe_review_json_encoding(effect):
    """Observe complete review JSON on either real framework encoding path.

    A typed DTO uses Pydantic dump_json and bypasses JSONResponse.render. A
    prepared response uses JSONResponse.render and bypasses serialize_response.
    Invoke each original encoder first and ignore errors and unrelated payloads.
    Callers require exactly one observation of their expected review payload.
    """
    original_render = JSONResponse.render
    original_serialize = fastapi_routing.serialize_response

    def observe(encoded):
        if not isinstance(encoded, (bytes, str)):
            return
        envelope = json.loads(encoded)
        if isinstance(envelope, dict) and (
                envelope.get("contract") == QUEUE_CONTRACT or
                {"receipt_id", "question_id", "duplicate"} <= envelope.keys()):
            effect(encoded)

    async def serialize(*args, **kwargs):
        encoded = await original_serialize(*args, **kwargs)
        if kwargs.get("dump_json") is True:
            observe(encoded)
        return encoded

    def render(response, content):
        encoded = original_render(response, content)
        observe(encoded)
        return encoded

    with patch.object(fastapi_routing, "serialize_response", serialize), \
            patch.object(JSONResponse, "render", render):
        yield


class ReviewDisclosureAuthorityTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "review_queue_read", "review_return",
        ))
        self.write()
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalars().all(), ["0008_review_convergence"])

    def persisted_state(self):
        """Include every return and event, including source access receipts."""
        with self.engine.connect() as connection:
            return {
                "returns": [dict(row) for row in connection.execute(text(
                    "SELECT * FROM investigation.question_review_receipts "
                    "ORDER BY receipt_id"
                )).mappings()],
                "events": [dict(row) for row in connection.execute(text(
                    "SELECT * FROM identity.identity_domain_events ORDER BY id"
                )).mappings()],
            }

    def operations(self, base):
        """Yield both current responses and exact-intent historical recovery."""
        patient = self.setup_case(base)
        status, source, _ = self.ingest(base, patient)
        self.assertEqual(status, 201, source)
        question, _ = create_question(self, base, patient, source["source_id"])
        prefix = f"/v1/patients/{patient}/cases/CASE-ALPHA"
        queue = ReviewOperation("queue", patient, question,
                                prefix + "/review-queue", None, 200)
        status, inbox, _ = review_request(base, queue)
        self.assertEqual(status, 200, inbox)
        self.assertEqual(len(inbox["items"]), 1)
        fingerprint = inbox["items"][0]["queue_fingerprint"]
        self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")
        intent = {"synthetic": True, "request_key": "REVIEW-JSON-RECORDED",
                  "expected_queue_fingerprint": fingerprint, "reason": RETURN_REASON}
        original = ReviewOperation(
            "new_return", patient, question,
            prefix + f"/questions/{question}/return-for-verification",
            intent, 201, False,
        )
        status, recorded, _ = review_request(base, original)
        self.assertEqual((status, recorded["duplicate"]), (201, False))
        receipt = recorded["receipt_id"]
        duplicate = replace(original, name="duplicate_return", status=200,
                            duplicate=True, receipt_id=receipt)
        yield queue
        yield replace(original, body={**intent, "request_key": "REVIEW-JSON-NEW"})
        yield duplicate

        status, amended, _ = self.ingest(base, patient, AMENDED)
        self.assertEqual(status, 201, amended)
        status, historical, _ = review_request(base, queue)
        self.assertEqual(status, 200, historical)
        item = historical["items"][0]
        self.assertEqual(item["question_id"], question)
        self.assertEqual(item["source_id"], source["source_id"])
        self.assertEqual(item["review_state"], "source_reassessment_required")
        self.assertIsNone(item["queue_fingerprint"])
        self.assertIsNone(item["current_return_receipt_id"])
        self.assertIn(receipt, [entry["receipt_id"] for entry in historical["receipts"]])
        yield replace(duplicate, name="post_amendment_retry")

    def assert_encoded_once(self, observed, operation):
        self.assertEqual(len(observed), 1, "The real review encoder must run exactly once")
        envelope = json.loads(observed[0])
        if operation.name == "queue":
            self.assertEqual(envelope["contract"], QUEUE_CONTRACT)
            self.assertEqual(envelope["patient_id"], operation.patient_id)
            self.assertEqual(envelope["items"][0]["question_id"], operation.question_id)
            self.assertRegex(envelope["access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
        else:
            self.assertEqual(set(envelope), {"receipt_id", "question_id", "duplicate"})
            self.assertEqual(envelope["question_id"], operation.question_id)
            self.assertIs(envelope["duplicate"], operation.duplicate)
            self.assertRegex(envelope["receipt_id"], r"^REVIEW-[0-9A-F]{32}$")
            if operation.receipt_id is not None:
                self.assertEqual(envelope["receipt_id"], operation.receipt_id)
        return envelope

    def assert_withheld(self, response, status, before, operation):
        self.assertEqual(response[0], status, response[1])
        self.assertIsInstance(response[1], dict)
        self.assertEqual(set(response[1]), {"detail"})
        self.assertEqual(response[2]["Cache-Control"], "no-store")
        self.assertNotIn("X-OI-Access-Receipt", response[2])
        for private in (TOKEN_A, RETURN_REASON, PRIVATE_FAILURE,
                        operation.patient_id, operation.question_id):
            self.assertNotIn(private, json.dumps(response[1]))
        if status == 503:
            self.assertEqual(response[1], {"detail": "Patient registry unavailable"})
        self.assertEqual(self.persisted_state(), before)

    def assert_success(self, response, operation, before, encoded):
        self.assertEqual(response[0], operation.status, response[1])
        self.assertEqual(response[1], encoded)
        self.assertEqual(response[2]["Cache-Control"], "no-store")
        after = self.persisted_state()
        is_new = operation.name == "new_return"
        self.assertEqual(len(after["returns"]), len(before["returns"]) + int(is_new))
        events = after["events"][len(before["events"]):]
        self.assertEqual([event["event_type"] for event in events],
                         (["investigation.review.returned_for_verification"] if is_new else [])
                         + ["source.read_authorized"])
        if operation.name == "queue":
            self.assertEqual(events[-1]["metadata_json"]["receipt_id"],
                             encoded["access_receipt_id"])
        else:
            self.assertIn(encoded["receipt_id"], [row["receipt_id"] for row in after["returns"]])

    def test_encoding_time_grant_or_actor_change_withholds_all_review_responses(self):
        with running_server(create_app(self.settings)) as base:
            for operation in self.operations(base):
                action = "review_queue_read" if operation.name == "queue" else "review_return"
                initial = copy.deepcopy(self.creds)
                for change in ("patient_read", "source_read", "question_read", action, "actor"):
                    with self.subTest(operation=operation.name, change=change):
                        # A broken baseline must not turn a later attempted new
                        # return into a duplicate and hide the response at issue.
                        attempted = operation
                        if operation.name == "new_return":
                            attempted = replace(operation, body={
                                **operation.body, "request_key": "REVIEW-JSON-NEW-" + change.upper(),
                            })
                        before = self.persisted_state()
                        observed = []

                        def withdraw(encoded):
                            observed.append(encoded)
                            if change == "actor":
                                self.creds[0]["actor"] = "ACTOR-CHANGED-DURING-ENCODING"
                            else:
                                self.creds[0]["actions"].remove(change)
                            self.write()

                        try:
                            with observe_review_json_encoding(withdraw):
                                response = review_request(base, attempted)
                        finally:
                            self.creds = copy.deepcopy(initial)
                            self.write()
                        self.assert_encoded_once(observed, attempted)
                        self.assert_withheld(response, 404, before, attempted)

    def test_real_encoding_failure_returns_sanitized_503_and_rolls_back(self):
        with running_server(create_app(self.settings)) as base:
            for operation in self.operations(base):
                with self.subTest(operation=operation.name):
                    before = self.persisted_state()
                    observed = []

                    def fail(encoded):
                        observed.append(encoded)
                        raise RuntimeError(PRIVATE_FAILURE)

                    with observe_review_json_encoding(fail):
                        response = review_request(base, operation)
                    self.assert_encoded_once(observed, operation)
                    self.assert_withheld(response, 503, before, operation)

    def test_patient_case_locks_and_uncommitted_effects_cover_actual_encoding(self):
        with running_server(create_app(self.settings)) as base:
            for operation in self.operations(base):
                with self.subTest(operation=operation.name):
                    before = self.persisted_state()
                    observed = []
                    during = {}

                    def inspect(encoded):
                        observed.append(encoded)
                        during["state"] = self.persisted_state()
                        during["locks"] = []
                        for sql, params in (
                            ("SELECT patient_id FROM identity.identity_patients "
                             "WHERE patient_id=:patient FOR UPDATE NOWAIT",
                             {"patient": operation.patient_id}),
                            ("SELECT case_id FROM coordination.patient_case_bindings "
                             "WHERE patient_id=:patient AND case_id=:case FOR UPDATE NOWAIT",
                             {"patient": operation.patient_id, "case": "CASE-ALPHA"}),
                        ):
                            with self.engine.connect() as connection:
                                try:
                                    connection.execute(text(sql), params).scalar_one()
                                except DBAPIError as error:
                                    details = error.orig.args[0] if error.orig.args else None
                                    during["locks"].append(
                                        details.get("C") if isinstance(details, dict) else None)
                                else:
                                    during["locks"].append("acquired")

                    with observe_review_json_encoding(inspect):
                        response = review_request(base, operation)
                    envelope = self.assert_encoded_once(observed, operation)
                    self.assertEqual(during["state"], before)
                    self.assertEqual(during["locks"], ["55P03", "55P03"])
                    self.assert_success(response, operation, before, envelope)

    def test_deferred_commit_failure_withholds_encoded_body_and_rolls_back(self):
        with running_server(create_app(self.settings)) as base:
            for operation in self.operations(base):
                with self.subTest(operation=operation.name):
                    before = self.persisted_state()
                    with self.engine.begin() as connection:
                        connection.exec_driver_sql("""
                            CREATE FUNCTION identity.reject_review_disclosure_commit()
                            RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
                            IF NEW.event_type='source.read_authorized' THEN
                                RAISE EXCEPTION 'PRIVATE-REVIEW-JSON-ENCODING';
                            END IF;
                            RETURN NEW; END; $$;
                        """)
                        connection.exec_driver_sql("""
                            CREATE CONSTRAINT TRIGGER reject_review_disclosure_commit
                            AFTER INSERT ON identity.identity_domain_events
                            DEFERRABLE INITIALLY DEFERRED
                            FOR EACH ROW EXECUTE FUNCTION identity.reject_review_disclosure_commit()
                        """)
                    try:
                        observed = []
                        with observe_review_json_encoding(observed.append):
                            response = review_request(base, operation)
                        self.assert_encoded_once(observed, operation)
                        self.assert_withheld(response, 503, before, operation)
                    finally:
                        # Drop before the fixture removes the identity schema;
                        # also keep amendment setup outside the injected failure.
                        with self.engine.begin() as connection:
                            connection.exec_driver_sql(
                                "DROP TRIGGER IF EXISTS reject_review_disclosure_commit "
                                "ON identity.identity_domain_events")
                            connection.exec_driver_sql(
                                "DROP FUNCTION IF EXISTS identity.reject_review_disclosure_commit()")

                    # The same intent remains usable after rollback. A new return
                    # still gets 201, then recovers its one durable receipt at 200.
                    observed = []
                    with observe_review_json_encoding(observed.append):
                        recovered = review_request(base, operation)
                    envelope = self.assert_encoded_once(observed, operation)
                    self.assert_success(recovered, operation, before, envelope)
                    if operation.name == "new_return":
                        repeated = review_request(base, operation)
                        self.assertEqual(repeated[0], 200, repeated[1])
                        self.assertEqual(repeated[1], {**envelope, "duplicate": True})
