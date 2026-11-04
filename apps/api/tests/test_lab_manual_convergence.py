"""Real populated upgrades from both published 0016 histories; synthetic only."""
import base64
import hashlib
import unittest

from alembic.util.exc import CommandError
from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from oi_api.contracts import SCHEMA_REVISION
from oi_api.document_contracts import DocumentImport
from oi_api.laboratory_fhir_r4 import prepare_laboratory_bundle
from oi_api.laboratory_fhir_store import PostgresLaboratoryFHIR
from oi_api.migrate import migrate
from oi_api.question_followthrough import PostgresQuestionFollowthrough
from oi_api.question_passages import QuestionPassages
from oi_api.reviewed_documents import ReviewedDocuments, fingerprint
from test_document_image_convergence import graph
import test_evidence_convergence_migrations as evidence
import test_image_report_convergence_migrations as images
from test_laboratory_fhir_r4 import example, encode
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture

LAB = "0016_fhir_laboratory_sources"
MANUAL = "0016_manual_task_dependency"
JOIN = "0017_lab_manual_convergence"
RAW = b"Independently fictional upgrade document.\nMarker pending.\n"


class LabManualMigrationContractTests(unittest.TestCase):
    def test_one_join_preserves_both_published_parents(self):
        script = graph()
        self.assertEqual(script.get_heads(), [JOIN])
        self.assertEqual(SCHEMA_REVISION, JOIN)
        self.assertEqual(set(script.get_revision(JOIN).down_revision), {LAB, MANUAL})
        for revision in (LAB, MANUAL):
            self.assertEqual(script.get_revision(revision).down_revision,
                             "0015_manual_report_context")


