"""Cross-branch intake regressions for the synthetic-only H1/current-main composition.

These controls guard the accepted text-intake contract while allowing the
reviewed document owner's PDF/correction path to remain separate. They do not
establish document authenticity, production identity or clinical approval.
"""
import hashlib
import unittest

from open_intelligence.document_intake import (
    classification_provenance, preview_document, preview_saved_document,
    preview_text, safe_filename,
)
from open_intelligence.store import InvalidInput


class H1MainDocumentIntakeMergeTests(unittest.TestCase):
    RAW = b"Fictional pathology note\r\nNo clinical conclusions recorded.\n"

    def test_main_utf8_preview_is_exactly_the_media_aware_text_preview(self):
        direct = preview_text(self.RAW, "fictional-note.txt")
        media = preview_document(self.RAW, "fictional-note.txt")
        saved = preview_saved_document(self.RAW, "fictional-note.txt")
        self.assertEqual(direct, media)
        self.assertEqual(direct, saved)
        self.assertEqual(direct["sha256"], hashlib.sha256(self.RAW).hexdigest())
        self.assertEqual(direct["media_type"], "text/plain; charset=utf-8")
        self.assertEqual(direct["lines"][0]["text"], "Fictional pathology note")
        self.assertEqual(direct["lines"][1]["text"], "No clinical conclusions recorded.")
        self.assertEqual(direct["clinical_review"], "not_performed")

    def test_pdf_extension_never_uses_the_plaintext_transcription_path(self):
        self.assertEqual(safe_filename("fictional.pdf"), "fictional.pdf")
        with self.assertRaises(InvalidInput):
            preview_text(b"%PDF-1.4\nsynthetic bytes", "fictional.pdf")
        with self.assertRaises(InvalidInput):
            preview_text(b"%PDF-1.4\nsynthetic bytes", "fictional.txt")
        with self.assertRaises(InvalidInput):
            preview_saved_document(self.RAW, "fictional.pdf")
        with self.assertRaises(InvalidInput):
            preview_saved_document(self.RAW, "fictional.txt", {"pages": []})

    def test_legacy_text_classification_never_becomes_source_authored(self):
        receipt = {
            "annotation_method": "manual-exact-line-selection",
            "clinical_review": "not_performed",
            "review_sha256": "a" * 64,
        }
        self.assertEqual(classification_provenance(receipt), {
            "classification_origin": "user_selected",
            "annotation_method": "manual-exact-line-selection",
            "clinical_review": "not_performed",
            "transcription_review_sha256": "a" * 64,
        })

    def test_no_filename_traversal_even_when_pdf_is_supported(self):
        for name in ("../fictional.pdf", "folder/fictional.txt", "fictional..pdf",
                     "fictional.pdf/other", ".pdf"):
            with self.subTest(filename=name), self.assertRaises(InvalidInput):
                safe_filename(name)


if __name__ == "__main__":
    unittest.main()
