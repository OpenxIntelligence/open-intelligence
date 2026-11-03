"""Offline contracts for the pinned PACSNode native OIDC real-backend probe."""
from __future__ import annotations

from base64 import urlsafe_b64decode
from hashlib import sha256
from pathlib import Path
import json
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from open_intelligence.store import InvalidInput
from tools.imaging import pacsnode_live_probe as pacs
from tools.imaging import pacsnode_oidc_probe as probe


def decode_fixture_token(token):
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        return json.loads(urlsafe_b64decode(parts[1] + "=="))
    except (ValueError, TypeError):
        return None


class OidcConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "config.toml"
        self.key = Path(self.tmp.name) / "public.pem"
        self.path.write_text(
            '[server]\nhttp_port = 18042\n'
            '[database]\nurl = "sqlite://./data/pacsnode.db"\n'
            '[filesystem_storage]\nroot = "./data/blobs"\n'
            '[plugins]\nenabled = ["admin-dashboard", "ohif-viewer"]\n'
            '[plugins.admin-dashboard]\nroute_prefix = "/admin"\n'
        )
        self.key.write_text(
            "-----BEGIN PUBLIC KEY-----\nFICTIONAL-PLACEHOLDER\n"
            "-----END PUBLIC KEY-----\n"
        )

    def test_replaces_only_enabled_plugins_and_retains_storage(self):
        probe.prepare_oidc_config(self.path, self.key)
        from tomllib import loads
        parsed = loads(self.path.read_text())
        self.assertEqual(parsed["plugins"]["enabled"], ["basic-auth"])
        self.assertEqual(parsed["plugins"]["basic-auth"]["mode"], "oidc")
        self.assertEqual(parsed["plugins"]["basic-auth"]["public_paths"], ["/health"])
        self.assertEqual(parsed["plugins"]["basic-auth"]["oidc"]["audience"], probe.AUDIENCE)
        self.assertEqual(parsed["plugins"]["basic-auth"]["oidc"]["role_map"]["oi_viewer"], "viewer")
        self.assertEqual(parsed["database"]["url"], "sqlite://./data/pacsnode.db")
        self.assertIn("filesystem_storage", parsed)
        self.assertIn("admin-dashboard", parsed["plugins"])

    def test_rejects_ambiguous_or_nonstandalone_config(self):
        for config in (
            self.path.read_text() + "\n[plugins]\nenabled = []\n",
            self.path.read_text().replace("sqlite://", "postgres://"),
            self.path.read_text().replace('enabled = ["admin-dashboard", "ohif-viewer"]', ""),
        ):
            with self.subTest(config=config[:30]):
                self.path.write_text(config)
                with self.assertRaises(InvalidInput):
                    probe.prepare_oidc_config(self.path, self.key)
                self.path.write_text(
                    '[database]\nurl = "sqlite://a"\n[filesystem_storage]\nroot = "x"\n'
                    '[plugins]\nenabled = ["admin-dashboard", "ohif-viewer"]\n'
                )


