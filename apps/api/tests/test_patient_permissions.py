from oi_api.contracts import SCHEMA_REVISION
"""Synthetic permission policy acceptance over actual HTTP and PostgreSQL 16."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from alembic.util.exc import CommandError

from oi_api.access import Principal, authentication_for_settings
from oi_api.app import create_app
from oi_api.config import Settings, ConfigurationError
from oi_api.migrate import migrate
from oi_api.patient_permissions import GrantPermission, RevokePermission
from oi_api.worker import run_once
from oi_api.event_worker import run_once as deliver_once
from oi_api.composer_runs import ACTIONS
from http_support import running_server
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture


def grant_payload(**changes):
    return dict(synthetic=True, request_key="GRANT-REQUEST-ONE", authority_ref="AUTHORITY-FICTIONAL",
        actor="ACTOR-ALPHA", purpose="operations", actions=["patient_read"], relationship="patient",
        expires_at=(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat()) | changes


class PermissionContractTests(unittest.TestCase):
    def test_declaration_rejects_implied_administration_and_ambiguous_input(self):
        valid = grant_payload()
        self.assertEqual(GrantPermission(**valid).relationship, "patient")
        for delta in ({"synthetic": False}, {"synthetic": 1}, {"actor": "person@example.org"},
                      {"actions": []}, {"actions": ["patient_create"]},
                      {"actions": ["patient_permissions_manage"]}, {"actions": ["unknown"]},
                      {"expires_at": "2026-12-01T12:00:00"}, {"organization": "ORG-OTHER"},
                      {"relationship": "verified_clinician"}, {"authority_ref": ""}):
            with self.subTest(delta=delta), self.assertRaises(ValidationError):
                GrantPermission(**(valid | delta))
        for revision in (True, "1", 0, 2):
            with self.subTest(revision=revision), self.assertRaises(ValidationError):
                RevokePermission(synthetic=True, request_key="REVOKE-ONE", authority_ref="REF-ONE", expected_revision=revision)

    def test_server_mode_cannot_be_disabled_by_credential(self):
        context = Principal(actor="ACTOR-ONE", organization="ORG-ONE", purpose="operations",
            expires_at=datetime.now(timezone.utc)+timedelta(hours=1), persisted_grants=False)
        class Provider:
            def authenticate(self, token):
                return context
        self.assertTrue(authentication_for_settings(Settings(require_persisted_grants=True), Provider())
                        .authenticate("unused").persisted_grants)
        for value in ("false", "true", "", "2"):
            with self.assertRaises(ConfigurationError):
                Settings.from_env({"OI_API_REQUIRE_PERSISTED_GRANTS": value})


class PermissionHTTPTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"] = sorted(set(self.creds[0]["actions"]) | set(ACTIONS) |
            {"patient_permissions_read", "patient_permissions_manage"})
        self.write()
        self.governed = replace(self.settings, require_persisted_grants=True)

    def url_permissions(self, patient):
        return f"/v1/patients/{patient}/permissions"

    def grant(self, base, patient, payload):
        return request(base, self.url_permissions(patient), token=TOKEN_A, body=payload)

    def revoke(self, base, patient, grant, **changes):
        return request(base, self.url_permissions(patient)+f"/{grant}/revocations", token=TOKEN_A,
            body=dict(synthetic=True, request_key="REVOKE-ONE", authority_ref="AUTHORITY-REVOKED",
                      expected_revision=1) | changes)

    def seed(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
        return patient

    def test_intersection_revocation_and_exact_retry_after_restart(self):
        patient = self.seed(); payload = grant_payload()
        with running_server(create_app(self.governed)) as base:
            self.assertEqual(request(base, f"/v1/patients/{patient}", token=TOKEN_A)[0], 404)
            code, grant, _ = self.grant(base, patient, payload)
            self.assertEqual(code, 200, grant)
            self.assertEqual(request(base, f"/v1/patients/{patient}", token=TOKEN_A)[0], 200)
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
            self.assertEqual(self.grant(base, patient, payload)[1], grant | {"duplicate": True})
            self.assertEqual(self.grant(base, patient, payload | {"relationship": "guardian"})[0], 409)
            self.creds[0]["actions"].remove("patient_read"); self.write()
            self.assertEqual(request(base, f"/v1/patients/{patient}", token=TOKEN_A)[0], 404)
            self.creds[0]["actions"].append("patient_read"); self.write()
            self.assertEqual(self.revoke(base, patient, grant["grant_id"])[0], 200)
        with running_server(create_app(self.governed)) as base:
            self.assertTrue(self.revoke(base, patient, grant["grant_id"])[1]["duplicate"])
            self.assertEqual(request(base, f"/v1/patients/{patient}", token=TOKEN_A)[0], 404)
            code, page, _ = request(base, self.url_permissions(patient), token=TOKEN_A)
            self.assertEqual(code, 200)
            self.assertEqual(page["enforcement"], "persisted_grants")
            self.assertEqual(page["grants"][0]["status"], "revoked")
            self.assertEqual(page["grants"][0]["revision"], 2)
            self.assertEqual(page["grants"][0]["revocation_ref"], "AUTHORITY-REVOKED")

    def test_actor_purpose_patient_and_organization_are_independent_boundaries(self):
        patient = self.seed()
        with running_server(create_app(self.governed)) as base:
            payload = grant_payload(actions=["patient_read", "source_read"])
            self.assertEqual(self.grant(base, patient, payload)[0], 200)
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 200)
            original = dict(self.creds[0])
            for change in ({"actor": "ACTOR-OTHER"}, {"purpose": "research"}, {"organization": "ORG-BETA"}, {"patient_ids": []}):
                self.creds[0] = original | change; self.write()
                self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
            self.creds[0] = original; self.write()
            self.assertEqual(request(base, self.url_permissions(patient), token=TOKEN_B)[0], 404)
            self.assertEqual(self.grant(base, "PAT-UNKNOWN", payload)[0], 404)
            self.assertEqual(self.grant(base, patient, payload | {"actions": ["patient_suspend"]})[0], 404)
            self.assertEqual(self.grant(base, patient, payload | {"expires_at": "2099-01-01T00:00:00Z"})[0], 404)
            self.assertEqual(self.grant(base, patient, payload | {"request_key": "x"*17000})[0], 413)

    def test_concurrent_retry_keeps_one_grant_and_one_event(self):
        patient = self.seed(); payload = grant_payload()
        with running_server(create_app(self.governed)) as base, ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.grant(base, patient, payload), range(2)))
            self.assertEqual([r[0] for r in results], [200, 200])
            self.assertEqual(results[0][1]["grant_id"], results[1][1]["grant_id"])
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT count(*) FROM identity.patient_access_grants")).scalar_one(), 1)
            self.assertEqual(c.execute(text("SELECT count(*) FROM identity.identity_domain_events WHERE event_type='identity.access.granted'")).scalar_one(), 1)

    def test_final_provider_revocation_and_encoding_failure_roll_back_grant(self):
        from oi_api import patient_permission_routes as routes
        patient = self.seed(); payload = grant_payload()
        original = routes.JSONResponse
        def deny_after_encoding(*args, **kwargs):
            response = original(*args, **kwargs)
            self.creds[0]["actions"].remove("patient_permissions_manage"); self.write()
            return response
        with running_server(create_app(self.governed)) as base:
            with patch.object(routes, "JSONResponse", deny_after_encoding):
                self.assertEqual(self.grant(base, patient, payload)[0], 404)
            self.creds[0]["actions"].append("patient_permissions_manage"); self.write()
            with patch.object(routes, "JSONResponse", side_effect=ValueError("PRIVATE-ENCODING")):
                code, value, _ = self.grant(base, patient, payload)
                self.assertEqual(code, 503)
                self.assertNotIn("PRIVATE-ENCODING", json.dumps(value))
            self.assertEqual(request(base, self.url_permissions(patient), token=TOKEN_A)[1]["grants"], [])
            self.assertEqual(self.grant(base, patient, payload)[0], 200)

    def test_expiry_and_both_workers_require_persisted_scope(self):
        import time
        patient = self.seed()
        with running_server(create_app(self.governed)) as base:
            payload = grant_payload(expires_at=(datetime.now(timezone.utc)+timedelta(seconds=2)).isoformat())
            self.assertEqual(self.grant(base, patient, payload)[0], 200)
            self.assertEqual(request(base, f"/v1/patients/{patient}", token=TOKEN_A)[0], 200)
            time.sleep(2.1)
            self.assertEqual(request(base, f"/v1/patients/{patient}", token=TOKEN_A)[0], 404)
            self.assertEqual(request(base, self.url_permissions(patient), token=TOKEN_A)[1]["grants"][0]["status"], "expired")
        for worker in (run_once, deliver_once):
            self.assertEqual(worker(self.governed, lambda: TOKEN_A, patient, "CASE-ALPHA")["status"], "blocked")
        with running_server(create_app(self.governed)) as base:
            grant = self.grant(base, patient, grant_payload(request_key="GRANT-WORKER", actions=list(ACTIONS)))[1]
        self.assertEqual(run_once(self.governed, lambda: TOKEN_A, patient, "CASE-ALPHA")["status"], "idle")
        with running_server(create_app(self.governed)) as base:
            self.assertEqual(self.revoke(base, patient, grant["grant_id"])[0], 200)
        for worker in (run_once, deliver_once):
            self.assertEqual(worker(self.governed, lambda: TOKEN_A, patient, "CASE-ALPHA")["status"], "blocked")

    def test_history_is_immutable_and_populated_downgrade_is_refused(self):
        patient = self.seed()
        with running_server(create_app(self.governed)) as base:
            grant = self.grant(base, patient, grant_payload())[1]
            self.assertEqual(self.revoke(base, patient, grant["grant_id"])[0], 200)
        for table in ("patient_access_grants", "patient_access_revocations"):
            for command in ("DELETE FROM", "TRUNCATE"):
                with self.assertRaises(Exception), self.engine.begin() as c:
                    c.execute(text(f"{command} identity.{table}"))
        with self.assertRaises(CommandError):
            migrate(self.admin, "downgrade", "0028_connected_product")
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(), SCHEMA_REVISION)

    def test_suspension_does_not_prevent_removing_existing_permission(self):
        patient = self.seed()
        with running_server(create_app(self.governed)) as base:
            grant = self.grant(base, patient, grant_payload())[1]
        self.creds[0]["actions"].append("patient_suspend"); self.write()
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(request(base, f"/v1/patients/{patient}/suspensions", token=TOKEN_A,
                body={"synthetic": True, "request_key": "SUSPEND-PERMISSIONS", "expected_revision": 1})[0], 200)
        with running_server(create_app(self.governed)) as base:
            self.assertEqual(self.revoke(base, patient, grant["grant_id"])[0], 200)
            self.assertEqual(request(base, self.url_permissions(patient), token=TOKEN_A)[1]["grants"][0]["status"], "revoked")

    def test_real_dump_restore_preserves_denial_and_retry(self):
        patient = self.seed(); payload = grant_payload()
        with running_server(create_app(self.governed)) as base:
            grant = self.grant(base, patient, payload)[1]
            self.assertEqual(self.revoke(base, patient, grant["grant_id"])[0], 200)
        url = make_url(self.admin.database_url)
        env = dict(os.environ, PGHOST=url.host, PGPORT=str(url.port or 5432), PGUSER=url.username,
                   PGPASSWORD=url.password or "", PGDATABASE=url.database)
        dump = Path(self.temp.name)/"permissions.dump"
        subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--file", str(dump)], env=env,
                       capture_output=True, check=True)
        # Restore the disposable test DB; never point this test at an ordinary DB.
        with self.engine.begin() as c:
            for schema in ("investigation", "clinical_source", "ehr", "coordination", "identity"):
                c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
            c.execute(text("DROP TABLE public.alembic_version"))
        subprocess.run(["pg_restore", "--no-owner", "--exit-on-error", "--dbname", url.database, str(dump)],
                       env=env, capture_output=True, check=True)
        with running_server(create_app(self.governed)) as base:
            self.assertEqual(request(base, f"/v1/patients/{patient}", token=TOKEN_A)[0], 404)
            self.assertTrue(self.grant(base, patient, payload)[1]["duplicate"])
            self.assertTrue(self.revoke(base, patient, grant["grant_id"])[1]["duplicate"])
            row = request(base, self.url_permissions(patient), token=TOKEN_A)[1]["grants"][0]
            self.assertEqual((row["grant_id"], row["status"]), (grant["grant_id"], "revoked"))
