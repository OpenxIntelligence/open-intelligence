"""Actual upgrades from each published evidence head preserve existing history.

Seed each old schema through its unchanged domain services. No schema stamping,
readiness bypass, copied patient ledger or alternate report renderer is used.
Current authenticated HTTP is exercised only after the real converging upgrade.
"""
from contextlib import contextmanager

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from oi_api.authored_evidence import PostgresQuestionEvidence as AuthoredEvidence
from oi_api.case_bindings import CanonicalCaseBindings
from oi_api.composer_preflight import PostgresSourceComposerPreflight
from oi_api.database import Database
from oi_api.evidence_catalog import fictional_records, seed_fictional_records
from oi_api.migrate import migrate
from oi_api.question_evidence import PostgresQuestionEvidence as MetadataEvidence
from oi_api.question_followthrough import PostgresQuestionFollowthrough
from oi_api.source_questions import PostgresSourceQuestions
from oi_api.source_world_model import project_source_world_model
from oi_api.sources import PostgresSourceVersions
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_evidence_owner_convergence import AUTHORED_ACTIONS, MERGED_REVISION, ORIGINAL_EVIDENCE, QUOTE
from test_patients import TOKEN_A, request
from test_source_versions import ORIGINAL, SourceVersionFixture


COMMON = {"organization": "ORG-ALPHA", "actor": "ACTOR-ALPHA", "purpose": "operations"}
OPTIONS = {**COMMON, "recheck_authority": lambda: None, "prepare_response": None}


