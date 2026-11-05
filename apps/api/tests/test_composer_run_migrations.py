"""Composer run migration boundaries against actual PostgreSQL, never SQLite.

The source-only check verifies the executable migration graph and readiness
contract. All relational/lifecycle checks require the existing disposable PG16
fixture; a local skip is not evidence that those database checks passed.
"""
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import unittest
import uuid

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.contracts import DatabaseStatus, SCHEMA_REVISION
from oi_api.database import Database
from oi_api.migrate import migrate
from oi_api.sources import PostgresSourceVersions
import test_evidence_convergence_migrations as previous
from test_source_versions import AMENDED, SourceVersionFixture


REVISION = "0019_composer_runs"
PARENT = "0018_laboratory_questions"
RUNS = "investigation.composer_tool_runs"
EVENTS = "investigation.composer_tool_run_events"
RESULTS = "investigation.composer_tool_run_results"
TABLES = (RUNS, EVENTS, RESULTS)
API_ROOT = Path(__file__).resolve().parents[1]


class ComposerMigrationGraphTests(unittest.TestCase):
    def test_composer_upgrade_is_the_single_ready_head_after_laboratory_questions(self):
        # Missing/sibling migration or a stale readiness literal must fail here.
        script = ScriptDirectory.from_config(Config(str(API_ROOT / "alembic.ini")))
        self.assertEqual(script.get_heads(), [REVISION])
        self.assertEqual(script.get_revision(REVISION).down_revision, PARENT)
        self.assertEqual(SCHEMA_REVISION, script.get_current_head())
        self.assertEqual(DatabaseStatus(status="ready").required_revision,
                         script.get_current_head())


