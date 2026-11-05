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
