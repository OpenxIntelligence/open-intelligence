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
                   "case_binding_revoke", "source_import")
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


if __name__ == "__main__":
    unittest.main()
