"""Purpose-safe source capture on populated published schemas; actual PG16 only.

The published 0020 backfill remains unchanged. Its refusal of pre-existing
research history is an explicit upgrade hold, not permission to rewrite history.
"""
from contextlib import contextmanager
import json

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.case_bindings import CanonicalCaseBindings
from oi_api.migrate import migrate
from oi_api.sources import PostgresSourceVersions
from open_intelligence.postgres_registry import PostgresPatientRegistry
import test_source_event_migrations as migration_fixture
from test_source_versions import AMENDED, ORIGINAL, SourceVersionFixture


OLD_CORE = "0026_integrated_core"
PRE_CAPTURE = "0019_composer_runs"
CASE = "CASE-ALPHA"
RESEARCH_CASE = "CASE-RESEARCH"
OUTBOX = "coordination.source_event_outbox"
DELIVERIES = "coordination.source_event_deliveries"
HISTORY = "coordination.source_event_delivery_events"
RECEIPTS = "investigation.composer_source_event_receipts"


class SourceEventPurposeUpgradeTests(SourceVersionFixture):
    # Reuse historical SQL writers without inheriting their unittest methods.
    queued = migration_fixture.SourceEventMigrationTests.queued
    event = migration_fixture.SourceEventMigrationTests.event
    claim = migration_fixture.SourceEventMigrationTests.claim
    receipt = migration_fixture.SourceEventMigrationTests.receipt

    @contextmanager
    def owner(self, *, research=False):
        actor = "ACTOR-RESEARCH" if research else "ACTOR-ALPHA"
        purpose = "research" if research else "operations"
        pooled = self.engine.raw_connection()
        try:
            registry = PostgresPatientRegistry(pooled.driver_connection,
                lambda actual_actor, subject, action, actual_purpose:
                    (actual_actor, actual_purpose) == (actor, purpose))
            yield registry, dict(organization="ORG-ALPHA", actor=actor, purpose=purpose)
        finally:
            pooled.driver_connection.rollback()
            pooled.close()

    def snapshot(self):
        """Every owner row and exact sequence state, including EHR tables."""
        schemas = "('identity','coordination','clinical_source','investigation','ehr')"
        with self.engine.connect() as connection:
            tables = {}
            for schema, name in connection.execute(text(
                    "SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN "
                    + schemas + " ORDER BY schemaname,tablename")).all():
                key = f"{schema}.{name}"
                tables[key] = connection.execute(text(
                    f"SELECT to_jsonb(t)::text FROM {key} t ORDER BY 1"
                )).scalars().all()
            sequences = {}
            for schema, name in connection.execute(text(
                    "SELECT schemaname,sequencename FROM pg_sequences WHERE schemaname IN "
                    + schemas + " ORDER BY schemaname,sequencename")).all():
                sequences[f"{schema}.{name}"] = tuple(connection.execute(text(
                    f"SELECT last_value,is_called FROM {schema}.{name}"
                )).one())
        return tables, sequences

    def bind_source(self, *, research=False):
        case = RESEARCH_CASE if research else CASE
        with self.owner(research=research) as (registry, common):
            patient = registry.create_patient(**common,
                request_key="RESEARCH-PATIENT" if research else "OPERATIONS-PATIENT")["patient_id"]
            CanonicalCaseBindings(registry).bind(patient, **common, case_id=case,
                source_organization="ORG-INSTITUTION", source_system="SYS-SYNTH",
                source_subject_ref=case + "-SUBJECT", review_ref=case + "-REVIEW")
            imported = PostgresSourceVersions(registry).import_original(patient, case,
                ORIGINAL.replace(CASE, case).encode(), **common, recheck_authority=lambda: None)
        return patient, imported

    def old_core(self):
        migrate(self.admin, "downgrade", "base")
        migrate(self.admin, "upgrade", OLD_CORE)
        patient, imported = self.bind_source()
        with self.engine.connect() as connection:
            envelope = dict(connection.execute(text(f"SELECT * FROM {OUTBOX}")).mappings().one())
        delivery = self.queued(envelope)
        token = self.claim(delivery)
        with self.engine.begin() as connection:
            self.receipt(connection, delivery, token)
            connection.execute(text(f"UPDATE {DELIVERIES} SET state='delivered',revision=revision+1,"
                "failure_count=0,lease_token=NULL,lease_expires_at=NULL WHERE delivery_id=:d"),
                {"d": delivery})
            self.event(connection, delivery, "delivered")
        return patient, imported, envelope, delivery

    def upgrade_preserving(self):
        before = self.snapshot()
        migrate(self.admin, "upgrade", "head")
        migrate(self.admin, "upgrade", "head")
        self.assertEqual(self.snapshot(), before)

    def research_event(self, patient, source):
        with self.engine.connect() as connection:
            event = connection.execute(text(
                "SELECT id,occurred_at FROM identity.identity_domain_events WHERE patient_id=:p "
                "AND event_type='source.original.imported' AND metadata_json->>'source_id'=:s"),
                {"p": patient, "s": source}).mappings().one()
            self.assertEqual(connection.execute(text(
                "SELECT raw FROM clinical_source.source_versions WHERE source_id=:s"),
                {"s": source}).scalar_one(), ORIGINAL.replace(CASE, RESEARCH_CASE).encode())
        return dict(event)

    def test_populated_old_core_preserves_delivery_history_and_research_custody(self):
        patient, original, envelope, delivery = self.old_core()
        self.upgrade_preserving()
        before = self.snapshot()
        with self.owner() as (registry, common):
            duplicate = PostgresSourceVersions(registry).import_original(patient, CASE,
                ORIGINAL.encode(), **common, recheck_authority=lambda: None)
        self.assertEqual(duplicate["source_id"], original["source_id"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(self.snapshot(), before)

        research_patient, imported = self.bind_source(research=True)
        self.research_event(research_patient, imported["source_id"])
        committed = self.snapshot()
        self.assertEqual(committed[0][OUTBOX], before[0][OUTBOX])
        for table in (DELIVERIES, HISTORY, RECEIPTS):
            self.assertEqual(committed[0][table], before[0][table])
        with self.owner(research=True) as (registry, common):
            duplicate = PostgresSourceVersions(registry).import_original(research_patient,
                RESEARCH_CASE, ORIGINAL.replace(CASE, RESEARCH_CASE).encode(), **common,
                recheck_authority=lambda: None)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["source_id"], imported["source_id"])
        self.assertEqual(self.snapshot(), committed)

        # Operations remain captured after the purpose repair.
        with self.owner() as (registry, common):
            amendment = PostgresSourceVersions(registry).import_original(patient, CASE,
                AMENDED.encode(), **common, recheck_authority=lambda: None)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(f"SELECT source_id FROM {OUTBOX} "
                "WHERE patient_id=:p ORDER BY source_version"), {"p": patient}).scalars().all(),
                [original["source_id"], amendment["source_id"]])
            self.assertEqual(connection.execute(text(f"SELECT state FROM {DELIVERIES} "
                "WHERE delivery_id=:d"), {"d": delivery}).scalar_one(), "delivered")

    def test_research_lineage_is_validated_before_filter_and_cannot_forge_operations_outbox(self):
        operations_patient, original, _, _ = self.old_core()
        self.upgrade_preserving()
        patient, research = self.bind_source(research=True)
        valid = {"case_id": RESEARCH_CASE, "source_id": research["source_id"],
                 "version": 1, "actor": "ACTOR-RESEARCH"}
        event = self.research_event(patient, research["source_id"])
        before = self.snapshot()[0]
        for subject, metadata in (
                (patient, {}), (patient, valid | {"actor": None}),
                (patient, valid | {"version": 999}),
                (operations_patient, valid),
                (patient, valid | {"case_id": CASE}),
                (patient, valid | {"source_id": original["source_id"]})):
            with self.subTest(subject=subject, metadata=metadata), \
                 self.assertRaisesRegex(DBAPIError, "OI-SOURCE-EVENT-(METADATA|LINEAGE)"), \
                 self.engine.begin() as connection:
                connection.execute(text("INSERT INTO identity.identity_domain_events"
                    "(patient_id,event_type,metadata_json) VALUES(:p,'source.original.imported',CAST(:m AS jsonb))"),
                    {"p": subject, "m": json.dumps(metadata)})
            self.assertEqual(self.snapshot()[0], before)

        # This valid research event has no outbox row: uniqueness cannot mask a
        # missing purpose check when forging an operations delivery obligation.
        for purpose in ("operations", "research"):
            with self.subTest(forged_purpose=purpose), self.assertRaises(DBAPIError), \
                 self.engine.begin() as connection:
                connection.execute(text(f"INSERT INTO {OUTBOX}"
                    "(event_id,patient_id,case_id,origin_org,purpose,source_id,source_version,occurred_at) "
                    "VALUES(:event,:patient,:case,'ORG-ALPHA',:purpose,:source,1,:at)"),
                    {"event": event["id"], "patient": patient, "case": RESEARCH_CASE,
                     "purpose": purpose, "source": research["source_id"], "at": event["occurred_at"]})
            self.assertEqual(self.snapshot()[0], before)

    def test_downgrade_restores_old_capture_without_discarding_research_history(self):
        patient, _, _, _ = self.old_core()
        self.upgrade_preserving()
        research_patient, research = self.bind_source(research=True)
        before = self.snapshot()
        migrate(self.admin, "downgrade", OLD_CORE)
        self.assertEqual(self.snapshot(), before)
        with self.engine.connect() as connection:
            self.assertIsNone(connection.execute(text(
                "SELECT to_regprocedure('coordination.source_event_binding(bigint)')")).scalar_one())
            self.assertEqual(connection.execute(text(
                "SELECT version_num FROM public.alembic_version")).scalar_one(), OLD_CORE)
        with self.owner(research=True) as (registry, common):
            with self.assertRaises(DBAPIError):
                PostgresSourceVersions(registry).import_original(research_patient, RESEARCH_CASE,
                    AMENDED.replace(CASE, RESEARCH_CASE).encode(), **common,
                    recheck_authority=lambda: None)
        self.assertEqual(self.snapshot()[0], before[0])
        self.upgrade_preserving()
        with self.owner(research=True) as (registry, common):
            amended = PostgresSourceVersions(registry).import_original(research_patient,
                RESEARCH_CASE, AMENDED.replace(CASE, RESEARCH_CASE).encode(), **common,
                recheck_authority=lambda: None)
        self.assertEqual(amended["version"], 2)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(f"SELECT count(*) FROM {OUTBOX} "
                "WHERE patient_id=:p"), {"p": research_patient}).scalar_one(), 0)
        # Published populated-history guards still prevent discarding the owner.
        with self.assertRaises(CommandError):
            migrate(self.admin, "downgrade", PRE_CAPTURE)

    def test_pre_capture_research_history_holds_upgrade_without_rewriting_history(self):
        migrate(self.admin, "downgrade", "base")
        migrate(self.admin, "upgrade", PRE_CAPTURE)
        patient, research = self.bind_source(research=True)
        before = self.snapshot()
        with self.assertRaises(DBAPIError):
            migrate(self.admin, "upgrade", "head")
        self.assertEqual(self.snapshot(), before)
        self.research_event(patient, research["source_id"])
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT version_num FROM public.alembic_version")).scalar_one(), PRE_CAPTURE)
            self.assertIsNone(connection.execute(text(
                "SELECT to_regclass('coordination.source_event_outbox')")).scalar_one())
            self.assertIsNone(connection.execute(text(
                "SELECT to_regprocedure('coordination.source_event_binding(bigint)')")).scalar_one())
