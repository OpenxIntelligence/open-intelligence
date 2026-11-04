"""Actual PG16/HTTP authority for complete question-packet JSON disclosure.

Only SourceVersionFixture is inherited, so upstream test methods are not run
again. The original FastAPI/Starlette encoders still create actual JSON bytes
before the injected effects. Observing both supported encoding paths prevents
an untouched typed-response fast path from making these checks falsely pass.
All records and credentials are independently authored fictional fixtures.
"""
import copy
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
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
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


PACKET_CONTRACT = "oi.synthetic-question-source-review-packet/1"
PRIVATE_FAILURE = "PRIVATE-QUESTION-PACKET-ENCODING"
QUESTION_TEXT = "Which independently fictional source details require verification?"
SOURCE_QUOTE = "Fictional café <script>literal</script>."


@dataclass(frozen=True)
class PacketRead:
    patient_id: str
    source_id: str
    question_id: str
    path: str


def packet_request(base, operation):
    """Read real HTTP, retaining an unfixed encoder's non-JSON failure body."""
    try:
        reply = build_opener(ProxyHandler({})).open(Request(
            base + operation.path,
            headers={"Authorization": "Bearer " + TOKEN_A},
        ), timeout=8)
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
def observe_packet_json_encoding(effect):
    """Inject only after the real selected packet encoder produced its bytes.

    The typed DTO path uses serialize_response(dump_json=True) and bypasses
    JSONResponse.render. A prepared response does the reverse. Unrelated
    responses and sanitized error envelopes must not activate the injection.
    Every test requires exactly one complete packet observation.
    """
    original_render = JSONResponse.render
    original_serialize = fastapi_routing.serialize_response

    def observe(encoded):
        if not isinstance(encoded, (bytes, str)):
            return
        envelope = json.loads(encoded)
        if isinstance(envelope, dict) and envelope.get("contract") == PACKET_CONTRACT:
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


class QuestionPacketDisclosureAuthorityTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "review_packet_read", "review_queue_read", "review_return",
        ))
        self.write()

    def saved_packet(self, base):
        patient = self.setup_case(base)
        status, source, _ = self.ingest(base, patient)
        self.assertEqual(status, 201, source)
        question, _ = create_question(self, base, patient, source["source_id"])
        return PacketRead(
            patient, source["source_id"], question,
            f"/v1/patients/{patient}/cases/CASE-ALPHA/questions/"
            f"{question}/source-review-packet",
        )

    def persisted_state(self):
        """Compare real owner rows, not an event count that could hide mutation."""
        queries = {
            "sources": "SELECT * FROM clinical_source.source_versions ORDER BY source_id",
            "assertions": "SELECT * FROM clinical_source.assertions ORDER BY assertion_id",
            "questions": "SELECT * FROM investigation.source_questions ORDER BY question_id",
            "returns": "SELECT * FROM investigation.question_review_receipts ORDER BY receipt_id",
            "events": "SELECT * FROM identity.identity_domain_events ORDER BY id",
        }
        with self.engine.connect() as connection:
            return {key: [dict(row) for row in connection.execute(text(sql)).mappings()]
                    for key, sql in queries.items()}

    def assert_encoded_once(self, observed, operation):
        self.assertEqual(len(observed), 1, "The actual packet encoder must run exactly once")
        packet = json.loads(observed[0])
        self.assertEqual(packet["contract"], PACKET_CONTRACT)
        self.assertEqual((packet["patient_id"], packet["case_id"], packet["question_id"]),
                         (operation.patient_id, "CASE-ALPHA", operation.question_id))
        self.assertEqual(packet["question"], QUESTION_TEXT)
        self.assertEqual(packet["selected_statement"]["source_id"], operation.source_id)
        self.assertEqual(packet["selected_statement"]["source_statement"], SOURCE_QUOTE)
        self.assertRegex(packet["source_access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
        return packet

    def assert_withheld(self, response, expected_status, before, operation):
        self.assertEqual(response[0], expected_status, response[1])
        self.assertIsInstance(response[1], dict)
        self.assertEqual(set(response[1]), {"detail"})
        self.assertEqual(response[2]["Cache-Control"], "no-store")
        self.assertNotIn("X-OI-Access-Receipt", response[2])
        for private in (TOKEN_A, PRIVATE_FAILURE, QUESTION_TEXT, SOURCE_QUOTE,
                        operation.patient_id, operation.source_id, operation.question_id):
            self.assertNotIn(private, json.dumps(response[1], ensure_ascii=False))
        if expected_status == 503:
            self.assertEqual(response[1], {"detail": "Patient registry unavailable"})
        self.assertEqual(self.persisted_state(), before)

    def assert_success(self, response, before, packet):
        self.assertEqual(response[0], 200, response[1])
        self.assertEqual(response[1], packet)
        self.assertEqual(response[2]["Cache-Control"], "no-store")
        self.assertTrue(response[2]["Content-Type"].startswith("application/json"))
        after = self.persisted_state()
        for owner in ("sources", "assertions", "questions", "returns"):
            self.assertEqual(after[owner], before[owner], owner)
        self.assertEqual(after["events"][:len(before["events"])], before["events"])
        added = after["events"][len(before["events"]):]
        self.assertEqual([event["event_type"] for event in added], ["source.read_authorized"])
        self.assertEqual(added[0]["metadata_json"]["receipt_id"],
                         packet["source_access_receipt_id"])

    @contextmanager
    def failing_receipt_write(self, *, deferred):
        """Fail the actual DB insert or deferred commit in the owned test DB."""
        with self.engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE FUNCTION identity.reject_question_packet_receipt()
                RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
                IF NEW.event_type='source.read_authorized' THEN
                    RAISE EXCEPTION 'PRIVATE-QUESTION-PACKET-ENCODING';
                END IF;
                RETURN NEW; END; $$;
            """)
            if deferred:
                connection.exec_driver_sql("""
                    CREATE CONSTRAINT TRIGGER reject_question_packet_receipt
                    AFTER INSERT ON identity.identity_domain_events
                    DEFERRABLE INITIALLY DEFERRED
                    FOR EACH ROW EXECUTE FUNCTION identity.reject_question_packet_receipt()
                """)
            else:
                connection.exec_driver_sql("""
                    CREATE TRIGGER reject_question_packet_receipt
                    BEFORE INSERT ON identity.identity_domain_events
                    FOR EACH ROW EXECUTE FUNCTION identity.reject_question_packet_receipt()
                """)
        try:
            yield
        finally:
            with self.engine.begin() as connection:
                connection.exec_driver_sql(
                    "DROP TRIGGER IF EXISTS reject_question_packet_receipt "
                    "ON identity.identity_domain_events")
                connection.exec_driver_sql(
                    "DROP FUNCTION IF EXISTS identity.reject_question_packet_receipt()")

    def test_encoding_time_independent_grant_withdrawal_withholds_packet(self):
        with running_server(create_app(self.settings)) as base:
            operation = self.saved_packet(base)
            initial = copy.deepcopy(self.creds)
            for action in ("patient_read", "source_read", "question_read", "review_packet_read"):
                with self.subTest(action=action):
                    before = self.persisted_state()
                    observed = []

                    def withdraw(encoded):
                        observed.append(encoded)
                        self.creds[0]["actions"].remove(action)
                        self.write()

                    try:
                        with observe_packet_json_encoding(withdraw):
                            response = packet_request(base, operation)
                    finally:
                        self.creds = copy.deepcopy(initial)
                        self.write()
                    self.assert_encoded_once(observed, operation)
                    self.assert_withheld(response, 404, before, operation)

    def test_encoding_time_identity_purpose_scope_or_expiry_change_withholds_packet(self):
        with running_server(create_app(self.settings)) as base:
            operation = self.saved_packet(base)
            initial = copy.deepcopy(self.creds)
            for field, value, expected_status in (
                ("actor", "ACTOR-CHANGED-DURING-ENCODING", 404),
                ("organization", "ORG-CHANGED-DURING-ENCODING", 404),
                ("purpose", "research", 404),
                ("patient_ids", [], 404),
                ("expires_at", "2000-01-01T00:00:00+00:00", 401),
            ):
                with self.subTest(field=field):
                    before = self.persisted_state()
                    observed = []

                    def change(encoded):
                        observed.append(encoded)
                        self.creds[0][field] = value
                        self.write()

                    try:
                        with observe_packet_json_encoding(change):
                            response = packet_request(base, operation)
                    finally:
                        self.creds = copy.deepcopy(initial)
                        self.write()
                    self.assert_encoded_once(observed, operation)
                    self.assert_withheld(response, expected_status, before, operation)

    def test_actual_encoder_failure_is_sanitized_and_leaves_no_success_receipt(self):
        with running_server(create_app(self.settings)) as base:
            operation = self.saved_packet(base)
            before = self.persisted_state()
            observed = []

            def fail(encoded):
                observed.append(encoded)
                raise RuntimeError(PRIVATE_FAILURE)

            with observe_packet_json_encoding(fail):
                response = packet_request(base, operation)
            self.assert_encoded_once(observed, operation)
            self.assert_withheld(response, 503, before, operation)

    def test_owner_locks_and_uncommitted_receipt_cover_actual_json_encoding(self):
        with running_server(create_app(self.settings)) as base:
            operation = self.saved_packet(base)
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

            with observe_packet_json_encoding(inspect):
                response = packet_request(base, operation)
            packet = self.assert_encoded_once(observed, operation)
            self.assertEqual(during["state"], before)
            self.assertEqual(during["locks"], ["55P03", "55P03"])
            self.assert_success(response, before, packet)

    def test_real_audit_insert_failure_withholds_prepared_packet(self):
        with running_server(create_app(self.settings)) as base:
            operation = self.saved_packet(base)
            before = self.persisted_state()
            observed = []
            with self.failing_receipt_write(deferred=False):
                with observe_packet_json_encoding(observed.append):
                    response = packet_request(base, operation)
                self.assert_encoded_once(observed, operation)
                self.assert_withheld(response, 503, before, operation)

            observed = []
            with observe_packet_json_encoding(observed.append):
                recovered = packet_request(base, operation)
            self.assert_success(recovered, before, self.assert_encoded_once(observed, operation))

    def test_real_deferred_commit_failure_withholds_encoded_packet_and_allows_fresh_retry(self):
        with running_server(create_app(self.settings)) as base:
            operation = self.saved_packet(base)
            before = self.persisted_state()
            observed = []
            with self.failing_receipt_write(deferred=True):
                with observe_packet_json_encoding(observed.append):
                    response = packet_request(base, operation)
                self.assert_encoded_once(observed, operation)
                self.assert_withheld(response, 503, before, operation)

            observed = []
            with observe_packet_json_encoding(observed.append):
                recovered = packet_request(base, operation)
            self.assert_success(recovered, before, self.assert_encoded_once(observed, operation))

    def test_successful_packet_reads_preserve_questions_returns_and_originals_across_restart(self):
        with running_server(create_app(self.settings)) as base:
            operation = self.saved_packet(base)
            prefix = f"/v1/patients/{operation.patient_id}/cases/CASE-ALPHA"
            status, queue, _ = request(base, prefix + "/review-queue", token=TOKEN_A)
            self.assertEqual(status, 200, queue)
            status, returned, _ = request(
                base, prefix + f"/questions/{operation.question_id}/return-for-verification",
                token=TOKEN_A, body={"synthetic": True, "request_key": "PACKET-EXISTING-RETURN",
                                    "expected_queue_fingerprint": queue["items"][0]["queue_fingerprint"],
                                    "reason": RETURN_REASON},
            )
            self.assertEqual(status, 201, returned)
            self.assertFalse(returned["duplicate"])
            before = self.persisted_state()
            observed = []
            with observe_packet_json_encoding(observed.append):
                response = packet_request(base, operation)
            first = self.assert_encoded_once(observed, operation)
            self.assert_success(response, before, first)
            for flag in ("clinical_approval", "clinical_review_connected",
                         "medical_interpretation_performed", "reviewer_identity_verified",
                         "published_evidence_rights_verified", "external_biomedical_evidence_qualified"):
                self.assertIs(first[flag], False, flag)
            self.assertEqual(first["selected_statement"]["review_state"], "not_established")
            self.assertIsNone(first["selected_statement"]["clinical_meaning"])
            self.assertEqual(first["selected_statement"]["source_line"], 8)
            self.assertEqual(first["selected_statement"]["document_version"], 1)
            stable = {key: value for key, value in first.items()
                      if key not in {"packet_sha256", "source_access_receipt_id"}}
            digest = hashlib.sha256(json.dumps(
                stable, sort_keys=True, ensure_ascii=False,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")).hexdigest()
            self.assertEqual(first["packet_sha256"], digest)

        with running_server(create_app(self.settings)) as restarted:
            before = self.persisted_state()
            observed = []
            with observe_packet_json_encoding(observed.append):
                response = packet_request(restarted, operation)
            second = self.assert_encoded_once(observed, operation)
            self.assert_success(response, before, second)
            self.assertEqual(second["packet_sha256"], first["packet_sha256"])
            self.assertNotEqual(second["source_access_receipt_id"], first["source_access_receipt_id"])
