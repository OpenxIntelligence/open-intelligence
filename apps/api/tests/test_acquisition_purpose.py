"""Purpose and in-flight authority across fictional source acquisition, on real PG16."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from contextlib import contextmanager
from copy import deepcopy
from threading import Barrier
from unittest.mock import patch

from fastapi.responses import JSONResponse
from sqlalchemy import text

from oi_api.app import create_app
from oi_api.record_requests import PostgresRecordRequests
from open_intelligence.postgres_registry import PostgresPatientRegistry

from http_support import running_server
from test_patients import TOKEN_A, request
from test_source_versions import ORIGINAL, SourceVersionFixture


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

    def test_workspace_scope_is_required_for_disclosure_create_and_retry(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            requests = f"/v1/patients/{patient}/record-requests"
            scoped = requests + "?case_id=CASE-ALPHA"
            created = self.create_record(base, scoped, "WORKSPACE-REQUEST")
            self.assertEqual(created[0], 201)
            self.assertEqual(self.create_record(base, scoped, "WORKSPACE-REQUEST")[:2],
                             (200, {**created[1], "duplicate": True}))
            before = self.state()
            for changes in ({"purpose": "research"}, {"patient_ids": []},
                            {"actions": [a for a in self.creds[0]["actions"] if a != "case_binding_read"]},
                            {"actions": [a for a in self.creds[0]["actions"] if a != "source_read"]}):
                with self.subTest(changes=changes), self.credential(**changes):
                    self.assertEqual(self.records(base, scoped)[0], 404)
                    self.assertEqual(self.create_record(base, scoped, "WORKSPACE-REQUEST")[0], 404)
                    self.assertEqual(self.create_record(base, scoped, "ANOTHER-REQUEST")[0], 404)
                    self.assertEqual(self.state(), before)
            self.assertEqual(self.create_record(base, requests, "WORKSPACE-REQUEST")[0], 409)
            for query in ("?case_id=CASE-ALPHA&case_id=CASE-BETA", "?case_id=wrong"):
                self.assertEqual(self.records(base, requests + query)[0], 422)
                self.assertEqual(self.create_record(base, requests + query, "INVALID-CONTEXT")[0], 422)
            self.assertEqual(self.state(), before)

    def test_revoke_before_scoped_response_rolls_back_a_new_request(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            scoped = f"/v1/patients/{patient}/record-requests?case_id=CASE-ALPHA"
            before = self.state()
            append = PostgresPatientRegistry.append_event
            def after_event(owner, subject, event, **details):
                append(owner, subject, event, **details)
                if event == "record.request.created":
                    self.creds[0]["actions"].remove("case_binding_read")
                    self.write()
            with self.credential(), patch.object(PostgresPatientRegistry, "append_event", after_event):
                self.assertEqual(self.create_record(base, scoped, "WITHDRAWN-IN-FLIGHT")[0], 404)
            self.assertEqual(self.state(), before)

    def test_case_revoked_during_scoped_create_leaves_only_the_independent_revocation(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            patient_path = f"/v1/patients/{patient}"
            append = PostgresPatientRegistry.append_event
            def revoke_after_insert(owner, subject, event, **details):
                append(owner, subject, event, **details)
                if event == "record.request.created":
                    reply = self.post(base, patient_path + "/case-bindings/CASE-ALPHA/revoke",
                                      reason="Withdraw the open fictional case")
                    self.assertEqual(reply[0], 200)
            with patch.object(PostgresPatientRegistry, "append_event", revoke_after_insert):
                reply = self.create_record(base, patient_path + "/record-requests?case_id=CASE-ALPHA",
                                           "REQUEST-REVOKED-CASE")
            self.assertEqual(reply[0], 404)
            bindings, records, events = self.state()
            self.assertEqual(bindings, [("CASE-ALPHA", "revoked", 2)])
            self.assertEqual(records, [])
            self.assertEqual([event for event, _ in events], [
                "identity.patient.created", "identity.case_binding_created", "identity.case_binding_revoked"])

    def test_legacy_mixed_purpose_receipt_withholds_source_identity(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            records = f"/v1/patients/{patient}/record-requests"
            source = self.ingest(base, patient)[1]["source_id"]
            with self.credential(purpose="research"):
                record = self.create_record(base, records, "HISTORICAL-REQUEST")[1]["request_id"]
                other = self.create_record(base, records, "VALID-RESEARCH")[1]["request_id"]
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
                self.assertEqual([row["request_id"] for row in body["requests"]], [other])
                before = self.state()
                self.assertEqual(self.post(base, records + "/" + record + "/cancel",
                                           reason="Fictional old receipt check")[0], 404)
                self.assertEqual(self.state(), before)

    def test_selected_original_must_match_before_write_and_on_exact_retry(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            path = f"/v1/patients/{patient}/record-requests"
            record = self.create_record(base, path, "SELECTED-ORIGINAL")[1]["request_id"]
            source = self.ingest(base, patient)[1]["source_id"]
            receive_path = path + "/" + record + "/receive"
            selection = {"version": 1, "sha256": hashlib.sha256(ORIGINAL.encode()).hexdigest()}

            def link(pin):
                return self.post(base, receive_path, case_id="CASE-ALPHA", source_id=source,
                                 expected_original=pin)

            for expected_status in (201, 200):
                before = self.state()
                for mismatch in ({"version": 2}, {"sha256": "0" * 64}):
                    self.assertEqual(link({**selection, **mismatch})[0], 409)
                    self.assertEqual(self.state(), before)
                status, receipt, _ = link(selection)
                self.assertEqual((status, receipt["duplicate"]), (expected_status, expected_status == 200))
            row, = self.records(base, path)[1]["requests"]
            self.assertEqual(row["source_reference"], {**selection, "source_id": source, "case_id": "CASE-ALPHA"})

    def test_concurrent_crossed_receipt_retries_return_conflicts_without_mutation(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            path = f"/v1/patients/{patient}"
            self.assertEqual(self.bind(base, path + "/case-bindings")[0], 201)
            records = path + "/record-requests"
            def receive(record, case, source):
                return self.post(base, records + "/" + record + "/receive",
                                 case_id=case, source_id=source)[0]
            cases = ("CASE-ALPHA", "CASE-BETA")
            accepted = []
            for case in cases:
                record = self.create_record(base, records, "REQUEST-" + case)[1]["request_id"]
                source = self.ingest(base, patient, ORIGINAL.replace(cases[0], case),
                                     case=case)[1]["source_id"]
                self.assertEqual(receive(record, case, source), 201)
                accepted.append((record, case, source))
            before = self.state()
            unscoped = self.records(base, records)[1]["requests"]
            self.assertEqual({r["source_reference"]["case_id"] for r in unscoped}, set(cases))
            for case in cases:
                scoped = self.records(base, records + "?case_id=" + case)[1]["requests"]
                self.assertEqual({r["request_id"] for r in scoped}, {r[0] for r in accepted})
                for row in scoped:
                    reference = next(item["source_reference"] for item in unscoped
                                     if item["request_id"] == row["request_id"])
                    self.assertEqual(row["source_reference"], reference if reference["case_id"] == case else None)
            # Meet only after each writer owns its submitted request, binding and source.
            barrier = Barrier(2, timeout=4)
            lookup = PostgresRecordRequests._receipt
            def synchronized(owner, *args, **kwargs):
                barrier.wait()
                return lookup(owner, *args, **kwargs)
            with patch.object(PostgresRecordRequests, "_receipt", synchronized), ThreadPoolExecutor(2) as pool:
                results = [pool.submit(receive, accepted[i][0], *accepted[1-i][1:]) for i in (0, 1)]
                self.assertEqual([result.result() for result in results], [409, 409])
            self.assertEqual(self.state(), before)

    def test_withdrawal_during_response_preparation_rolls_back_or_withholds_each_result(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            path = f"/v1/patients/{patient}"
            bindings, records = path + "/case-bindings", path + "/record-requests"
            record = self.create_record(base, records, "ALREADY-REQUESTED")[1]["request_id"]
            source = self.ingest(base, patient)[1]["source_id"]
            linked = self.create_record(base, records, "RECEIVED-RECORD")[1]["request_id"]
            self.assertEqual(self.post(base, records + "/" + linked + "/receive",
                                       case_id="CASE-ALPHA", source_id=source)[0], 201)
            reason = {"reason": "Fictional transaction test"}
            checks = (
                ("case_binding_read", lambda: self.records(base, bindings)),
                ("case_binding_create", lambda: self.bind(base, bindings)),
                ("case_binding_revoke", lambda: self.post(base, bindings + "/CASE-ALPHA/revoke", **reason)),
                ("record_request_read", lambda: self.records(base, records)),
                ("source_read", lambda: self.records(base, records)),
                ("record_request_create", lambda: self.create_record(base, records, "NEW-REQUEST")),
                ("patient_read", lambda: self.create_record(base, records, "ALREADY-REQUESTED")),
                ("record_request_cancel", lambda: self.post(base, records + "/" + record + "/cancel", **reason)),
            )
            for grant, act in checks:
                with self.subTest(grant=grant), self.credential():
                    before = self.state()
                    render = JSONResponse.render
                    def withdraw(response, content):
                        encoded = render(response, content)
                        if isinstance(content, dict) and "detail" not in content:
                            self.creds[0]["actions"].remove(grant)
                            self.write()
                        return encoded
                    with patch.object(JSONResponse, "render", withdraw):
                        status, result, _ = act()
                    self.assertEqual((status, set(result), self.state() == before),
                                     (404, {"detail"}, True))
