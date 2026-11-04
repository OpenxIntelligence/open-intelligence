"""Real populated upgrades from the two published 0011 owner histories.

No schema stamp, fabricated migration state or application readiness bypass is
used. Direct existing owner services populate legitimate old schemas; current
authenticated HTTP begins only after the explicit converging migration.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from oi_api.authored_evidence import PostgresQuestionEvidence
from oi_api.case_bindings import CanonicalCaseBindings
from oi_api.composer_preflight import PostgresSourceComposerPreflight
from oi_api.database import Database
from oi_api.contracts import SCHEMA_REVISION
from oi_api.migrate import migrate
from oi_api.source_questions import PostgresSourceQuestions
from oi_api.source_world_model import project_source_world_model
from oi_api.sources import PostgresSourceVersions
from test_evidence_convergence_migrations import COMMON, OPTIONS
import test_evidence_convergence_migrations as existing_upgrades
from test_evidence_owner_convergence import AUTHORED_ACTIONS, ORIGINAL_EVIDENCE, QUOTE
from test_image_report_convergence import (
    IMAGE_ACTIONS, IMAGE_REVISION, IMAGING_ORIGINAL, MERGED_REVISION, REPORT_REVISION, declared_rights,
)
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


class ImageReportConvergenceMigrationTests(SourceVersionFixture):
    services = existing_upgrades.EvidenceConvergenceMigrationTests.services
    snapshot = existing_upgrades.EvidenceConvergenceMigrationTests.snapshot
    seed_metadata_task = existing_upgrades.EvidenceConvergenceMigrationTests.seed_metadata_task

    def require_graph(self):
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        revisions = {item.revision for item in ScriptDirectory.from_config(config).walk_revisions()}
        self.assertIn(MERGED_REVISION, revisions,
                      "The published image/report owners have no explicit joining migration")
        self.assertIn(IMAGE_REVISION, revisions)

    def heads(self):
        with self.engine.connect() as connection:
            return set(connection.execute(text("SELECT version_num FROM public.alembic_version")).scalars())

    def readiness(self, ready):
        database = Database(self.settings)
        try:
            self.assertEqual(database.check().status, "ready" if ready else "schema_mismatch")
            if not ready:
                with self.assertRaisesRegex(RuntimeError, "Unsupported migration state"):
                    with database.registry_connection():
                        self.fail("Current application accepted an incomplete historical schema")
        finally:
            database.close()

    def start_at(self, revision):
        self.require_graph()
        migrate(self.admin, "downgrade", "base")
        migrate(self.admin, "upgrade", revision)
        self.assertEqual(self.heads(), {revision})
        self.readiness(False)
        with self.services() as registry:
            patient = registry.create_patient(**COMMON, request_key="JOINED-UPGRADE-PATIENT")["patient_id"]
            CanonicalCaseBindings(registry).bind(patient, **COMMON, case_id="CASE-ALPHA",
                source_organization="ORG-INSTITUTION", source_system="SYS-SYNTH",
                source_subject_ref="SUBJECT-ALPHA", review_ref="INDEPENDENT-UPGRADE-REVIEW")
            source = PostgresSourceVersions(registry).import_original(
                patient, "CASE-ALPHA", IMAGING_ORIGINAL.encode(), **OPTIONS)["source_id"]
            index = PostgresSourceVersions(registry).list(patient, "CASE-ALPHA", **OPTIONS)
            fingerprint = project_source_world_model(index)["snapshot_fingerprint"]
            title = "Which independently fictional source anchors still require review?"
            prepared = PostgresSourceComposerPreflight(registry).preview(patient, "CASE-ALPHA", **OPTIONS,
                source_id=source, source_line=8, question=title, expected_source_snapshot_sha256=fingerprint)
            question = PostgresSourceQuestions(registry).create(patient, "CASE-ALPHA", **OPTIONS,
                request_key="JOINED-UPGRADE-QUESTION", question=title, source_id=source, source_line=8,
                expected_source_snapshot_sha256=fingerprint,
                expected_preflight_sha256=prepared["preflight_sha256"])["question_id"]
        self.creds[0]["patient_ids"].append(patient)
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read", "evidence_read", "evidence_link",
            "followthrough_read", "followthrough_create", *AUTHORED_ACTIONS, *IMAGE_ACTIONS,
        ))
        self.write()
        link_intent, link, task_intent, task = self.seed_metadata_task(patient, question, prepared)
        return dict(patient=patient, question=question, prepared=prepared, source=source,
                    prefix=f"/v1/patients/{patient}/cases/CASE-ALPHA/questions/{question}",
                    writes=[("/evidence-links", link_intent, link), ("/followthrough", task_intent, task)])

    def seed_report(self, flow):
        with self.services() as registry:
            owner = PostgresQuestionEvidence(registry)
            imported = owner.import_evidence(flow["patient"], "CASE-ALPHA", flow["question"], **OPTIONS,
                payload={"synthetic": True, "request_key": "JOINED-UPGRADE-EVIDENCE",
                         "original_text": ORIGINAL_EVIDENCE, "content_item": "api_output",
                         "permissions": declared_rights()})
            packet = owner.packet(flow["patient"], "CASE-ALPHA", flow["question"], **OPTIONS)
            evidence, = packet["evidence"]
            comparison_intent = {"synthetic": True, "request_key": "JOINED-UPGRADE-COMPARISON",
                "evidence_id": imported["evidence_id"], "evidence_sha256": evidence["sha256"],
                "rights_sha256": evidence["rights_sha256"],
                "expected_source_snapshot_sha256": flow["prepared"]["source_snapshot_sha256"],
                "expected_preflight_sha256": flow["prepared"]["preflight_sha256"],
                "quote": QUOTE, "relation": "context", "applicability": "limited",
                "rationale": "The independently authored fixture does not establish clinical applicability."}
            comparison = owner.assess(flow["patient"], "CASE-ALPHA", flow["question"], **OPTIONS,
                                      payload=comparison_intent)
            packet = owner.packet(flow["patient"], "CASE-ALPHA", flow["question"], **OPTIONS)
            report_intent = {"synthetic": True, "request_key": "JOINED-UPGRADE-REPORT",
                             "expected_packet_sha256": packet["packet_sha256"],
                             "assessment_ids": [comparison["assessment_id"]]}
            prepared = owner.create_report(flow["patient"], "CASE-ALPHA", flow["question"], **OPTIONS,
                                           payload=report_intent)
            flow["report"] = owner.report(flow["patient"], "CASE-ALPHA", flow["question"],
                                          prepared["report_id"], **OPTIONS)
        flow["writes"].extend((("/evidence-assessments", comparison_intent, comparison),
                               ("/evidence-reports", report_intent, prepared)))

    def seed_image(self, flow):
        # Called only after the actual published image schema is installed.
        from oi_api.images import PostgresSourceImages
        from test_image_custody import image_bytes
        flow["raw"] = image_bytes(study_date="20260110")
        with self.services() as registry:
            flow["image"] = PostgresSourceImages(registry).import_original(
                flow["patient"], "CASE-ALPHA", flow["source"], flow["raw"], **OPTIONS)

    def schema_definition(self):
        scope = "('identity','coordination','clinical_source','investigation')"
        queries = {
            "columns": "SELECT table_schema,table_name,column_name,ordinal_position,data_type,udt_name,"
                       "is_nullable,column_default FROM information_schema.columns "
                       f"WHERE table_schema IN {scope} ORDER BY 1,2,4",
            "constraints": "SELECT n.nspname,c.relname,k.conname,pg_get_constraintdef(k.oid) "
                           "FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid "
                           f"JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN {scope} ORDER BY 1,2,3",
            "indexes": f"SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes WHERE schemaname IN {scope} ORDER BY 1,2,3",
            "functions": "SELECT n.nspname,p.proname,pg_get_functiondef(p.oid) FROM pg_proc p "
                         f"JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN {scope} ORDER BY 1,2",
            "triggers": "SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t "
                        "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                        f"WHERE NOT t.tgisinternal AND n.nspname IN {scope} ORDER BY 1,2,3",
        }
        with self.engine.connect() as connection:
            return {name: [tuple(row) for row in connection.execute(text(query))]
                    for name, query in queries.items()}

    def upgrade_preserving(self, before, target=SCHEMA_REVISION):
        migrate(self.admin, "upgrade", target)
        after = self.snapshot(before[0])
        self.assertEqual(after[0], before[0])
        for name, state in before[1].items():
            self.assertEqual(after[1][name], state, name)
        self.assertEqual(self.heads(), {target})
        self.readiness(target == SCHEMA_REVISION)

    def reopen(self, flow):
        from test_image_custody import image_request
        case = f"/v1/patients/{flow['patient']}/cases/CASE-ALPHA"
        image_path = case + "/sources/" + flow["source"] + "/images"
        with running_server(create_app(self.settings)) as base:
            for suffix, intent, receipt in flow["writes"]:
                code, actual, _ = request(base, flow["prefix"] + suffix, token=TOKEN_A,
                                          body={"synthetic": True, **intent})
                self.assertEqual((code, actual), (200, {**receipt, "duplicate": True}))
            if "image" in flow:
                self.assertEqual(image_request(base, image_path + "/" + flow["image"]["image_id"])[:2],
                                 (200, flow["raw"]))
                self.assertEqual(image_request(base, image_path, raw=flow["raw"])[:2],
                                 (200, {**flow["image"], "result": "duplicate"}))
            else:
                code, index, _ = request(base, image_path, token=TOKEN_A)
                self.assertEqual((code, index["images"]), (200, []))
            if "report" in flow:
                frozen = flow["report"]
                code, actual, _ = request(base, flow["prefix"] + "/evidence-reports/" + frozen["report_id"], token=TOKEN_A)
                self.assertEqual(code, 200, actual)
                for name in ("report_id", "body", "body_sha256", "snapshot", "snapshot_sha256", "prepared_at"):
                    self.assertEqual(actual[name], frozen[name], name)
            else:
                code, packet, _ = request(base, flow["prefix"] + "/evidence", token=TOKEN_A)
                self.assertEqual(code, 200, packet)
                self.assertEqual((packet["evidence"], packet["assessments"], packet["reports"]), ([], [], []))

    def test_populated_report_head_adds_images_without_changing_report_citation_or_task(self):
        flow = self.start_at(REPORT_REVISION)
        self.seed_report(flow)
        before = self.snapshot()
        self.assertNotIn("clinical_source.dicom_objects", before[0])
        self.upgrade_preserving(before)
        self.reopen(flow)

    def test_populated_image_head_adds_authored_reports_without_changing_originals_or_tasks(self):
        flow = self.start_at(IMAGE_REVISION)
        self.seed_image(flow)
        before = self.snapshot()
        self.assertNotIn("investigation.case_evidence_versions", before[0])
        self.upgrade_preserving(before)
        self.reopen(flow)

    def test_both_populated_0011_heads_need_only_a_reversible_no_ddl_join(self):
        flow = self.start_at(REPORT_REVISION)
        self.seed_report(flow)
        migrate(self.admin, "upgrade", IMAGE_REVISION)
        self.seed_image(flow)
        self.assertEqual(self.heads(), {REPORT_REVISION, IMAGE_REVISION})
        self.readiness(False)
        before, definitions = self.snapshot(), self.schema_definition()
        self.upgrade_preserving(before, target=MERGED_REVISION)
        self.assertEqual(self.schema_definition(), definitions)
        self.assertEqual(self.snapshot(), before)
        # Removing the joining node must change version bookkeeping only.
        migrate(self.admin, "downgrade", REPORT_REVISION)
        self.assertEqual(self.heads(), {REPORT_REVISION, IMAGE_REVISION})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.schema_definition(), definitions)
        self.readiness(False)
        self.upgrade_preserving(before)
        self.reopen(flow)
