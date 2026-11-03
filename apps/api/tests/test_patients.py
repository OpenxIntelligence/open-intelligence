"""Actual HTTP + PostgreSQL acceptance for the canonical patient boundary.

Every identifier and credential here is independently authored for disposable
synthetic tests. Tokens are local fixtures, not people or clinical authority.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from sqlalchemy import event, text
from sqlalchemy.engine import make_url

from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.database import Database, make_engine
from oi_api.migrate import migrate

from http_support import running_server


TOKEN_A = "synthetic-operations-A-" + "a" * 32
TOKEN_B = "synthetic-operations-B-" + "b" * 32


def request(base, path, *, token=None, body=None, method=None, headers=None):
    supplied = dict(headers or {})
    if token is not None:
        supplied["Authorization"] = "Bearer " + token
    if body is not None:
        supplied["Content-Type"] = "application/json"
    req = Request(base + path, data=None if body is None else json.dumps(body).encode(),
                  method=method, headers=supplied)
    try:
        response = build_opener(ProxyHandler({})).open(req, timeout=5)
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, json.load(response), response.headers


def credential(token, *, organization="ORG-ALPHA", actor="ACTOR-ALPHA", patients=(),
               actions=("patient_create", "patient_read"), expires=None):
    return {"token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "actor": actor, "organization": organization, "purpose": "operations",
            "actions": list(actions), "patient_ids": list(patients),
            "expires_at": (expires or (datetime.now(timezone.utc) + timedelta(hours=1))).isoformat()}


class PatientBoundaryWithoutDatabaseTests(unittest.TestCase):
    def test_missing_trusted_identity_is_denied_before_any_database_operation(self):
        with running_server(create_app(Settings.from_env({}))) as base:
            for token in (None, "unrecognized-token"):
                status, body, headers = request(base, "/v1/patients", token=token,
                                               body={"synthetic": True, "request_key": "REQ-ALPHA"})
                self.assertEqual(status, 401)
                self.assertEqual(body, {"detail": "Authentication required"})
                self.assertEqual(headers["Cache-Control"], "no-store")


@unittest.skipUnless(os.environ.get("OI_API_RUN_DATABASE_TESTS") == "1",
                     "Requires a disposable oi_api_test_* PostgreSQL 16 database")
class PatientHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get("OI_API_TEST_DATABASE_URL", "")
        name = make_url(value).database
        if not name or not name.startswith("oi_api_test_"):
            raise RuntimeError("Patient HTTP tests require a disposable database")
        cls.database_url = value
        cls.admin_settings = Settings(database_url=value)
        cls.engine = make_engine(cls.admin_settings)
        with cls.engine.connect() as conn:
            version = int(conn.execute(text("SELECT current_setting('server_version_num')")).scalar_one())
        if version // 10000 != 16:
            raise RuntimeError("Patient HTTP acceptance requires PostgreSQL 16")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS investigation CASCADE"))
            conn.execute(text("DROP SCHEMA IF EXISTS clinical_source CASCADE"))
            conn.execute(text("DROP SCHEMA IF EXISTS coordination CASCADE"))
            conn.execute(text("DROP SCHEMA IF EXISTS identity CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS public.alembic_version"))
        migrate(self.admin_settings, "upgrade", "head")
        self.directory = tempfile.TemporaryDirectory(prefix="oi-synthetic-access-")
        self.addCleanup(self.directory.cleanup)
        self.access_file = Path(self.directory.name) / "access.json"
        self.credentials = [credential(TOKEN_A), credential(TOKEN_B, organization="ORG-BETA", actor="ACTOR-BETA")]
        self.save_credentials()
        self.settings = Settings.from_env({"OI_API_DATABASE_URL": self.database_url,
                                           "OI_API_ACCESS_FILE": str(self.access_file)})

    def tearDown(self):
        with self.engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS investigation CASCADE"))
            conn.execute(text("DROP SCHEMA IF EXISTS clinical_source CASCADE"))
            conn.execute(text("DROP SCHEMA IF EXISTS coordination CASCADE"))
            conn.execute(text("DROP SCHEMA IF EXISTS identity CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS public.alembic_version"))

    def save_credentials(self):
        pending = self.access_file.with_suffix(".new")
        pending.write_text(json.dumps({"version": "oi.synthetic-access/1", "credentials": self.credentials}))
        pending.chmod(0o600)
        pending.replace(self.access_file)

    def create(self, base, key="REQ-ALPHA", token=TOKEN_A):
        return request(base, "/v1/patients", token=token,
                       body={"synthetic": True, "request_key": key})

    def counts(self):
        with self.engine.connect() as conn:
            return tuple(conn.execute(text("SELECT count(*) FROM identity." + name)).scalar_one()
                         for name in ("identity_patients", "identity_create_receipts", "identity_domain_events"))

    def test_create_retry_granted_read_and_restart_preserve_one_identity(self):
        with running_server(create_app(self.settings)) as base:
            status, first, _ = self.create(base)
            self.assertEqual(status, 201)
            patient = first["patient_id"]
            self.assertTrue(patient.startswith("PAT-"))
            self.assertEqual(first["duplicate"], False)
            self.assertEqual(self.create(base)[:2], (200, {"patient_id": patient, "duplicate": True}))
            self.assertEqual(request(base, "/v1/patients/" + patient, token=TOKEN_A)[0], 404)
            self.credentials[0]["patient_ids"] = [patient]
            self.save_credentials()
            status, body, _ = request(base, "/v1/patients/" + patient, token=TOKEN_A)
            self.assertEqual((status, body["origin_org"], body["revision"]), (200, "ORG-ALPHA", 1))
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(self.create(base)[0:2], (200, {"patient_id": patient, "duplicate": True}))
            self.assertEqual(request(base, "/v1/patients/" + patient, token=TOKEN_A)[1]["patient_id"], patient)
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_authority_overposting_and_real_data_fields_are_rejected_without_echo(self):
        with running_server(create_app(self.settings)) as base:
            for extra in ({"actor": "private-canary"}, {"organization": "private-canary"},
                          {"purpose": "care"}, {"name": "private-canary"}, {"patient_id": "PAT-FORGED"},
                          {"synthetic": False}, {"synthetic": 1}, {"request_key": "x"}):
                with self.subTest(extra=list(extra)):
                    status, body, _ = request(base, "/v1/patients", token=TOKEN_A,
                                             body={"synthetic": True, "request_key": "REQ-ALPHA", **extra})
                    self.assertEqual(status, 422)
                    self.assertNotIn("private-canary", json.dumps(body))
            self.assertEqual(self.create(base)[0], 201)
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_exact_patient_and_organization_grants_are_both_required(self):
        with running_server(create_app(self.settings)) as base:
            patient_a = self.create(base)[1]["patient_id"]
            other_a = self.create(base, "REQ-OTHER")[1]["patient_id"]
            patient_b = self.create(base, token=TOKEN_B)[1]["patient_id"]
            self.credentials[0]["patient_ids"] = [patient_a, patient_b]
            self.save_credentials()
            self.assertEqual(request(base, "/v1/patients/" + patient_a, token=TOKEN_A)[0], 200)
            hidden = []
            for patient in (other_a, patient_b, "PAT-UNKNOWN"):
                hidden.append(request(base, "/v1/patients/" + patient, token=TOKEN_A)[:2])
            self.assertEqual(hidden, [(404, {"detail": "Patient unavailable"})] * 3)
        self.assertEqual(self.counts(), (3, 3, 3))

    def test_permission_failure_cannot_be_overridden_by_forged_identity_headers(self):
        self.credentials[0]["actions"] = ["patient_read"]
        self.save_credentials()
        with running_server(create_app(self.settings)) as base:
            status, _, _ = request(base, "/v1/patients", token=TOKEN_A,
                                   body={"synthetic": True, "request_key": "REQ-ALPHA"},
                                   headers={"X-Actor": "ACTOR-BETA", "X-Organization": "ORG-BETA", "X-Forwarded-User": "admin"})
            self.assertEqual(status, 403)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_access_file_changes_revoke_without_restarting_application(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.create(base)[1]["patient_id"]
            self.credentials[0]["patient_ids"] = [patient]
            self.save_credentials()
            path = "/v1/patients/" + patient
            self.assertEqual(request(base, path, token=TOKEN_A)[0], 200)
            self.credentials[0]["patient_ids"] = []
            self.save_credentials()
            self.assertEqual(request(base, path, token=TOKEN_A)[0], 404)
            self.credentials.pop(0)
            self.save_credentials()
            self.assertEqual(self.create(base, "REQ-REVOKED")[0], 401)
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_expired_or_ambiguous_credentials_fail_closed(self):
        self.credentials[0]["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.save_credentials()
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(self.create(base)[0], 401)
            self.credentials = [credential(TOKEN_A), credential(TOKEN_A, actor="ACTOR-OTHER")]
            self.save_credentials()
            self.assertEqual(self.create(base)[0], 503)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_unavailable_or_invalid_access_file_never_reuses_old_authority(self):
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(self.create(base)[0], 201)
            self.access_file.write_text('{"private-canary":')
            status, body, _ = self.create(base, "REQ-BAD-FILE")
            self.assertEqual(status, 503)
            self.assertNotIn("private-canary", json.dumps(body))
            self.access_file.unlink()
            self.assertEqual(self.create(base, "REQ-MISSING-FILE")[0], 503)
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_actor_change_cannot_reuse_committed_request_intent(self):
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(self.create(base)[0], 201)
            self.credentials[0]["actor"] = "ACTOR-OTHER"
            self.save_credentials()
            self.assertEqual(self.create(base)[0], 409)
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_concurrent_retry_leaves_one_patient_receipt_and_event(self):
        with running_server(create_app(self.settings)) as base:
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: self.create(base), range(2)))
            self.assertEqual(sorted(response[0] for response in responses), [200, 201])
            self.assertEqual(responses[0][1]["patient_id"], responses[1][1]["patient_id"])
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_unknown_migration_revision_refuses_patient_writes(self):
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE public.alembic_version SET version_num='future_revision'"))
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(self.create(base)[0], 503)
            self.assertEqual(request(base, "/health")[0], 200)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_oversized_declared_and_chunked_bodies_are_bounded_before_parsing(self):
        with running_server(create_app(self.settings)) as base:
            large = {"synthetic": True, "request_key": "REQ-LARGE", "data": "x" * 17_000}
            self.assertEqual(request(base, "/v1/patients", token=TOKEN_A, body=large)[0], 413)
            host = base.removeprefix("http://")
            client = http.client.HTTPConnection(host, timeout=5)
            try:
                client.request("POST", "/v1/patients", body=iter([b"x" * 8_000] * 3),
                               headers={"Authorization": "Bearer " + TOKEN_A, "Content-Type": "application/json"},
                               encode_chunked=True)
                response = client.getresponse()
                self.assertEqual(response.status, 413)
                self.assertEqual(json.loads(response.read()), {"detail": "Request body too large"})
            finally:
                client.close()
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_duplicate_auth_headers_and_query_credentials_do_not_authenticate(self):
        with running_server(create_app(self.settings)) as base:
            client = http.client.HTTPConnection(base.removeprefix("http://"), timeout=5)
            try:
                client.putrequest("POST", "/v1/patients")
                client.putheader("Authorization", "Bearer " + TOKEN_A)
                client.putheader("Authorization", "Bearer " + TOKEN_B)
                body = json.dumps({"synthetic": True, "request_key": "REQ-HEADER"}).encode()
                client.putheader("Content-Type", "application/json")
                client.putheader("Content-Length", str(len(body)))
                client.endheaders(body)
                response = client.getresponse()
                self.assertEqual(response.status, 401)
                response.read()
            finally:
                client.close()
            self.assertEqual(request(base, "/v1/patients?token=" + TOKEN_A,
                                     body={"synthetic": True, "request_key": "REQ-QUERY"})[0], 401)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_lost_database_connection_is_returned_even_when_rollback_fails(self):
        database = Database(self.settings)
        self.addCleanup(database.close)
        returned = []
        event.listen(database._engine, "checkin", lambda connection, record: returned.append(record))
        retained = []
        connect = database._engine.raw_connection

        def capture_connection():
            owned = connect()  # Real DB connection; hold it to exclude GC cleanup.
            retained.append(owned)
            return owned

        try:
            with patch.object(database._engine, "raw_connection", side_effect=capture_connection):
                with self.assertRaises(Exception):
                    with database.registry_connection() as connection:
                        cursor = connection.cursor()
                        cursor.execute("SELECT pg_backend_pid()")
                        backend = cursor.fetchone()[0]
                        cursor.close()
                        with self.engine.begin() as admin:
                            self.assertTrue(admin.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": backend}).scalar_one())
                self.assertEqual(len(returned), 1, "Failed request retained an unchecked-in database connection")
        finally:
            for owned in retained:
                owned.close()


if __name__ == "__main__":
    unittest.main()
