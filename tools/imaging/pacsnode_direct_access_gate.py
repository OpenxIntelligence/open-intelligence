"""Observe direct anonymous WADO access after OI source invalidation.

RESEARCH / SYNTHETIC ONLY. This is a negative-security experiment, not an
authorization mechanism or an adopted PACS. Run only against the isolated
127.0.0.1 PACS after pacsnode_live_probe completed its amendment test.
Never return or persist image bytes, authentication tokens, or patient records.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import hmac
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.request import Request

from open_intelligence.store import InvalidInput
from tools.imaging import pacsnode_live_probe as pacs

_EXPECTED_SOURCE = "e9b4334477a66967d290add9e0b9afa068f59dc0"
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def _validate_prior_receipt(receipt: dict) -> dict[str, str]:
    """Require documented first-party denial *before* probing direct URLs."""
    if not isinstance(receipt, dict) or any(
        receipt.get(key) is not True for key in (
            "synthetic_only",
            "technical_evaluation_passed",
            "first_party_wado_wrong_case_refused",
            "first_party_wado_amendment_refused",
            "source_and_retrieved_objects_byte_identical",
        )
    ):
        raise InvalidInput("Valid fictional upstream and source-denial receipt required")
    if (receipt.get("source_commit") != _EXPECTED_SOURCE
            or receipt.get("candidate") != "knopkem/pacsnode standalone"
            or receipt.get("real_patient_data_used") is not False
            or receipt.get("clinical_or_full_dicomweb_approval") is not False):
        raise InvalidInput("Upstream source or synthetic research boundaries differ")
    originals = receipt.get("sop_original_sha256")
    retrieved = receipt.get("sop_returned_sha256")
    if (not isinstance(originals, dict) or not isinstance(retrieved, dict)
            or set(originals) != set(pacs.SOP_UIDS)
            or set(retrieved) != set(pacs.SOP_UIDS)):
        raise InvalidInput("Expected exactly the two fictional original SOPs")
    for sop in pacs.SOP_UIDS:
        digest = originals[sop]
        if (not isinstance(digest, str) or _SHA256.fullmatch(digest) is None
                or not isinstance(retrieved[sop], str)
                or not hmac.compare_digest(digest, retrieved[sop])):
            raise InvalidInput("The original SOP hash is unverified")
    return originals


def anonymous_get(url: str, accept: str) -> tuple[int, str, bytes]:
    """No credentials/cookies, redirects or proxies; bounded in-memory bytes."""
    request = Request(url, headers={"Accept": accept}, method="GET")
    try:
        response = pacs.OPENER.open(request, timeout=15)
    except HTTPError as exc:
        # Do not include or persist untrusted denial bodies or headers.
        status = exc.code
        exc.close()
        return status, "", b""
    with response:
        body = response.read(pacs.MAX_WIRE_SIZE + 1)
        if len(body) > pacs.MAX_WIRE_SIZE:
            raise InvalidInput("Direct WADO response exceeds the test-only bound")
        return response.status, response.headers.get("Content-Type", ""), body


def inspect_direct_access(
    prior_receipt: dict, backend_origin: str, *, fetch=None,
) -> dict:
    """Observe, never grant: one fresh anonymous URL fetch per fictional SOP.

    A 401/403 is an observed denial, NOT proof that tenant-level rights or
    revocation work. An exact anonymous 200 proves the stale SOP remains
    directly accessible in this isolated candidate configuration.
    Every other response is inconclusive; none can promote adoption.
    """
    originals = _validate_prior_receipt(prior_receipt)
    origin = pacs.loopback_origin(backend_origin)
    getter = anonymous_get if fetch is None else fetch
    observations = {}
    for sop in pacs.SOP_UIDS:
        path = (f"/wado/studies/{pacs.IMAGE_STUDY_UID}"
                f"/series/{pacs.IMAGE_SERIES_UID}/instances/{sop}")
        status, content_type, body = getter(origin + path, pacs.WADO_ACCEPT)
        if type(status) is not int or not isinstance(content_type, str) or not isinstance(body, bytes):
            raise InvalidInput("Invalid anonymous WADO test transport result")
        outcome = "inconclusive"
        observed_sha = None
        if status == 200:
            try:
                parts = pacs.multipart_dicom_parts(content_type, body)
                if len(parts) == 1:
                    observed_sha = sha256(parts[0]).hexdigest()
                    if hmac.compare_digest(observed_sha, originals[sop]):
                        outcome = "anonymous_original_access_observed"
            except (InvalidInput, ValueError):
                # Malformed data must never be misreported as authorization.
                pass
        elif status in (401, 403):
            outcome = "anonymous_request_denied"
        observations[sop] = {
            "http_status": status,
            "outcome": outcome,
            "expected_original_sha256": originals[sop],
            "observed_original_sha256": observed_sha,
        }

    statuses = [item["outcome"] for item in observations.values()]
    complete = all(x != "inconclusive" for x in statuses)
    exposed = any(x == "anonymous_original_access_observed" for x in statuses)
    return {
        "kind": "pacsnode_anonymous_direct_wado_after_source_amendment",
        "candidate": prior_receipt["candidate"],
        "source_commit": _EXPECTED_SOURCE,
        "synthetic_only": True,
        "original_source_amendment_guard_confirmed": True,
        "credential_header_sent": False,
        "direct_access_test_completed": complete,
        "anonymous_original_access_observed": exposed,
        "anonymous_original_access_observed_for_all_sops": all(
            x == "anonymous_original_access_observed" for x in statuses
        ),
        "sop_observations": observations,
        "upstream_patient_authorization_verified": False,
        "upstream_tenant_isolation_verified": False,
        "upstream_revocation_verified": False,
        "backend_adoption_approved": False,
        "real_patient_data_used": False,
        "interpretation": (
            "Direct URL test against an isolated unauthenticated synthetic PACS; "
            "a first-party source refusal does not revoke upstream objects. "
            "An observed 401/403 alone never establishes tenant authorization."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--prior-receipt", required=True)
    parser.add_argument(
        "--output", default="verification-artifacts/pacsnode-anonymous-access.json"
    )
    args = parser.parse_args()
    try:
        prior = json.loads(Path(args.prior_receipt).read_text(encoding="utf-8"))
        evidence = inspect_direct_access(prior, args.base_url)
    except Exception as exc:
        # Never reflect an upstream body, patient data or untrusted text.
        evidence = {
            "kind": "pacsnode_anonymous_direct_wado_after_source_amendment",
            "evaluation_status": "HOLD_test_error",
            "failure_type": type(exc).__name__,
            "direct_access_test_completed": False,
            "backend_adoption_approved": False,
            "real_patient_data_used": False,
        }
    output = Path(args.output)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n",
                          encoding="utf-8")
    except OSError:
        print("HOLD: anonymous direct-access receipt could not be persisted", file=sys.stderr)
        return 1
    if not evidence["direct_access_test_completed"]:
        print("HOLD: anonymous direct-access evaluation was inconclusive", file=sys.stderr)
        return 1
    if evidence["anonymous_original_access_observed"]:
        print("SECURITY HOLD: original synthetic SOP retrievable by direct anonymous URL.")
    else:
        print("Direct anonymous retrieval denied; patient/tenant authorization remains UNVERIFIED.")
    print("Backend adoption remains HOLD. Evidence file:", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
