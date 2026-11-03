"""Inspect a real synthetic PACS evaluation receipt without granting deployment approval.

This is a dependency-free, read-only governance gate for one vendor-neutral
imaging backend bake-off. It does NOT certify DICOMweb, software licensing,
security compliance, patient authorization or clinical efficacy. Passing a
technical byte roundtrip must never become a production-approval decision.
"""
from __future__ import annotations

import json
from datetime import date
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_UID = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))*\Z")
_EXPECTED_EVALUATION_SOURCE = "e9b4334477a66967d290add9e0b9afa068f59dc0"
_EXPECTED_SYNTAX = "1.2.840.10008.1.2.1"


class InvalidReceipt(ValueError):
    """The artifact is malformed or cannot justify any technical conclusion."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidReceipt(message)


def _digest_map(value: object, *, key: str) -> dict[str, str]:
    _require(isinstance(value, dict) and len(value) == 2,
             f"{key} must identify exactly two synthetic SOPs")
    result: dict[str, str] = {}
    for uid, digest in value.items():
        _require(isinstance(uid, str) and len(uid) <= 64
                 and _UID.fullmatch(uid) is not None,
                 f"{key} contains an invalid SOP UID")
        _require(isinstance(digest, str)
                 and _HEX64.fullmatch(digest) is not None,
                 f"{key} contains an invalid SHA-256")
        result[uid] = digest
    return result


def _source_bound_reads(data: dict, originals: dict, retrieved: dict) -> bool:
    """Receipt consistency only; not a signed original-ingestion authority."""
    from tools.imaging import pacsnode_live_probe as pacs
    if set(originals) != set(pacs.SOP_UIDS):
        return False
    expected = {
        'case_id': 'CASE-ALPHA', 'source_document_id': 'IMG-ALPHA',
        'source_event_date': '2026-05-17', 'source_version': 1,
        'source_sha256': sha256(pacs.IMAGING_REPORT.read_bytes()).hexdigest(),
        'study_uid': pacs.IMAGE_STUDY_UID, 'series_uid': pacs.IMAGE_SERIES_UID,
    }
    receipts = data.get('first_party_source_bound_receipts')
    if (not isinstance(receipts, dict) or set(receipts) != set(originals)
            or not all(data.get(key) is True for key in (
                'first_party_source_bound_wado_verified',
                'first_party_wado_wrong_case_refused',
                'first_party_wado_amendment_refused'))):
        return False
    anchor = None
    for uid, receipt in receipts.items():
        if not isinstance(receipt, dict):
            return False
        if any(receipt.get(key) != value for key, value in expected.items()):
            return False
        if (receipt.get('kind') != 'synthetic_source_bound_wado_read'
                or receipt.get('sop_uid') != uid
                or receipt.get('retrieved_original_dicom_sha256') != originals[uid]
                or originals[uid] != retrieved[uid]
                or receipt.get('original_bytes_verified') is not True
                or receipt.get('source_current_before_and_after') is not True):
            return False
        for field in ('source_version_id', 'source_version'):
            value = receipt.get(field)
            if type(value) is not int or value < 1:
                return False
        for field in ('case_id', 'source_document_id'):
            value = receipt.get(field)
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value):
                return False
        digest = receipt.get('source_sha256')
        if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
            return False
        for field in ('study_uid', 'series_uid'):
            value = receipt.get(field)
            if not isinstance(value, str) or len(value) > 64 or not _UID.fullmatch(value):
                return False
        try:
            day = receipt.get('source_event_date')
            if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
                return False
        except ValueError:
            return False
        current = tuple(receipt.get(field) for field in (
            'case_id', 'source_version_id', 'source_version', 'source_sha256',
            'source_document_id', 'source_event_date', 'study_uid', 'series_uid'))
        if anchor is not None and anchor != current:
            return False
        anchor = current
    return True


def _direct_access(data: dict, originals: dict) -> tuple[bool, bool]:
    observation = data.get('direct_access_after_amendment')
    if (not isinstance(observation, dict)
            or observation.get('kind') != 'oi.pacs-direct-access/1'
            or observation.get('phase') != 'after_oi_source_amendment'
            or observation.get('credential_mode') != 'none'):
        return False, False
    objects = observation.get('objects')
    if not isinstance(objects, dict) or set(objects) != set(originals):
        return False, False
    disclosure = False
    for entry in objects.values():
        if not isinstance(entry, dict) or type(entry.get('http_status')) is not int:
            return False, False
        status = entry['http_status']
        if status == 200:
            digest, count = entry.get('returned_dicom_sha256'), entry.get('returned_dicom_bytes')
            if (not isinstance(digest, str) or not _HEX64.fullmatch(digest)
                    or type(count) is not int or not 132 <= count <= 500_000):
                return False, False
            # A different returned file still demonstrates unauthenticated
            # disclosure. A free-standing success/denial boolean cannot hide it.
            disclosure = True
        elif status not in (401, 403, 404):
            return False, False
        elif entry.get('returned_dicom_sha256') is not None or entry.get('returned_dicom_bytes') != 0:
            return False, False
    return True, disclosure


def _network_confined(data: dict) -> bool:
    boundary = data.get('evaluation_network_boundary')
    if not isinstance(boundary, dict):
        return False
    from tools.imaging.network_confinement import network_evidence_is_confined
    before, after = boundary.get('before'), boundary.get('after')
    if not network_evidence_is_confined(before) or not network_evidence_is_confined(after):
        return False
    return all(before.get(key) == after.get(key) for key in (
        'parent_namespace', 'probe_namespace', 'server_namespace',
        'server_pid', 'server_start_ticks', 'expected_ports'))


def assess_pacs_receipt(data: dict[str, Any]) -> dict[str, Any]:
    """Return a reproducible HOLD classification, with separate evidence axes.

    The only supported input is an *actual* fictional PACS evaluation receipt,
    not untrusted original image bytes. Incomplete/suspicious receipt is an
    error, not a production readiness pass.
    """
    _require(isinstance(data, dict), "A structured receipt is required")
    _require(data.get("synthetic_only") is True and
             data.get("real_patient_data_used") is False,
             "Real or unverified patient inputs are not eligible")
    _require(data.get("source_commit") == _EXPECTED_EVALUATION_SOURCE,
             "Upstream source revision is not the reviewed pinned commit")
    _require(data.get("dicom_count") == 2 and
             data.get("study_count") == 1 and
             data.get("series_count") == 1,
             "Unexpected synthetic study/instance count")
    _require(data.get("stow_http_status") in (200, 201, 202),
             "No valid STOW response receipt")
    original = _digest_map(data.get("sop_original_sha256"),
                           key="sop_original_sha256")
    retrieved = _digest_map(data.get("sop_returned_sha256"),
                            key="sop_returned_sha256")
    _require(set(original) == set(retrieved),
             "A different SOP set was retrieved")
    pixel = _digest_map(data.get("sop_pixel_sha256"),
                        key="sop_pixel_sha256")
    _require(set(original) == set(pixel),
             "Pixel receipt SOP identities disagree")
    diagnostics = data.get("pixel_diagnostics")
    _require(isinstance(diagnostics, dict)
             and set(diagnostics) == set(original),
             "Missing per-object diagnostic source references")

    object_integrity = all(original[uid] == retrieved[uid] for uid in original)
    pixel_integrity = True
    for uid, entry in diagnostics.items():
        _require(isinstance(entry, dict), "Invalid pixel diagnostic")
        before = entry.get("source_pixel_sha256")
        after = entry.get("retrieved_pixel_sha256")
        _require(isinstance(before, str) and isinstance(after, str)
                 and _HEX64.fullmatch(before) is not None
                 and _HEX64.fullmatch(after) is not None,
                 "Missing actual pixel digests")
        if (before != after or after != pixel[uid]
                or entry.get("source_transfer_syntax") != _EXPECTED_SYNTAX
                or entry.get("retrieved_transfer_syntax") != _EXPECTED_SYNTAX
                or entry.get("retrieval_is_expected_uncompressed_encoding") is not True
                or entry.get("encoded_pixel_bytes_equal") is not True):
            pixel_integrity = False
    # Receipt-level claims cannot overrule contradictory hashes.
    object_integrity = (
        object_integrity
        and data.get("source_and_retrieved_objects_byte_identical") is True
        and all(data.get("exact_original_object_preserved", {}).get(uid) is True
                for uid in original)
    )
    pixel_integrity = (
        pixel_integrity
        and data.get("uncompressed_pixel_integrity_passed") is True
    )

    identity_link = (
        data.get("first_party_wrong_case_rejected") is True
        and data.get("first_party_amendment_rejected") is True
    )
    qido = data.get("qido_media_types")
    _require(isinstance(qido, dict)
             and isinstance(qido.get("study"), str)
             and isinstance(qido.get("instance"), str),
             "Missing study and instance QIDO response media evidence")
    qido_conforms = (
        qido["study"].split(";", 1)[0].strip().lower() == "application/dicom+json"
        and qido["instance"].split(";", 1)[0].strip().lower() == "application/dicom+json"
        and data.get("qido_media_type_conformant") is True
    )
    source_reads = _source_bound_reads(data, original, retrieved)
    direct_characterized, direct_disclosure = _direct_access(data, original)
    namespace_confined = _network_confined(data)
    # This schema measures anonymous access and disposable network confinement.
    # Neither a denial nor optimistic input booleans establish an authorization
    # model, tenant isolation, or production listener policy.
    server_access = False
    # Legal and clinical approval are always independent human gates.
    license_gate = data.get("upstream_license_approved") is True
    clinical_gate = data.get("clinical_validation") is True
    issues: list[str] = []
    if not object_integrity:
        issues.append("original_sop_object_integrity_unverified_or_failed")
    if not pixel_integrity:
        issues.append("uncompressed_pixel_integrity_unverified_or_failed")
    if not identity_link:
        issues.append("oi_case_source_binding_or_amendment_not_proven")
    if not source_reads:
        issues.append('source_bound_wado_read_receipts_unverified')
    if not direct_characterized:
        issues.append('direct_pacs_access_boundary_uncharacterized')
    elif direct_disclosure:
        issues.append('direct_pacs_access_survives_oi_source_amendment')
    if not namespace_confined:
        issues.append('evaluation_network_namespace_confinement_unverified')
    if not qido_conforms:
        issues.append("dicomweb_qido_media_type_nonconformant")
    if not server_access:
        issues.append("pacs_server_access_or_listener_isolation_unverified")
    if data.get("standards_conformance_verified") is not True:
        issues.append("independent_dicomweb_conformance_not_verified")
    if not license_gate:
        issues.append("source_crate_binary_asset_and_distribution_rights_not_approved")
    if not clinical_gate:
        issues.append("clinical_intended_use_not_validated")

    return {
        "classification": "HOLD_NOT_APPROVED",
        "approval_automatically_granted": False,
        "upstream_source_commit": _EXPECTED_EVALUATION_SOURCE,
        "synthetic_case_only": True,
        "technical_byte_roundtrip": object_integrity,
        "uncompressed_pixel_integrity": pixel_integrity,
        "first_party_case_and_amendment_checks": identity_link,
        "first_party_source_bound_reads": source_reads,
        "direct_access_boundary_characterized": direct_characterized,
        "anonymous_direct_object_disclosure_observed": direct_disclosure,
        "evaluation_network_namespace_confined": namespace_confined,
        "qido_dicom_json_media_type": qido_conforms,
        "pacs_service_access_controls": server_access,
        "upstream_rights_cleared": license_gate,
        "clinical_use_validated": clinical_gate,
        "open_gates": issues,
        "next_decision": (
            "Independent founder/legal/security/clinical approval is required; "
            "never infer clinical release from this engineering receipt."
        ),
    }


def assess_file(path: Path) -> dict[str, Any]:
    if path.stat().st_size > 100_000:
        raise InvalidReceipt("Evaluation receipt exceeds size limit")
    return assess_pacs_receipt(json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = assess_file(args.receipt)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    # 0 means this HOLD/negative-evidence report was produced; it does
    # NOT imply acceptance, installation or production readiness.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
