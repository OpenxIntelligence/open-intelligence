"""H1 wire boundary for independently fictional reviewed documents."""
import base64
import unittest
from pydantic import ValidationError
from oi_api.document_contracts import DocumentUpload, DocumentImport, AnnotationCorrection

class DocumentContractTests(unittest.TestCase):
    def test_upload_preserves_bom_crlf_unicode_bytes(self):
        raw="\ufeffFictional café\r\n".encode()
        p=DocumentUpload(synthetic=True,filename="fictional.txt",original_base64=base64.b64encode(raw).decode())
        self.assertEqual(p.original_bytes(),raw)

    def test_invalid_or_oversized_binary_envelope_is_rejected(self):
        for body in ("", "!!!!", "YQ==\n",base64.b64encode(b"x"*65537).decode()):
            with self.subTest(body_length=len(body)), self.assertRaises((ValidationError,ValueError)):
                DocumentUpload(synthetic=True,filename="fictional.pdf",original_base64=body).original_bytes()

    def test_synthetic_and_filename_are_explicit(self):
        for flag in (False,1,"true"):
            with self.assertRaises(ValidationError):
                DocumentUpload(synthetic=flag,filename="fictional.txt",original_base64="YQ==")
        for name in ("../file.txt","file.pdf\r\nInjected: yes","report.docx"):
            with self.assertRaises(ValidationError):
                DocumentUpload(synthetic=True,filename=name,original_base64="YQ==")

    def test_correction_requires_exact_revision_reason_and_bounded_key(self):
        good=dict(synthetic=True,request_key="CORRECT-ONE",expected_revision_id="ANN-"+"A"*32,
                  expected_sha256="a"*64,expected_extraction_sha256=None,
                  confirmed_case_id="CASE-ALPHA",reason="Correct selected passage",findings=[])
        self.assertEqual(AnnotationCorrection(**good).request_key,"CORRECT-ONE")
        for patch in ({"expected_revision_id":"old"},{"request_key":"x"},{"reason":" "},{"findings":[{}]}):
            with self.assertRaises(ValidationError): AnnotationCorrection(**(good|patch))
