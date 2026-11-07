"""Real PostgreSQL guard and published-history acceptance for event recovery.

Every source is independently fictional. Skips are not database acceptance.
"""
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.app import create_app
from oi_api.migrate import migrate
from http_support import running_server
import test_source_event_delivery as delivery_fixture
import test_source_versions as source_fixture


PARENT = "0029_patient_access"
REVISION = "0030_source_event_recovery"
RECOVERIES = "coordination.source_event_recoveries"


class SourceEventRecoveryMigrationTests(source_fixture.SourceVersionFixture):
    # Reuse the fixture helpers without inheriting and rerunning its tests.
    delivery_store = delivery_fixture.SourceEventDeliveryPostgresTests.delivery_store
    claim_event = delivery_fixture.SourceEventDeliveryPostgresTests.claim_event
    fail_event = delivery_fixture.SourceEventDeliveryPostgresTests.fail_event
    deliver_event = delivery_fixture.SourceEventDeliveryPostgresTests.deliver_event
    rows = delivery_fixture.SourceEventDeliveryPostgresTests.rows
    delivery = delivery_fixture.SourceEventDeliveryPostgresTests.delivery
    snapshot = delivery_fixture.SourceEventDeliveryPostgresTests.snapshot

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(("composer_context_read", "question_create",
                                         "question_read", "source_brief_export"))
        self.write()

    def terminal(self, reason="authority_unavailable"):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
        claim = self.claim_event(patient)
        self.assertEqual(self.fail_event(claim, reason), "dead_letter")
        return self.delivery(claim["delivery_id"])

    @staticmethod
    def insert_request(connection, row):
        connection.execute(text(
            "INSERT INTO coordination.source_event_recoveries "
            "(delivery_id,failed_revision,recovery_revision) VALUES (:id,:failed,:recovered)"),
            {"id": row["delivery_id"], "failed": row["revision"], "recovered": row["revision"] + 1})

    @staticmethod
    def requeue(connection, row):
        connection.execute(text(
            "UPDATE coordination.source_event_deliveries SET state='queued',revision=revision+1,"
            "failure_count=0,lease_token=NULL,lease_expires_at=NULL,available_at=clock_timestamp() "
            "WHERE delivery_id=:id"), {"id": row["delivery_id"]})

    def commit_recovery(self, row):
        with self.engine.begin() as connection:
            self.insert_request(connection, row)
            self.requeue(connection, row)
            connection.execute(text(
                "INSERT INTO coordination.source_event_delivery_events "
                "(delivery_id,revision,state,attempt_count,failure_count,reason_code) "
                "VALUES (:id,:revision,'queued',:attempt,0,'recovery_requested')"),
                {"id": row["delivery_id"], "revision": row["revision"] + 1,
                 "attempt": row["attempt_count"]})

    def test_upgrade_preserves_populated_delivery_and_restores_published_guard_on_downgrade(self):
        row = self.terminal()
        before = self.snapshot()
        migrate(self.admin, "downgrade", PARENT)
        self.assertEqual(self.snapshot(), before)
        with self.engine.connect() as connection:
            old_guards = connection.execute(text(
                "SELECT p.proname,p.prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='coordination' AND p.proname IN "
                "('guard_source_event_delivery','guard_source_event_delivery_event',"
                "'require_source_delivery_consistency') ORDER BY p.proname")).all()
        with self.assertRaisesRegex(DBAPIError, "OI-DELIVERY-TERMINAL-REVISION"):
            with self.engine.begin() as connection:
                self.requeue(connection, row)
        migrate(self.admin, "upgrade", REVISION)
        migrate(self.admin, "upgrade", REVISION)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.rows(RECOVERIES, "delivery_id,failed_revision"), [])
        migrate(self.admin, "downgrade", PARENT)
        with self.engine.connect() as connection:
            restored = connection.execute(text(
                "SELECT p.proname,p.prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='coordination' AND p.proname IN "
                "('guard_source_event_delivery','guard_source_event_delivery_event',"
                "'require_source_delivery_consistency') ORDER BY p.proname")).all()
        self.assertEqual(restored, old_guards)
        self.assertEqual(self.snapshot(), before)
        migrate(self.admin, "upgrade", "head")

    def test_no_reset_without_exact_recovery_receipt_and_no_orphan_request_or_lifecycle(self):
        row = self.terminal()
        before = self.snapshot()
        with self.assertRaisesRegex(DBAPIError, "OI-DELIVERY-RECOVERY"):
            with self.engine.begin() as connection:
                self.requeue(connection, row)
        with self.assertRaisesRegex(DBAPIError, "OI-DELIVERY-ORPHAN-RECOVERY"):
            with self.engine.begin() as connection:
                self.insert_request(connection, row)
        with self.assertRaisesRegex(DBAPIError, "OI-DELIVERY-(ORPHAN-RECOVERY|HISTORY)"):
            with self.engine.begin() as connection:
                self.insert_request(connection, row)
                self.requeue(connection, row)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.rows(RECOVERIES, "delivery_id,failed_revision"), [])

    def test_stale_target_invalid_reason_and_changed_attempt_are_rejected_atomically(self):
        row = self.terminal()
        before = self.snapshot()
        with self.assertRaisesRegex(DBAPIError, "OI-DELIVERY-RECOVERY-TARGET"):
            with self.engine.begin() as connection:
                self.insert_request(connection, {**row, "revision": row["revision"] - 1})
        with self.assertRaisesRegex(DBAPIError, "OI-DELIVERY-RECOVERY"):
            with self.engine.begin() as connection:
                self.insert_request(connection, row)
                connection.execute(text(
                    "UPDATE coordination.source_event_deliveries SET state='queued',revision=revision+1,"
                    "failure_count=0,attempt_count=attempt_count+1 WHERE delivery_id=:id"),
                    {"id": row["delivery_id"]})
        with self.assertRaisesRegex(DBAPIError, "OI-DELIVERY-EVENT-REASON"):
            with self.engine.begin() as connection:
                self.insert_request(connection, row)
                self.requeue(connection, row)
                connection.execute(text(
                    "INSERT INTO coordination.source_event_delivery_events "
                    "(delivery_id,revision,state,attempt_count,failure_count,reason_code) "
                    "VALUES (:id,:revision,'queued',:attempt,0,'continued')"),
                    {"id": row["delivery_id"], "revision": row["revision"] + 1,
                     "attempt": row["attempt_count"]})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.rows(RECOVERIES, "delivery_id,failed_revision"), [])

    def test_invalid_event_terminal_cannot_be_recovered_by_direct_sql(self):
        row = self.terminal("invalid_event")
        before = self.snapshot()
        with self.assertRaisesRegex(DBAPIError, "OI-DELIVERY-RECOVERY-TARGET"):
            with self.engine.begin() as connection:
                self.insert_request(connection, row)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.rows(RECOVERIES, "delivery_id,failed_revision"), [])

    def test_recovery_history_is_immutable_and_populated_downgrade_is_refused(self):
        row = self.terminal()
        self.commit_recovery(row)
        before = self.snapshot()
        receipts = self.rows(RECOVERIES, "delivery_id,failed_revision")
        self.assertEqual(len(receipts), 1)
        current = self.delivery(row["delivery_id"])
        self.assertEqual((current["state"], current["revision"], current["attempt_count"],
                          current["failure_count"]),
                         ("queued", row["revision"] + 1, row["attempt_count"], 0))
        for statement in (
                f"UPDATE {RECOVERIES} SET recorded_at=clock_timestamp()",
                f"DELETE FROM {RECOVERIES}", f"TRUNCATE {RECOVERIES}"):
            with self.subTest(statement=statement), self.assertRaises(DBAPIError):
                with self.engine.begin() as connection:
                    connection.execute(text(statement))
        with self.assertRaisesRegex(CommandError, "recovery history must be retained"):
            migrate(self.admin, "downgrade", PARENT)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(),
                             REVISION)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.rows(RECOVERIES, "delivery_id,failed_revision"), receipts)

    def test_completed_delivery_cannot_be_reopened(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
        claim = self.claim_event(patient)
        self.assertEqual(self.deliver_event(claim)["status"], "delivered")
        row = self.delivery(claim["delivery_id"])
        before = self.snapshot()
        with self.assertRaisesRegex(DBAPIError, "OI-DELIVERY-RECOVERY-TARGET"):
            with self.engine.begin() as connection:
                self.insert_request(connection, row)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.rows(RECOVERIES, "delivery_id,failed_revision"), [])
