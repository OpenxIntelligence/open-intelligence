"""Upgrade either published 0019 history with independently fictional records."""
import unittest

from alembic.util.exc import CommandError

from http_support import running_server
from oi_api.app import create_app
from oi_api.contracts import SCHEMA_REVISION
from oi_api.evidence_catalog import fictional_records, seed_fictional_records
from oi_api.migrate import migrate
from oi_api.question_evidence import PostgresLaboratoryQuestionEvidence
from open_intelligence.postgres_encounters import PostgresClinicalEncounters
import test_evidence_convergence_migrations as evidence
import test_image_report_convergence_migrations as migrations
import test_lab_manual_convergence as laboratory
import test_laboratory_question_migration as questions
from test_document_image_convergence import graph
from test_durable_laboratory_questions import LAB_HISTORY
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture

EHR = "0019_ehr_encounters"
LAB = "0019_laboratory_citations"
COMMON = "0018_laboratory_questions"
EHR_TABLES = ["ehr.clinical_" + name for name in
              ("encounters", "note_headers", "note_versions", "encounter_commands")]
NOTE = {"body": "Independently fictional consultation draft.", "request_key": "JOIN-NOTE",
        "expected_version": 0}


class EHRLaboratoryGraphTests(unittest.TestCase):
    def test_single_head_depends_on_both_published_owners(self):
        script = graph()
        self.assertEqual(script.get_heads(), [SCHEMA_REVISION])
        self.assertEqual(set(script.get_revision(SCHEMA_REVISION).down_revision), {EHR, LAB})
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

    def upgrade(self, expected_heads):
        self.assertEqual(self.heads(), expected_heads)
        self.readiness(False)
        tables, _ = self.snapshot()
        names = list(tables) + (EHR_TABLES if EHR in expected_heads else [])
        before = self.snapshot(names)
        migrate(self.admin, "upgrade", "head")
        migrate(self.admin, "upgrade", "head")
        self.assertEqual(self.heads(), {SCHEMA_REVISION})
        self.readiness(True)
        self.assertEqual(self.snapshot(names), before)

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

    def test_populated_ehr_parent_upgrades_and_keeps_note_retry(self):
        patient, _, _ = self.start_at(EHR)
        note = self.seed_encounter(patient)
        self.upgrade({EHR})
        with running_server(create_app(self.settings)) as base:
            self.check_note(base, *note)
        with self.assertRaisesRegex(CommandError, "Populated encounter"):
            migrate(self.admin, "downgrade", COMMON)
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
