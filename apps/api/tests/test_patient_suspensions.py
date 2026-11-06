"""Administrative suspension of independently fictional patients over real HTTP/PG16."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import threading
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import text

from oi_api.app import create_app
from oi_api.patients import SuspendPatient, SuspendedPatient
from open_intelligence.postgres_registry import PostgresPatientRegistry
from http_support import running_server
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture


class SuspensionContractTests(unittest.TestCase):
    def test_requires_fictional_acknowledgement_opaque_key_and_strict_revision(self):
        valid = {"synthetic": True, "request_key": "SUSPEND-ONE", "expected_revision": 1}
        self.assertEqual(SuspendPatient(**valid).expected_revision, 1)
        for change in ({"synthetic": False}, {"synthetic": 1}, {"request_key": "person@example.org"},
                       {"expected_revision": True}, {"expected_revision": "1"},
                       {"expected_revision": 1.0}, {"expected_revision": 0},
                       {"expected_revision": 2**63}, {"actor": "ACTOR-IMPERSONATED"}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                SuspendPatient(**(valid | change))


class PatientSuspensionHTTPTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].append("patient_suspend")
        self.write()

    def suspend(self, base, patient, *, token=TOKEN_A, **overrides):
        return request(base, f"/v1/patients/{patient}/suspensions", token=token, body={
            "synthetic": True, "request_key": "SUSPEND-ONE", "expected_revision": 1, **overrides})

    def state(self, patient):
        with self.engine.connect() as connection:
            row = connection.execute(text(
                "SELECT status,revision FROM identity.identity_patients WHERE patient_id=:p"),
                {"p": patient}).one()
            events = connection.execute(text(
                "SELECT event_type,metadata_json FROM identity.identity_domain_events "
                "WHERE patient_id=:p ORDER BY id"), {"p": patient}).all()
            return tuple(row), [tuple(event) for event in events]

    def test_exact_retry_and_changed_intent_after_api_restart(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            code, receipt, headers = self.suspend(base, patient)
            self.assertEqual((code, receipt), (200, {"patient_id": patient,
                                                   "status": "suspended", "revision": 2}))
            self.assertEqual(headers["Cache-Control"], "no-store")
            state = self.state(patient)
            self.assertEqual(state[0], ("suspended", 2))
            event, = [e for e in state[1] if e[0] == "identity.patient.suspended"]
            self.assertEqual(event[1]["request_key"], "SUSPEND-ONE")
            self.assertEqual(event[1]["actor"], "ACTOR-ALPHA")
            self.assertNotIn(TOKEN_A, json.dumps(event))
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(self.suspend(base, patient)[:2], (200, receipt))
            self.assertEqual(self.suspend(base, patient, expected_revision=2)[0], 409)
            self.assertEqual(self.suspend(base, patient, request_key="SUSPEND-OTHER")[0], 409)
            self.creds[0]["actor"] = "ACTOR-REPLACEMENT"
            self.write()
            self.assertEqual(self.suspend(base, patient)[0], 409)
            self.assertEqual(self.state(patient), state)

    def test_independent_grants_scope_org_purpose_and_bounded_input(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            before = self.state(patient)
            original = deepcopy(self.creds)
            for action in ("patient_read", "patient_suspend"):
                self.creds = deepcopy(original)
                self.creds[0]["actions"].remove(action)
                self.write()
                self.assertEqual(self.suspend(base, patient)[0], 404)
            for change in ({"patient_ids": []}, {"organization": "ORG-BETA"}, {"purpose": "research"}):
                self.creds = deepcopy(original)
                self.creds[0].update(change)
                self.write()
                code, body, _ = self.suspend(base, patient)
                self.assertEqual((code, body), (404, {"detail": "Patient unavailable"}))
            self.creds = deepcopy(original)
            self.write()
            self.assertEqual(self.suspend(base, patient, token=TOKEN_B)[0], 404)
            self.assertEqual(self.suspend(base, "PAT-UNKNOWN")[0], 404)
            self.assertEqual(self.suspend(base, patient, token=None)[0], 401)
            self.assertEqual(self.suspend(base, patient, expected_revision=True)[0], 422)
            self.assertEqual(self.suspend(base, patient, expected_revision=2)[0], 409)
            self.assertEqual(self.suspend(base, patient, request_key="X" * 17_000)[0], 413)
            self.assertEqual(self.state(patient), before)

    def test_concurrent_exact_retries_write_one_transition_and_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            barrier = threading.Barrier(2)
            def command(_):
                barrier.wait(timeout=5)
                return self.suspend(base, patient)[:2]
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(command, range(2)))
            self.assertEqual([r[0] for r in results], [200, 200])
            self.assertEqual(results[0], results[1])
            self.assertEqual(sum(e[0] == "identity.patient.suspended" for e in self.state(patient)[1]), 1)

    def test_response_encoding_failure_rolls_back_patient_and_event(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            before = self.state(patient)
            with patch.object(SuspendedPatient, "model_dump", side_effect=ValueError("PRIVATE-ENCODING")):
                code, body, _ = self.suspend(base, patient)
            self.assertEqual(code, 503, body)
            self.assertNotIn("PRIVATE-ENCODING", json.dumps(body))
            self.assertEqual(self.state(patient), before)
            self.assertEqual(self.suspend(base, patient)[0], 200)

    def test_revocation_after_json_preparation_rolls_back_and_blocks_receipt_retry(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            before = self.state(patient)
            original = SuspendedPatient.model_dump
            def revoke(response, *args, **kwargs):
                value = original(response, *args, **kwargs)
                self.creds[0]["actions"].remove("patient_suspend")
                self.write()
                return value
            with patch.object(SuspendedPatient, "model_dump", revoke):
                self.assertEqual(self.suspend(base, patient)[0], 404)
            self.assertEqual(self.state(patient), before)
            self.creds[0]["actions"].append("patient_suspend")
            self.write()
            self.assertEqual(self.suspend(base, patient)[0], 200)
            committed = self.state(patient)
            self.creds[0]["actions"].remove("patient_suspend")
            self.write()
            self.assertEqual(self.suspend(base, patient)[0], 404)
            self.assertEqual(self.state(patient), committed)

    def test_authority_is_refreshed_after_patient_lock_and_after_journal_write(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            before = self.state(patient)
            fetch = PostgresPatientRegistry._fetchone
            def after_lock(owner, sql, params=()):
                result = fetch(owner, sql, params)
                if sql.startswith("SELECT status,revision") and "FOR UPDATE" in sql:
                    self.creds[0]["actions"].remove("patient_suspend")
                    self.write()
                return result
            with patch.object(PostgresPatientRegistry, "_fetchone", after_lock):
                self.assertEqual(self.suspend(base, patient)[0], 404)
            self.assertEqual(self.state(patient), before)
            self.creds[0]["actions"].append("patient_suspend")
            self.write()
            write_event = PostgresPatientRegistry._write_event
            def after_event(owner, patient_id, kind, details):
                write_event(owner, patient_id, kind, details)
                if kind == "identity.patient.suspended":
                    self.creds.clear()
                    self.write()
            with patch.object(PostgresPatientRegistry, "_write_event", after_event):
                self.assertEqual(self.suspend(base, patient)[0], 401)
            self.assertEqual(self.state(patient), before)

    def test_suspended_patient_withholds_sources_but_retains_identity_status(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            code, source, _ = self.ingest(base, patient)
            self.assertEqual(code, 201)
            self.assertEqual(self.suspend(base, patient)[0], 200)
            before = self.state(patient)
            for path in (self.url(patient), self.url(patient) + "/" + source["source_id"],
                         f"/v1/patients/{patient}/case-bindings"):
                self.assertEqual(request(base, path, token=TOKEN_A)[0], 404)
            self.assertEqual(self.ingest(base, patient)[0], 404)
            code, identity, _ = request(base, f"/v1/patients/{patient}", token=TOKEN_A)
            self.assertEqual((code, identity["status"], identity["revision"]), (200, "suspended", 2))
            self.assertEqual(self.state(patient), before)
