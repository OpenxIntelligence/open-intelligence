"""B-01 real PostgreSQL contract tests: no PHI, no chosen production stack.

Without PG_BAKEOFF_DSN the integration tests are deliberately skipped; CI sets
PG_BAKEOFF_REQUIRE=1 and provisions PostgreSQL 18 as an actual service.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import re
import unittest
import uuid

SQL_FILE = (Path(__file__).resolve().parents[1]
            / "tools/research/postgres_bakeoff/001_contract.sql")
DSN = os.environ.get("PG_BAKEOFF_DSN", "")
REQUIRE = os.environ.get("PG_BAKEOFF_REQUIRE", "") == "1"
TEST_PASSWORD = "oi-b01-disposable-credential"  # ephemeral CI role only

try:
    import asyncpg
except ImportError:
    asyncpg = None


class StaticPostgresContractTests(unittest.TestCase):
    def test_reference_schema_preserves_existing_domain_ownership(self):
        sql = SQL_FILE.read_text()
        for name in (
            "identity.identity_patients", "ehr.clinical_encounters",
            "ehr.clinical_note_headers", "ehr.clinical_note_versions",
            "clinical_source.source_versions", "platform.platform_outbox",
        ):
            self.assertIn(name, sql)
        self.assertNotIn("CREATE TABLE patient_master", sql)
        self.assertNotIn("CREATE EXTENSION", sql)

    def test_document_and_note_history_are_append_only(self):
        sql = SQL_FILE.read_text()
        for symbol in (
            "oi_note_history_update", "oi_note_history_delete",
            "oi_source_history_update", "oi_source_history_delete",
            "oi_commands_update", "oi_commands_delete",
        ):
            self.assertIn(symbol, sql)

    def test_rls_and_purpose_are_explicit_not_claimed_as_identity_proof(self):
        sql = SQL_FILE.read_text()
        self.assertGreaterEqual(sql.count("FORCE ROW LEVEL SECURITY"), 5)
        self.assertIn("role_patient_grants", sql)
        self.assertIn("oi.request_purpose", sql)
        self.assertIn("OI-EVENT-OWNER: encounter", sql)
        self.assertIn("OI-SOURCE-LINEAGE", sql)
        self.assertIn("OI-OUTBOX-IMMUTABLE", sql)
        self.assertIn("SESSION_USER", sql)
        self.assertIn("NOT implemented", sql)
        self.assertNotIn("GRANT ALL ON", sql)


@unittest.skipUnless(DSN and asyncpg is not None,
                     "PostgreSQL integration is required only by the dedicated CI job")
class PostgresDomainIntegrityTests(unittest.IsolatedAsyncioTestCase):
    """The test's explicit disposable roles are NOT real identity/consent proof."""

    async def asyncSetUp(self):
        if REQUIRE and (not DSN or asyncpg is None):
            self.fail("PG_BAKEOFF_REQUIRE=1 requires a live DSN and asyncpg")
        self.admin = await asyncpg.connect(dsn=DSN)
        await self.admin.execute(SQL_FILE.read_text())
        # Test roles are disposable/nonproduction. Cannot become a product user.
        await self.admin.execute(f"""
        DO $create$
        BEGIN
         IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='oi_b01_a') THEN
           CREATE ROLE oi_b01_a LOGIN PASSWORD '{TEST_PASSWORD}';
         END IF;
         IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='oi_b01_b') THEN
           CREATE ROLE oi_b01_b LOGIN PASSWORD '{TEST_PASSWORD}';
         END IF;
        END;
        $create$;
        """)
        await self.admin.execute("""
         GRANT USAGE ON SCHEMA identity,ehr,clinical_source,platform,auth
            TO oi_b01_a,oi_b01_b;
         GRANT SELECT ON identity.identity_patients TO oi_b01_a,oi_b01_b;
         GRANT SELECT,INSERT,UPDATE ON ehr.clinical_encounters TO oi_b01_a,oi_b01_b;
         GRANT SELECT,INSERT,UPDATE ON ehr.clinical_note_headers TO oi_b01_a,oi_b01_b;
         GRANT SELECT,INSERT,UPDATE,DELETE ON ehr.clinical_note_versions
            TO oi_b01_a,oi_b01_b;
         GRANT SELECT ON clinical_source.source_versions TO oi_b01_a,oi_b01_b;
         GRANT USAGE ON ALL SEQUENCES IN SCHEMA ehr TO oi_b01_a,oi_b01_b;
         GRANT EXECUTE ON FUNCTION auth.can_access_patient(text),
           platform.enqueue_event(text,text,text,text,text,bigint),
           ehr.reserve_command(text,text,text) TO oi_b01_a,oi_b01_b;
        """)
        self.p_a = "OI-B01-A-" + uuid.uuid4().hex
        self.p_b = "OI-B01-B-" + uuid.uuid4().hex
        for patient, org in ((self.p_a, "site-one"), (self.p_b, "site-two")):
            await self.admin.execute("""
                INSERT INTO identity.identity_patients
                 (patient_id,origin_org,created_by) VALUES ($1,$2,$3)
            """, patient, org, "b01-fixture")
        await self.admin.execute("""
         INSERT INTO auth.role_patient_grants(database_role,patient_id,purpose)
         VALUES ('oi_b01_a',$1,'care'),('oi_b01_b',$2,'care')
        """, self.p_a, self.p_b)
        self.a = await asyncpg.connect(dsn=DSN, user="oi_b01_a", password=TEST_PASSWORD)
        self.b = await asyncpg.connect(dsn=DSN, user="oi_b01_b", password=TEST_PASSWORD)
        for conn in (self.a,self.b):
            await conn.execute("SELECT set_config('oi.request_purpose','care',false)")

    async def asyncTearDown(self):
        for name in ("a","b","admin"):
            conn = getattr(self,name,None)
            if conn is not None and not conn.is_closed():
                await conn.close()

    async def _insert_encounter(self, conn, patient_id, label="B01-encounter"):
        return await conn.fetchval("""
          INSERT INTO ehr.clinical_encounters
            (patient_id,external_key,kind,service_date,status)
          VALUES ($1,$2,'outpatient',DATE '2026-11-02','scheduled') RETURNING id
        """,patient_id,label+uuid.uuid4().hex)

    async def test_subject_isolation_and_no_anonymous_permission(self):
        own_id = await self._insert_encounter(self.a,self.p_a)
        await self._insert_encounter(self.b,self.p_b)
        self.assertEqual(await self.a.fetchval(
            "SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=$1", self.p_b),0)
        with self.assertRaises(asyncpg.PostgresError):
            await self._insert_encounter(self.a,self.p_b)
        with self.assertRaises(asyncpg.PostgresError):
            await self.a.execute("INSERT INTO auth.role_patient_grants(database_role,patient_id,purpose) VALUES ('oi_b01_a',$1,'research')",self.p_a)
        self.assertIsNotNone(own_id)

    async def test_purpose_and_revocation_fail_closed(self):
        await self._insert_encounter(self.a,self.p_a)
        self.assertEqual(await self.a.fetchval("SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=$1",self.p_a),1)
        await self.a.execute("SELECT set_config('oi.request_purpose','research',false)")
        self.assertEqual(await self.a.fetchval("SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=$1",self.p_a),0)
        await self.a.execute("SELECT set_config('oi.request_purpose','',false)")
        self.assertEqual(await self.a.fetchval("SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=$1",self.p_a),0)
        await self.a.execute("SELECT set_config('oi.request_purpose','care',false)")
        await self.admin.execute("UPDATE auth.role_patient_grants SET revoked_at=now() WHERE patient_id=$1",self.p_a)
        self.assertEqual(await self.a.fetchval("SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=$1",self.p_a),0)
        with self.assertRaises(asyncpg.PostgresError):
            await self.a.fetchval("SELECT platform.enqueue_event($1,$2,$3,$4,$5,$6)",self.p_a,"evt"+uuid.uuid4().hex,"ehr.encounter.changed","ehr","ref",1)

    async def test_suspended_patient_is_inaccessible(self):
        await self._insert_encounter(self.a,self.p_a)
        await self.admin.execute("UPDATE identity.identity_patients SET status='suspended',revision=2 WHERE patient_id=$1",self.p_a)
        self.assertEqual(await self.a.fetchval("SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=$1",self.p_a),0)
        self.assertEqual(await self.a.fetchval("SELECT auth.can_access_patient($1)",self.p_a),False)

    async def test_immutable_note_versions_and_predecessor(self):
        encounter = await self._insert_encounter(self.a,self.p_a)
        note = await self.a.fetchval("""
            INSERT INTO ehr.clinical_note_headers(encounter_id,note_key)
            VALUES ($1,'NOTE-B01-A') RETURNING id
        """,encounter)
        version1 = await self.a.fetchval("""
          INSERT INTO ehr.clinical_note_versions
            (note_id,version,status,body,sha256,authored_by)
          VALUES ($1,1,'draft','fictional document one',$2,'fixture-actor') RETURNING id
        """,note,"a"*64)
        version2 = await self.a.fetchval("""
          INSERT INTO ehr.clinical_note_versions
            (note_id,version,status,body,sha256,authored_by,supersedes_id,amendment_reason)
          VALUES ($1,2,'attested_correction','fictional corrected note',$2,'fixture-actor',$3,'corrected transcription') RETURNING id
        """,note,"b"*64,version1)
        self.assertNotEqual(version1,version2)
        with self.assertRaises(asyncpg.PostgresError):
            await self.admin.execute("UPDATE ehr.clinical_note_versions SET body='silently changed' WHERE id=$1",version1)
        with self.assertRaises(asyncpg.PostgresError):
            await self.admin.execute("DELETE FROM ehr.clinical_note_versions WHERE id=$1",version1)
        with self.assertRaises(asyncpg.PostgresError):
            await self.a.execute("""
              INSERT INTO ehr.clinical_note_versions
                (note_id,version,status,body,sha256,authored_by,supersedes_id)
              VALUES ($1,3,'draft','bad chronology',$2,'fixture-actor',$3)
            """,note,"c"*64,version1)
        self.assertEqual(await self.admin.fetchval("SELECT count(*) FROM ehr.clinical_note_versions WHERE note_id=$1",note),2)

    async def test_outbox_is_atomic_with_clinical_state(self):
        event_id = "evt-b01-"+uuid.uuid4().hex
        ext_key = "B01-rollback-"+uuid.uuid4().hex
        with self.assertRaises(RuntimeError):
            async with self.a.transaction():
                eid=await self.a.fetchval("""
                  INSERT INTO ehr.clinical_encounters(patient_id,external_key,kind,service_date)
                  VALUES ($1,$2,'outpatient',DATE '2026-11-02') RETURNING id
                """,self.p_a,ext_key)
                await self.a.fetchval("SELECT platform.enqueue_event($1,$2,$3,$4,$5,$6)",self.p_a,event_id,"ehr.encounter.scheduled","ehr",str(eid),1)
                raise RuntimeError("simulate command abort after both inserts")
        self.assertEqual(await self.admin.fetchval("SELECT count(*) FROM ehr.clinical_encounters WHERE external_key=$1",ext_key),0)
        self.assertEqual(await self.admin.fetchval("SELECT count(*) FROM platform.platform_outbox WHERE event_id=$1",event_id),0)
        async with self.a.transaction():
            eid=await self._insert_encounter(self.a,self.p_a)
            seq=await self.a.fetchval("SELECT platform.enqueue_event($1,$2,$3,$4,$5,$6)",self.p_a,event_id,"ehr.encounter.scheduled","ehr",str(eid),1)
            self.assertGreater(seq,0)
        self.assertEqual(await self.admin.fetchval("SELECT count(*) FROM platform.platform_outbox WHERE event_id=$1",event_id),1)
        self.assertEqual(await self.admin.fetchval("SELECT count(*) FROM platform.platform_outbox WHERE event_id=$1 AND state='pending'",event_id),1)

    async def test_command_idempotency_hash_conflict(self):
        key = "B01-command-"+uuid.uuid4().hex
        ok=await self.a.fetchval("SELECT ehr.reserve_command($1,$2,$3)",self.p_a,key,"a"*64)
        again=await self.a.fetchval("SELECT ehr.reserve_command($1,$2,$3)",self.p_a,key,"a"*64)
        self.assertEqual((ok,again),(True,False))
        with self.assertRaises(asyncpg.PostgresError):
            await self.a.fetchval("SELECT ehr.reserve_command($1,$2,$3)",self.p_a,key,"b"*64)
        self.assertEqual(await self.admin.fetchval("SELECT count(*) FROM ehr.clinical_encounter_commands WHERE request_key=$1",key),1)
        with self.assertRaises(asyncpg.PostgresError):
            await self.admin.execute("DELETE FROM ehr.clinical_encounter_commands WHERE request_key=$1",key)

    async def test_source_amendment_retains_both_versions(self):
        ref="source-"+uuid.uuid4().hex
        v1=await self.admin.fetchval("""
          INSERT INTO clinical_source.source_versions
            (patient_id,origin_ref,source_version,sha256,authored_at)
          VALUES ($1,$2,1,$3,TIMESTAMPTZ '2026-10-30 11:00:00Z') RETURNING id
        """,self.p_a,ref,"c"*64)
        v2=await self.admin.fetchval("""
          INSERT INTO clinical_source.source_versions
           (patient_id,origin_ref,source_version,sha256,authored_at,supersedes_id)
          VALUES ($1,$2,2,$3,TIMESTAMPTZ '2026-10-31 11:00:00Z',$4) RETURNING id
        """,self.p_a,ref,"d"*64,v1)
        self.assertEqual(await self.a.fetchval("SELECT count(*) FROM clinical_source.source_versions WHERE origin_ref=$1",ref),2)
        self.assertEqual(await self.b.fetchval("SELECT count(*) FROM clinical_source.source_versions WHERE origin_ref=$1",ref),0)
        with self.assertRaises(asyncpg.PostgresError):
            await self.admin.execute("UPDATE clinical_source.source_versions SET sha256=$1 WHERE id=$2","e"*64,v1)
        with self.assertRaises(asyncpg.PostgresError):
            await self.admin.execute("DELETE FROM clinical_source.source_versions WHERE id=$1",v1)
        self.assertNotEqual(v1,v2)

    async def test_duplicate_event_id_is_rejected(self):
        eid = "evt" + uuid.uuid4().hex
        encounter = await self._insert_encounter(self.a,self.p_a)
        await self.a.fetchval("SELECT platform.enqueue_event($1,$2,$3,$4,$5,$6)",self.p_a,eid,"ehr.encounter.updated","ehr",str(encounter),1)
        with self.assertRaises(asyncpg.PostgresError):
            await self.a.fetchval("SELECT platform.enqueue_event($1,$2,$3,$4,$5,$6)",self.p_a,eid,"ehr.encounter.updated","ehr",str(encounter),1)
        self.assertEqual(await self.admin.fetchval("SELECT count(*) FROM platform.platform_outbox WHERE event_id=$1",eid),1)

    async def test_forged_cross_patient_aggregate_cannot_be_published(self):
        wrong_encounter = await self._insert_encounter(self.b,self.p_b)
        with self.assertRaises(asyncpg.PostgresError):
            await self.a.fetchval(
                "SELECT platform.enqueue_event($1,$2,$3,$4,$5,$6)",
                self.p_a,"evt"+uuid.uuid4().hex,
                "ehr.encounter.scheduled","ehr",str(wrong_encounter),1)
        self.assertEqual(await self.admin.fetchval(
            "SELECT count(*) FROM platform.platform_outbox WHERE patient_id=$1",
            self.p_a),0)

    async def test_cross_patient_source_amendment_rejected(self):
        source_a="A-source-"+uuid.uuid4().hex
        source_b="B-source-"+uuid.uuid4().hex
        a1=await self.admin.fetchval("""
          INSERT INTO clinical_source.source_versions
            (patient_id,origin_ref,source_version,sha256,authored_at)
          VALUES($1,$2,1,$3,now()) RETURNING id
        """,self.p_a,source_a,"a"*64)
        b1=await self.admin.fetchval("""
          INSERT INTO clinical_source.source_versions
            (patient_id,origin_ref,source_version,sha256,authored_at)
          VALUES($1,$2,1,$3,now()) RETURNING id
        """,self.p_b,source_b,"b"*64)
        with self.assertRaises(asyncpg.PostgresError):
            await self.admin.execute("""
             INSERT INTO clinical_source.source_versions
               (patient_id,origin_ref,source_version,sha256,authored_at,supersedes_id)
             VALUES($1,$2,2,$3,now(),$4)
            """,self.p_a,source_a,"c"*64,b1)
        with self.assertRaises(asyncpg.PostgresError):
            await self.admin.execute("""
             INSERT INTO clinical_source.source_versions
               (patient_id,origin_ref,source_version,sha256,authored_at,supersedes_id)
             VALUES($1,$2,3,$3,now(),$4)
            """,self.p_a,source_a,"c"*64,a1)
        self.assertEqual(await self.admin.fetchval(
           "SELECT count(*) FROM clinical_source.source_versions WHERE patient_id=$1",
           self.p_a),1)

    async def test_published_event_identity_cannot_be_changed(self):
        encounter=await self._insert_encounter(self.a,self.p_a)
        event="evt"+uuid.uuid4().hex
        await self.a.fetchval(
            "SELECT platform.enqueue_event($1,$2,$3,$4,$5,$6)",
            self.p_a,event,"ehr.encounter.scheduled","ehr",str(encounter),1)
        with self.assertRaises(asyncpg.PostgresError):
            await self.admin.execute(
                "UPDATE platform.platform_outbox SET patient_id=$1 WHERE event_id=$2",
                self.p_b,event)
        # A dispatcher is allowed to change delivery status without rewriting
        # patient, owner, aggregate or revision.
        await self.admin.execute(
            "UPDATE platform.platform_outbox SET state='leased',attempts=attempts+1 WHERE event_id=$1",
            event)
        self.assertEqual(await self.admin.fetchval(
            "SELECT state FROM platform.platform_outbox WHERE event_id=$1",event),
            "leased")

    async def test_simultaneous_command_retry_is_idempotent(self):
        key="B01-concurrent-"+uuid.uuid4().hex
        other=await asyncpg.connect(dsn=DSN,user="oi_b01_a",password=TEST_PASSWORD)
        try:
            await other.execute("SELECT set_config('oi.request_purpose','care',false)")
            async def reserve(conn):
                return await conn.fetchval(
                    "SELECT ehr.reserve_command($1,$2,$3)",self.p_a,key,"a"*64)
            results=await asyncio.gather(reserve(self.a),reserve(other))
            self.assertEqual(sorted(results),[False,True])
            self.assertEqual(await self.admin.fetchval(
                "SELECT count(*) FROM ehr.clinical_encounter_commands WHERE request_key=$1",key),1)
        finally:
            await other.close()

    async def test_second_permissive_driver_read_parity(self):
        try:
            import pg8000.dbapi
        except ImportError:
            if REQUIRE:
                self.fail("Required permissive second driver pg8000 is missing")
            self.skipTest("pg8000 unavailable")
        await self._insert_encounter(self.a,self.p_a)
        def get_counts():
            conn = pg8000.dbapi.connect(host="127.0.0.1",port=5432,
                                        database="oi_bakeoff",user="oi_b01_a",password=TEST_PASSWORD)
            try:
                cur=conn.cursor()
                cur.execute("SELECT set_config('oi.request_purpose','care',false)")
                cur.execute("SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=%s",(self.p_a,))
                own=cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM ehr.clinical_encounters WHERE patient_id=%s",(self.p_b,))
                wrong=cur.fetchone()[0]
                return own,wrong
            finally:
                conn.close()
        self.assertEqual(await asyncio.to_thread(get_counts),(1,0))


if __name__ == "__main__":
    unittest.main()
