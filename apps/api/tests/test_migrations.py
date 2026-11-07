"""Real PostgreSQL checks use an explicitly disposable synthetic database."""

import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from oi_api.app import create_app
from oi_api.config import ConfigurationError, Settings
from oi_api.contracts import SCHEMA_REVISION
from oi_api.database import Database, make_engine
from oi_api.migrate import migrate

from http_support import get_json, running_server

API_ROOT = Path(__file__).resolve().parents[1]


class MigrationCLITests(unittest.TestCase):
    def test_downgrade_requires_disposable_database_and_explicit_test_mode(self):
        for database, mode in (("oi_api_synthetic", "1"), ("oi_api_test_shell", "0")):
            with self.subTest(database=database, mode=mode):
                settings = Settings.from_env({"OI_API_DATABASE_URL": f"postgresql+pg8000://user:secret@localhost/{database}"})
                with patch.dict(os.environ, {"OI_API_RUN_DATABASE_TESTS": mode}), patch("oi_api.migrate.make_engine") as engine:
                    with self.assertRaises(ConfigurationError):
                        migrate(settings, "downgrade", "base")
                    engine.assert_not_called()

    def test_missing_database_fails_without_a_traceback(self):
        env = dict(os.environ)
        env.pop("OI_API_DATABASE_URL", None)
        env["OI_API_ENVIRONMENT"] = "synthetic"
        result = subprocess.run(
            [sys.executable, "-m", "oi_api.migrate", "upgrade", "head"],
            env=env, capture_output=True, text=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Database configuration is required", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_credentials_are_not_printed(self):
        env = dict(os.environ, OI_API_DATABASE_URL="invalid://secret-canary",
                   OI_API_ENVIRONMENT="synthetic")
        result = subprocess.run(
            [sys.executable, "-m", "oi_api.migrate", "upgrade", "head"],
            env=env, capture_output=True, text=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("secret-canary", result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)


@unittest.skipUnless(os.environ.get("OI_API_RUN_DATABASE_TESTS") == "1",
                     "Set OI_API_RUN_DATABASE_TESTS=1 and a disposable oi_api_test_* database URL")
class PostgreSQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get("OI_API_TEST_DATABASE_URL", "")
        try:
            name = make_url(value).database
        except Exception:
            raise RuntimeError("A disposable test database URL is required") from None
        if not name or not name.startswith("oi_api_test_"):
            raise RuntimeError("Database tests require the oi_api_test_ name prefix")
        cls.settings = Settings.from_env({"OI_API_DATABASE_URL": value})
        cls.engine = make_engine(cls.settings)
        with cls.engine.connect() as conn:
            version = int(conn.execute(text("SELECT current_setting('server_version_num')")).scalar_one())
        if version // 10000 != 16:
            raise RuntimeError("Integration tests require actual PostgreSQL 16")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.remove_owned_fixtures()

    def remove_owned_fixtures(self):
        with self.engine.begin() as conn:
            # Release only the declared 0019 execution children and functions.
            # Unknown dependencies still stop cleanup through RESTRICT.
            # Explicitly release only the declared 0020 source delivery objects.
            conn.execute(text("DO $$ BEGIN IF to_regclass('identity.identity_domain_events') IS NOT NULL THEN EXECUTE 'DROP TRIGGER IF EXISTS oi_capture_source_event ON identity.identity_domain_events'; END IF; END $$"))
            conn.execute(text('DROP TABLE IF EXISTS investigation.composer_source_event_receipts'))
            conn.execute(text('DROP TABLE IF EXISTS coordination.source_event_delivery_events'))
            conn.execute(text('DROP TABLE IF EXISTS coordination.source_event_deliveries'))
            conn.execute(text('DROP TABLE IF EXISTS coordination.source_event_outbox'))
            conn.execute(text('DROP FUNCTION IF EXISTS coordination.capture_source_event()'))
            conn.execute(text('DROP FUNCTION IF EXISTS coordination.guard_source_event_outbox()'))
            conn.execute(text('DROP FUNCTION IF EXISTS coordination.source_event_binding(bigint)'))
            conn.execute(text('DROP FUNCTION IF EXISTS coordination.guard_source_event_delivery()'))
            conn.execute(text('DROP FUNCTION IF EXISTS coordination.guard_source_event_delivery_event()'))
            conn.execute(text('DROP FUNCTION IF EXISTS coordination.require_source_delivery_consistency()'))
            conn.execute(text('DROP FUNCTION IF EXISTS investigation.guard_composer_source_receipt()'))
            conn.execute(text("DROP TABLE IF EXISTS investigation.composer_tool_run_results"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.composer_tool_run_events"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.composer_tool_runs"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.require_composer_run_consistency()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_composer_run_result()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_composer_run_event()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_composer_run()"))
            # Drop the declared 0016 FK child before its canonical task owner;
            # RESTRICT remains in effect for every unknown dependency.
            conn.execute(text("DROP TABLE IF EXISTS coordination.question_followthrough_manual_dependencies"))
            conn.execute(text("DROP TABLE IF EXISTS coordination.question_followthrough_events"))
            conn.execute(text("DROP TABLE IF EXISTS coordination.question_followthrough_tasks"))
            conn.execute(text("DROP FUNCTION IF EXISTS coordination.guard_question_followthrough_event_insert()"))
            conn.execute(text("DROP FUNCTION IF EXISTS coordination.guard_question_followthrough_task_insert()"))
            conn.execute(text("DROP FUNCTION IF EXISTS coordination.guard_question_followthrough_manual_dependency()"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.question_evidence_links"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_question_evidence_insert()"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.evidence_rights_decisions"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_evidence_rights_insert()"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.evidence_catalog_records"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.evidence_command_origins"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_evidence_command_origin_insert()"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.question_passage_revisions"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_question_passage_revision()"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.evidence_commands"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.question_evidence_reports"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.question_evidence_assessments"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.case_evidence_withdrawals"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.case_evidence_versions"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.require_evidence_command_origin()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_case_evidence_scope()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_case_evidence_version()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_case_evidence_withdrawal()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_question_evidence_assessment()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_question_evidence_report()"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.question_review_receipts"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_review_return_insert()"))
            # Release the 0018 observation anchor before its question and source parents.
            conn.execute(text("DROP TABLE IF EXISTS investigation.laboratory_question_anchors"))
            conn.execute(text("DROP TABLE IF EXISTS investigation.source_questions"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.require_lab_question_child()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_lab_question_child()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_lab_question_insert()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.require_text_question_target()"))
            conn.execute(text("DROP FUNCTION IF EXISTS investigation.guard_question_insert()"))
            conn.execute(text("DROP SCHEMA IF EXISTS investigation"))
            conn.execute(text("DROP TABLE IF EXISTS clinical_source.fhir_laboratory_commands"))
            conn.execute(text("DROP TABLE IF EXISTS clinical_source.fhir_laboratory_observations"))
            conn.execute(text("DROP TABLE IF EXISTS clinical_source.fhir_laboratory_sources"))
            conn.execute(text("DROP FUNCTION IF EXISTS clinical_source.guard_fhir_laboratory_command_insert()"))
            conn.execute(text("DROP FUNCTION IF EXISTS clinical_source.guard_fhir_laboratory_source_insert()"))
            conn.execute(text("DROP TABLE IF EXISTS clinical_source.annotation_revisions"))
            conn.execute(text("DROP TABLE IF EXISTS clinical_source.document_intakes"))
            conn.execute(text("DROP TABLE IF EXISTS clinical_source.source_image_links"))
            conn.execute(text("DROP TABLE IF EXISTS clinical_source.dicom_objects"))
            conn.execute(text("DROP FUNCTION IF EXISTS clinical_source.guard_image_source_link()"))
            conn.execute(text("DROP TABLE IF EXISTS clinical_source.assertions"))
            conn.execute(text("DROP TABLE IF EXISTS clinical_source.quarantine"))
            conn.execute(text("DROP TABLE IF EXISTS clinical_source.source_versions"))
            conn.execute(text("DROP FUNCTION IF EXISTS clinical_source.guard_version_history()"))
            conn.execute(text("DROP SCHEMA IF EXISTS clinical_source"))
            conn.execute(text("DROP TABLE IF EXISTS coordination.patient_case_bindings"))
            conn.execute(text("DROP TABLE IF EXISTS coordination.record_requests"))
            conn.execute(text("DROP FUNCTION IF EXISTS coordination.guard_case_binding_origin()"))
            conn.execute(text("DROP FUNCTION IF EXISTS coordination.guard_case_binding_update()"))
            conn.execute(text("DROP FUNCTION IF EXISTS coordination.guard_record_request_origin()"))
            conn.execute(text("DROP FUNCTION IF EXISTS coordination.guard_record_request_update()"))
            conn.execute(text("DROP SCHEMA IF EXISTS coordination"))
            for name in ("identity_domain_events", "identity_create_receipts", "identity_patients"):
                conn.execute(text(f"DROP TABLE IF EXISTS identity.{name}"))
            for name in ("guard_patient_identity_mutation", "guard_registration_receipt", "reject_registry_history_mutation"):
                conn.execute(text(f"DROP FUNCTION IF EXISTS identity.{name}()"))
            conn.execute(text("DROP SCHEMA IF EXISTS identity"))
            conn.execute(text("DROP TABLE IF EXISTS public.alembic_version"))

    def tearDown(self):
        self.remove_owned_fixtures()

    def test_apply_restart_downgrade_and_reapply_preserve_readiness_contract(self):
        probe = Database(self.settings)
        self.addCleanup(probe.close)
        self.assertEqual(probe.check().status, "schema_mismatch")
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(get_json(base, "/health/ready")[0], 503)
            migrate(self.settings, "upgrade", "head")
            status, body, _ = get_json(base, "/health/ready")
            self.assertEqual(status, 200)
            self.assertEqual(body["database"]["required_revision"], SCHEMA_REVISION)
            # Repeat upgrade is idempotent; identity lives in its owned schema.
            migrate(self.settings, "upgrade", "head")
            self.assertEqual(inspect(self.engine).get_table_names(schema="public"), ["alembic_version"])
        with running_server(create_app(self.settings)) as restarted:
            self.assertEqual(get_json(restarted, "/health/ready")[0], 200)
        migrate(self.settings, "downgrade", "base")
        self.assertEqual(probe.check().status, "schema_mismatch")
        migrate(self.settings, "upgrade", "head")
        self.assertEqual(probe.check().status, "ready")

    def test_unknown_or_multiple_revisions_are_not_accepted(self):
        migrate(self.settings, "upgrade", "head")
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE public.alembic_version SET version_num = 'unknown_revision'"))
        probe = Database(self.settings)
        self.addCleanup(probe.close)
        self.assertEqual(probe.check().status, "schema_mismatch")
        with self.assertRaisesRegex(RuntimeError, "Unsupported migration state"):
            with probe.registry_connection():
                self.fail("Unknown revisions must not admit domain operations")

        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO public.alembic_version VALUES (:revision)"), {"revision": SCHEMA_REVISION})
        self.assertEqual(probe.check().status, "schema_mismatch")
        with self.assertRaisesRegex(RuntimeError, "Unsupported migration state"):
            with probe.registry_connection():
                self.fail("Multiple revisions must not admit domain operations")

    def test_failed_migration_rolls_back_ddl_and_keeps_readiness_false(self):
        def fail_after_ddl(config, revision):
            config.attributes["connection"].execute(text("CREATE TABLE public.oi_shell_rollback_probe (id integer)"))
            raise RuntimeError("Authored migration failure fixture")

        def remove_fixture_if_regression():
            with self.engine.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS public.oi_shell_rollback_probe"))

        self.addCleanup(remove_fixture_if_regression)
        with patch("oi_api.migrate.command.upgrade", side_effect=fail_after_ddl):
            with self.assertRaisesRegex(RuntimeError, "Authored migration failure"):
                migrate(self.settings, "upgrade", "head")
        self.assertNotIn("oi_shell_rollback_probe", inspect(self.engine).get_table_names(schema="public"))
        probe = Database(self.settings)
        self.addCleanup(probe.close)
        self.assertEqual(probe.check().status, "schema_mismatch")


if __name__ == "__main__":
    unittest.main()
