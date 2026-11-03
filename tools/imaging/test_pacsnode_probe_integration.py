"""Exercise the research evaluator with real DICOM bytes and a bounded HTTP fake.

Run only after installing requirements-pacsnode-research.txt. This module is
outside tests/ so pydicom remains an isolated evaluation dependency. No network,
PACS process, compression codec, or numerical pixel decoder is used here.
"""
from email import policy
from email.message import Message
from email.parser import BytesParser
from hashlib import sha256
from io import BytesIO
import json
import struct
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import warnings

from pydicom import dcmread, dcmwrite
from pydicom.uid import ImplicitVRLittleEndian

from tools.imaging import pacsnode_live_probe as probe


ORIGIN = "http://127.0.0.1:18042"
EXPLICIT_LE = "1.2.840.10008.1.2.1"


def rewrite_dataset(data, mutate):
    dataset = dcmread(BytesIO(data))
    mutate(dataset)
    output = BytesIO()
    dcmwrite(output, dataset, enforce_file_format=True)
    return output.getvalue()


class FictionalDicomExchange:
    """Return only the two objects actually uploaded by the real evaluator."""

    def __init__(self, transform_first=None, qido_type="application/dicom+json"):
        self.transform_first = transform_first
        self.qido_type = qido_type
        self.uploaded = {}
        self.returned = {}
        self.wado_accepts = []

    @staticmethod
    def json_response(value, media_type="application/dicom+json"):
        return 200, media_type, json.dumps(value).encode("utf-8")

    def request(self, url, *, method="GET", content=None, accept=None,
                content_type=None):
        parsed_url = urlsplit(url)
        if parsed_url.scheme != "http" or parsed_url.netloc != "127.0.0.1:18042":
            raise AssertionError("Unexpected external origin in offline evaluation")
        if method == "POST" and parsed_url.path == "/wado/studies":
            if self.uploaded or not isinstance(content, bytes) or len(content) > 20_000:
                raise AssertionError("Expected one bounded two-object upload")
            message = BytesParser(policy=policy.default).parsebytes(
                ("Content-Type: " + content_type + "\r\n\r\n").encode("ascii")
                + content
            )
            parts = list(message.iter_parts())
            if message.defects or len(parts) != 2:
                raise AssertionError("Evaluator did not send two well-formed MIME parts")
            referenced = []
            for part in parts:
                data = part.get_payload(decode=True)
                dataset = dcmread(BytesIO(data))
                uid = str(dataset.SOPInstanceUID)
                if uid in self.uploaded:
                    raise AssertionError("Duplicate uploaded SOP identity")
                self.uploaded[uid] = data
                referenced.append({
                    "00081150": {"vr": "UI", "Value": [str(dataset.SOPClassUID)]},
                    "00081155": {"vr": "UI", "Value": [uid]},
                })
            return self.json_response({"00081199": {"vr": "SQ", "Value": referenced}})
        if not self.uploaded:
            raise AssertionError("Discovery or retrieval preceded upload")
        datasets = [dcmread(BytesIO(data)) for data in self.uploaded.values()]
        study = str(datasets[0].StudyInstanceUID)
        series = str(datasets[0].SeriesInstanceUID)
        prefix = f"/wado/studies/{study}/series/{series}/instances"
        if method == "GET" and parsed_url.path == "/wado/studies":
            if parse_qs(parsed_url.query) != {"StudyInstanceUID": [study]}:
                raise AssertionError("Study discovery lost its requested identity")
            return self.json_response([
                {"0020000D": {"vr": "UI", "Value": [study]}}
            ], self.qido_type)
        if method == "GET" and parsed_url.path == prefix:
            rows = [{
                "0020000D": {"vr": "UI", "Value": [str(ds.StudyInstanceUID)]},
                "0020000E": {"vr": "UI", "Value": [str(ds.SeriesInstanceUID)]},
                "00080018": {"vr": "UI", "Value": [str(ds.SOPInstanceUID)]},
                "00080016": {"vr": "UI", "Value": [str(ds.SOPClassUID)]},
                "00080020": {"vr": "DA", "Value": [str(ds.StudyDate)]},
                "00080060": {"vr": "CS", "Value": [str(ds.Modality)]},
            } for ds in datasets]
            return self.json_response(rows, self.qido_type)
        if method == "GET" and parsed_url.path.startswith(prefix + "/"):
            uid = parsed_url.path[len(prefix) + 1:]
            if uid not in self.uploaded or uid in self.returned:
                raise AssertionError("Unexpected or duplicate instance retrieval")
            data = self.uploaded[uid]
            if uid == next(iter(self.uploaded)) and self.transform_first:
                data = self.transform_first(data)
            self.returned[uid] = data
            self.wado_accepts.append(accept)
            # This response is authored independently of the production MIME helper.
            body = (b"--OfflineDicomResponse\r\nContent-Type: application/dicom\r\n\r\n"
                    + data + b"\r\n--OfflineDicomResponse--\r\n")
            return (200, 'multipart/related; type="application/dicom"; '
                    'boundary=OfflineDicomResponse', body)
        raise AssertionError(f"Unexpected evaluator request: {method} {parsed_url.path}")


