"""Real ASGI routing/serialization with simulated source transactions, not PG proof."""
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry
from oi_api import laboratory_fhir_routes as routes
from oi_api.laboratory_fhir_routes import register_laboratory_fhir_routes
from oi_api.laboratory_fhir_store import PostgresLaboratoryFHIR
from oi_api.request_limits import PatientRequestLimit
from oi_api.sources import PostgresSourceVersions
from oi_api.source_world_model import project_source_world_model
from test_laboratory_question_preflight import context, PID, CASE, SID, QUESTION, OBS

PATH = f"/v1/patients/{PID}/cases/{CASE}/composer/laboratory-preflight"


class LaboratoryQuestionRouteTests(unittest.TestCase):
    def setUp(self):
        self.index, self.labs = context()
        self.events = []
        self.state = {"allowed": {"patient_read", "source_read", "composer_context_read"},
                      "purpose": "operations", "late_deny": False, "audit_fail": False}
        self.patient_registry = PostgresPatientRegistry(SimpleNamespace(autocommit=False))
        app = FastAPI()
        app.add_middleware(PatientRequestLimit)
        for exc, code in ((PatientRegistryDenied, 404), (PatientRegistryConflict, 409),
                          (PatientRegistryError, 422)):
            def handler(request, error, status=code):
                return JSONResponse({"detail": "Context unavailable"}, status_code=status)
            app.add_exception_handler(exc, handler)
        router = APIRouter(prefix="/v1/patients")
        def principal():
            return SimpleNamespace(actor="ACTOR-ALPHA", organization="ORG-ALPHA",
                                   purpose=self.state["purpose"])
        @contextmanager
        def registry(context):
            yield self.patient_registry
        def authorized(patients, context, patient, action):
            self.events.append("grant:" + action)
            if patient != PID or not {"patient_read", action} <= self.state["allowed"]:
                raise PatientRegistryDenied("Fictional denial")
        def final(request, context, patients, patient, actions):
            self.events.append("final-authority")
            if self.state["late_deny"]:
                raise PatientRegistryDenied("Fictional revoked grant")
            for action in actions:
                authorized(patients, context, patient, action)
        register_laboratory_fhir_routes(
            router, principal=principal, registry=registry,
            records_authorized=authorized, final_authority=final, errors={})
        app.include_router(router)
        self.app = app
        self.client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)
        def source_read(owner, patient, case, **kw):
            self.events.append("transaction")
            self.assertEqual((patient, case), (PID, CASE))
            self.patient_registry._transaction_active = True
            try:
                result = kw["prepare_response"](self.index)
                self.assertIsInstance(result, JSONResponse)
                self.assertIsInstance(result.body, bytes)
                self.events.append("serialized")
                kw["recheck_authority"]()
                self.events.append("audit")
                if self.state["audit_fail"]:
                    raise RuntimeError("Fictional audit unavailable")
                kw["recheck_authority"]()
                self.events.append("commit")
                return result
            except Exception:
                self.events.append("rollback")
                raise
            finally:
                self.patient_registry._transaction_active = False
        def labs(owner, case):
            self.assertTrue(self.patient_registry._transaction_active)
            return self.labs
        for patcher in (patch.object(PostgresSourceVersions, "list", source_read),
                        patch.object(PostgresLaboratoryFHIR, "current_observations_locked", labs)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.payload = {"synthetic": True, "source_id": SID,
                        "observation_reference": OBS, "question": QUESTION,
                        "expected_source_snapshot_sha256": project_source_world_model(self.index)["snapshot_fingerprint"]}

    def test_route_returns_typed_context_only_after_complete_serialization(self):
        response = self.client.post(PATH, json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["selected_source"]["value_text"], "4.20")
        self.assertEqual(body["selected_source"]["resource_reference"], OBS)
        self.assertFalse(body["durable_question_created"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertLess(self.events.index("serialized"), self.events.index("final-authority"))
        self.assertEqual(self.events[-1], "commit")
        self.assertEqual(self.events.count("final-authority"), 2)

    def test_independent_patient_source_and_composer_grants_are_required(self):
        for grant in ("patient_read", "source_read", "composer_context_read"):
            with self.subTest(grant=grant):
                self.events.clear()
                self.state["allowed"].remove(grant)
                response = self.client.post(PATH, json=self.payload)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("transaction", self.events)
                self.state["allowed"].add(grant)

    def test_final_authority_denial_withholds_prepared_values(self):
        self.state["late_deny"] = True
        response = self.client.post(PATH, json=self.payload)
        self.assertEqual(response.status_code, 404)
        self.assertIn("serialized", self.events)
        self.assertIn("rollback", self.events)
        self.assertNotIn("commit", self.events)
        self.assertNotIn("4.20", response.text)
        self.assertNotIn(OBS, response.text)

    def test_audit_failure_withholds_response(self):
        self.state["audit_fail"] = True
        response = self.client.post(PATH, json=self.payload)
        self.assertEqual(response.status_code, 500)
        self.assertIn("rollback", self.events)
        self.assertNotIn("commit", self.events)
        self.assertNotIn("4.20", response.text)

    def test_serialization_failure_does_not_reach_authority_or_audit(self):
        response_type = getattr(routes, "PreparedLaboratoryQuestion", None)
        self.assertIsNotNone(response_type, "typed response contract missing")
        with patch.object(routes, "PreparedLaboratoryQuestion", side_effect=ValueError("Fictional serialization failure")):
            response = self.client.post(PATH, json=self.payload)
        self.assertEqual(response.status_code, 500)
        self.assertIn("rollback", self.events)
        self.assertNotIn("final-authority", self.events)
        self.assertNotIn("audit", self.events)

    def test_changed_snapshot_is_conflict_not_success(self):
        response = self.client.post(PATH, json={**self.payload, "expected_source_snapshot_sha256": "0" * 64})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("commit", self.events)

    def test_strict_request_rejects_old_line_anchor_and_false_authority(self):
        for change in ({"source_line": 8}, {"synthetic": "true"},
                       {"question": 123}, {"source_id": False}):
            with self.subTest(change=change):
                self.assertEqual(self.client.post(PATH, json={**self.payload, **change}).status_code, 422)
        self.assertEqual(self.client.post(PATH, json={**self.payload, "synthetic": False}).status_code, 404)
        self.assertEqual(self.client.post(PATH + "?unexpected=true", json=self.payload).status_code, 404)
        self.state["purpose"] = "research"
        self.assertEqual(self.client.post(PATH, json=self.payload).status_code, 404)

    def test_request_bytes_are_bounded_before_json_parsing(self):
        response = self.client.post(PATH, content=b" " * 16385,
                                    headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.events, [])

    def test_openapi_marks_operation_as_preparation_not_question_write(self):
        path = "/v1/patients/{patient_id}/cases/{case_id}/composer/laboratory-preflight"
        schema = self.app.openapi()
        self.assertIn(path, schema["paths"])
        operation = schema["paths"][path]["post"]
        self.assertEqual(operation["operationId"], "prepare_fictional_laboratory_question_v1")
        ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        self.assertEqual(ref, "#/components/schemas/PreparedLaboratoryQuestion")
