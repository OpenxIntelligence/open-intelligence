"""Research source custody survives the operations worker's outbox upgrade."""
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.case_bindings import CanonicalCaseBindings
from oi_api.composer_runs import PostgresComposerRuns
from oi_api.migrate import migrate
from oi_api.sources import PostgresSourceVersions
from open_intelligence.patient_registry import PatientRegistryDenied
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_source_versions import SourceVersionFixture, ORIGINAL, AMENDED


class ResearchSourceMigrationTests(SourceVersionFixture):
    def test_pre_outbox_research_history_survives_upgrade_and_amendment(self):
        migrate(self.admin, 'downgrade', 'base')
        migrate(self.admin, 'upgrade', '0019_composer_runs')
        pooled = self.engine.raw_connection()
        self.addCleanup(pooled.close)
        registry = PostgresPatientRegistry(pooled.driver_connection, lambda *args: True)
        common = dict(organization='ORG-ALPHA', actor='ACTOR-ALPHA', purpose='research')
        options = dict(**common, recheck_authority=lambda: None)
        patient = registry.create_patient(**common, request_key='RESEARCH-UPGRADE')['patient_id']
        CanonicalCaseBindings(registry).bind(patient, **common, case_id='CASE-ALPHA',
            source_organization='ORG-SYNTH', source_system='SYS-SYNTH',
            source_subject_ref='SUBJECT-SYNTH', review_ref='REVIEW-SYNTH')
        source = PostgresSourceVersions(registry).import_original(
            patient, 'CASE-ALPHA', ORIGINAL.encode(), **options)['source_id']
        migrate(self.admin, 'upgrade', 'head')
        migrate(self.admin, 'upgrade', 'head')
        owner = PostgresSourceVersions(registry)
        self.assertTrue(owner.import_original(patient, 'CASE-ALPHA', ORIGINAL.encode(), **options)['duplicate'])
        amended = owner.import_original(patient, 'CASE-ALPHA', AMENDED.encode(), **options)['source_id']
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text('SELECT purpose,source_id FROM coordination.source_event_outbox ORDER BY event_id')).all(),
                             [('research', source), ('research', amended)])
        with self.assertRaises(PatientRegistryDenied):
            PostgresComposerRuns(registry).source_events().claim_next(patient, 'CASE-ALPHA', **options)
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text('SELECT count(*) FROM coordination.source_event_deliveries')).scalar_one(), 0)
        with self.assertRaises(DBAPIError), self.engine.begin() as db:
            db.execute(text("INSERT INTO coordination.source_event_deliveries "
                "(delivery_id,event_id,consumer,patient_id,case_id,origin_org,actor,purpose) "
                "SELECT 'DELIVERY-' || repeat('A',32),event_id,'composer-source-context/1',patient_id,case_id,"
                "origin_org,'ACTOR-ALPHA','research' FROM coordination.source_event_outbox LIMIT 1"))

    def test_existing_operations_schema_receives_research_compatibility(self):
        migrate(self.admin, 'downgrade', '0026_integrated_core')
        # Reproduce the exact legacy outbox guard and constraint on an empty
        # published schema. The bootstrap fix alone must not satisfy this test.
        with self.engine.begin() as db:
            db.execute(text('ALTER TABLE coordination.source_event_outbox DROP CONSTRAINT source_event_outbox_purpose_check'))
            db.execute(text("ALTER TABLE coordination.source_event_outbox ADD CONSTRAINT source_event_outbox_purpose_check CHECK(purpose='operations')"))
            definition = db.execute(text("SELECT pg_get_functiondef('coordination.guard_source_event_outbox()'::regprocedure)")).scalar_one()
            db.exec_driver_sql(definition.replace("b.purpose IN ('operations','research')", "b.purpose='operations'"))
        migrate(self.admin, 'upgrade', 'head')
        self.creds[0]['purpose'] = 'research'
        self.write()
        from http_support import running_server
        from oi_api.app import create_app
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, result, _ = self.ingest(base, patient)
            self.assertEqual(status, 201, result)
