"""B-01b first-party PatientRegistry parity on live PostgreSQL 17 and 18.

The existing SQLite PatientRegistry is the *behavioral* oracle. The alternative
PostgreSQL persistence port is tested with disposable invented IDs; it does
not qualify identity proof, informed consent, clinical-signing or PHI security.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from urllib.parse import urlsplit, unquote
import uuid

from open_intelligence.patient_registry import (
    PatientRegistry, PatientRegistryDenied, PatientRegistryError,
    PatientRegistryConflict,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

BASE = Path(__file__).resolve().parents[1]
SQL1 = BASE / "tools/research/postgres_bakeoff/001_contract.sql"
SQL2 = BASE / "tools/research/postgres_bakeoff/002_registry_port.sql"
DSN = os.environ.get("PG_BAKEOFF_DSN", "")
REQUIRE = os.environ.get("PG_BAKEOFF_REQUIRE") == "1"
try:
    import pg8000.dbapi
    import asyncpg
except ImportError:
    pg8000 = None
    asyncpg = None


def pg_connection():
    url = urlsplit(DSN)
    if url.scheme not in ("postgresql", "postgres") or not url.hostname:
        raise ValueError("Missing controlled PostgreSQL test DSN")
    return pg8000.dbapi.connect(
        host=url.hostname, port=url.port or 5432,
        user=unquote(url.username or ""),
        password=unquote(url.password or ""),
        database=(url.path or "").lstrip("/"),
        timeout=6,
    )


class StaticRegistryPortTests(unittest.TestCase):
    def test_one_canonical_patient_table_and_immutable_history(self):
        sql = SQL2.read_text()
        self.assertNotIn("CREATE TABLE identity.identity_patients", sql)
        self.assertIn("identity.identity_create_receipts", sql)
        self.assertIn("identity.identity_domain_events", sql)
        self.assertIn("oi_identity_receipts_no_update", sql)
        self.assertIn("oi_identity_events_no_delete", sql)
        self.assertIn("oi_registry_receipt_check_origin", sql)
        self.assertIn("oi_patient_identity_guard", sql)

    def test_deduplicated_business_contract_from_existing_registry(self):
        source = (BASE / "src/open_intelligence/postgres_registry.py").read_text()
        self.assertIn("PatientRegistry._allow(self", source)
        self.assertIn("_digest({", source)
        self.assertNotIn("CREATE TABLE", source)
        self.assertNotIn("DB_PASSWORD", source)


class PostgresRegistryParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DSN or asyncpg is None or pg8000 is None:
            if REQUIRE:
                raise AssertionError("Real B-01b PostgreSQL requires DSN and both pinned drivers")
            raise unittest.SkipTest("Only static B-01b checks run without PostgreSQL service")
        async def init():
            admin = await asyncpg.connect(dsn=DSN)
            try:
                await admin.execute(SQL1.read_text())
                await admin.execute(SQL2.read_text())
            finally:
                await admin.close()
        asyncio.run(init())

    def setUp(self):
        self.db = pg_connection()
        self.assertIs(self.db.autocommit, False)
        self.addCleanup(self.db.close)
        self.sql = sqlite3.connect(":memory:")
        self.addCleanup(self.sql.close)
        self.policy = lambda actor, subject, action, purpose: actor == "CLINICIAN-ONE"
        self.pg = PostgresPatientRegistry(self.db, self.policy)
        self.sqlite = PatientRegistry(self.sql, self.policy)
        self.org = "SITE-" + uuid.uuid4().hex.upper()
        self.req = "REQ-" + uuid.uuid4().hex.upper()

    def data(self, **overrides):
        fields = dict(organization=self.org, actor="CLINICIAN-ONE",
                      purpose="care", request_key=self.req)
        fields.update(overrides)
        return fields

    def count(self, query: str, params: tuple = ()) -> int:
        with self.pg.transaction():
            return self.pg._fetchone(query, params)[0]

    def test_real_sqlite_and_postgres_creation_read_list_parity(self):
        result_pg = self.pg.create_patient(**self.data())
        result_sqlite = self.sqlite.create_patient(**self.data())
        for result in (result_pg, result_sqlite):
            self.assertFalse(result["duplicate"])
            self.assertTrue(result["patient_id"].startswith("PAT-"))
        for reg, result in ((self.pg, result_pg), (self.sqlite, result_sqlite)):
            self.assertEqual(reg.create_patient(**self.data()),
                             {"patient_id": result["patient_id"], "duplicate": True})
            p = reg.get_patient(result["patient_id"], actor="CLINICIAN-ONE", purpose="care")
            self.assertEqual((p["origin_org"], p["revision"], p["status"]),
                             (self.org, 1, "active"))
            self.assertEqual(reg.list_patients(organization=self.org, actor="CLINICIAN-ONE",purpose="care"),
                             [{"patient_id": result["patient_id"], "status":"active","revision":1}])
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_patients WHERE origin_org=%s",
                                    (self.org,)), 1)
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_domain_events WHERE patient_id=%s",
                                    (result_pg["patient_id"],)), 1)

    def test_missing_authorizer_and_untrusted_actor_denied(self):
        for reg in (PostgresPatientRegistry(self.db), PatientRegistry(self.sql)):
            with self.assertRaises(PatientRegistryDenied):
                reg.create_patient(**self.data())
        with self.assertRaises(PatientRegistryDenied):
            self.pg.create_patient(**self.data(actor="UNTRUSTED"))
        with self.assertRaises(PatientRegistryDenied):
            self.pg.create_patient(**self.data(purpose="unknown"))
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_patients WHERE origin_org=%s",(self.org,)),0)

    def test_request_digest_rejects_actor_or_purpose_reuse(self):
        self.pg.authorizer = lambda *_: True
        self.sqlite.authorizer = lambda *_: True
        p = self.pg.create_patient(**self.data())
        self.sqlite.create_patient(**self.data())
        for reg in (self.pg, self.sqlite):
            with self.assertRaises(PatientRegistryConflict):
                reg.create_patient(**self.data(actor="CLINICIAN-TWO"))
            with self.assertRaises(PatientRegistryConflict):
                reg.create_patient(**self.data(purpose="research"))
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_patients WHERE origin_org=%s",(self.org,)),1)
        self.assertEqual(self.pg.create_patient(**self.data())["patient_id"],p["patient_id"])

    def test_immutable_events_and_receipts_with_revisioned_suspension(self):
        patient = self.pg.create_patient(**self.data())["patient_id"]
        result = self.pg.suspend_patient(patient, actor="CLINICIAN-ONE", purpose="care", expected_revision=1)
        self.assertEqual(result,{"patient_id":patient,"revision":2,"status":"suspended"})
        with self.assertRaises(PatientRegistryDenied):
            self.pg.require_patient(patient)
        with self.assertRaises(PatientRegistryConflict):
            self.pg.suspend_patient(patient,actor="CLINICIAN-ONE",purpose="care",expected_revision=1)
        for sql, params in (
           ("DELETE FROM identity.identity_create_receipts WHERE patient_id=%s",(patient,)),
           ("UPDATE identity.identity_domain_events SET event_type='forged' WHERE patient_id=%s",(patient,)),
        ):
            with self.assertRaises(Exception):
                with self.pg.transaction():
                    self.pg._execute(sql,params)
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_domain_events WHERE patient_id=%s",(patient,)),2)

    def test_event_append_requires_same_transaction_and_rolls_back(self):
        pid = self.pg.create_patient(**self.data())["patient_id"]
        with self.assertRaises(PatientRegistryError):
            self.pg.append_event(pid,"clinical.encounter.started",encounter_id="ENC-ONE")
        enc_key="B01B-"+uuid.uuid4().hex
        try:
            with self.assertRaisesRegex(RuntimeError,"abort"):
                with self.pg.transaction():
                    eid=self.pg._fetchone(
                      "INSERT INTO ehr.clinical_encounters(patient_id,external_key,kind,service_date) "
                      "VALUES (%s,%s,'outpatient',DATE '2026-11-02') RETURNING id",
                      (pid,enc_key))[0]
                    self.pg.append_event(pid,"clinical.encounter.started",encounter_id=eid)
                    raise RuntimeError("abort entire encounter and event")
            self.assertEqual(self.count("SELECT count(*) FROM ehr.clinical_encounters WHERE external_key=%s",(enc_key,)),0)
            self.assertEqual(self.count("SELECT count(*) FROM identity.identity_domain_events WHERE patient_id=%s",(pid,)),1)
            with self.pg.transaction():
                self.pg._execute(
                  "INSERT INTO ehr.clinical_encounters(patient_id,external_key,kind,service_date) "
                  "VALUES (%s,%s,'outpatient',DATE '2026-11-02')",
                  (pid,enc_key))
                self.pg.append_event(pid,"clinical.encounter.started",encounter_id="ENC-ONE")
            self.assertEqual(self.count("SELECT count(*) FROM identity.identity_domain_events WHERE patient_id=%s",(pid,)),2)
        finally:
            pass

    def test_speculative_creation_rolls_back_if_event_write_fails(self):
        class Broken(PostgresPatientRegistry):
            def _write_event(self,*_args,**_kwargs):
                raise RuntimeError("forced event-store failure")
        with self.assertRaisesRegex(RuntimeError,"forced"):
            Broken(self.db,self.policy).create_patient(**self.data())
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_patients WHERE origin_org=%s",(self.org,)),0)
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_create_receipts WHERE origin_org=%s",(self.org,)),0)

    def test_concurrent_same_request_has_one_identity_and_event(self):
        def worker(_):
            db=pg_connection()
            try:
                return PostgresPatientRegistry(db,self.policy).create_patient(**self.data())
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            out=list(pool.map(worker,[1,2]))
        self.assertEqual([z["duplicate"] for z in out].count(False),1)
        self.assertEqual([z["duplicate"] for z in out].count(True),1)
        self.assertEqual(out[0]["patient_id"],out[1]["patient_id"])
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_patients WHERE origin_org=%s",(self.org,)),1)
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_domain_events WHERE patient_id=%s",(out[0]["patient_id"],)),1)

    def test_concurrent_same_request_different_intent_is_explicit_conflict(self):
        def worker(actor):
            db=pg_connection()
            try:
                return PostgresPatientRegistry(db,lambda *_:True).create_patient(**self.data(actor=actor))
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=[]
            futures=[pool.submit(worker,actor) for actor in ("CLINICIAN-ONE","CLINICIAN-TWO")]
            for fut in futures:
                try: results.append(fut.result())
                except PatientRegistryConflict: results.append("conflict")
        self.assertEqual(sum(x=="conflict" for x in results),1)
        self.assertEqual(sum(isinstance(x,dict) for x in results),1)
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_patients WHERE origin_org=%s",(self.org,)),1)

    def test_receipt_cannot_link_another_organizations_patient(self):
        pid=self.pg.create_patient(**self.data())["patient_id"]
        with self.assertRaises(Exception):
            with self.pg.transaction():
                self.pg._execute(
                   "INSERT INTO identity.identity_create_receipts "
                   "(origin_org,request_key,request_digest,patient_id) VALUES (%s,%s,%s,%s)",
                   ("UNRELATED-ORG","REQUEST-FOREIGN-"+uuid.uuid4().hex,"a"*64,pid))
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_create_receipts WHERE origin_org='UNRELATED-ORG'"),0)

    def test_canonical_identifier_and_origin_are_database_immutable(self):
        patient=self.pg.create_patient(**self.data())["patient_id"]
        for statement, args in (
            ("UPDATE identity.identity_patients SET origin_org='FORGED' WHERE patient_id=%s", (patient,)),
            ("UPDATE identity.identity_patients SET patient_id='PAT-FORGED' WHERE patient_id=%s", (patient,)),
            ("UPDATE identity.identity_patients SET revision=100 WHERE patient_id=%s", (patient,)),
        ):
            with self.assertRaises(Exception):
                with self.pg.transaction():
                    self.pg._execute(statement, args)
        self.assertEqual(self.pg.get_patient(patient,actor="CLINICIAN-ONE",purpose="care")["revision"],1)

    def test_host_event_body_is_not_permitted_and_nested_tx_denied(self):
        pid=self.pg.create_patient(**self.data())["patient_id"]
        with self.assertRaises(PatientRegistryError):
            with self.pg.transaction():
                self.pg.append_event(pid,"clinical.encounter.started",note="a"*200)
        with self.pg.transaction():
            with self.assertRaises(PatientRegistryError):
                with self.pg.transaction(): pass
        self.assertEqual(self.count("SELECT count(*) FROM identity.identity_domain_events WHERE patient_id=%s",(pid,)),1)

    def test_invalid_requests_are_rejected_in_same_api(self):
        with self.assertRaises(PatientRegistryError):
            self.pg.create_patient(**self.data(request_key="X"))
        pid=self.pg.create_patient(**self.data())["patient_id"]
        with self.assertRaises(PatientRegistryError):
            self.pg.suspend_patient(pid,actor="CLINICIAN-ONE",purpose="care",expected_revision=True)
        with self.assertRaises(PatientRegistryDenied):
            self.pg.get_patient("PAT-UNKNOWN-ID",actor="CLINICIAN-ONE",purpose="care")

if __name__ == "__main__":
    unittest.main()
