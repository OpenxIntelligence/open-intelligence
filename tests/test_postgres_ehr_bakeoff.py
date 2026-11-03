"""B-01c actual encounter/note workflows: SQLite oracle versus PostgreSQL.

Uses independently authored invented notes only. No clinical or PHI clearance.
Live tests run only with the existing controlled PG_BAKEOFF_DSN.
"""
from concurrent.futures import ThreadPoolExecutor
import asyncio
import importlib.util
import json
from pathlib import Path
import sqlite3
import unittest
import uuid
from unittest.mock import patch

from open_intelligence.clinical_encounters import (
    ClinicalEncounters, ClinicalConflict, ClinicalAuthorizationError,
)
from open_intelligence.patient_registry import PatientRegistry, PatientRegistryDenied
from open_intelligence.postgres_registry import PostgresPatientRegistry
from open_intelligence.store import InvalidInput
from test_postgres_registry_bakeoff import DSN, REQUIRE, asyncpg, pg8000, pg_connection

MODULE = "open_intelligence.postgres_encounters"
AVAILABLE = importlib.util.find_spec(MODULE) is not None
if AVAILABLE:
    from open_intelligence.postgres_encounters import PostgresClinicalEncounters, _Rows
ROOT = Path(__file__).resolve().parents[1]
ACTOR = dict(actor="CLINICIAN-ONE", purpose="care")


class EHRPortAvailabilityTests(unittest.TestCase):
    def test_existing_state_machine_can_be_used_on_postgres(self):
        # A missing adapter would leave production workflow portability absent.
        self.assertTrue(AVAILABLE, "PostgreSQL encounter/note persistence is missing")
        self.assertTrue(issubclass(PostgresClinicalEncounters, ClinicalEncounters))


class PostgresEHRParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DSN or asyncpg is None or pg8000 is None:
            if REQUIRE:
                raise AssertionError("B-01c requires live PostgreSQL and pinned drivers")
            raise unittest.SkipTest("PostgreSQL service not configured locally")
        if not AVAILABLE:
            raise AssertionError("PostgreSQL EHR port missing")
        async def install():
            db = await asyncpg.connect(dsn=DSN)
            try:
                for name in ("001_contract.sql", "002_registry_port.sql", "003_encounter_port.sql"):
                    await db.execute((ROOT / "tools/research/postgres_bakeoff" / name).read_text())
            finally:
                await db.close()
        asyncio.run(install())

    def setUp(self):
        self.db = pg_connection()
        self.addCleanup(self.db.close)
        self.policy = lambda actor, patient, action, purpose: actor == ACTOR["actor"]
        self.pg = PostgresPatientRegistry(self.db, self.policy)
        self.org = "SITE-" + uuid.uuid4().hex.upper()
        self.pid = self.pg.create_patient(organization=self.org, request_key="CREATE-ONE", **ACTOR)["patient_id"]
        self.ehr = PostgresClinicalEncounters(self.pg, self.policy)
        sql = sqlite3.connect(":memory:")
        sql.row_factory = sqlite3.Row  # Oracle uses the same named-row contract as CaseStore.
        self.addCleanup(sql.close)
        self.oracle_registry = PatientRegistry(sql, self.policy)
        self.sid = self.oracle_registry.create_patient(organization=self.org, request_key="CREATE-ONE", **ACTOR)["patient_id"]
        self.oracle = ClinicalEncounters(self.oracle_registry, self.policy)

    def count(self, table, patient_id=None):
        # Table names here are test-owned constants, never caller identifiers.
        with self.pg.transaction():
            return self.pg._fetchone(f"SELECT count(*) FROM {table} WHERE patient_id=%s", (patient_id or self.pid,))[0]

    def start(self, ehr=None, pid=None, key="ENCOUNTER-ONE"):
        ehr, pid = ehr or self.ehr, pid or self.pid
        scheduled = ehr.schedule(pid, key, "outpatient", "2026-11-01", request_key="SCHEDULE-" + key, **ACTOR)
        ehr.transition(pid, scheduled["encounter_id"], "in_progress", expected_revision=1,
                       request_key="START-" + key, **ACTOR)
        return scheduled["encounter_id"]

    def test_full_note_lifecycle_matches_sqlite_original(self):
        normalized = []
        for ehr, pid in ((self.oracle, self.sid), (self.ehr, self.pid)):
            eid = self.start(ehr, pid)
            body = "Independently invented engineering note: observation pending."
            d = ehr.write_note(pid, eid, "NOTE-ONE", body, expected_version=0, request_key="DRAFT-ONE", **ACTOR)
            a = ehr.attest_note(pid, eid, "NOTE-ONE", expected_version=1, request_key="ATTEST-ONE", **ACTOR)
            c = ehr.write_note(pid, eid, "NOTE-ONE", "Corrected invented observation.", expected_version=2,
                               correction_reason="Correct fictional transcription", request_key="CORRECT-ONE", **ACTOR)
            f = ehr.attest_note(pid, eid, "NOTE-ONE", expected_version=3, request_key="REATTEST-ONE", **ACTOR)
            self.assertEqual([d["status"],a["status"],c["status"],f["status"]],
                             ["draft","attested","draft_correction","attested_correction"])
            history = ehr.note_history(pid, eid, "NOTE-ONE", **ACTOR)
            self.assertEqual(history[0]["body"], body)
            self.assertEqual(history[1]["body"], body)
            self.assertEqual([r["version"] for r in history], [1,2,3,4])
            self.assertTrue(all(isinstance(r["created_at"], str) for r in history))
            for previous, current in zip(history, history[1:]):
                self.assertEqual(current["supersedes_id"], previous["id"])
            normalized.append([{k:r[k] for k in ("version","status","body","sha256","authored_by","amendment_reason")} for r in history])
            complete = ehr.transition(pid,eid,"completed",expected_revision=2,request_key="COMPLETE-ONE",**ACTOR)
            self.assertEqual(complete["revision"],3)
            row = ehr.list_encounters(pid, **ACTOR)[0]
            self.assertEqual((row["status"], row["service_date"]), ("completed", "2026-11-01"))
        self.assertEqual(normalized[0], normalized[1])
        with self.pg.transaction():
            events = self.pg._fetchall("SELECT metadata_json FROM identity.identity_domain_events WHERE patient_id=%s", (self.pid,))
        self.assertNotIn("invented observation", json.dumps(events))

    def test_idempotent_retry_survives_reconnect_and_conflicting_intent_denied(self):
        args=dict(patient_id=self.pid,external_key="ENCOUNTER-ONE",kind="outpatient",service_date="2026-11-01",request_key="SCHEDULE-ONE",**ACTOR)
        result = self.ehr.schedule(**args)
        db = pg_connection(); self.addCleanup(db.close)
        other = PostgresClinicalEncounters(PostgresPatientRegistry(db,self.policy),self.policy)
        self.assertEqual(other.schedule(**args),result)
        with self.assertRaises(ClinicalConflict):
            other.schedule(**dict(args,kind="telehealth"))
        self.assertEqual(self.count("ehr.clinical_encounter_commands"),1)
        self.assertEqual(self.count("identity.identity_domain_events"),2)

    def test_cross_patient_and_untrusted_access_rejected(self):
        eid = self.start()
        second = self.pg.create_patient(organization=self.org,request_key="CREATE-TWO",**ACTOR)["patient_id"]
        with self.assertRaises(InvalidInput):
            self.ehr.note_history(second,eid,"NOTE-ONE",**ACTOR)
        with self.assertRaises(ClinicalAuthorizationError):
            PostgresClinicalEncounters(self.pg).list_encounters(self.pid,**ACTOR)
        with self.assertRaises(ClinicalAuthorizationError):
            self.ehr.list_encounters(self.pid,actor="UNTRUSTED",purpose="care")

    def test_optimistic_revision_and_attested_correction_rules_preserved(self):
        eid=self.start()
        with self.assertRaises(ClinicalConflict):
            self.ehr.transition(self.pid,eid,"completed",expected_revision=1,request_key="STALE-REVISION",**ACTOR)
        self.ehr.write_note(self.pid,eid,"NOTE-ONE","Original invented note",expected_version=0,request_key="DRAFT-ONE",**ACTOR)
        self.ehr.attest_note(self.pid,eid,"NOTE-ONE",expected_version=1,request_key="ATTEST-ONE",**ACTOR)
        with self.assertRaises(ClinicalConflict):
            self.ehr.write_note(self.pid,eid,"NOTE-ONE","Overwrite",expected_version=2,request_key="INVALID-CORRECTION",**ACTOR)
        self.assertEqual(len(self.ehr.note_history(self.pid,eid,"NOTE-ONE",**ACTOR)),2)

    def test_failed_event_rolls_back_state_note_header_and_receipt(self):
        eid=self.start(); before=self.count("ehr.clinical_encounter_commands")
        original=self.pg.append_event
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise RuntimeError("injected event delivery failure")
        self.pg.append_event=fail
        with self.assertRaises(RuntimeError):
            self.ehr.write_note(self.pid,eid,"NOTE-ONE","Rollback invented note",expected_version=0,request_key="ROLLBACK-NOTE",**ACTOR)
        self.pg.append_event=original
        self.assertEqual(self.ehr.note_history(self.pid,eid,"NOTE-ONE",**ACTOR),[])
        self.assertEqual(self.count("ehr.clinical_encounter_commands"),before)
        self.assertEqual(self.count("identity.identity_domain_events"),3)

    def test_database_denies_history_and_command_receipt_rewrite(self):
        eid=self.start()
        self.ehr.write_note(self.pid,eid,"NOTE-ONE","Immutable invented note",expected_version=0,request_key="DRAFT-ONE",**ACTOR)
        history=self.ehr.note_history(self.pid,eid,"NOTE-ONE",**ACTOR)
        for query,params in (
            ("UPDATE ehr.clinical_note_versions SET body='tampered' WHERE id=%s",(history[0]["id"],)),
            ("DELETE FROM ehr.clinical_note_versions WHERE id=%s",(history[0]["id"],)),
            ("UPDATE ehr.clinical_encounter_commands SET result_json='{}' WHERE patient_id=%s",(self.pid,)),
        ):
            with self.assertRaises(Exception):
                with self.pg.transaction(): self.pg._execute(query,params)
        self.assertEqual(self.ehr.note_history(self.pid,eid,"NOTE-ONE",**ACTOR),history)

    def test_concurrent_duplicate_schedule_creates_one_encounter_and_event(self):
        def submit(_):
            db=pg_connection()
            try:
                svc=PostgresClinicalEncounters(PostgresPatientRegistry(db,self.policy),self.policy)
                return svc.schedule(self.pid,"ENCOUNTER-ONE","outpatient","2026-11-01",request_key="SCHEDULE-ONE",**ACTOR)
            finally: db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(submit,range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.count("ehr.clinical_encounters"),1)
        self.assertEqual(self.count("ehr.clinical_encounter_commands"),1)
        self.assertEqual(self.count("identity.identity_domain_events"),2)

    def test_concurrent_stale_note_writers_have_one_winner(self):
        eid=self.start()
        def submit(i):
            db=pg_connection()
            try:
                svc=PostgresClinicalEncounters(PostgresPatientRegistry(db,self.policy),self.policy)
                try:
                    svc.write_note(self.pid,eid,"NOTE-ONE",f"Invented draft {i}",expected_version=0,request_key=f"DRAFT-CONCURRENT-{i}",**ACTOR)
                    return "saved"
                except ClinicalConflict: return "conflict"
            finally: db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(submit,range(2)))
        self.assertCountEqual(outcomes,["saved","conflict"])
        self.assertEqual(len(self.ehr.note_history(self.pid,eid,"NOTE-ONE",**ACTOR)),1)

    def test_revocation_before_command_commit_rolls_back_all_writes(self):
        allowed={"yes":True}; self.ehr.authorizer=lambda *_:allowed["yes"]
        original=self.pg.append_event
        def revoke(*args,**kwargs):
            original(*args,**kwargs); allowed["yes"]=False
        self.pg.append_event=revoke
        with self.assertRaises(ClinicalAuthorizationError):
            self.ehr.schedule(self.pid,"ENCOUNTER-ONE","outpatient","2026-11-01",request_key="SCHEDULE-ONE",**ACTOR)
        self.assertEqual(self.count("ehr.clinical_encounters"),0)
        self.assertEqual(self.count("ehr.clinical_encounter_commands"),0)
        self.assertEqual(self.count("identity.identity_domain_events"),1)

    def test_read_rechecks_permission_before_disclosing_results(self):
        self.start()
        calls=[]
        def revoke_on_second_check(*args):
            calls.append(args); return len(calls)==1
        self.ehr.authorizer=revoke_on_second_check
        with self.assertRaises(ClinicalAuthorizationError):
            self.ehr.list_encounters(self.pid,**ACTOR)

    def test_suspended_patient_cannot_read_or_replay_old_command(self):
        self.start()
        self.pg.suspend_patient(self.pid,expected_revision=1,**ACTOR)
        with self.assertRaises(PatientRegistryDenied):
            self.ehr.list_encounters(self.pid,**ACTOR)
        with self.assertRaises(PatientRegistryDenied):
            self.ehr.schedule(self.pid,"ENCOUNTER-ONE","outpatient","2026-11-01",request_key="SCHEDULE-ENCOUNTER-ONE",**ACTOR)


    def test_real_postgres_current_note_integrity_rejects_tampered_read(self):
        """Live PG domain refuses to attest a mismatched current note body/hash.

        Intercept only the selected returned row to emulate damaged restored
        storage: no immutable trigger is disabled on a shared test database.
        All commands and other reads still execute on real PostgreSQL.
        """
        eid = self.start()
        self.ehr.write_note(self.pid, eid, "NOTE-ONE", "Original independent synthetic note",
                            expected_version=0, request_key="DRAFT-CORRUPT-ONE", **ACTOR)
        original = self.ehr._execute

        def inject_corrupt_body(sql, parameters=()):
            result = original(sql, parameters)
            if "JOIN clinical_note_versions v" in sql and "v.sha256" in sql:
                row = result.fetchone()
                if row is not None:
                    altered = dict(row)
                    altered["body"] = "Altered synthetic note after its source hash"
                    return _Rows([altered])
            return result

        with patch.object(self.ehr, "_execute", side_effect=inject_corrupt_body):
            with self.assertRaisesRegex(ClinicalConflict, "integrity"):
                self.ehr.attest_note(self.pid, eid, "NOTE-ONE",
                                     expected_version=1, request_key="ATTEST-CORRUPT-ONE", **ACTOR)
        self.assertEqual(len(self.ehr.note_history(self.pid, eid, "NOTE-ONE", **ACTOR)), 1)
        self.assertEqual(self.count("ehr.clinical_encounter_commands"), 3)

    def test_real_postgres_historical_notes_fail_closed_on_digest_mismatch(self):
        """A historical-row discrepancy is rejected before client disclosure."""
        eid = self.start()
        self.ehr.write_note(self.pid, eid, "NOTE-ONE", "First fictional version",
                            expected_version=0, request_key="DRAFT-HISTORY-ONE", **ACTOR)
        self.ehr.write_note(self.pid, eid, "NOTE-ONE", "Second fictional version",
                            expected_version=1, request_key="DRAFT-HISTORY-TWO", **ACTOR)
        original = self.ehr._execute

        def inject_historical_corruption(sql, parameters=()):
            result = original(sql, parameters)
            if "JOIN clinical_note_versions v" in sql and "ORDER BY v.version" in sql:
                rows = result.fetchall()
                if rows:
                    rows[0] = dict(rows[0], body="Altered historical fictional text")
                return _Rows(rows)
            return result

        with patch.object(self.ehr, "_execute", side_effect=inject_historical_corruption):
            with self.assertRaisesRegex(ClinicalConflict, "integrity"):
                self.ehr.note_history(self.pid, eid, "NOTE-ONE", **ACTOR)
        self.assertEqual(len(self.ehr.note_history(self.pid, eid, "NOTE-ONE", **ACTOR)), 2)



if __name__ == "__main__":
    unittest.main()
