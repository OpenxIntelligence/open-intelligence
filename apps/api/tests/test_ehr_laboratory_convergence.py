"""Upgrade either published 0019 history with independently fictional records."""
import json
import unittest
import uuid

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from http_support import running_server
from oi_api.app import create_app
from oi_api.contracts import SCHEMA_REVISION
from oi_api.evidence_catalog import fictional_records, seed_fictional_records
from oi_api.migrate import migrate
from oi_api.question_evidence import PostgresLaboratoryQuestionEvidence
from oi_api.sources import PostgresSourceVersions
from open_intelligence.patient_registry import PatientRegistryConflict, _digest
from open_intelligence.postgres_encounters import PostgresClinicalEncounters
import test_evidence_convergence_migrations as evidence
import test_image_report_convergence_migrations as migrations
import test_lab_manual_convergence as laboratory
import test_laboratory_question_migration as questions
import test_document_image_convergence as document_convergence
from test_document_image_convergence import graph
from test_durable_laboratory_questions import LAB_HISTORY
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture

EHR = "0019_ehr_encounters"
LAB = "0019_laboratory_citations"
LAB_SCOPE = "0022_lab_citation_source_scope"
EHR_OWNERSHIP = "0022_ehr_patient_ownership"
COMMON = "0018_laboratory_questions"
EHR_TABLES = ["ehr.clinical_" + name for name in
              ("encounters", "note_headers", "note_versions", "encounter_commands")]
NOTE = {"body": "Independently fictional consultation draft.", "request_key": "JOIN-NOTE",
        "expected_version": 0}


class EHRLaboratoryGraphTests(unittest.TestCase):
    def test_single_head_depends_on_both_published_owners(self):
        script = graph()
        self.assertEqual(script.get_heads(), [SCHEMA_REVISION])
        self.assertEqual(script.get_revision("0023_lab_question_followthrough").down_revision, "0022_lab_citation_source_scope")
        self.assertEqual(script.get_revision("0022_lab_citation_source_scope").down_revision,
                         "0021_lab_citation_freshness")
        self.assertEqual(script.get_revision("0021_lab_citation_freshness").down_revision,
                         "0020_ehr_lab_convergence")
        self.assertEqual(set(script.get_revision("0020_ehr_lab_convergence").down_revision), {EHR, LAB})
        for parent in (EHR, LAB):
            self.assertEqual(script.get_revision(parent).down_revision, COMMON)


