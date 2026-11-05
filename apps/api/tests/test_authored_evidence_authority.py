"""Real PostgreSQL and encoded-HTTP evidence authority/rollback acceptance.

The encoders still produce actual bytes before each injected boundary effect.
Both FastAPI typed serialization and explicit JSONResponse paths are observed,
so moving disclosure after commit cannot evade a passing test. All database
failure probes are confined to the existing disposable fictional PG fixture.
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextlib import contextmanager
import copy
import hashlib
import json
import threading
from unittest.mock import patch

from fastapi import routing as fastapi_routing
from fastapi.responses import JSONResponse
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from http_support import running_server
from oi_api.app import create_app
from oi_api.contracts import SCHEMA_REVISION
from oi_api.migrate import migrate
from oi_api.authored_evidence import PostgresQuestionEvidence
import test_evidence_convergence_migrations as history
from test_patients import TOKEN_A, request
from test_authored_evidence_postgres import (
    EvidenceFixture, PACKET_CONTRACT, REPORT_CONTRACT, PRIVATE_FAILURE,
    WITHDRAW_REASON, digest, evidence_text, permissions,
)


@contextmanager
def observe_evidence_encoding(matches, effect):
    """Observe complete selected wire JSON, never mocked DTO rendering."""
    original_render = JSONResponse.render
    original_serialize = fastapi_routing.serialize_response

    def observed(encoded):
        if not isinstance(encoded, (bytes, str)):
            return
        value = json.loads(encoded)
        if isinstance(value, dict) and matches(value):
            effect(encoded)

    def render(response, content):
        encoded = original_render(response, content)
        observed(encoded)
        return encoded

    async def serialize(*args, **kwargs):
        encoded = await original_serialize(*args, **kwargs)
        if kwargs.get("dump_json") is True:
            observed(encoded)
        return encoded

    with patch.object(JSONResponse, "render", render), \
            patch.object(fastapi_routing, "serialize_response", serialize):
        yield


class QuestionEvidenceAuthorityTests(EvidenceFixture):
    def operations(self, state):
        prefix = self.prefix(state["patient"], state["question"])
        return (
            ("packet", "authored_evidence_read", prefix + "/evidence", None,
             lambda value: value.get("contract") == PACKET_CONTRACT),
            ("original", "authored_evidence_original_read", prefix + "/evidence/" + state["evidence_id"] + "/original", None,
             lambda value: value.get("contract") == "oi.h1-evidence-original/1"),
            ("read_report", "evidence_report_export", prefix + "/evidence-reports/" + state["report_id"], None,
             lambda value: value.get("contract") == REPORT_CONTRACT),
            ("import", "authored_evidence_import", prefix + "/evidence", {
                "synthetic": True, "request_key": "IMPORT-ENCODING-BOUNDARY",
                "original_text": evidence_text("FICTION-ENCODING"),
                "content_item": "full_text", "permissions": permissions(),
             }, lambda value: set(value) == {"evidence_id", "version", "duplicate"}),
            ("assessment", "authored_evidence_assess", prefix + "/evidence-assessments", {
                **state["assessment_body"], "request_key": "ASSESS-ENCODING-BOUNDARY",
             }, lambda value: set(value) == {"assessment_id", "question_id", "duplicate"}),
            ("create_report", "evidence_report_export", prefix + "/evidence-reports", {
                **state["report_body"], "request_key": "REPORT-ENCODING-BOUNDARY",
             }, lambda value: set(value) == {"report_id", "question_id", "duplicate"}),
            ("withdrawal", "authored_evidence_withdraw", prefix + "/evidence/" + state["evidence_id"] + "/withdraw", {
                "synthetic": True, "request_key": "WITHDRAW-ENCODING-BOUNDARY", "reason": WITHDRAW_REASON,
             }, lambda value: set(value) == {"withdrawal_id", "evidence_id", "duplicate"}),
        )

    @contextmanager
    def failing_source_receipt(self, *, deferred):
        """Use a real insert/deferred-commit failure, not a mocked DB commit."""
        with self.engine.begin() as db:
            db.exec_driver_sql("""
                CREATE FUNCTION identity.reject_evidence_test_receipt()
                RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
                IF NEW.event_type='source.read_authorized' THEN
                    RAISE EXCEPTION 'PRIVATE-FICTIONAL-EVIDENCE-FAILURE';
                END IF;
                RETURN NEW; END; $$;
            """)
            if deferred:
                db.exec_driver_sql("""
                    CREATE CONSTRAINT TRIGGER reject_evidence_test_receipt
                    AFTER INSERT ON identity.identity_domain_events
                    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
                    EXECUTE FUNCTION identity.reject_evidence_test_receipt()
                """)
            else:
                db.exec_driver_sql("""
                    CREATE TRIGGER reject_evidence_test_receipt
                    BEFORE INSERT ON identity.identity_domain_events FOR EACH ROW
                    EXECUTE FUNCTION identity.reject_evidence_test_receipt()
                """)
        try:
            yield
        finally:
            with self.engine.begin() as db:
                db.exec_driver_sql("DROP TRIGGER IF EXISTS reject_evidence_test_receipt "
                                   "ON identity.identity_domain_events")
                db.exec_driver_sql("DROP FUNCTION IF EXISTS identity.reject_evidence_test_receipt()")

    def test_every_route_rechecks_each_independent_grant_after_complete_wire_encoding(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            initial = copy.deepcopy(self.creds)
            for name, extra_action, path, body, matches in self.operations(state):
                for missing in sorted({extra_action, "patient_read", "source_read", "question_read", "authored_evidence_read"}):
                    with self.subTest(operation=name, missing=missing):
                        before = self.persisted_state()
                        observed = []

                        def revoke(encoded):
                            observed.append(encoded)
                            self.creds[0]["actions"].remove(missing)
                            self.write()

                        try:
                            with observe_evidence_encoding(matches, revoke):
                                response = request(base, path, token=TOKEN_A, body=body)
                        finally:
                            self.creds = copy.deepcopy(initial)
                            self.write()
                        self.assertEqual(len(observed), 1, "Must observe actual selected response bytes once")
                        self.assert_denied(response)
                        self.assertEqual(self.persisted_state(), before)

    def test_actor_scope_purpose_or_expiry_change_during_encoding_rolls_back_assessment(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            operation = next(row for row in self.operations(state) if row[0] == "assessment")
            _, _, path, body, matches = operation
            initial = copy.deepcopy(self.creds)
            for field, value, status in (
                ("actor", "ACTOR-REPLACED-DURING-ENCODING", 404),
                ("organization", "ORG-REPLACED-DURING-ENCODING", 404),
                ("patient_ids", [], 404), ("purpose", "research", 404),
                ("expires_at", "2000-01-01T00:00:00+00:00", 401),
            ):
                with self.subTest(field=field):
                    before = self.persisted_state()
                    observed = []

                    def change(encoded):
                        observed.append(encoded)
                        self.creds[0][field] = value
                        self.write()

                    try:
                        with observe_evidence_encoding(matches, change):
                            response = request(base, path, token=TOKEN_A, body=body)
                    finally:
                        self.creds = copy.deepcopy(initial)
                        self.write()
                    self.assertEqual(len(observed), 1)
                    self.assert_denied(response, status)
                    self.assertEqual(self.persisted_state(), before)

    def test_real_encoding_failure_withholds_every_response_and_rolls_back_each_command(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            for name, _, path, body, matches in self.operations(state):
                with self.subTest(operation=name):
                    before = self.persisted_state()
                    observed = []

                    def fail(encoded):
                        observed.append(encoded)
                        raise RuntimeError(PRIVATE_FAILURE)

                    with observe_evidence_encoding(matches, fail):
                        response = request(base, path, token=TOKEN_A, body=body)
                    self.assertEqual(len(observed), 1)
                    self.assert_denied(response, 503)
                    self.assertEqual(self.persisted_state(), before)

    def test_real_audit_insert_failure_rolls_back_versions_assessments_reports_and_withdrawals(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            for name, _, path, body, matches in self.operations(state):
                with self.subTest(operation=name):
                    before = self.persisted_state()
                    observed = []
                    with self.failing_source_receipt(deferred=False):
                        with observe_evidence_encoding(matches, observed.append):
                            response = request(base, path, token=TOKEN_A, body=body)
                    self.assertEqual(len(observed), 1)
                    self.assert_denied(response, 503)
                    self.assertEqual(self.persisted_state(), before)

    def test_real_deferred_commit_failure_withholds_prepared_bytes_and_allows_exact_retry(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            operations = self.operations(state)
            for name, _, path, body, matches in operations:
                with self.subTest(operation=name):
                    before = self.persisted_state()
                    observed = []
                    with self.failing_source_receipt(deferred=True):
                        with observe_evidence_encoding(matches, observed.append):
                            response = request(base, path, token=TOKEN_A, body=body)
                    self.assertEqual(len(observed), 1)
                    self.assert_denied(response, 503)
                    self.assertEqual(self.persisted_state(), before)
            # Retrying the exact failed report command is a first write, not a
            # recovered receipt for an operation that the server never committed.
            _, _, path, body, _ = next(row for row in operations if row[0] == "create_report")
            code, created, _ = request(base, path, token=TOKEN_A, body=body)
            self.assertEqual(code, 201, created)
            self.assertFalse(created["duplicate"])
            code, recovered, _ = request(base, path, token=TOKEN_A, body=body)
            self.assertEqual(code, 200, recovered)
            self.assertEqual(recovered["report_id"], created["report_id"])

    def test_patient_and_case_owner_locks_remain_held_until_report_wire_preparation(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            before = self.persisted_state()
            during = []

            def inspect(encoded):
                locks = []
                for sql in (
                    "SELECT patient_id FROM identity.identity_patients WHERE patient_id=:patient FOR UPDATE NOWAIT",
                    "SELECT case_id FROM coordination.patient_case_bindings WHERE patient_id=:patient FOR UPDATE NOWAIT",
                ):
                    try:
                        with self.engine.begin() as db:
                            db.execute(text(sql), {"patient": state["patient"]}).all()
                    except DBAPIError as error:
                        details = error.orig.args[0] if error.orig.args else None
                        locks.append(details.get("C") if isinstance(details, dict) else None)
                    else:
                        locks.append("acquired")
                during.append((json.loads(encoded), locks, self.persisted_state()))

            with observe_evidence_encoding(lambda value: value.get("contract") == REPORT_CONTRACT, inspect):
                result = self.read_report(base, state["patient"], state["question"], state["report_id"])
            self.assertEqual(result[0], 200, result[1])
            self.assertEqual(len(during), 1)
            self.assertEqual(during[0][0], result[1])
            self.assertEqual(during[0][1], ["55P03", "55P03"])
            self.assertEqual(during[0][2], before)
            after = self.persisted_state()
            for key in before.keys() - {"events"}:
                self.assertEqual(after[key], before[key])
            self.assertEqual(len(after["events"]), len(before["events"]) + 1)

    def test_concurrent_withdrawal_waits_for_prepared_report_then_blocks_subsequent_disclosure(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            future = []
            observed = []
            started = threading.Event()

            def withdraw():
                started.set()
                return self.withdrawn(base, state["patient"], state["question"], state["evidence_id"])

            with ThreadPoolExecutor(max_workers=1) as pool:
                def inspect(encoded):
                    observed.append(encoded)
                    future.append(pool.submit(withdraw))
                    self.assertTrue(started.wait(timeout=2))
                    with self.assertRaises(FutureTimeout):
                        future[0].result(timeout=0.2)

                with observe_evidence_encoding(lambda value: value.get("contract") == REPORT_CONTRACT, inspect):
                    result = self.read_report(base, state["patient"], state["question"], state["report_id"])
                self.assertEqual(result[0], 200, result[1])
                self.assertEqual(len(observed), 1)
                self.assertEqual(result[1]["state"], "current_unreviewed")
                self.assertEqual(result[1]["body"], state["prepared"]["body"])
                withdrawn = future[0].result(timeout=10)
                self.assertEqual(withdrawn[0], 201, withdrawn[1])
            result = self.read_report(base, state["patient"], state["question"], state["report_id"])
            self.assertEqual(result[0], 200, result[1])
            self.assertEqual(result[1]["state"], "content_withheld")
            self.assertIsNone(result[1]["body"])

    def test_concurrent_identical_import_and_assessment_commands_have_one_durable_effect(self):
        with running_server(create_app(self.settings)) as base:
            p, q, _ = self.start(base)

            def concurrent(operation):
                barrier = threading.Barrier(2)
                def submit():
                    barrier.wait(timeout=3)
                    return operation()
                with ThreadPoolExecutor(max_workers=2) as pool:
                    left, right = pool.submit(submit), pool.submit(submit)
                    values = [left.result(timeout=10), right.result(timeout=10)]
                self.assertEqual(sorted(result[0] for result in values), [200, 201], values)
                return values

            imported = concurrent(lambda: self.imported(base, p, q))
            self.assertEqual(imported[0][1]["evidence_id"], imported[1][1]["evidence_id"])
            packet = self.packet(base, p, q)
            body = self.assessment_body(packet, imported[0][1]["evidence_id"])
            assessed = concurrent(lambda: self.assessed(base, p, q, body))
            self.assertEqual(assessed[0][1]["assessment_id"], assessed[1][1]["assessment_id"])
            packet = self.packet(base, p, q)
            body = self.report_body(packet, [assessed[0][1]["assessment_id"]])
            reported = concurrent(lambda: self.reported(base, p, q, body))
            self.assertEqual(reported[0][1]["report_id"], reported[1][1]["report_id"])
            state = self.persisted_state()
            self.assertEqual([len(state[name]) for name in ("versions", "assessments", "reports", "commands")],
                             [1, 1, 1, 3])

    def test_database_guards_preserve_all_immutable_evidence_owners(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            self.assertEqual(self.withdrawn(base, state["patient"], state["question"], state["evidence_id"])[0], 201)
            before = self.persisted_state()
            for table in ("case_evidence_versions", "case_evidence_withdrawals",
                          "question_evidence_assessments", "question_evidence_reports", "evidence_commands", "evidence_command_origins"):
                for statement in (f"DELETE FROM investigation.{table}",
                                  f"UPDATE investigation.{table} SET actor=actor"):
                    with self.subTest(table=table, statement=statement), self.assertRaises(DBAPIError):
                        with self.engine.begin() as db:
                            db.exec_driver_sql(statement)
            self.assertEqual(self.persisted_state(), before)

    def test_recomputed_report_snapshot_and_body_cannot_override_actual_stored_provenance(self):
        """Consistent attacker-controlled hashes are not proof of true custody."""
        from oi_api.evidence_report import render_evidence_report
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            original = state["prepared"]

            def replace(snapshot, body):
                with self.engine.begin() as db:
                    db.exec_driver_sql("ALTER TABLE investigation.question_evidence_reports DISABLE TRIGGER USER")
                    db.execute(text(
                        "UPDATE investigation.question_evidence_reports SET snapshot=CAST(:snapshot AS jsonb),"
                        "snapshot_sha256=:snapshot_sha,body=:body,body_sha256=:body_sha WHERE report_id=:report"
                    ), {"snapshot": json.dumps(snapshot, ensure_ascii=False), "snapshot_sha": digest(snapshot),
                        "body": body, "body_sha": hashlib.sha256(body.encode()).hexdigest(),
                        "report": state["report_id"]})
                    db.exec_driver_sql("ALTER TABLE investigation.question_evidence_reports ENABLE TRIGGER USER")

            for path, field, replacement in (
                (("selected_source",), "statement", "Forged fictional source wording that never appeared in its original."),
                (("comparisons", 0, "evidence"), "title", "Forged fictional title with unchanged original evidence identity"),
                (("comparisons", 0, "assessment"), "rationale", "A forged human rationale was never recorded by the original author."),
                (("question",), "question", "A forged question with an unchanged original identifier?"),
            ):
                with self.subTest(owner=path, field=field):
                    snapshot = copy.deepcopy(original["snapshot"])
                    target = snapshot
                    for component in path:
                        target = target[component]
                    target[field] = replacement
                    body = render_evidence_report(snapshot)
                    self.assertIn(replacement, body)
                    self.assertNotEqual(body, original["body"])
                    try:
                        replace(snapshot, body)
                        corrupted = self.persisted_state()
                        # Packet history and direct report both cross-check the
                        # frozen preparation against actual owner rows.
                        for path in (
                            self.prefix(state["patient"], state["question"]) + "/evidence",
                            self.prefix(state["patient"], state["question"]) + "/evidence-reports/" + state["report_id"],
                        ):
                            self.assert_denied(request(base, path, token=TOKEN_A), 503)
                            self.assertEqual(self.persisted_state(), corrupted)
                    finally:
                        replace(original["snapshot"], original["body"])
            code, recovered, _ = self.read_report(base, state["patient"], state["question"], state["report_id"])
            self.assertEqual(code, 200, recovered)
            self.assertEqual(recovered["snapshot"], original["snapshot"])
            self.assertEqual(recovered["body_sha256"], original["body_sha256"])

    def test_corrupted_original_hash_metadata_or_lineage_withholds_even_historical_report(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            with self.engine.connect() as db:
                original = dict(db.execute(text(
                    "SELECT original_bytes,sha256,title,statement_line,supersedes_id "
                    "FROM investigation.case_evidence_versions WHERE evidence_id=:id"
                ), {"id": state["evidence_id"]}).mappings().one())

            def replace(field, value):
                self.assertIn(field, original)
                with self.engine.begin() as db:
                    db.exec_driver_sql("ALTER TABLE investigation.case_evidence_versions DISABLE TRIGGER USER")
                    db.execute(text("UPDATE investigation.case_evidence_versions SET " + field +
                                    "=:value WHERE evidence_id=:id"),
                               {"value": value, "id": state["evidence_id"]})
                    db.exec_driver_sql("ALTER TABLE investigation.case_evidence_versions ENABLE TRIGGER USER")

            for field, value in (
                ("original_bytes", evidence_text().replace("authored samples", "invented samples").encode()),
                ("sha256", "0" * 64), ("title", "Forged metadata contradicts stored original"),
                ("statement_line", 5), ("supersedes_id", state["evidence_id"]),
            ):
                with self.subTest(field=field):
                    try:
                        replace(field, value)
                        corrupted = self.persisted_state()
                        prefix = self.prefix(state["patient"], state["question"])
                        for path in (prefix + "/evidence", prefix + "/evidence/" + state["evidence_id"] + "/original",
                                     prefix + "/evidence-reports/" + state["report_id"]):
                            self.assert_denied(request(base, path, token=TOKEN_A), 503)
                            self.assertEqual(self.persisted_state(), corrupted)
                    finally:
                        replace(field, original[field])

    services = history.EvidenceConvergenceMigrationTests.services

    def test_migration_downgrade_refuses_to_discard_authored_evidence_history(self):
        # Import on the historical schema so the evidence owner's downgrade
        # guard is reached before an independently populated source outbox.
        revision = "0010_authored_evidence_origin"
        patient, question, _ = history.EvidenceConvergenceMigrationTests.start_at(self, revision)
        with self.services() as registry:
            imported = PostgresQuestionEvidence(registry).import_evidence(
                patient, "CASE-ALPHA", question, **history.OPTIONS,
                payload={"synthetic": True, "request_key": "IMPORT-SUPPORT",
                         "original_text": evidence_text(), "content_item": "full_text",
                         "permissions": permissions("full_text")})
        before = self.persisted_state()
        with self.assertRaisesRegex(CommandError, "Evidence history requires explicit reconciliation"):
            migrate(self.admin, "downgrade", "0008_review_convergence")
        self.assertEqual(self.persisted_state(), before)
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(), revision)

        migrate(self.admin, "upgrade", "head")
        current = self.persisted_state()
        with self.assertRaisesRegex(CommandError, "Stored source delivery history"):
            migrate(self.admin, "downgrade", "0008_review_convergence")
        self.assertEqual(self.persisted_state(), current)
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(),
                             SCHEMA_REVISION)
        with running_server(create_app(self.settings)) as base:
            code, retry, _ = self.imported(base, patient, question)
            self.assertEqual((code, retry["duplicate"], retry["evidence_id"]),
                             (200, True, imported["evidence_id"]))
            self.assertEqual(len(self.packet(base, patient, question)["evidence"]), 1)
