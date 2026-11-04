"""Reviewed-document ownership must survive structured-looking original bytes.

All inputs are independently fictional. One adverse legacy link is inserted
through the published schema to prove that reads also enforce source ownership.
The test does not alter migrations, triggers, grants or application readiness.
"""
import base64
import hashlib

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
import test_source_document_audit_authority as audit_authority
from test_image_custody import REPORT, image_bytes, image_request
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


class ReviewedDocumentImageBoundaryTests(SourceVersionFixture):
    durable_rows = audit_authority.SourceDocumentAuditAuthorityTests.durable_rows
    get_bytes = audit_authority.SourceDocumentAuditAuthorityTests.get_bytes

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(
            ("image_import", "image_read", "image_original_read")
        )
        self.write()

    def reviewed_image(self, base, patient):
        prefix = self.url(patient).removesuffix("/sources") + "/documents"
        raw = REPORT.encode()
        status, saved, _ = request(base, prefix, token=TOKEN_A, body={
            "synthetic": True,
            "filename": "fictional-imaging.txt",
            "original_base64": base64.b64encode(raw).decode(),
            "expected_sha256": hashlib.sha256(raw).hexdigest(),
            "confirmed_case_id": "CASE-ALPHA",
            "metadata": {
                "document_id": "DOC-IMAGE",
                "kind": "imaging",
                "event_date": "2026-02-01",
                "issued_at": "2026-02-02",
                "manual_transcription_confirmed": True,
            },
            "findings": [],
        })
        self.assertEqual(status, 201, saved)
        return saved["source_id"], prefix + "/" + saved["source_id"]

    def assert_withheld(self, base, path, *, raw=None):
        before = self.durable_rows()
        status, body, headers = image_request(base, path, raw=raw)
        self.assertEqual(
            (status, body, self.durable_rows() == before),
            (404, {"detail": "Image unavailable"}, True),
        )
        self.assertEqual(headers["Cache-Control"], "no-store")
        for header in ("X-OI-Access-Receipt", "X-Access-Receipt-ID",
                       "Content-Disposition", "X-Content-SHA256"):
            self.assertNotIn(header, headers)

    def assert_document_owner_preserved(self, base, patient, source, path):
        status, document, _ = request(base, path, token=TOKEN_A)
        self.assertEqual(status, 200, document)
        self.assertEqual(document["source_id"], source)
        self.assertEqual(document["preview"]["text"], REPORT)
        self.assertEqual(document["revisions"][0]["classification_origin"],
                         "user_selected")
        self.assertEqual(document["revisions"][0]["clinical_review"],
                         "not_performed")
        status, raw, headers = self.get_bytes(base, path + "/original")
        self.assertEqual((status, raw), (200, REPORT.encode()))
        self.assertEqual(headers["X-Content-SHA256"],
                         hashlib.sha256(raw).hexdigest())
        self.assertEqual(
            request(base, self.url(patient) + "/" + source, token=TOKEN_A)[0],
            404,
        )
        status, index, _ = request(base, self.url(patient), token=TOKEN_A)
        self.assertEqual(status, 200, index)
        self.assertNotIn(source, {item["source_id"] for item in index["sources"]})
        self.assertNotIn(
            source,
            {item["source_id"] for item in index["source_reported_assertions"]},
        )

    def test_structured_looking_document_cannot_start_image_custody(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source, document = self.reviewed_image(base, patient)
            path = self.url(patient) + "/" + source + "/images"
            for operation, raw in (("index", None), ("new_import", image_bytes())):
                with self.subTest(operation=operation):
                    self.assert_withheld(base, path, raw=raw)
            self.assert_document_owner_preserved(
                base, patient, source, document
            )

    def test_existing_cross_owner_link_cannot_authorize_reads_or_retries(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, source, _ = self.ingest(
                base, patient, REPORT.replace("DOC-IMAGE", "DOC-STRUCTURED")
            )
            self.assertEqual(status, 201, source)
            structured = self.url(patient) + "/" + source["source_id"] + "/images"
            original = image_bytes()
            status, image, _ = image_request(base, structured, raw=original)
            self.assertEqual(status, 201, image)
            image_id = image["image_id"]
            reviewed, document = self.reviewed_image(base, patient)
            # The historical image schema predates reviewed-document ownership.
            # Preserve an adverse existing link; runtime must not disclose it.
            with self.engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO clinical_source.source_image_links(source_id,image_id) "
                    "VALUES (:source,:image)"
                ), {"source": reviewed, "image": image_id})
            path = self.url(patient) + "/" + reviewed + "/images"
            for operation, endpoint, raw in (
                ("index", path, None),
                ("original", path + "/" + image_id, None),
                ("duplicate", path, original),
            ):
                with self.subTest(operation=operation):
                    self.assert_withheld(base, endpoint, raw=raw)
            self.assertEqual(
                image_request(base, structured + "/" + image_id)[:2],
                (200, original),
            )
            status, duplicate, _ = image_request(base, structured, raw=original)
            self.assertEqual((status, duplicate["result"], duplicate["image_id"]),
                             (200, "duplicate", image_id))
            self.assert_document_owner_preserved(
                base, patient, reviewed, document
            )
