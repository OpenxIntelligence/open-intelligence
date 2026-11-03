"""No-network validation of the real-backend evaluation harness."""
import unittest
from unittest.mock import patch
import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
from open_intelligence.store import InvalidInput
from tools.imaging import pacsnode_live_probe as probe
from tools.imaging.pacsnode_live_probe import (
    SOP_UIDS, IMAGE_STUDY_UID, _uid_value, _qido_list, loopback_origin,
    multipart_body, multipart_dicom_parts,
)


class RealBackendHarnessTests(unittest.TestCase):
    def test_no_external_or_redirectable_origin_allowed(self):
        self.assertEqual(loopback_origin("http://127.0.0.1:18042"),
                         "http://127.0.0.1:18042")
        for value in (
            "http://localhost:18042", "https://127.0.0.1:18042",
            "http://www.example.org:18042",
            "http://127.0.0.1:18042/wado",
            "http://127.0.0.1:18042?token=a",
            "http://a:b@127.0.0.1:18042", "http://127.0.0.1",
            "http://127.0.0.2:18042", "file:///tmp/study.dcm",
            "http://[::1]:18042",
        ):
            with self.subTest(value=value), self.assertRaises(InvalidInput):
                loopback_origin(value)

    def test_two_fictional_part10_parts_are_lossless_in_test_harness(self):
        first = b"\0"*128 + b"DICM" + b"\x01"*16
        second = b"\0"*128 + b"DICM" + b"\x02"*18
        media, wire = multipart_body([first, second])
        self.assertEqual(multipart_dicom_parts(media, wire), [first, second])
        self.assertIn('multipart/related; type="application/dicom"', media)

    def test_bad_mime_or_extra_part_refused(self):
        one = b"\0"*128 + b"DICM" + b"hi"
        media, wire = multipart_body([one])
        with self.assertRaises(InvalidInput):
            multipart_dicom_parts("application/dicom", wire)
        with self.assertRaises(InvalidInput):
            multipart_dicom_parts(media, b"not multipart")
        with self.assertRaises(InvalidInput):
            multipart_body([])
        with self.assertRaises(InvalidInput):
            multipart_body([one]*3)

    def test_instance_metadata_requires_exact_uid_tag(self):
        self.assertEqual(_uid_value({"00080018":{"vr":"UI",
                                                   "Value":[SOP_UIDS[0]]}},
                                    "00080018"),SOP_UIDS[0])
        for row in (
            {"00080018":{"vr":"IS","Value":[SOP_UIDS[0]]}},
            {"00080018":{"vr":"UI","Value":[SOP_UIDS[0],SOP_UIDS[1]]}},
            {},
        ):
            with self.subTest(row=row),self.assertRaises(InvalidInput):
                _uid_value(row,"00080018")

    def test_qido_mime_deviation_is_retained_not_silently_corrected(self):
        payload = json.dumps([{"0020000D": {"vr": "UI", "Value": [IMAGE_STUDY_UID]}}]).encode()
        for media in ("application/dicom+json", "application/json"):
            with self.subTest(media=media), patch(
                "tools.imaging.pacsnode_live_probe._request",
                return_value=(200, media, payload)
            ):
                result, actual_mime = _qido_list("http://127.0.0.1:18042/wado/studies")
                self.assertEqual(actual_mime, media)
                self.assertEqual(_uid_value(result[0], "0020000D"), IMAGE_STUDY_UID)
        with patch(
            "tools.imaging.pacsnode_live_probe._request",
            return_value=(200, "text/html", payload)
        ), self.assertRaises(InvalidInput):
            _qido_list("http://127.0.0.1:18042/wado/studies")

    def test_study_uid_scope_is_fixed_fictional(self):
        self.assertEqual(len(SOP_UIDS),2)
        self.assertTrue(IMAGE_STUDY_UID.startswith("2.25."))
        self.assertNotEqual(SOP_UIDS[0],SOP_UIDS[1])


class EvaluationReceiptTests(unittest.TestCase):
    def invoke(self, *, original=True, pixels=True, error=None):
        evidence = {
            "technical_evaluation_passed": pixels,
            "uncompressed_pixel_integrity_passed": pixels,
            "source_and_retrieved_objects_byte_identical": original,
            "qido_media_type_conformant": False,
            "clinical_or_full_dicomweb_approval": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            stdout, stderr = StringIO(), StringIO()
            with patch.object(probe, "run_evaluation", return_value=evidence,
                              side_effect=error), patch.object(
                probe.sys, "argv", ["probe", "--base-url", "http://127.0.0.1:18042",
                                    "--output", str(output)]
            ), redirect_stdout(stdout), redirect_stderr(stderr):
                status = probe.main()
            saved = json.loads(output.read_text()) if output.exists() else None
            return status, saved, stdout.getvalue() + stderr.getvalue()

    def test_changed_original_file_cannot_pass_with_matching_pixels(self):
        status, saved, _ = self.invoke(original=False)
        self.assertEqual(status, 1)
        self.assertIsNotNone(saved)
        self.assertFalse(saved["technical_evaluation_passed"])
        self.assertFalse(saved["source_and_retrieved_objects_byte_identical"])

    def test_pixel_failure_preserves_receipt(self):
        status, saved, _ = self.invoke(pixels=False)
        self.assertEqual(status, 1)
        self.assertIsNotNone(saved)
        self.assertFalse(saved["uncompressed_pixel_integrity_passed"])

    def test_backend_error_preserves_safe_failure_receipt(self):
        sensitive = "UNTRUSTED_SERVER_RESPONSE_MUST_NOT_BE_LOGGED"
        status, saved, logs = self.invoke(error=InvalidInput(sensitive))
        self.assertEqual(status, 1)
        self.assertIsNotNone(saved)
        self.assertFalse(saved["technical_evaluation_passed"])
        self.assertEqual(saved["failure_type"], "InvalidInput")
        self.assertNotIn(sensitive, json.dumps(saved) + logs)

    def test_verified_bytes_do_not_clear_standards_hold(self):
        status, saved, logs = self.invoke()
        self.assertEqual(status, 0)
        self.assertTrue(saved["technical_evaluation_passed"])
        self.assertFalse(saved["qido_media_type_conformant"])
        self.assertFalse(saved["clinical_or_full_dicomweb_approval"])
        self.assertIn("STANDARDS HOLD", logs)


if __name__ == "__main__":
    unittest.main()
