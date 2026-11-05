"""Pure read-integrity checks over independently authored fictional originals."""

from datetime import date, datetime, timezone
import hashlib
import unittest

from oi_api.source_integrity import SourceIntegrityError, validate_original


SOURCE_ONE = "SRC-" + "A" * 32
SOURCE_TWO = "SRC-" + "B" * 32
ORIGINAL = (
    "OI-SYNTHETIC-REPORT/1\n"
    "Patient: CASE-ALPHA\n"
    "Document: DOC-ALPHA\n"
    "Type: pathology\n"
    "Event-Date: 2026-05-03\n"
    "Issued-At: 2026-05-05\n"
    "Specimen: BIOPSY-ALPHA\n"
    "Finding: marker|not-reported|Fictional café <b>not tested</b>.  \n"
).encode("utf-8")
AMENDED = (
    "OI-SYNTHETIC-REPORT/1\n"
    "Patient: CASE-ALPHA\n"
    "Document: DOC-ALPHA\n"
    "Type: pathology\n"
    "Event-Date: 2026-05-03\n"
    "Issued-At: 2026-05-06\n"
    "Specimen: BIOPSY-ALPHA\n"
    "Amends: DOC-ALPHA@1\n"
    "Finding: marker|negative|Independently fictional amended finding.\n"
).encode("utf-8")


def original_row(**changes):
    row = {
        "source_id": SOURCE_ONE, "case_id": "CASE-ALPHA", "raw": ORIGINAL,
        "sha256": hashlib.sha256(ORIGINAL).hexdigest(), "document_id": "DOC-ALPHA",
        "version": 1, "state": "current", "kind": "pathology",
        "event_date": date(2026, 5, 3), "issued_at": date(2026, 5, 5),
        "specimen_id": "BIOPSY-ALPHA", "supersedes_id": None,
    }
    row.update(changes)
    return row


def amended_row(**changes):
    return original_row(**{
        "source_id": SOURCE_TWO, "raw": AMENDED,
        "sha256": hashlib.sha256(AMENDED).hexdigest(), "version": 2,
        "issued_at": date(2026, 5, 6), "supersedes_id": SOURCE_ONE,
        **changes,
    })


def predecessor(**changes):
    row = {
        "source_id": SOURCE_ONE, "case_id": "CASE-ALPHA", "document_id": "DOC-ALPHA",
        "version": 1, "kind": "pathology", "event_date": date(2026, 5, 3),
        "specimen_id": "BIOPSY-ALPHA", "state": "superseded",
    }
    row.update(changes)
    return row


