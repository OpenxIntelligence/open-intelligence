"""Pinned PACSNode native OIDC acceptance, synthetic-only / RESEARCH HOLD.

This exercises the upstream built-in auth middleware against actual local WADO,
QIDO and REST routes; it is NOT an Open Intelligence patient permission layer.
A role-allowed reader with another fictional patient claim may still retrieve
the same SOP. That condition must be preserved as negative security evidence.
No real records, tokens, private keys or DICOM bytes enter output artifacts.
"""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import hmac
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import tomllib
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request

from open_intelligence.store import InvalidInput
from tools.imaging import pacsnode_live_probe as pacs
from tools.imaging.pacsnode_direct_access_gate import _validate_prior_receipt

ISSUER = "https://oi-fixture-issuer.example.invalid"
AUDIENCE = "oi-synthetic-pacs"
_MAX_RESPONSE = pacs.MAX_WIRE_SIZE


def prepare_oidc_config(config_path: Path, public_key_path: Path) -> None:
    """Activate only the already-compiled upstream auth plugin in test config.

    Never create production credentials or replace the application auth owner.
    The public verification key is ephemeral and exists only in runner temp.
    """
    original = config_path.read_text(encoding="utf-8")
    public_key = public_key_path.read_text(encoding="ascii").strip()
    if (original.count("[plugins]\n") != 1
            or "[plugins.basic-auth]" in original
            or len(re.findall(r'(?m)^enabled = \[[^\n]*\]$', original)) != 1
            or not public_key.startswith("-----BEGIN PUBLIC KEY-----")
            or not public_key.endswith("-----END PUBLIC KEY-----")
            or "'" in public_key):
        raise InvalidInput("Unexpected fictional PACS config or OIDC test key")
    # Reuse the generated standalone SQLite/filesystem configuration. Remove
    # the enabled static viewers/admin assets from this *auth* experiment.
    secured = re.sub(
        r'(?m)^enabled = \[[^\n]*\]$', 'enabled = ["basic-auth"]',
        original, count=1,
    )
    secured += (
        "\n[plugins.basic-auth]\n"
        'mode = "oidc"\n'
        'public_paths = ["/health"]\n'
        "\n[plugins.basic-auth.oidc]\n"
        f'issuer = "{ISSUER}"\n'
        f'audience = "{AUDIENCE}"\n'
        "public_key_pem = '''" + public_key + "\n'''\n"
        'role_claim = "roles"\n'
        'default_role = "uploader"\n'
        'role_map = { oi_viewer = "viewer", oi_uploader = "uploader" }\n'
        'attributes_claims = ["modality_access", "patient_id", "tenant_id", "purpose"]\n'
    )
    try:
        parsed = tomllib.loads(secured)
        conf = parsed["plugins"]["basic-auth"]
        if (parsed["plugins"]["enabled"] != ["basic-auth"]
                or conf["mode"] != "oidc"
                or conf["oidc"]["audience"] != AUDIENCE
                or not parsed["database"]["url"].startswith("sqlite://")
                or "filesystem_storage" not in parsed):
            raise InvalidInput("OIDC test config lost standalone isolation")
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidInput("Unable to validate pinned synthetic auth configuration") from exc
    config_path.write_text(secured, encoding="utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def signed_fixture_token(
    private_key: Path,
    *,
    identity: str,
    patient: str,
    role: str = "oi_viewer",
    modalities: tuple[str, ...] = ("CT",),
    seconds_to_expiry: int = 600,
    now: int | None = None,
) -> str:
    """Sign an ephemeral RS256 JWT using openssl; never log or export it."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identity):
        raise InvalidInput("Invalid fictional OIDC identity")
    at = int(time.time()) if now is None else now
    claims = {
        "iss": ISSUER, "aud": AUDIENCE, "sub": identity,
        "preferred_username": identity, "iat": at - 60,
        "nbf": at - 60, "exp": at + seconds_to_expiry,
        "roles": [role], "modality_access": list(modalities),
        "patient_id": patient, "tenant_id": "OI-FICTIONAL-ORG",
        "purpose": "synthetic-research",
    }
    header = {"alg": "RS256", "typ": "JWT"}
    message = ".".join(_b64(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())
                       for obj in (header, claims))
    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(private_key)],
        input=message.encode("ascii"), capture_output=True, check=True,
    )
    return message + "." + _b64(result.stdout)


def bounded_http(
    origin: str, path: str, *,
    token: str | None = None,
    accept: str = "application/dicom+json",
    method: str = "GET",
    content: bytes | None = None,
) -> tuple[int, str, bytes]:
    """Direct PACS connection, with no proxy/redirect and no cookie jar."""
    base = pacs.loopback_origin(origin)
    if not path.startswith("/") or "//" in path or "\\" in path:
        raise InvalidInput("Untrusted PACS path")
    headers = {"Accept": accept}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if method == "POST":
        headers["Content-Type"] = 'multipart/related; type="application/dicom"'
    request = Request(base + path, headers=headers, method=method, data=content)
    try:
        response = pacs.OPENER.open(request, timeout=15)
    except HTTPError as exc:
        code = exc.code
        exc.close()
        # Never expose response bodies/URLs/authorization headers in errors.
        return code, "", b""
    with response:
        body = response.read(_MAX_RESPONSE + 1)
        if len(body) > _MAX_RESPONSE:
            raise InvalidInput("PACS auth response exceeded bounded synthetic limit")
        return response.status, response.headers.get("Content-Type", ""), body


def _original_ok(status: int, media: str, body: bytes, expected_hash: str) -> bool:
    if status != 200:
        return False
    try:
        parts = pacs.multipart_dicom_parts(media, body)
    except (InvalidInput, ValueError):
        return False
    return len(parts) == 1 and hmac.compare_digest(sha256(parts[0]).hexdigest(), expected_hash)


def evaluate_native_oidc(
    prior_receipt: dict, origin: str, private_key: Path, *, fetch=bounded_http
) -> dict:
    """Probe actual PACS OIDC enforcement using previously stored synthetic SOPs.

    Test status codes are observations, not patient authorization proofs.
    """
    originals = _validate_prior_receipt(prior_receipt)
    origin = pacs.loopback_origin(origin)
    sop = pacs.SOP_UIDS[0]
    source = f"/wado/studies/{pacs.IMAGE_STUDY_UID}/series/{pacs.IMAGE_SERIES_UID}/instances/{sop}"
    qido = "/wado/studies?" + urlencode({"StudyInstanceUID": pacs.IMAGE_STUDY_UID})
    legacy = "/wado?" + urlencode({
        "requestType": "WADO", "studyUID": pacs.IMAGE_STUDY_UID,
        "seriesUID": pacs.IMAGE_SERIES_UID, "objectUID": sop,
    })
    fixed = [
        ("wado_instance", source),
        ("wado_study", f"/wado/studies/{pacs.IMAGE_STUDY_UID}"),
        ("wado_metadata", f"/wado/studies/{pacs.IMAGE_STUDY_UID}/metadata"),
        ("wado_legacy", legacy),
        ("qido", qido),
        ("rest", "/api/studies"),
    ]
    anonym = {}
    for name, path in fixed:
        status, _, _ = fetch(origin, path, accept=pacs.WADO_ACCEPT)
        anonym[name] = status
    stow_status, _, _ = fetch(origin, "/wado/studies", method="POST", content=b"")
    anonym["stow"] = stow_status

    reader = signed_fixture_token(
        private_key, identity="oi-reader-alpha", patient="FICTIONAL-CASE-ALPHA")
    wrong_patient = signed_fixture_token(
        private_key, identity="oi-reader-beta", patient="FICTIONAL-CASE-BETA")
    wrong_modality = signed_fixture_token(
        private_key, identity="oi-reader-us", patient="FICTIONAL-CASE-ALPHA",
        modalities=("US",))
    uploader = signed_fixture_token(
        private_key, identity="oi-uploader", patient="FICTIONAL-CASE-ALPHA",
        role="oi_uploader")
    expired = signed_fixture_token(
        private_key, identity="oi-expired", patient="FICTIONAL-CASE-ALPHA",
        seconds_to_expiry=-300, now=int(time.time())-300)

    reader_reply = fetch(origin, source, token=reader, accept=pacs.WADO_ACCEPT)
    wrong_patient_reply = fetch(
        origin, source, token=wrong_patient, accept=pacs.WADO_ACCEPT)
    different_modality_reply = fetch(
        origin, source, token=wrong_modality, accept=pacs.WADO_ACCEPT)
    uploader_reply = fetch(origin, source, token=uploader, accept=pacs.WADO_ACCEPT)
    expired_reply = fetch(origin, source, token=expired, accept=pacs.WADO_ACCEPT)
    invalid_reply = fetch(origin, source, token="not-a-valid-token", accept=pacs.WADO_ACCEPT)

    me_status, _, me_body = fetch(origin, "/auth/me", token=reader, accept="application/json")
    me_verified = False
    if me_status == 200:
        try:
            me = json.loads(me_body)
            attrs = me.get("attributes", {})
            me_verified = (
                me.get("role") == "viewer"
                and me.get("username") == "oi-reader-alpha"
                and attrs.get("patient_id") == "FICTIONAL-CASE-ALPHA"
                and attrs.get("tenant_id") == "OI-FICTIONAL-ORG"
                and attrs.get("purpose") == "synthetic-research"
                and attrs.get("modality_access") == ["CT"]
            )
        except (ValueError, AttributeError, TypeError):
            pass

    anonymous_blocked = all(status in (401, 403) for status in anonym.values())
    authorized = _original_ok(*reader_reply, originals[sop])
    cross_patient = _original_ok(*wrong_patient_reply, originals[sop])
    role_blocked = uploader_reply[0] == 403
    modality_blocked = different_modality_reply[0] == 403
    expired_blocked = expired_reply[0] == 401
    invalid_blocked = invalid_reply[0] == 401
    complete = all([anonymous_blocked, authorized, role_blocked,
                    modality_blocked, expired_blocked, invalid_blocked,
                    me_verified])
    return {
        "kind": "pacsnode_pinned_builtin_oidc_security_evaluation",
        "candidate": prior_receipt["candidate"],
        "source_commit": prior_receipt["source_commit"],
        "synthetic_only": True,
        "native_oidc_auth_plugin_tested": True,
        "test_completed": complete,
        "anonymous_request_statuses": anonym,
        "anonymous_routes_blocked": anonymous_blocked,
        "authorized_reader_original_bytes_verified": authorized,
        "reader_token_claims_reflected_by_pacs": me_verified,
        "uploader_wado_http_status": uploader_reply[0],
        "uploader_read_refused": role_blocked,
        "different_modality_wado_http_status": different_modality_reply[0],
        "different_modality_read_refused": modality_blocked,
        "expired_token_http_status": expired_reply[0],
        "expired_token_refused": expired_blocked,
        "invalid_token_http_status": invalid_reply[0],
        "invalid_token_refused": invalid_blocked,
        "different_patient_token_wado_http_status": wrong_patient_reply[0],
        "different_patient_original_bytes_exposed": cross_patient,
        "patient_scope_authorization_verified": False,
        "tenant_scope_authorization_verified": False,
        "purpose_authorization_verified": False,
        "first_party_original_source_guard_verified_in_prior_run": True,
        "pacs_source_amendment_revocation_verified": False,
        "listener_network_isolation_verified": False,
        "dimse_entrypoints_secured_verified": False,
        "dicomweb_full_conformance_verified": False,
        "upstream_rights_approved": False,
        "clinical_validation": False,
        "backend_adoption_approved": False,
        "real_patient_data_used": False,
        "interpretation": (
            "Upstream OIDC authentication is distinct from patient/case rights. "
            "The fictional patient_id claim is not a first-party clinical grant. "
            "A permitted PACS role can read stored resources unless PACS enforces "
            "patient- and purpose-level resource policy; keep release on HOLD."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--prior-receipt", required=True)
    parser.add_argument("--private-key", required=True)
    parser.add_argument("--output", default="verification-artifacts/pacsnode-oidc-read.json")
    args = parser.parse_args()
    try:
        prior = json.loads(Path(args.prior_receipt).read_text(encoding="utf-8"))
        result = evaluate_native_oidc(prior, args.base_url, Path(args.private_key))
    except Exception as error:
        result = {
            "kind": "pacsnode_pinned_builtin_oidc_security_evaluation",
            "test_completed": False, "failure_type": type(error).__name__,
            "backend_adoption_approved": False, "real_patient_data_used": False,
        }
    try:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        print("HOLD: unable to preserve OIDC probe status", file=sys.stderr)
        return 1
    if not result["test_completed"]:
        print("HOLD: native PACS OIDC test did not establish expected controls", file=sys.stderr)
        return 1
    if result["different_patient_original_bytes_exposed"]:
        print("SECURITY HOLD: cross-patient token retrieved fictional original despite OIDC.")
    else:
        print("Cross-patient direct read denied or changed; patient-policy equivalence unverified.")
    print("Native OIDC route controls verified only for synthetic test; adoption HOLD.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
