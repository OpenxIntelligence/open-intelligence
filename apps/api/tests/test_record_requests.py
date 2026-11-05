"""Real PostgreSQL 16 / FastAPI synthetic record-acquisition acceptance.

Never stores personal medical information. The canonical patient registry
remains authoritative; record receipt is withheld without a source version.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest

from sqlalchemy import text
from sqlalchemy.engine import make_url

from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.database import make_engine
from oi_api.migrate import migrate

from http_support import running_server
from test_patients import request, credential, TOKEN_A, TOKEN_B


@unittest.skipUnless(os.environ.get("OI_API_RUN_DATABASE_TESTS") == "1",
                     "Requires disposable PostgreSQL 16 synthetic test database")
class RecordRequestHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get("OI_API_TEST_DATABASE_URL", "")
        if not (make_url(value).database or "").startswith("oi_api_test_"):
            raise RuntimeError("Record-request acceptance requires disposable oi_api_test_ database")
        cls.settings_admin = Settings(database_url=value)
        cls.engine = make_engine(cls.settings_admin)
        with cls.engine.connect() as c:
            if int(c.execute(text("SHOW server_version_num")).scalar_one()) // 10000 != 16:
                raise RuntimeError("Actual PostgreSQL 16 required")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as c:
            c.execute(text("DROP SCHEMA IF EXISTS investigation CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS clinical_source CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS ehr CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS coordination CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS identity CASCADE"))
            c.execute(text("DROP TABLE IF EXISTS public.alembic_version"))
        migrate(self.settings_admin, "upgrade", "head")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.access_file = Path(self.temp.name) / "access.json"
        self.creds = [credential(TOKEN_A, actions=("patient_create", "patient_read",
                     "record_request_create", "record_request_read", "record_request_cancel")),
                      credential(TOKEN_B, organization="ORG-BETA", actor="ACTOR-BETA",
                     actions=("patient_create", "patient_read", "record_request_create",
                              "record_request_read", "record_request_cancel"))]
        self.write_credentials()
        self.settings = Settings.from_env({
            "OI_API_DATABASE_URL": self.settings_admin.database_url,
            "OI_API_ACCESS_FILE": str(self.access_file),
        })

    def tearDown(self):
        with self.engine.begin() as c:
            c.execute(text("DROP SCHEMA IF EXISTS investigation CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS clinical_source CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS ehr CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS coordination CASCADE"))
            c.execute(text("DROP SCHEMA IF EXISTS identity CASCADE"))
            c.execute(text("DROP TABLE IF EXISTS public.alembic_version"))

    def write_credentials(self):
        target = self.access_file.with_suffix(".next")
        target.write_text(json.dumps({"version": "oi.synthetic-access/1",
                                      "credentials": self.creds}))
        target.replace(self.access_file)

    def setup_patient(self, base, token=TOKEN_A, key="CREATE-ALPHA"):
        code, result, _ = request(base, "/v1/patients", token=token,
                                  body={"synthetic": True, "request_key": key})
        self.assertEqual(code, 201)
        patient = result["patient_id"]
        for c in self.creds:
            if c["token_sha256"] == __import__("hashlib").sha256(token.encode()).hexdigest():
                c["patient_ids"].append(patient)
        self.write_credentials()
        return patient

    def create(self, base, patient, key="RECORD-REQUEST-001", token=TOKEN_A, **overrides):
        data = {"synthetic": True, "request_key": key, "kind": "pathology",
                "record_label": "Fictional pathology document",
                "source_organization": "Fictional laboratory"}
        data.update(overrides)
        return request(base, f"/v1/patients/{patient}/record-requests", body=data, token=token)

    def list(self, base, patient, token=TOKEN_A):
        return request(base, f"/v1/patients/{patient}/record-requests", token=token)

    def test_create_retry_cancel_and_restart_preserve_one_patient_event_history(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_patient(base)
            status, first, _ = self.create(base, patient)
            self.assertEqual((status, first["duplicate"]), (201, False))
            request_id = first["request_id"]
            self.assertEqual(self.create(base, patient)[:2], (200, {"request_id": request_id, "duplicate": True}))
            status, rows, _ = self.list(base, patient)
            self.assertEqual(status, 200)
            self.assertEqual(rows["patient_id"], patient)
            self.assertTrue(rows["source_receipts_enabled"])
            self.assertFalse(rows["external_request_sent"])
            self.assertEqual((rows["requests"][0]["status"], rows["requests"][0]["revision"]), ("requested", 1))
            self.assertEqual(rows["requests"][0]["receipt_status"],
                             "not_received")
            path = f"/v1/patients/{patient}/record-requests/{request_id}/cancel"
            self.assertEqual(request(base, path, token=TOKEN_A, body={
                "synthetic": True, "reason": "No longer needed in fictional exercise"
            })[0], 200)
            self.assertEqual(request(base, path, token=TOKEN_A, body={
                "synthetic": True, "reason": "Already cancelled"
            })[1]["duplicate"], True)
        with running_server(create_app(self.settings)) as restarted:
            value = self.list(restarted, patient)[1]["requests"][0]
            self.assertEqual((value["status"], value["revision"]), ("cancelled", 2))
            self.assertEqual(self.create(restarted, patient)[1]["request_id"], request_id)
            self.assertEqual(self.create(restarted, patient, kind="laboratory")[0], 409)
        with self.engine.connect() as c:
            events = c.execute(text("SELECT event_type FROM identity.identity_domain_events "
                                    "WHERE patient_id=:p ORDER BY id"), {"p": patient}).scalars().all()
            self.assertEqual(events, ["identity.patient.created", "record.request.created", "record.request.cancelled"])
            self.assertEqual(c.execute(text("SELECT count(*) FROM coordination.record_requests")).scalar_one(), 1)

    def test_exact_patient_org_and_independent_action_grants(self):
        with running_server(create_app(self.settings)) as base:
            a = self.setup_patient(base)
            b = self.setup_patient(base, TOKEN_B, "CREATE-BETA")
            self.assertEqual(self.create(base, a, token=TOKEN_B)[0], 404)
            self.assertEqual(self.list(base, a, token=TOKEN_B)[0], 404)
            self.assertEqual(self.create(base, b, token=TOKEN_A)[0], 404)
            self.creds[0]["actions"] = ["patient_create", "patient_read", "record_request_read"]
            self.write_credentials()
            self.assertEqual(self.create(base, a)[0], 404)
            self.assertEqual(self.list(base, a)[0], 200)
            self.creds[0]["actions"] = ["patient_create", "record_request_create"]
            self.write_credentials()
            self.assertEqual(self.create(base, a)[0], 404)
            self.assertEqual(self.list(base, a)[0], 404)
            self.creds[0]["actions"] = ["patient_create", "patient_read", "record_request_create"]
            self.creds[0]["patient_ids"] = []
            self.write_credentials()
            self.assertEqual(self.create(base, a)[0], 404)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT count(*) FROM coordination.record_requests")).scalar_one(), 0)

    def test_invalid_real_data_shape_and_future_source_receipt_fail_closed(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_patient(base)
            for bad in (
                {"synthetic": False}, {"synthetic": 1}, {"patient_id": "PAT-FORGED"},
                {"external_contact": "secret-canary"}, {"source_version_id": 1},
                {"record_label": ""}, {"record_label": "note\nforged"},
                {"kind": "prescription"}, {"request_key": "bad key"},
            ):
                with self.subTest(bad=bad):
                    status, body, _ = self.create(base, patient, **bad)
                    self.assertEqual(status, 422)
                    self.assertNotIn("secret-canary", json.dumps(body))
            self.assertEqual(self.list(base, patient)[1]["requests"], [])
            self.assertEqual(request(
                base, f"/v1/patients/{patient}/record-requests/RECORD-UNKNOWN/receive",
                token=TOKEN_A, body={"source_version_id": 1})[0], 422)

    def test_revoked_credential_and_suspended_patient_never_expose_queue(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_patient(base)
            self.assertEqual(self.create(base, patient)[0], 201)
            self.creds[0]["patient_ids"] = []
            self.write_credentials()
            self.assertEqual(self.list(base, patient)[0], 404)
            self.creds[0]["patient_ids"] = [patient]
            self.write_credentials()
            with self.engine.begin() as c:
                c.execute(text("UPDATE identity.identity_patients SET status='suspended',revision=2 "
                               "WHERE patient_id=:p"), {"p": patient})
            self.assertEqual(self.list(base, patient)[0], 404)
            self.assertEqual(self.create(base, patient, key="RECORD-OTHER-002")[0], 404)

    def test_immutable_request_guard_and_event_failure_rollback(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_patient(base)
            req = self.create(base, patient)[1]["request_id"]
            with self.assertRaises(Exception):
                with self.engine.begin() as c:
                    c.execute(text("UPDATE coordination.record_requests SET record_label='forged'"))
            with self.engine.begin() as c:
                c.execute(text("""CREATE FUNCTION identity.test_fail_acquisition_event() RETURNS trigger
                    LANGUAGE plpgsql AS $$
                    BEGIN IF NEW.event_type='record.request.cancelled' THEN
                      RAISE EXCEPTION 'AUTHORED-ACQUISITION-ROLLBACK';
                    END IF; RETURN NEW; END; $$"""))
                c.execute(text("CREATE TRIGGER test_fail_acquisition_event BEFORE INSERT "
                               "ON identity.identity_domain_events FOR EACH ROW "
                               "EXECUTE FUNCTION identity.test_fail_acquisition_event()"))
            path = f"/v1/patients/{patient}/record-requests/{req}/cancel"
            status, body, _ = request(base, path, token=TOKEN_A, body={
                "synthetic": True, "reason": "Authored cancellation"
            })
            self.assertEqual(status, 503)
            self.assertEqual(body, {"detail": "Patient registry unavailable"})
            self.assertEqual(self.list(base, patient)[1]["requests"][0]["status"], "requested")
            with self.engine.begin() as c:
                c.execute(text("DROP TRIGGER test_fail_acquisition_event ON identity.identity_domain_events"))
                c.execute(text("DROP FUNCTION identity.test_fail_acquisition_event()"))
                self.assertEqual(c.execute(text("SELECT count(*) FROM identity.identity_domain_events "
                                                "WHERE event_type='record.request.cancelled'")).scalar_one(), 0)
