"""B-01c: exercise ORIGINAL first-party ClinicalEncounters on live PostgreSQL.

Original SQLite state-machine implementation is not copied or reimplemented.
The PostgreSQL host translates only its existing static SQL and uses the same
canonical PatientRegistry, connection and transaction. Synthetic IDs only.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import sqlite3
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, unquote
import uuid

from open_intelligence.patient_registry import PatientRegistry, PatientRegistryDenied
from open_intelligence.clinical_encounters import (
    ClinicalEncounters, ClinicalConflict, ClinicalAuthorizationError,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry
from open_intelligence.postgres_encounters import PostgresClinicalEncounters
from open_intelligence.store import InvalidInput

BASE = Path(__file__).resolve().parents[1]
SQL_FILES = [BASE / "tools/research/postgres_bakeoff" / x for x in
             ("001_contract.sql", "002_registry_port.sql", "003_encounter_port.sql")]
DSN = os.environ.get("PG_BAKEOFF_DSN", "")
REQUIRE = os.environ.get("PG_BAKEOFF_REQUIRE") == "1"
try:
    import pg8000.dbapi
    import asyncpg
except ImportError:
    pg8000 = None
    asyncpg = None


def db_connection():
    url = urlsplit(DSN)
    if not url.hostname or url.scheme not in ("postgresql", "postgres"):
        raise ValueError("controlled PG_BAKEOFF_DSN required")
    return pg8000.dbapi.connect(
        host=url.hostname, port=url.port or 5432,
        user=unquote(url.username or ""), password=unquote(url.password or ""),
        database=(url.path or "").lstrip("/"), timeout=6,
    )


class StaticPostgresEncounterPortTests(unittest.TestCase):
    def test_adapts_original_business_logic_without_sqlite_ddl_or_parallel_identity(self):
        src = (BASE / "src/open_intelligence/postgres_encounters.py").read_text()
        self.assertIn("class PostgresClinicalEncounters(ClinicalEncounters)", src)
        self.assertIn("registry.append_event(patient_id, kind", src)
        self.assertIn("FOR UPDATE", src)
        self.assertNotIn("CREATE TABLE", src)
        self.assertNotIn("psycopg", src)

    def test_migration_extends_existing_tables_without_second_patient_master(self):
        sql = SQL_FILES[2].read_text()
        self.assertIn("ALTER TABLE ehr.clinical_encounter_commands", sql)
        self.assertIn("oi_note_header_version", sql)
        self.assertNotIn("CREATE TABLE", sql)
        self.assertNotIn("identity.identity_patients (", sql)


class PostgresEncounterParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DSN or pg8000 is None or asyncpg is None:
            if REQUIRE:
                raise AssertionError("B-01c must execute against real PostgreSQL and pinned drivers")
            raise unittest.SkipTest("B-01c needs actual PostgreSQL; only static tests run locally")
        async def setup():
            conn = await asyncpg.connect(dsn=DSN)
            try:
                for f in SQL_FILES:
                    await conn.execute(f.read_text())
            finally:
                await conn.close()
        asyncio.run(setup())

    def setUp(self):
        self.db = db_connection()
        self.addCleanup(self.db.close)
        self.org = "ORG-" + uuid.uuid4().hex.upper()
        self.actor = "idp:clinician-001"
        self.purpose = "care"
        self.args = {"actor": self.actor, "purpose": self.purpose}
        self.policy = lambda actor, subject, action, purpose: (
            actor == self.actor and purpose == self.purpose)
        self.pg = PostgresPatientRegistry(self.db, self.policy)
        self.pid = self.pg.create_patient(
            organization=self.org, actor=self.actor, purpose=self.purpose,
            request_key="REG-" + uuid.uuid4().hex.upper(),
        )["patient_id"]
        self.service = PostgresClinicalEncounters(self.pg, self.policy)
        self.sqlite_connection = sqlite3.connect(":memory:")
        self.sqlite_connection.row_factory = sqlite3.Row
        self.addCleanup(self.sqlite_connection.close)
        self.sqlite = PatientRegistry(self.sqlite_connection, self.policy)
        self.local_pid = self.sqlite.create_patient(
            organization=self.org, actor=self.actor, purpose=self.purpose,
            request_key="REG-" + uuid.uuid4().hex.upper(),
        )["patient_id"]
        self.local_service = ClinicalEncounters(self.sqlite, self.policy)
        self.external = "ENC-" + uuid.uuid4().hex.upper()
        self.req = "CMD-" + uuid.uuid4().hex.upper()

    def count(self, sql, args=()):
        with self.pg.transaction():
            return self.pg._fetchone(sql, args)[0]

    def schedule(self, key=None, service=None, patient=None):
        service = service or self.service
        patient = patient or self.pid
        return service.schedule(patient, self.external, "outpatient", "2026-11-02",
                                request_key=key or self.req, **self.args)

    def begin(self):
        created = self.schedule()
        self.service.transition(self.pid, created["encounter_id"], "in_progress",
                                expected_revision=1,
                                request_key="START-" + uuid.uuid4().hex.upper(), **self.args)
        return created["encounter_id"]

    def test_original_sqlite_and_postgres_end_to_end_state_parity(self):
        p = self.schedule()
        s = self.local_service.schedule(
            self.local_pid, self.external, "outpatient", "2026-11-02",
            request_key=self.req, **self.args)
        for svc, pid, r in ((self.service, self.pid, p),
                            (self.local_service, self.local_pid, s)):
            self.assertEqual(r["status"], "scheduled")
            self.assertEqual(svc.transition(pid, r["encounter_id"], "in_progress",
                                            expected_revision=1,
                                            request_key="CMD-START-0001", **self.args)["revision"], 2)
            note = svc.write_note(pid, r["encounter_id"], "NOTE-001", "Clinical author draft",
                                  expected_version=0, request_key="CMD-DRAFT-0001", **self.args)
            self.assertEqual(note["status"], "draft")
            a = svc.attest_note(pid, r["encounter_id"], "NOTE-001", expected_version=1,
                                request_key="CMD-ATTEST-001", **self.args)
            self.assertEqual(a["status"], "attested")
            with self.assertRaises(ClinicalConflict):
                svc.write_note(pid, r["encounter_id"], "NOTE-001", "Silent rewrite",
                               expected_version=2, request_key="CMD-SILENT-001", **self.args)
            c = svc.write_note(pid, r["encounter_id"], "NOTE-001", "Corrected authored words",
                               expected_version=2, correction_reason="Transcription correction",
                               request_key="CMD-CORRECT-01", **self.args)
            self.assertEqual(c["status"], "draft_correction")
            self.assertEqual(svc.attest_note(pid, r["encounter_id"], "NOTE-001",
                                              expected_version=3, request_key="CMD-REVIEW-001",
                                              **self.args)["status"], "attested_correction")
            h = svc.note_history(pid, r["encounter_id"], "NOTE-001", **self.args)
            self.assertEqual([x["version"] for x in h], [1, 2, 3, 4])
            self.assertEqual(h[0]["body"], "Clinical author draft")
            self.assertEqual(h[3]["supersedes_id"], h[2]["id"])
            self.assertEqual(h[-1]["sha256"], h[-2]["sha256"])
            self.assertEqual(svc.list_encounters(pid, **self.args)[0]["status"], "in_progress")
        self.assertEqual(self.count(
            "SELECT count(*) FROM identity.identity_domain_events WHERE patient_id=%s", (self.pid,)), 7)
        self.assertEqual(self.count(
            "SELECT count(*) FROM ehr.clinical_encounter_commands WHERE patient_id=%s", (self.pid,)), 6)

    def test_duplicate_command_is_byte_identical_after_new_connection(self):
        saved = self.schedule()
        self.assertEqual(self.schedule(), saved)
        db2 = db_connection()
        try:
            registry = PostgresPatientRegistry(db2, self.policy)
            other = PostgresClinicalEncounters(registry, self.policy)
            self.assertEqual(other.schedule(self.pid, self.external, "outpatient", "2026-11-02",
                                            request_key=self.req, **self.args), saved)
            with self.assertRaises(ClinicalConflict):
                other.schedule(self.pid, self.external, "telehealth", "2026-11-02",
                               request_key=self.req, **self.args)
        finally:
            db2.close()
        self.assertEqual(self.count("SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=%s",
                                    (self.pid,)), 1)

    def test_no_authorizer_and_throwing_authorizer_fail_closed(self):
        for auth in (None, lambda *_: (_ for _ in ()).throw(RuntimeError("test"))):
            denied = PostgresClinicalEncounters(self.pg, auth)
            with self.assertRaises(ClinicalAuthorizationError):
                denied.list_encounters(self.pid, **self.args)
            with self.assertRaises(ClinicalAuthorizationError):
                denied.schedule(self.pid, self.external, "outpatient", "2026-11-02",
                                request_key="CMD-DENIED-0001", **self.args)
        self.assertEqual(self.count("SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=%s",
                                    (self.pid,)), 0)

    def test_cross_patient_encounter_and_notes_are_inaccessible(self):
        encounter = self.begin()
        other_patient = self.pg.create_patient(
            organization=self.org, actor=self.actor, purpose="care",
            request_key="REG-OTHER-" + uuid.uuid4().hex.upper(),
        )["patient_id"]
        other = PostgresClinicalEncounters(self.pg, lambda *_: True)
        with self.assertRaises(InvalidInput):
            other.transition(other_patient, encounter, "completed", expected_revision=2,
                             request_key="CMD-CROSS-0001", **self.args)
        with self.assertRaises(InvalidInput):
            other.note_history(other_patient, encounter, "NOTE-001", **self.args)

    def test_transaction_rolls_back_encounter_receipt_and_event_if_event_fails(self):
        with patch.object(self.pg, "_write_event", side_effect=RuntimeError("forced event failure")):
            with self.assertRaisesRegex(RuntimeError, "forced event failure"):
                self.schedule()
        self.assertEqual(self.count("SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=%s",
                                    (self.pid,)), 0)
        self.assertEqual(self.count("SELECT count(*) FROM ehr.clinical_encounter_commands WHERE patient_id=%s",
                                    (self.pid,)), 0)
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_domain_events WHERE patient_id=%s",
                                    (self.pid,)), 1)  # patient creation remains

    def test_postgres_history_is_immutable_and_corrections_required(self):
        encounter = self.begin()
        note = self.service.write_note(self.pid, encounter, "NOTE-001", "Original clinician-authored words",
                                       expected_version=0, request_key="CMD-ORIG-00001", **self.args)
        history = self.service.note_history(self.pid, encounter, "NOTE-001", **self.args)
        for statement, params in (
            ("UPDATE ehr.clinical_note_versions SET body=%s WHERE id=%s", ("forgery", history[0]["id"])),
            ("DELETE FROM ehr.clinical_note_versions WHERE id=%s", (history[0]["id"],)),
            ("DELETE FROM ehr.clinical_encounter_commands WHERE patient_id=%s", (self.pid,)),
        ):
            with self.assertRaises(Exception):
                with self.pg.transaction():
                    self.pg._execute(statement, params)
        self.assertEqual(self.service.note_history(self.pid, encounter, "NOTE-001", **self.args)[0]["sha256"],
                         note["sha256"])
        self.assertEqual(self.count("SELECT count(*) FROM ehr.clinical_encounter_commands WHERE patient_id=%s",
                                    (self.pid,)), 3)

    def test_suspended_patient_cannot_change_or_read_encounter(self):
        self.schedule()
        self.pg.suspend_patient(self.pid, actor=self.actor, purpose="care", expected_revision=1)
        with self.assertRaises(PatientRegistryDenied):
            self.service.list_encounters(self.pid, **self.args)
        with self.assertRaises(PatientRegistryDenied):
            self.schedule(key="CMD-AFTER-SUSPENSION")

    def test_illegal_state_transition_and_stale_revision_are_denied(self):
        encounter = self.begin()
        with self.assertRaises(ClinicalConflict):
            self.service.transition(self.pid, encounter, "completed", expected_revision=1,
                                    request_key="CMD-STALE-00001", **self.args)
        with self.assertRaises(ClinicalConflict):
            self.service.transition(self.pid, encounter, "scheduled", expected_revision=2,
                                    request_key="CMD-REWIND-001", **self.args)
        self.assertEqual(self.service.list_encounters(self.pid, **self.args)[0]["revision"], 2)

    def test_parallel_identical_command_creates_one_encounter_and_one_event(self):
        def create(_):
            db = db_connection()
            try:
                registry = PostgresPatientRegistry(db, self.policy)
                svc = PostgresClinicalEncounters(registry, self.policy)
                return svc.schedule(self.pid, self.external, "outpatient", "2026-11-02",
                                    request_key=self.req, **self.args)
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(create, (0, 1)))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(self.count("SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=%s",
                                    (self.pid,)), 1)
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_domain_events "
                                    "WHERE patient_id=%s AND event_type='clinical_encounter_scheduled'",
                                    (self.pid,)), 1)

    def test_parallel_transition_on_different_keys_has_one_revision_winner(self):
        enc = self.begin()
        def go(index):
            db = db_connection()
            try:
                registry = PostgresPatientRegistry(db, self.policy)
                svc = PostgresClinicalEncounters(registry, self.policy)
                return svc.transition(self.pid, enc, "completed", expected_revision=2,
                                      request_key=f"CMD-RACE-{index:05d}", **self.args)
            except ClinicalConflict:
                return "CONFLICT"
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(go, (1, 2)))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertEqual(results.count("CONFLICT"), 1)
        self.assertEqual(self.service.list_encounters(self.pid, **self.args)[0]["revision"], 3)