class EvidenceConvergenceMigrationTests(SourceVersionFixture):
    @contextmanager
    def services(self):
        # Direct fixture setup can use a legitimately older schema. It does not
        # relax the application's separate exact-revision readiness boundary.
        pooled = self.engine.raw_connection()
        connection = pooled.driver_connection
        try:
            yield PostgresPatientRegistry(connection, lambda actor, subject, action, purpose:
                actor == "ACTOR-ALPHA" and purpose == "operations")
        finally:
            connection.rollback()
            pooled.close()

    def start_at(self, revision):
        migrate(self.admin, "downgrade", "base")
        migrate(self.admin, "upgrade", revision)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT version_num FROM public.alembic_version"))
                             .scalars().all(), [revision])
        probe = Database(self.settings)
        self.addCleanup(probe.close)
        self.assertEqual(probe.check().status, "schema_mismatch")
        with self.assertRaisesRegex(RuntimeError, "Unsupported migration state"):
            with probe.registry_connection():
                self.fail("Current application accepted an older evidence schema")
        with self.services() as registry:
            patient = registry.create_patient(**COMMON, request_key="UPGRADE-PATIENT")["patient_id"]
            CanonicalCaseBindings(registry).bind(
                patient, **COMMON, case_id="CASE-ALPHA", source_organization="ORG-INSTITUTION",
                source_system="SYS-SYNTH", source_subject_ref="UPGRADE-SUBJECT", review_ref="UPGRADE-REVIEW")
            source = PostgresSourceVersions(registry).import_original(
                patient, "CASE-ALPHA", ORIGINAL.encode("utf-8"), **OPTIONS)["source_id"]
            index = PostgresSourceVersions(registry).list(patient, "CASE-ALPHA", **OPTIONS)
            snapshot = project_source_world_model(index)["snapshot_fingerprint"]
            question_text = "Which fictional continuity details require independent review?"
            prepared = PostgresSourceComposerPreflight(registry).preview(
                patient, "CASE-ALPHA", **OPTIONS, expected_source_snapshot_sha256=snapshot,
                source_id=source, source_line=8, question=question_text)
            question = PostgresSourceQuestions(registry).create(
                patient, "CASE-ALPHA", **OPTIONS, request_key="UPGRADE-QUESTION", source_id=source,
                source_line=8, question=question_text, expected_source_snapshot_sha256=snapshot,
                expected_preflight_sha256=prepared["preflight_sha256"])["question_id"]
        self.creds[0]["patient_ids"].append(patient)
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read", "evidence_read", "evidence_link",
            "followthrough_read", "followthrough_create", *AUTHORED_ACTIONS,
        ))
        self.write()
        return patient, question, prepared

    def snapshot(self, names=None):
        with self.engine.connect() as connection:
            if names is None:
                rows = connection.execute(text(
                    "SELECT table_schema,table_name FROM information_schema.tables "
                    "WHERE table_schema IN ('identity','coordination','clinical_source','investigation') "
                    "AND table_type='BASE TABLE' ORDER BY table_schema,table_name")).all()
                names = [f"{schema}.{name}" for schema, name in rows]
            tables = {name: connection.execute(text(
                f"SELECT row_to_json(t)::text FROM {name} t ORDER BY row_to_json(t)::text"
            )).scalars().all() for name in names}
            sequences = {}
            for schema, name in connection.execute(text(
                "SELECT schemaname,sequencename FROM pg_sequences "
                "WHERE schemaname IN ('identity','coordination','clinical_source','investigation') "
                "ORDER BY schemaname,sequencename")).all():
                sequences[f"{schema}.{name}"] = tuple(connection.execute(text(
                    f"SELECT last_value,is_called FROM {schema}.{name}"
                )).one())
        return tables, sequences

    def upgrade_preserving(self, before):
        migrate(self.admin, "upgrade", "head")
        after = self.snapshot(before[0])
        self.assertEqual(after[0], before[0])
        for name, state in before[1].items():
            self.assertEqual(after[1][name], state)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT version_num FROM public.alembic_version"))
                             .scalars().all(), [MERGED_REVISION])
        probe = Database(self.settings)
        self.addCleanup(probe.close)
        self.assertEqual(probe.check().status, "ready")

    def seed_metadata_task(self, patient, question, prepared):
        context = {"source_snapshot_contract": "oi.pg-source-world-model/1",
                   "expected_source_snapshot_sha256": prepared["source_snapshot_sha256"],
                   "expected_preflight_sha256": prepared["preflight_sha256"]}
        with self.services() as registry:
            seed_fictional_records(registry, fictional_records(), recorded_by="UPGRADE-FIXTURE")
            owner = MetadataEvidence(registry)
            found = owner.search(patient, "CASE-ALPHA", question, **OPTIONS, query="continuity")
            record, = found["records"]
            link_intent = {**context, "request_key": "UPGRADE-CITATION", "citation": record["citation"],
                           "expected_metadata_sha256": record["metadata_sha256"]}
            link = owner.create_link(patient, "CASE-ALPHA", question, **OPTIONS, **link_intent)
            task_intent = {**context, "request_key": "UPGRADE-TASK", "title": "Review the fictional sources",
                           "detail": "", "owner_label": "", "due_date": None,
                           "review_trigger": "When the source changes", "reason": "Preserve the authored follow-up work."}
            task = PostgresQuestionFollowthrough(registry).create(
                patient, "CASE-ALPHA", question, **OPTIONS, **task_intent)
        return link_intent, link, task_intent, task

    def test_populated_metadata_head_upgrades_without_changing_citations_or_tasks(self):
        patient, question, prepared = self.start_at("0010_question_evidence")
        link_intent, link, task_intent, task = self.seed_metadata_task(patient, question, prepared)
        self.upgrade_preserving(self.snapshot())
        prefix = f"/v1/patients/{patient}/cases/CASE-ALPHA/questions/{question}"
        with running_server(create_app(self.settings)) as base:
            for suffix, intent, receipt in (("/evidence-links", link_intent, link),
                                           ("/followthrough", task_intent, task)):
                code, actual, _ = request(base, prefix + suffix, token=TOKEN_A,
                                           body={"synthetic": True, **intent})
                self.assertEqual((code, actual), (200, {**receipt, "duplicate": True}))
            code, packet, _ = request(base, prefix + "/evidence", token=TOKEN_A)
            self.assertEqual(code, 200, packet)
            self.assertEqual((packet["evidence"], packet["assessments"], packet["reports"]), ([], [], []))

    def test_populated_authored_head_upgrades_without_changing_report_bytes_or_retry_identity(self):
        patient, question, prepared = self.start_at("0010_authored_evidence_origin")
        rights = {item: {use: "unknown" for use in ("store", "display", "redistribute", "ml_use")}
                  for item in ("metadata", "abstract", "full_text", "figures", "terminology", "api_output")}
        for item in ("metadata", "api_output"):
            rights[item].update(store="allowed", display="allowed", redistribute="allowed")
        with self.services() as registry:
            owner = AuthoredEvidence(registry)
            original = owner.import_evidence(patient, "CASE-ALPHA", question, **OPTIONS,
                payload={"synthetic": True, "request_key": "UPGRADE-ORIGINAL", "original_text": ORIGINAL_EVIDENCE,
                         "content_item": "api_output", "permissions": rights})
            packet = owner.packet(patient, "CASE-ALPHA", question, **OPTIONS)
            evidence, = packet["evidence"]
            assessment_intent = {
                "synthetic": True, "request_key": "UPGRADE-ASSESSMENT", "evidence_id": original["evidence_id"],
                "evidence_sha256": evidence["sha256"], "rights_sha256": evidence["rights_sha256"],
                "expected_source_snapshot_sha256": prepared["source_snapshot_sha256"],
                "expected_preflight_sha256": prepared["preflight_sha256"],
                "quote": QUOTE, "relation": "context", "applicability": "limited",
                "rationale": "This fictional preparation requires independent human review.",
            }
            assessment = owner.assess(patient, "CASE-ALPHA", question, **OPTIONS, payload=assessment_intent)
            packet = owner.packet(patient, "CASE-ALPHA", question, **OPTIONS)
            report_intent = {"synthetic": True, "request_key": "UPGRADE-REPORT",
                             "expected_packet_sha256": packet["packet_sha256"],
                             "assessment_ids": [assessment["assessment_id"]]}
            report = owner.create_report(patient, "CASE-ALPHA", question, **OPTIONS, payload=report_intent)
            frozen = owner.report(patient, "CASE-ALPHA", question, report["report_id"], **OPTIONS)
        self.upgrade_preserving(self.snapshot())
        prefix = f"/v1/patients/{patient}/cases/CASE-ALPHA/questions/{question}"
        with running_server(create_app(self.settings)) as base:
            code, reopened, _ = request(base, prefix + "/evidence-reports/" + report["report_id"], token=TOKEN_A)
            self.assertEqual(code, 200, reopened)
            for field in ("report_id", "body", "body_sha256", "snapshot", "snapshot_sha256", "prepared_at"):
                self.assertEqual(reopened[field], frozen[field])
            for suffix, intent, receipt in (("/evidence-assessments", assessment_intent, assessment),
                                           ("/evidence-reports", report_intent, report)):
                code, actual, _ = request(base, prefix + suffix, token=TOKEN_A, body=intent)
                self.assertEqual((code, actual), (200, {**receipt, "duplicate": True}))
            code, metadata, _ = request(base, prefix + "/evidence-links", token=TOKEN_A)
            self.assertEqual((code, metadata["links"]), (200, []))

    def test_populated_two_head_state_stays_unready_until_explicit_merge(self):
        patient, question, prepared = self.start_at("0010_question_evidence")
        self.seed_metadata_task(patient, question, prepared)
        before = self.snapshot()
        migrate(self.admin, "upgrade", "0010_authored_evidence_origin")
        with self.engine.connect() as connection:
            self.assertEqual(set(connection.execute(text("SELECT version_num FROM public.alembic_version"))
                                 .scalars()), {"0010_question_evidence", "0010_authored_evidence_origin"})
        probe = Database(self.settings)
        self.addCleanup(probe.close)
        self.assertEqual(probe.check().status, "schema_mismatch")
        with self.assertRaisesRegex(RuntimeError, "Unsupported migration state"):
            with probe.registry_connection():
                self.fail("Current application accepted an unconverged two-head schema")
        self.upgrade_preserving(before)
