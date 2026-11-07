"""Non-diagnostic preview tests for the bounded synthetic CT custody profile."""

import struct
import unittest
import zlib

from oi_api.dicom_integrity import DicomIntegrityError, render_dicom_preview

from dicom_integrity_fixture import dicom_bytes, file_bytes, fixture_elements


PNG = b"\x89PNG\r\n\x1a\n"


def chunks(raw):
    assert raw.startswith(PNG)
    offset = len(PNG)
    while offset < len(raw):
        length = struct.unpack_from(">I", raw, offset)[0]
        kind = raw[offset + 4:offset + 8]
        payload = raw[offset + 8:offset + 8 + length]
        yield kind, payload
        offset += 12 + length


class DicomPreviewTests(unittest.TestCase):
    def test_composed_route_returns_png_bound_to_the_original_and_access_receipt(self):
        # Execute the real route's response preparation without a TCP server.
        # Custody/database behavior is covered by the PostgreSQL/browser suites.
        import hashlib
        from contextlib import nullcontext
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch
        from starlette.requests import Request
        from oi_api.access import Principal
        from oi_api.patients import patient_router
        raw = dicom_bytes(rows=2, columns=2, pixels=struct.pack("<4H", 0, 100, 200, 300))
        receipt = "ACCESS-" + "A" * 32
        principal = Principal(actor="ACTOR-FICTIONAL", organization="ORG-FICTIONAL",
            purpose="operations", patient_ids={"PAT-FICTIONAL"},
            actions={"patient_read", "image_original_read"},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        database = MagicMock()
        database.registry_connection.return_value = nullcontext(object())
        registry = MagicMock()
        with patch("oi_api.patients.registry_for_principal", return_value=registry), \
             patch("oi_api.patients.authenticate_request", return_value=principal), \
             patch("oi_api.patients.PostgresSourceImages") as images:
            def original(*args, **kwargs):
                response = kwargs["prepare_response"](raw, receipt)
                kwargs["recheck_authority"]()
                return response
            images.return_value.original.side_effect = original
            router = patient_router(database, MagicMock())
            endpoint = next(route.endpoint for route in router.routes
                            if route.operation_id == "preview_source_image_v1")
            response = endpoint(Request({"type": "http", "query_string": b""}),
                "PAT-FICTIONAL", "CASE-FICTIONAL", "SRC-" + "B"*32, "IMG-" + "C"*32, principal)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, render_dicom_preview(raw))
        self.assertEqual(response.headers["x-oi-original-sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(response.headers["x-oi-access-receipt"], receipt)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_preview_preserves_dimensions_and_maps_frame_min_max_without_clinical_windowing(self):
        raw = dicom_bytes(rows=2, columns=2, pixels=struct.pack("<4H", 0, 100, 200, 300))
        png = render_dicom_preview(raw)
        self.assertTrue(png.startswith(PNG))
        decoded = dict(chunks(png))
        width, height, depth, colour, compression, filtering, interlace = struct.unpack(">IIBBBBB", decoded[b"IHDR"])
        self.assertEqual((width, height, depth, colour, compression, filtering, interlace), (2, 2, 8, 0, 0, 0, 0))
        self.assertEqual(zlib.decompress(decoded[b"IDAT"]), b"\x00\x00\x55\x00\xaa\xff")

    def test_signed_pixels_are_supported_with_the_same_bounded_profile(self):
        meta, dataset = fixture_elements(rows=2, columns=2, pixels=struct.pack("<4h", -300, -100, 100, 300))
        dataset = [(tag, vr, struct.pack("<H", 1) if tag == 0x00280103 else value)
                   for tag, vr, value in dataset]
        png = render_dicom_preview(file_bytes(meta, dataset))
        decoded = dict(chunks(png))
        self.assertEqual(zlib.decompress(decoded[b"IDAT"]), b"\x00\x00\x55\x00\xaa\xff")

    def test_constant_frame_is_visible_without_inventing_contrast(self):
        raw = dicom_bytes(rows=2, columns=2, pixels=struct.pack("<4H", 42, 42, 42, 42))
        decoded = dict(chunks(render_dicom_preview(raw)))
        self.assertEqual(zlib.decompress(decoded[b"IDAT"]), b"\x00\x7f\x7f\x00\x7f\x7f")

    def test_unsupported_or_corrupt_originals_fail_closed(self):
        for raw in (b"", b"not a dicom", dicom_bytes()[:-2]):
            with self.subTest(size=len(raw)):
                with self.assertRaises(DicomIntegrityError):
                    render_dicom_preview(raw)


if __name__ == "__main__":
    unittest.main()