class ProbeIntegrityIntegrationTests(unittest.TestCase):
    def evaluate(self, **exchange_options):
        exchange = FictionalDicomExchange(**exchange_options)
        with patch.object(probe, "_request", side_effect=exchange.request):
            receipt = probe.run_evaluation(ORIGIN)
        return receipt, exchange

    def test_two_original_objects_roundtrip_with_source_guards(self):
        receipt, exchange = self.evaluate()
        self.assertEqual(len(exchange.uploaded), 2)
        self.assertEqual(receipt["dicom_count"], 2)
        self.assertEqual(receipt["study_count"], 1)
        self.assertEqual(receipt["series_count"], 1)
        self.assertTrue(receipt["technical_evaluation_passed"])
        self.assertTrue(receipt["source_and_retrieved_objects_byte_identical"])
        self.assertTrue(receipt["uncompressed_pixel_integrity_passed"])
        self.assertEqual(receipt["sop_original_sha256"], {
            uid: sha256(data).hexdigest() for uid, data in exchange.uploaded.items()
        })
        self.assertEqual(receipt["sop_returned_sha256"], receipt["sop_original_sha256"])
        self.assertTrue(receipt["first_party_wrong_case_rejected"])
        self.assertTrue(receipt["first_party_amendment_rejected"])
        self.assertTrue(receipt["first_party_source_bound_wado_verified"])
        self.assertTrue(receipt["first_party_wado_wrong_case_refused"])
        self.assertTrue(receipt["first_party_wado_amendment_refused"])
        self.assertEqual(len(receipt["first_party_source_bound_receipts"]), 2)
        self.assertFalse(receipt["pacs_authentication_verified"])
        self.assertFalse(receipt["pacs_tenant_isolation_verified"])
        self.assertFalse(receipt["clinical_or_full_dicomweb_approval"])

    def test_changed_preamble_fails_even_when_all_pixel_bytes_match(self):
        receipt, exchange = self.evaluate(transform_first=lambda data: b"X" + data[1:])
        first, second = exchange.uploaded
        self.assertEqual(dcmread(BytesIO(exchange.uploaded[first])).PixelData,
                         dcmread(BytesIO(exchange.returned[first])).PixelData)
        self.assertTrue(receipt["uncompressed_pixel_integrity_passed"])
        self.assertEqual(receipt["exact_original_object_preserved"],
                         {first: False, second: True})
        self.assertFalse(receipt["source_and_retrieved_objects_byte_identical"])
        self.assertFalse(receipt["first_party_source_bound_wado_verified"])
        self.assertFalse(receipt["technical_evaluation_passed"])

    def test_changed_nonpixel_metadata_fails_original_object_gate(self):
        def change_description(data):
            return rewrite_dataset(data, lambda ds: setattr(
                ds, "StudyDescription", "ALTERED SYNTHETIC DESCRIPTION"))

        receipt, exchange = self.evaluate(transform_first=change_description)
        first = next(iter(exchange.uploaded))
        self.assertEqual(dcmread(BytesIO(exchange.uploaded[first])).PixelData,
                         dcmread(BytesIO(exchange.returned[first])).PixelData)
        self.assertTrue(receipt["pixel_diagnostics"][first]["encoded_pixel_bytes_equal"])
        self.assertFalse(receipt["exact_original_object_preserved"][first])
        self.assertFalse(receipt["technical_evaluation_passed"])

    def test_changed_raw_pixel_byte_fails_with_bounded_hash_diagnostics(self):
        def change_pixel(data):
            def mutate(ds):
                pixels = bytearray(ds.PixelData)
                pixels[0] ^= 1
                ds.PixelData = bytes(pixels)
            return rewrite_dataset(data, mutate)

        receipt, exchange = self.evaluate(transform_first=change_pixel)
        first = next(iter(exchange.uploaded))
        diagnostic = receipt["pixel_diagnostics"][first]
        self.assertEqual(diagnostic["source_pixel_length"], 8)
        self.assertEqual(diagnostic["retrieved_pixel_length"], 8)
        self.assertEqual(diagnostic["retrieved_transfer_syntax"], EXPLICIT_LE)
        self.assertNotEqual(diagnostic["source_pixel_sha256"],
                            diagnostic["retrieved_pixel_sha256"])
        self.assertFalse(diagnostic["encoded_pixel_bytes_equal"])
        self.assertFalse(receipt["uncompressed_pixel_integrity_passed"])
        self.assertFalse(receipt["technical_evaluation_passed"])

    def test_unexpected_valid_transfer_syntax_fails_even_with_equal_pixel_bytes(self):
        def change_encoding(data):
            return rewrite_dataset(data, lambda ds: setattr(
                ds.file_meta, "TransferSyntaxUID", ImplicitVRLittleEndian))

        receipt, exchange = self.evaluate(transform_first=change_encoding)
        first = next(iter(exchange.uploaded))
        diagnostic = receipt["pixel_diagnostics"][first]
        self.assertEqual(diagnostic["retrieved_transfer_syntax"], "1.2.840.10008.1.2")
        self.assertTrue(diagnostic["encoded_pixel_bytes_equal"])
        self.assertFalse(diagnostic["retrieval_is_expected_uncompressed_encoding"])
        self.assertFalse(receipt["uncompressed_pixel_integrity_passed"])
        self.assertFalse(receipt["technical_evaluation_passed"])

    def test_wado_explicitly_requests_the_uncompressed_syntax_it_records(self):
        receipt, exchange = self.evaluate()
        self.assertEqual(len(exchange.wado_accepts), 2)
        for accept in exchange.wado_accepts:
            with self.subTest(accept=accept):
                header = Message()
                header["Content-Type"] = accept
                self.assertEqual(header.get_content_type(), "multipart/related")
                self.assertEqual(header.get_param("type"), "application/dicom")
                self.assertEqual(header.get_param("transfer-syntax"), EXPLICIT_LE)
        for diagnostic in receipt["pixel_diagnostics"].values():
            self.assertEqual(diagnostic["requested_uncompressed_transfer_syntax"], EXPLICIT_LE)

    def test_fixture_generation_uses_valid_vrs_and_known_fictional_pixels(self):
        # A pydicom VR warning is a test failure, including an oversized SH value.
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            _, exchange = self.evaluate()
        pixels_by_instance = {}
        for data in exchange.uploaded.values():
            ds = dcmread(BytesIO(data))
            self.assertLessEqual(len(ds.AccessionNumber), 16)
            pixels_by_instance[int(ds.InstanceNumber)] = struct.unpack("<4H", ds.PixelData)
        self.assertEqual(pixels_by_instance, {1: (1, 2, 3, 4), 2: (2, 3, 4, 5)})

    def test_qido_json_deviation_remains_a_separate_standards_hold(self):
        receipt, _ = self.evaluate(qido_type="application/json")
        self.assertTrue(receipt["technical_evaluation_passed"])
        self.assertEqual(receipt["qido_media_types"], {
            "study": "application/json", "instance": "application/json",
        })
        self.assertFalse(receipt["qido_media_type_conformant"])
        self.assertFalse(receipt["standards_conformance_verified"])
        self.assertFalse(receipt["clinical_or_full_dicomweb_approval"])


if __name__ == "__main__":
    unittest.main()
