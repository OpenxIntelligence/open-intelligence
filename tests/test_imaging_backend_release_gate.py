"""Adversarial tests for source-grounded fictional PACS acceptance decisions."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.imaging.assess_pacsnode_receipt import (
    InvalidReceipt, assess_pacs_receipt, assess_file,
)

RECEIPT = (Path(__file__).resolve().parents[1]
           / "examples" / "synthetic" / "pacsnode_evidence_receipt_41555864030.json")


class PacsAcceptanceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(RECEIPT.read_text(encoding="utf-8"))

    def check(self, d=None):
        return assess_pacs_receipt(deepcopy(self.original if d is None else d))

    def test_actual_success_cannot_be_mislabeled_as_approved(self):
        result = assess_file(RECEIPT)
        self.assertEqual(result["classification"], "HOLD_NOT_APPROVED")
        self.assertFalse(result["approval_automatically_granted"])
        self.assertTrue(result["technical_byte_roundtrip"])
        self.assertTrue(result["uncompressed_pixel_integrity"])
        self.assertTrue(result["first_party_case_and_amendment_checks"])
        self.assertFalse(result["qido_dicom_json_media_type"])
        self.assertFalse(result["pacs_service_access_controls"])
        self.assertFalse(result["upstream_rights_cleared"])
        self.assertFalse(result["clinical_use_validated"])
        self.assertEqual(
            result["upstream_source_commit"],
            "e9b4334477a66967d290add9e0b9afa068f59dc0",
        )
        self.assertIn("dicomweb_qido_media_type_nonconformant", result["open_gates"])
        self.assertIn("pacs_server_access_or_listener_isolation_unverified", result["open_gates"])

    def test_forged_success_booleans_do_not_override_mismatched_digests(self):
        d = deepcopy(self.original)
        uid = next(iter(d["sop_returned_sha256"]))
        d["sop_returned_sha256"][uid] = "0"*64
        d["source_and_retrieved_objects_byte_identical"] = True
        d["exact_original_object_preserved"][uid] = True
        result = self.check(d)
        self.assertFalse(result["technical_byte_roundtrip"])
        self.assertIn("original_sop_object_integrity_unverified_or_failed", result["open_gates"])

    def test_pixel_encoding_integrity_must_match_actual_digests(self):
        d = deepcopy(self.original)
        uid = next(iter(d["pixel_diagnostics"]))
        d["pixel_diagnostics"][uid]["retrieved_pixel_sha256"] = "f"*64
        d["uncompressed_pixel_integrity_passed"] = True
        result = self.check(d)
        self.assertFalse(result["uncompressed_pixel_integrity"])
        self.assertIn("uncompressed_pixel_integrity_unverified_or_failed", result["open_gates"])

    def test_claimed_qido_success_does_not_hide_wrong_media_type(self):
        d = deepcopy(self.original)
        d["qido_media_type_conformant"] = True
        result = self.check(d)
        self.assertFalse(result["qido_dicom_json_media_type"])

    def test_wrong_case_or_revocation_missing_keeps_approval_blocked(self):
        for field in ("first_party_wrong_case_rejected", "first_party_amendment_rejected"):
            d = deepcopy(self.original)
            d[field] = False
            with self.subTest(field=field):
                result = self.check(d)
                self.assertFalse(result["first_party_case_and_amendment_checks"])

    def test_unpinned_source_or_nonfictional_data_rejected(self):
        for key, value in (
            ("source_commit", "HEAD"),
            ("source_commit", "a"*40),
            ("synthetic_only", False),
            ("real_patient_data_used", True),
            ("real_patient_data_used", None),
        ):
            d = deepcopy(self.original)
            d[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(InvalidReceipt):
                self.check(d)

    def test_missing_or_ambiguous_sop_set_is_invalid(self):
        for key in ("sop_original_sha256", "sop_returned_sha256", "sop_pixel_sha256"):
            d = deepcopy(self.original)
            d[key] = {}
            with self.subTest(key=key), self.assertRaises(InvalidReceipt):
                self.check(d)
        d = deepcopy(self.original)
        d["sop_returned_sha256"]["2.25.5"] = d["sop_returned_sha256"].pop(
            next(iter(d["sop_returned_sha256"]))
        )
        with self.assertRaises(InvalidReceipt):
            self.check(d)

    def test_even_optimistic_claims_still_require_independent_release_review(self):
        d = deepcopy(self.original)
        for field in (
            "qido_media_type_conformant", "backend_listener_isolation_verified",
            "pacs_authentication_verified", "pacs_tenant_isolation_verified",
            "upstream_license_approved", "clinical_validation",
            "standards_conformance_verified"
        ):
            d[field] = True
        d["qido_media_types"] = {
            "study": "application/dicom+json",
            "instance": "application/dicom+json",
        }
        result = self.check(d)
        self.assertEqual(result["classification"], "HOLD_NOT_APPROVED")
        self.assertFalse(result["approval_automatically_granted"])
        self.assertEqual(result["open_gates"], [])
        self.assertIn("Independent", result["next_decision"])

    def test_nonmatching_transfer_syntax_holds_pixel_claim(self):
        d = deepcopy(self.original)
        uid = next(iter(d["pixel_diagnostics"]))
        d["pixel_diagnostics"][uid]["retrieved_transfer_syntax"] = "1.2.840.10008.1.2.4.90"
        result = self.check(d)
        self.assertFalse(result["uncompressed_pixel_integrity"])

if __name__ == "__main__":
    unittest.main()