class OidcProbeTests(unittest.TestCase):
    def setUp(self):
        self.private = Path("/not-a-real-key.pem")
        self.sop = pacs.SOP_UIDS[0]
        self.original = b"\x00"*128 + b"DICM" + b"FICTIONAL-DICOM-OBJECT"
        self.digests = {
            self.sop: sha256(self.original).hexdigest(),
            pacs.SOP_UIDS[1]: "1"*64,
        }
        self.prior = {
            "synthetic_only": True,
            "technical_evaluation_passed": True,
            "first_party_wado_wrong_case_refused": True,
            "first_party_wado_amendment_refused": True,
            "source_and_retrieved_objects_byte_identical": True,
            "clinical_or_full_dicomweb_approval": False,
            "real_patient_data_used": False,
            "candidate": "knopkem/pacsnode standalone",
            "source_commit": "e9b4334477a66967d290add9e0b9afa068f59dc0",
            "sop_original_sha256": self.digests,
            "sop_returned_sha256": self.digests.copy(),
        }

    @staticmethod
    def mock_sign(*args, **kwargs):
        return Mock(stdout=b"synthetic-signature")

    def server(self, origin, path, *, token=None, accept=None, method="GET", content=None):
        self.assertEqual(origin, "http://127.0.0.1:18042")
        if not token:
            return (401, "", b"")
        claims = decode_fixture_token(token)
        if not claims or claims["exp"] < time.time():
            return (401, "", b"")
        if path == "/auth/me":
            identity = claims["sub"]
            return (200, "application/json", json.dumps({
                "username": identity,
                "role": "viewer",
                "attributes": {k: claims[k] for k in (
                    "patient_id", "tenant_id", "purpose", "modality_access")}
            }).encode())
        if claims["roles"] != ["oi_viewer"] or claims["modality_access"] != ["CT"]:
            return (403, "", b"")
        if "/instances/" in path:
            media, body = pacs.multipart_body([self.original])
            return (200, media, body)
        return (200, "application/json", b"[]")

    def evaluate(self, *, server=None, prior=None):
        with patch.object(probe.subprocess, "run", side_effect=self.mock_sign):
            return probe.evaluate_native_oidc(
                self.prior if prior is None else prior, "http://127.0.0.1:18042",
                self.private, fetch=server if server is not None else self.server)

    def test_observes_native_auth_with_patient_scope_still_missing(self):
        results = self.evaluate()
        self.assertTrue(results["test_completed"])
        self.assertTrue(results["anonymous_routes_blocked"])
        self.assertTrue(results["authorized_reader_original_bytes_verified"])
        self.assertTrue(results["different_patient_original_bytes_exposed"])
        self.assertTrue(results["uploader_read_refused"])
        self.assertTrue(results["different_modality_read_refused"])
        self.assertTrue(results["invalid_token_refused"])
        self.assertTrue(results["expired_token_refused"])
        self.assertTrue(results["reader_token_claims_reflected_by_pacs"])
        self.assertFalse(results["patient_scope_authorization_verified"])
        self.assertFalse(results["pacs_source_amendment_revocation_verified"])
        self.assertFalse(results["backend_adoption_approved"])
        self.assertNotIn("DICM", json.dumps(results))
        self.assertNotIn("synthetic-signature", json.dumps(results))

    def test_missing_anonymous_guard_fails_even_with_valid_authenticated_bytes(self):
        def exposed(origin, path, *, token=None, **kwargs):
            if not token:
                return (200, "application/json", b"[]")
            return self.server(origin, path, token=token, **kwargs)
        results = self.evaluate(server=exposed)
        self.assertFalse(results["anonymous_routes_blocked"])
        self.assertFalse(results["test_completed"])
        self.assertFalse(results["backend_adoption_approved"])

    def test_modified_original_refuses_valid_reader_success(self):
        def changed(origin, path, *, token=None, **kwargs):
            result = self.server(origin, path, token=token, **kwargs)
            if token and "/instances/" in path and result[0] == 200:
                media, body = pacs.multipart_body([self.original + b"x"])
                return 200, media, body
            return result
        results = self.evaluate(server=changed)
        self.assertFalse(results["authorized_reader_original_bytes_verified"])
        self.assertFalse(results["test_completed"])

    def test_cross_patient_denial_cannot_be_misreported_as_policy_clearance(self):
        def patient_aware(origin, path, *, token=None, **kwargs):
            claims = decode_fixture_token(token) if token else None
            if claims and claims["patient_id"] == "FICTIONAL-CASE-BETA":
                return (403, "", b"")
            return self.server(origin, path, token=token, **kwargs)
        results = self.evaluate(server=patient_aware)
        self.assertTrue(results["test_completed"])
        self.assertFalse(results["different_patient_original_bytes_exposed"])
        # A 403 test response alone is not an integration with OI rights.
        self.assertFalse(results["patient_scope_authorization_verified"])

    def test_expired_token_and_issuer_are_in_signed_claims(self):
        with patch.object(probe.subprocess, "run", side_effect=self.mock_sign) as sign:
            token = probe.signed_fixture_token(
                self.private, identity="oi-reader-alpha",
                patient="FICTIONAL-CASE-ALPHA", now=1_700_000_000,
                seconds_to_expiry=-300)
        claims = decode_fixture_token(token)
        self.assertEqual(claims["iss"], probe.ISSUER)
        self.assertEqual(claims["aud"], probe.AUDIENCE)
        self.assertEqual(claims["exp"], 1_699_999_700)
        self.assertEqual(claims["roles"], ["oi_viewer"])
        self.assertEqual(claims["modality_access"], ["CT"])
        self.assertEqual(sign.call_count, 1)
        self.assertNotIn("PRIVATE KEY", token)

    def test_invalid_prior_receipt_refuses_all_network_calls(self):
        called = Mock()
        prior = {**self.prior, "first_party_wado_amendment_refused": False}
        with self.assertRaises(InvalidInput):
            self.evaluate(server=called, prior=prior)
        called.assert_not_called()

    def test_nonloopback_backend_refused(self):
        with patch.object(probe.subprocess, "run", side_effect=self.mock_sign):
            with self.assertRaises(InvalidInput):
                probe.evaluate_native_oidc(self.prior, "https://example.invalid", self.private)
    
    def test_output_never_includes_issued_signed_tokens(self):
        results = self.evaluate()
        self.assertFalse(results["backend_adoption_approved"])
        self.assertNotIn("Authorization", json.dumps(results))
        self.assertNotIn("Bearer", json.dumps(results))


if __name__ == "__main__":
    unittest.main()
