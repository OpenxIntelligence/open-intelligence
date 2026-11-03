"""Inspect a real synthetic PACS evaluation receipt without granting deployment approval.

This is a dependency-free, read-only governance gate for one vendor-neutral
imaging backend bake-off. It does NOT certify DICOMweb, software licensing,
security compliance, patient authorization or clinical efficacy. Passing a
technical byte roundtrip must never become a production-approval decision.
"""
from __future__ import annotations

import json
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
    server_access = (
        data.get("pacs_authentication_verified") is True
        and data.get("pacs_tenant_isolation_verified") is True
        and data.get("backend_listener_isolation_verified") is True
    )
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
