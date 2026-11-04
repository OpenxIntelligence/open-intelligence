"""Populated document/image convergence over the published canonical owners.

All input bytes are independently fictional. Route/graph guards deliberately
precede imports from the image donor so the document-only baseline fails on
missing integration behavior, not on an unavailable future test module.
"""
import base64
import hashlib
from pathlib import Path
import unittest
from urllib.request import Request, ProxyHandler, build_opener

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.contracts import SCHEMA_REVISION
from oi_api.database import Database
from oi_api.document_contracts import DocumentImport, AnnotationCorrection
from oi_api.migrate import migrate
from oi_api.reviewed_documents import ReviewedDocuments
import test_evidence_convergence_migrations as evidence_upgrades
from test_evidence_convergence_migrations import OPTIONS
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture

DOCUMENT_REVISION = "0012_reviewed_documents"
IMAGE_REVISION = "0012_image_report_convergence"
JOINED_REVISION = "0013_document_image_convergence"
DOCUMENT_PATH = "/v1/patients/{patient_id}/cases/{case_id}/documents"
IMAGE_PATH = "/v1/patients/{patient_id}/cases/{case_id}/sources/{source_id}/images"
RAW = b"Independently fictional migration document.\nMarker pending.\nSecond passage.\n"


def graph():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    return ScriptDirectory.from_config(config)


class DocumentImageConvergenceContractTests(unittest.TestCase):
    def test_one_api_exposes_both_original_owners_without_replacing_question_routes(self):
        paths = create_app(Settings.from_env({})).openapi()["paths"]
        for path, method in (
            (DOCUMENT_PATH, "post"), (DOCUMENT_PATH, "get"),
            (DOCUMENT_PATH + "/{source_id}/original", "get"),
            (IMAGE_PATH, "post"), (IMAGE_PATH, "get"),
            (IMAGE_PATH + "/{image_id}", "get"),
            ("/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/evidence-reports/{report_id}", "get"),
        ):
            with self.subTest(path=path, method=method):
                self.assertIn(path, paths, "The connected API is missing a published original owner")
                self.assertEqual(paths[path][method]["security"], [{"SyntheticFixture": []}])

    def test_single_join_preserves_both_published_document_and_image_histories(self):
        script = graph()
        self.assertEqual(script.get_heads(), [SCHEMA_REVISION],
                         "The complete history must have exactly one current head")
        self.assertEqual(script.get_revision("0014_question_passages").down_revision,
                         JOINED_REVISION)
        self.assertEqual(script.get_revision(SCHEMA_REVISION).down_revision,
                         "0014_question_passages")
        self.assertEqual(set(script.get_revision(JOINED_REVISION).down_revision),
                         {DOCUMENT_REVISION, IMAGE_REVISION})
        self.assertEqual(script.get_revision(DOCUMENT_REVISION).down_revision, "0011_evidence_convergence")
        self.assertEqual(set(script.get_revision(IMAGE_REVISION).down_revision),
                         {"0011_evidence_convergence", "0011_image_evidence_merge"})


