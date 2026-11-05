"""Authorized, nonwriting FHIR lab preview against disposable PostgreSQL 16.

All subjects/resources are invented; no external data, live FHIR server or model.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.engine import make_url

from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.contracts import SCHEMA_REVISION
from oi_api.database import make_engine
from oi_api.migrate import migrate
from http_support import running_server
from test_patients import TOKEN_A, TOKEN_B, request, credential
from test_laboratory_fhir_r4 import example, encode, resource


@unittest.skipUnless(os.environ.get("OI_API_RUN_DATABASE_TESTS") == "1",
                     "Requires a disposable PostgreSQL 16 database")
class LaboratoryFHIRHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.environ.get("OI_API_TEST_DATABASE_URL", "")
        if not (make_url(url).database or "").startswith("oi_api_test_"):
            raise RuntimeError("Lab HTTP tests require a disposable oi_api_test_ PostgreSQL database")
        cls.settings = Settings(database_url=url)
        cls.engine = make_engine(cls.settings)
        with cls.engine.connect() as c:
            if int(c.execute(text("SHOW server_version_num")).scalar_one()) // 10000 != 16:
                raise RuntimeError("PostgreSQL 16 required")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as c:
            for name in ("investigation", "clinical_source", "coordination", "identity"):
                c.execute(text("DROP SCHEMA IF EXISTS " + name + " CASCADE"))
            c.execute(text("DROP TABLE IF EXISTS public.alembic_version"))
        migrate(self.settings, "upgrade", "head")
        self.folder = tempfile.TemporaryDirectory(prefix="oi-fictional-lab-")
        self.addCleanup(self.folder.cleanup)
        self.access_path = Path(self.folder.name) / "access.json"
        actions = ("patient_create", "patient_read", "case_binding_create",
                   "case_binding_revoke", "source_import", "source_read",
                   "source_original_read")
        self.creds = [credential(TOKEN_A, actions=actions),
                      credential(TOKEN_B, organization="ORG-BETA", actor="ACTOR-BETA",
                                 actions=actions)]
        self.write_access()
        self.app = create_app(Settings.from_env({
            "OI_API_DATABASE_URL": self.settings.database_url,
            "OI_API_ACCESS_FILE": str(self.access_path),
        }))

    def tearDown(self):
        with self.engine.begin() as c:
            for name in ("investigation", "clinical_source", "coordination", "identity"):
                c.execute(text("DROP SCHEMA IF EXISTS " + name + " CASCADE"))
            c.execute(text("DROP TABLE IF EXISTS public.alembic_version"))

    def write_access(self):
        temp = self.access_path.with_suffix(".new")
        temp.write_text(json.dumps({"version": "oi.synthetic-access/1",
                                    "credentials": self.creds}))
        temp.chmod(0o600)
        temp.replace(self.access_path)

    def make_patient(self, base):
        status, value, _ = request(base, "/v1/patients", token=TOKEN_A,
                                   body={"synthetic": True, "request_key": "REQ-LAB-A"})
        self.assertEqual(status, 201)
        pid = value["patient_id"]
        self.creds[0]["patient_ids"] = [pid]
        self.write_access()
        status, receipt, _ = request(base, f"/v1/patients/{pid}/case-bindings",
                token=TOKEN_A, body={"synthetic": True, "case_id": "CASE-LAB-A",
                    "source_organization": "ORG-FICTIONAL-HOSPITAL",
                    "source_system": "SYS-FICTIONAL-LIS",
                    "source_subject_ref": "FICTIONAL-PATIENT-A",
                    "review_ref": "FICTIONAL-REVIEW-A"})
        self.assertEqual(status, 201, receipt)
        return pid

    def source_counts(self):
        with self.engine.connect() as c:
            return (c.execute(text("SELECT count(*) FROM clinical_source.source_versions")).scalar_one(),
                    c.execute(text("SELECT count(*) FROM identity.identity_domain_events")).scalar_one())

    def preview(self, base, patient, bundle=None, token=TOKEN_A):
        data = encode(example() if bundle is None else bundle).decode("utf-8")
        return request(base, f"/v1/patients/{patient}/cases/CASE-LAB-A/laboratory/fhir-r4/preview",
                       token=token, body={"synthetic": True, "bundle_json": data})

    def import_source(self, base, patient, bundle=None, *, request_key="LAB-IMPORT-ONE",
                      expected_previous_source_id=None, token=TOKEN_A):
        data = encode(example() if bundle is None else bundle).decode("utf-8")
        return request(
            base, f"/v1/patients/{patient}/cases/CASE-LAB-A/laboratory/fhir-r4/sources",
            token=token,
            body={"synthetic": True, "request_key": request_key,
                  "expected_previous_source_id": expected_previous_source_id,
                  "bundle_json": data},
        )

    def lab_counts(self):
        with self.engine.connect() as c:
            return (
                c.execute(text("SELECT count(*) FROM clinical_source.source_versions")).scalar_one(),
                c.execute(text("SELECT count(*) FROM clinical_source.fhir_laboratory_sources")).scalar_one(),
                c.execute(text("SELECT count(*) FROM clinical_source.fhir_laboratory_observations")).scalar_one(),
                c.execute(text("SELECT count(*) FROM clinical_source.fhir_laboratory_commands")).scalar_one(),
            )

    def test_valid_preview_is_real_scoped_http_and_nonwriting(self):
        with running_server(self.app) as base:
            patient = self.make_patient(base)
            before = self.source_counts()
            status, body, headers = self.preview(base, patient)
            self.assertEqual(status, 200, body)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(body["patient_id"], patient)
            self.assertEqual(body["case_id"], "CASE-LAB-A")
            self.assertEqual(body["mapped_subject_reference"], "Patient/FICTIONAL-PATIENT-A")
            self.assertEqual(body["source_system"], "SYS-FICTIONAL-LIS")
            self.assertEqual(body["specimen_reference"], "Specimen/FICTIONAL-SPECIMEN-A")
            self.assertEqual(body["observations"][0]["value_text"], "4.20")
            self.assertFalse(body["persisted"])
            self.assertFalse(body["verified_identity"])
            self.assertFalse(body["source_version_created"])
            self.assertEqual(body["original_sha256"], hashlib.sha256(encode(example())).hexdigest())
            self.assertEqual(before, self.source_counts())
            self.assertEqual(self.preview(base, patient)[1], body)
            self.assertEqual(before, self.source_counts())

    def test_wrong_subject_and_cross_actor_refused_without_writes(self):
        with running_server(self.app) as base:
            patient = self.make_patient(base)
            before = self.source_counts()
            b = example()
            resource(b, "Observation")["subject"] = {"reference": "Patient/OTHER"}
            self.assertEqual(self.preview(base, patient, b)[0], 422)
            self.assertEqual(self.preview(base, patient, token=TOKEN_B)[0], 404)
            self.assertEqual(before, self.source_counts())

    def test_revoked_case_binding_or_source_grant_does_not_disclose(self):
        with running_server(self.app) as base:
            patient = self.make_patient(base)
            path = f"/v1/patients/{patient}/case-bindings/CASE-LAB-A/revoke"
            self.assertEqual(request(base, path, token=TOKEN_A,
                                     body={"synthetic": True, "reason": "Fictional case revoked"})[0], 200)
            self.assertEqual(self.preview(base, patient)[0], 404)

    def test_mid_preparation_revocation_blocks_response_and_all_writes(self):
        with running_server(self.app) as base:
            patient = self.make_patient(base)
            baseline = self.source_counts()
            from oi_api import laboratory_fhir_routes
            real_parser = laboratory_fhir_routes.prepare_laboratory_bundle

            def change_grant(*args, **kwargs):
                result = real_parser(*args, **kwargs)
                self.creds[0]["actions"] = [x for x in self.creds[0]["actions"]
                                            if x != "source_import"]
                self.write_access()
                return result

            with patch.object(laboratory_fhir_routes, "prepare_laboratory_bundle",
                              side_effect=change_grant):
                self.assertEqual(self.preview(base, patient)[0], 404)
            self.assertEqual(self.source_counts(), baseline)

    def test_persisted_bundle_uses_canonical_source_custody_and_typed_world_model(self):
        with running_server(self.app) as base:
            patient = self.make_patient(base)
            raw = encode(example()).decode("utf-8")
            status, receipt, _ = self.import_source(base, patient)
            self.assertEqual(status, 201, receipt)
            self.assertFalse(receipt["duplicate"])
            self.assertEqual(receipt["version"], 1)
            self.assertEqual(receipt["observation_count"], 1)
            self.assertEqual(receipt["original_sha256"], hashlib.sha256(raw.encode()).hexdigest())
            source_id = receipt["source_id"]
            self.assertEqual(self.lab_counts(), (1, 1, 1, 1))

            source_url = f"/v1/patients/{patient}/cases/CASE-LAB-A/sources"
            code, index, _ = request(base, source_url, token=TOKEN_A)
            self.assertEqual(code, 200, index)
            self.assertEqual(index["sources"][0]["source_id"], source_id)
            self.assertEqual(index["sources"][0]["kind"], "laboratory")
            self.assertEqual(index["source_reported_assertions"], [])

            code, original, _ = request(base, source_url + "/" + source_id, token=TOKEN_A)
            self.assertEqual(code, 200, original)
            self.assertEqual(original["original_text"], raw)
            self.assertEqual(original["sha256"], hashlib.sha256(raw.encode()).hexdigest())

            code, world, _ = request(
                base, f"/v1/patients/{patient}/cases/CASE-LAB-A/world-model", token=TOKEN_A)
            self.assertEqual(code, 200, world)
            self.assertEqual(world["observations"], [])
            self.assertEqual(world["summary"]["current_laboratory_observations"], 1)
            self.assertEqual(world["summary"]["current_observations"], 1)
            self.assertEqual(len(world["laboratory_observations"]), 1)
            lab = world["laboratory_observations"][0]
            self.assertEqual(lab["source_id"], source_id)
            self.assertEqual(lab["loinc_code"], "777-3")
            self.assertEqual(lab["value_text"], "4.20")
            self.assertEqual(lab["unit_code"], "10*9/L")
            self.assertEqual(lab["review_state"], "not_established")
            self.assertIsNone(lab["clinical_meaning"])
            self.assertEqual(world["laboratory_timeline"][0]["observation_reference"],
                             "Observation/FICTIONAL-OBS-A")
            self.assertEqual(world["laboratory_timeline"][0]["clinical_interpretation"],
                             "not_performed")

    def test_exact_retry_and_changed_bundle_require_explicit_amendment(self):
        with running_server(self.app) as base:
            patient = self.make_patient(base)
            first = self.import_source(base, patient)
            self.assertEqual(first[0], 201, first[1])
            source_id = first[1]["source_id"]
            retry = self.import_source(base, patient)
            self.assertEqual(retry[0], 200, retry[1])
            self.assertTrue(retry[1]["duplicate"])
            self.assertEqual(retry[1]["source_id"], source_id)
            self.assertEqual(retry[1]["original_sha256"], first[1]["original_sha256"])
            self.assertEqual(self.lab_counts(), (1, 1, 1, 1))

            changed = example()
            resource(changed, "Observation")["valueQuantity"]["value"] = 5
            self.assertEqual(self.import_source(base, patient, changed)[0], 409)
            self.assertEqual(self.import_source(
                base, patient, changed, request_key="LAB-IMPORT-TWO")[0], 409)
            status, amended, _ = self.import_source(
                base, patient, changed, request_key="LAB-IMPORT-TWO",
                expected_previous_source_id=source_id)
            self.assertEqual(status, 201, amended)
            self.assertEqual(amended["version"], 2)
            self.assertNotEqual(amended["source_id"], source_id)
            self.assertEqual(self.lab_counts(), (2, 2, 2, 2))

            world = request(
                base, f"/v1/patients/{patient}/cases/CASE-LAB-A/world-model",
                token=TOKEN_A)[1]
            self.assertEqual(world["history"][0]["source_id"], source_id)
            self.assertEqual(world["current_sources"][0]["version"], 2)
            self.assertEqual(world["laboratory_observations"][0]["value_text"], "5")
            # Exact retry of the original historical command remains valid, but
            # a fresh request key may not resurrect superseded bytes as current.
            self.assertEqual(self.import_source(
                base, patient, request_key="LAB-STALE-REPLAY")[0], 409)
            replay = self.import_source(base, patient)
            self.assertEqual((replay[0], replay[1]["source_id"], replay[1]["version"]),
                             (200, source_id, 1))
            self.assertTrue(replay[1]["duplicate"])
            self.assertEqual(self.lab_counts(), (2, 2, 2, 2))

    def test_import_revocation_after_preparation_rolls_back_all_source_and_lab_rows(self):
        with running_server(self.app) as base:
            patient = self.make_patient(base)
            from oi_api import laboratory_fhir_routes
            real_parser = laboratory_fhir_routes.prepare_laboratory_bundle

            def revoke(*args, **kwargs):
                result = real_parser(*args, **kwargs)
                self.creds[0]["actions"] = [x for x in self.creds[0]["actions"]
                                            if x != "source_import"]
                self.write_access()
                return result

            with patch.object(laboratory_fhir_routes, "prepare_laboratory_bundle",
                              side_effect=revoke):
                self.assertEqual(self.import_source(base, patient)[0], 404)
            self.assertEqual(self.lab_counts(), (0, 0, 0, 0))

    def test_lab_schema_is_forward_only_and_dependent_on_canonical_source_owner(self):
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text(
                "SELECT version_num FROM public.alembic_version")).scalar_one(),
                             SCHEMA_REVISION)
            self.assertEqual(c.execute(text(
                "SELECT to_regclass('clinical_source.fhir_laboratory_sources')")).scalar_one(),
                             "clinical_source.fhir_laboratory_sources")
            self.assertEqual(c.execute(text(
                "SELECT to_regclass('clinical_source.fhir_laboratory_observations')")).scalar_one(),
                             "clinical_source.fhir_laboratory_observations")

    def prepare_lab_question(self, base, patient, source_id, fingerprint, *, token=TOKEN_A,
                             observation_reference="Observation/FICTIONAL-OBS-A", case="CASE-LAB-A"):
        return request(
            base, f"/v1/patients/{patient}/cases/{case}/composer/laboratory-preflight",
            token=token,
            body={"synthetic": True, "source_id": source_id,
                  "observation_reference": observation_reference,
                  "expected_source_snapshot_sha256": fingerprint,
                  "question": "What should I ask my care team about this source-reported result?"})

    def lab_question_fixture(self, base):
        self.creds[0]["actions"].append("composer_context_read")
        self.write_access()
        patient = self.make_patient(base)
        status, receipt, _ = self.import_source(base, patient)
        self.assertEqual(status, 201, receipt)
        status, world, _ = request(
            base, f"/v1/patients/{patient}/cases/CASE-LAB-A/world-model", token=TOKEN_A)
        self.assertEqual(status, 200, world)
        return patient, receipt["source_id"], world["snapshot_fingerprint"]

    def test_lab_question_preparation_is_typed_audited_and_not_persisted(self):
        with running_server(self.app) as base:
            patient, source, fingerprint = self.lab_question_fixture(base)
            before = self.lab_counts()
            event_count = self.source_counts()[1]
            code, first, headers = self.prepare_lab_question(base, patient, source, fingerprint)
            self.assertEqual(code, 200, first)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            selected = first["selected_source"]
            self.assertEqual(selected["anchor_kind"], "fhir_observation")
            self.assertEqual(selected["source_id"], source)
            self.assertEqual(selected["resource_reference"], "Observation/FICTIONAL-OBS-A")
            self.assertEqual(selected["specimen_reference"], "Specimen/FICTIONAL-SPECIMEN-A")
            self.assertEqual(selected["report_reference"], "DiagnosticReport/FICTIONAL-REPORT-A")
            self.assertEqual(selected["value_text"], "4.20")
            self.assertNotIn("line", selected)
            self.assertFalse(first["durable_question_created"])
            self.assertFalse(first["model_execution_authorized"])
            self.assertEqual(before, self.lab_counts())
            self.assertEqual(self.source_counts()[1], event_count + 1)
            with self.engine.connect() as db:
                self.assertEqual(db.execute(text("SELECT count(*) FROM investigation.source_questions")).scalar_one(), 0)
            code, repeated, _ = self.prepare_lab_question(base, patient, source, fingerprint)
            self.assertEqual(code, 200, repeated)
            self.assertEqual(repeated["preflight_sha256"], first["preflight_sha256"])
            self.assertNotEqual(repeated["access_receipt_id"], first["access_receipt_id"])
            # Typed values do not grant access to the separate original endpoint.
            self.creds[0]["actions"].remove("source_original_read")
            self.write_access()
            self.assertEqual(self.prepare_lab_question(base, patient, source, fingerprint)[0], 200)
            self.assertEqual(request(base, f"/v1/patients/{patient}/cases/CASE-LAB-A/sources/{source}", token=TOKEN_A)[0], 404)

    def test_lab_question_preparation_requires_current_independent_grants_and_scope(self):
        with running_server(self.app) as base:
            patient, source, fingerprint = self.lab_question_fixture(base)
            before = self.source_counts()
            for grant in ("patient_read", "source_read", "composer_context_read"):
                with self.subTest(grant=grant):
                    self.creds[0]["actions"].remove(grant)
                    self.write_access()
                    self.assertEqual(self.prepare_lab_question(base, patient, source, fingerprint)[0], 404)
                    self.assertEqual(self.source_counts(), before)
                    self.creds[0]["actions"].append(grant)
                    self.write_access()
            self.assertEqual(self.prepare_lab_question(base, patient, source, fingerprint, token=TOKEN_B)[0], 404)
            self.assertEqual(self.prepare_lab_question(base, patient, source, fingerprint, case="CASE-OTHER")[0], 404)
            self.assertEqual(self.source_counts(), before)

    def test_lab_question_preparation_rejects_amended_snapshot_and_old_anchor(self):
        with running_server(self.app) as base:
            patient, original_source, fingerprint = self.lab_question_fixture(base)
            code, old, _ = self.prepare_lab_question(base, patient, original_source, fingerprint)
            self.assertEqual(code, 200, old)
            changed = example()
            resource(changed, "Observation")["valueQuantity"]["value"] = 5
            code, amended, _ = self.import_source(
                base, patient, changed, request_key="LAB-QUESTION-AMENDMENT",
                expected_previous_source_id=original_source)
            self.assertEqual(code, 201, amended)
            self.assertEqual(self.prepare_lab_question(base, patient, original_source, fingerprint)[0], 409)
            _, world, _ = request(base, f"/v1/patients/{patient}/cases/CASE-LAB-A/world-model", token=TOKEN_A)
            new_fingerprint = world["snapshot_fingerprint"]
            self.assertEqual(self.prepare_lab_question(base, patient, original_source, new_fingerprint)[0], 409)
            code, fresh, _ = self.prepare_lab_question(base, patient, amended["source_id"], new_fingerprint)
            self.assertEqual(code, 200, fresh)
            self.assertEqual(fresh["selected_source"]["value_text"], "5")
            self.assertNotEqual(fresh["preflight_sha256"], old["preflight_sha256"])
            self.assertEqual(old["selected_source"]["value_text"], "4.20")
            self.assertEqual(world["history"][0]["source_id"], original_source)

    def test_lab_question_preparation_revocation_after_serialization_withholds_all(self):
        from oi_api import laboratory_fhir_routes as routes
        with running_server(self.app) as base:
            patient, source, fingerprint = self.lab_question_fixture(base)
            before = self.source_counts()
            real_response = routes.JSONResponse
            def revoke_after_serialization(*args, **kwargs):
                response = real_response(*args, **kwargs)
                self.creds[0]["actions"].remove("composer_context_read")
                self.write_access()
                return response
            with patch.object(routes, "JSONResponse", revoke_after_serialization):
                status, body, _ = self.prepare_lab_question(base, patient, source, fingerprint)
            self.assertEqual(status, 404)
            self.assertNotIn("4.20", json.dumps(body))
            self.assertEqual(self.source_counts(), before)

    def test_lab_question_preparation_audit_tail_denial_and_serialization_failure_roll_back(self):
        from open_intelligence.postgres_registry import PostgresPatientRegistry
        from oi_api import laboratory_fhir_routes as routes
        with running_server(self.app) as base:
            patient, source, fingerprint = self.lab_question_fixture(base)
            before = self.source_counts()
            original_append = PostgresPatientRegistry.append_event
            def revoke_after_audit(registry, patient_id, event_type, **refs):
                result = original_append(registry, patient_id, event_type, **refs)
                if event_type == "source.read_authorized":
                    self.creds[0]["actions"].remove("composer_context_read")
                    self.write_access()
                return result
            with patch.object(PostgresPatientRegistry, "append_event", revoke_after_audit):
                status, body, _ = self.prepare_lab_question(base, patient, source, fingerprint)
            self.assertEqual(status, 404)
            self.assertEqual(self.source_counts(), before)
            self.creds[0]["actions"].append("composer_context_read")
            self.write_access()
            with patch.object(routes, "JSONResponse", side_effect=RuntimeError("Fictional serialization failure")):
                status, body, _ = self.prepare_lab_question(base, patient, source, fingerprint)
            self.assertEqual(status, 503)
            self.assertEqual(self.source_counts(), before)
            self.assertNotIn("4.20", json.dumps(body))


if __name__ == "__main__":
    unittest.main()
