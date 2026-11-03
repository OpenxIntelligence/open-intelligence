"""No-network validation of the real-backend evaluation harness."""
import unittest
from unittest.mock import patch
import json
from open_intelligence.store import InvalidInput
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


if __name__ == "__main__":
    unittest.main()
