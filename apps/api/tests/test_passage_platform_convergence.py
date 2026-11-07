"""Populated upgrades from both published branches preserve canonical citations."""
import base64
import hashlib
import json

from oi_api.contracts import SCHEMA_REVISION
from oi_api.document_contracts import DocumentImport
from oi_api.evidence_catalog import fictional_records, seed_fictional_records
from oi_api.laboratory_questions import PostgresLaboratoryQuestions
from oi_api.composer_preflight import PostgresSourceComposerPreflight
from oi_api.source_world_model import project_source_world_model
from oi_api.sources import PostgresSourceVersions
from oi_api.migrate import migrate
from oi_api.reviewed_documents import ReviewedDocuments, fingerprint
from oi_api.reviewed_questions import PassageQuestionWrite, passage_questions
from oi_api.question_evidence import PostgresQuestionEvidence, PostgresLaboratoryQuestionEvidence
from test_laboratory_fhir_r4 import OBS
from test_source_versions import SourceVersionFixture
import test_lab_manual_convergence as joined
import test_evidence_convergence_migrations as evidence

OPTIONS = evidence.OPTIONS

RAW = b"Independent fictional convergence record.\nMarker pending.\n"


class PassagePlatformConvergenceTests(evidence.PublishedEvidenceFixture, SourceVersionFixture):
    snapshot = evidence.EvidenceConvergenceMigrationTests.snapshot
    assert_existing_history_preserved = joined.LabManualPopulatedMigrationTests.assert_existing_history_preserved
    seed_lab = joined.LabManualPopulatedMigrationTests.seed_lab

    def seed_citation(self, patient, manual):
        if manual:
            payload = DocumentImport(synthetic=True, filename="fictional.txt",
                original_base64=base64.b64encode(RAW).decode(),
                confirmed_case_id="CASE-ALPHA", expected_sha256=hashlib.sha256(RAW).hexdigest(),
                metadata=dict(document_id="DOC-PASSAGE", kind="pathology", event_date="2026-01-10",
                              issued_at="2026-01-11", manual_transcription_confirmed=True),
                findings=[dict(key="marker", state="pending", quote="Marker pending.", line=2)])
            with self.services() as registry:
                documents = ReviewedDocuments(registry)
                saved = documents.import_document(patient, "CASE-ALPHA", payload, **{**OPTIONS, "prepare_response":lambda value:value})
                source = saved["source_id"]
                selected = documents.read_selection(patient, "CASE-ALPHA", source,
                    saved["annotation_revision_id"], "marker", **{**OPTIONS, "prepare_response":lambda value:value})
                command = PassageQuestionWrite(synthetic=True, request_key="PASSAGE-QUESTION",
                    question="Which fictional original explains this marker?",
                    revision_id=saved["annotation_revision_id"], selection_key="marker",
                    anchor_sha256=selected["anchor_sha256"])
                result = passage_questions(documents, patient, "CASE-ALPHA", source, command,
                                           **{k:v for k,v in OPTIONS.items() if k!="prepare_response"})
                qid = json.loads(result.body)["question_id"]
            extra = {"reviewed_source":source}
            snapshot = selected["anchor_sha256"]
            preflight = fingerprint([snapshot, command.question])
            contract = "oi.reviewed-document-selection/1"
            owner_type = PostgresQuestionEvidence
        else:
            _, saved = self.seed_lab(patient)
            source = saved["source_id"]
            with self.services() as registry:
                index = PostgresSourceVersions(registry).list(patient, "CASE-ALPHA", **OPTIONS)
                snapshot = project_source_world_model(index)["snapshot_fingerprint"]
                args = dict(source_id=source, observation_reference=OBS,
                    question="Which fictional assay explains this observation?",
                    expected_source_snapshot_sha256=snapshot)
                checked = PostgresSourceComposerPreflight(registry).preview_laboratory(
                    patient, "CASE-ALPHA", **args, **OPTIONS)
                preflight = checked["preflight_sha256"]
                qid = PostgresLaboratoryQuestions(registry).save(patient, "CASE-ALPHA",
                    **args, expected_preflight_sha256=preflight, request_key="LAB-QUESTION", **OPTIONS)["question_id"]
            extra = {}
            contract = "oi.pg-source-world-model/1"
            owner_type = PostgresLaboratoryQuestionEvidence
        with self.services() as registry:
            owner = owner_type(registry)
            hit, = owner.search(patient, "CASE-ALPHA", qid, query="continuity", **extra, **OPTIONS)["records"]
            command = dict(citation=hit["citation"], expected_metadata_sha256=hit["metadata_sha256"],
                source_snapshot_contract=contract, expected_source_snapshot_sha256=snapshot,
                expected_preflight_sha256=preflight, request_key="CITATION-"+("MANUAL" if manual else "LAB"))
            receipt = owner.create_link(patient, "CASE-ALPHA", qid, **extra, **command, **OPTIONS)
        return qid, owner_type, extra, command, receipt

    def upgrade_parent(self, parent, manual):
        patient, _, _ = self.start_at(parent)
        with self.services() as registry:
            seed_fictional_records(registry, fictional_records(), recorded_by="FIXTURE-AUTHOR")
        qid, owner_type, extra, command, receipt = self.seed_citation(patient, manual)
        before = self.snapshot()
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        self.assert_existing_history_preserved(before)
        self.seed_citation(patient, not manual)
        with self.services() as registry:
            owner = owner_type(registry)
            history = owner.links(patient, "CASE-ALPHA", qid, **extra, **OPTIONS)
            self.assertEqual(history["links"][0]["link_id"], receipt["link_id"])
            self.assertEqual(owner.create_link(patient, "CASE-ALPHA", qid, **extra, **command, **OPTIONS),
                             {**receipt, "duplicate":True})

    def test_populated_passage_parent_preserves_citations_and_accepts_laboratory_citations(self):
        self.upgrade_parent("0020_passage_citations", True)

    def test_populated_patient_platform_preserves_laboratory_citations_and_accepts_passages(self):
        self.upgrade_parent("0029_patient_access", False)
