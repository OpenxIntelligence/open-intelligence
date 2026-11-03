"""Bounded extraction of independently authored PDF fixtures, never patients."""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import venv

from open_intelligence.store import InvalidInput
from pdf_fixtures import encrypted_pdf, streams_pdf, text_pdf


class PdfIntakeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("open_intelligence.pdf_intake"),
                             "The bounded PDF extractor has not been implemented")
        self.module = importlib.import_module("open_intelligence.pdf_intake")
        self.extract = self.module.extract_pdf

    def test_two_page_rendition_preserves_page_text_and_exact_global_anchors(self):
        raw = text_pdf([["Independent fictional report", "Marker Q remains pending."],
                        ["Marker P was not assessed."]])
        result = self.extract(raw)
        self.assertEqual(result["text"], "Independent fictional report\nMarker Q remains pending.\nMarker P was not assessed.")
        self.assertEqual(result["lines"], [
            {"line": 1, "text": "Independent fictional report", "page": 1, "page_line": 1},
            {"line": 2, "text": "Marker Q remains pending.", "page": 1, "page_line": 2},
            {"line": 3, "text": "Marker P was not assessed.", "page": 2, "page_line": 1},
        ])
        self.assertEqual(result["page_count"], 2)
        self.assertEqual([p["text"] for p in result["pages"]], [
            "Independent fictional report\nMarker Q remains pending.\n",
            "Marker P was not assessed.\n",
        ])
        for page in result["pages"]:
            self.assertEqual(page["sha256"], hashlib.sha256(page["text"].encode()).hexdigest())
        self.assertEqual(result["extractor"]["name"], "pypdf")
        self.assertEqual(result["extractor"]["version"], "6.21.4")
        self.assertEqual(result["extractor"]["wheel_sha256"],
                         "33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c")
        payload = {k: v for k, v in result.items() if k != "extraction_sha256"}
        expected = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(result["extraction_sha256"], expected)
        self.assertEqual(self.extract(raw), result)
        self.assertNotIn("assertions", result)

    def test_blank_middle_page_is_explicit_without_inventing_lines(self):
        result = self.extract(text_pdf([["First original page."], [], ["Third original page."]]))
        self.assertEqual(result["page_count"], 3)
        self.assertEqual(result["pages"][1], {
            "page": 2, "text": "", "sha256": hashlib.sha256(b"").hexdigest(),
        })
        self.assertEqual(result["lines"][1], {
            "line": 2, "text": "Third original page.", "page": 3, "page_line": 1,
        })

    def test_literal_whitespace_punctuation_and_markup_are_not_rewritten(self):
        source = "  Marker P: not assessed (pending); <script>fictional</script>  "
        result = self.extract(text_pdf([[source]]))
        self.assertEqual(result["lines"][0]["text"], source)

    def test_empty_non_pdf_and_oversized_inputs_reject(self):
        for raw in (b"", b"fictional text", b"%PDF-1.4\n" + b"x" * 65536, "pdf", None):
            with self.subTest(value_type=type(raw).__name__):
                with self.assertRaises(InvalidInput):
                    self.extract(raw)

    def test_encrypted_inputs_reject_even_with_empty_open_password(self):
        for empty in (False, True):
            with self.subTest(empty_password=empty):
                with self.assertRaisesRegex(InvalidInput, "encrypted"):
                    self.extract(encrypted_pdf(empty_password=empty))

    def test_image_only_page_rejects_instead_of_returning_partial_document(self):
        raw = streams_pdf([b"BT /F1 10 Tf 36 756 Td (Fictional text page) Tj ET",
                           b"q 100 0 0 100 36 600 cm /Im0 Do Q"], image_pages=(1,))
        with self.assertRaisesRegex(InvalidInput, "extractable text"):
            self.extract(raw)

    def test_all_blank_and_graphics_only_documents_reject(self):
        for raw in (text_pdf([[], []]), streams_pdf([b"0 0 10 10 re f"])):
            with self.subTest(length=len(raw)):
                with self.assertRaisesRegex(InvalidInput, "extractable text"):
                    self.extract(raw)

    def test_malformed_or_unreadable_page_rejects_entire_document(self):
        normal = text_pdf([["Fictional report"]])
        for raw in (normal[:-12], normal.replace(b"startxref\n", b"startxref\n999999"),
                    streams_pdf([b"content"], stream_filter=b"/UnsupportedFixtureFilter")):
            with self.subTest(length=len(raw)):
                with self.assertRaises(InvalidInput):
                    self.extract(raw)

    def test_page_and_line_limits_reject_without_truncation(self):
        for raw in (text_pdf([["Fictional page"]] * 21),
                    text_pdf([["Fictional line"] * 513], compressed=True)):
            with self.subTest(length=len(raw)):
                self.assertLess(len(raw), 65536)
                with self.assertRaises(InvalidInput):
                    self.extract(raw)

    def test_compressed_text_expansion_is_rejected_and_next_job_succeeds(self):
        raw = text_pdf([["A" * 70000]], compressed=True)
        self.assertLess(len(raw), 65536)
        with self.assertRaises(InvalidInput):
            self.extract(raw)
        self.assertEqual(self.extract(text_pdf([["Next fictional report."]]))["text"],
                         "Next fictional report.")

    def test_worker_timeout_is_bounded_and_does_not_break_next_job(self):
        command = [sys.executable, "-I", "-c", "import time; time.sleep(60)"]
        before = time.monotonic()
        with patch.object(self.module, "_worker_command", return_value=command), \
                patch.object(self.module, "WALL_SECONDS", 0.15):
            with self.assertRaisesRegex(InvalidInput, "time"):
                self.extract(text_pdf([["Fictional timeout fixture."]]))
        self.assertLess(time.monotonic() - before, 2)
        self.assertEqual(self.extract(text_pdf([["Recovered worker."]]))["text"], "Recovered worker.")

    def test_worker_output_is_bounded_and_untrusted_schema_rejects(self):
        for script in ("import os; os.write(1, b'x' * 600000)",
                       "print('{\"text\": \"invented clinical result\"}')"):
            with self.subTest(script=script[:20]):
                command = [sys.executable, "-I", "-c", script]
                with patch.object(self.module, "_worker_command", return_value=command):
                    with self.assertRaises(InvalidInput):
                        self.extract(text_pdf([["Fictional report."]]))

    def test_worker_protocol_rejects_boolean_numeric_alias_and_excessive_nesting(self):
        raw = text_pdf([["Fictional protocol fixture."]])
        changed = self.extract(raw)
        changed["page_count"] = True  # Python True == 1 must not validate a schema.
        malformed_number = {**changed, "page_count": float("nan")}
        for payload in (json.dumps(changed), json.dumps(malformed_number),
                        "[" * 1500 + "0" + "]" * 1500):
            script = "import sys; sys.stdout.write(" + repr(payload) + ")"
            with patch.object(self.module, "_worker_command", return_value=[sys.executable, "-I", "-c", script]):
                with self.assertRaises(InvalidInput):
                    self.extract(raw)

    def test_worker_fails_closed_when_pinned_dependency_is_missing_or_wrong(self):
        worker_path = str(Path(self.module.__file__).with_name("pdf_worker.py"))
        with tempfile.TemporaryDirectory() as directory:
            venv.EnvBuilder(with_pip=False).create(directory)
            executable = str(Path(directory) / "bin" / "python")
            command = [executable, "-I", "-B", worker_path]
            with patch.object(self.module, "_worker_command", return_value=command):
                with self.assertRaisesRegex(InvalidInput, "exact pinned"):
                    self.extract(text_pdf([["Fictional missing dependency."]]))
            site = Path(directory) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
            metadata = site / "pypdf-0.0.0.dist-info"
            metadata.mkdir()
            (metadata / "METADATA").write_text("Metadata-Version: 2.1\nName: pypdf\nVersion: 0.0.0\n", encoding="utf-8")
            with patch.object(self.module, "_worker_command", return_value=command):
                with self.assertRaisesRegex(InvalidInput, "exact pinned"):
                    self.extract(text_pdf([["Fictional mismatched dependency."]]))

    def test_compressed_stream_limit_rejects_before_unbounded_expansion(self):
        raw = streams_pdf([b" " * (16 * 1024 * 1024)], compressed=True)
        self.assertLess(len(raw), 65536)
        with self.assertRaises(InvalidInput):
            self.extract(raw)
        self.assertEqual(self.extract(text_pdf([["After expansion rejection."]]))["text"],
                         "After expansion rejection.")

    def test_all_orthogonal_text_rotations_retain_page_anchors(self):
        matrices = ("1 0 0 1", "0 1 -1 0", "-1 0 0 -1", "0 -1 1 0")
        streams = [(f"BT /F1 10 Tf {matrix} 300 300 Tm (Fictional rotation {index * 90}.) Tj ET").encode()
                   for index, matrix in enumerate(matrices)]
        result = self.extract(streams_pdf(streams))
        self.assertEqual(result["lines"], [
            {"line": 1, "text": "Fictional rotation 0.", "page": 1, "page_line": 1},
            {"line": 2, "text": "Fictional rotation 90.", "page": 2, "page_line": 1},
            {"line": 3, "text": "Fictional rotation 180.", "page": 3, "page_line": 1},
            {"line": 4, "text": "Fictional rotation 270.", "page": 4, "page_line": 1},
        ])

    def test_actions_attachments_forms_and_annotations_reject_as_unqualified_content(self):
        content = [b"BT /F1 10 Tf 36 756 Td (Fictional main page.) Tj ET"]
        attachment = b"Independent fictional attachment, not a patient record."
        inputs = [
            streams_pdf(content, catalog_extra=b"/OpenAction << /S /JavaScript /JS (fixture) >> "),
            streams_pdf(content, catalog_extra=b"/Names << /EmbeddedFiles << /Names [(fictional.txt) 6 0 R] >> >> ",
                        extra_objects=(
                            b"<< /Type /Filespec /F (fictional.txt) /EF << /F 7 0 R >> >>",
                            f"<< /Type /EmbeddedFile /Length {len(attachment)} >>\nstream\n".encode()
                            + attachment + b"\nendstream")),
            streams_pdf(content, catalog_extra=b"/AcroForm << /Fields [] >> "),
            streams_pdf(content, page_extra=b"/Annots [<< /Type /Annot /Subtype /Text /Rect [0 0 20 20] /Contents (Fictional annotation.) >>] "),
        ]
        for raw in inputs:
            with self.subTest(length=len(raw)):
                with self.assertRaisesRegex(InvalidInput, "unsupported"):
                    self.extract(raw)


if __name__ == "__main__":
    unittest.main()
