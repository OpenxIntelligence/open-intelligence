"""Purpose and in-flight authority across fictional source acquisition, on real PG16."""
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import patch

from sqlalchemy import text

from oi_api.app import create_app
from oi_api.patients import CaseBindingList, CaseBindingReceipt, RecordRequests, RecordRequestReceipt
from open_intelligence.postgres_registry import PostgresPatientRegistry

from http_support import running_server
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


class AcquisitionPurposeTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "record_request_create", "record_request_read", "record_request_cancel",
            "record_request_receive",
        ))
        self.write()

    def post(self, base, path, **fields):
        return request(base, path, token=TOKEN_A, body={"synthetic": True, **fields})

    def records(self, base, path):
        return request(base, path, token=TOKEN_A)

    def create_record(self, base, path, key):
        return self.post(base, path, request_key=key, kind="pathology",
                         record_label="Fictional source request", source_organization="ORG-TEST")

    def bind(self, base, path):
        return self.post(base, path, case_id="CASE-BETA", source_organization="ORG-SECOND",
                         source_system="SYS-LOCAL", source_subject_ref="SUBJECT-BETA",
                         review_ref="REVIEW-SECOND")

    @contextmanager
    def credential(self, **changes):
        original = deepcopy(self.creds[0])
        self.creds[0].update(changes)
        self.write()
        try:
            yield
        finally:
            self.creds[0] = original
            self.write()

    def state(self):
        with self.engine.connect() as db:
            return tuple(db.execute(text(query)).all() for query in (
                "SELECT case_id, status, revision FROM coordination.patient_case_bindings ORDER BY case_id",
                "SELECT request_id, status, revision FROM coordination.record_requests ORDER BY request_id",
                "SELECT event_type, metadata_json FROM identity.identity_domain_events ORDER BY id",
            ))

    def test_same_patient_and_actor_have_separate_purpose_scopes(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            path = f"/v1/patients/{patient}"
            records = path + "/record-requests"
            bindings = path + "/case-bindings"
            source = self.ingest(base, patient)[1]["source_id"]
            ops_request = self.create_record(base, records, "OPS-REQUEST")[1]["request_id"]
            reason = {"reason": "Fictional permission isolation check"}

            with self.credential(purpose="research"):
                self.assertEqual(self.bind(base, bindings)[0], 201)
                research_request = self.create_record(base, records, "RESEARCH-REQUEST")[1]["request_id"]
                self.assertEqual([row["case_id"] for row in self.records(base, bindings)[1]["mappings"]],
                                 ["CASE-BETA"])
                self.assertEqual([row["request_id"] for row in self.records(base, records)[1]["requests"]],
                                 [research_request])
                before = self.state()
                self.assertEqual(self.post(base, bindings + "/CASE-ALPHA/revoke", **reason)[0], 404)
                self.assertEqual(self.post(base, records + "/" + ops_request + "/cancel", **reason)[0], 404)
                self.assertEqual(self.state(), before)

            self.assertEqual([row["case_id"] for row in self.records(base, bindings)[1]["mappings"]],
                             ["CASE-ALPHA"])
            self.assertEqual([row["request_id"] for row in self.records(base, records)[1]["requests"]],
                             [ops_request])
            before = self.state()
            self.assertEqual(self.post(base, records + "/" + research_request + "/receive",
                                       case_id="CASE-ALPHA", source_id=source)[0], 404)
            self.assertEqual(self.state(), before)
            receipt = self.post(base, records + "/" + ops_request + "/receive",
                                case_id="CASE-ALPHA", source_id=source)
            self.assertEqual((receipt[0], receipt[1]["source_id"]), (201, source))
            self.assertEqual(self.post(base, bindings + "/CASE-ALPHA/revoke", **reason)[0], 200)
            row, = self.records(base, records)[1]["requests"]
            self.assertEqual((row["receipt_status"], row["source_reference"]),
                             ("binding_revoked_not_usable", None))

    def test_legacy_mixed_purpose_receipt_withholds_source_identity(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            records = f"/v1/patients/{patient}/record-requests"
            source = self.ingest(base, patient)[1]["source_id"]
            with self.credential(purpose="research"):
                record = self.create_record(base, records, "HISTORICAL-REQUEST")[1]["request_id"]
            # Reproduce a receipt that could be written by an older version.
            with self.engine.begin() as db:
                raw = db.connection.driver_connection
                owner = PostgresPatientRegistry(raw)
                with owner.transaction():
                    digest, version = owner._fetchone(
                        "SELECT sha256,version FROM clinical_source.source_versions WHERE source_id=%s",
                        (source,))
                    owner.append_event(patient, "record.request.received", request_id=record,
                                       case_id="CASE-ALPHA", source_id=source, source_sha256=digest,
                                       source_version=version, actor=self.creds[0]["actor"])
            with self.credential(purpose="research"):
                status, body, _ = self.records(base, records)
                self.assertEqual(status, 200)
                row, = body["requests"]
                self.assertEqual((row["status"], row["receipt_status"], row["source_reference"]),
                                 ("received", "binding_purpose_not_usable", None))

    def test_withdrawal_during_response_preparation_rolls_back_or_withholds_each_result(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            path = f"/v1/patients/{patient}"
            bindings, records = path + "/case-bindings", path + "/record-requests"
            record = self.create_record(base, records, "ALREADY-REQUESTED")[1]["request_id"]
            reason = {"reason": "Fictional transaction test"}
            checks = (
                (CaseBindingList, "case_binding_read", lambda: self.records(base, bindings)),
                (CaseBindingReceipt, "case_binding_create", lambda: self.bind(base, bindings)),
                (CaseBindingReceipt, "case_binding_revoke", lambda: self.post(base, bindings + "/CASE-ALPHA/revoke", **reason)),
                (RecordRequests, "record_request_read", lambda: self.records(base, records)),
                (RecordRequests, "source_read", lambda: self.records(base, records)),
                (RecordRequestReceipt, "record_request_create", lambda: self.create_record(base, records, "NEW-REQUEST")),
                (RecordRequestReceipt, "patient_read", lambda: self.create_record(base, records, "ALREADY-REQUESTED")),
                (RecordRequestReceipt, "record_request_cancel", lambda: self.post(base, records + "/" + record + "/cancel", **reason)),
            )
            for model, grant, act in checks:
                with self.subTest(grant=grant), self.credential():
                    before = self.state()
                    validate = model.__init__
                    def withdraw(instance, **values):
                        validate(instance, **values)
                        self.creds[0]["actions"].remove(grant)
                        self.write()
                    with patch.object(model, "__init__", withdraw):
                        status, result, _ = act()
                    self.assertEqual((status, set(result), self.state() == before),
                                     (404, {"detail"}, True))
