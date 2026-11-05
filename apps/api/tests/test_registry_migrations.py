"""Exercise the canonical identity migration on disposable PostgreSQL 16.

Only authored opaque identifiers are used. The injected authorizer is a test
fixture, not authenticated identity, consent, or a qualified database-role policy.
"""

from contextlib import contextmanager
import os
import unittest

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from alembic.util.exc import CommandError

from oi_api.config import Settings
from oi_api.database import make_engine
from oi_api.migrate import migrate
from open_intelligence.postgres_registry import PostgresPatientRegistry


REGISTRY_REVISION = "0012_second_opinion_packets"
BASELINE_REVISION = "0001_h1_shell"
TABLES = {"identity_patients", "identity_create_receipts", "identity_domain_events"}


@unittest.skipUnless(os.environ.get("OI_API_RUN_DATABASE_TESTS") == "1",
                     "Requires explicit disposable PostgreSQL 16 test mode")
class RegistryMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get("OI_API_REGISTRY_MIGRATION_TEST_DATABASE_URL",
                               os.environ.get("OI_API_TEST_DATABASE_URL", ""))
        try:
            name = make_url(value).database
        except Exception:
            raise RuntimeError("A disposable migration test database URL is required") from None
        if not name or not name.startswith("oi_api_test_"):
            raise RuntimeError("Migration tests require an oi_api_test_ database")
        cls.settings = Settings.from_env({"OI_API_DATABASE_URL": value})
        cls.engine = make_engine(cls.settings)
        with cls.engine.connect() as connection:
            version = int(connection.execute(text("SHOW server_version_num")).scalar_one())
        if version // 10000 != 16:
            raise RuntimeError("Migration acceptance requires actual PostgreSQL 16")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self._remove_authored_fixtures()

    def tearDown(self):
        self._remove_authored_fixtures()

    def _remove_authored_fixtures(self):
        # Remove only known test-owned objects. RESTRICT is intentional: an
        # unexpected dependent object must stop cleanup rather than be erased.
        with self.engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS public.oi_registry_external_reference"))
            connection.execute(text("DROP TABLE IF EXISTS coordination.second_opinion_packet_questions"))
            connection.execute(text("DROP TABLE IF EXISTS coordination.second_opinion_packet_sources"))
            connection.execute(text("DROP TABLE IF EXISTS coordination.second_opinion_packets"))
            connection.execute(text("DROP FUNCTION IF EXISTS coordination.guard_second_opinion_packet_question_insert()"))
            connection.execute(text("DROP FUNCTION IF EXISTS coordination.guard_second_opinion_packet_source_insert()"))
            connection.execute(text("DROP FUNCTION IF EXISTS coordination.guard_second_opinion_packet_insert()"))
            connection.execute(text("DROP TABLE IF EXISTS coordination.question_followthrough_events"))
            connection.execute(text("DROP TABLE IF EXISTS coordination.question_followthrough_tasks"))
            connection.execute(text("DROP FUNCTION IF EXISTS coordination.guard_question_followthrough_event_insert()"))
            connection.execute(text("DROP FUNCTION IF EXISTS coordination.guard_question_followthrough_task_insert()"))
            connection.execute(text("DROP TABLE IF EXISTS investigation.question_evidence_links"))
            connection.execute(text("DROP FUNCTION IF EXISTS investigation.guard_question_evidence_insert()"))
            connection.execute(text("DROP TABLE IF EXISTS investigation.evidence_rights_decisions"))
            connection.execute(text("DROP FUNCTION IF EXISTS investigation.guard_evidence_rights_insert()"))
            connection.execute(text("DROP TABLE IF EXISTS investigation.evidence_catalog_records"))
            connection.execute(text("DROP TABLE IF EXISTS investigation.evidence_command_origins"))
            connection.execute(text("DROP FUNCTION IF EXISTS investigation.guard_evidence_command_origin_insert()"))
            connection.execute(text("DROP TABLE IF EXISTS investigation.evidence_commands"))
            connection.execute(text("DROP TABLE IF EXISTS investigation.question_evidence_reports"))
            connection.execute(text("DROP TABLE IF EXISTS investigation.question_evidence_assessments"))
            connection.execute(text("DROP TABLE IF EXISTS investigation.case_evidence_withdrawals"))
            connection.execute(text("DROP TABLE IF EXISTS investigation.case_evidence_versions"))
            connection.execute(text("DROP FUNCTION IF EXISTS investigation.require_evidence_command_origin()"))
            connection.execute(text("DROP FUNCTION IF EXISTS investigation.guard_case_evidence_scope()"))
            connection.execute(text("DROP FUNCTION IF EXISTS investigation.guard_case_evidence_version()"))
            connection.execute(text("DROP FUNCTION IF EXISTS investigation.guard_case_evidence_withdrawal()"))
            connection.execute(text("DROP FUNCTION IF EXISTS investigation.guard_question_evidence_assessment()"))
            connection.execute(text("DROP FUNCTION IF EXISTS investigation.guard_question_evidence_report()"))
            connection.execute(text("DROP TABLE IF EXISTS investigation.question_review_receipts"))
            connection.execute(text("DROP FUNCTION IF EXISTS investigation.guard_review_return_insert()"))
            connection.execute(text("DROP TABLE IF EXISTS investigation.source_questions"))
            connection.execute(text("DROP FUNCTION IF EXISTS investigation.guard_question_insert()"))
            connection.execute(text("DROP SCHEMA IF EXISTS investigation"))
            connection.execute(text("DROP TABLE IF EXISTS clinical_source.assertions"))
            connection.execute(text("DROP TABLE IF EXISTS clinical_source.quarantine"))
            connection.execute(text("DROP TABLE IF EXISTS clinical_source.source_versions"))
            connection.execute(text("DROP FUNCTION IF EXISTS clinical_source.guard_version_history()"))
            connection.execute(text("DROP SCHEMA IF EXISTS clinical_source"))
            connection.execute(text("DROP TABLE IF EXISTS coordination.patient_case_bindings"))
            connection.execute(text("DROP TABLE IF EXISTS coordination.record_requests"))
            connection.execute(text("DROP FUNCTION IF EXISTS coordination.guard_case_binding_origin()"))
            connection.execute(text("DROP FUNCTION IF EXISTS coordination.guard_case_binding_update()"))
            connection.execute(text("DROP FUNCTION IF EXISTS coordination.guard_record_request_origin()"))
            connection.execute(text("DROP FUNCTION IF EXISTS coordination.guard_record_request_update()"))
            connection.execute(text("DROP SCHEMA IF EXISTS coordination"))
            connection.execute(text("DROP TABLE IF EXISTS identity.oi_registry_unrelated_fixture"))
            for name in ("identity_domain_events", "identity_create_receipts", "identity_patients"):
                kind = connection.execute(text(
                    "SELECT c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='identity' AND c.relname=:name"
                ), {"name": name}).scalar_one_or_none()
                if kind is not None:
                    if kind not in ("r", "v"):
                        raise RuntimeError("Unexpected fixture object kind; refusing cleanup")
                    operation = "VIEW" if kind == "v" else "TABLE"
                    connection.execute(text(f"DROP {operation} identity.{name}"))
            for name in ("reject_registry_history_mutation", "guard_registration_receipt",
                         "guard_patient_identity_mutation", "oi_registry_fail_event_fixture"):
                connection.execute(text(f"DROP FUNCTION IF EXISTS identity.{name}()"))
            connection.execute(text("DROP SCHEMA IF EXISTS identity"))
            connection.execute(text("DROP TABLE IF EXISTS public.alembic_version"))

    def _apply_registry(self):
        migrate(self.settings, "upgrade", "head")
        # Missing migration must fail as an unmet contract, not as a later
        # undefined-table error in a registry method.
        self.assertEqual(set(inspect(self.engine).get_table_names(schema="identity")), TABLES,
                         "The canonical patient identity migration has not been applied")

    def _scalar(self, statement):
        with self.engine.connect() as connection:
            return connection.execute(text(statement)).scalar_one()

    @contextmanager
    def _registry(self):
        proxy = self.engine.raw_connection()
        try:
            def synthetic_authorizer(actor, subject, action, purpose):
                return (actor == "ACTOR-MIGRATION" and purpose == "research"
                        and action in {"patient_create", "patient_read", "patient_list", "patient_suspend"})

            yield PostgresPatientRegistry(proxy.driver_connection, synthetic_authorizer)
        finally:
            proxy.rollback()
            proxy.close()

    def _create(self, registry, key="REQUEST-ONE"):
        return registry.create_patient(organization="ORG-ONE", actor="ACTOR-MIGRATION",
                                       purpose="research", request_key=key)

    def test_only_canonical_identity_tables_are_installed(self):
        self._apply_registry()
        schemas = set(inspect(self.engine).get_schema_names())
        self.assertFalse(schemas & {"auth", "ehr", "platform"})
        self.assertEqual(inspect(self.engine).get_table_names(schema="public"), ["alembic_version"])
        self.assertEqual(self._scalar("SELECT version_num FROM public.alembic_version"), REGISTRY_REVISION)
        self.assertEqual(self._scalar(
            "SELECT count(*) FROM information_schema.tables WHERE table_name='identity_patients'"
        ), 1)

    def test_create_duplicate_and_reopen_preserve_identity_receipt_and_event(self):
        self._apply_registry()
        with self._registry() as registry:
            created = self._create(registry)
            self.assertFalse(created["duplicate"])
            self.assertTrue(created["patient_id"].startswith("PAT-"))
            self.assertEqual(self._create(registry), {"patient_id": created["patient_id"], "duplicate": True})
        # Re-open the actual adapter/connection after the original is closed.
        with self._registry() as restarted:
            self.assertEqual(self._create(restarted), {"patient_id": created["patient_id"], "duplicate": True})
            patient = restarted.get_patient(created["patient_id"], actor="ACTOR-MIGRATION", purpose="research")
            self.assertEqual((patient["origin_org"], patient["status"], patient["revision"]), ("ORG-ONE", "active", 1))
        for name in TABLES:
            self.assertEqual(self._scalar(f"SELECT count(*) FROM identity.{name}"), 1)
        self.assertEqual(self._scalar("SELECT event_type FROM identity.identity_domain_events"), "identity.patient.created")

    def test_original_receipt_event_and_patient_origin_cannot_be_rewritten(self):
        self._apply_registry()
        with self._registry() as registry:
            self._create(registry)
        attempts = (
            ("UPDATE identity.identity_create_receipts SET request_key='FORGED-KEY'", "OI-IDENTITY-HISTORY-IMMUTABLE"),
            ("DELETE FROM identity.identity_create_receipts", "OI-IDENTITY-HISTORY-IMMUTABLE"),
            ("UPDATE identity.identity_domain_events SET event_type='forged.event'", "OI-IDENTITY-HISTORY-IMMUTABLE"),
            ("DELETE FROM identity.identity_domain_events", "OI-IDENTITY-HISTORY-IMMUTABLE"),
            ("UPDATE identity.identity_patients SET origin_org='ORG-OTHER'", "OI-PATIENT-IDENTITY-IMMUTABLE"),
            ("UPDATE identity.identity_patients SET status='suspended',revision=3", "OI-PATIENT-STATE"),
        )
        for statement, expected in attempts:
            with self.subTest(statement=statement), self.assertRaisesRegex(SQLAlchemyError, expected):
                with self.engine.begin() as connection:
                    connection.execute(text(statement))
        self.assertEqual(self._scalar("SELECT origin_org FROM identity.identity_patients"), "ORG-ONE")
        self.assertEqual(self._scalar("SELECT count(*) FROM identity.identity_domain_events"), 1)

    def test_creation_receipt_cannot_claim_another_organization(self):
        self._apply_registry()
        with self._registry() as registry:
            self._create(registry)
        with self.assertRaisesRegex(SQLAlchemyError, "OI-REGISTRY-ORG"):
            with self.engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO identity.identity_create_receipts "
                    "(origin_org,request_key,request_digest,patient_id) "
                    "SELECT 'ORG-OTHER','FORGED-KEY',repeat('a',64),patient_id FROM identity.identity_patients"
                ))
        self.assertEqual(self._scalar("SELECT count(*) FROM identity.identity_create_receipts"), 1)

    def test_failed_event_insert_rolls_back_patient_and_receipt(self):
        self._apply_registry()
        with self.engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE FUNCTION identity.oi_registry_fail_event_fixture() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'AUTHORED-EVENT-FAILURE'; END; $$;
                CREATE TRIGGER oi_registry_fail_event_fixture BEFORE INSERT ON identity.identity_domain_events
                FOR EACH ROW EXECUTE FUNCTION identity.oi_registry_fail_event_fixture();
            """)
        with self._registry() as registry:
            with self.assertRaises(Exception) as failure:
                self._create(registry)
            self.assertIn("AUTHORED-EVENT-FAILURE", str(failure.exception))
        for name in TABLES:
            self.assertEqual(self._scalar(f"SELECT count(*) FROM identity.{name}"), 0)

    def test_empty_downgrade_and_reupgrade_preserve_unrelated_objects(self):
        self._apply_registry()
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE identity.oi_registry_unrelated_fixture (id integer PRIMARY KEY)"))
            connection.execute(text("INSERT INTO identity.oi_registry_unrelated_fixture VALUES (42)"))
        migrate(self.settings, "downgrade", BASELINE_REVISION)
        self.assertEqual(set(inspect(self.engine).get_table_names(schema="identity")), {"oi_registry_unrelated_fixture"})
        self.assertEqual(self._scalar("SELECT id FROM identity.oi_registry_unrelated_fixture"), 42)
        migrate(self.settings, "upgrade", "head")
        self.assertEqual(set(inspect(self.engine).get_table_names(schema="identity")), TABLES | {"oi_registry_unrelated_fixture"})
        self.assertEqual(self._scalar("SELECT id FROM identity.oi_registry_unrelated_fixture"), 42)
        with self._registry() as registry:
            self.assertFalse(self._create(registry)["duplicate"])

    def test_downgrade_dependency_failure_keeps_all_owned_objects_and_revision(self):
        self._apply_registry()
        with self.engine.begin() as connection:
            connection.execute(text(
                "CREATE TABLE public.oi_registry_external_reference "
                "(patient_id text REFERENCES identity.identity_patients(patient_id))"
            ))
        with self.assertRaises(SQLAlchemyError):
            migrate(self.settings, "downgrade", BASELINE_REVISION)
        self.assertEqual(set(inspect(self.engine).get_table_names(schema="identity")), TABLES)
        self.assertEqual(self._scalar("SELECT version_num FROM public.alembic_version"), REGISTRY_REVISION)
        self.assertIn("oi_registry_external_reference", inspect(self.engine).get_table_names(schema="public"))

    def test_conflicting_view_is_preserved_and_migration_revision_unchanged(self):
        migrate(self.settings, "upgrade", BASELINE_REVISION)
        with self.engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA identity"))
            # An incompatible existing object is rejected before domain DDL.
            # Preserve both that object and the prior migration revision.
            connection.execute(text("CREATE VIEW identity.identity_create_receipts AS SELECT 1 AS fixture"))
        with self.assertRaises((SQLAlchemyError, CommandError)):
            migrate(self.settings, "upgrade", "head")
        self.assertEqual(inspect(self.engine).get_table_names(schema="identity"), [])
        self.assertEqual(inspect(self.engine).get_view_names(schema="identity"), ["identity_create_receipts"])
        self.assertEqual(self._scalar("SELECT version_num FROM public.alembic_version"), BASELINE_REVISION)

    def test_existing_weakened_patient_table_requires_explicit_reconciliation(self):
        migrate(self.settings, "upgrade", BASELINE_REVISION)
        with self.engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE SCHEMA identity;
                CREATE TABLE identity.identity_patients (
                  patient_id text PRIMARY KEY, origin_org text, created_at timestamptz,
                  created_by text, status text, revision bigint
                );
                INSERT INTO identity.identity_patients VALUES
                  ('SYNTHETIC-LEGACY','ORG-LEGACY',now(),'ACTOR-LEGACY','active',1);
            """)
        with self.assertRaises(CommandError):
            migrate(self.settings, "upgrade", "head")
        self.assertEqual(self._scalar("SELECT version_num FROM public.alembic_version"), BASELINE_REVISION)
        self.assertEqual(inspect(self.engine).get_table_names(schema="identity"), ["identity_patients"])
        self.assertEqual(self._scalar("SELECT patient_id FROM identity.identity_patients"), "SYNTHETIC-LEGACY")


if __name__ == "__main__":
    unittest.main()