class EHRLaboratoryUpgradeTests(SourceVersionFixture):
    services = evidence.EvidenceConvergenceMigrationTests.services
    start_at = evidence.EvidenceConvergenceMigrationTests.start_at
    snapshot = evidence.EvidenceConvergenceMigrationTests.snapshot
    heads = migrations.ImageReportConvergenceMigrationTests.heads
    readiness = migrations.ImageReportConvergenceMigrationTests.readiness
    seed_lab = laboratory.LabManualPopulatedMigrationTests.seed_lab

    def seed_encounter(self, patient):
        scope = {"actor": "ACTOR-ALPHA", "purpose": "operations"}
        with self.services() as registry:
            service = PostgresClinicalEncounters(registry, registry.authorizer)
            visit = service.schedule(patient, "JOIN-VISIT", "outpatient", "2026-01-10",
                                     request_key="JOIN-SCHEDULE", **scope)["encounter_id"]
            service.transition(patient, visit, "in_progress", expected_revision=1,
                               request_key="JOIN-START", **scope)
            note = service.write_note(patient, visit, "JOIN-DRAFT", **NOTE, **scope)
        self.creds[0]["actions"].extend(("encounter.read", "note.write", "note.read"))
        self.write()
        return f"/v1/patients/{patient}/encounters/{visit}/notes/JOIN-DRAFT/versions", note

    def seed_citation(self):
        patient, _, payload, saved = questions.LaboratoryQuestionMigrationTests.seed(self)
        migrate(self.admin, "upgrade", LAB)
        scope = (patient, "CASE-ALPHA", saved["question_id"])
        with self.services() as registry:
            seed_fictional_records(registry, fictional_records(), recorded_by="FICTIONAL-AUTHOR")
            owner = PostgresLaboratoryQuestionEvidence(registry)
            record, = owner.search(*scope, query="continuity", **evidence.OPTIONS)["records"]
            command = dict(citation=record["citation"], expected_metadata_sha256=record["metadata_sha256"],
                           source_snapshot_contract="oi.pg-source-world-model/1",
                           expected_source_snapshot_sha256=payload["expected_source_snapshot_sha256"],
                           expected_preflight_sha256=payload["expected_preflight_sha256"],
                           request_key="JOIN-CITATION")
            receipt = owner.create_link(*scope, **command, **evidence.OPTIONS)
        url = f"/v1/patients/{patient}/cases/CASE-ALPHA{LAB_HISTORY}/{saved['question_id']}/evidence-links"
        return patient, url, command, receipt

    def test_reviewed_document_preserves_citation_through_guard_upgrade_and_downgrade(self):
        patient, url, command, receipt = self.seed_citation()
        previous = "0021_lab_citation_freshness"
        migrate(self.admin, "upgrade", previous)
        # Exercise the changing citation guard with both sibling schemas present.
        migrate(self.admin, "upgrade", "0020_source_event_delivery")
        # Ordinary reviewed bytes and user selections are outside this saved
        # laboratory question's canonical structured-source snapshot. Import
        # them after the question, while the published guard is still present.
        document = {"patient": patient}
        document_convergence.DocumentImageConvergenceMigrationTests.seed_document(self, document)
        before = self.snapshot()
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        self.assertEqual(self.snapshot(), (before[0] | {"clinical_source.episode_drafts": []}, before[1]))

        with running_server(create_app(self.settings)) as base:
            status, page, _ = request(base, url, token=TOKEN_A)
            self.assertEqual(status, 200, page)
            self.assertEqual(page["source_context_state"], "current_unreviewed_question")
            self.assertEqual([link["link_id"] for link in page["links"]], [receipt["link_id"]])
            history_url = url.rsplit("/", 2)[0]
            status, history, _ = request(base, history_url, token=TOKEN_A)
            self.assertEqual(status, 200, history)
            question, = history["questions"]
            self.assertEqual(question["source_context_state"], "current_unreviewed_question")
            self.assertEqual(question["source_snapshot_sha256"], command["expected_source_snapshot_sha256"])

            new_command = {**command, "request_key": "CITATION-AFTER-REVIEWED-DOCUMENT"}
            status, saved, _ = request(base, url, token=TOKEN_A, body={"synthetic": True, **new_command})
            self.assertEqual(status, 201, saved)
            self.assertFalse(saved["duplicate"])
            self.assertNotEqual(saved["link_id"], receipt["link_id"])
            self.assertEqual(request(base, url, token=TOKEN_A,
                                     body={"synthetic": True, **new_command})[:2],
                             (200, saved | {"duplicate": True}))
            status, page, _ = request(base, url, token=TOKEN_A)
            self.assertEqual(status, 200, page)
            self.assertEqual(page["source_context_state"], "current_unreviewed_question")
            self.assertEqual({link["link_id"] for link in page["links"]},
                             {receipt["link_id"], saved["link_id"]})

        key = "DIRECT-CITATION-AFTER-REVIEWED-DOCUMENT"
        link_id = "EVIDENCE-LINK-" + uuid.uuid4().hex.upper()
        intent = _digest(dict(operation="evidence.link", patient_id=patient, case_id="CASE-ALPHA",
                              question_id=url.split("/")[-2], **evidence.COMMON, request_key=key,
                              citation=command["citation"], metadata_sha256=command["expected_metadata_sha256"],
                              source_snapshot_contract=command["source_snapshot_contract"],
                              source_snapshot_sha256=command["expected_source_snapshot_sha256"],
                              preflight_sha256=command["expected_preflight_sha256"]))

        def write_directly(conn):
            params = {"prior": receipt["link_id"], "link": link_id, "replacements": json.dumps(
                {"link_id": link_id, "request_key": key, "intent_sha256": intent})}
            conn.execute(text("""
                INSERT INTO investigation.laboratory_citation_anchors
                    (link_id,question_id,source_id,observation_reference,rights_decision_id)
                SELECT :link,question_id,source_id,observation_reference,rights_decision_id
                FROM investigation.laboratory_citation_anchors WHERE link_id=:prior
            """), params)
            conn.execute(text("""
                INSERT INTO investigation.question_evidence_links
                SELECT (jsonb_populate_record(NULL::investigation.question_evidence_links,
                    to_jsonb(l) || CAST(:replacements AS jsonb))).*
                FROM investigation.question_evidence_links l WHERE link_id=:prior
            """), params)
            conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            self.assertEqual(conn.execute(text("SELECT count(*) FROM investigation.question_evidence_links "
                                               "WHERE link_id=:link"), params).scalar_one(), 1)

        # The database boundary must agree with the API, including its deferred
        # typed-anchor checks. These controls roll back their provisional row.
        before = self.snapshot()
        with self.engine.connect() as conn:
            write_directly(conn)
            conn.rollback()
        self.assertEqual(self.snapshot(), before)
        migrate(self.admin, "downgrade", previous)
        old_tables = dict(before[0])
        self.assertEqual(old_tables.pop("clinical_source.episode_drafts"), [])
        self.assertEqual(self.snapshot(), (old_tables, before[1]))
        with self.assertRaisesRegex(DBAPIError, "OI-LAB-CITATION-CASE-SOURCES-CHANGED"):
            with self.engine.begin() as conn:
                write_directly(conn)
        self.assertEqual(self.snapshot(), (old_tables, before[1]))
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        self.assertEqual(self.snapshot(), before)
        with self.engine.connect() as conn:
            write_directly(conn)
            conn.rollback()
        self.assertEqual(self.snapshot(), before)
        with running_server(create_app(self.settings)) as base:
            status, restored, _ = request(base, url, token=TOKEN_A,
                body={"synthetic": True, **command, "request_key": "CITATION-AFTER-GUARD-REUPGRADE"})
            self.assertEqual(status, 201, restored)
            self.assertFalse(restored["duplicate"])
            self.assertNotIn(restored["link_id"], {receipt["link_id"], saved["link_id"]})

    def test_new_citation_refuses_an_independent_case_source_at_the_database_boundary(self):
        patient, url, command, receipt = self.seed_citation()
        migrate(self.admin, "upgrade", "0020_ehr_lab_convergence")
        case = "CASE-ALPHA"
        question = url.split("/")[-2]
        scope = (patient, case, question)
        newer = evidence.ORIGINAL.replace("Document: DOC-ONE", "Document: DOC-TWO")
        key = "CITATION-AFTER-INDEPENDENT-IMPORT"
        link = "EVIDENCE-LINK-" + uuid.uuid4().hex.upper()
        intent = _digest(dict(operation="evidence.link", patient_id=patient, case_id=case,
                              question_id=question, **evidence.COMMON, request_key=key,
                              citation=command["citation"], metadata_sha256=command["expected_metadata_sha256"],
                              source_snapshot_contract=command["source_snapshot_contract"],
                              source_snapshot_sha256=command["expected_source_snapshot_sha256"],
                              preflight_sha256=command["expected_preflight_sha256"]))

        def write_directly(conn):
            # Submit the same new command to both schemas, including its exact
            # rights decision and observation foreign key. Force deferred checks.
            params = {"prior": receipt["link_id"], "link": link, "replacements": json.dumps(
                {"link_id": link, "request_key": key, "intent_sha256": intent})}
            conn.execute(text("""
                INSERT INTO investigation.laboratory_citation_anchors
                    (link_id,question_id,source_id,observation_reference,rights_decision_id)
                SELECT :link,question_id,source_id,observation_reference,rights_decision_id
                FROM investigation.laboratory_citation_anchors WHERE link_id=:prior
            """), params)
            conn.execute(text("""
                INSERT INTO investigation.question_evidence_links
                SELECT (jsonb_populate_record(NULL::investigation.question_evidence_links,
                    to_jsonb(l) || CAST(:replacements AS jsonb))).*
                FROM investigation.question_evidence_links l WHERE link_id=:prior
            """), params)
            conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            self.assertEqual(conn.execute(text("SELECT count(*) FROM investigation.question_evidence_links "
                                               "WHERE link_id=:link"), params).scalar_one(), 1)

        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        # A fresh new key is valid even for an anchor saved before upgrade.
        with self.engine.connect() as conn:
            write_directly(conn)
            conn.rollback()

        count_sources = text("SELECT count(*) FROM clinical_source.source_versions WHERE case_id=:case")
        with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            at_start = conn.execute(count_sources, {"case": case}).scalar_one()
            # Separate connection and committed import after the writer's snapshot.
            with self.services() as registry:
                PostgresSourceVersions(registry).import_original(
                    patient, case, newer.encode(), **evidence.OPTIONS)
            self.assertEqual(conn.execute(count_sources, {"case": case}).scalar_one(), at_start)
            with self.assertRaisesRegex(DBAPIError, "OI-LAB-CITATION-READ-COMMITTED-REQUIRED"):
                write_directly(conn)
        with self.services() as registry:
            owner = PostgresLaboratoryQuestionEvidence(registry)
            self.assertEqual(owner.links(*scope, **evidence.OPTIONS)["source_context_state"],
                             "source_reassessment_required")
            with self.assertRaises(PatientRegistryConflict):
                owner.create_link(*scope, **{**command, "request_key": key}, **evidence.OPTIONS)

        migrate(self.admin, "downgrade", "0020_ehr_lab_convergence")
        # Demonstrate the old schema accepted this command, then roll it back.
        with self.engine.connect() as conn:
            with conn.begin_nested() as control:
                write_directly(conn)
                control.rollback()
        before = self.snapshot()
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        with self.assertRaisesRegex(DBAPIError, "OI-LAB-CITATION-CASE-SOURCES-CHANGED"):
            with self.engine.begin() as conn:
                write_directly(conn)
        self.assertEqual(self.snapshot(before[0])[0], before[0])
        with self.services() as registry:
            retry = PostgresLaboratoryQuestionEvidence(registry).create_link(*scope, **command, **evidence.OPTIONS)
            self.assertTrue(retry["duplicate"])
            self.assertEqual(retry["link_id"], receipt["link_id"])

    def ownership_fixture(self):
        patient_a, _, _ = self.start_at(LAB_SCOPE)
        note_url, note = self.seed_encounter(patient_a)
        encounter_a = int(note_url.split("/encounters/")[1].split("/")[0])
        with self.services() as registry:
            patient_b = registry.create_patient(**evidence.COMMON, request_key="OWNERSHIP-PATIENT-B")["patient_id"]
            service = PostgresClinicalEncounters(registry, registry.authorizer)
            encounter_b = service.schedule(patient_b, "OWNERSHIP-VISIT-B", "outpatient", "2026-02-10",
                                           actor="ACTOR-ALPHA", purpose="operations",
                                           request_key="OWNERSHIP-SCHEDULE-B")["encounter_id"]
        self.creds[0]["patient_ids"].append(patient_b)
        self.write()
        return patient_a, encounter_a, patient_b, encounter_b, note_url, note

    def test_encounter_and_note_ownership_survive_direct_reassignment_attempts(self):
        patient_a, encounter_a, patient_b, encounter_b, note_url, note = self.ownership_fixture()
        headers_b = f"/v1/patients/{patient_b}/encounters/{encounter_b}/notes"
        history_b = headers_b + "/JOIN-DRAFT/versions"
        move_header = text("UPDATE ehr.clinical_note_headers SET encounter_id=:owner WHERE id=:id")
        move_visit = text("UPDATE ehr.clinical_encounters SET patient_id=:owner WHERE id=:id")
        # Exhibit the old cross-patient read on populated records. The first
        # upgrade must refuse to certify that pre-existing damaged ownership.
        with self.engine.begin() as conn:
            conn.execute(move_header, {"owner": encounter_b, "id": note["note_id"]})
        with self.services() as registry:
            service = PostgresClinicalEncounters(registry, registry.authorizer)
            versions = service.note_history(patient_b, encounter_b, "JOIN-DRAFT",
                                            actor="ACTOR-ALPHA", purpose="operations")
            self.assertEqual(versions[0]["body"], NOTE["body"])
        with self.assertRaisesRegex(CommandError, "ownership requires explicit reconciliation"):
            migrate(self.admin, "upgrade", SCHEMA_REVISION)
        self.assertEqual(self.heads(), {LAB_SCOPE})
        with self.engine.begin() as conn:
            conn.execute(move_header, {"owner": encounter_a, "id": note["note_id"]})
            conn.execute(move_visit, {"owner": patient_b, "id": encounter_a})
        with self.assertRaisesRegex(CommandError, "ownership requires explicit reconciliation"):
            migrate(self.admin, "upgrade", SCHEMA_REVISION)
        with self.engine.begin() as conn:
            conn.execute(move_visit, {"owner": patient_a, "id": encounter_a})
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        for statement, owner, row in ((move_header, encounter_b, note["note_id"]),
                                      (move_visit, patient_b, encounter_a)):
            with self.assertRaisesRegex(DBAPIError, "HISTORY-IMMUTABLE"):
                with self.engine.begin() as conn:
                    conn.execute(statement, {"owner": owner, "id": row})
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(request(base, headers_b, token=TOKEN_A)[1]["notes"], [])
            status, history, _ = request(base, history_b, token=TOKEN_A)
            self.assertEqual(status, 200, history)
            self.assertEqual(history["versions"], [])
            self.check_note(base, note_url, note)

    def test_upgrade_refuses_a_note_moved_back_after_another_patient_appended_a_version(self):
        patient_a, encounter_a, patient_b, encounter_b, _, note = self.ownership_fixture()
        change = text("UPDATE ehr.clinical_note_headers SET encounter_id=:encounter WHERE id=:note")
        with self.engine.begin() as conn:
            conn.execute(change, {"encounter": encounter_b, "note": note["note_id"]})
        access = {"actor": "ACTOR-ALPHA", "purpose": "operations"}
        second_body = "Independently fictional draft for patient B."
        with self.services() as registry:
            service = PostgresClinicalEncounters(registry, registry.authorizer)
            service.transition(patient_b, encounter_b, "in_progress", expected_revision=1,
                               request_key="OWNERSHIP-START-B", **access)
            service.write_note(patient_b, encounter_b, "JOIN-DRAFT", body=second_body,
                               expected_version=1, request_key="OWNERSHIP-NOTE-B", **access)
        with self.engine.begin() as conn:
            conn.execute(change, {"encounter": encounter_a, "note": note["note_id"]})
        with self.services() as registry:
            history = PostgresClinicalEncounters(registry, registry.authorizer).note_history(
                patient_a, encounter_a, "JOIN-DRAFT", **access)
            self.assertEqual([v["body"] for v in history], [NOTE["body"], second_body])
        with self.assertRaisesRegex(CommandError, "ownership requires explicit reconciliation"):
            migrate(self.admin, "upgrade", SCHEMA_REVISION)
        self.assertEqual(self.heads(), {LAB_SCOPE})

    def test_upgrade_refuses_an_encounter_moved_back_after_a_foreign_transition(self):
        patient_a, encounter_a, patient_b, _, _, _ = self.ownership_fixture()
        change = text("UPDATE ehr.clinical_encounters SET patient_id=:patient WHERE id=:encounter")
        with self.engine.begin() as conn:
            conn.execute(change, {"patient": patient_b, "encounter": encounter_a})
        with self.services() as registry:
            PostgresClinicalEncounters(registry, registry.authorizer).transition(
                patient_b, encounter_a, "completed", expected_revision=2, actor="ACTOR-ALPHA",
                purpose="operations", request_key="OWNERSHIP-COMPLETE-B")
        with self.engine.begin() as conn:
            conn.execute(change, {"patient": patient_a, "encounter": encounter_a})
        with self.assertRaisesRegex(CommandError, "ownership requires explicit reconciliation"):
            migrate(self.admin, "upgrade", SCHEMA_REVISION)
        self.assertEqual(self.heads(), {LAB_SCOPE})

    def upgrade(self, expected_heads):
        self.assertEqual(self.heads(), expected_heads)
        self.readiness(False)
        tables, _ = self.snapshot()
        names = list(tables) + (EHR_TABLES if expected_heads & {EHR, LAB_SCOPE, EHR_OWNERSHIP, "0023_ehr_lab_ownership_join"} else [])
        before = self.snapshot(names)
        migrate(self.admin, "upgrade", "head")
        migrate(self.admin, "upgrade", "head")
        self.assertEqual(self.heads(), {SCHEMA_REVISION})
        self.readiness(True)
        laboratory.LabManualPopulatedMigrationTests.assert_existing_history_preserved(self, before)

    def check_note(self, base, url, receipt):
        self.assertEqual(request(base, url, token=TOKEN_A, body={"synthetic": True, **NOTE})[:2],
                         (200, receipt))
        status, history, _ = request(base, url, token=TOKEN_A)
        self.assertEqual(status, 200, history)
        version, = history["versions"]
        self.assertEqual((version["sha256"], version["body"]), (receipt["sha256"], NOTE["body"]))
        self.assertEqual(request(base, url, token=TOKEN_B)[0], 404)

    def check_citation(self, base, url, command, receipt):
        self.assertEqual(request(base, url, token=TOKEN_A, body={"synthetic": True, **command})[:2],
                         (200, receipt | {"duplicate": True}))
        status, page, _ = request(base, url, token=TOKEN_A)
        self.assertEqual(status, 200, page)
        link, = page["links"]
        self.assertEqual(link["link_id"], receipt["link_id"])
        self.assertEqual(request(base, url, token=TOKEN_B)[0], 404)

    def check_guard_parent_upgrade(self, parent):
        patient, url, command, receipt = self.seed_citation()
        migrate(self.admin, "upgrade", parent)
        note = self.seed_encounter(patient)
        self.upgrade({parent})
        with running_server(create_app(self.settings)) as base:
            self.check_note(base, *note)
            self.check_citation(base, url, command, receipt)

    def test_populated_citation_scope_parent_keeps_both_histories(self):
        self.check_guard_parent_upgrade(LAB_SCOPE)

    def test_populated_ownership_parent_keeps_both_histories(self):
        self.check_guard_parent_upgrade(EHR_OWNERSHIP)

    def test_published_ownership_join_keeps_citation_and_note(self):
        self.check_guard_parent_upgrade("0023_ehr_lab_ownership_join")

    def test_backup_and_execution_join_preserves_populated_clinical_owners(self):
        self.check_guard_parent_upgrade("0023_composer_clinical_join")

    def test_source_event_and_clinical_join_preserves_populated_clinical_owners(self):
        self.check_guard_parent_upgrade("0025_clinical_source_events")

    def test_populated_ehr_parent_upgrades_and_keeps_note_retry(self):
        patient, _, _ = self.start_at(EHR)
        note = self.seed_encounter(patient)
        self.upgrade({EHR})
        with running_server(create_app(self.settings)) as base:
            self.check_note(base, *note)
        with self.assertRaisesRegex(CommandError, "Populated encounter"):
            migrate(self.admin, "downgrade", f"{EHR}@{COMMON}")
        self.assertEqual(self.heads(), {SCHEMA_REVISION})

    def test_populated_lab_parent_upgrades_and_accepts_same_patient_encounter(self):
        patient, url, command, receipt = self.seed_citation()
        self.upgrade({LAB})
        note = self.seed_encounter(patient)
        with running_server(create_app(self.settings)) as base:
            self.check_note(base, *note)
            self.check_citation(base, url, command, receipt)
            self.creds[0]["actions"].remove("note.read")
            self.write()
            self.assertEqual(request(base, note[0], token=TOKEN_A)[0], 404)
            self.assertEqual(request(base, url, token=TOKEN_A)[0], 200)

    def test_two_populated_heads_join_without_rewriting_either_history(self):
        patient, url, command, receipt = self.seed_citation()
        migrate(self.admin, "upgrade", EHR)
        note = self.seed_encounter(patient)
        self.upgrade({EHR, LAB})
        with running_server(create_app(self.settings)) as base:
            self.check_note(base, *note)
            self.check_citation(base, url, command, receipt)
            self.creds[0]["actions"].remove("evidence_read")
            self.write()
            self.assertEqual(request(base, url, token=TOKEN_A)[0], 404)
            self.assertEqual(request(base, note[0], token=TOKEN_A)[0], 200)

    def test_published_clinical_head_reopens_citation_note_and_observation_task_after_join(self):
        from oi_api.question_followthrough import PostgresQuestionFollowthrough
        from test_laboratory_followthrough import V2

        patient, url, citation_command, citation = self.seed_citation()
        previous = "0023_lab_question_followthrough"
        migrate(self.admin, "upgrade", previous)
        question = url.split("/")[-2]
        task_intent = {
            "request_key": "CLINICAL-JOIN-FOLLOWUP",
            "title": "Review the fictional laboratory source",
            "detail": "", "owner_label": "", "due_date": None,
            "review_trigger": "When the source changes",
            "reason": "Revisit the recorded Observation with its source.",
            **{key: citation_command[key] for key in (
                "source_snapshot_contract", "expected_source_snapshot_sha256", "expected_preflight_sha256")},
        }
        with self.services() as registry:
            task = PostgresQuestionFollowthrough(registry).create(
                patient, "CASE-ALPHA", question, **evidence.OPTIONS, **task_intent)
        note = self.seed_encounter(patient)
        tables, _ = self.snapshot()
        names = [*tables, *EHR_TABLES]
        snapshot = self.snapshot(names)
        self.readiness(False)
        clinical = "0024_clinical_execution_join"
        migrate(self.admin, "upgrade", clinical)
        self.assertEqual(self.heads(), {clinical})
        laboratory.LabManualPopulatedMigrationTests.assert_existing_history_preserved(self, snapshot)
        self.readiness(False)
        with self.engine.connect() as db:
            journal = db.execute(text(
                "SELECT id,patient_id,metadata_json->>'source_id',metadata_json->>'version',occurred_at "
                "FROM identity.identity_domain_events WHERE event_type='source.original.imported' ORDER BY id"
            )).all()
        self.assertGreaterEqual(len(journal), 2)
        migrate(self.admin, "upgrade", "head")
        migrate(self.admin, "upgrade", "head")
        self.assertEqual(self.heads(), {SCHEMA_REVISION})
        laboratory.LabManualPopulatedMigrationTests.assert_existing_history_preserved(self, snapshot)
        with self.engine.connect() as db:
            envelopes = db.execute(text(
                "SELECT event_id,patient_id,source_id,source_version::text,occurred_at "
                "FROM coordination.source_event_outbox ORDER BY event_id"
            )).all()
        self.assertEqual(envelopes, journal)
        with running_server(create_app(self.settings)) as base:
            self.check_citation(base, url, citation_command, citation)
            self.check_note(base, *note)
            path = f"/v1/patients/{patient}/cases/CASE-ALPHA/followthrough"
            code, page, _ = request(base, path, token=TOKEN_A, headers={"Accept": V2})
            self.assertEqual(code, 200, page)
            restored, = [item for item in page["tasks"] if item["task_id"] == task["task_id"]]
            self.assertEqual(restored["question_id"], question)
            self.assertTrue(restored["observation_reference"].startswith("Observation/"))