class SourceIntegrityTests(unittest.TestCase):
    def assert_corrupt(self, row, *, requested_case_id="CASE-ALPHA", prior=None):
        with self.assertRaises(SourceIntegrityError) as raised:
            validate_original(row, requested_case_id=requested_case_id, predecessor=prior)
        self.assertIsInstance(raised.exception, RuntimeError)
        self.assertNotIn("PRIVATE-DETAIL", str(raised.exception))
        self.assertNotIn("not tested", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertTrue(raised.exception.__suppress_context__)

    def test_current_and_historical_originals_keep_every_byte(self):
        for state in ("current", "superseded"):
            with self.subTest(state=state):
                self.assertEqual(validate_original(original_row(state=state),
                                                   requested_case_id="CASE-ALPHA"), ORIGINAL)

    def test_current_and_historical_amendments_keep_their_own_original(self):
        for state in ("current", "superseded"):
            with self.subTest(state=state):
                actual = validate_original(amended_row(state=state), requested_case_id="CASE-ALPHA",
                                           predecessor=predecessor())
                self.assertEqual(actual, AMENDED)

    def test_bytea_views_return_bytes_without_changing_content(self):
        for raw in (bytearray(ORIGINAL), memoryview(ORIGINAL)):
            with self.subTest(kind=type(raw).__name__):
                result = validate_original(original_row(raw=raw), requested_case_id="CASE-ALPHA")
                self.assertIs(type(result), bytes)
                self.assertEqual(result, ORIGINAL)

    def test_source_bytes_are_bounded_at_65536_without_truncation(self):
        raw = ORIGINAL + b"\n" * (65536 - len(ORIGINAL))
        row = original_row(raw=raw, sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(validate_original(row, requested_case_id="CASE-ALPHA"), raw)
        raw += b"\n"
        self.assert_corrupt(original_row(raw=raw, sha256=hashlib.sha256(raw).hexdigest()))

    def test_hash_mismatch_is_stored_corruption(self):
        self.assert_corrupt(original_row(sha256="0" * 64))

    def test_requested_case_and_report_patient_must_both_match_storage(self):
        self.assert_corrupt(original_row(), requested_case_id="CASE-BETA")
        self.assert_corrupt(original_row(case_id="CASE-BETA"))
        raw = ORIGINAL.replace(b"Patient: CASE-ALPHA", b"Patient: CASE-BETA")
        self.assert_corrupt(original_row(raw=raw, sha256=hashlib.sha256(raw).hexdigest()))

    def test_stored_context_must_match_the_original_headers(self):
        for field, value in (
            ("document_id", "DOC-OTHER"), ("kind", "imaging"),
            ("event_date", date(2026, 5, 4)), ("issued_at", date(2026, 5, 7)),
            ("specimen_id", "BIOPSY-OTHER"), ("specimen_id", None),
            ("source_id", "PRIVATE-DETAIL"), ("state", "reviewed"),
        ):
            with self.subTest(field=field, value=value):
                self.assert_corrupt(original_row(**{field: value}))

    def test_postgresql_date_columns_require_date_objects(self):
        for field in ("event_date", "issued_at"):
            for value in ("2026-05-03", datetime(2026, 5, 3, tzinfo=timezone.utc), None):
                with self.subTest(field=field, value=value):
                    self.assert_corrupt(original_row(**{field: value}))

    def test_malformed_source_cannot_be_rescued_by_recomputing_its_hash(self):
        for raw in (
            ORIGINAL.replace(b"OI-SYNTHETIC-REPORT/1", b"PRIVATE-DETAIL/1"),
            ORIGINAL.replace(b"Document: DOC-ALPHA\n", b""),
            ORIGINAL.replace(b"\n", b"\r\n"), ORIGINAL + b"\x00", ORIGINAL + b"\xff", b"",
        ):
            with self.subTest(raw=raw[:30]):
                self.assert_corrupt(original_row(raw=raw, sha256=hashlib.sha256(raw).hexdigest()))
        for raw in (ORIGINAL.decode("utf-8"), None, 12):
            with self.subTest(kind=type(raw).__name__):
                self.assert_corrupt(original_row(raw=raw))

    def test_all_required_stored_fields_are_required(self):
        for field in original_row():
            with self.subTest(field=field):
                row = original_row()
                del row[field]
                self.assert_corrupt(row)

    def test_first_version_cannot_claim_or_receive_a_predecessor(self):
        self.assert_corrupt(original_row(supersedes_id=SOURCE_TWO))
        self.assert_corrupt(original_row(), prior=predecessor())
        self.assert_corrupt(amended_row(version=1, supersedes_id=None))

    def test_version_numbers_are_positive_integers(self):
        for version in (0, -1, True, "1", 1.0):
            with self.subTest(version=version):
                self.assert_corrupt(original_row(version=version))

    def test_amendment_requires_the_immediately_preceding_version(self):
        self.assert_corrupt(amended_row())
        self.assert_corrupt(amended_row(supersedes_id=None), prior=predecessor())
        self.assert_corrupt(amended_row(supersedes_id=SOURCE_TWO), prior=predecessor(source_id=SOURCE_TWO))
        self.assert_corrupt(original_row(source_id=SOURCE_TWO, version=2, supersedes_id=SOURCE_ONE),
                            prior=predecessor())
        raw = AMENDED.replace(b"Amends: DOC-ALPHA@1", b"Amends: DOC-ALPHA@2")
        self.assert_corrupt(amended_row(raw=raw, sha256=hashlib.sha256(raw).hexdigest()),
                            prior=predecessor())

    def test_predecessor_identity_context_and_historical_state_must_match(self):
        for field, value in (
            ("source_id", "SRC-" + "C" * 32), ("case_id", "CASE-BETA"),
            ("document_id", "DOC-OTHER"), ("version", 2), ("version", True),
            ("kind", "imaging"), ("event_date", date(2026, 5, 4)),
            ("event_date", "2026-05-03"), ("specimen_id", "BIOPSY-OTHER"),
            ("specimen_id", None), ("state", "current"),
        ):
            with self.subTest(field=field, value=value):
                self.assert_corrupt(amended_row(), prior=predecessor(**{field: value}))
        for field in predecessor():
            with self.subTest(missing=field):
                prior = predecessor()
                del prior[field]
                self.assert_corrupt(amended_row(), prior=prior)

    def test_parser_supported_unicode_line_separators_are_not_normalized(self):
        raw = ORIGINAL.replace(b"\n", "\u2028".encode("utf-8"))
        row = original_row(raw=raw, sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(validate_original(row, requested_case_id="CASE-ALPHA"), raw)


if __name__ == "__main__":
    unittest.main()
