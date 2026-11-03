"""Real PG16/HTTP packet disclosure must prepare JSON under source authority.

Public Pydantic and JSONResponse encoders run normally before scoped effects.
The same assertions cover the inherited typed FastAPI response and the prepared
response correction. Only the fixture without runnable test methods is reused;
all patient, source and question input is independently fictional.
"""
import copy
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from fastapi.responses import JSONResponse
from pydantic import TypeAdapter
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.app import create_app
from http_support import running_server
from test_canonical_review_flow import create_question
from test_patients import TOKEN_A
from test_source_versions import AMENDED, ORIGINAL, SourceVersionFixture


PACKET_CONTRACT = "oi.synthetic-question-source-review-packet/1"
PRIVATE_FAILURE = "PRIVATE-PACKET-JSON-ENCODING"


@dataclass(frozen=True)
class PacketOperation:
    patient_id: str
    question_id: str
    source_id: str
    snapshot: str

    @property
    def path(self):
        return (f"/v1/patients/{self.patient_id}/cases/CASE-ALPHA/questions/"
                f"{self.question_id}/source-review-packet")


def packet_request(base, operation):
    """Keep non-JSON failures readable without masking durable state checks."""
    try:
        reply = build_opener(ProxyHandler({})).open(Request(
            base + operation.path, headers={"Authorization": "Bearer " + TOKEN_A},
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
    """Observe actual complete bytes exactly once on either encoding path."""
    original_dump_json = TypeAdapter.dump_json
    original_render = JSONResponse.render

    def observe(encoded):
        envelope = json.loads(encoded)
        if isinstance(envelope, dict) and envelope.get("contract") == PACKET_CONTRACT:
            effect(encoded)

    def dump_json(adapter, content, *args, **kwargs):
        encoded = original_dump_json(adapter, content, *args, **kwargs)
        observe(encoded)
        return encoded

    def render(response, content):
        encoded = original_render(response, content)
        observe(encoded)
        return encoded

    with patch.object(TypeAdapter, "dump_json", dump_json), \
            patch.object(JSONResponse, "render", render):
        yield


class PacketDisclosureAuthorityTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "review_packet_read",
        ))
        self.write()

    def operation(self, base):
        patient = self.setup_case(base)
        status, source, _ = self.ingest(base, patient)
        self.assertEqual(status, 201, source)
        question, snapshot = create_question(self, base, patient, source["source_id"])
        return PacketOperation(patient, question, source["source_id"], snapshot)

    def persisted_state(self):
        """Read committed rows using an independent connection, never HTTP."""
        with self.engine.connect() as connection:
            return {
                name: [dict(row) for row in connection.execute(text(sql)).mappings()]
                for name, sql in (
                    ("events", "SELECT * FROM identity.identity_domain_events ORDER BY id"),
                    ("questions", "SELECT * FROM investigation.source_questions ORDER BY question_id"),
                    ("returns", "SELECT * FROM investigation.question_review_receipts ORDER BY receipt_id"),
                    ("sources", "SELECT * FROM clinical_source.source_versions ORDER BY source_id"),
                    ("assertions", "SELECT * FROM clinical_source.assertions ORDER BY assertion_id"),
                )
            }

    def change_authority(self, change):
        if change.startswith("grant:"):
            self.creds[0]["actions"].remove(change.partition(":")[2])
        elif change == "patient":
            self.creds[0]["patient_ids"] = []
        elif change == "actor":
            self.creds[0]["actor"] = "ACTOR-CHANGED-DURING-PACKET-ENCODING"
        elif change == "organization":
            self.creds[0]["organization"] = "ORG-CHANGED-DURING-PACKET-ENCODING"
        elif change == "purpose":
            self.creds[0]["purpose"] = "research"
        elif change == "expired":
            self.creds[0]["expires_at"] = (
                datetime.now(timezone.utc) - timedelta(minutes=1)
            ).isoformat()
        elif change == "revoked":
            self.creds.clear()
        elif change == "provider":
            self.access.write_text(PRIVATE_FAILURE)
            return
        else:
            raise AssertionError("Unknown packet authority change")
        self.write()

    def assert_encoded_once(self, observed, operation, *, historical=False):
        self.assertEqual(len(observed), 1, "The actual packet encoder must run exactly once")
        envelope = json.loads(observed[0])
        self.assertEqual(envelope["contract"], PACKET_CONTRACT)
        self.assertEqual((envelope["patient_id"], envelope["case_id"], envelope["question_id"]),
                         (operation.patient_id, "CASE-ALPHA", operation.question_id))
        self.assertEqual(envelope["question"],
                         "Which independently fictional source details require verification?")
        anchor = envelope["original_anchor"]
        self.assertEqual((anchor["source_id"], anchor["source_line"], anchor["source_version"]),
                         (operation.source_id, 8, 1))
        self.assertEqual(anchor["source_sha256"], hashlib.sha256(ORIGINAL.encode()).hexdigest())
        self.assertEqual(anchor["source_snapshot_sha256"], operation.snapshot)
        self.assertEqual(anchor["source_snapshot_contract"], "oi.pg-source-world-model/1")
        self.assertRegex(envelope["source_access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
        self.assertFalse(envelope["clinical_approval"])
        self.assertFalse(envelope["clinical_review_connected"])
        if historical:
            self.assertEqual(envelope["source_context_state"], "source_reassessment_required")
            self.assertIsNone(envelope["selected_statement"])
        else:
            self.assertEqual(envelope["source_context_state"], "current_unreviewed_source")
            selected = envelope["selected_statement"]
            self.assertEqual((selected["source_id"], selected["source_line"],
                              selected["document_version"], selected["source_sha256"]),
                             (operation.source_id, 8, 1, anchor["source_sha256"]))
            self.assertEqual(selected["source_statement"],
                             "Fictional café <script>literal</script>.")
        return envelope

    def assert_withheld(self, response, expected, before, operation):
        # Evaluate persistence first even if status/body assertions expose a
        # regression; parsing a success or plaintext 500 cannot hide a commit.
        unchanged = self.persisted_state() == before
        self.assertEqual((response[0], unchanged), (expected, True), response[1])
        self.assertIsInstance(response[1], dict)
        self.assertEqual(set(response[1]), {"detail"})
        self.assertEqual(response[2]["Cache-Control"], "no-store")
        self.assertNotIn("X-OI-Access-Receipt", response[2])
        for private in (TOKEN_A, PRIVATE_FAILURE, operation.patient_id,
                        operation.question_id, operation.source_id, "Fictional café"):
            self.assertNotIn(private, json.dumps(response[1], ensure_ascii=False))
        if expected == 503:
            self.assertIn(response[1]["detail"],
                          ("Patient registry unavailable", "Access service unavailable"))

    def assert_success(self, response, before, envelope):
        self.assertEqual(response[0], 200, response[1])
        self.assertEqual(response[1], envelope)
        self.assertEqual(response[2]["Cache-Control"], "no-store")
        after = self.persisted_state()
        events = after.pop("events")
        prior_events = before["events"]
        self.assertEqual(events[:len(prior_events)], prior_events)
        new = events[len(prior_events):]
        self.assertEqual([event["event_type"] for event in new], ["source.read_authorized"])
        self.assertEqual(new[0]["metadata_json"]["receipt_id"],
                         envelope["source_access_receipt_id"])
        self.assertEqual(after, {key: value for key, value in before.items() if key != "events"})

    def test_independent_grants_identity_expiry_and_provider_change_during_encoding(self):
        changes = [("grant:" + action, 404) for action in (
            "patient_read", "question_read", "source_read", "review_packet_read",
        )] + [("patient", 404), ("actor", 404), ("organization", 404),
             ("purpose", 404), ("expired", 401), ("revoked", 401), ("provider", 503)]
        with running_server(create_app(self.settings)) as base:
            operation = self.operation(base)
            initial = copy.deepcopy(self.creds)
            for change, expected in changes:
                with self.subTest(change=change):
                    before = self.persisted_state()
                    observed = []

                    def withdraw(encoded):
                        observed.append(encoded)
                        self.change_authority(change)

                    try:
                        with observe_packet_json_encoding(withdraw):
                            response = packet_request(base, operation)
                    finally:
                        self.creds = copy.deepcopy(initial)
                        self.write()
                    self.assert_withheld(response, expected, before, operation)
                    self.assert_encoded_once(observed, operation)
                    # Restored authority discloses the original exact anchor.
                    observed = []
                    with observe_packet_json_encoding(observed.append):
                        restored = packet_request(base, operation)
                    envelope = self.assert_encoded_once(observed, operation)
                    self.assert_success(restored, before, envelope)

    def test_real_encoder_failure_withholds_packet_and_rolls_back_receipt(self):
        with running_server(create_app(self.settings)) as base:
            operation = self.operation(base)
            before = self.persisted_state()
            observed = []

            def fail(encoded):
                observed.append(encoded)
                raise RuntimeError(PRIVATE_FAILURE)

            with observe_packet_json_encoding(fail):
                response = packet_request(base, operation)
            self.assert_withheld(response, 503, before, operation)
            self.assert_encoded_once(observed, operation)
            observed = []
            with observe_packet_json_encoding(observed.append):
                recovered = packet_request(base, operation)
            envelope = self.assert_encoded_once(observed, operation)
            self.assert_success(recovered, before, envelope)

    def test_owner_locks_and_uncommitted_event_cover_current_and_historical_json(self):
        with running_server(create_app(self.settings)) as base:
            operation = self.operation(base)
            for historical in (False, True):
                with self.subTest(historical=historical):
                    if historical:
                        self.assertEqual(self.ingest(base, operation.patient_id, AMENDED)[0], 201)
                    before = self.persisted_state()
                    observed = []
                    during = {}

                    def inspect(encoded):
                        observed.append(encoded)
                        during["state"] = self.persisted_state()
                        during["locks"] = []
                        for sql in (
                            "SELECT patient_id FROM identity.identity_patients "
                            "WHERE patient_id=:patient FOR UPDATE NOWAIT",
                            "SELECT case_id FROM coordination.patient_case_bindings "
                            "WHERE patient_id=:patient AND case_id='CASE-ALPHA' FOR UPDATE NOWAIT",
                        ):
                            with self.engine.connect() as connection:
                                try:
                                    connection.execute(text(sql), {"patient": operation.patient_id}).scalar_one()
                                except DBAPIError as error:
                                    details = error.orig.args[0] if error.orig.args else None
                                    during["locks"].append(
                                        details.get("C") if isinstance(details, dict) else None)
                                else:
                                    during["locks"].append("acquired")

                    with observe_packet_json_encoding(inspect):
                        response = packet_request(base, operation)
                    envelope = self.assert_encoded_once(observed, operation, historical=historical)
                    self.assertEqual(during["state"], before)
                    self.assertEqual(during["locks"], ["55P03", "55P03"])
                    self.assert_success(response, before, envelope)

    def test_deferred_commit_failure_withholds_prepared_json_and_all_effects(self):
        with running_server(create_app(self.settings)) as base:
            operation = self.operation(base)
            before = self.persisted_state()
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""
                    CREATE FUNCTION identity.reject_packet_disclosure_commit()
                    RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
                    IF NEW.event_type='source.read_authorized' THEN
                        RAISE EXCEPTION 'PRIVATE-PACKET-JSON-ENCODING';
                    END IF;
                    RETURN NEW; END; $$;
                """)
                connection.exec_driver_sql("""
                    CREATE CONSTRAINT TRIGGER reject_packet_disclosure_commit
                    AFTER INSERT ON identity.identity_domain_events
                    DEFERRABLE INITIALLY DEFERRED
                    FOR EACH ROW EXECUTE FUNCTION identity.reject_packet_disclosure_commit()
                """)
            try:
                observed = []
                with observe_packet_json_encoding(observed.append):
                    response = packet_request(base, operation)
                # A typed response that commits before encoding must fail here.
                self.assert_withheld(response, 503, before, operation)
                self.assert_encoded_once(observed, operation)
            finally:
                with self.engine.begin() as connection:
                    connection.exec_driver_sql(
                        "DROP TRIGGER IF EXISTS reject_packet_disclosure_commit "
                        "ON identity.identity_domain_events")
                    connection.exec_driver_sql(
                        "DROP FUNCTION IF EXISTS identity.reject_packet_disclosure_commit()")
            observed = []
            with observe_packet_json_encoding(observed.append):
                recovered = packet_request(base, operation)
            envelope = self.assert_encoded_once(observed, operation)
            self.assert_success(recovered, before, envelope)
