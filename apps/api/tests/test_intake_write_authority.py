"""Real PG16/HTTP races at the existing source and received-pointer writers.

Hooks retain actual parsing, SQL, events and JSON rendering. They only change the
operator-controlled fictional credential at a precise in-flight boundary, or
inject a genuine preparation failure. Durable state is read independently.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from starlette.responses import JSONResponse

from oi_api.app import create_app
from oi_api.patients import OriginalSourceReceipt, ReceivedRecordRequest
from oi_api.record_requests import PostgresRecordRequests
from open_intelligence.postgres_registry import PostgresPatientRegistry

from http_support import running_server
from test_patients import TOKEN_A, request
from test_source_versions import AMENDED, ORIGINAL, SourceVersionFixture


class IntakeWriteAuthorityTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "record_request_create", "record_request_read", "record_request_receive",
        ))
        self.write()

    def durable_state(self):
        with self.engine.connect() as connection:
            return {
                "sources": connection.execute(text(
                    "SELECT source_id,case_id,document_id,version,sha256,raw,state,supersedes_id "
                    "FROM clinical_source.source_versions ORDER BY source_id"
                )).all(),
                "assertions": connection.execute(text(
                    "SELECT source_id,finding_key,certainty,quote,source_line "
                    "FROM clinical_source.assertions ORDER BY assertion_id"
                )).all(),
                "quarantine": connection.execute(text(
                    "SELECT target_case_id,declared_case_id,sha256,raw,reason "
                    "FROM clinical_source.quarantine ORDER BY quarantine_id"
                )).all(),
                "events": connection.execute(text(
                    "SELECT patient_id,event_type,metadata_json "
                    "FROM identity.identity_domain_events ORDER BY id"
                )).all(),
                "requests": connection.execute(text(
                    "SELECT request_id,status,revision FROM coordination.record_requests "
                    "ORDER BY request_id"
                )).all(),
            }

    def change_authority(self, change):
        if change.startswith("grant:"):
            self.creds[0]["actions"].remove(change.partition(":")[2])
        elif change == "patient":
            self.creds[0]["patient_ids"] = []
        elif change == "actor":
            self.creds[0]["actor"] = "ACTOR-CHANGED"
        elif change == "organization":
            self.creds[0]["organization"] = "ORG-CHANGED"
        elif change == "purpose":
            self.creds[0]["purpose"] = "research"
        elif change == "expired":
            self.creds[0]["expires_at"] = (
                datetime.now(timezone.utc) - timedelta(minutes=1)
            ).isoformat()
        elif change == "revoked":
            self.creds.clear()
        elif change == "provider":
            self.access.write_text("PRIVATE-FIXTURE-PROVIDER-FAILURE")
            return
        else:
            raise AssertionError("Unknown test authority mutation")
        self.write()

    @contextmanager
    def restore_authority(self):
        initial = deepcopy(self.creds)
        try:
            yield
        finally:
            self.creds = initial
            self.write()

    @contextmanager
    def change_after_event(self, event, change):
        append = PostgresPatientRegistry.append_event
        def changed(owner, patient, kind, **details):
            append(owner, patient, kind, **details)
            if kind == event:
                self.change_authority(change)
        with self.restore_authority(), patch.object(
                PostgresPatientRegistry, "append_event", changed):
            yield

    @contextmanager
    def change_after_query(self, fragment, change):
        fetch = PostgresPatientRegistry._fetchone
        def changed(owner, sql, params=()):
            result = fetch(owner, sql, params)
            if fragment in sql:
                self.change_authority(change)
            return result
        with self.restore_authority(), patch.object(
                PostgresPatientRegistry, "_fetchone", changed):
            yield

    def create_request(self, base, patient, key="RECORD-INTAKE-001"):
        status, result, _ = request(base, f"/v1/patients/{patient}/record-requests",
                                   token=TOKEN_A, body={
            "synthetic": True, "request_key": key, "kind": "pathology",
            "record_label": "Independently fictional source",
            "source_organization": "Fictional institution",
        })
        self.assertEqual(status, 201)
        return result["request_id"]

    def receive(self, base, patient, request_id, source_id):
        return request(base, f"/v1/patients/{patient}/record-requests/{request_id}/receive",
                       token=TOKEN_A, body={"synthetic": True,
                                           "case_id": "CASE-ALPHA", "source_id": source_id})

    def assert_refused_without_write(self, result, before, status=404):
        # Inspect the database even when the HTTP status is wrong. An error
        # response after an accidental commit is a different failure from a
        # refusal that rolled back as intended.
        unchanged = self.durable_state() == before
        self.assertEqual((result[0], unchanged), (status, True))
        self.assertEqual(set(result[1]), {"detail"})
        self.assertNotIn("PRIVATE-FIXTURE", json.dumps(result[1]))

    def raw_post(self, base, path, body):
        """Inspect even an unexpected plaintext 500 without hiding rollback."""
        req = Request(base + path, data=json.dumps(body).encode("utf-8"),
                      headers={"Content-Type": "application/json",
                               "Authorization": "Bearer " + TOKEN_A})
        try:
            response = urlopen(req, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read().decode("utf-8")
            try:
                content = json.loads(raw)
            except ValueError:
                content = {"unparsed_error_body": raw}
            return response.status, content, dict(response.headers)

    def test_import_final_grants_and_identity_are_independently_refreshed(self):
        changes = [
            ("grant:source_import", 404), ("grant:patient_read", 404),
            ("patient", 404), ("actor", 404), ("organization", 404),
            ("purpose", 404), ("expired", 401), ("revoked", 401), ("provider", 503),
        ]
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            for index, (change, expected) in enumerate(changes):
                with self.subTest(change=change):
                    raw = ORIGINAL.replace("DOC-ONE", f"DOC-FINAL-{index}")
                    before = self.durable_state()
                    with self.change_after_event("source.original.imported", change):
                        result = self.ingest(base, patient, raw)
                    self.assert_refused_without_write(result, before, expected)
                    # The same valid intent can succeed once authority is restored.
                    self.assertEqual(self.ingest(base, patient, raw)[0], 201)

    def test_denied_amendment_rolls_back_supersession_assertions_and_event(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            original_id = self.ingest(base, patient)[1]["source_id"]
            before = self.durable_state()
            with self.change_after_event("source.original.imported", "grant:source_import"):
                result = self.ingest(base, patient, AMENDED)
            self.assert_refused_without_write(result, before)
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            original = request(base, self.url(patient) + "/" + original_id, token=TOKEN_A)[1]
            self.assertEqual(original["original_text"], ORIGINAL)
            self.assertEqual(original["state"], "superseded")

    def test_quarantine_final_denial_leaves_no_bytes_or_event(self):
        wrong_case = ORIGINAL.replace("Patient: CASE-ALPHA", "Patient: CASE-BETA")
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            before = self.durable_state()
            with self.change_after_event("source.original.quarantined", "grant:source_import"):
                result = self.ingest(base, patient, wrong_case)
            self.assert_refused_without_write(result, before)
            accepted = self.ingest(base, patient, wrong_case)
            self.assertEqual((accepted[0], accepted[1]["result"]), (200, "quarantined"))

    def test_duplicate_original_requires_fresh_authority_after_identity_lookup(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            original_id = self.ingest(base, patient)[1]["source_id"]
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            before = self.durable_state()
            for change in ("grant:source_import", "grant:patient_read", "actor"):
                with self.subTest(change=change):
                    with self.change_after_query("SELECT source_id,version FROM", change):
                        result = self.ingest(base, patient)
                    self.assert_refused_without_write(result, before)
            retry = self.ingest(base, patient)
            self.assertEqual((retry[0], retry[1]["source_id"], retry[1]["version"]),
                             (200, original_id, 1))
            self.assertTrue(retry[1]["duplicate"])
            self.assertEqual(self.durable_state(), before)

    def test_duplicate_quarantine_requires_fresh_authority(self):
        wrong_case = ORIGINAL.replace("Patient: CASE-ALPHA", "Patient: CASE-BETA")
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient, wrong_case)[0], 200)
            before = self.durable_state()
            with self.change_after_query("SELECT quarantine_id FROM", "grant:source_import"):
                result = self.ingest(base, patient, wrong_case)
            self.assert_refused_without_write(result, before)
            retry = self.ingest(base, patient, wrong_case)
            self.assertEqual((retry[0], retry[1]["result"], retry[1]["duplicate"]),
                             (200, "quarantined", True))
            self.assertEqual(self.durable_state(), before)

    def test_receive_final_actions_and_principal_are_independently_refreshed(self):
        changes = [
            ("grant:record_request_receive", 404), ("grant:source_read", 404),
            ("grant:patient_read", 404), ("patient", 404), ("actor", 404),
            ("organization", 404), ("purpose", 404), ("expired", 401),
            ("revoked", 401), ("provider", 503),
        ]
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source_id = self.ingest(base, patient)[1]["source_id"]
            for index, (change, expected) in enumerate(changes):
                with self.subTest(change=change):
                    request_id = self.create_request(base, patient, f"RECORD-CHANGE-{index}")
                    before = self.durable_state()
                    with self.change_after_event("record.request.received", change):
                        result = self.receive(base, patient, request_id, source_id)
                    self.assert_refused_without_write(result, before, expected)
                    self.assertEqual(self.receive(base, patient, request_id, source_id)[0], 201)

    def test_historical_duplicate_receipt_requires_current_independent_grants(self):
        read_receipt = PostgresRecordRequests._receipt
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source_id = self.ingest(base, patient)[1]["source_id"]
            request_id = self.create_request(base, patient)
            self.assertEqual(self.receive(base, patient, request_id, source_id)[0], 201)
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            before = self.durable_state()
            for change in ("grant:record_request_receive", "grant:source_read", "actor"):
                with self.subTest(change=change):
                    def changed(owner, *args, **kwargs):
                        value = read_receipt(owner, *args, **kwargs)
                        self.change_authority(change)
                        return value
                    with self.restore_authority(), patch.object(PostgresRecordRequests, "_receipt", changed):
                        result = self.receive(base, patient, request_id, source_id)
                    self.assert_refused_without_write(result, before)
            retry = self.receive(base, patient, request_id, source_id)
            self.assertEqual((retry[0], retry[1]["source_id"], retry[1]["version"]),
                             (200, source_id, 1))
            self.assertTrue(retry[1]["duplicate"])
            self.assertEqual(self.durable_state(), before)

    def test_final_recheck_follows_actual_json_preparation_for_both_commands(self):
        render = JSONResponse.render
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source_id = self.ingest(base, patient)[1]["source_id"]
            request_id = self.create_request(base, patient)
            operations = [
                (lambda: self.ingest(base, patient, ORIGINAL.replace("DOC-ONE", "DOC-PREPARE")),
                 "result", "grant:source_import"),
                (lambda: self.receive(base, patient, request_id, source_id), "request_id", "grant:source_read"),
            ]
            for operation, marker, change in operations:
                with self.subTest(command=marker):
                    before = self.durable_state()
                    def prepared(response, content):
                        encoded = render(response, content)
                        if marker in content and "source_id" in content:
                            self.change_authority(change)
                        return encoded
                    with self.restore_authority(), patch.object(JSONResponse, "render", prepared):
                        result = operation()
                    self.assert_refused_without_write(result, before)

    def test_final_recheck_follows_receipt_construction_for_both_commands(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source_id = self.ingest(base, patient)[1]["source_id"]
            request_id = self.create_request(base, patient)
            operations = [
                (lambda: self.ingest(base, patient, ORIGINAL.replace("DOC-ONE", "DOC-TYPED")),
                 OriginalSourceReceipt, "grant:source_import"),
                (lambda: self.receive(base, patient, request_id, source_id),
                 ReceivedRecordRequest, "grant:source_read"),
            ]
            for operation, model, change in operations:
                with self.subTest(command=model.__name__):
                    before = self.durable_state()
                    construct = model.__init__
                    def prepared(instance, **values):
                        construct(instance, **values)
                        self.change_authority(change)
                    with self.restore_authority(), patch.object(model, "__init__", prepared):
                        result = operation()
                    self.assert_refused_without_write(result, before)

    def test_receipt_construction_failure_rolls_back_both_commands(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source_id = self.ingest(base, patient)[1]["source_id"]
            request_id = self.create_request(base, patient)
            operations = [
                (self.url(patient), {"synthetic": True,
                                    "original_text": ORIGINAL.replace("DOC-ONE", "DOC-DTO")},
                 OriginalSourceReceipt),
                (f"/v1/patients/{patient}/record-requests/{request_id}/receive",
                 {"synthetic": True, "case_id": "CASE-ALPHA", "source_id": source_id},
                 ReceivedRecordRequest),
            ]
            for path, body, model in operations:
                with self.subTest(command=model.__name__):
                    before = self.durable_state()
                    construct = model.__init__
                    def broken(instance, **values):
                        construct(instance, **values)
                        raise ValueError("PRIVATE-FIXTURE-RECEIPT-FAILURE")
                    with patch.object(model, "__init__", broken):
                        result = self.raw_post(base, path, body)
                    self.assert_refused_without_write(result, before, 503)

    def test_json_failure_rolls_back_both_commands(self):
        render = JSONResponse.render
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source_id = self.ingest(base, patient)[1]["source_id"]
            request_id = self.create_request(base, patient)
            operations = [
                (self.url(patient), {"synthetic": True,
                                    "original_text": ORIGINAL.replace("DOC-ONE", "DOC-SERIALIZE")}, "result"),
                (f"/v1/patients/{patient}/record-requests/{request_id}/receive",
                 {"synthetic": True, "case_id": "CASE-ALPHA", "source_id": source_id}, "request_id"),
            ]
            for path, body, marker in operations:
                with self.subTest(command=marker):
                    before = self.durable_state()
                    def broken(response, content):
                        encoded = render(response, content)
                        if marker in content and "source_id" in content:
                            raise ValueError("PRIVATE-FIXTURE-SERIALIZATION-FAILURE")
                        return encoded
                    with patch.object(JSONResponse, "render", broken):
                        result = self.raw_post(base, path, body)
                    self.assert_refused_without_write(result, before, 503)

    def test_owner_case_lock_is_held_during_response_preparation(self):
        observed = []
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            request_id = self.create_request(base, patient)
            def lock_probe(construct):
                def prepared(instance, **values):
                    construct(instance, **values)
                    with self.engine.connect() as other:
                        transaction = other.begin()
                        try:
                            other.execute(text("SELECT case_id FROM coordination.patient_case_bindings "
                                               "WHERE case_id='CASE-ALPHA' FOR UPDATE NOWAIT"))
                            observed.append("unlocked")
                        except DBAPIError as exc:
                            observed.append(exc.orig.args[0].get("C"))
                        finally:
                            transaction.rollback()
                return prepared
            with patch.object(OriginalSourceReceipt, "__init__", lock_probe(OriginalSourceReceipt.__init__)), \
                    patch.object(ReceivedRecordRequest, "__init__", lock_probe(ReceivedRecordRequest.__init__)):
                status, original, _ = self.ingest(base, patient)
                self.assertEqual(status, 201)
                result = self.receive(base, patient, request_id, original["source_id"])
                self.assertEqual(result[0], 201)
            self.assertEqual(observed, ["55P03", "55P03"])

