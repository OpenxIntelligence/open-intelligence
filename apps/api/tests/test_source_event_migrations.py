"""Source delivery schema checks; relational evidence requires actual PostgreSQL16."""
from pathlib import Path
import unittest
from alembic.config import Config
from alembic.script import ScriptDirectory
from oi_api.contracts import SCHEMA_REVISION, DatabaseStatus

REVISION = '0020_source_event_delivery'
PARENT = '0019_composer_runs'


class SourceEventGraphTests(unittest.TestCase):
    def test_single_successor_and_exact_readiness(self):
        script = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini')))
        self.assertEqual(script.get_heads(), [SCHEMA_REVISION])
        self.assertEqual(script.get_revision("0030_source_event_recovery").down_revision, "0029_patient_access")
        self.assertEqual(script.get_revision("0029_patient_access").down_revision, "0028_connected_product")
        self.assertEqual(script.get_revision("0027_source_event_purpose").down_revision, "0026_integrated_core")
        self.assertEqual(set(script.get_revision("0026_integrated_core").down_revision), {
            "0025_clinical_source_events", "0023_composer_clinical_join", "0023_ehr_lab_ownership_join",
        })
        self.assertEqual(script.get_revision(REVISION).down_revision, PARENT)
        self.assertEqual(DatabaseStatus(status='ready').required_revision, SCHEMA_REVISION)

import json
import uuid
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from alembic.util.exc import CommandError
from oi_api.migrate import migrate
from oi_api.sources import PostgresSourceVersions
import test_evidence_convergence_migrations as previous
from test_source_versions import SourceVersionFixture, ORIGINAL, AMENDED, DIFFERENT

OUTBOX = 'coordination.source_event_outbox'
DELIVERIES = 'coordination.source_event_deliveries'
EVENTS = 'coordination.source_event_delivery_events'
RECEIPTS = 'investigation.composer_source_event_receipts'


