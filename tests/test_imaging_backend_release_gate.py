"""Adversarial tests for source-grounded fictional PACS acceptance decisions."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.imaging import pacsnode_live_probe as pacs

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

    def with_source_reads(self):
        data = deepcopy(self.original)
        data.update(first_party_source_bound_wado_verified=True,
                    first_party_wado_wrong_case_refused=True,
                    first_party_wado_amendment_refused=True)
        data['first_party_source_bound_receipts'] = {
            uid: {'kind': 'synthetic_source_bound_wado_read',
                  'case_id': 'CASE-ALPHA', 'source_version_id': 1,
                  'source_version': 1, 'source_sha256': sha256(pacs.IMAGING_REPORT.read_bytes()).hexdigest(),
                  'source_document_id': 'IMG-ALPHA',
                  'source_event_date': '2026-05-17',
                  'study_uid': pacs.IMAGE_STUDY_UID,
                  'series_uid': pacs.IMAGE_SERIES_UID,
                  'sop_uid': uid, 'retrieved_original_dicom_sha256': digest,
                  'original_bytes_verified': True,
                  'source_current_before_and_after': True,
                  'caller_authenticated': False,
                  'case_authorization_verified': False}
            for uid, digest in data['sop_original_sha256'].items()
        }
        return data

    def test_legacy_byte_success_does_not_prove_new_source_read_boundary(self):
        result = self.check()
        self.assertIs(result.get('first_party_source_bound_reads'), False)
        self.assertTrue(result['technical_byte_roundtrip'])
        self.assertIn('source_bound_wado_read_receipts_unverified', result['open_gates'])

    def test_exact_per_object_source_receipts_are_required(self):
        data = self.with_source_reads()
        self.assertIs(self.check(data).get('first_party_source_bound_reads'), True)
        uid = next(iter(data['sop_original_sha256']))
        for field, value in [('sop_uid', '9.9.1'), ('source_version_id', True),
                             ('source_sha256', 'short'), ('case_id', 'CASE-OTHER'),
                             ('retrieved_original_dicom_sha256', '0' * 64),
                             ('source_current_before_and_after', 'true')]:
            changed = deepcopy(data)
            changed['first_party_source_bound_receipts'][uid][field] = value
            with self.subTest(field=field):
                self.assertIs(self.check(changed).get('first_party_source_bound_reads'), False)
        del data['first_party_source_bound_receipts'][uid]
        self.assertIs(self.check(data).get('first_party_source_bound_reads'), False)

    def test_anonymous_disclosure_overrides_optimistic_security_claims(self):
        data = self.with_source_reads()
        data.update(pacs_authentication_verified=True, pacs_tenant_isolation_verified=True,
                    backend_listener_isolation_verified=True,
                    pacs_direct_object_access_revoked=True)
        data['direct_access_after_amendment'] = {
            'kind': 'oi.pacs-direct-access/1', 'phase': 'after_oi_source_amendment',
            'credential_mode': 'none', 'anonymous_dicom_returned': False,
            'backend_authorization_verified': True,
            'objects': {uid: {'http_status': 200, 'returned_dicom_sha256': 'a' * 64,
                             'returned_dicom_bytes': 1024,
                             'original_bytes_match': False}
                        for uid in data['sop_original_sha256']}}
        result = self.check(data)
        self.assertIs(result.get('anonymous_direct_object_disclosure_observed'), True)
        self.assertFalse(result['pacs_service_access_controls'])
        self.assertIn('direct_pacs_access_survives_oi_source_amendment', result['open_gates'])

    def test_consistently_wrong_source_anchor_is_not_this_evaluation(self):
        for field, value in [('case_id', 'CASE-OTHER'), ('source_document_id', 'UNRELATED'),
                             ('study_uid', '9.9.1'), ('series_uid', '9.9.2'),
                             ('source_sha256', 'a' * 64), ('source_version', 2)]:
            data = self.with_source_reads()
            for entry in data['first_party_source_bound_receipts'].values():
                entry[field] = value
            with self.subTest(field=field):
                self.assertFalse(self.check(data)['first_party_source_bound_reads'])

    def test_anonymous_denials_do_not_prove_service_access_controls(self):
        for status in (401, 403, 404):
            data = self.with_source_reads()
            data.update(pacs_authentication_verified=True, pacs_tenant_isolation_verified=True,
                        backend_listener_isolation_verified=True)
            data['direct_access_after_amendment'] = {
                'kind': 'oi.pacs-direct-access/1', 'phase': 'after_oi_source_amendment',
                'credential_mode': 'none', 'backend_authorization_verified': False,
                'objects': {uid: {'http_status': status, 'returned_dicom_sha256': None,
                                 'returned_dicom_bytes': 0}
                            for uid in data['sop_original_sha256']}}
            with self.subTest(status=status):
                result = self.check(data)
                self.assertTrue(result['direct_access_boundary_characterized'])
                self.assertFalse(result['pacs_service_access_controls'])

    def test_new_schema_receipt_is_assessable_in_a_fresh_module_process(self):
        data = self.with_source_reads()
        data['evaluation_network_boundary'] = {'before': {}, 'after': {}}
        root = RECEIPT.parents[2]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fictional.json'
            path.write_text(json.dumps(data))
            result = subprocess.run(
                [sys.executable, '-m', 'tools.imaging.assess_pacsnode_receipt', str(path)],
                cwd=root, env={**os.environ, 'PYTHONPATH': str(root / 'src')},
                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['evaluation_network_namespace_confined'])

    def test_missing_direct_probe_or_namespace_cannot_be_replaced_by_flags(self):
        data = self.with_source_reads()
        data.update(evaluation_network_namespace_confined=True,
                    pacs_authentication_verified=True, pacs_tenant_isolation_verified=True,
                    backend_listener_isolation_verified=True)
        result = self.check(data)
        self.assertIs(result.get('evaluation_network_namespace_confined'), False)
        self.assertIs(result.get('direct_access_boundary_characterized'), False)
        self.assertFalse(result['pacs_service_access_controls'])

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
        self.assertIn('source_bound_wado_read_receipts_unverified', result['open_gates'])
        self.assertIn('direct_pacs_access_boundary_uncharacterized', result['open_gates'])
        self.assertIn('evaluation_network_namespace_confinement_unverified', result['open_gates'])
        self.assertIn("Independent", result["next_decision"])

    def test_nonmatching_transfer_syntax_holds_pixel_claim(self):
        d = deepcopy(self.original)
        uid = next(iter(d["pixel_diagnostics"]))
        d["pixel_diagnostics"][uid]["retrieved_transfer_syntax"] = "1.2.840.10008.1.2.4.90"
        result = self.check(d)
        self.assertFalse(result["uncompressed_pixel_integrity"])

if __name__ == "__main__":
    unittest.main()
