"""Read-only, version-bound WADO acceptance for fictional imaging data.

RESEARCH/TEST ONLY. This is NOT an authorization system. The caller supplies
an OI case/source binding and an original object digest. No user/role/consent
is authenticated here; this module MUST NOT be exposed as a patient endpoint.
Its job is to refuse stale or cross-case source bindings before and after
an actual *loopback-only* backend retrieval, and retain inspectable receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import re
from typing import Callable

from open_intelligence.imaging_backend_contract import check_dicomweb_metadata
from open_intelligence.store import CaseStore, InvalidInput
from tools.imaging import pacsnode_live_probe as pacs

_SHA = re.compile(r"[a-f0-9]{64}\Z")
_UID = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))*\Z")


@dataclass(frozen=True)
class SyntheticWadoBinding:
    case_id: str
    source_version_id: int
    source_sha256: str
    study_uid: str
    series_uid: str
    sop_uid: str
    original_dicom_sha256: str


def _validate_binding(binding: SyntheticWadoBinding) -> None:
    if not isinstance(binding, SyntheticWadoBinding):
        raise InvalidInput("An explicit fictional imaging source binding is required")
    if not isinstance(binding.case_id, str) or not binding.case_id:
        raise InvalidInput("Case ID is required")
    if type(binding.source_version_id) is not int or binding.source_version_id < 1:
        raise InvalidInput("Source version ID must be a positive integer")
    for value in (binding.source_sha256, binding.original_dicom_sha256):
        if not isinstance(value, str) or _SHA.fullmatch(value) is None:
            raise InvalidInput("An exact original SHA-256 is required")
    for value in (binding.study_uid, binding.series_uid, binding.sop_uid):
        if (not isinstance(value, str) or len(value) > 64
                or _UID.fullmatch(value) is None):
            raise InvalidInput("Invalid DICOM object identity")


def _current_source(store: CaseStore, binding: SyntheticWadoBinding) -> dict:
    # One existing, case-scoped record read; no new patient/source ledger.
    state = store.state(binding.case_id)
    source = next(
        (source for source in state["sources"]
         if source["id"] == binding.source_version_id
         and source["kind"] == "imaging"
         and source["state"] == "current"),
        None,
    )
    if source is None or not hmac.compare_digest(
        source["sha256"], binding.source_sha256
    ):
        raise InvalidInput("stale or wrong-case original imaging source")
    return source


def _canonical_metadata(binding: SyntheticWadoBinding, source: dict) -> dict:
    def tag(vr: str, value: str) -> dict:
        return {"vr": vr, "Value": [value]}
    return {
        "oi_test_case_id": binding.case_id,
        "oi_test_source_version_id": binding.source_version_id,
        "0020000D": tag("UI", binding.study_uid),
        "0020000E": tag("UI", binding.series_uid),
        "00080018": tag("UI", binding.sop_uid),
        "00080020": tag("DA", source["event_date"].replace("-", "")),
        "00080060": tag("CS", "CT"),
    }


def read_source_bound_wado(
    store: CaseStore,
    binding: SyntheticWadoBinding,
    backend_origin: str,
    *,
    fetch: Callable[[str, str], tuple[int, str, bytes]] | None = None,
) -> dict:
    """Return a digest-only receipt; never return patient/image bytes.

    The optional fetch callback is **test injection**, not a runtime plugin
    system. The default enforces PACSNode probe's no-proxy/no-redirect
    loopback HTTP implementation. No untrusted user controls the URL path.
    The before/after check stops publication of already-invalid source data
    on a concurrent report amendment; it cannot revoke upstream PACS bytes.
    """
    _validate_binding(binding)
    origin = pacs.loopback_origin(backend_origin)
    source_before = _current_source(store, binding)
    metadata = _canonical_metadata(binding, source_before)
    # Reuse the independently tested current source/UID metadata contract.
    check_dicomweb_metadata(store, binding.case_id, [metadata])

    path = (f"/wado/studies/{binding.study_uid}/series/{binding.series_uid}"
            f"/instances/{binding.sop_uid}")
    getter = fetch if fetch is not None else (
        lambda url, accept: pacs._request(url, accept=accept)
    )
    status, content_type, body = getter(origin + path, pacs.WADO_ACCEPT)
    if status != 200:
        raise InvalidInput("WADO retrieval did not return HTTP 200")
    parts = pacs.multipart_dicom_parts(content_type, body)
    if len(parts) != 1:
        raise InvalidInput("Expected exactly one original DICOM object")
    digest = sha256(parts[0]).hexdigest()
    if not hmac.compare_digest(digest, binding.original_dicom_sha256):
        raise InvalidInput("WADO original object bytes differ from source digest")

    # The second check is essential: do not return a valid old object as a
    # current patient result if its source was amended during HTTP transfer.
    source_after = _current_source(store, binding)
    if (source_before["id"], source_before["version"],
        source_before["sha256"]) != (
        source_after["id"], source_after["version"], source_after["sha256"]
    ):
        raise InvalidInput("original imaging report changed during retrieval")
    check_dicomweb_metadata(store, binding.case_id, [metadata])

    return {
        "kind": "synthetic_source_bound_wado_read",
        "case_id": binding.case_id,
        "source_version_id": binding.source_version_id,
        "source_version": source_after["version"],
        "source_sha256": source_after["sha256"],
        "source_document_id": source_after["document_id"],
        "source_event_date": source_after["event_date"],
        "study_uid": binding.study_uid,
        "series_uid": binding.series_uid,
        "sop_uid": binding.sop_uid,
        "retrieved_original_dicom_sha256": digest,
        "original_bytes_verified": True,
        "source_current_before_and_after": True,
        "upstream_object_access_revoked": False,
        "caller_authenticated": False,
        "case_authorization_verified": False,
        "clinical_review_state": "not_performed",
        "pacs_adoption_approved": False,
        "disclaimer": (
            "Synthetic research-only source and byte freshness proof. "
            "Not user authentication, consent, DICOM server ACL, "
            "clinical imaging, or external-object revocation."
        ),
    }
