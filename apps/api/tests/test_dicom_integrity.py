"""Bounded parser tests over independently authored fictional Part 10 bytes."""

from dataclasses import FrozenInstanceError, asdict
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import struct
import unittest
from unittest.mock import patch
import warnings

from dicom_integrity_fixture import dicom_bytes, element, file_bytes, fixture_elements
from oi_api import dicom_integrity


def replace(elements, tag, vr, value):
    return [(key, vr, value) if key == tag else (key, old_vr, old_value)
            for key, old_vr, old_value in elements]


class DicomIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.parser = dicom_integrity

    def reject(self, raw):
        with self.assertRaises(self.parser.DicomIntegrityError) as caught:
            self.parser.parse_dicom(raw)
        self.assertNotIn("PRIVATE-DETAIL", str(caught.exception))
        self.assertNotIn("SYNTHETIC-ALPHA", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_parses_actual_image_identity_and_exact_original_hash(self):
        raw = dicom_bytes()
        actual = self.parser.parse_dicom(raw)
        self.assertEqual(asdict(actual), {
            "patient_id": "SYNTHETIC-ALPHA", "issuer": "SYNTHETIC-PACS",
            "study_uid": "2.25.11001", "series_uid": "2.25.11002", "sop_uid": "2.25.11003",
            "sop_class_uid": "1.2.840.10008.5.1.4.1.1.2",
            "transfer_syntax_uid": "1.2.840.10008.1.2.1", "study_date": "2026-05-17",
            "modality": "CT", "rows": 2, "columns": 2,
            "byte_count": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        })
        with self.assertRaises(FrozenInstanceError):
            actual.patient_id = "ANOTHER-SUBJECT"

    def test_two_instances_keep_distinct_identity_and_bytes(self):
        first = self.parser.parse_dicom(dicom_bytes())
        second = self.parser.parse_dicom(dicom_bytes(sop_uid="2.25.11004", pixels=b"\4\0\5\0\6\0\7\0"))
        self.assertEqual(second.sop_uid, "2.25.11004")
        self.assertNotEqual(first.sha256, second.sha256)
        self.assertEqual((first.patient_id, first.study_uid), (second.patient_id, second.study_uid))

    def test_whole_file_hash_includes_preamble_and_nonpixel_metadata(self):
        raw = dicom_bytes()
        original = self.parser.parse_dicom(raw)
        for changed in (b"X" + raw[1:], raw.replace(b"FICTIONAL^INDEPENDENT", b"FICTIONAL^OTHER-NAME!")):
            result = self.parser.parse_dicom(changed)
            self.assertEqual(result.sop_uid, original.sop_uid)
            self.assertNotEqual(result.sha256, original.sha256)
            self.assertEqual(result.sha256, hashlib.sha256(changed).hexdigest())

    def test_bytes_type_and_complete_part10_framing_are_required(self):
        raw = dicom_bytes()
        for bad in (None, "PRIVATE-DETAIL", bytearray(raw), memoryview(raw), b"", raw[132:],
                    raw[:128] + b"NOPE" + raw[132:], b"\0" * 128 + b"DICMPRIVATE-DETAIL"):
            with self.subTest(kind=type(bad).__name__):
                self.reject(bad)
        for end in (1, 127, 131, 135, 139, 143, 151, 200, len(raw) - 1, len(raw) - 4):
            with self.subTest(end=end):
                self.reject(raw[:end])

    def test_wire_bound_is_enforced_without_truncating_a_valid_object(self):
        meta, dataset = fixture_elements()
        position = next(i for i, item in enumerate(dataset) if item[0] > 0x00111010)
        dataset.insert(position, (0x00111010, "OB", b""))
        missing = 2_097_152 - len(file_bytes(meta, dataset))
        dataset[position] = (0x00111010, "OB", b"\0" * missing)
        raw = file_bytes(meta, dataset)
        self.assertEqual(len(raw), 2_097_152)
        self.assertEqual(self.parser.parse_dicom(raw).byte_count, 2_097_152)
        self.reject(raw + b"\0\0")

    def test_duplicate_identity_tags_are_rejected_even_if_values_match(self):
        meta, dataset = fixture_elements()
        for tag in (0x00080018, 0x00100020, 0x00100021, 0x0020000D, 0x0020000E):
            at = next(i for i, item in enumerate(dataset) if item[0] == tag)
            for replacement in (dataset[at], (tag, dataset[at][1], b"PRIVATE-DETAIL")):
                with self.subTest(tag=hex(tag), matching=replacement == dataset[at]):
                    self.reject(file_bytes(meta, dataset[:at] + [replacement] + dataset[at:]))
        self.reject(file_bytes(meta[:2] + [meta[2]] + meta[2:], dataset))

    def test_out_of_order_and_interleaved_file_meta_are_rejected(self):
        meta, dataset = fixture_elements()
        self.reject(file_bytes(meta, [dataset[1], dataset[0], *dataset[2:]]))
        self.reject(file_bytes([meta[1], meta[0], *meta[2:]], dataset))
        self.reject(file_bytes(meta, dataset[:2] + [meta[2]] + dataset[2:]))

    def test_meta_length_must_match_exact_group_boundary(self):
        raw = dicom_bytes()
        declared = struct.unpack_from("<I", raw, 140)[0]
        for length in (0, declared - 2, declared + 2, 0xFFFFFFFE):
            self.reject(raw[:140] + struct.pack("<I", length) + raw[144:])

    def test_file_meta_and_dataset_sop_identity_must_agree(self):
        meta, dataset = fixture_elements()
        self.reject(file_bytes(replace(meta, 0x00020003, "UI", b"2.25.999"), dataset))
        self.reject(file_bytes(replace(meta, 0x00020002, "UI", b"1.2.840.10008.5.1.4.1.1.4"), dataset))

    def test_supported_transfer_syntax_and_storage_class_are_explicit(self):
        meta, dataset = fixture_elements()
        for uid in (b"1.2.840.10008.1.2", b"1.2.840.10008.1.2.2", b"1.2.840.10008.1.2.4.90"):
            self.reject(file_bytes(replace(meta, 0x00020010, "UI", uid), dataset))
        for uid in (b"1.2.840.10008.5.1.4.1.1.4", b"1.2.840.10008.5.1.4.1.1.2.1"):
            self.reject(file_bytes(replace(meta, 0x00020002, "UI", uid),
                                   replace(dataset, 0x00080016, "UI", uid)))

    def test_uids_are_single_canonical_bounded_numeric_values(self):
        meta, dataset = fixture_elements()
        for value in (b"", b"1.02.3", b".1.2", b"1.2.", b"1..2", b"1.2\\1.3", b"1.2\0.3",
                      b"1." + b"2" * 63, b"PRIVATE-DETAIL", b"1.2 "):
            with self.subTest(value=value):
                self.reject(file_bytes(meta, replace(dataset, 0x0020000D, "UI", value)))
        self.reject(file_bytes(meta, replace(dataset, 0x0020000D, "LO", b"1.2.3")))

    def test_patient_and_issuer_are_nonempty_bounded_single_ascii_identifiers(self):
        meta, dataset = fixture_elements()
        for tag in (0x00100020, 0x00100021):
            for value in (b"", b" ", b"A" * 65, b"PRIVATE-DETAIL\n", b"A\\B", b"A\0B",
                          b"PRIVATE-DETAIL\x80", b" SUBJECT"):
                with self.subTest(tag=hex(tag), value=value):
                    self.reject(file_bytes(meta, replace(dataset, tag, "LO", value)))
            self.reject(file_bytes(meta, replace(dataset, tag, "PN", b"SUBJECT")))

    def test_study_date_is_real_calendar_date_not_a_lexical_placeholder(self):
        self.assertEqual(self.parser.parse_dicom(dicom_bytes(study_date="20240229")).study_date, "2024-02-29")
        for value in ("20260229", "20261301", "20260001", "20260500", "00000517", "2026-05-17", "202605"):
            with self.subTest(value=value):
                self.reject(dicom_bytes(study_date=value))

    def test_required_identity_and_pixel_description_cannot_be_omitted(self):
        meta, dataset = fixture_elements()
        for tag in (0x00020001, 0x00020002, 0x00020003, 0x00020010, 0x00020012):
            self.reject(file_bytes([item for item in meta if item[0] != tag], dataset))
        for tag in (0x00080016, 0x00080018, 0x00080020, 0x00080060, 0x00100020, 0x00100021,
                    0x0020000D, 0x0020000E, 0x00280002, 0x00280004, 0x00280010, 0x00280011,
                    0x00280100, 0x00280101, 0x00280102, 0x00280103, 0x7FE00010):
            with self.subTest(tag=hex(tag)):
                self.reject(file_bytes(meta, [item for item in dataset if item[0] != tag]))

    def test_pixel_geometry_and_encoding_are_checked_before_return(self):
        meta, dataset = fixture_elements()
        for tag, vr, value in (
            (0x00080060, "CS", b"MR"), (0x00280002, "US", struct.pack("<H", 3)),
            (0x00280004, "CS", b"MONOCHROME1"), (0x00280008, "IS", b"2"),
            (0x00280010, "US", b"\0\0"), (0x00280011, "US", b"\0\0"),
            (0x00280010, "US", b"\2\0\2\0"), (0x00280011, "IS", b"2"),
            (0x00280100, "US", struct.pack("<H", 8)), (0x00280101, "US", struct.pack("<H", 12)),
            (0x00280102, "US", struct.pack("<H", 14)), (0x00280103, "US", struct.pack("<H", 2)),
            (0x7FE00010, "OW", b"\0" * 6), (0x7FE00010, "OW", b"\0" * 10),
            (0x7FE00010, "OB", b"\0" * 8),
        ):
            with self.subTest(tag=hex(tag), value=value):
                self.reject(file_bytes(meta, replace(dataset, tag, vr, value)))

    def test_each_dimension_has_a_bound_independent_of_total_wire_size(self):
        for rows, columns in ((1024, 1), (1, 1024)):
            actual = self.parser.parse_dicom(dicom_bytes(rows=rows, columns=columns))
            self.assertEqual((actual.rows, actual.columns), (rows, columns))
        for rows, columns in ((1025, 1), (1, 1025)):
            self.reject(dicom_bytes(rows=rows, columns=columns))

    def test_authored_512_square_frame_is_supported_without_pixel_decoding(self):
        raw = dicom_bytes(rows=512, columns=512)
        result = self.parser.parse_dicom(raw)
        self.assertEqual((result.rows, result.columns), (512, 512))
        self.assertGreater(result.byte_count, 524_288)
        self.assertEqual(result.sha256, hashlib.sha256(raw).hexdigest())

    def test_missing_number_of_frames_and_signed_16_bit_pixels_are_supported(self):
        meta, dataset = fixture_elements()
        dataset = [item for item in dataset if item[0] != 0x00280008]
        dataset = replace(dataset, 0x00280103, "US", struct.pack("<H", 1))
        self.assertEqual(self.parser.parse_dicom(file_bytes(meta, dataset)).rows, 2)

    def test_resource_limits_also_bound_element_count_and_meta_group(self):
        meta, dataset = fixture_elements()
        extra = [(0x00111000 + index, "OB", b"") for index in range(4096)]
        self.reject(file_bytes(meta, sorted(dataset + extra)))
        meta.append((0x00020102, "OB", b"\0" * 65_536))
        self.reject(file_bytes(meta, dataset))

    def test_sequences_undefined_lengths_and_fragments_are_out_of_profile(self):
        meta, dataset = fixture_elements()
        self.reject(file_bytes(meta, sorted(dataset + [(0x00081110, "SQ", b"")])))
        raw = dicom_bytes()
        pixel_header = raw.index(b"\xe0\x7f\x10\x00OW")
        self.reject(raw[:pixel_header + 8] + b"\xff" * 4 + raw[pixel_header + 12:])
        self.reject(raw + struct.pack("<HHI", 0xFFFE, 0xE000, 0))

    def test_unknown_vr_reserved_bits_odd_lengths_and_trailing_data_are_rejected(self):
        raw = dicom_bytes()
        first_meta_long = raw.index(b"\x02\x00\x01\x00OB")
        self.reject(raw[:first_meta_long + 6] + b"\1\0" + raw[first_meta_long + 8:])
        patient = raw.index(b"\x10\x00\x20\x00LO")
        self.reject(raw[:patient + 4] + b"ZZ" + raw[patient + 6:])
        self.reject(raw[:patient + 6] + struct.pack("<H", 15) + raw[patient + 8:])
        self.reject(raw + b"PRIVATE-DETAIL")
        self.reject(raw + element(0xFFFCFFFC, "OB", b"\0\0"))

    def test_character_set_and_file_meta_version_are_explicit(self):
        meta, dataset = fixture_elements()
        self.assertEqual(self.parser.parse_dicom(file_bytes(
            meta, [(0x00080005, "CS", b"ISO_IR 6"), *dataset])).patient_id, "SYNTHETIC-ALPHA")
        for charset in (b"ISO_IR 192", b"PRIVATE-DETAIL", b"ISO_IR 6\\ISO_IR 100"):
            self.reject(file_bytes(meta, [(0x00080005, "CS", charset), *dataset]))
        self.reject(file_bytes(replace(meta, 0x00020001, "OB", b"\0\2"), dataset))

    def test_rejected_identifiers_do_not_reach_logs_warnings_or_exception_context(self):
        meta, dataset = fixture_elements()
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output), warnings.catch_warnings(record=True) as notices:
            with self.assertNoLogs("pydicom"):
                self.reject(file_bytes(meta, replace(dataset, 0x0020000D, "UI", b"PRIVATE-DETAIL")))
                self.reject(file_bytes(meta, replace(dataset, 0x00100020, "LO", b"PRIVATE-DETAIL\x80")))
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(notices, [])

    def test_success_does_not_mutate_pydicom_configuration_or_disclose_repr_identifiers(self):
        from pydicom import config
        before = (config.settings.reading_validation_mode, config.data_element_callback,
                  dict(config.data_element_callback_kwargs))
        result = self.parser.parse_dicom(dicom_bytes())
        after = (config.settings.reading_validation_mode, config.data_element_callback,
                 dict(config.data_element_callback_kwargs))
        self.assertEqual(before, after)
        self.assertNotIn("SYNTHETIC-ALPHA", repr(result))
        self.assertNotIn("2.25.11003", repr(result))

    def test_sequence_tags_cannot_be_hidden_under_another_explicit_vr(self):
        meta, dataset = fixture_elements()
        for vr in ("UN", "OB"):
            with self.subTest(vr=vr):
                self.reject(file_bytes(meta, sorted(dataset + [(0x00081110, vr, b"")])))

    def test_diagnostic_mode_and_global_callbacks_are_refused_before_library_read(self):
        from pydicom import config
        with patch.object(config, "debugging", True), self.assertNoLogs("pydicom", level="DEBUG"):
            self.reject(dicom_bytes())
        calls = []
        def callback(raw, **kwargs):
            calls.append(raw)
            return raw
        with patch.object(config, "data_element_callback", callback):
            self.reject(dicom_bytes())
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