class ComposerRunMigrationTests(SourceVersionFixture):
    services = previous.EvidenceConvergenceMigrationTests.services
    start_at = previous.EvidenceConvergenceMigrationTests.start_at
    snapshot = previous.EvidenceConvergenceMigrationTests.snapshot
    upgrade_preserving = previous.EvidenceConvergenceMigrationTests.upgrade_preserving

    def seed(self):
        patient, question, _ = self.start_at(PARENT)
        self.upgrade_preserving(self.snapshot())
        return patient, question

    def values(self, question, **changes):
        with self.engine.connect() as conn:
            row = dict(conn.execute(text(
                "SELECT patient_id,case_id,question_id,origin_org,actor,purpose,"
                "source_snapshot_contract,source_snapshot_sha256,preflight_sha256,"
                "source_id,source_version,source_sha256,source_line "
                "FROM investigation.source_questions WHERE question_id=:question"
            ), {"question": question}).mappings().one())
        return {
            **row, "run_id": "RUN-" + uuid.uuid4().hex.upper(),
            "kind": "source-question-brief/1", "request_key": uuid.uuid4().hex,
            "request_digest": "a" * 64, **changes,
        }

    @staticmethod
    def insert(conn, values):
        # Column names come only from the fixed test fixtures above.
        columns = ",".join(values)
        parameters = ",".join(":" + name for name in values)
        conn.execute(text(f"INSERT INTO {RUNS} ({columns}) VALUES ({parameters})"), values)

    @staticmethod
    def event(conn, run, reason):
        conn.execute(text(
            f"INSERT INTO {EVENTS} (run_id,revision,state,attempt_count,reason_code) "
            f"SELECT run_id,revision,state,attempt_count,:reason FROM {RUNS} WHERE run_id=:run"
        ), {"run": run, "reason": reason})

    def queue(self, question, **changes):
        values = self.values(question, **changes)
        with self.engine.begin() as conn:
            self.insert(conn, values)
            self.event(conn, values["run_id"], "queued")
        return values["run_id"]

    def row(self, run):
        with self.engine.connect() as conn:
            return dict(conn.execute(text(f"SELECT * FROM {RUNS} WHERE run_id=:run"),
                                     {"run": run}).mappings().one())

    def claim(self, run, *, reason="claimed", lease_seconds=300, token=None):
        token = token or "LEASE-" + uuid.uuid4().hex.upper()
        with self.engine.begin() as conn:
            conn.execute(text(
                f"UPDATE {RUNS} SET state='running',revision=revision+1,"
                "attempt_count=attempt_count+1,lease_token=:token,"
                "lease_expires_at=clock_timestamp()+:seconds*interval '1 second' "
                "WHERE run_id=:run"
            ), {"run": run, "token": token, "seconds": lease_seconds})
            self.event(conn, run, reason)
        return token

    def expire_lease(self, run):
        # Wait on the database clock; do not rewrite lease history for a test.
        with self.engine.connect() as conn:
            conn.execute(text(
                "SELECT pg_sleep(GREATEST(0,EXTRACT(EPOCH FROM "
                f"(lease_expires_at-clock_timestamp())))+0.02) FROM {RUNS} WHERE run_id=:run"
            ), {"run": run})

    def terminal(self, conn, run, state, reason):
        conn.execute(text(
            f"UPDATE {RUNS} SET state=:state,revision=revision+1,"
            "lease_token=NULL,lease_expires_at=NULL WHERE run_id=:run"
        ), {"state": state, "run": run})
        self.event(conn, run, reason)

    @staticmethod
    def result(conn, run, value=None):
        value = value if value is not None else {
            "contract": "oi.synthetic-source-brief/2",
            "body": "Independently fictional migration artifact.",
        }
        canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        conn.execute(text(
            f"INSERT INTO {RESULTS} (run_id,result_json,result_sha256) "
            "VALUES (:run,CAST(:result AS jsonb),:sha)"
        ), {"run": run, "result": canonical,
            "sha": hashlib.sha256(canonical.encode("utf-8")).hexdigest()})

    def complete(self, run):
        with self.engine.begin() as conn:
            self.terminal(conn, run, "completed", "completed")
            self.result(conn, run)

    def test_fresh_upgrade_and_empty_downgrade_restore_readiness(self):
        probe = Database(self.settings)
        self.addCleanup(probe.close)
        self.assertEqual(probe.check().status, "ready")
        with self.engine.connect() as conn:
            for table in TABLES:
                self.assertEqual(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one(), 0)
        migrate(self.admin, "downgrade", PARENT)
        self.assertEqual(probe.check().status, "schema_mismatch")
        migrate(self.admin, "upgrade", "head")
        self.assertEqual(probe.check().status, "ready")

    def test_populated_upgrade_preserves_question_source_event_and_task_history(self):
        patient, question, prepared = self.start_at(PARENT)
        previous.EvidenceConvergenceMigrationTests.seed_metadata_task(self, patient, question, prepared)
        before = self.snapshot()
        self.upgrade_preserving(before)
        for table in TABLES:
            self.assertEqual(self.snapshot()[0][table], [])
        migrate(self.admin, "downgrade", PARENT)
        self.assertEqual(self.snapshot(), before)
        migrate(self.admin, "upgrade", "head")
        run = self.queue(question)
        self.assertEqual((self.row(run)["state"], self.row(run)["attempt_count"]), ("queued", 0))

    def test_insert_requires_exact_patient_case_question_and_current_source(self):
        patient, question = self.seed()
        forged = (
            {"patient_id": "PAT-" + "B" * 32}, {"case_id": "CASE-OTHER"},
            {"question_id": "QUESTION-" + "C" * 32}, {"origin_org": "ORG-OTHER"},
            {"purpose": "research"}, {"source_id": "SRC-" + "D" * 32},
            {"source_line": 9}, {"source_version": 2}, {"source_sha256": "0" * 64},
            {"source_snapshot_sha256": "0" * 64}, {"preflight_sha256": "0" * 64},
        )
        for change in forged:
            with self.subTest(change=change), self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-.*BOUNDARY"):
                with self.engine.begin() as conn:
                    self.insert(conn, self.values(question, **change))
        with self.services() as registry:
            PostgresSourceVersions(registry).import_original(
                patient, "CASE-ALPHA", AMENDED.encode("utf-8"), **previous.OPTIONS)
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-.*BOUNDARY"):
            self.queue(question)

    def test_new_run_cannot_start_running_or_reuse_actor_request_key(self):
        _, question = self.seed()
        for change in ({"state": "completed"}, {"revision": 2}, {"attempt_count": 1},
                       {"max_attempts": 4}):
            with self.subTest(change=change), self.assertRaises(DBAPIError):
                self.queue(question, **change)
        self.queue(question, request_key="ONE-ORIGIN-INTENT")
        with self.assertRaisesRegex(DBAPIError, "unique constraint"):
            self.queue(question, request_key="ONE-ORIGIN-INTENT", request_digest="b" * 64)

    def test_intent_and_all_retained_history_are_immutable(self):
        _, question = self.seed()
        run = self.queue(question)
        before = self.row(run)
        for column, value in (
            ("run_id", "RUN-" + "F" * 32), ("actor", "ACTOR-OTHER"),
            ("request_key", "OTHER-REQUEST"), ("request_digest", "f" * 64),
            ("source_snapshot_sha256", "f" * 64), ("source_version", 2),
            ("created_at", before["created_at"] - timedelta(days=1)),
        ):
            with self.subTest(column=column), self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-INTENT-IMMUTABLE"):
                with self.engine.begin() as conn:
                    conn.execute(text(f"UPDATE {RUNS} SET {column}=:value WHERE run_id=:run"),
                                 {"run": run, "value": value})
        for command in (f"DELETE FROM {RUNS}", f"TRUNCATE {RUNS} CASCADE",
                        f"UPDATE {EVENTS} SET reason_code=reason_code", f"DELETE FROM {EVENTS}",
                        f"TRUNCATE {EVENTS}"):
            with self.subTest(command=command), self.assertRaisesRegex(DBAPIError, "HISTORY-IMMUTABLE"):
                with self.engine.begin() as conn:
                    conn.execute(text(command))
        self.assertEqual(self.row(run), before)

    def test_every_run_revision_needs_matching_consecutive_event_at_commit(self):
        _, question = self.seed()
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-RUN-HISTORY"):
            with self.engine.begin() as conn:
                self.insert(conn, self.values(question))
        run = self.queue(question)
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-RUN-HISTORY"):
            with self.engine.begin() as conn:
                conn.execute(text(f"UPDATE {RUNS} SET state='cancelled',revision=revision+1 WHERE run_id=:run"),
                             {"run": run})
        self.assertEqual((self.row(run)["state"], self.row(run)["revision"]), ("queued", 1))
        for revision, state, attempt, reason in ((2, "queued", 0, "queued"),
                                                (1, "completed", 0, "completed"),
                                                (1, "queued", 1, "queued")):
            with self.subTest(state=state, revision=revision, attempt=attempt), self.assertRaises(DBAPIError):
                with self.engine.begin() as conn:
                    conn.execute(text(
                        f"INSERT INTO {EVENTS} (run_id,revision,state,attempt_count,reason_code) "
                        "VALUES (:run,:revision,:state,:attempt,:reason)"
                    ), {"run": run, "revision": revision, "state": state,
                        "attempt": attempt, "reason": reason})

    def test_claim_and_recovery_require_expired_lease_new_token_and_attempt_budget(self):
        _, question = self.seed()
        run = self.queue(question)
        first = self.claim(run)
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-LEASE"):
            self.claim(run, reason="lease_recovered")
        for seconds in (0, 301):
            another = self.queue(question)
            with self.subTest(seconds=seconds), self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-LEASE"):
                self.claim(another, lease_seconds=seconds)
        expired = self.queue(question)
        previous_token = self.claim(expired, lease_seconds=0.03)
        self.expire_lease(expired)
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-LEASE"):
            self.claim(expired, reason="lease_recovered", token=previous_token)
        second = self.claim(expired, reason="lease_recovered", lease_seconds=0.03)
        self.assertNotEqual(second, previous_token)
        self.expire_lease(expired)
        self.claim(expired, reason="lease_recovered", lease_seconds=0.03)
        self.expire_lease(expired)
        with self.assertRaises(DBAPIError):
            self.claim(expired, reason="lease_recovered")
        with self.engine.begin() as conn:
            self.terminal(conn, expired, "failed", "attempts_exhausted")
        row = self.row(expired)
        self.assertEqual((row["state"], row["attempt_count"], row["revision"]), ("failed", 3, 5))
        self.assertIsNone(row["lease_token"])
        self.assertIsNone(row["lease_expires_at"])
        self.assertEqual(self.row(run)["lease_token"], first)

    def test_retry_keeps_attempt_clears_lease_and_bounds_next_claim_time(self):
        _, question = self.seed()
        run = self.queue(question)
        self.claim(run)
        for delay in (-1, 61):
            with self.subTest(delay=delay), self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-RETRY"):
                with self.engine.begin() as conn:
                    conn.execute(text(
                        f"UPDATE {RUNS} SET state='queued',revision=revision+1,lease_token=NULL,"
                        "lease_expires_at=NULL,available_at=clock_timestamp()+:delay*interval '1 second' "
                        "WHERE run_id=:run"
                    ), {"run": run, "delay": delay})
                    self.event(conn, run, "retryable_failure")
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-LEASE"):
            with self.engine.begin() as conn:
                conn.execute(text(
                    f"UPDATE {RUNS} SET state='queued',revision=revision+1,lease_token=NULL,"
                    "lease_expires_at=NULL,available_at=clock_timestamp()+interval '30 seconds' "
                    "WHERE run_id=:run"
                ), {"run": run})
                self.event(conn, run, "retryable_failure")
                conn.execute(text(
                    f"UPDATE {RUNS} SET state='running',revision=revision+1,attempt_count=attempt_count+1,"
                    "lease_token=:token,lease_expires_at=clock_timestamp()+interval '300 seconds' "
                    "WHERE run_id=:run"
                ), {"run": run, "token": "LEASE-" + uuid.uuid4().hex.upper()})
        with self.engine.begin() as conn:
            conn.execute(text(
                f"UPDATE {RUNS} SET state='queued',revision=revision+1,lease_token=NULL,"
                "lease_expires_at=NULL,available_at=clock_timestamp()+interval '0.03 second' "
                "WHERE run_id=:run"
            ), {"run": run})
            self.event(conn, run, "retryable_failure")
        row = self.row(run)
        self.assertEqual((row["state"], row["attempt_count"], row["revision"]), ("queued", 1, 3))
        self.assertIsNone(row["lease_token"])
        self.assertIsNone(row["lease_expires_at"])
        with self.engine.connect() as conn:
            conn.execute(text(
                "SELECT pg_sleep(GREATEST(0,EXTRACT(EPOCH FROM "
                f"(available_at-clock_timestamp())))+0.02) FROM {RUNS} WHERE run_id=:run"
            ), {"run": run})
        self.claim(run)
        self.assertEqual((self.row(run)["state"], self.row(run)["attempt_count"]), ("running", 2))

    def test_completed_state_requires_exactly_one_result_and_a_live_lease(self):
        _, question = self.seed()
        queued = self.queue(question)
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-RUN-RESULT"):
            with self.engine.begin() as conn:
                self.result(conn, queued)
        run = self.queue(question)
        self.claim(run)
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-RUN-RESULT"):
            with self.engine.begin() as conn:
                self.terminal(conn, run, "completed", "completed")
        self.assertEqual(self.row(run)["state"], "running")
        expired = self.queue(question)
        self.claim(expired, lease_seconds=0.03)
        self.expire_lease(expired)
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-LEASE"):
            self.complete(expired)
        self.complete(run)
        self.assertEqual(self.row(run)["state"], "completed")
        with self.assertRaisesRegex(DBAPIError, "unique constraint"):
            with self.engine.begin() as conn:
                self.result(conn, run)

    def test_terminal_rows_freeze_and_cancellation_cannot_be_completed(self):
        _, question = self.seed()
        for state, reason in (("cancelled", "cancelled"), ("blocked", "authority_unavailable"),
                              ("stale", "source_changed")):
            run = self.queue(question)
            with self.engine.begin() as conn:
                self.terminal(conn, run, state, reason)
            with self.subTest(state=state), self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-TERMINAL"):
                self.claim(run)
        run = self.queue(question)
        self.claim(run)
        with self.engine.begin() as conn:
            self.terminal(conn, run, "cancelled", "cancelled")
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-TERMINAL"):
            self.complete(run)

    def test_history_reasons_cannot_misrepresent_the_transition(self):
        _, question = self.seed()
        run = self.queue(question)
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-EVENT"):
            self.claim(run, reason="lease_recovered")
        self.claim(run)
        with self.assertRaisesRegex(DBAPIError, "OI-COMPOSER-EVENT"):
            with self.engine.begin() as conn:
                self.terminal(conn, run, "failed", "attempts_exhausted")
        with self.engine.begin() as conn:
            self.terminal(conn, run, "failed", "invalid_output")

    def test_result_shape_byte_bound_and_immutability_survive_source_amendment(self):
        patient, question = self.seed()
        for value in ([], {"body": "é" * 70_000}):
            run = self.queue(question)
            self.claim(run)
            with self.subTest(shape=type(value).__name__), self.assertRaises(DBAPIError):
                with self.engine.begin() as conn:
                    self.terminal(conn, run, "completed", "completed")
                    self.result(conn, run, value)
        run = self.queue(question)
        self.claim(run)
        self.complete(run)
        with self.engine.connect() as conn:
            result = dict(conn.execute(text(f"SELECT * FROM {RESULTS} WHERE run_id=:run"),
                                       {"run": run}).mappings().one())
        for command in (f"UPDATE {RESULTS} SET result_json=result_json WHERE run_id=:run",
                        f"DELETE FROM {RESULTS} WHERE run_id=:run", f"TRUNCATE {RESULTS}"):
            with self.subTest(command=command), self.assertRaisesRegex(DBAPIError, "HISTORY-IMMUTABLE"):
                with self.engine.begin() as conn:
                    conn.execute(text(command), {"run": run})
        with self.services() as registry:
            PostgresSourceVersions(registry).import_original(
                patient, "CASE-ALPHA", AMENDED.encode("utf-8"), **previous.OPTIONS)
        with self.engine.connect() as conn:
            self.assertEqual(dict(conn.execute(text(f"SELECT * FROM {RESULTS} WHERE run_id=:run"),
                                               {"run": run}).mappings().one()), result)
        self.assertEqual(self.row(run)["state"], "completed")

    def test_populated_execution_history_refuses_downgrade_without_data_loss(self):
        _, question = self.seed()
        run = self.queue(question)
        self.claim(run)
        self.complete(run)
        before = self.snapshot()
        with self.assertRaisesRegex(CommandError, "Stored Composer execution history"):
            migrate(self.admin, "downgrade", PARENT)
        self.assertEqual(self.snapshot(), before)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(), REVISION)