class DocumentImageConvergenceMigrationTests(SourceVersionFixture):
    services = evidence_upgrades.EvidenceConvergenceMigrationTests.services
    snapshot = evidence_upgrades.EvidenceConvergenceMigrationTests.snapshot
    seed_metadata_task = evidence_upgrades.EvidenceConvergenceMigrationTests.seed_metadata_task

    def require_graph(self):
        self.assertEqual(graph().get_heads(), [SCHEMA_REVISION],
                         "The document/image join and manual-context successors must form one head")

    @staticmethod
    def image_helpers():
        import test_image_report_convergence_migrations as image_upgrades
        return image_upgrades.ImageReportConvergenceMigrationTests

    def heads(self):
        with self.engine.connect() as connection:
            return set(connection.execute(text("SELECT version_num FROM public.alembic_version")).scalars())

    def readiness(self, ready):
        probe = Database(self.settings)
        try:
            self.assertEqual(probe.check().status, "ready" if ready else "schema_mismatch")
            if not ready:
                with self.assertRaisesRegex(RuntimeError, "Unsupported migration state"):
                    with probe.registry_connection():
                        self.fail("Current application accepted an unconverged database")
        finally:
            probe.close()

    def start_at(self, revision):
        self.require_graph()
        return self.image_helpers().start_at(self, revision)

    def seed_report(self, flow):
        return self.image_helpers().seed_report(self, flow)

    def seed_image(self, flow):
        return self.image_helpers().seed_image(self, flow)

    def schema_definition(self):
        return self.image_helpers().schema_definition(self)

    def seed_document(self, flow):
        payload = DocumentImport(
            synthetic=True, filename="fictional-migration.txt",
            original_base64=base64.b64encode(RAW).decode(),
            confirmed_case_id="CASE-ALPHA", expected_sha256=hashlib.sha256(RAW).hexdigest(),
            metadata=dict(document_id="DOC-MIGRATION-MANUAL", kind="pathology",
                          event_date="2026-01-10", issued_at="2026-01-11",
                          manual_transcription_confirmed=True),
            findings=[dict(key="marker", state="pending", quote="Marker pending.", line=2)],
        )
        identity = lambda result: result
        options = {**OPTIONS, "prepare_response": identity}
        with self.services() as registry:
            owner = ReviewedDocuments(registry)
            saved = owner.import_document(flow["patient"], "CASE-ALPHA", payload, **options)
            correction = AnnotationCorrection(
                synthetic=True, request_key="MIGRATION-CORRECTION",
                expected_revision_id=saved["annotation_revision_id"],
                confirmed_case_id="CASE-ALPHA", expected_sha256=payload.expected_sha256,
                reason="Correct the independently authored passage selection",
                findings=[dict(key="passage", state="reported", quote="Second passage.", line=3)],
            )
            corrected = owner.correct(flow["patient"], "CASE-ALPHA", saved["source_id"],
                                      correction, **options)
            doc = owner.read(flow["patient"], "CASE-ALPHA", saved["source_id"],
                             **{**OPTIONS, "prepare_response": lambda result, raw: result})
        flow.update(document=doc, document_intent=payload.model_dump(), document_receipt=saved,
                    correction_intent=correction.model_dump(), correction_receipt=corrected)

    def upgrade_preserving(self, before):
        migrate(self.admin, "upgrade", "head")
        after = self.snapshot(before[0])
        self.assertEqual(after[0], before[0])
        for name, state in before[1].items():
            self.assertEqual(after[1][name], state, name)
        self.assertEqual(self.heads(), {SCHEMA_REVISION})
        self.assertEqual(self.snapshot()[0]["investigation.question_passage_revisions"], [],
                         "Upgrading historical cases must not manufacture manual selections")
        self.readiness(True)

    def reopen(self, flow):
        self.image_helpers().reopen(self, flow)
        case = f"/v1/patients/{flow['patient']}/cases/CASE-ALPHA"
        documents = case + "/documents"
        path = documents + "/" + flow["document"]["source_id"]
        before = self.snapshot()
        with running_server(create_app(self.settings)) as base:
            status, doc, _ = request(base, path, token=TOKEN_A)
            self.assertEqual(status, 200, doc)
            self.assertEqual(doc["revisions"], flow["document"]["revisions"])
            self.assertEqual(doc["preview"]["text"], RAW.decode())
            self.assertEqual(doc["revisions"][0]["classification_origin"], "user_selected")
            self.assertEqual(doc["revisions"][1]["clinical_review"], "not_performed")
            for endpoint, intent, saved in (
                (documents, flow["document_intent"], flow["document_receipt"]),
                (path + "/annotations", flow["correction_intent"], flow["correction_receipt"]),
            ):
                code, receipt, _ = request(base, endpoint, token=TOKEN_A, body=intent)
                self.assertEqual((code, receipt), (200, {**saved, "duplicate": True}))
            req = Request(base + path + "/original", headers={"Authorization": "Bearer " + TOKEN_A})
            with build_opener(ProxyHandler({})).open(req) as response:
                self.assertEqual(response.read(), RAW)
                self.assertEqual(response.headers["X-Content-SHA256"], hashlib.sha256(RAW).hexdigest())
                self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(request(base, path, token=TOKEN_B)[0], 404)
            # Manual classifications cannot appear as structured source facts or
            # make the structured original endpoint disclose a document body.
            code, index, _ = request(base, case + "/sources", token=TOKEN_A)
            self.assertEqual(code, 200, index)
            self.assertNotIn(doc["source_id"], {item["source_id"] for item in index["sources"]})
            self.assertNotIn(doc["source_id"],
                             {item["source_id"] for item in index["source_reported_assertions"]})
            self.assertEqual(request(base, case + "/sources/" + doc["source_id"], token=TOKEN_A)[0], 404)
        after = self.snapshot(before[0])
        # Successful reads append access receipts. All other owner rows, including
        # document revisions, image custody, citations, tasks and reports, persist.
        for name, rows in before[0].items():
            if name != "identity.identity_domain_events":
                self.assertEqual(after[0][name], rows, name)

    def test_populated_document_head_adds_images_without_rewriting_selected_passages_or_reports(self):
        flow = self.start_at(DOCUMENT_REVISION)
        self.seed_report(flow)
        self.seed_document(flow)
        before = self.snapshot()
        self.assertNotIn("clinical_source.dicom_objects", before[0])
        self.upgrade_preserving(before)
        self.seed_image(flow)
        self.reopen(flow)

    def test_populated_image_head_adds_documents_without_rewriting_originals_citations_or_tasks(self):
        flow = self.start_at(IMAGE_REVISION)
        self.seed_report(flow)
        self.seed_image(flow)
        before = self.snapshot()
        self.assertNotIn("clinical_source.document_intakes", before[0])
        self.upgrade_preserving(before)
        self.seed_document(flow)
        self.reopen(flow)

    def test_two_populated_heads_join_without_ddl_and_reject_serving_until_converged(self):
        flow = self.start_at(DOCUMENT_REVISION)
        self.seed_report(flow)
        self.seed_document(flow)
        migrate(self.admin, "upgrade", IMAGE_REVISION)
        self.seed_image(flow)
        self.assertEqual(self.heads(), {DOCUMENT_REVISION, IMAGE_REVISION})
        self.readiness(False)
        before, definitions = self.snapshot(), self.schema_definition()
        # The historical 0013 join is strictly DDL-free and reversible.
        # New 0014/0015 manual-context schema must not be mistaken for that join.
        migrate(self.admin, "upgrade", JOINED_REVISION)
        self.assertEqual(self.heads(), {JOINED_REVISION})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.schema_definition(), definitions)
        self.readiness(False)
        migrate(self.admin, "downgrade", DOCUMENT_REVISION)
        self.assertEqual(self.heads(), {DOCUMENT_REVISION, IMAGE_REVISION})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.schema_definition(), definitions)
        self.readiness(False)
        self.upgrade_preserving(before)
        self.reopen(flow)