class SourceEventMigrationTests(SourceVersionFixture):
    services = previous.EvidenceConvergenceMigrationTests.services
    start_at = previous.EvidenceConvergenceMigrationTests.start_at
    snapshot = previous.EvidenceConvergenceMigrationTests.snapshot
    upgrade_preserving = previous.EvidenceConvergenceMigrationTests.upgrade_preserving

    def seed(self):
        patient, _, _ = self.start_at(PARENT)
        before = self.snapshot()
        self.upgrade_preserving(before)
        with self.engine.connect() as c:
            envelope = dict(c.execute(text(f'SELECT * FROM {OUTBOX}')).mappings().one())
        return patient, envelope

    def queued(self, envelope):
        delivery = 'DELIVERY-' + uuid.uuid4().hex.upper()
        with self.engine.begin() as c:
            c.execute(text(f'''INSERT INTO {DELIVERIES}
                (delivery_id,event_id,consumer,patient_id,case_id,origin_org,actor,purpose)
                VALUES(:delivery,:event_id,'composer-source-context/1',:patient_id,:case_id,:origin_org,'ACTOR-ALPHA',:purpose)'''),
                {**envelope, 'delivery': delivery})
            self.event(c, delivery, 'queued')
        return delivery

    def event(self, c, delivery, reason):
        c.execute(text(f'''INSERT INTO {EVENTS}(delivery_id,revision,state,attempt_count,failure_count,reason_code)
            SELECT delivery_id,revision,state,attempt_count,failure_count,:reason FROM {DELIVERIES} WHERE delivery_id=:delivery'''),
            {'delivery': delivery, 'reason': reason})

    def claim(self, delivery):
        token = 'LEASE-' + uuid.uuid4().hex.upper()
        with self.engine.begin() as c:
            c.execute(text(f'''UPDATE {DELIVERIES} SET state='running',revision=revision+1,attempt_count=attempt_count+1,
                lease_token=:token,lease_expires_at=clock_timestamp()+interval '30 seconds' WHERE delivery_id=:delivery'''),
                {'delivery': delivery, 'token': token})
            self.event(c, delivery, 'claimed')
        return token

    def receipt(self, c, delivery, token, *, more=False, count=0):
        c.execute(text(f'''INSERT INTO {RECEIPTS}(delivery_id,attempt_count,event_id,claim_token,source_snapshot_contract,
            source_snapshot_sha256,invalidated_count,has_more)
            SELECT delivery_id,attempt_count,event_id,:token,'oi.pg-source-world-model/1',:digest,:count,:more
            FROM {DELIVERIES} WHERE delivery_id=:delivery'''),
            {'delivery': delivery, 'token': token, 'digest': 'a' * 64, 'count': count, 'more': more})

    def test_backfill_preserves_every_existing_row_and_exact_journal_lineage(self):
        patient, e = self.seed()
        with self.engine.connect() as c:
            journal = c.execute(text('SELECT * FROM identity.identity_domain_events WHERE id=:event'), {'event': e['event_id']}).mappings().one()
        self.assertEqual(e['patient_id'], patient)
        self.assertEqual(e['source_id'], journal['metadata_json']['source_id'])
        self.assertEqual(e['source_version'], journal['metadata_json']['version'])
        self.assertEqual(e['occurred_at'], journal['occurred_at'])
        self.assertEqual(e['contract'], 'oi.h1-source-context-event/1')
        self.assertNotIn('actor', e)

    def test_bad_historical_selected_metadata_aborts_upgrade_without_partial_schema(self):
        patient, _, _ = self.start_at(PARENT)
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO identity.identity_domain_events(patient_id,event_type,metadata_json) VALUES(:p,'source.original.imported','{}'::jsonb)"), {'p': patient})
        before = self.snapshot()
        with self.assertRaises(DBAPIError):
            migrate(self.admin, 'upgrade', 'head')
        self.assertEqual(self.snapshot(), before)
        with self.engine.connect() as c:
            self.assertIsNone(c.execute(text("SELECT to_regclass('coordination.source_event_outbox')")).scalar_one())

    def test_live_invalid_journal_lineage_is_atomic(self):
        patient, e = self.seed()
        before = self.snapshot()
        for metadata in ({}, {'case_id': e['case_id'], 'source_id': e['source_id'], 'version': 999, 'actor': 'ACTOR-ALPHA'},
                         {'case_id': 'CASE-WRONG', 'source_id': e['source_id'], 'version': 1, 'actor': 'ACTOR-ALPHA'}):
            with self.assertRaises(DBAPIError), self.engine.begin() as c:
                c.execute(text("INSERT INTO identity.identity_domain_events(patient_id,event_type,metadata_json) VALUES(:p,'source.original.imported',CAST(:m AS jsonb))"), {'p': patient, 'm': json.dumps(metadata)})
        # Identity sequences may advance on rolled-back inserts; committed rows must not.
        self.assertEqual(self.snapshot()[0], before[0])

    def test_duplicate_quarantine_and_failed_response_do_not_emit_outbox(self):
        patient, _ = self.seed()
        with self.engine.connect() as c:
            initial = c.execute(text(f'SELECT count(*) FROM {OUTBOX}')).scalar_one()
        with self.services() as registry:
            owner = PostgresSourceVersions(registry)
            common = dict(organization='ORG-ALPHA', actor='ACTOR-ALPHA', purpose='operations', recheck_authority=lambda: None)
            self.assertTrue(owner.import_original(patient, 'CASE-ALPHA', ORIGINAL.encode(), **common)['duplicate'])
            self.assertEqual(owner.import_original(patient, 'CASE-ALPHA', DIFFERENT.encode(), **common)['result'], 'quarantined')
            before = self.snapshot()[0]
            def fail(_): raise RuntimeError('Synthetic response failure')
            with self.assertRaises(RuntimeError):
                owner.import_original(patient, 'CASE-ALPHA', AMENDED.encode(), **common, prepare_response=fail)
            self.assertEqual(self.snapshot()[0], before)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text(f'SELECT count(*) FROM {OUTBOX}')).scalar_one(), initial)

    def test_outbox_update_delete_truncate_and_forged_scope_rejected(self):
        _, e = self.seed()
        for sql in (f"UPDATE {OUTBOX} SET source_version=99", f'DELETE FROM {OUTBOX}', f'TRUNCATE {OUTBOX} CASCADE'):
            with self.assertRaises(DBAPIError), self.engine.begin() as c: c.execute(text(sql))
        with self.assertRaises(DBAPIError), self.engine.begin() as c:
            c.execute(text(f'''INSERT INTO {DELIVERIES}(delivery_id,event_id,consumer,patient_id,case_id,origin_org,actor,purpose)
                VALUES(:d,:event,'composer-source-context/1',:p,:case,'ORG-WRONG','ACTOR-ALPHA','operations')'''),
                {'d': 'DELIVERY-' + uuid.uuid4().hex.upper(), 'event': e['event_id'], 'p': e['patient_id'], 'case': e['case_id']})

    def test_delivery_requires_each_revision_history_and_receipt_for_ack(self):
        _, e = self.seed(); delivery = self.queued(e); self.claim(delivery)
        with self.assertRaises(DBAPIError), self.engine.begin() as c:
            c.execute(text(f"UPDATE {DELIVERIES} SET state='delivered',revision=revision+1,lease_token=NULL,lease_expires_at=NULL WHERE delivery_id=:d"), {'d': delivery})
        with self.assertRaises(DBAPIError), self.engine.begin() as c:
            c.execute(text(f"UPDATE {DELIVERIES} SET state='dead_letter',failure_count=failure_count+1,revision=revision+1,lease_token=NULL,lease_expires_at=NULL WHERE delivery_id=:d"), {'d': delivery})

    def test_receipt_needs_current_claim_and_atomic_ack(self):
        _, e = self.seed(); delivery = self.queued(e); token = self.claim(delivery)
        for wrong in ('LEASE-' + '0' * 32, token):
            with self.assertRaises(DBAPIError), self.engine.begin() as c:
                self.receipt(c, delivery, wrong)
        with self.engine.begin() as c:
            self.receipt(c, delivery, token)
            c.execute(text(f"UPDATE {DELIVERIES} SET state='delivered',revision=revision+1,failure_count=0,lease_token=NULL,lease_expires_at=NULL WHERE delivery_id=:d"), {'d': delivery})
            self.event(c, delivery, 'delivered')
        for table in (DELIVERIES, EVENTS, RECEIPTS):
            with self.assertRaises(DBAPIError), self.engine.begin() as c: c.execute(text(f'DELETE FROM {table}'))
        with self.assertRaises(DBAPIError), self.engine.begin() as c:
            c.execute(text(f"UPDATE {DELIVERIES} SET state='queued',revision=revision+1 WHERE delivery_id=:d"), {'d': delivery})

    def test_partial_success_has_receipt_and_resets_failure_counter(self):
        _, e = self.seed(); delivery = self.queued(e); token = self.claim(delivery)
        with self.engine.begin() as c:
            self.receipt(c, delivery, token, more=True, count=100)
            c.execute(text(f"UPDATE {DELIVERIES} SET state='queued',revision=revision+1,failure_count=0,lease_token=NULL,lease_expires_at=NULL WHERE delivery_id=:d"), {'d': delivery})
            self.event(c, delivery, 'continued')
        self.claim(delivery)
        with self.engine.connect() as c:
            self.assertEqual(tuple(c.execute(text(f'SELECT attempt_count,failure_count FROM {DELIVERIES}')).one()), (2, 0))

    def test_populated_downgrade_refuses_and_empty_downgrade_preserves_graph(self):
        migrate(self.admin, 'downgrade', PARENT)
        migrate(self.admin, 'upgrade', 'head')
        self.seed()
        before = self.snapshot()
        with self.assertRaises(CommandError): migrate(self.admin, 'downgrade', PARENT)
        self.assertEqual(self.snapshot(), before)

    def test_historical_superseded_sources_and_revoked_binding_backfill(self):
        from oi_api.case_bindings import CanonicalCaseBindings
        patient, _, _ = self.start_at(PARENT)
        with self.services() as registry:
            PostgresSourceVersions(registry).import_original(
                patient, 'CASE-ALPHA', AMENDED.encode(), organization='ORG-ALPHA',
                actor='ACTOR-ALPHA', purpose='operations', recheck_authority=lambda: None)
            CanonicalCaseBindings(registry).revoke(
                patient, 'CASE-ALPHA', organization='ORG-ALPHA', actor='ACTOR-ALPHA',
                reason='Fictional binding revoked before upgrade')
        before = self.snapshot()
        self.upgrade_preserving(before)
        with self.engine.connect() as c:
            versions = c.execute(text(f'SELECT source_version FROM {OUTBOX} ORDER BY source_version')).scalars().all()
        self.assertEqual(versions, [1, 2])

    def test_populated_source_delivery_parent_resumes_queued_delivery_after_join(self):
        from oi_api.event_worker import run_once
        from test_patients import TOKEN_A

        patient, _, _ = self.start_at(REVISION)
        with self.engine.connect() as connection:
            envelope = dict(connection.execute(text(f"SELECT * FROM {OUTBOX}")).mappings().one())
        delivery = self.queued(envelope)
        before = self.snapshot()
        self.upgrade_preserving(before)
        self.creds[0]["actions"].append("source_brief_export")
        self.write()
        self.assertEqual(run_once(self.settings, lambda: TOKEN_A, patient, "CASE-ALPHA"),
                         {"status": "delivered", "attempt_count": 1, "invalidated_count": 0})
        self.assertEqual(run_once(self.settings, lambda: TOKEN_A, patient, "CASE-ALPHA"),
                         {"status": "idle"})
        with self.engine.connect() as connection:
            receipts = connection.execute(text(
                f"SELECT event_id,attempt_count FROM {RECEIPTS} WHERE delivery_id=:id"
            ), {"id": delivery}).all()
        self.assertEqual([tuple(row) for row in receipts], [(envelope["event_id"], 1)])
