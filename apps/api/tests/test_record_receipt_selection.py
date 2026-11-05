"""Wire contract for linking the exact original selected in Records."""
import unittest

from pydantic import ValidationError

from oi_api.patients import ReceiveRecordRequest


class RecordReceiptSelectionTests(unittest.TestCase):
    command = {"synthetic": True, "case_id": "CASE-ALPHA", "source_id": "SRC-" + "A" * 32}
    digest = "a" * 64

    def test_selected_version_and_digest_are_accepted_together(self):
        pinned = ReceiveRecordRequest(**self.command, expected_original={"version": 2, "sha256": self.digest})
        self.assertEqual((pinned.expected_original.version, pinned.expected_original.sha256), (2, self.digest))

    def test_earlier_clients_can_still_submit_an_exact_source_id(self):
        self.assertIsNone(ReceiveRecordRequest(**self.command).expected_original)

    def test_malformed_or_partial_pins_are_rejected(self):
        for pin in ({"version": 1}, {"sha256": self.digest}, {"version": True, "sha256": self.digest},
                    {"version": 0, "sha256": self.digest}, {"version": 1, "sha256": self.digest.upper()}):
            with self.subTest(pin=pin), self.assertRaises(ValidationError):
                ReceiveRecordRequest(**self.command, expected_original=pin)