class LabManualPopulatedMigrationTests(SourceVersionFixture):
    services = evidence.EvidenceConvergenceMigrationTests.services
    start_at = evidence.EvidenceConvergenceMigrationTests.start_at
    snapshot = evidence.EvidenceConvergenceMigrationTests.snapshot
    seed_metadata_task = evidence.EvidenceConvergenceMigrationTests.seed_metadata_task
    heads = images.ImageReportConvergenceMigrationTests.heads
    readiness = images.ImageReportConvergenceMigrationTests.readiness
    schema_definition = images.ImageReportConvergenceMigrationTests.schema_definition

    def seed_lab(self, patient):
        raw = encode(example()).replace(b"FICTIONAL-PATIENT-A", b"UPGRADE-SUBJECT")
        prepared = prepare_laboratory_bundle(
            raw, expected_subject_reference="Patient/UPGRADE-SUBJECT")
        with self.services() as registry:
            receipt = PostgresLaboratoryFHIR(registry).import_bundle(
                patient, "CASE-ALPHA", prepared, **evidence.OPTIONS,
                request_key="CONVERGENCE-LAB", expected_previous_source_id=None)
        return raw, receipt

    def seed_manual(self, patient, question, prepared):
        # Create the historical records through their existing owners, without
        # bypassing readiness for any HTTP request or stamping a schema version.
        options = {**evidence.OPTIONS, "prepare_response": lambda value: value}
        payload = DocumentImport(
            synthetic=True, filename="fictional-convergence.txt",
            original_base64=base64.b64encode(RAW).decode(),
            confirmed_case_id="CASE-ALPHA", expected_sha256=hashlib.sha256(RAW).hexdigest(),
            metadata=dict(document_id="DOC-CONVERGENCE", kind="pathology",
                          event_date="2026-01-10", issued_at="2026-01-11",
                          manual_transcription_confirmed=True),
            findings=[dict(key="marker", state="pending", quote="Marker pending.", line=2)])
        with self.services() as registry:
            owner = ReviewedDocuments(registry)
            document = owner.import_document(patient, "CASE-ALPHA", payload, **options)
            selected = owner.read_selection(
                patient, "CASE-ALPHA", document["source_id"],
                document["annotation_revision_id"], "marker", **options)
            reference = dict(source_id=document["source_id"],
                annotation_revision_id=document["annotation_revision_id"], selection_key="marker",
                anchor_sha256=selected["anchor_sha256"])
            passages = QuestionPassages(registry)
            passage_options = {**options, "recheck_authority": lambda needs_original: None}
            current = passages.perform(patient, "CASE-ALPHA", question, **passage_options)
            saved = passages.perform(patient, "CASE-ALPHA", question, **passage_options,
                payload=dict(synthetic=True, request_key="CONVERGENCE-PASSAGES",
                    expected_context_sha256=current["context_sha256"], references=[reference]))
            intent = dict(request_key="CONVERGENCE-MANUAL-TASK", title="Inspect the fictional passage",
                detail="", owner_label="", due_date=None, review_trigger="When the passage changes",
                reason="Keep the existing source basis inspectable.",
                source_snapshot_contract="oi.pg-source-world-model/1",
                expected_source_snapshot_sha256=prepared["source_snapshot_sha256"],
                expected_preflight_sha256=prepared["preflight_sha256"],
                manual_dependency=dict(patient_id=patient, case_id="CASE-ALPHA", question_id=question,
                    revision_id=saved["revision_id"], references_sha256=fingerprint([reference])))
            receipt = PostgresQuestionFollowthrough(registry).create(
                patient, "CASE-ALPHA", question, **evidence.OPTIONS, **intent)
        self.creds[0]["actions"].extend(("followthrough_read", "followthrough_create"))
        self.write()
        return intent, receipt

    def upgrade_preserving(self, before):
        migrate(self.admin, "upgrade", "head")
        self.assertEqual(self.heads(), {JOIN})
        self.assertEqual(self.snapshot(before[0]), before)
        self.readiness(True)

    def replay(self, patient, question, *, laboratory=None, manual=None):
        prefix = f"/v1/patients/{patient}/cases/CASE-ALPHA"
        with running_server(create_app(self.settings)) as base:
            if laboratory:
                raw, saved = laboratory
                status, retry, _ = request(base, prefix + "/laboratory/fhir-r4/sources",
                    token=TOKEN_A, body=dict(synthetic=True, request_key="CONVERGENCE-LAB",
                        bundle_json=raw.decode()))
                self.assertEqual((status, retry), (200, saved | {"duplicate": True}))
                status, original, _ = request(base, prefix + "/sources/" + saved["source_id"], token=TOKEN_A)
                self.assertEqual(status, 200, original)
                self.assertEqual(original["original_text"], raw.decode())
                self.assertEqual(original["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(request(base, prefix + "/sources/" + saved["source_id"], token=TOKEN_B)[0], 404)
            if manual:
                intent, saved = manual
                endpoint = prefix + f"/questions/{question}/followthrough"
                status, retry, _ = request(base, endpoint, token=TOKEN_A,
                                          body={"synthetic": True, **intent})
                self.assertEqual((status, retry), (200, saved | {"duplicate": True}))
                status, listing, _ = request(base, prefix + "/followthrough", token=TOKEN_A)
                self.assertEqual(status, 200, listing)
                task = next(t for t in listing["tasks"] if t["task_id"] == saved["task_id"])
                self.assertEqual(task["manual_dependency_revision_id"], intent["manual_dependency"]["revision_id"])
                self.assertEqual(task["manual_context_state"], "current_unreviewed")
                self.assertNotIn("Marker pending.", str(task))
                self.assertEqual(request(base, prefix + "/followthrough", token=TOKEN_B)[0], 404)

    def test_populated_laboratory_head_preserves_originals_and_source_only_tasks(self):
        patient, question, prepared = self.start_at(LAB)
        self.seed_metadata_task(patient, question, prepared)
        laboratory = self.seed_lab(patient)
        before = self.snapshot()
        self.assertNotIn("coordination.question_followthrough_manual_dependencies", before[0])
        with self.assertRaisesRegex(CommandError, "FHIR laboratory history"):
            migrate(self.admin, "downgrade", "0015_manual_report_context")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.heads(), {LAB})
        self.upgrade_preserving(before)
        self.assertEqual(self.snapshot()[0]["coordination.question_followthrough_manual_dependencies"], [])
        self.replay(patient, question, laboratory=laboratory)

    def test_populated_manual_head_preserves_exact_task_dependency_and_retry(self):
        patient, question, prepared = self.start_at(MANUAL)
        manual = self.seed_manual(patient, question, prepared)
        before = self.snapshot()
        self.assertNotIn("clinical_source.fhir_laboratory_sources", before[0])
        with self.assertRaisesRegex(CommandError, "Stored manual task dependencies"):
            migrate(self.admin, "downgrade", "0015_manual_report_context")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.heads(), {MANUAL})
        self.upgrade_preserving(before)
        self.assertEqual(self.snapshot()[0]["clinical_source.fhir_laboratory_sources"], [])
        self.replay(patient, question, manual=manual)

    def test_populated_two_head_join_has_no_ddl_and_keeps_downgrade_guards(self):
        patient, question, prepared = self.start_at(MANUAL)
        manual = self.seed_manual(patient, question, prepared)
        migrate(self.admin, "upgrade", LAB)
        laboratory = self.seed_lab(patient)
        self.assertEqual(self.heads(), {MANUAL, LAB})
        self.readiness(False)
        before, schema = self.snapshot(), self.schema_definition()
        self.upgrade_preserving(before)
        self.assertEqual(self.schema_definition(), schema)
        # Removing only the join is reversible and cannot erase either owner.
        migrate(self.admin, "downgrade", LAB)
        self.assertEqual(self.heads(), {MANUAL, LAB})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.schema_definition(), schema)
        self.readiness(False)
        for revision in (MANUAL, LAB):
            with self.assertRaises(CommandError):
                migrate(self.admin, "downgrade", revision + "-1")
            self.assertEqual(self.heads(), {MANUAL, LAB})
            self.assertEqual(self.snapshot(), before)
        self.upgrade_preserving(before)
        self.replay(patient, question, laboratory=laboratory, manual=manual)
