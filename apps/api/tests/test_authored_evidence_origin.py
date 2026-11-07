"""Actual PostgreSQL origin binding, old-owner upgrade and receipt corruption.

The legacy fixture reconstructs the published 0009 schema and report format in
an explicitly disposable database. The migration then runs normally; application
code never rewrites historical source, evidence, assessment, report or command.
"""
import hashlib
import json

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from http_support import running_server
from oi_api.app import create_app
from oi_api.contracts import SCHEMA_REVISION
from oi_api.evidence_report import render_evidence_report
from oi_api.migrate import migrate
from test_authored_evidence_postgres import EvidenceFixture
from test_evidence_convergence_migrations import PublishedEvidenceFixture

HEAD = SCHEMA_REVISION


class EvidenceOriginPostgresTests(PublishedEvidenceFixture, EvidenceFixture):
    def corrupt_command_result(self, operation, key, result):
        # Deliberate administrator corruption probe, not an application write.
        with self.engine.begin() as db:
            db.exec_driver_sql("ALTER TABLE investigation.evidence_commands DISABLE TRIGGER USER")
            db.execute(text("UPDATE investigation.evidence_commands SET result=CAST(:result AS jsonb) "
                            "WHERE operation=:operation AND request_key=:key"),
                       {"result": json.dumps(result), "operation": operation, "key": key})
            db.exec_driver_sql("ALTER TABLE investigation.evidence_commands ENABLE TRIGGER USER")

    def test_assessment_receipt_cannot_redirect_to_same_payload_created_under_another_key(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            p, q = state["patient"], state["question"]
            other = {**state["assessment_body"], "request_key": "SAME-PAYLOAD-SECOND-ASSESSMENT"}
            code, second, _ = self.assessed(base, p, q, other)
            self.assertEqual(code, 201, second)
            self.assertNotEqual(second["assessment_id"], state["assessment"]["assessment_id"])
            self.corrupt_command_result("assess", state["assessment_body"]["request_key"], {
                "assessment_id": second["assessment_id"], "question_id": q,
            })
            before = self.persisted_state()
            self.assert_denied(self.assessed(base, p, q, state["assessment_body"]), expected=503)
            self.assertEqual(self.persisted_state(), before)

    def test_report_receipt_cannot_redirect_to_same_selection_created_under_another_key(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            p, q = state["patient"], state["question"]
            other = {**state["report_body"], "request_key": "SAME-PACKET-SECOND-REPORT"}
            code, second, _ = self.reported(base, p, q, other)
            self.assertEqual(code, 201, second)
            self.assertNotEqual(second["report_id"], state["report_id"])
            self.corrupt_command_result("report", state["report_body"]["request_key"], {
                "report_id": second["report_id"], "question_id": q,
            })
            before = self.persisted_state()
            self.assert_denied(self.reported(base, p, q, state["report_body"]), expected=503)
            self.assertEqual(self.persisted_state(), before)

    def test_new_report_origin_binds_the_exact_inspected_packet_digest(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            with self.engine.connect() as db:
                row = db.execute(text("SELECT expected_packet_sha256,packet_binding,report_renderer "
                                      "FROM investigation.evidence_command_origins WHERE operation='report' "
                                      "AND object_id=:id"), {"id": state["report_id"]}).one()
            self.assertEqual(tuple(row), (state["report_body"]["expected_packet_sha256"],
                                          "explicit_digest", "oi.h1-evidence-text/2"))
            with self.engine.begin() as db:
                db.exec_driver_sql("ALTER TABLE investigation.evidence_command_origins DISABLE TRIGGER USER")
                db.execute(text("UPDATE investigation.evidence_command_origins "
                                "SET expected_packet_sha256=:bad WHERE operation='report' AND object_id=:id"),
                           {"bad": "f" * 64, "id": state["report_id"]})
                db.exec_driver_sql("ALTER TABLE investigation.evidence_command_origins ENABLE TRIGGER USER")
            before = self.persisted_state()
            self.assert_denied(self.reported(base, state["patient"], state["question"], state["report_body"]), expected=503)
            self.assertEqual(self.persisted_state(), before)

    def test_retired_writer_cannot_commit_an_assessment_or_report_without_creating_origin(self):
        with running_server(create_app(self.settings)) as base:
            self.support_report(base)
            before = self.persisted_state()
            statements = (
                "INSERT INTO investigation.question_evidence_assessments "
                "(assessment_id,patient_id,case_id,origin_org,question_id,evidence_id,evidence_sha256,rights_sha256,"
                "source_snapshot_sha256,preflight_sha256,relation,applicability,quote,quote_start,rationale,actor,purpose) "
                "SELECT 'ASSESSMENT-'||repeat('D',32),patient_id,case_id,origin_org,question_id,evidence_id,evidence_sha256,rights_sha256,"
                "source_snapshot_sha256,preflight_sha256,relation,applicability,quote,quote_start,rationale,actor,purpose "
                "FROM investigation.question_evidence_assessments LIMIT 1",
                "INSERT INTO investigation.question_evidence_reports "
                "(report_id,patient_id,case_id,origin_org,question_id,prepared_at,body,body_sha256,snapshot,snapshot_sha256,actor,purpose) "
                "SELECT 'REPORT-'||repeat('E',32),patient_id,case_id,origin_org,question_id,prepared_at,body,body_sha256,snapshot,snapshot_sha256,actor,purpose "
                "FROM investigation.question_evidence_reports LIMIT 1",
            )
            for statement in statements:
                with self.subTest(statement=statement), self.assertRaisesRegex(DBAPIError, "OI-EVIDENCE-CREATING-COMMAND-REQUIRED"):
                    with self.engine.begin() as db:
                        db.exec_driver_sql(statement)
                self.assertEqual(self.persisted_state(), before)

    def legacy_checkpoint(self):
        patient, question, prepared = self.start_at("0010_authored_evidence_origin")
        state = self.seed_authored_report(patient, question, prepared)
        legacy_body = render_evidence_report(state["prepared"]["snapshot"], renderer="oi.h1-evidence-text/1")
        legacy_sha = hashlib.sha256(legacy_body.encode("utf-8")).hexdigest()
        # Author a fixture with the exact published old renderer, at its published
        # owner, before the source outbox existed.
        with self.engine.begin() as db:
            db.exec_driver_sql("ALTER TABLE investigation.question_evidence_reports DISABLE TRIGGER USER")
            db.execute(text("UPDATE investigation.question_evidence_reports SET body=:body,body_sha256=:sha "
                            "WHERE report_id=:id"), {"body": legacy_body, "sha": legacy_sha, "id": state["report_id"]})
            db.exec_driver_sql("ALTER TABLE investigation.question_evidence_reports ENABLE TRIGGER USER")
            db.exec_driver_sql("ALTER TABLE investigation.evidence_command_origins DISABLE TRIGGER USER")
            db.exec_driver_sql("DELETE FROM investigation.evidence_command_origins")
            db.exec_driver_sql("ALTER TABLE investigation.evidence_command_origins ENABLE TRIGGER USER")
        migrate(self.admin, "downgrade", "0009_question_evidence")
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT version_num FROM public.alembic_version"))
                             .scalars().all(), ["0009_question_evidence"])
        state["prepared"] = {**state["prepared"], "body": legacy_body, "body_sha256": legacy_sha}
        return state

    def old_history(self):
        tables = ("case_evidence_versions", "case_evidence_withdrawals", "question_evidence_assessments",
                  "question_evidence_reports", "evidence_commands")
        with self.engine.connect() as db:
            result = {name: db.execute(text(f"SELECT row_to_json(t)::text FROM investigation.{name} t "
                                           "ORDER BY row_to_json(t)::text")).scalars().all() for name in tables}
            result["events"] = db.execute(text("SELECT row_to_json(t)::text FROM identity.identity_domain_events t ORDER BY id")).scalars().all()
        return result

    def test_populated_0009_upgrade_preserves_legacy_report_and_exact_command_recovery(self):
        with running_server(create_app(self.settings)) as base:
            state = self.legacy_checkpoint()
            before = self.old_history()
            migrate(self.admin, "upgrade", "head")
            self.assertEqual(self.old_history(), before)
            with self.engine.connect() as db:
                row = db.execute(text("SELECT packet_binding,expected_packet_sha256,report_renderer "
                                      "FROM investigation.evidence_command_origins WHERE operation='report'")).one()
                revision = db.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
            self.assertEqual(tuple(row), ("intent_digest_only", None, "oi.h1-evidence-text/1"))
            self.assertEqual(revision, HEAD)
            p, q = state["patient"], state["question"]
            code, report, _ = self.read_report(base, p, q, state["report_id"])
            self.assertEqual(code, 200, report)
            for field in ("report_id", "body", "body_sha256", "snapshot", "snapshot_sha256", "prepared_at"):
                self.assertEqual(report[field], state["prepared"][field])
            for command, body, field, identifier in (
                (self.assessed, state["assessment_body"], "assessment_id", state["assessment"]["assessment_id"]),
                (self.reported, state["report_body"], "report_id", state["report_id"]),
            ):
                code, receipt, _ = command(base, p, q, body)
                self.assertEqual(code, 200, receipt)
                self.assertTrue(receipt["duplicate"])
                self.assertEqual(receipt[field], identifier)
            packet = self.packet(base, p, q)
            body = self.report_body(packet, [state["assessment"]["assessment_id"]], key="AFTER-ORIGIN-UPGRADE")
            code, receipt, _ = self.reported(base, p, q, body)
            self.assertEqual(code, 201, receipt)
            code, new_report, _ = self.read_report(base, p, q, receipt["report_id"])
            self.assertEqual(code, 200, new_report)
            self.assertIn("metadata/store: allowed", new_report["body"])
            self.assertNotIn("metadata/store: allowed", report["body"])

    def test_0009_backfill_refuses_missing_or_ambiguous_creating_commands_without_mutation(self):
        with running_server(create_app(self.settings)) as base:
            state = self.legacy_checkpoint()
            for mode in ("missing", "ambiguous"):
                with self.subTest(mode=mode):
                    # Roll the deliberately corrupt setup back after the probe.
                    with self.engine.connect() as db:
                        original = db.execute(text("SELECT result FROM investigation.evidence_commands "
                                                   "WHERE operation='report' AND request_key=:key"),
                                              {"key": state["report_body"]["request_key"]}).scalar_one()
                    if mode == "missing":
                        self.corrupt_command_result("report", state["report_body"]["request_key"], {
                            "report_id": "REPORT-" + "F" * 32, "question_id": state["question"],
                        })
                    else:
                        with self.engine.begin() as db:
                            db.execute(text("INSERT INTO investigation.evidence_commands "
                                            "(patient_id,case_id,origin_org,operation,request_key,intent_sha256,result,actor,purpose) "
                                            "SELECT patient_id,case_id,origin_org,operation,'AMBIGUOUS-LEGACY-REPORT',intent_sha256,result,actor,purpose "
                                            "FROM investigation.evidence_commands WHERE operation='report' AND request_key=:key"),
                                       {"key": state["report_body"]["request_key"]})
                    before = self.old_history()
                    with self.assertRaisesRegex(CommandError, "Missing or ambiguous evidence creating command"):
                        migrate(self.admin, "upgrade", "head")
                    self.assertEqual(self.old_history(), before)
                    with self.engine.connect() as db:
                        self.assertEqual(db.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(),
                                         "0009_question_evidence")
                        self.assertIsNone(db.execute(text("SELECT to_regclass('investigation.evidence_command_origins')")).scalar_one())
                    if mode == "missing":
                        self.corrupt_command_result("report", state["report_body"]["request_key"], original)
                    else:
                        with self.engine.begin() as db:
                            db.exec_driver_sql("ALTER TABLE investigation.evidence_commands DISABLE TRIGGER USER")
                            db.exec_driver_sql("DELETE FROM investigation.evidence_commands WHERE request_key='AMBIGUOUS-LEGACY-REPORT'")
                            db.exec_driver_sql("ALTER TABLE investigation.evidence_commands ENABLE TRIGGER USER")
